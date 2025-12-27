import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import json
from pyairtable import Api
import os
from dotenv import load_dotenv
import time
import random
import datetime

load_dotenv()

ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

authors = [
    {
        "name": "Natalia Gálvez",
        "url": "https://www.metro.pr/autor/nataliagalvez",
    },
    {
        "name": "Joaquín Rosado Lebrón",
        "url": "https://www.metro.pr/autor/joaquin-rosado-lebron",
    },
    {
        "name": "Jona Valenzuela",
        "url": "https://www.metro.pr/autor/jonathan-valenzuela",
    },
    {
        "name": "Andrea Rodríguez",
        "url": "https://www.metro.pr/autor/andrea-rodriguez",
    },
]


def initialize_playwright():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    return p, browser, page


def get_html_playwright(url: str):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Try to wait for content, but continue if it times out
            try:
                page.goto(url)
                page.wait_for_load_state("networkidle", timeout=10000)
                page.wait_for_timeout(5000)
            except Exception as wait_error:
                print(f"  Warning: Wait timeout, using partial content")

            # Always try to get content even if wait failed
            html_content = page.content()
            browser.close()
            return html_content

    except Exception as e:
        print(f"An error occurred while fetching HTML content: {e}")
        return None


def get_reporters_list_from_articles(url):
    p, browser, page = initialize_playwright()
    try:
        page.goto(url)
        load_more_button = page.locator(".c-button.c-button--medium.c-button--primary")

        i = 1
        while load_more_button.is_visible() and i <= 10:
            print(f"Loading more articles... ({i})")
            load_more_button.click()

            # wait for content to load
            page.wait_for_timeout(5000)
            i += 1

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        news_article_divs = list(
            soup.find_all("div", class_="b-results-list b-results-list--show-image")
        )
        reporters = []
        for article_div in news_article_divs:

            article_title = article_div.find("h2", class_="c-heading")
            if article_title:
                article_title = article_title.find("a")
                if article_title and article_title.has_attr("href"):
                    article_link = (
                        "https://www.metro.pr" + article_title["href"]
                    ).rstrip("/")
                    article_title = article_title.get_text(strip=True)
                else:
                    article_link = ""
                    article_title = ""
            else:
                article_link = ""
                article_title = ""

            attribution_div = article_div.find("div", class_="c-attribution")
            if not attribution_div:
                continue

            article_date = attribution_div.find("time", class_="c-date")
            if article_date and article_date.has_attr("datetime"):
                # 2025-11-04T16:29:04.458Z -> 04/11/2025
                article_date = article_date.get("datetime")
                article_date = datetime.datetime.fromisoformat(article_date).strftime(
                    "%d/%m/%Y"
                )
            else:
                article_date = ""

            reporter_link_tags = list(attribution_div.find_all("a"))

            if reporter_link_tags == []:
                texts = [
                    t.strip()
                    for t in attribution_div.find_all(string=True, recursive=False)
                ]

                if not texts or len(texts) == 0:
                    continue

                reporter_name = texts[0].replace("Por", "").replace("\xa0", "").strip()

                reporters.append(
                    {
                        "name": reporter_name,
                        "reporter_url": "",
                        "article_title": article_title,
                        "article_link": article_link,
                        "article_date": article_date,
                    }
                )
                continue

            for reporter_link_tag in reporter_link_tags:
                reporter_name = reporter_link_tag.get_text(strip=True)
                reporter_link = (
                    "https://www.metro.pr" + reporter_link_tag.get("href") or ""
                ).rstrip("/")
                if reporter_link == "https://www.metro.pr":
                    reporter_link = ""

                reporters.append(
                    {
                        "name": reporter_name,
                        "reporter_url": reporter_link,
                        "article_title": article_title,
                        "article_link": article_link,
                        "article_date": article_date,
                    }
                )

            time.sleep(random.uniform(1, 2))  # sleep for 1 to 2 seconds

        return reporters

    finally:
        browser.close()
        p.stop()


