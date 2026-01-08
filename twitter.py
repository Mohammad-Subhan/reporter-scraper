import requests
import os
from dotenv import load_dotenv
from pyairtable import Api
import time

load_dotenv()

URL = "https://api.twitterapi.io/twitter/user/search"
ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")

print(TWITTER_API_KEY)

queries = [
    "periodista Puerto Rico",
    "reportero Puerto Rico",
    '"periodista PR" OR "reportero PR"',
    "journalist puerto rico",
    "reporter puerto rico",
]


def get_response(query: str, cursor: str = None):
    params = {
        "query": query,
        "cursor": cursor,
    }

    headers = {"X-API-Key": TWITTER_API_KEY}

    try:
        response = requests.get(URL, headers=headers, params=params)
        response.raise_for_status()
        print(f"Fetched data for query: '{query}' (cursor: {cursor})")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for query '{query}': {e}")
        raise
    finally:
        time.sleep(2)  # Add a delay to avoid hitting rate limits


def update_airtable(reporters: list[dict]):
    """Update Airtable with reporter data"""
    print(f"Updating Airtable with {len(reporters)} reporters...")
    api = Api(ACCESS_TOKEN)
    table = api.table(BASE_ID, table_name="Reporters")

    print("\nFetching existing reporters from Airtable...")
    # Fetch all existing reporters to check for duplicates
    existing_records = table.all()
    existing_by_name = {}
    existing_by_email = {}
    existing_by_twitter = {}

    # Create lookup dictionaries by name and email separately
    for record in existing_records:
        fields = record.get("fields", {})
        name = fields.get("Nombre del Reportero", "").strip()
        email = fields.get("Email", "").strip().lower()
        twitter = fields.get("Twitter/X", "").strip().lower()

        if name:
            existing_by_name[name.lower()] = record
        if email:
            existing_by_email[email] = record
        if twitter:
            existing_by_twitter[twitter] = record

    print(f"Found {len(existing_records)} existing reporters in Airtable")

    added_count = 0
    updated_count = 0

    for reporter in reporters:
        reporter_name = (reporter.get("reporter_name") or "").strip()
        reporter_email = (reporter.get("email") or "").strip().lower()
        reporter_twitter = (reporter.get("twitter") or "").strip().lower()

        record = {
            "Medio": reporter.get("media") or "",
            "Tipo de Medio": reporter.get("media_type") or "",
            "Website del Medio": reporter.get("website_medium"),
            "Nombre del Reportero": reporter_name,
            "Título/Rol": reporter.get("title_role"),
            "Email": reporter_email,
            "Teléfono": reporter.get("phone"),
            "Celular": reporter.get("cellular"),
            "Twitter/X": reporter_twitter,
            "LinkedIn": reporter.get("linkedin"),
            "Instagram": reporter.get("instagram"),
            "Facebook": reporter.get("facebook"),
            "Temas que Cubre": reporter.get("topics_covered"),
        }

        for i, a in enumerate(reporter.get("articles") or []):
            record[f"Pub #{i+1} – Título"] = a.get("title") or ""
            record[f"Pub #{i+1} – Enlace"] = a.get("link") or ""
            record[f"Pub #{i+1} – Fecha"] = a.get("date")

        # Check if reporter already exists (prioritize twitter, then name, then email)
        existing_record = None
        if reporter_twitter and reporter_twitter in existing_by_twitter:
            existing_record = existing_by_twitter[reporter_twitter]
        elif reporter_name and reporter_name.lower() in existing_by_name:
            existing_record = existing_by_name[reporter_name.lower()]
        elif reporter_email and reporter_email in existing_by_email:
            existing_record = existing_by_email[reporter_email]

        if existing_record:
            # No change to existing record, skip update
            continue
        else:
            # Create new reporter
            try:
                table.create(record)
                print(f"  + Added: {reporter_name}")
                added_count += 1
            except Exception as e:
                print(f"  ! Error adding {reporter_name}: {e}")

    print(f"\n{'='*50}")
    print(
        f"Summary: {added_count} new reporters added, {updated_count} existing reporters updated"
    )
    print(f"{'='*50}")


def main():
    print("Starting Twitter scraper...")
    reporters = []

    for query in queries:
        cursor = None
        while True:
            try:
                data = get_response(query, cursor)
                reporters.extend(data.get("users") or [])
                if data.get("has_next_page"):
                    cursor = data.get("next_cursor")
                else:
                    break
            except Exception as e:
                print(f"Skipping query '{query}' due to error")
                break

    # Remove duplicates based on user ID
    unique_reporters = {reporter["id"]: reporter for reporter in reporters}
    reporters = list(unique_reporters.values())

    reporter_list = []
    for reporter in reporters:
        reporter_list.append(
            {
                "media": reporter.get("media") or "",
                "media_type": reporter.get("media_type") or "",
                "website_medium": reporter.get("website_medium") or "",
                "reporter_name": reporter.get("name") or "",
                "title_role": reporter.get("title") or "",
                "email": reporter.get("email") or "",
                "phone": reporter.get("phone") or "",
                "cellular": reporter.get("cellular") or "",
                "twitter": (
                    "https://x.com/" + reporter.get("screen_name")
                    if reporter.get("screen_name")
                    else ""
                ),
                "linkedin": reporter.get("linkedin") or "",
                "facebook": reporter.get("facebook") or "",
                "instagram": reporter.get("instagram") or "",
                "topics_covered": reporter.get("topics_covered") or "",
                "articles": reporter.get("articles") or [],
            }
        )

    print(f"✓ Collected {len(reporter_list)} unique reporters")
    update_airtable(reporter_list)


if __name__ == "__main__":
    main()
