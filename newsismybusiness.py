import requests
from bs4 import BeautifulSoup
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

pages = [
    "https://newsismybusiness.com/",
    "https://newsismybusiness.com/page/2/",
    "https://newsismybusiness.com/page/3/",
    "https://newsismybusiness.com/page/4/",
    "https://newsismybusiness.com/page/5/",
    "https://newsismybusiness.com/page/6/",
]

authors = [
    {
        "name": "Michelle Kantrow-Vázquez",
        "url": "https://newsismybusiness.com/author/mkantrow-2",
    },
    {
        "name": "Eduardo San Miguel Tió",
        "url": "https://newsismybusiness.com/author/eduardosanmiguel",
    },
    {
        "name": "Maria Miranda",
        "url": "https://newsismybusiness.com/author/mariamiranda",
    },
    {
        "name": "Terri Schlichenmeyer",
        "url": "https://newsismybusiness.com/author/terri-schlichenmeyer",
    },
    {
        "name": "G. Torres",
        "url": "https://newsismybusiness.com/author/g-torres",
    },
    {
        "name": "Kiara Visbal-González",
        "url": "https://newsismybusiness.com/author/kiara-visbal",
    },
    {
        "name": "Dennis Costa",
        "url": "https://newsismybusiness.com/author/dennis-costa",
    },
    {
        "name": "Yamilet Aponte-Claudio",
        "url": "https://newsismybusiness.com/author/yamilet-aponte",
    },
    {
        "name": "Brenda Reyes-Tomassini",
        "url": "https://newsismybusiness.com/author/brenda-reyes",
    },
]


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

    html_content = get_html_requests(url)

    if not html_content:
        print(f"  Warning: No content found for {url}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    news_article_divs = list(soup.find_all("div", class_="tt-post-info"))

    if not news_article_divs:
        return []

    print(f"Found {len(news_article_divs)} articles")

    reporters = []
    for idx, article_div in enumerate(news_article_divs, 1):
        print(f" Processing article {idx}/{len(news_article_divs)}")

        article_title_div = article_div.find("a", class_="tt-post-title")
        if article_title_div:
            article_title = article_title_div.get_text(strip=True)
            article_link = (article_title_div.get("href") or "").rstrip("/")
        else:
            article_title = ""
            article_link = ""

        author_div = article_div.find("div", class_="tt-post-label")

        article_date = article_div.find("span", class_="tt-post-date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        if not author_div:
            continue

        article_info = []
        for author in author_div.find_all("a"):
            author_name = author.get_text(strip=True)
            author_url = (author.get("href") or "").rstrip("/")

            article_info.append(
                {
                    "author_name": author_name,
                    "author_url": author_url,
                    "title": article_title,
                    "date": article_date,
                    "link": article_link,
                }
            )

        reporters.extend(article_info)
        time.sleep(random.uniform(1, 2))  # sleep for 1 to 2 seconds

    return reporters


def get_reporters_from_homepage(url: str) -> list[dict]:
    html_content = get_html_requests(url)

    if not html_content:
        print(f"  Warning: No content found for {url}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    news_article_divs = list(soup.find_all("article"))

    if not news_article_divs:
        return []

    reporters = []
    for idx, article_div in enumerate(news_article_divs, 1):
        print(f" Processing article {idx}/{len(news_article_divs)}")

        article_title_div = article_div.find("h3") or article_div.find("h2")
        if article_title_div:
            article_title = article_title_div.get_text(strip=True)
        else:
            article_title = ""

        article_link = article_title_div.find("a")
        if article_link:
            article_link = (article_link.get("href") or "").rstrip("/")
        else:
            article_link = ""

        article_info = get_article_info(article_link)

        reporters.extend(article_info)
        time.sleep(random.uniform(1, 2))  # sleep for 1 to 2 seconds

    return reporters


def get_article_info(article_link: str) -> list[dict]:
    html_content = get_html_requests(article_link)

    if not html_content:
        print(f"  Warning: No content found for {article_link}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    article_info_div = soup.find("article")
    if not article_info_div:
        print(f"Warning: No article info found for {article_link}")
        return []

    article_title = article_info_div.find("h1")
    if article_title:
        article_title = article_title.get_text(strip=True)
    else:
        article_title = ""

    article_meta_info = article_info_div.find("div", class_="tt-blog-user-content")
    authors = []

    author_links = list(article_meta_info.find_all("a"))
    for author_link in author_links:
        authors.append(
            {
                "name": author_link.get_text(strip=True),
                "url": (author_link.get("href") or "").rstrip("/"),
            }
        )

    article_date = article_meta_info.find("span", class_="tt-post-date-single")
    if article_date:
        article_date = article_date.get_text(strip=True)
    else:
        article_date = ""

    article_info = []

    for author in authors:
        article_info.append(
            {
                "author_name": author.get("name"),
                "author_url": author.get("url"),
                "title": article_title,
                "date": article_date,
                "link": article_link,
            }
        )

    return article_info


def process_news_sources() -> list[dict]:
    all_reporters = []
    for news_url in pages:
        print(f"\nProcessing news source: {news_url}")

        if news_url == "https://newsismybusiness.com/":
            reporters = get_reporters_from_homepage(news_url)
            all_reporters.extend(reporters)

        reporters = get_reporters_list_from_articles(news_url)
        all_reporters.extend(reporters)

    return all_reporters


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "div",
            class_="tt-post-info",
        )
    )

    articles = []

    # maximum 4
    for article_div in articles_div_list[:4]:
        article_date = article_div.find("span", class_="tt-post-date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_title = article_div.find("a", class_="tt-post-title")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_link = article_div.find("a", class_="tt-post-title")
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

        articles = get_articles(soup)

        return {
            "name": "",
            "title": "",
            "email": "",
            "twitter": "",
            "linkedin": "",
            "instagram": "",
            "facebook": "",
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

        key = reporter_url

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

    for reporter in authors:
        if reporter["url"] not in [r["url"] for r in reporters_list]:
            reporters_list.append(
                {
                    "name": reporter["name"],
                    "url": reporter["url"],
                    "articles": [],
                }
            )

    print(f"\nProcessing {len(reporters_list)} reporters...")

    processed_reporters = []
    media_name = "Newsismybusiness"
    media_type = ""
    website_url = "https://www.newsismybusiness.com"

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
    print(f"Updating Airtable with {len(reporters)} reporters...")
    api = Api(ACCESS_TOKEN)
    table = api.table(BASE_ID, table_name="Reporters")

    print("\nFetching existing reporters from Airtable...")
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
            "Nombre del Reportero": reporter_name,
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
    reporters_flat = process_news_sources()

    if not reporters_flat:
        print("No reporters found.")
        return

    reporters = process_reporters_list(reporters_flat)

    update_airtable(reporters[:2])


if __name__ == "__main__":
    main()
