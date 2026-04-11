"""
Sincroniza datos del componente cloud (JSONL en el repo) con la base de datos SQLite local.
"""

import json
import logging
import subprocess
from pathlib import Path

from config.settings import RAW_NEWS_DIR, DB_PATH
from cloud.storage.cloud_storage import load_all_articles
from shared.db import get_connection, init_db, insert_raw_article, get_seen_article_ids

logger = logging.getLogger(__name__)


def git_pull() -> bool:
    """Ejecuta git pull para traer datos nuevos del repo."""
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent),
        )
        if result.returncode == 0:
            logger.info(f"Git pull exitoso: {result.stdout.strip()}")
            return True
        else:
            logger.warning(f"Git pull falló: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error en git pull: {e}")
        return False


def sync_jsonl_to_sqlite() -> int:
    """
    Importa artículos de archivos JSONL a SQLite.
    Devuelve el número de artículos nuevos importados.
    """
    init_db()
    conn = get_connection()

    try:
        # Obtener IDs ya en la DB
        existing_ids = get_seen_article_ids(conn)

        # Cargar todos los artículos de JSONL
        all_articles = load_all_articles()
        logger.info(f"Artículos totales en JSONL: {len(all_articles)}")

        # Insertar solo los nuevos
        new_count = 0
        for article in all_articles:
            if article.article_id not in existing_ids:
                if insert_raw_article(conn, article):
                    new_count += 1

        logger.info(f"Importados {new_count} artículos nuevos a SQLite")
        return new_count

    finally:
        conn.close()


def full_sync() -> dict:
    """Sincronización completa: git pull + importar a SQLite."""
    logger.info("=== Iniciando sincronización completa ===")

    pull_ok = git_pull()
    new_articles = sync_jsonl_to_sqlite()

    result = {
        "git_pull_ok": pull_ok,
        "new_articles_imported": new_articles,
    }
    logger.info(f"Sincronización completada: {result}")
    return result