def get_articles(soup: BeautifulSoup) -> list[dict]:
    article_div = soup.find("div", class_="c-stack b-results-list__wrapper")
    if not article_div:
        print("  Warning: No articles section found")
        return []

    articles_div_list = list(
        article_div.find_all(
            "div",
            class_="b-results-list b-results-list--show-image",
        )
    )

    articles = []

    # maximum 4
    for article_div in articles_div_list[:4]:
        article_link = article_div.find("a", class_="c-link")
        if article_link and article_link.get("href"):
            article_link = ("https://www.metro.pr" + article_link["href"]).rstrip("/")
        else:
            article_link = ""

        article_title = article_div.find("h2", class_="c-heading")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_date = article_div.find("time", class_="c-date")
        if article_date and article_date.has_attr("datetime"):
            # 2025-12-12T17:50:33-04:00 -> 12/12/2025
            article_date = article_date.get("datetime")
            article_date = datetime.datetime.fromisoformat(article_date).strftime(
                "%d/%m/%Y"
            )
        else:
            article_date = ""

        articles.append(
            {
                "title": article_title,
                "link": article_link,
                "date": article_date,
            }
        )

    return articles


def extract_reporter_info(url: str) -> dict:
    try:
        html_content = get_html_playwright(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        reporter_bio_section = soup.find(
            "div", class_="c-stack b-full-author-bio__text"
        )
        if not reporter_bio_section:
            print(f"  Warning: No author bio found for {url}")
            return {}

        reporter_name = reporter_bio_section.find(
            "h2", class_="c-heading b-full-author-bio__name"
        )
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_title = reporter_bio_section.find(
            "h3", class_="c-heading b-full-author-bio__role"
        )
        if reporter_title:
            reporter_title = reporter_title.get_text(strip=True)
        else:
            reporter_title = ""

        reporter_social_div = reporter_bio_section.find(
            "div", class_="b-full-author-bio__social-icons"
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
            "title": reporter_title,
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


def process_reporters_list(reporters_list: list[dict]) -> list[dict]:

    reporters_dict = {}
    for reporter in reporters_list:
        reporter_name = reporter.get("name") or ""

        if reporter_name not in reporters_dict:
            reporters_dict[reporter_name] = {
                "name": reporter_name,
                "url": reporter.get("reporter_url") or "",
                "articles": [],
            }

        article = {
            "title": reporter.get("article_title") or "",
            "date": reporter.get("article_date") or "",
            "link": reporter.get("article_link") or "",
        }
        reporters_dict[reporter_name]["articles"].append(article)

    reporters_refined = list(reporters_dict.values())

    # max 4 articles per reporter
    for reporter in reporters_refined:
        reporter["articles"] = reporter["articles"][:4]

    for reporter in authors:
        if reporter["url"] not in [r["url"] for r in reporters_refined]:
            reporters_refined.append(
                {
                    "name": reporter["name"],
                    "url": reporter["url"],
                    "articles": [],
                }
            )

    print(f"\nProcessing {len(reporters_refined)} reporters...")
    reporters = []

    media_name = "Metro World News"
    media_type = ""
    website_url = "https://www.metro.pr"

    for idx, reporter in enumerate(reporters_refined, 1):
        reporter_name = reporter.get("name") or ""
        reporter_url = reporter.get("url") or ""
        reporter_title = reporter.get("title") or ""

        print(f"[{idx}/{len(reporters_refined)}] {reporter_name}")

        if reporter_url != "":
            reporter_info = extract_reporter_info(reporter_url)
        else:
            reporter_info = {}

        reporters.append(
            {
                "media": media_name,
                "media_type": media_type,
                "website_medium": website_url,
                "reporter_name": reporter_name or reporter_info.get("name") or "",
                "title_role": reporter_title or reporter_info.get("title") or "",
                "email": reporter_info.get("email") or reporter.get("email") or "",
                "phone": reporter_info.get("phone") or "",
                "cellular": reporter_info.get("cellular") or "",
                "twitter": reporter_info.get("twitter") or "",
                "linkedin": reporter_info.get("linkedin") or "",
                "facebook": reporter_info.get("facebook") or "",
                "instagram": reporter_info.get("instagram") or "",
                "topics_covered": reporter_info.get("topics") or "",
                "articles": reporter_info.get("articles")
                or reporter.get("articles")
                or [],
            }
        )

        time.sleep(random.uniform(1, 3))  # sleep for 1 to 3 seconds

    print(f"[OK] Completed {len(reporters)} reporters")
    return reporters


def update_airtable(reporters: list[dict]):
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

        # Check if reporter already exists
        existing_record = None
        if reporter_name and reporter_name.lower() in existing_reporters:
            existing_record = existing_reporters[reporter_name.lower()]

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
    all_reporters = get_reporters_list_from_articles("https://www.metro.pr/noticias/")

    if not all_reporters:
        print("No reporters found.")

    reporters = process_reporters_list(all_reporters)

    update_airtable(reporters)

    print("All done!")


if __name__ == "__main__":
    main()
