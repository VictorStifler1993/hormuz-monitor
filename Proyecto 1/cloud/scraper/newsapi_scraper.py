"""
Scraper de NewsAPI.org. Complementario al RSS.
Free tier: 100 requests/día → 1 request por ejecución.
"""

import logging
from datetime import datetime, timezone

import requests

from cloud.scraper.base import BaseScraper
from config.keywords import SEARCH_QUERIES
from config.settings import NEWSAPI_KEY, SCRAPE_TIMEOUT_SECONDS
from shared.models import RawArticle

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"


class NewsApiScraper(BaseScraper):

    @property
    def source_id(self) -> str:
        return "newsapi"

    @property
    def rate_limit_per_day(self) -> int:
        return 100

    def scrape(self) -> list[RawArticle]:
        if not NEWSAPI_KEY:
            logger.warning("NEWSAPI_KEY no configurada, saltando NewsAPI")
            return []

        query = " OR ".join(f'"{q}"' for q in SEARCH_QUERIES[:3])
        articles = []

        try:
            response = requests.get(
                NEWSAPI_URL,
                params={
                    "q": query,
                    "language": "en",
                    "pageSize": 10,
                    "sortBy": "publishedAt",
                    "apiKey": NEWSAPI_KEY,
                },
                timeout=SCRAPE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("articles", []):
                published_str = item.get("publishedAt", "")
                try:
                    published_at = datetime.fromisoformat(
                        published_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    published_at = datetime.now(timezone.utc)

                content = item.get("content", "") or item.get("description", "") or ""

                articles.append(
                    RawArticle(
                        source_id="newsapi",
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        content=content,
                        published_at=published_at,
                        scraped_at=datetime.now(timezone.utc),
                        language="en",
                        raw_metadata={
                            "source_name": item.get("source", {}).get("name", ""),
                            "author": item.get("author", ""),
                            "image": item.get("urlToImage", ""),
                        },
                    )
                )

            logger.info(f"NewsAPI: {len(articles)} artículos obtenidos")

        except requests.RequestException as e:
            logger.error(f"Error en NewsAPI: {e}")

        return articles
