import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import json
import os
from dotenv import load_dotenv
import datetime
import time
import random

load_dotenv()

from bigquery_sync import upsert_reporters_merge


sincimillas_pages = [
    "https://sincomillas.com/",
    "https://sincomillas.com/page/2/?post_type=post",
    "https://sincomillas.com/page/3/?post_type=post",
    "https://sincomillas.com/page/4/?post_type=post",
    "https://sincomillas.com/page/5/?post_type=post",
    "https://sincomillas.com/page/6/?post_type=post",
    "https://sincomillas.com/page/7/?post_type=post",
    "https://sincomillas.com/page/8/?post_type=post",
    "https://sincomillas.com/page/9/?post_type=post",
    "https://sincomillas.com/page/10/?post_type=post",
]


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


def get_reporters_list_from_articles(url: str) -> list[dict]:
    """Fetch reporters list from articles on a given page URL"""

    html_content = get_html_requests(url)

    if not html_content:
        print(f"  Warning: No content found for {url}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    # Find all article elements
    news_article_divs = list(soup.find_all("div", class_="item-bot-content"))

    if not news_article_divs:
        return []

    reporters = []
    for idx, article_div in enumerate(news_article_divs, 1):

        article_title = article_div.find("h3", class_="item-title")
        if article_title:
            article_title = article_title.get_text(strip=True)
        else:
            article_title = ""

        article_link_div = article_div.find("h3", class_="item-title")
        if article_link_div:
            article_link = article_link_div.find("a")
            if article_link and article_link.has_attr("href"):
                article_link = article_link.get("href").rstrip("/")
            else:
                article_link = ""
        else:
            article_link = ""

        article_date_div = article_div.find("a", class_="item-date-time")
        if article_date_div:
            article_date = article_date_div.get_text(strip=True)
        else:
            article_date = ""

        article_authors = []
        article_authors_links = article_div.find_all("a", class_="item-author")
        for author_link in article_authors_links:
            author_name = author_link.get_text(strip=True)
            author_url = (
                author_link.get("href").rstrip("/")
                if author_link.has_attr("href")
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
        time.sleep(random.uniform(1, 2))

    return reporters


def process_news_sources() -> list[dict]:
    all_reporters = []
    for news_url in sincimillas_pages:
        print(f"\nProcessing news source: {news_url}")
        reporters = get_reporters_list_from_articles(news_url)
        all_reporters.extend(reporters)

    return all_reporters


def get_articles(soup: BeautifulSoup) -> list[dict]:
    articles_div_list = list(
        soup.find_all(
            "div",
            class_="item-bot-content",
        )
    )

    articles = []

    # maximum 3
    for article_div in articles_div_list[:4]:
        article_date = article_div.find("a", class_="item-date-time")
        if article_date:
            article_date = article_date.get_text(strip=True)
        else:
            article_date = ""

        article_title = article_div.find("h3", class_="item-title")
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

        author_name_div = soup.find("h1", class_="fn-archive-title")
        if author_name_div:
            author_name = author_name_div.find("strong").get_text(strip=True)
        else:
            author_name = ""

        articles = get_articles(soup)

        return {
            "name": author_name,
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

    print(f"\nProcessing {len(reporters_list)} unique reporters...")

    processed_reporters = []
    media_name = "Sin Comillas"
    media_type = ""
    website_url = "https://www.sincomillas.com"

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
        time.sleep(random.uniform(1, 3))

    print(f"[OK] Completed {len(processed_reporters)} reporters")
    return processed_reporters



def main():
    # Step 1: Get all articles and reporters
    reporters_flat = process_news_sources()

    if not reporters_flat:
        print("No reporters found.")
        return

    reporters = process_reporters_list(reporters_flat)

    upsert_reporters_merge(reporters, "sincimillas.py", match_emails=False)


if __name__ == "__main__":
    main()
