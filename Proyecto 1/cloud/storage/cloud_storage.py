"""
Almacenamiento en formato JSONL para el componente cloud.
Cada día genera un archivo YYYY-MM-DD.jsonl con los artículos nuevos.
"""

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

from config.settings import RAW_NEWS_DIR, STATE_FILE
from shared.models import RawArticle

logger = logging.getLogger(__name__)


def save_articles_jsonl(articles: list[RawArticle]) -> str:
    """Guarda artículos en un archivo JSONL del día actual. Devuelve la ruta."""
    os.makedirs(RAW_NEWS_DIR, exist_ok=True)
    filepath = RAW_NEWS_DIR / f"{date.today().isoformat()}.jsonl"

    with open(filepath, "a", encoding="utf-8") as f:
        for article in articles:
            f.write(json.dumps(article.to_dict(), ensure_ascii=False) + "\n")

    logger.info(f"Guardados {len(articles)} artículos en {filepath}")
    return str(filepath)


def load_articles_jsonl(filepath: str) -> list[RawArticle]:
    """Carga artículos desde un archivo JSONL."""
    articles = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                articles.append(RawArticle.from_dict(json.loads(line)))
    return articles


def load_all_articles(since_date: date | None = None) -> list[RawArticle]:
    """Carga todos los artículos desde archivos JSONL, opcionalmente desde una fecha."""
    articles = []
    if not RAW_NEWS_DIR.exists():
        return articles

    for filepath in sorted(RAW_NEWS_DIR.glob("*.jsonl")):
        file_date_str = filepath.stem  # YYYY-MM-DD
        try:
            file_date = date.fromisoformat(file_date_str)
        except ValueError:
            continue

        if since_date and file_date < since_date:
            continue

        articles.extend(load_articles_jsonl(str(filepath)))

    return articles


def load_state() -> dict:
    """Carga el estado persistente (IDs vistos, última ejecución, etc.)."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}


def save_state(state: dict) -> None:
    """Guarda el estado persistente."""
    os.makedirs(STATE_FILE.parent, exist_ok=True)
    # Mantener solo los últimos 10000 IDs
    if len(state.get("seen_ids", [])) > 10000:
        state["seen_ids"] = state["seen_ids"][-10000:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
