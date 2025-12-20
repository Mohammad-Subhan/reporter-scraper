import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import json
from pyairtable import Api
import os
from dotenv import load_dotenv
import asyncio
import random

load_dotenv()

ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

authors = [
    {
        "name": "Ayeza Díaz Rolón",
        "url": "https://www.elvocero.com/users/profile/adiaz",
    },
    {
        "name": "Carlos Antonio Otero",
        "url": "https://www.elvocero.com/users/profile/cotero",
    },
    {
        "name": "Ileanexis Vera Rosado",
        "url": "https://www.elvocero.com/users/profile/ivera",
    },
    {
        "name": "Jan Figueroa Roqué",
        "url": "https://www.elvocero.com/users/profile/Jan%20Figueroa",
    },
    {
        "name": "Mariam M. Echevarría Báez",
        "url": "https://www.elvocero.com/users/profile/mechevarria",
    },
    {
        "name": "Miguel Rivera Puig",
        "url": "https://www.elvocero.com/users/profile/jrivera",
    },
    {
        "name": "Neidy Rosado",
        "url": "https://www.elvocero.com/users/profile/nrosado",
    },
    {
        "name": "Yaira Solís Escudero",
        "url": "https://www.elvocero.com/users/profile/ysolis",
    },
    {
        "name": "Jarniel Canales Conde",
        "url": "https://www.elvocero.com/users/profile/Jarniel%20Canales",
    },
    {
        "name": "Brandon Garcés",
        "url": "https://www.elvocero.com/users/profile/Brandon%20Garc%C3%A9s",
    },
    {
        "name": "Istra Pacheco",
        "url": "https://www.elvocero.com/users/profile/ipacheco",
    },
    {
        "name": "Rocío Fernández",
        "url": "https://www.elvocero.com/users/profile/Roc%C3%ADo%20Fern%C3%A1ndez",
    },
    {
        "name": "Alexandra Acosta Vilanova",
        "url": "https://www.elvocero.com/users/profile/Alexandra%20Acosta",
    },
    {
        "name": "Glorimar Velázquez",
        "url": "https://www.elvocero.com/users/profile/Glorimar%20Vel%C3%A1zquez",
    },
    {
        "name": "Narianyelis Ortega Soto",
        "url": "https://www.elvocero.com/users/profile/Narianyelis%20Ortega",
    },
    {
        "name": "Stephanie L. López",
        "url": "https://www.elvocero.com/users/profile/Stephanie%20L.%20L%C3%B3pez",
    },
    {
        "name": "Gabriela Meléndez",
        "url": "https://www.elvocero.com/users/profile/gabriela%20mel%c3%a9ndez",
    },
]


async def initialize_playwright():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
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


async def get_html_playwright(url: str):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Try to wait for content, but continue if it times out
            try:
                await page.goto(url)
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception as wait_error:
                print(f"  Warning: Wait timeout, using partial content")

            # Always try to get content even if wait failed
            html_content = await page.content()
            await browser.close()
            return html_content

    except Exception as e:
        print(f"An error occurred while fetching HTML content: {e}")
        return None


async def get_reporters_list(url):
    html_content = await get_html_playwright(url)
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    reporters_profiles = []
    reporters_divs = list(soup.find_all("div", class_="conocenos-block"))

    for reporter_div in reporters_divs:
        reporter_profile_link = reporter_div.find("a")
        if reporter_profile_link and reporter_profile_link.has_attr("href"):
            reporter_profile_link = (
                "https://www.elvocero.com" + reporter_profile_link["href"]
            ).rstrip("/")
        else:
            reporter_profile_link = ""

        reporter_name = reporter_div.find("h3", class_="media-heading")
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporters_profiles.append(
            {
                "name": reporter_name,
                "url": reporter_profile_link,
            }
        )

    return reporters_profiles


async def get_reporter_info_from_article(article_div):
    article_link = article_div.find("a", class_="tnt-asset-link")
    if not article_link or not article_link.has_attr("href"):
        return None, None

    article_url = ("https://www.elvocero.com" + article_link["href"]).rstrip("/")

    html_content = await get_html_playwright(article_url)
    if not html_content:
        return None, None

    soup = BeautifulSoup(html_content, "html.parser")

    reporter_div = soup.find("span", class_="tnt-byline asset-byline")
    if not reporter_div:
        return None, None

    reporter_link_tag = reporter_div.find("a")
    if not reporter_link_tag or not reporter_link_tag.has_attr("href"):
        return None, None
    reporter_name = reporter_link_tag.get_text(strip=True)
    reporter_link = reporter_link_tag["href"]

    return reporter_name, reporter_link


