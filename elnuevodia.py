from bs4 import BeautifulSoup
import json
import requests
from pyairtable import Api
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

section_headings = set(
    [
        "Noticias",
        "Corresponsalías",
        "Opinión",
        "Negocios",
        "Entretenimiento y Estilos de Vida",
        "Deportes",
        "Breaking News",
        "Edición impresa",
    ]
)


def get_html(url: str):
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


def extract_reporters(url: str) -> list[dict]:
    try:
        html_content = get_html(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return []

        soup = BeautifulSoup(html_content, "html.parser")

        sections = list(
            child
            for child in list(soup.find("div", class_="static-sections").children)[
                1:
            ]  # Skip first child
            if child.find("h2").get_text(strip=True) in section_headings
        )

        reporters = []
        for section in sections:
            reporters_div_list = list(
                section.find(
                    "div", class_="static-sections-list_container_single_col"
                ).children
            )

            for reporter_div in reporters_div_list:
                reporter_name = reporter_div.find("a")
                if reporter_name:
                    reporter_name = reporter_name.get_text(strip=True)
                reporter_profile_url = reporter_div.find("a")["href"]
                reporter_email = (
                    reporter_div.find("div", class_="static-sections-list_profile")
                    .find("span")
                    .find("a")
                )
                if reporter_email:
                    reporter_email = reporter_email.get_text(strip=True)

                reporters.append(
                    {
                        "name": reporter_name,
                        "profile_url": reporter_profile_url,
                        "email": reporter_email,
                    }
                )

        print(f"Extracted {len(reporters)} reporters")
        return reporters

    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def get_article_info(url: str) -> dict:
    try:
        html_content = get_html(url)

        soup = BeautifulSoup(html_content, "html.parser")

        article_title = soup.find("h1", class_="article-headline__title")
        if article_title:
            article_title = article_title.get_text(strip=True)

        article_date = soup.find("div", class_="article-headline__date")
        if article_date:
            article_date = article_date.get_text(strip=True)

        return {
            "title": article_title,
            "link": url,
            "date": article_date,
        }

    except Exception as e:
        print(f"An error occurred while processing article info: {e}")
        return {}


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "article", class_="standard-teaser-container condensed-horizontal news"
        )
    )

    articles = []
    for article in articles_div_list[:4]:
        anchor = article.find(
            "a", class_="standard-teaser-image-container no-decoration square"
        )
        if anchor and anchor.get("href"):
            url = ("https://www.elnuevodia.com" + anchor["href"]).rstrip("/")
            article_info = get_article_info(url)
            articles.append(article_info)

            time.sleep(random.uniform(1, 2))  # sleep for 1 to 2 seconds

    return articles


