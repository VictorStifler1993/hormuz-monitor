"""
Entry point del componente local.
Se ejecuta manualmente en el PC del usuario.
Orquesta: sincronización → clasificación → análisis → informes.
"""

import argparse
import logging
import sys
from pathlib import Path

# Añadir el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import LOG_LEVEL, DB_PATH
from shared.db import init_db, get_connection, insert_classified_article, insert_oil_price
from shared.db import get_unclassified_articles, get_classified_articles, get_oil_prices

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def cmd_sync():
    """Sincroniza datos del cloud (git pull + importar JSONL a SQLite)."""
    from local.ingest.sync_cloud_data import full_sync
    result = full_sync()
    logger.info(f"Sincronización: {result}")


def cmd_classify():
    """Clasifica artículos pendientes usando subagente Claude Code."""
    from local.classifier.subagent_classifier import classify_batch
    from shared.models import RawArticle
    from datetime import datetime

    init_db()
    conn = get_connection()
    try:
        unclassified = get_unclassified_articles(conn)
        if not unclassified:
            logger.info("No hay artículos pendientes de clasificar")
            return

        logger.info(f"{len(unclassified)} artículos pendientes de clasificar")

        # Convertir dicts a RawArticle
        def parse_dt(val):
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val)
            return datetime.now()

        articles = []
        for row in unclassified:
            articles.append(RawArticle(
                source_id=row["source_id"],
                url=row["url"],
                title=row["title"],
                content=row["content"] or "",
                published_at=parse_dt(row["published_at"]),
                scraped_at=parse_dt(row["scraped_at"]),
                language=row.get("language", "en"),
            ))

        classified = classify_batch(articles)

        # Guardar en DB
        for article in classified:
            insert_classified_article(conn, article)

        # Enviar notificaciones si procede
        from local.notifier.email_notifier import process_notifications
        notified = process_notifications(classified)
        if notified:
            logger.info(f"Enviadas {len(notified)} notificaciones por email")

    finally:
        conn.close()


def cmd_prices():
    """Obtiene precios actuales del petróleo."""
    from local.ingest.oil_prices import fetch_all_oil_prices

    init_db()
    conn = get_connection()
    try:
        prices = fetch_all_oil_prices()
        for price in prices:
            insert_oil_price(conn, price)
        logger.info(f"Guardados {len(prices)} registros de precio")
    finally:
        conn.close()


def cmd_correlate():
    """Ejecuta análisis de correlación."""
    from local.analysis.correlator import build_news_series, build_price_returns, sweep_lags

    init_db()
    conn = get_connection()
    try:
        articles = get_classified_articles(conn, min_relevance=0.3)
        prices = get_oil_prices(conn, symbol="CL=F")

        if not articles or not prices:
            logger.warning("Datos insuficientes para correlación")
            return

        news_series = build_news_series(articles)
        price_returns = build_price_returns(prices)

        results = sweep_lags(news_series, price_returns)

        if results:
            best = results[0]
            logger.info(
                f"Mejor correlación: lag={best.lag_minutes}min, "
                f"r={best.correlation_coefficient:.4f}, p={best.p_value:.4f}"
            )
    finally:
        conn.close()


def cmd_discover():
    """Ejecuta el motor de descubrimiento de patrones."""
    from local.analysis.pattern_discovery import PatternDiscoverer
    from local.reports.report_generator import export_to_json

    init_db()
    conn = get_connection()
    try:
        articles = get_classified_articles(conn, min_relevance=0.3)
        prices = get_oil_prices(conn, symbol="CL=F")

        if not articles or not prices:
            logger.warning("Datos insuficientes para descubrimiento")
            return

        discoverer = PatternDiscoverer(articles, prices)
        report = discoverer.run_full_discovery()

        filepath = export_to_json(report, "discovery_latest.json")
        logger.info(f"Informe de descubrimiento guardado en {filepath}")

    finally:
        conn.close()


def cmd_calibrate():
    """Recalibra la escala de escalación con backtesting."""
    from local.analysis.scale_calibrator import recalibrate_scale

    init_db()
    conn = get_connection()
    try:
        articles = get_classified_articles(conn, min_relevance=0.3)
        prices = get_oil_prices(conn, symbol="CL=F")

        if not articles or not prices:
            logger.warning("Datos insuficientes para calibración")
            return

        new_scale = recalibrate_scale(articles, prices)
        logger.info(f"Nueva escala: {len(new_scale)} niveles calibrados")
    finally:
        conn.close()


def cmd_report():
    """Genera informe completo."""
    from local.analysis.correlator import build_news_series, build_price_returns, sweep_lags
    from local.analysis.pattern_discovery import PatternDiscoverer
    from local.analysis.backtester import sweep_thresholds
    from local.analysis.source_ranker import rank_sources
    from local.reports.report_generator import generate_full_report

    init_db()
    conn = get_connection()
    try:
        articles = get_classified_articles(conn, min_relevance=0.3)
        prices = get_oil_prices(conn, symbol="CL=F")

        if not articles or not prices:
            logger.warning("Datos insuficientes para informe")
            return

        # Correlaciones
        news_series = build_news_series(articles)
        price_returns = build_price_returns(prices)
        corr_results = sweep_lags(news_series, price_returns)
        corr_dicts = [r.to_dict() for r in corr_results] if corr_results else []

        # Descubrimiento
        discoverer = PatternDiscoverer(articles, prices)
        discovery = discoverer.run_full_discovery()

        # Backtest
        bt_df = sweep_thresholds(articles, prices)
        bt_dict = bt_df.to_dict("records") if not bt_df.empty else None

        # Ranking de fuentes
        rankings_df = rank_sources(articles, prices)
        rankings = rankings_df.to_dict("records") if not rankings_df.empty else None

        # Generar informe
        summary = generate_full_report(
            articles, prices, corr_dicts, discovery, bt_dict, rankings
        )

        # Mostrar highlights
        for h in summary.get("highlights", []):
            logger.info(f"  → {h}")

    finally:
        conn.close()


def cmd_full():
    """Ejecuta el pipeline completo: sync → classify → prices → correlate → discover → calibrate → report."""
    logger.info("=== Pipeline completo ===")
    cmd_sync()
    cmd_classify()
    cmd_prices()
    cmd_correlate()
    cmd_discover()
    cmd_calibrate()
    cmd_report()
    logger.info("=== Pipeline completado ===")


def main():
    parser = argparse.ArgumentParser(
        description="Hormuz Monitor - Componente Local",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandos disponibles:
  sync        Sincronizar datos del cloud (git pull + importar)
  classify    Clasificar artículos pendientes con Claude Code
  prices      Obtener precios actuales del petróleo
  correlate   Ejecutar análisis de correlación
  discover    Ejecutar descubrimiento de patrones
  calibrate   Recalibrar escala de escalación
  report      Generar informe completo
  full        Ejecutar todo el pipeline
        """,
    )
    parser.add_argument(
        "command",
        choices=["sync", "classify", "prices", "correlate", "discover",
                 "calibrate", "report", "full"],
        help="Comando a ejecutar",
    )

    args = parser.parse_args()

    commands = {
        "sync": cmd_sync,
        "classify": cmd_classify,
        "prices": cmd_prices,
        "correlate": cmd_correlate,
        "discover": cmd_discover,
        "calibrate": cmd_calibrate,
        "report": cmd_report,
        "full": cmd_full,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