async def get_reporters_list_from_articles(url):
    p, browser, page = await initialize_playwright()
    try:
        # Increase timeout and use domcontentloaded for faster loading
        try:
            await page.goto(url)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as goto_error:
            print(
                f"  Warning: Timeout on initial page load, continuing with partial content..."
            )

        load_more_button = page.locator(
            "#dycol-trigger-63d64ab0-910a-11ec-b48d-b7ebc0fc5bca"
        )

        while await load_more_button.is_visible():
            await load_more_button.click()
            
            await asyncio.sleep(3)  # wait for content to load

        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        news_article_divs = list(soup.find_all("div", class_="asset"))
        reporters = []
        for article_div in news_article_divs:
            reporter_name, reporter_link = await get_reporter_info_from_article(article_div)
            if reporter_name and reporter_link:
                reporters.append(
                    {
                        "name": reporter_name,
                        "url": reporter_link.rstrip("/"),
                    }
                )

            await asyncio.sleep(random.uniform(5, 10))  # sleep for 5 to 10 seconds

        # Remove duplicates based on reporter URL
        unique_reporters = {
            reporter["url"]: reporter for reporter in reporters
        }.values()
        return list(unique_reporters)

    finally:
        await browser.close()
        await p.stop()


async def get_article_info(url: str) -> dict:
    try:
        html_content = await get_html_playwright(url)

        soup = BeautifulSoup(html_content, "html.parser")

        article_title = soup.find("h1", class_="headline")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_date = ""
        article_date_div = soup.find("div", class_="meta")
        if article_date_div:
            article_date_li = article_date_div.find("li", class_="hidden-print")
            if article_date_li:
                article_date_elem = article_date_li.find("time", class_="asset-date")
                if article_date_elem:
                    article_date = article_date_elem.get_text(strip=True)

        return {
            "title": article_title,
            "link": url,
            "date": article_date,
        }

    except Exception as e:
        print(f"An error occurred while processing article info: {e}")
        return {}


async def get_articles(soup: BeautifulSoup) -> list[dict]:
    article_div = soup.find("div", id="posts")
    if not article_div:
        print("  Warning: No articles section found")
        return []

    articles_div_list = list(
        article_div.find_all(
            "article",
            class_="tnt-asset-type-article",
        )
    )

    articles = []

    # maximum 4
    for article_div in articles_div_list[:4]:
        article_link = article_div.find("a", class_="tnt-asset-link")
        if article_link and article_link.get("href"):
            article_link = ("https://www.elvocero.com" + article_link["href"]).rstrip(
                "/"
            )
        else:
            article_link = ""

        article_info = await get_article_info(article_link)

        articles.append(
            {
                "title": article_info.get("title") or "",
                "link": article_link,
                "date": article_info.get("date") or "",
            }
        )

        await asyncio.sleep(random.uniform(5, 10))  # sleep for 5 to 10 seconds

    return articles


async def extract_reporter_info(url: str) -> dict:
    try:
        html_content = await get_html_playwright(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        reporter_bio_section = soup.find("section", id="profile-main")
        if not reporter_bio_section:
            print(f"  Warning: No author bio found for {url}")
            return {}

        reporter_name = reporter_bio_section.find("h1", class_="name real-name")
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_title = reporter_bio_section.find("div", class_="title")
        if reporter_title:
            reporter_title = reporter_title.get_text(strip=True)
        else:
            reporter_title = ""

        reporter_social_div = reporter_bio_section.find("ul", class_="social-links")

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

        articles = await get_articles(soup)

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


async def process_reporters_list(reporters_list: list[dict]) -> list[dict]:
    print(f"\nProcessing {len(reporters_list)} reporters...")
    reporters = []

    for idx, reporter in enumerate(reporters_list, 1):

        reporter_name = reporter.get("name") or ""
        reporter_url = reporter.get("url") or ""
        reporter_title = reporter.get("title") or ""

        print(f"[{idx}/{len(reporters_list)}] {reporter_name}")
        reporter_info = await extract_reporter_info(reporter_url)

        media_name = "El Vocero"
        media_type = ""
        website_url = "https://www.elvocero.com"

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
                "articles": reporter_info.get("articles") or [],
            }
        )

        await asyncio.sleep(random.uniform(5, 10))  # sleep for 5 to 10 seconds

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

        record = {
            "Medio": reporter.get("media") or "",
            "Tipo de Medio": reporter.get("media_type") or "",
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


async def main():
    reporters_list = await get_reporters_list_from_articles(
        "https://www.elvocero.com/lo-mas-reciente/lo-m-s-reciente/collection_63d64ab0-910a-11ec-b48d-b7ebc0fc5bca.html"
    )

    for reporter in reporters_list:
        if reporter["url"] not in [a["url"] for a in authors]:
            authors.append(reporter)

    reporters_list = authors

    # remove where url is empty
    all_reporters = [
        r for r in reporters_list if (r.get("url") is not None and r.get("url") != "")
    ]

    # Remove duplicates based on reporter URL
    unique_reporters = {
        reporter["url"].rstrip("/"): reporter for reporter in all_reporters
    }.values()
    reporters_list = list(unique_reporters)

    reporters = await process_reporters_list(reporters_list)

    update_airtable(reporters)

    print("All done!")


if __name__ == "__main__":
    asyncio.run(main())
