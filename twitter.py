import requests
import os
from dotenv import load_dotenv
import time

from bigquery_sync import upsert_reporters_merge

load_dotenv()

URL = "https://api.twitterapi.io/twitter/user/search"
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")

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

    print(f"Pushing {len(reporter_list)} reporters to BigQuery (create-only)...")
    upsert_reporters_merge(reporter_list, "twitter.py", create_only=True)


if __name__ == "__main__":
    main()
