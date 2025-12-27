import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import json
from pyairtable import Api
import os
from dotenv import load_dotenv
import datetime
import time
import random

load_dotenv()

ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

news_urls = [
    "https://wapa.tv/noticias/locales/",
    "https://wapa.tv/noticias/politica/",
    "https://wapa.tv/noticias/deportes/",
    "https://wapa.tv/noticias/internacionales/",
    "https://wapa.tv/noticias/entretenimiento/",
]


def initialize_playwright():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    return p, browser, page


def get_html_requests(url: str):
    try:
        # Send GET request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise exception for bad status codes

        return response.content

    except Exception as e:
        print(f"An error occurred while fetching HTML content: {e}")
        return None


def get_html_playwright(url: str):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Try to wait for content, but continue if it times out
            try:
                page.goto(url)
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception as wait_error:
                print(f"  Warning: Wait timeout, using partial content")

            # Always try to get content even if wait failed
            html_content = page.content()
            browser.close()
            return html_content

    except Exception as e:
        print(f"An error occurred while fetching HTML content: {e}")
        return None


def get_article_info(url: str) -> list[dict]:
    """Fetch article information from a given URL"""
    try:
        html_content = get_html_playwright(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        article_info_div = soup.find("header", class_="asset-header")
        if not article_info_div:
            print(f"  Warning: No article info div found for {url}")
            return {}

        article_title = article_info_div.find("h1")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_author_div = article_info_div.find("span", class_="tnt-byline")
        if not article_author_div:
            print(f"  Warning: No article author div found for {url}")
            return {}

        article_authors = article_author_div.get_text(strip=True)

        # split by / and , then strip whitespace
        article_authors = [
            {"name": author.strip(), "url": ""}  # No author URL available
            for part in article_authors.split("/")
            for author in part.split(",")
        ]

        article_date = article_info_div.find("time", class_="tnt-date")

        if article_date and article_date.has_attr("datetime"):
            # 2025-12-12T17:50:33-04:00 -> 17/12/2025
            article_date = article_date.get("datetime")
            article_date = datetime.datetime.fromisoformat(article_date).strftime(
                "%d/%m/%Y"
            )
        else:
            article_date = ""

        article_info = []
        for author in article_authors:
            article_info.append(
                {
                    "author_name": author.get("name"),
                    "title": article_title,
                    "date": article_date,
                    "link": url,
                }
            )

        return article_info

    except Exception as e:
        print(f"Error: An error occurred while extracting article info: {e}")
        return []


def get_reporters_list_from_articles(url: str) -> list[dict]:
    p, browser, page = initialize_playwright()
    try:
        page.goto(url)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as goto_error:
            print(f"  Warning: Wait timeout, using partial content")

        # Click "Ver más" button 2 times to load more articles
        i = 1
        while i <= 2:
            try:
                # Look for the "Ver más" (See more) button
                load_more_button = page.locator("#trigger-next-1444330")

                if load_more_button.is_visible(timeout=5000):
                    print(f"  Clicking 'See More' button {i}/2")
                    # Use force=True to bypass ad overlay interceptions
                    load_more_button.click(force=True, timeout=10000)
                    page.wait_for_timeout(20000)
                    i += 1
                else:
                    print(f"  No more 'See More' button found after {i-1} clicks")
                    break
            except Exception as e:
                print(
                    f"  Could not click more (continuing with current content): {str(e)[:100]}"
                )
                break

        html_content = page.content()

        browser.close()
        p.stop()

        soup = BeautifulSoup(html_content, "html.parser")

        # Find all article elements
        news_article_divs = list(soup.find_all("div", class_="card-body"))

        if not news_article_divs:
            return []

        reporters = []
        for idx, article_div in enumerate(news_article_divs, 1):
            article_link_tag = article_div.find("a", class_="tnt-asset-link")

            if article_link_tag and article_link_tag.has_attr("href"):
                href = article_link_tag.get("href")

                # Skip template placeholders or empty hrefs
                if not href or "{{" in href or "}}" in href:
                    continue

                # Only prepend domain if href is relative
                if href.startswith("http"):
                    article_link = href.rstrip("/")
                else:
                    article_link = ("https://wapa.tv" + href).rstrip("/")
            else:
                # Skip articles without valid links
                continue

            article_info = get_article_info(article_link)

            reporters.extend(article_info)
            time.sleep(random.uniform(3, 5))  # Increased delay to avoid rate limiting

        return reporters

    except Exception as e:
        print(f"Error: An error occurred while extracting reporters from articles: {e}")
        return []


def process_news_sources() -> list[dict]:
    all_reporters = []
    for news_url in news_urls:
        print(f"\nProcessing news source: {news_url}")
        reporters = get_reporters_list_from_articles(news_url)
        all_reporters.extend(reporters)

        # Add delay between processing different news sources
        time.sleep(random.uniform(5, 10))

    return all_reporters


def process_reporters_list(reporters_flat: list[dict]) -> list[dict]:
    """Transform flat list to grouped structure and fetch profile info"""

    # Group articles by reporter
    reporters_dict = {}
    for item in reporters_flat:
        reporter_name = item.get("author_name") or ""
        reporter_url = (item.get("author_url") or "").rstrip("/")

        key = reporter_name

        if key == "Fotos crédito: Jean Ayala y Josian Bruno":
            continue

        if not key:
            continue

        # Initialize reporter if not exists
        if key not in reporters_dict:
            reporters_dict[key] = {
                "name": reporter_name,
                "url": reporter_url,
                "articles": [],
            }

        # Add article to reporter's articles list
        article = {
            "title": item.get("title") or "",
            "date": item.get("date") or "",
            "link": (item.get("link") or "").rstrip("/"),
        }
        reporters_dict[key]["articles"].append(article)

    reporters_list = list(reporters_dict.values())

    # Limit to 4 articles per reporter, the most recent ones using date
    for reporter in reporters_list:
        reporter["articles"] = sorted(
            reporter["articles"],
            key=lambda x: (
                datetime.datetime.strptime(x["date"], "%d/%m/%Y")
                if x["date"]
                else datetime.datetime.min
            ),
            reverse=True,
        )[:4]

    print(f"\nProcessing {len(reporters_list)} unique reporters...")

    processed_reporters = []
    media_name = "WAPA-TV"
    media_type = ""
    website_url = "https://www.wapa.tv"

    for idx, reporter in enumerate(reporters_list, 1):
        reporter_name = reporter.get("name", "")
        reporter_url = reporter.get("url", "")

        print(f"[{idx}/{len(reporters_list)}] {reporter_name}")

        # Get profile info if URL exists
        reporter_info = {}

        processed_reporters.append(
            {
                "media": media_name,
                "media_type": media_type,
                "website_medium": website_url,
                "reporter_name": reporter_name or reporter_info.get("name", ""),
                "title_role": reporter_info.get("title") or "",
                "email": reporter_info.get("email") or "",
                "phone": reporter_info.get("phone") or "",
                "cellular": reporter_info.get("cellular") or "",
                "twitter": reporter_info.get("twitter") or "",
                "linkedin": reporter_info.get("linkedin") or "",
                "facebook": reporter_info.get("facebook") or "",
                "instagram": reporter_info.get("instagram") or "",
                "topics_covered": reporter_info.get("topics_covered") or "",
                "articles": reporter.get("articles") or [],
            }
        )
        time.sleep(random.uniform(3, 5))

    print(f"[OK] Completed {len(processed_reporters)} reporters")
    return processed_reporters


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

    # Create lookup dictionaries by name and email separately
    for record in existing_records:
        fields = record.get("fields", {})
        name = fields.get("Nombre del Reportero", "").strip()

        # Store by name (only if not already exists to avoid overwriting)
        if name and name.lower() not in existing_by_name:
            existing_by_name[name.lower()] = record

    print(f"Found {len(existing_records)} existing reporters in Airtable")

    added_count = 0
    updated_count = 0

    for reporter in reporters:
        reporter_name = (reporter.get("reporter_name") or "").strip()

        record = {
            "Medio": reporter.get("media") or "",
            "Tipo de Medio": reporter.get("media_type") or "",
            "Website del Medio": reporter.get("website_medium"),
            "Nombre del Reportero": reporter_name,
            "Título/Rol": reporter.get("title_role"),
            "Email": reporter.get("email"),
            "Teléfono": reporter.get("phone"),
            "Celular": reporter.get("cellular"),
            "Twitter/X": (reporter.get("twitter") or "").rstrip("/"),
            "LinkedIn": (reporter.get("linkedin") or "").rstrip("/"),
            "Instagram": (reporter.get("instagram") or "").rstrip("/"),
            "Facebook": (reporter.get("facebook") or "").rstrip("/"),
            "Temas que Cubre": reporter.get("topics_covered"),
        }

        for i, a in enumerate(reporter.get("articles") or []):
            record[f"Pub #{i+1} – Título"] = a.get("title") or ""
            record[f"Pub #{i+1} – Enlace"] = a.get("link") or ""
            record[f"Pub #{i+1} – Fecha"] = a.get("date")

        # Check if reporter already exists (prioritize name match, then email)
        existing_record = None
        if reporter_name and reporter_name.lower() in existing_by_name:
            existing_record = existing_by_name[reporter_name.lower()]

        if existing_record:
            # Update existing reporter
            record_id = existing_record["id"]

            # Don't overwrite existing Twitter/X if the new value is empty
            existing_twitter = (
                existing_record.get("fields", {}).get("Twitter/X", "").strip()
            )
            if existing_twitter and not record.get("Twitter/X"):
                record["Twitter/X"] = existing_twitter

            table.update(record_id, record)
            print(f"  [OK] Updated: {reporter_name}")
            updated_count += 1
        else:
            # Create new reporter
            table.create(record)
            print(f"  + Added: {reporter_name}")
            added_count += 1

    print(f"\n{'='*50}")
    print(
        f"Summary: {added_count} new reporters added, {updated_count} existing reporters updated"
    )
    print(f"{'='*50}")


def main():
    # Step 1-3: Get all articles and reporters
    reporters_flat = process_news_sources()

    if not reporters_flat:
        print("No reporters found.")
        return

    reporters = process_reporters_list(reporters_flat)

    update_airtable(reporters)


if __name__ == "__main__":
    main()