def extract_reporter_info(url: str) -> dict:
    try:
        html_content = get_html(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        reporter_bio_div = soup.find(
            "div", class_="author-bio-block__container__flex-info"
        )

        if not reporter_bio_div:
            print(f"  Warning: Reporter bio not found for {url}")
            return {}

        reporter_name = reporter_bio_div.find("h1")
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_email = reporter_bio_div.find(
            "a", class_="author-bio-block__container__email"
        )
        if reporter_email:
            reporter_email = reporter_email.get_text(strip=True)
        else:
            reporter_email = ""

        social_div = reporter_bio_div.find("div", class_="author-bio-block__social")
        reporter_socials = []
        if social_div:
            reporter_socials = [
                social["href"]
                for social in social_div.find_all("a")
                if social.get("href")
            ]

        # I want to select the one social link that has "twitter.com" or "x.com" in it
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

        reporter_topics = ""
        reporter_title = ""
        for div in soup.find_all(
            "div", class_="author-detail-page__container__block-container"
        ):
            title_div = div.find(
                "div", class_="author-detail-page__container__detail-title"
            )
            if not title_div:
                continue

            title_text = title_div.get_text(strip=True)
            subtitle_div = div.find(
                "div", class_="author-detail-page__container__detail-subtitle"
            )

            if title_text == "Áreas de especialización" and subtitle_div:
                reporter_topics = subtitle_div.get_text(strip=True)
            elif title_text == "Título oficial" and subtitle_div:
                reporter_title = subtitle_div.get_text(strip=True)

        articles = get_articles(soup)

        return {
            "name": reporter_name,
            "title": reporter_title,
            "email": reporter_email,
            "twitter": reporter_x,
            "linkedin": reporter_linkedin,
            "instagram": reporter_instagram,
            "facebook": reporter_facebook,
            "topics": reporter_topics,
            "articles": articles,
        }

    except Exception as e:
        print(f"An error occurred while extracting reporter info: {e}")
        return {}


def process_reporters_list(reporters_list: list[dict]) -> list[dict]:
    print(f"\nProcessing {len(reporters_list)} reporters...")
    reporters = []

    for idx, reporter in enumerate(reporters_list, 1):
        print(f"[{idx}/{len(reporters_list)}] {reporter['name']}")
        reporter_info = extract_reporter_info(reporter["profile_url"])

        media_name = "El Nuevo Día"
        media_type = ""
        website_url = "https://www.elnuevodia.com"

        reporters.append(
            {
                "media": media_name,
                "media_type": media_type,
                "website_medium": website_url,
                "reporter_name": reporter_info.get("name")
                or reporter.get("name")
                or "",
                "title_role": reporter_info.get("title") or "",
                "email": reporter_info.get("email") or reporter.get("email") or "",
                "phone": reporter_info.get("phone") or "",
                "cellular": reporter_info.get("cellular") or "",
                "twitter": reporter_info.get("twitter") or "",
                "linkedin": reporter_info.get("linkedin") or "",
                "facebook": reporter_info.get("facebook") or "",
                "instagram": reporter_info.get("instagram") or "",
                "topics_covered": reporter_info.get("topics") or "",
                "articles": reporter_info.get("articles") or [],
            }
        )

        time.sleep(random.uniform(1, 3))  # sleep for 1 to 3 seconds

    print(f"[OK] Completed {len(reporters)} reporters")
    return reporters


def update_airtable(reporters: list[dict]):
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
        email = fields.get("Email", "").strip()

        # Store by both name and email for flexible matching
        if name:
            existing_reporters[name.lower()] = record
        if email:
            existing_reporters[email.lower()] = record

    print(f"Found {len(existing_records)} existing reporters in Airtable")

    added_count = 0
    updated_count = 0

    for reporter in reporters:
        reporter_name = (reporter.get("reporter_name") or "").strip()
        reporter_email = (reporter.get("email") or "").strip()

        # Build the record fields
        record = {
            "Medio": reporter.get("media") or "",
            "Tipo de Medio": reporter.get("media_type") or "",
            "Website del Medio": reporter.get("website_medium"),
            "Nombre del Reportero": reporter_name,
            "Título/Rol": reporter.get("title_role"),
            "Email": reporter_email,
            "Teléfono": reporter.get("phone"),
            "Celular": reporter.get("cellular"),
            "Twitter/X": reporter.get("twitter"),
            "LinkedIn": reporter.get("linkedin"),
            "Instagram": reporter.get("instagram"),
            "Facebook": reporter.get("facebook"),
            "Temas que Cubre": reporter.get("topics_covered"),
        }

        # Add article information
        for i, a in enumerate(reporter.get("articles") or []):
            record[f"Pub #{i+1} – Título"] = a.get("title") or ""
            record[f"Pub #{i+1} – Enlace"] = a.get("link") or ""
            record[f"Pub #{i+1} – Fecha"] = a.get("date")

        # Check if reporter already exists
        existing_record = None
        if reporter_name and reporter_name.lower() in existing_reporters:
            existing_record = existing_reporters[reporter_name.lower()]
        elif reporter_email and reporter_email.lower() in existing_reporters:
            existing_record = existing_reporters[reporter_email.lower()]

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
    url = "https://www.elnuevodia.com/sobre-nosotros/"

    reporters_list = extract_reporters(url)

    # only last reporter for testing
    reporters = process_reporters_list(reporters_list)

    update_airtable(reporters)

    print("All done!")


if __name__ == "__main__":
    main()
