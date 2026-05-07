"""
BigQuery persistence for reporter scrapers.

Scrapers keep emitting logical dict keys (reporter_name, media, title_role, …).
This module maps them to BigQuery-legal column names (snake_case, no / or #).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from dotenv import load_dotenv

load_dotenv()

MAX_PUB_ARTICLES = 10

PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or ""
DATASET_ID = (os.environ.get("BIGQUERY_DATASET") or "").strip() or "reporter_scraper"
# Default `reporters` avoids clashing with a legacy `Reporters` table that had invalid BQ identifiers.
TABLE_ID = (os.environ.get("BIGQUERY_TABLE") or "").strip() or "reporters"

# --- Physical BigQuery columns (single source of truth; legal identifiers only) ---

COL_MEDIO = "medio"
COL_TIPO_DE_MEDIO = "tipo_de_medio"
COL_WEBSITE_DEL_MEDIO = "website_del_medio"
COL_NOMBRE_DEL_REPORTERO = "nombre_del_reportero"
COL_TITULO_ROL = "titulo_rol"
COL_EMAIL = "email"
COL_TELEFONO = "telefono"
COL_CELULAR = "celular"
COL_TWITTER_X = "twitter_x"
COL_LINKEDIN = "linkedin"
COL_INSTAGRAM = "instagram"
COL_FACEBOOK = "facebook"
COL_TEMAS_QUE_CUBRE = "temas_que_cubre"

CORE_BQ_FIELDS: list[str] = [
    COL_MEDIO,
    COL_TIPO_DE_MEDIO,
    COL_WEBSITE_DEL_MEDIO,
    COL_NOMBRE_DEL_REPORTERO,
    COL_TITULO_ROL,
    COL_EMAIL,
    COL_TELEFONO,
    COL_CELULAR,
    COL_TWITTER_X,
    COL_LINKEDIN,
    COL_INSTAGRAM,
    COL_FACEBOOK,
    COL_TEMAS_QUE_CUBRE,
]


def _pub_bq_field_names() -> list[str]:
    names: list[str] = []
    for i in range(1, MAX_PUB_ARTICLES + 1):
        p = f"pub_{i:02d}"
        names.extend([f"{p}_title", f"{p}_link", f"{p}_date"])
    return names


BQ_DATA_FIELDS: list[str] = CORE_BQ_FIELDS + _pub_bq_field_names()

RECORD_ID_FIELD = "record_id"


def _client() -> bigquery.Client:
    if not PROJECT_ID:
        raise RuntimeError(
            "Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT for BigQuery."
        )
    return bigquery.Client(project=PROJECT_ID)


def _table_ref() -> str:
    return f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"


def _full_table_id() -> str:
    return f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"


def get_bigquery_schema() -> list[bigquery.SchemaField]:
    fields: list[bigquery.SchemaField] = [
        bigquery.SchemaField(RECORD_ID_FIELD, "STRING", mode="REQUIRED"),
    ]
    for name in BQ_DATA_FIELDS:
        fields.append(bigquery.SchemaField(name, "STRING", mode="NULLABLE"))
    return fields


def row_for_bigquery(reporter: dict[str, Any]) -> dict[str, str]:
    """
    Map a scraper payload (logical keys) to a flat dict with **exactly** BQ_DATA_FIELDS keys.
    Scrapers must not need to know physical column names.
    """
    reporter_name = (reporter.get("reporter_name") or "").strip()
    reporter_email = (reporter.get("email") or "").strip()

    row: dict[str, str] = {
        COL_MEDIO: _as_str(reporter.get("media") or ""),
        COL_TIPO_DE_MEDIO: _as_str(reporter.get("media_type") or ""),
        COL_WEBSITE_DEL_MEDIO: _as_str(reporter.get("website_medium")),
        COL_NOMBRE_DEL_REPORTERO: _as_str(reporter_name),
        COL_TITULO_ROL: _as_str(reporter.get("title_role")),
        COL_EMAIL: _as_str(reporter_email),
        COL_TELEFONO: _as_str(reporter.get("phone")),
        COL_CELULAR: _as_str(reporter.get("cellular")),
        COL_TWITTER_X: _as_str(reporter.get("twitter")),
        COL_LINKEDIN: _as_str(reporter.get("linkedin")),
        COL_INSTAGRAM: _as_str(reporter.get("instagram")),
        COL_FACEBOOK: _as_str(reporter.get("facebook")),
        COL_TEMAS_QUE_CUBRE: _as_str(reporter.get("topics_covered")),
    }

    articles = reporter.get("articles") or []
    for i in range(MAX_PUB_ARTICLES):
        p = f"pub_{i + 1:02d}"
        if i < len(articles):
            a = articles[i] or {}
            row[f"{p}_title"] = _as_str(a.get("title"))
            row[f"{p}_link"] = _as_str(a.get("link"))
            row[f"{p}_date"] = _as_str(a.get("date"))
        else:
            row[f"{p}_title"] = ""
            row[f"{p}_link"] = ""
            row[f"{p}_date"] = ""

    if set(row.keys()) != set(BQ_DATA_FIELDS):
        missing = set(BQ_DATA_FIELDS) - set(row.keys())
        extra = set(row.keys()) - set(BQ_DATA_FIELDS)
        raise RuntimeError(
            f"row_for_bigquery internal bug: missing={missing}, extra={extra}"
        )
    return row


def ensure_reporters_table_exists() -> None:
    client = _client()
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset_ref.location = os.environ.get("BIGQUERY_LOCATION", "US")
        client.create_dataset(dataset_ref, exists_ok=True)

    table_ref = dataset_ref.table(TABLE_ID)
    required_fields = {RECORD_ID_FIELD, *BQ_DATA_FIELDS}

    try:
        existing = client.get_table(table_ref)
        existing_names = {f.name for f in existing.schema}
        if not required_fields.issubset(existing_names):
            missing = sorted(required_fields - existing_names)
            raise RuntimeError(
                f"BigQuery table {_full_table_id()} has an incompatible schema "
                f"(missing columns, e.g.: {missing[:8]}). "
                f"Drop and recreate: bq rm -f -t {_full_table_id()}"
            )
    except NotFound:
        table = bigquery.Table(table_ref, schema=get_bigquery_schema())
        client.create_table(table)


def fetch_all_reporter_rows() -> list[dict[str, Any]]:
    """All rows as dicts (physical column names + record_id)."""
    ensure_reporters_table_exists()
    client = _client()
    sql = f"SELECT * FROM {_table_ref()}"
    rows: list[dict[str, Any]] = []
    for r in client.query(sql).result():
        rows.append(dict(r.items()))
    return rows


def _apply_twitter_preserve(
    existing_row: dict[str, Any], new_fields: dict[str, str]
) -> None:
    existing_tw = (existing_row.get(COL_TWITTER_X) or "").strip()
    new_tw = (new_fields.get(COL_TWITTER_X) or "").strip()
    if existing_tw and not new_tw:
        new_fields[COL_TWITTER_X] = existing_tw


def _bq_update_row(record_id: str, fields: dict[str, str]) -> None:
    client = _client()
    set_parts: list[str] = []
    qp: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("rid", "STRING", record_id)
    ]
    for i, k in enumerate(BQ_DATA_FIELDS):
        pname = f"f{i}"
        set_parts.append(f"`{k}` = @{pname}")
        qp.append(
            bigquery.ScalarQueryParameter(
                pname, "STRING", fields.get(k, "")
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


def _bq_insert_row(record_id: str, fields: dict[str, str]) -> None:
    client = _client()
    qp: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("rid", "STRING", record_id)
    ]
    cols = [f"`{RECORD_ID_FIELD}`"]
    vals = ["@rid"]
    for i, k in enumerate(BQ_DATA_FIELDS):
        pname = f"f{i}"
        qp.append(bigquery.ScalarQueryParameter(pname, "STRING", fields.get(k, "")))
        cols.append(f"`{k}`")
        vals.append(f"@{pname}")
    sql = f"INSERT INTO {_table_ref()} ({', '.join(cols)}) VALUES ({', '.join(vals)})"
    client.query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=qp)
    ).result()


def update_reporter_twitter_only(record_id: str, twitter_url: str) -> None:
    ensure_reporters_table_exists()
    client = _client()
    sql = (
        f"UPDATE {_table_ref()} SET `{COL_TWITTER_X}` = @tw "
        f"WHERE record_id = @rid"
    )
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
    Upsert by nombre (and optionally email). create_only: twitter discovery inserts only.
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
            name = (row.get(COL_NOMBRE_DEL_REPORTERO) or "").strip()
            email = (row.get(COL_EMAIL) or "").strip().lower()
            twitter = (row.get(COL_TWITTER_X) or "").strip().lower()
            if name:
                existing_by_name[name.lower()] = row
            if email:
                existing_by_email[email] = row
            if twitter:
                existing_by_twitter[twitter] = row

        added = 0
        for reporter in reporters:
            fields = row_for_bigquery(reporter)
            reporter_name = (fields.get(COL_NOMBRE_DEL_REPORTERO) or "").strip()
            reporter_email = (fields.get(COL_EMAIL) or "").strip().lower()
            reporter_twitter = (fields.get(COL_TWITTER_X) or "").strip().lower()

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
            new_row = {
                RECORD_ID_FIELD: rid,
                **{k: fields[k] for k in BQ_DATA_FIELDS},
            }
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

    existing_by_name: dict[str, dict] = {}
    existing_by_email: dict[str, dict] = {}
    for row in existing_rows:
        name = (row.get(COL_NOMBRE_DEL_REPORTERO) or "").strip()
        email = (row.get(COL_EMAIL) or "").strip()
        if name:
            existing_by_name[name.lower()] = row
        if match_emails and email:
            existing_by_email[email.lower()] = row

    added_count = 0
    updated_count = 0
    error_count = 0
    for reporter in reporters:
        fields = row_for_bigquery(reporter)
        reporter_name = (fields.get(COL_NOMBRE_DEL_REPORTERO) or "").strip()
        reporter_email = (fields.get(COL_EMAIL) or "").strip()

        existing_record = None
        if reporter_name and reporter_name.lower() in existing_by_name:
            existing_record = existing_by_name[reporter_name.lower()]
        elif (
            match_emails
            and reporter_email
            and reporter_email.lower() in existing_by_email
        ):
            existing_record = existing_by_email[reporter_email.lower()]

        if existing_record:
            _apply_twitter_preserve(existing_record, fields)
            rid = existing_record[RECORD_ID_FIELD]
            try:
                _bq_update_row(rid, fields)
                print(f"  [OK] Updated: {reporter_name}")
                updated_count += 1
            except Exception as e:
                print(f"  ! Error updating {reporter_name}: {e}")
                error_count += 1
        else:
            rid = str(uuid.uuid4())
            try:
                _bq_insert_row(rid, fields)
                new_row = {
                    RECORD_ID_FIELD: rid,
                    **{k: fields[k] for k in BQ_DATA_FIELDS},
                }
                if reporter_name:
                    existing_by_name[reporter_name.lower()] = new_row
                if match_emails and reporter_email:
                    existing_by_email[reporter_email.lower()] = new_row
                print(f"  + Added: {reporter_name}")
                added_count += 1
            except Exception as e:
                print(f"  ! Error adding {reporter_name}: {e}")
                error_count += 1

    print(f"\n{'='*50}")
    print(
        f"Summary: {added_count} new reporters added, {updated_count} existing reporters updated"
        + (f", {error_count} errors" if error_count else "")
    )
    print(f"{'='*50}")


def _validate_schema_and_row_builder() -> None:
    """Guard: schema DDL and row_for_bigquery must stay aligned."""
    schema_names = [f.name for f in get_bigquery_schema()]
    expected = [RECORD_ID_FIELD, *BQ_DATA_FIELDS]
    if schema_names != expected:
        raise AssertionError(
            "get_bigquery_schema() field order mismatch vs RECORD_ID_FIELD + BQ_DATA_FIELDS"
        )
    sample = row_for_bigquery(
        {
            "reporter_name": "Test",
            "media": "M",
            "media_type": "T",
            "website_medium": "https://x",
            "title_role": "R",
            "email": "e@e",
            "phone": "1",
            "cellular": "2",
            "twitter": "https://x.com/t",
            "linkedin": "",
            "instagram": "",
            "facebook": "",
            "topics_covered": "news",
            "articles": [{"title": "a", "link": "l", "date": "d"}],
        }
    )
    if list(sample.keys()) != BQ_DATA_FIELDS:
        raise AssertionError(
            "row_for_bigquery key order must match BQ_DATA_FIELDS for stable UPDATE SET clauses"
        )


_validate_schema_and_row_builder()
