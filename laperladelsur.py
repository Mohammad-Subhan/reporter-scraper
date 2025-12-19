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

reporters = [
    {
        "name": "Luis Valentín Ortiz",
        "url": "https://www.periodicolaperla.com/author/luis",
    },
    {
        "name": "Dennis Dávila",
        "url": "https://www.periodicolaperla.com/author/dennis",
    },
    {
        "name": "Jason Rodríguez Grafal",
        "url": "https://www.periodicolaperla.com/author/jason",
    },
    {
        "name": "Julio César Muñoz Gómez",
        "url": "https://www.periodicolaperla.com/author/juliocesar",
    },
    {
        "name": "Omar Alfonso",
        "url": "https://www.periodicolaperla.com/author/omaralfonso",
    },
    {
        "name": "Javier De Jesús Martínez",
        "url": "https://www.periodicolaperla.com/author/javierdejesus",
    },
    {
        "name": "Arturo Massol Deyá",
        "url": "https://www.periodicolaperla.com/author/arturomassol",
    },
    {
        "name": "Carlos F. Ramos Hernández",
        "url": "https://www.periodicolaperla.com/author/carlosramoshernandez",
    },
]


def initialize_playwright():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    return p, browser, page


def get_html_requests(url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"An error occurred while fetching HTML content: {e}")
        return None


