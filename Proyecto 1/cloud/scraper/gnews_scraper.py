"""
Scraper de GNews API. Complementario al RSS.
Free tier: 100 requests/día → 1 request por ejecución (cada 15 min = 96/día).
"""

import logging
from datetime import datetime, timezone

import requests

from cloud.scraper.base import BaseScraper
from config.keywords import SEARCH_QUERIES
from config.settings import GNEWS_API_KEY, SCRAPE_TIMEOUT_SECONDS
from shared.models import RawArticle

logger = logging.getLogger(__name__)

GNEWS_API_URL = "https://gnews.io/api/v4/search"


class GNewsScraper(BaseScraper):

    @property
    def source_id(self) -> str:
        return "gnews"

    @property
    def rate_limit_per_day(self) -> int:
        return 100

    def scrape(self) -> list[RawArticle]:
        if not GNEWS_API_KEY:
            logger.warning("GNEWS_API_KEY no configurada, saltando GNews")
            return []

        # Una sola query por ejecución para no gastar el límite
        query = SEARCH_QUERIES[0]  # "Strait of Hormuz"
        articles = []

        try:
            response = requests.get(
                GNEWS_API_URL,
                params={
                    "q": query,
                    "lang": "en",
                    "max": 10,
                    "token": GNEWS_API_KEY,
                    "sortby": "publishedAt",
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

                articles.append(
                    RawArticle(
                        source_id="gnews",
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        content=item.get("content", item.get("description", "")),
                        published_at=published_at,
                        scraped_at=datetime.now(timezone.utc),
                        language="en",
                        raw_metadata={
                            "source_name": item.get("source", {}).get("name", ""),
                            "source_url": item.get("source", {}).get("url", ""),
                            "image": item.get("image", ""),
                        },
                    )
                )

            logger.info(f"GNews: {len(articles)} artículos obtenidos")

        except requests.RequestException as e:
            logger.error(f"Error en GNews API: {e}")

        return articles
