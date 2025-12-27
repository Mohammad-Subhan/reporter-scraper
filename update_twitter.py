import requests
import os
from dotenv import load_dotenv
from pyairtable import Api
import time

load_dotenv()

# API Configuration
TWITTER_API_URL = "https://api.twitterapi.io/twitter/user/lookup"
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")

# Airtable Configuration
ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
TABLE_NAME = "Reporters"  # The table to fetch reporters from


def fetch_twitter_profile(name: str) -> dict:
    """
    Fetch Twitter profile link for a given name using twitterapi.io API

    Args:
        name: The name of the person to search for

    Returns:
        dict with twitter profile data or None if not found
    """
    search_url = "https://api.twitterapi.io/twitter/user/search"
    headers = {"X-API-Key": TWITTER_API_KEY}

    print(f"  Searching for: '{name}'")
    params = {"query": name}

    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        users = data.get("users", [])

        if users:
            # Return the first match
            user = users[0]
            print(f"  + Found match")
            return {
                "screen_name": user.get("screen_name"),
                "twitter_url": (
                    f"https://x.com/{user.get('screen_name')}"
                    if user.get("screen_name")
                    else None
                ),
                "name": user.get("name"),
            }
        else:
            print(f"  No Twitter profile found")
            return None

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching Twitter profile: {e}")
        return None
    finally:
        time.sleep(2)  # Rate limiting


def get_reporters_from_airtable() -> list:
    """
    Fetch all reporters from Airtable 'Reporters copy' table

    Returns:
        list of reporter records
    """
    print("Connecting to Airtable...")
    api = Api(ACCESS_TOKEN)
    table = api.table(BASE_ID, table_name=TABLE_NAME)

    print(f"Fetching reporters from '{TABLE_NAME}' table...")
    records = table.all()
    print(f"+ Found {len(records)} reporters\n")

    return records


def update_reporter_twitter(record_id: str, twitter_url: str):
    """
    Update a reporter's Twitter/X field in Airtable

    Args:
        record_id: The Airtable record ID
        twitter_url: The Twitter profile URL to update
    """
    api = Api(ACCESS_TOKEN)
    table = api.table(BASE_ID, table_name=TABLE_NAME)

    try:
        table.update(record_id, {"Twitter/X": twitter_url})
        print(f"  + Updated record in Airtable")
    except Exception as e:
        print(f"  x Error updating Airtable: {e}")


def main():
    """
    Main function to fetch Twitter profiles for all reporters in the list
    """
    print("=" * 60)
    print("Twitter Profile Fetcher for Reporters")
    print("=" * 60 + "\n")

    # Get reporters from Airtable
    reporters = get_reporters_from_airtable()

    # Track statistics
    found_count = 0
    not_found_count = 0
    already_has_twitter = 0
    updated_count = 0

    # Process each reporter
    for i, record in enumerate(reporters, 1):
        fields = record.get("fields", {})
        reporter_name = fields.get("Nombre del Reportero", "").strip()
        media_outlet = fields.get("Medio", "").strip()
        existing_twitter = fields.get("Twitter/X", "").strip()

        if not reporter_name:
            print(f"{i}. Skipping - No name provided")
            continue

        print(f"{i}. Processing: {reporter_name}")

        # Skip if already has Twitter
        if existing_twitter:
            print(f"  o Already has Twitter: {existing_twitter}")
            already_has_twitter += 1
            continue

        # Fetch Twitter profile
        twitter_data = fetch_twitter_profile(reporter_name)

        if twitter_data and twitter_data.get("twitter_url"):
            print(f"  + Found: {twitter_data['twitter_url']}")
            print(f"    - Screen name: @{twitter_data['screen_name']}")

            # Update Airtable
            update_reporter_twitter(record["id"], twitter_data["twitter_url"])
            found_count += 1
            updated_count += 1
        else:
            print(f"  x No Twitter profile found")
            not_found_count += 1

        print()

    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total reporters processed: {len(reporters)}")
    print(f"Already had Twitter: {already_has_twitter}")
    print(f"Twitter profiles found: {found_count}")
    print(f"Not found: {not_found_count}")
    print(f"Records updated in Airtable: {updated_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
