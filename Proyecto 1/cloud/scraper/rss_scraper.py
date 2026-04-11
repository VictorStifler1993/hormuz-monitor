"""
Scraper de feeds RSS. Fuente principal: gratis, ilimitada, fiable.
"""

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser

from cloud.scraper.base import BaseScraper
from config.keywords import RSS_FEEDS, HORMUZ_KEYWORDS, OIL_KEYWORDS
from config.settings import MAX_ARTICLES_PER_SOURCE
from shared.models import RawArticle

logger = logging.getLogger(__name__)


class RssScraper(BaseScraper):

    @property
    def source_id(self) -> str:
        return "rss"

    def scrape(self) -> list[RawArticle]:
        articles = []
        all_keywords = [kw.lower() for kw in HORMUZ_KEYWORDS + OIL_KEYWORDS]

        for feed_name, feed_url in RSS_FEEDS.items():
            try:
                feed_articles = self._scrape_feed(feed_name, feed_url, all_keywords)
                articles.extend(feed_articles)
                logger.info(f"RSS {feed_name}: {len(feed_articles)} artículos relevantes")
            except Exception as e:
                logger.warning(f"Error scraping RSS {feed_name}: {e}")

        # Limitar total
        articles = articles[:MAX_ARTICLES_PER_SOURCE * len(RSS_FEEDS)]
        logger.info(f"RSS total: {len(articles)} artículos")
        return articles

    def _scrape_feed(
        self, feed_name: str, feed_url: str, keywords: list[str]
    ) -> list[RawArticle]:
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Feed {feed_name} tiene errores: {feed.bozo_exception}")
            return []

        articles = []
        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")

            if not link or not title:
                continue

            # Filtrar por relevancia usando keywords
            text = f"{title} {summary}".lower()
            if not any(kw in text for kw in keywords):
                # Para feeds generales (BBC, Al Jazeera), filtrar por keywords
                # Para feeds de Google News ya filtrados por query, pasar todo
                if "google_news" not in feed_name:
                    continue

            published_at = self._parse_date(entry)

            articles.append(
                RawArticle(
                    source_id=f"rss_{feed_name}",
                    url=link,
                    title=title,
                    content=summary,
                    published_at=published_at,
                    scraped_at=datetime.now(timezone.utc),
                    language=self._detect_language(entry),
                    raw_metadata={
                        "feed_name": feed_name,
                        "feed_url": feed_url,
                        "tags": [t.get("term", "") for t in entry.get("tags", [])],
                    },
                )
            )

        return articles

    def _parse_date(self, entry) -> datetime:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(
                mktime(entry.published_parsed), tz=timezone.utc
            )
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime.fromtimestamp(
                mktime(entry.updated_parsed), tz=timezone.utc
            )
        return datetime.now(timezone.utc)

    def _detect_language(self, entry) -> str:
        content_lang = entry.get("content", [{}])
        if isinstance(content_lang, list) and content_lang:
            lang = content_lang[0].get("language", "")
            if lang:
                return lang
        return "en"
