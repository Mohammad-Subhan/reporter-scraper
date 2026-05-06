"""
BigQuery persistence mirroring the Airtable Reporters table.

Schema: same field names as Airtable, plus record_id (stable row key for updates).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from dotenv import load_dotenv

load_dotenv()

# Same Pub #… column naming as Airtable / scrapers (en dash U+2013).
MAX_PUB_ARTICLES = 10

PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or ""
DATASET_ID = (os.environ.get("BIGQUERY_DATASET") or "").strip() or "reporter_scraper"
TABLE_ID = (os.environ.get("BIGQUERY_TABLE") or "").strip() or "Reporters"

# Core Airtable fields (exact names).
CORE_AIRTABLE_FIELDS = [
    "Medio",
    "Tipo de Medio",
    "Website del Medio",
    "Nombre del Reportero",
    "Título/Rol",
    "Email",
    "Teléfono",
    "Celular",
    "Twitter/X",
    "LinkedIn",
    "Instagram",
    "Facebook",
    "Temas que Cubre",
]


def _pub_field_names() -> list[str]:
    names: list[str] = []
    for i in range(1, MAX_PUB_ARTICLES + 1):
        names.extend(
            [
                f"Pub #{i} – Título",
                f"Pub #{i} – Enlace",
                f"Pub #{i} – Fecha",
            ]
        )
    return names


ALL_DATA_FIELDS = CORE_AIRTABLE_FIELDS + _pub_field_names()


def _client() -> bigquery.Client:
    if not PROJECT_ID:
        raise RuntimeError(
            "Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT for BigQuery."
        )
    return bigquery.Client(project=PROJECT_ID)


def _table_ref() -> str:
    return f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"


def get_bigquery_schema() -> list[bigquery.SchemaField]:
    """Table schema: record_id + exact Airtable-shaped STRING columns."""
    fields: list[bigquery.SchemaField] = [
        bigquery.SchemaField("record_id", "STRING", mode="REQUIRED"),
    ]
    for name in ALL_DATA_FIELDS:
        fields.append(bigquery.SchemaField(name, "STRING", mode="NULLABLE"))
    return fields


def ensure_reporters_table_exists() -> None:
    client = _client()
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset_ref.location = os.environ.get("BIGQUERY_LOCATION", "US")
        client.create_dataset(dataset_ref, exists_ok=True)

    table_ref = dataset_ref.table(TABLE_ID)
    try:
        client.get_table(table_ref)
    except NotFound:
        table = bigquery.Table(table_ref, schema=get_bigquery_schema())
        client.create_table(table)


def build_airtable_shaped_fields(reporter: dict[str, Any]) -> dict[str, Any]:
    """Map scraper dict to Airtable field names; fill Pub # slots up to MAX_PUB_ARTICLES."""
    reporter_name = (reporter.get("reporter_name") or "").strip()
    reporter_email = (reporter.get("email") or "").strip()

    row: dict[str, Any] = {
        "Medio": reporter.get("media") or "",
        "Tipo de Medio": reporter.get("media_type") or "",
        "Website del Medio": reporter.get("website_medium"),
        "Nombre del Reportero": reporter_name,
        "Título/Rol": reporter.get("title_role"),
        "Email": reporter_email,
        "Teléfono": reporter.get("phone"),
        "Celular": reporter.get("cellular"),
        "Twitter/X": reporter.get("twitter"),
        "LinkedIn": reporter.get("linkedin"),
        "Instagram": reporter.get("instagram"),
        "Facebook": reporter.get("facebook"),
        "Temas que Cubre": reporter.get("topics_covered"),
    }

    articles = reporter.get("articles") or []
    for i in range(MAX_PUB_ARTICLES):
        prefix = f"Pub #{i + 1}"
        if i < len(articles):
            a = articles[i] or {}
            row[f"{prefix} – Título"] = a.get("title") or ""
            row[f"{prefix} – Enlace"] = a.get("link") or ""
            row[f"{prefix} – Fecha"] = a.get("date")
        else:
            row[f"{prefix} – Título"] = ""
            row[f"{prefix} – Enlace"] = ""
            row[f"{prefix} – Fecha"] = ""

    return row


def fetch_all_reporter_rows() -> list[dict[str, Any]]:
    """All rows as dicts (including record_id)."""
    ensure_reporters_table_exists()
    client = _client()
    sql = f"SELECT * FROM {_table_ref()}"
    rows: list[dict[str, Any]] = []
    for r in client.query(sql).result():
        rows.append(dict(r.items()))
    return rows


def _apply_twitter_preserve(
    existing_row: dict[str, Any], new_fields: dict[str, Any]
) -> None:
    existing_tw = (existing_row.get("Twitter/X") or "").strip()
    new_tw = (new_fields.get("Twitter/X") or "").strip()
    if existing_tw and not new_tw:
        new_fields["Twitter/X"] = existing_tw


def _bq_update_row(record_id: str, fields: dict[str, Any]) -> None:
    client = _client()
    set_parts: list[str] = []
    qp: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("rid", "STRING", record_id)
    ]
    for i, k in enumerate(ALL_DATA_FIELDS):
        pname = f"f{i}"
        set_parts.append(f"`{k}` = @{pname}")
        qp.append(
            bigquery.ScalarQueryParameter(
                pname, "STRING", _as_str(fields.get(k))
            )
        )
    sql = f"UPDATE {_table_ref()} SET {', '.join(set_parts)} WHERE record_id = @rid"
    client.query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=qp)
    ).result()


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _bq_insert_row(record_id: str, fields: dict[str, Any]) -> None:
    client = _client()
    row = {"record_id": record_id, **{k: _as_str(fields.get(k)) for k in ALL_DATA_FIELDS}}
    errors = client.insert_rows_json(
        f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}", [row]
    )
    if errors:
        raise RuntimeError(f"BigQuery insert_rows_json failed: {errors}")