def get_reporters_list_from_articles(url: str) -> list[dict]:
    """Fetch reporters list from articles on a given page URL"""

    p, browser, page = initialize_playwright()
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"Warning: Wait timeout, using partial content{e}")
        page.wait_for_timeout(2000)

    reporters = []
    for i in range(5):
        html_content = page.content()

        if not html_content:
            print(f"  Warning: No content found for {url}")
            return []

        soup = BeautifulSoup(html_content, "html.parser")

        # Find all article elements
        news_article_divs = list(
            soup.find_all("article", class_="jeg_post jeg_pl_md_2 format-standard")
        )

        print(f"  Found {len(news_article_divs)} articles on page {i+1}")

        if not news_article_divs:
            continue

        for idx, article_div in enumerate(news_article_divs, 1):

            article_title_div = article_div.find("h3", class_="jeg_post_title")
            if article_title_div:
                article_title = article_title_div.get_text(strip=True)
            else:
                article_title = ""

            article_link = article_title_div.find("a")
            if article_link:
                article_link = (
                    article_link.get("href").rstrip("/")
                    if article_link.get("href")
                    else ""
                )
            else:
                article_link = ""

            article_date = article_div.find("div", class_="jeg_meta_date")
            if article_date:
                article_date = article_date.get_text(strip=True).split("|")[0].strip()
            else:
                article_date = ""

            article_author_div = article_div.find("div", class_="jeg_meta_author")
            if not article_author_div:
                continue

            article_authors = []
            article_authors_links = article_author_div.find_all("a")

            for author_link in article_authors_links:
                author_name = author_link.get_text(strip=True)
                author_url = (
                    author_link.get("href").rstrip("/")
                    if author_link.has_attr("href") and author_link.get("href")
                    else ""
                )
                article_authors.append({"name": author_name, "url": author_url})

            article_info = []
            for author in article_authors:
                article_info.append(
                    {
                        "author_name": author.get("name"),
                        "author_url": author.get("url"),
                        "title": article_title,
                        "date": article_date,
                        "link": article_link,
                    }
                )

            reporters.extend(article_info)

            time.sleep(random.uniform(1, 2))  # sleep for 1 to 2 seconds

        # Pagination - move next button click outside of article loop
        try:
            next_button = page.locator("a.next")
            if next_button.is_visible():
                print("  Clicking next page...")
                next_button.click()
                page.wait_for_timeout(2000)
            else:
                print("  No more pages found")
                break
        except Exception as e:
            break

    # Cleanup
    browser.close()
    p.stop()

    return reporters


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "div",
            class_="jeg_postblock_content",
        )
    )

    articles = []

    # maximum 4
    for article_div in articles_div_list[:4]:
        article_date = article_div.find("div", class_="jeg_meta_date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_title = article_div.find("h3", class_="jeg_post_title")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_link = article_div.find("a")
        if article_link and article_link.get("href"):
            article_link = article_link["href"].rstrip("/")
        else:
            article_link = ""

        articles.append(
            {
                "title": article_title,
                "link": article_link,
                "date": article_date,
            }
        )

        time.sleep(random.uniform(1, 2))  # sleep for 1 to 2 seconds

    return articles


def extract_reporter_info(url: str) -> dict:
    try:
        html_content = get_html_requests(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        reporter_bio_section = soup.find("div", class_="jeg_author_content")
        if not reporter_bio_section:
            print(f"  Warning: No author bio found for {url}")
            return {}

        reporter_name = reporter_bio_section.find("h3", class_="jeg_author_name fn")
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_social_div = reporter_bio_section.find(
            "div", class_="jeg_author_socials"
        )

        reporter_socials = []
        if reporter_social_div:
            reporter_socials = [
                social["href"]
                for social in reporter_social_div.find_all("a")
                if social.get("href")
            ]

        reporter_email = ""
        reporter_x = ""
        reporter_facebook = ""
        reporter_linkedin = ""
        reporter_instagram = ""
        for social_link in reporter_socials:
            if "twitter.com" in social_link or "x.com" in social_link:
                reporter_x = social_link
            elif "facebook.com" in social_link:
                reporter_facebook = social_link
            elif "linkedin.com" in social_link:
                reporter_linkedin = social_link
            elif "instagram.com" in social_link:
                reporter_instagram = social_link
            elif "mailto:" in social_link:
                reporter_email = social_link.replace("mailto:", "")

        articles = get_articles(soup)

        return {
            "name": reporter_name,
            "title": "",
            "email": reporter_email,
            "twitter": reporter_x,
            "linkedin": reporter_linkedin,
            "instagram": reporter_instagram,
            "facebook": reporter_facebook,
            "topics": "",
            "articles": articles,
        }

    except Exception as e:
        print(f"Error: An error occurred while extracting reporter info: {e}")
        return {}


def process_reporters_list(reporters_flat: list[dict]) -> list[dict]:
    """Transform flat list to grouped structure and fetch profile info"""

    # Group articles by reporter
    reporters_dict = {}
    for item in reporters_flat:
        reporter_name = item.get("author_name") or ""
        reporter_url = (item.get("author_url") or "").rstrip("/")

        key = reporter_name

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
            "link": item.get("link") or "",
        }
        reporters_dict[key]["articles"].append(article)

    reporters_list = list(reporters_dict.values())

    # limit articles to 4 per reporter
    for reporter in reporters_list:
        reporter["articles"] = reporter["articles"][:4]

    # Add reporters from the global reporters list
    for reporter in reporters:
        if reporter["url"] not in [r["url"].rstrip("/") for r in reporters_list]:
            reporters_list.append(
                {
                    "name": reporter["name"],
                    "url": reporter["url"],
                    "articles": [],
                }
            )

    print(f"\nProcessing {len(reporters_list)} reporters...")

    processed_reporters = []
    media_name = "La Perla del Sur"
    media_type = ""
    website_url = "https://www.periodicolaperla.com"

    for idx, reporter in enumerate(reporters_list, 1):
        reporter_name = reporter.get("name") or ""
        reporter_url = reporter.get("url") or ""

        print(f"[{idx}/{len(reporters_list)}] {reporter_name}")

        # Get profile info if URL exists
        reporter_info = extract_reporter_info(reporter_url)

        processed_reporters.append(
            {
                "media": media_name,
                "media_type": media_type,
                "website_medium": website_url,
                "reporter_name": reporter_name or reporter_info.get("name") or "",
                "title_role": reporter_info.get("title") or "",
                "email": reporter_info.get("email") or "",
                "phone": reporter_info.get("phone") or "",
                "cellular": reporter_info.get("cellular") or "",
                "twitter": reporter_info.get("twitter") or "",
                "linkedin": reporter_info.get("linkedin") or "",
                "facebook": reporter_info.get("facebook") or "",
                "instagram": reporter_info.get("instagram") or "",
                "topics_covered": reporter_info.get("topics_covered") or "",
                "articles": reporter_info.get("articles")
                or reporter.get("articles")
                or [],
            }
        )

        time.sleep(random.uniform(1, 3))  # sleep for 1 to 3 seconds

    print(f"[OK] Completed {len(processed_reporters)} reporters")
    return processed_reporters


def update_airtable(reporters: list[dict]):
    """Update Airtable with reporter data"""
    print(f"\nUpdating Airtable with {len(reporters)} reporters...")
    api = Api(ACCESS_TOKEN)
    table = api.table(BASE_ID, table_name="Reporters")

    print("Fetching existing reporters from Airtable...")
    # Fetch all existing reporters to check for duplicates
    existing_records = table.all()
    existing_reporters = {}

    # Create a lookup dictionary by name and email
    for record in existing_records:
        fields = record.get("fields", {})
        name = fields.get("Nombre del Reportero", "").strip()

        # Store by both name and email for flexible matching
        if name:
            existing_reporters[name.lower()] = record

    print(f"Found {len(existing_records)} existing reporters in Airtable")

    added_count = 0
    updated_count = 0

    for reporter in reporters:
        reporter_name = (reporter.get("reporter_name") or "").strip()

        record = {
            "Medio": reporter.get("media", ""),
            "Tipo de Medio": reporter.get("media_type", ""),
            "Website del Medio": reporter.get("website_medium"),
            "Nombre del Reportero": reporter.get("reporter_name"),
            "Título/Rol": reporter.get("title_role"),
            "Email": reporter.get("email"),
            "Teléfono": reporter.get("phone"),
            "Celular": reporter.get("cellular"),
            "Twitter/X": reporter.get("twitter"),
            "LinkedIn": reporter.get("linkedin"),
            "Instagram": reporter.get("instagram"),
            "Facebook": reporter.get("facebook"),
            "Temas que Cubre": reporter.get("topics_covered"),
        }

        for i, a in enumerate(reporter.get("articles", [])[:4]):
            record[f"Pub #{i+1} – Título"] = a.get("title", "")
            record[f"Pub #{i+1} – Enlace"] = a.get("link", "")
            record[f"Pub #{i+1} – Fecha"] = a.get("date", "")

        existing_record = None
        if reporter_name and reporter_name.lower() in existing_reporters:
            existing_record = existing_reporters[reporter_name.lower()]

        if existing_record:
            # Update existing reporter
            record_id = existing_record["id"]
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
    # Step 1: Get all articles and reporters
    reporters_flat = get_reporters_list_from_articles(
        "https://www.periodicolaperla.com/ahora/"
    )

    reporters = process_reporters_list(reporters_flat)

    update_airtable(reporters)

    print("All done!")


if __name__ == "__main__":
    main()
