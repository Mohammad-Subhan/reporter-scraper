from bs4 import BeautifulSoup
import json
import requests
import os
from dotenv import load_dotenv
import time
import random

load_dotenv()

from bigquery_sync import upsert_reporters_merge



reporters_profiles = [
    {
        "name": "Yalixa Rivera Cruz",
        "url": "https://www.primerahora.com/autor/yalixa-rivera-cruz",
    },
    {
        "name": "Mildred Tirado Vázquez",
        "url": "https://www.primerahora.com/autor/mildred-tirado-vazquez",
    },
    {
        "name": "Noel Piñeiro Planas",
        "url": "https://www.primerahora.com/autor/noel-pineiro-planas",
    },
    {
        "name": "Edlyn M. Vega Rodríguez",
        "url": "https://www.primerahora.com/autor/edlyn-m-vega-rodriguez",
    },
    {
        "name": "Samuel Mujica de León",
        "url": "https://www.primerahora.com/autor/samuel-mujica-de-leon",
    },
    {
        "name": "Luis Alfonso Oliveras Quiles",
        "url": "https://www.primerahora.com/autor/luis-alfonso-oliveras-quiles",
    },
    {
        "name": "Karol Joselyn Sepúlveda",
        "url": "https://www.primerahora.com/autor/karol-joselyn-sepulveda",
    },
    {
        "name": "Jayson Vázquez Torres",
        "url": "https://www.primerahora.com/autor/jayson-vazquez-torres",
    },
    {
        "name": "Fernando Ribas Reyes",
        "url": "https://www.primerahora.com/autor/fernando-ribas-reyes",
    },
    {
        "name": "Glenn Santana",
        "url": "https://www.primerahora.com/autor/glenn-santana",
    },
    {
        "name": "Maribel Hernández Pérez",
        "url": "https://www.primerahora.com/autor/maribel-hernandez-perez",
    },
    {
        "name": "Rosa Escribano Carrasquillo",
        "url": "https://www.primerahora.com/autor/rosa-escribano-carrasquillo",
    },
    {
        "name": "Keishla M. Carbó Otero",
        "url": "https://www.primerahora.com/autor/keishla-m-carbo-otero",
    },
    {
        "name": "Osman Pérez Méndez",
        "url": "https://www.primerahora.com/autor/osman-perez-mendez",
    },
    {
        "name": "Frances Rosario",
        "url": "https://www.primerahora.com/autor/frances-rosario",
    },
    {
        "name": "Hillary Román",
        "url": "https://www.primerahora.com/autor/Hillary",
    },
    {
        "name": "Joseph Reboyras",
        "url": "https://www.primerahora.com/autor/Joseph",
    },
    {
        "name": "Sara R. Marrero Cabán",
        "url": "https://www.primerahora.com/autor/sara-marrero-caban",
    },
    {
        "name": "Pedro Correa Henry",
        "url": "https://www.primerahora.com/autor/pedro-correa-henry",
    },
    {
        "name": "Francisco Quiñones",
        "url": "https://www.primerahora.com/autor/Francisco",
    },
    {
        "name": "Víctor Ramos Rosado",
        "url": "https://www.primerahora.com/autor/vramosrosado",
    },
    {
        "name": "Carlos González",
        "url": "https://www.primerahora.com/autor/carlos-gonzalez",
    },
    {
        "name": "Damaris Hernández Mercado",
        "url": "https://www.primerahora.com/autor/damaris-hernandez-mercado",
    },
    {
        "name": "Jomar José Rivera Cedeño",
        "url": "https://www.primerahora.com/autor/jomar-jose-rivera-cedeno",
    },
    {
        "name": "Ana Enid López",
        "url": "https://www.primerahora.com/autor/ana-enid-lopez",
    },
    {
        "name": "Eliezer Ríos Camacho",
        "url": "https://www.primerahora.com/autor/eliezer-rios-camacho",
    },
]


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

        reporters_div_list = list(soup.find_all("div", class_="StaticProfile__info"))

        reporters = []
        for reporter_div in reporters_div_list:

            reporter_name = reporter_div.find("h3")
            if reporter_name:
                reporter_name = reporter_name.get_text(strip=True)
            else:
                reporter_name = ""

            reporter_title = reporter_div.find("h4")
            if reporter_title:
                reporter_title = reporter_title.get_text(strip=True)
            else:
                reporter_title = ""

            reporter_profile_link = reporter_div.find("a")
            if reporter_profile_link and reporter_profile_link.get("href"):
                reporter_profile_link = (
                    "https://www.primerahora.com" + reporter_profile_link["href"]
                ).rstrip("/")
            else:
                reporter_profile_link = ""

            reporters.append(
                {
                    "name": reporter_name,
                    "title": reporter_title,
                    "profile_url": reporter_profile_link,
                }
            )

        return reporters

    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "li",
            class_="ListItemTeaser",
        )
    )

    articles = []

    # maximum 3
    for article_div in articles_div_list[:4]:
        article_date = article_div.find("div", class_="ListItemTeaser__date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_title = article_div.find(
            "h3", class_="ListItemTeaser__title TeaserTitle"
        )
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_link = article_div.find("a", class_="TeaserImage ListItemTeaser__image")
        if article_link and article_link.get("href"):
            article_link = (
                "https://www.primerahora.com" + article_link["href"]
            ).rstrip("/")
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

        author_bio_div = soup.find("div", class_="AuthorBio__info")
        if not author_bio_div:
            print(f"  Warning: No author bio found for {url}")
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

        author_name = author_bio_div.find("h2", class_="AuthorBio__name")
        if author_name:
            author_name = author_name.get_text(strip=True)
        else:
            author_name = ""

        author_social_div = author_bio_div.find(
            "div", class_="AuthorBio__iconContainer"
        )

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
                reporter_x = social_link.rstrip("/")
            elif "facebook.com" in social_link:
                reporter_facebook = social_link.rstrip("/")
            elif "linkedin.com" in social_link:
                reporter_linkedin = social_link.rstrip("/")
            elif "instagram.com" in social_link:
                reporter_instagram = social_link.rstrip("/")
            elif "mailto:" in social_link:
                reporter_email = social_link.replace("mailto:", "")

        articles = get_articles(soup)

        return {
            "name": author_name,
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
    for reporter in reporters_profiles:
        reporter_name = reporter.get("name") or ""
        reporter_profile_link = reporter.get("url") or ""

        # Update reporters_list with profile URLs from reporters_profiles
        for r in reporters_list:
            if r.get("name") == reporter_name and not r.get("profile_url"):
                r["profile_url"] = reporter_profile_link

        if reporter_name not in [r.get("name") for r in reporters_list]:
            reporters_list.append(
                {
                    "name": reporter_name,
                    "title": "",
                    "profile_url": reporter_profile_link,
                }
            )

    print(f"\nProcessing {len(reporters_list)} reporters...")
    reporters = []

    for idx, reporter in enumerate(reporters_list, 1):

        reporter_name = reporter.get("name") or ""
        reporter_url = reporter.get("profile_url") or ""
        reporter_title = reporter.get("title") or ""

        print(f"[{idx}/{len(reporters_list)}] {reporter_name}")
        reporter_info = extract_reporter_info(reporter_url)

        media_name = "Primera Hora"
        media_type = ""
        website_url = "https://www.primerahora.com"

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



def main():
    url = "https://www.primerahora.com/quienes-somos/"

    reporters_list = extract_reporters(url)

    reporters = process_reporters_list(reporters_list)

    upsert_reporters_merge(reporters, "primerahora.py", match_emails=True)

    print("All done!")


if __name__ == "__main__":
    main()