def update_reporter_twitter_only(record_id: str, twitter_url: str) -> None:
    ensure_reporters_table_exists()
    client = _client()
    sql = f"UPDATE {_table_ref()} SET `Twitter/X` = @tw WHERE record_id = @rid"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("tw", "STRING", twitter_url),
            bigquery.ScalarQueryParameter("rid", "STRING", record_id),
        ]
    )
    client.query(sql, job_config=job_config).result()


def upsert_reporters_merge(
    reporters: list[dict[str, Any]],
    source_script: str,
    *,
    match_emails: bool = False,
    create_only: bool = False,
) -> None:
    """
    Mirror prior Airtable upsert behavior.

    - Normal mode (create_only=False): match by name; if match_emails, also match email.
      Update existing row or insert with new record_id.
    - create_only=True (twitter.py): match twitter URL (lower), then name, then email; only insert if none match; no updates.

    source_script is accepted for API compatibility with callers; optional logging only.
    """
    _ = source_script
    ensure_reporters_table_exists()
    existing_rows = fetch_all_reporter_rows()
    print(f"\nLoaded {len(existing_rows)} existing reporters from BigQuery")

    if create_only:
        existing_by_name: dict[str, dict] = {}
        existing_by_email: dict[str, dict] = {}
        existing_by_twitter: dict[str, dict] = {}
        for row in existing_rows:
            name = (row.get("Nombre del Reportero") or "").strip()
            email = (row.get("Email") or "").strip().lower()
            twitter = (row.get("Twitter/X") or "").strip().lower()
            if name:
                existing_by_name[name.lower()] = row
            if email:
                existing_by_email[email] = row
            if twitter:
                existing_by_twitter[twitter] = row

        added = 0
        for reporter in reporters:
            fields = build_airtable_shaped_fields(reporter)
            reporter_name = (fields.get("Nombre del Reportero") or "").strip()
            reporter_email = (fields.get("Email") or "").strip().lower()
            reporter_twitter = (fields.get("Twitter/X") or "").strip().lower()

            existing_record = None
            if reporter_twitter and reporter_twitter in existing_by_twitter:
                existing_record = existing_by_twitter[reporter_twitter]
            elif reporter_name and reporter_name.lower() in existing_by_name:
                existing_record = existing_by_name[reporter_name.lower()]
            elif reporter_email and reporter_email in existing_by_email:
                existing_record = existing_by_email[reporter_email]

            if existing_record:
                continue
            rid = str(uuid.uuid4())
            try:
                _bq_insert_row(rid, fields)
            except Exception as e:
                print(f"  ! Error adding {reporter_name}: {e}")
                continue
            new_row = {"record_id": rid, **{k: _as_str(fields.get(k)) for k in ALL_DATA_FIELDS}}
            if reporter_name:
                existing_by_name[reporter_name.lower()] = new_row
            if reporter_email:
                existing_by_email[reporter_email] = new_row
            if reporter_twitter:
                existing_by_twitter[reporter_twitter] = new_row
            print(f"  + Added: {reporter_name}")
            added += 1
        print(f"\n{'='*50}")
        print(f"Summary: {added} new reporters added, 0 existing reporters updated")
        print(f"{'='*50}")
        return

    # Full upsert (site scrapers)
    existing_by_name: dict[str, dict] = {}
    existing_by_email: dict[str, dict] = {}
    for row in existing_rows:
        name = (row.get("Nombre del Reportero") or "").strip()
        email = (row.get("Email") or "").strip()
        if name:
            existing_by_name[name.lower()] = row
        if match_emails and email:
            existing_by_email[email.lower()] = row

    added_count = 0
    updated_count = 0
    for reporter in reporters:
        fields = build_airtable_shaped_fields(reporter)
        reporter_name = (fields.get("Nombre del Reportero") or "").strip()
        reporter_email = (fields.get("Email") or "").strip()

        existing_record = None
        if reporter_name and reporter_name.lower() in existing_by_name:
            existing_record = existing_by_name[reporter_name.lower()]
        elif match_emails and reporter_email and reporter_email.lower() in existing_by_email:
            existing_record = existing_by_email[reporter_email.lower()]

        if existing_record:
            _apply_twitter_preserve(existing_record, fields)
            rid = existing_record["record_id"]
            _bq_update_row(rid, fields)
            print(f"  [OK] Updated: {reporter_name}")
            updated_count += 1
        else:
            rid = str(uuid.uuid4())
            _bq_insert_row(rid, fields)
            new_row = {"record_id": rid, **{k: _as_str(fields.get(k)) for k in ALL_DATA_FIELDS}}
            if reporter_name:
                existing_by_name[reporter_name.lower()] = new_row
            if match_emails and reporter_email:
                existing_by_email[reporter_email.lower()] = new_row
            print(f"  + Added: {reporter_name}")
            added_count += 1

    print(f"\n{'='*50}")
    print(
        f"Summary: {added_count} new reporters added, {updated_count} existing reporters updated"
    )
    print(f"{'='*50}")
