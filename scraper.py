#!/usr/bin/env python3
"""Iran conflict news scraper using RSS feeds with SQLite storage."""

import argparse
import sqlite3
import time
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

DB_PATH = "iran_news.db"

KEYWORDS = [
    "iran", "iranian", "tehran", "khamenei", "irgc",
    "persian gulf", "strait of hormuz",
]

RSS_FEEDS = [
    {
        "name": "Google News",
        "url": "https://news.google.com/rss/search?q=iran+war+conflict&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "type": "standard",
    },
    {
        "name": "BBC Middle East",
        "url": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
        "type": "standard",
    },
    {
        "name": "Reuters (via Google)",
        "url": "https://news.google.com/rss/search?q=iran+site:reuters.com&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
    {
        "name": "AP News (via Google)",
        "url": "https://news.google.com/rss/search?q=iran+site:apnews.com&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
    # Middle East specialists
    {
        "name": "Iran International",
        "url": "https://news.google.com/rss/search?q=iran+site:iranintl.com&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
    {
        "name": "Times of Israel",
        "url": "https://www.timesofisrael.com/feed/",
        "type": "standard",
    },
    {
        "name": "Jerusalem Post",
        "url": "https://news.google.com/rss/search?q=iran+site:jpost.com&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
    {
        "name": "Middle East Eye",
        "url": "https://news.google.com/rss/search?q=iran+site:middleeasteye.net&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
    {
        "name": "Al-Monitor",
        "url": "https://news.google.com/rss/search?q=iran+site:al-monitor.com&hl=en-US&gl=US&ceid=US:en",
        "type": "google",
    },
]


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            source TEXT NOT NULL,
            pub_date TEXT,
            link TEXT,
            scraped_at TEXT NOT NULL,
            UNIQUE(title, source)
        )
    """)
    conn.commit()
    return conn


def matches_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def parse_pub_date(entry) -> str | None:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None
    try:
        dt = dateparser.parse(raw)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def parse_google_news_feed(feed_cfg: dict) -> list[dict]:
    feed = feedparser.parse(feed_cfg["url"])
    articles = []
    for entry in feed.entries:
        title = entry.get("title", "")
        # Strip " - SourceName" suffix common in Google News
        if " - " in title:
            title = title.rsplit(" - ", 1)[0].strip()

        articles.append({
            "title": title,
            "description": "",  # Google News descriptions are junk HTML
            "source": feed_cfg["name"],
            "pub_date": parse_pub_date(entry),
            "link": entry.get("link", ""),
        })
    return articles


def parse_standard_rss_feed(feed_cfg: dict) -> list[dict]:
    feed = feedparser.parse(feed_cfg["url"])
    articles = []
    for entry in feed.entries:
        title = entry.get("title", "")
        description = entry.get("summary", entry.get("description", ""))

        # Keyword filter for standard feeds
        combined = f"{title} {description}"
        if not matches_keywords(combined):
            continue

        articles.append({
            "title": title,
            "description": description,
            "source": feed_cfg["name"],
            "pub_date": parse_pub_date(entry),
            "link": entry.get("link", ""),
        })
    return articles


def scrape_feed(feed_cfg: dict) -> list[dict]:
    if feed_cfg["type"] == "google":
        return parse_google_news_feed(feed_cfg)
    return parse_standard_rss_feed(feed_cfg)


def store_articles(conn: sqlite3.Connection, articles: list[dict]) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for a in articles:
        try:
            conn.execute(
                """INSERT INTO articles (title, description, source, pub_date, link, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (a["title"], a["description"], a["source"], a["pub_date"], a["link"], now),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # duplicate
    conn.commit()
    return inserted


def run_scraper(db_path: str = DB_PATH):
    conn = init_db(db_path)
    total_new = 0
    for feed_cfg in RSS_FEEDS:
        try:
            articles = scrape_feed(feed_cfg)
            new = store_articles(conn, articles)
            total_new += new
            print(f"  {feed_cfg['name']}: {len(articles)} found, {new} new")
        except Exception as e:
            print(f"  {feed_cfg['name']}: ERROR - {e}")
    conn.close()
    print(f"Total new articles stored: {total_new}")
    return total_new


def main():
    parser = argparse.ArgumentParser(description="Iran conflict news scraper")
    parser.add_argument("--loop", action="store_true", help="Run continuously every 30 minutes")
    parser.add_argument("--interval", type=int, default=1800, help="Loop interval in seconds (default: 1800)")
    args = parser.parse_args()

    if args.loop:
        print("Running in loop mode. Press Ctrl+C to stop.")
        while True:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scraping...")
            run_scraper()
            print(f"Sleeping {args.interval}s...")
            time.sleep(args.interval)
    else:
        print("Scraping Iran conflict news...")
        run_scraper()


if __name__ == "__main__":
    main()
