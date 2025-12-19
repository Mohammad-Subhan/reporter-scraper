from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pyairtable import Api
import os
from dotenv import load_dotenv
import time
import random

load_dotenv()

ACCESS_TOKEN = os.environ.get("AIRTABLE_ACCESS_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")


reporters_profiles = [
    {
        "name": "Lic Alexis Quiñones",
        "title": "Abogado",
        "url": "https://noticel.com/author/alexisquinones/",
    },
    {
        "name": "Adriana Sánchez",
        "title": "Derecho y deporte",
        "url": "https://noticel.com/author/asanc/",
    },
    {
        "name": "Dra. Bárbara D. Barros",
        "title": "Salud Mental & Menopausia",
        "url": "https://noticel.com/author/bdbarros/",
    },
    {
        "name": "Brian Díaz",
        "title": "Presidente & Fundador Pacifico Group",
        "url": "https://noticel.com/author/bdiaz/",
    },
    {
        "name": "José Julio Aparicio",
        "title": "Política y derecho",
        "url": "https://noticel.com/author/chechecehe/",
    },
    {
        "name": "Carlos Johnny Méndez Núñez",
        "title": "Presidente Cámara de Representantes",
        "url": "https://noticel.com/author/cmendez/",
    },
    {
        "name": "Dennis Dávila",
        "title": "Cine",
        "url": "https://noticel.com/author/dennisdavila/",
    },
    {
        "name": "Lic Eddie López Serrano",
        "title": "Abogado y analista político",
        "url": "https://noticel.com/author/eddielopez/",
    },
    {
        "name": "González Pons MD",
        "title": "Médico radiólogo",
        "url": "https://noticel.com/author/egonzanles/",
    },
    {
        "name": "Enrique A. Völckers-Nin",
        "title": "Innovación pública",
        "url": "https://noticel.com/author/evol/",
    },
    {
        "name": "Heriberto N. Saurí",
        "title": "Salud y emergencias",
        "url": "https://noticel.com/author/heribertosauri/",
    },
    {
        "name": "Lic Jaime Sanabria",
        "title": "Profesor de derecho",
        "url": "https://noticel.com/author/jsanabria/",
    },
    {
        "name": "Kiara Genera",
        "title": "Energía Renovable",
        "url": "https://noticel.com/author/kgenera/",
    },
    {
        "name": "Laureano Giraldez MD",
        "title": "Otorrinolaringología y Cirugía de Cabeza y Cuello",
        "url": "https://noticel.com/author/lgiraldez/",
    },
    {
        "name": "Moises Cortés",
        "title": "Consultor Financiero",
        "url": "https://noticel.com/author/mcortes/",
    },
    {
        "name": "Dra. Natalie Pérez Luna",
        "title": "",
        "url": "https://noticel.com/author/natalie-perez-luna/",
    },
    {
        "name": "Orlando Alomá",
        "title": "Gerente de Proyectos en un Startup",
        "url": "https://noticel.com/author/oaloma/",
    },
    {
        "name": "Oscar J. Serrano",
        "title": "Periodista Editor",
        "url": "https://noticel.com/author/oserrano/",
    },
    {
        "name": "Tomás Ramírez",
        "title": "",
        "url": "https://noticel.com/author/ramirez/",
    },
    {
        "name": "Ramón L. Rosario Cortés",
        "title": "Política y derecho",
        "url": "https://noticel.com/author/rrosario/",
    },
    {
        "name": "Víctor García San Inocencio",
        "title": "Política y justicia",
        "url": "https://noticel.com/author/victorgarcia/",
    },
    {
        "name": "Luisito Vigoreaux",
        "title": "Columnista Cultural y de Entretenimiento",
        "url": "https://noticel.com/author/vigouroux/",
    },
    {
        "name": "William Maldonado",
        "title": "Economista y Estratega Financiero",
        "url": "https://noticel.com/author/wmal/",
    },
]


def get_html(url: str):
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

            page.wait_for_load_state("domcontentloaded")
            html_content = page.content()
            browser.close()
            return html_content

    except Exception as e:
        print(f"An error occurred while fetching HTML content: {e}")
        return None


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "div",
            class_="newsCard flex--row space--between",
        )
    )

    articles = []

    # maximum 4
    for article_div in articles_div_list[:4]:
        article_date = article_div.find("div", class_="newsCard__date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_title = article_div.find("h3")
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
        html_content = get_html(url)
        if not html_content:
            print(f"  Warning: No content found for {url}")
            return {}

        soup = BeautifulSoup(html_content, "html.parser")

        reporter_detail_div = soup.find("div", class_="columnistSection__top")
        if not reporter_detail_div:
            print(f"  Warning: No reporter details found for {url}")
            return {}

        reporter_name = reporter_detail_div.find("h5")
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_title = reporter_detail_div.find("p")
        if reporter_title:
            reporter_title = reporter_title.get_text(strip=True)
        else:
            reporter_title = ""

        author_social_div = reporter_detail_div.find("div", class_="socialsBlock")

        reporter_socials = []
        if author_social_div:
            reporter_socials = [
                social["href"]
                for social in author_social_div.find_all("a")
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
                reporter_email = social_link

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


def process_reporters_list(reporters_list: list[dict]) -> list[dict]:
    print(f"\nProcessing {len(reporters_list)} reporters...")
    reporters = []

    for idx, reporter in enumerate(reporters_list, 1):

        reporter_name = reporter.get("name") or ""
        reporter_url = reporter.get("url") or ""
        reporter_title = reporter.get("title") or ""

        print(f"[{idx}/{len(reporters_list)}] {reporter_name}")
        reporter_info = extract_reporter_info(reporter_url)

        media_name = "Noticel"
        media_type = ""
        website_url = "https://www.noticel.com"

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
            record[f"Pub #{i+1} – Fecha"] = a.get("date") or ""

        # Check if reporter already exists
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
    reporters = process_reporters_list(reporters_profiles)

    update_airtable(reporters)

    print("All Done!")


if __name__ == "__main__":
    main()
