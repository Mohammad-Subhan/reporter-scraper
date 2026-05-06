import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import json
import os
from dotenv import load_dotenv
import datetime
import time

load_dotenv()

from bigquery_sync import upsert_reporters_merge


authors = [
    {
        "name": "jesus davila",
        "url": "https://claridadpuertorico.com/author/jesus-davila",
    },
    {
        "name": "carlos severino valdez",
        "url": "https://claridadpuertorico.com/author/carlos-severino-valdez",
    },
    {
        "name": "miguel angel nater",
        "url": "https://claridadpuertorico.com/author/miguel-angel-nater",
    },
    {
        "name": "jose-enrique-laboy-gomez",
        "url": "https://claridadpuertorico.com/author/jose-enrique-laboy-gomez",
    },
    {
        "name": "olga-i-sanabria-davila",
        "url": "https://claridadpuertorico.com/author/olga-i-sanabria-davila",
    },
    {
        "name": "Marissel Hernandez",
        "url": "https://claridadpuertorico.com/author/marisel-hernandez",
    },
    {
        "name": "hiram-lozada-perez",
        "url": "https://claridadpuertorico.com/author/hiram-lozada-perez",
    },
    {
        "name": "juan-r-recondo",
        "url": "https://claridadpuertorico.com/author/juan-r-recondo",
    },
    {
        "name": "rafael anglada lopez",
        "url": "https://claridadpuertorico.com/author/rafael-anglada-lopez",
    },
    {
        "name": "jorge rodriguez acevedo",
        "url": "https://claridadpuertorico.com/author/jorge-rodriguez-acevedo",
    },
    {
        "name": "elvin calcano ortiz",
        "url": "https://claridadpuertorico.com/author/elvin-calcano-ortiz",
    },
    {
        "name": "ruben ramos colon",
        "url": "https://claridadpuertorico.com/author/ruben-ramos-colon",
    },
    {
        "name": "manuel-de-j-gonzalez",
        "url": "https://claridadpuertorico.com/author/manuel-de-j-gonzalez",
    },
    {
        "name": "jorge mercado",
        "url": "https://claridadpuertorico.com/author/jorge-mercado",
    },
    {
        "name": "en-rojo",
        "url": "https://claridadpuertorico.com/author/en-rojo",
    },
]

claridad_pages = [
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/2/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/3/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/4/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/5/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/6/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/7/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/8/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/9/",
    "https://claridadpuertorico.com/category/nacion/ultimasnoticas/page/10/",
]


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


def get_reporters_list_from_articles(url: str) -> list[dict]:
    """Fetch reporters list from articles on a given page URL"""

    html_content = get_html_playwright(url)

    if not html_content:
        print(f"  Warning: No content found for {url}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    # Find all article elements
    news_article_divs = list(
        soup.find_all("div", class_="td_module_1 td_module_wrap td-animation-stack")
    )

    if not news_article_divs:
        return []

    print(f"Found {len(news_article_divs)} articles")

    reporters = []
    for idx, article_div in enumerate(news_article_divs, 1):
        print(f" Processing article {idx}/{len(news_article_divs)}")

        article_title_div = article_div.find("h3", class_="entry-title td-module-title")
        if article_title_div:
            article_title = article_title_div.get_text(strip=True)
        else:
            article_title = ""

        article_link = article_title_div.find("a")
        if article_link:
            article_link = article_link.get("href")
        else:
            article_link = ""

        article_date = article_div.find("time", class_="entry-date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_author_div = article_div.find("span", class_="td-post-author-name")
        if not article_author_div:
            continue

        article_authors = []
        article_authors_links = article_author_div.find_all("a")

        for author_link in article_authors_links:
            author_name = author_link.get_text(strip=True)
            author_url = (
                author_link.get("href") if author_link.has_attr("href") else ""
            ).rstrip("/")
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
        time.sleep(1)

    print(f"Extracted {len(reporters)} reporters")
    return reporters


def process_news_sources() -> list[dict]:
    all_reporters = []
    for news_url in claridad_pages:
        print(f"\nProcessing news source: {news_url}")
        reporters = get_reporters_list_from_articles(news_url)
        all_reporters.extend(reporters)

    return all_reporters


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "div",
            class_="td_module_1 td_module_wrap td-animation-stack",
        )
    )

    print(f"  Found {len(articles_div_list)} articles")

    articles = []

    # maximum 4
    for article_div in articles_div_list[:4]:
        article_date = article_div.find("time", class_="entry-date")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_title = article_div.find("h3", class_="entry-title td-module-title")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_link = article_div.find("a")
        if article_link and article_link.get("href"):
            article_link = article_link["href"]
        else:
            article_link = ""

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

        reporter_bio_section = soup.find("div", class_="td-ss-main-content")
        if not reporter_bio_section:
            print(f"  Warning: No author bio found for {url}")
            return {}

        reporter_name = reporter_bio_section.find(
            "h1", class_="entry-title td-page-title"
        )
        if reporter_name:
            reporter_name = reporter_name.get_text(strip=True)
        else:
            reporter_name = ""

        reporter_social_div = reporter_bio_section.find(
            "div", class_="td-author-social"
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

    # add authors to reporters list
    for reporter in authors:
        if reporter["name"] not in [r["name"] for r in reporters_list]:
            reporters_list.append(
                {
                    "name": reporter["name"],
                    "url": reporter["url"],
                    "articles": [],
                }
            )

    print(f"\nProcessing {len(reporters_list)} unique reporters...")

    processed_reporters = []
    media_name = "Claridad"
    media_type = ""
    website_url = "https://www.claridadpuertorico.com/"

    for idx, reporter in enumerate(reporters_list, 1):
        reporter_name = reporter.get("name") or ""
        reporter_url = (reporter.get("url") or "").rstrip("/")

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

    print(f"[OK] Completed {len(processed_reporters)} reporters")
    return processed_reporters



def main():
    # Step 1: Get all articles and reporters
    reporters_flat = process_news_sources()

    reporters = process_reporters_list(reporters_flat)

    upsert_reporters_merge(reporters, "claridad.py", match_emails=True)


if __name__ == "__main__":
    main()
