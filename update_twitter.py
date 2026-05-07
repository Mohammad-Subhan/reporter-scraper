import requests
import os
from dotenv import load_dotenv
import time

from bigquery_sync import (
    fetch_all_reporter_rows,
    update_reporter_twitter_only,
    COL_NOMBRE_DEL_REPORTERO,
    COL_TWITTER_X,
)

load_dotenv()

TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")


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
        if response.status_code == 402:
            print(f"  ! Twitter API quota exhausted (402)")
            raise requests.exceptions.HTTPError(response=response)
        response.raise_for_status()

        data = response.json()
        users = data.get("users", [])

        if users:
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

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 402:
            raise
        print(f"  Error fetching Twitter profile: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching Twitter profile: {e}")
        return None
    finally:
        time.sleep(2)


def get_reporters_from_bigquery() -> list:
    print("Connecting to BigQuery...")
    records = fetch_all_reporter_rows()
    print(f"+ Found {len(records)} reporters\n")
    return records


def main():
    print("=" * 60)
    print("Twitter Profile Fetcher for Reporters")
    print("=" * 60 + "\n")

    reporters = get_reporters_from_bigquery()

    found_count = 0
    not_found_count = 0
    already_has_twitter = 0
    updated_count = 0
    quota_exhausted = False

    for i, row in enumerate(reporters, 1):
        reporter_name = (row.get(COL_NOMBRE_DEL_REPORTERO) or "").strip()
        existing_twitter = (row.get(COL_TWITTER_X) or "").strip()
        record_id = row.get("record_id")

        if not reporter_name:
            print(f"{i}. Skipping - No name provided")
            continue

        if not record_id:
            print(f"{i}. Skipping - No record_id")
            continue

        print(f"{i}. Processing: {reporter_name}")

        if existing_twitter:
            print(f"  o Already has Twitter: {existing_twitter}")
            already_has_twitter += 1
            continue

        try:
            twitter_data = fetch_twitter_profile(reporter_name)
        except requests.exceptions.HTTPError:
            print("\n! Twitter API quota exhausted — stopping early.")
            quota_exhausted = True
            break

        if twitter_data and twitter_data.get("twitter_url"):
            print(f"  + Found: {twitter_data['twitter_url']}")
            print(f"    - Screen name: @{twitter_data['screen_name']}")

            try:
                update_reporter_twitter_only(record_id, twitter_data["twitter_url"])
                print(f"  + Updated record in BigQuery")
                found_count += 1
                updated_count += 1
            except Exception as e:
                print(f"  x Error updating BigQuery: {e}")
        else:
            print(f"  x No Twitter profile found")
            not_found_count += 1

        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total reporters processed: {len(reporters)}")
    print(f"Already had Twitter: {already_has_twitter}")
    print(f"Twitter profiles found: {found_count}")
    print(f"Not found: {not_found_count}")
    print(f"Records updated in BigQuery: {updated_count}")
    if quota_exhausted:
        print("Twitter API quota exhausted — run stopped early")
    print("=" * 60)


if __name__ == "__main__":
    main()
