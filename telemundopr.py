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


authors = [
    {
        "name": "Maggie More",
        "url": "https://www.telemundopr.com/author/maggie-more",
    },
    {
        "name": "Roberto Cortés",
        "url": "https://www.telemundopr.com/author/roberto-cortes",
    },
    {
        "name": "Zamira Mendoza",
        "url": "https://www.telemundopr.com/author/zamira-mendoza-telemundo-pr",
    },
    {
        "name": "Efrén Arroyo",
        "url": "https://www.telemundopr.com/author/efren-arroyo",
    },
    {
        "name": "Alexandra Fuentes",
        "url": "https://www.telemundopr.com/author/alexandra-fuentes",
    },
    {
        "name": "Jorge Rivera Nieves",
        "url": "https://www.telemundopr.com/author/jorge-rivera-nieves",
    },
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
            page.goto(url)

            # Try to wait for content, but continue if it times out
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
                page.wait_for_timeout(2000)
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
        html_content = get_html_requests(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        article_info_div = soup.find("div", class_="article-header--wrap")
        if not article_info_div:
            print(f"  Warning: No article info div found for {url}")
            return {}

        article_title = article_info_div.find("h1", class_="article-headline")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_author_div = article_info_div.find("h4", class_="article-byline")
        article_author_links = article_author_div.find_all("a")

        article_authors = []

        if article_author_links == []:
            article_author = article_author_div.get_text(strip=True)
            remove_text = ""
            for child in list(article_author_div.children)[1:]:
                remove_text += child.get_text(strip=True)

            article_author = article_author.replace(remove_text, "").strip()
            article_author = article_author.replace("Por ", "").strip()
            article_author_names = article_author.split("|")
            article_author_names = [name.strip() for name in article_author_names]

            for name in article_author_names:
                article_authors.append({"name": name, "url": ""})

            print(f"  No author links found, extracted names: {article_author_names}")
        else:
            for link in article_author_links:
                link_url = link.get("href")
                author_name = link.get_text(strip=True)

                article_authors.append({"name": author_name, "url": link_url})

        article_date = article_author_div.find("time", class_="entry-date published")
        if article_date and article_date.has_attr("datetime"):
            # 2025-12-12T17:50:33-04:00 -> 12/12/2025
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
                    "author_url": author.get("url"),
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

        # Click "Ver más" button 10 times to load more articles
        i = 1
        while i <= 5:
            try:
                # Look for the "Ver más" (See more) button
                load_more_button = page.locator(".content-list-button.button")

                if load_more_button.is_visible():
                    print(f"  Clicking 'Mostrar más' button {i}/10")
                    load_more_button.click()
                    page.wait_for_timeout(5000)
                    i += 1
                else:
                    print(f"  No more 'Mostrar más' button found after {i-1} clicks")
                    break
            except Exception as e:
                print(f"  Could not click more: {e}")
                break

        html_content = page.content()

        browser.close()
        p.stop()

        soup = BeautifulSoup(html_content, "html.parser")

        # Find all article elements
        news_article_divs = list(soup.find_all("div", class_="story-card__text"))

        if not news_article_divs:
            return []

        reporters = []
        for idx, article_div in enumerate(news_article_divs, 1):
            article_link_tag = article_div.find("a", class_="story-card__title-link")

            if article_link_tag and article_link_tag.has_attr("href"):
                article_link = article_link_tag.get("href").rstrip("/")
            else:
                article_link = ""

            if "https://www.telemundopr.com/video/noticias/" in article_link:
                continue

            article_info = get_article_info(article_link)

            reporters.extend(article_info)
            time.sleep(random.uniform(1, 2))

        return reporters

    except Exception as e:
        print(f"Error: An error occurred while extracting reporters from articles: {e}")
        return []


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "div",
            class_="story-card__text",
        )
    )

    articles = []

    # maximum 3
    for article_div in articles_div_list[:4]:
        article_title = article_div.find(
            "h3", class_="story-card__title more-news__story-card-title"
        )
        if article_title:
            article_link = article_title.find("a")
            if article_link and article_link.get("href"):
                article_link = article_link["href"].rstrip("/")
            else:
                article_link = ""
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""
            article_link = ""

        article_info = get_article_info(article_link)
        if article_info and len(article_info) > 0:
            article_date = article_info[0].get("date") or ""
        else:
            article_date = ""

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
    """Extract reporter profile information"""
    try:
        html_content = get_html_requests(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        # Look for reporter bio section
        reporter_bio_section = soup.find("div", class_="profile-meta")
        if not reporter_bio_section:
            print(f"  Warning: No author bio found for {url}")
            return {}

        reporter_name = reporter_bio_section.find("div", class_="profile-name")
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_title = reporter_bio_section.find("div", class_="profile-title")
        if reporter_title:
            reporter_title = reporter_title.get_text(strip=True)
        else:
            reporter_title = ""

        # Find social links
        reporter_socials = []
        social_links = reporter_bio_section.find_all("a", href=True)
        for social in social_links:
            href = social.get("href") or ""
            reporter_socials.append(href)

        reporter_email = ""
        reporter_x = ""
        reporter_facebook = ""
        reporter_linkedin = ""
        reporter_instagram = ""

        for social_link in reporter_socials:
            if "twitter.com" in social_link or "x.com" in social_link:
                reporter_x = social_link.rstrip("/")
            elif "facebook.com" in social_link:
                reporter_facebook = social_link.rstrip("/")
            elif "linkedin.com" in social_link:
                reporter_linkedin = social_link.rstrip("/")
            elif "instagram.com" in social_link:
                reporter_instagram = social_link.rstrip("/")
            elif "mailto:" in social_link:
                reporter_email = social_link.replace("mailto:", "")
            elif "@" in social_link and "." in social_link:
                reporter_email = social_link

        articles = get_articles(soup)

        return {
            "name": reporter_name,
            "title": reporter_title,
            "email": reporter_email,
            "twitter": reporter_x,
            "linkedin": reporter_linkedin,
            "instagram": reporter_instagram,
            "facebook": reporter_facebook,
            "topics_covered": "",
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

        # Normalize key to group all TELEMUNDO entries together
        if "TELEMUNDO" in key.upper():
            key = "TELEMUNDO"

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

    # Limit to 4 articles per reporter
    for reporter in reporters_list:
        reporter["articles"] = reporter["articles"][:4]

    for a in authors:
        if a["url"] not in [r["url"] for r in reporters_list]:
            reporters_list.append(
                {
                    "name": a["name"],
                    "url": a["url"],
                    "articles": [],
                }
            )

    print(f"\nProcessing {len(reporters_list)} unique reporters...")

    processed_reporters = []
    media_name = "Telemundo Puerto Rico"
    media_type = ""
    website_url = "https://www.telemundopr.com"

    for idx, reporter in enumerate(reporters_list, 1):
        reporter_name = reporter.get("name", "")
        reporter_url = reporter.get("url", "")

        print(f"[{idx}/{len(reporters_list)}] {reporter_name}")

        # Get profile info if URL exists
        reporter_info = {}
        if reporter_url:
            reporter_info = extract_reporter_info(reporter_url)

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
                "articles": reporter_info.get("articles")
                or reporter.get("articles")
                or [],
            }
        )
        time.sleep(random.uniform(1, 3))

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
            "Twitter/X": reporter.get("twitter"),
            "LinkedIn": reporter.get("linkedin"),
            "Instagram": reporter.get("instagram"),
            "Facebook": reporter.get("facebook"),
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
    # Step 1: Get all articles and reporters
    reporters_flat = get_reporters_list_from_articles(
        "https://www.telemundopr.com/noticias/"
    )

    if not reporters_flat:
        print("No reporters found.")
        return

    # Step 2: Process reporters list
    reporters = process_reporters_list(reporters_flat)

    # Step 3: Update Airtable
    update_airtable(reporters)


if __name__ == "__main__":
    main()
