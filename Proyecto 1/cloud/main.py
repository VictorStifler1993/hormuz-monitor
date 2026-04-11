"""
Entry point del componente cloud.
Se ejecuta cada 15 minutos vía GitHub Actions.
Solo recoge noticias en bruto (NO clasifica — eso lo hace el componente local).
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Añadir el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import LOG_LEVEL, MAX_RETRIES
from cloud.scraper.rss_scraper import RssScraper
from cloud.storage.cloud_storage import save_articles_jsonl, load_state, save_state

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def scrape_all_sources() -> list:
    """Ejecuta todos los scrapers con reintentos."""
    from cloud.scraper.rss_scraper import RssScraper

    scrapers = [RssScraper()]

    # Intentar importar scrapers opcionales (Fase 2)
    try:
        from cloud.scraper.gnews_scraper import GNewsScraper
        scrapers.append(GNewsScraper())
    except ImportError:
        pass
    try:
        from cloud.scraper.newsapi_scraper import NewsApiScraper
        scrapers.append(NewsApiScraper())
    except ImportError:
        pass

    all_articles = []
    for scraper in scrapers:
        for attempt in range(MAX_RETRIES):
            try:
                articles = scraper.scrape()
                all_articles.extend(articles)
                logger.info(f"{scraper.source_id}: {len(articles)} artículos obtenidos")
                break
            except Exception as e:
                logger.warning(
                    f"Intento {attempt + 1}/{MAX_RETRIES} falló para "
                    f"{scraper.source_id}: {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Backoff: 1s, 2s, 4s
                else:
                    logger.error(f"Scraper {scraper.source_id} falló definitivamente")

    return all_articles


def deduplicate(articles: list, seen_ids: list) -> list:
    """Filtra artículos ya vistos usando deduplicador avanzado."""
    try:
        from cloud.dedup.deduplicator import deduplicate_articles
        return deduplicate_articles(articles, seen_ids=set(seen_ids))
    except ImportError:
        # Fallback simple
        seen_set = set(seen_ids)
        return [a for a in articles if a.article_id not in seen_set]


def check_keyword_alerts(articles: list) -> list:
    """Comprueba si hay artículos con keywords de urgencia (sin IA)."""
    try:
        from cloud.notifier.keyword_alerter import check_alerts
        return check_alerts(articles)
    except ImportError:
        return []


def main():
    logger.info("=== Iniciando ciclo de monitoreo Hormuz ===")

    # 1. Cargar estado
    state = load_state()
    seen_ids = state.get("seen_ids", [])

    # 2. Scraping
    raw_articles = scrape_all_sources()
    logger.info(f"Artículos crudos obtenidos: {len(raw_articles)}")

    # 3. Deduplicar
    new_articles = deduplicate(raw_articles, seen_ids)
    logger.info(f"Artículos nuevos tras deduplicación: {len(new_articles)}")

    if not new_articles:
        logger.info("Sin artículos nuevos. Fin del ciclo.")
        save_state(state)
        return

    # 4. Guardar en JSONL
    filepath = save_articles_jsonl(new_articles)
    logger.info(f"Guardados en {filepath}")

    # 5. Alertas básicas por keywords (sin IA)
    alerts = check_keyword_alerts(new_articles)
    if alerts:
        logger.info(f"¡{len(alerts)} alerta(s) por keywords detectada(s)!")

    # 6. Actualizar estado
    state["seen_ids"] = seen_ids + [a.article_id for a in new_articles]
    save_state(state)

    logger.info(
        f"=== Ciclo completado: {len(new_articles)} artículos nuevos, "
        f"{len(alerts)} alertas ==="
    )


if __name__ == "__main__":
    main()
