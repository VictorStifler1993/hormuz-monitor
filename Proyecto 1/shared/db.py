"""
Helpers para la base de datos SQLite.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from shared.schemas import SCHEMA_SQL
from shared.models import RawArticle, ClassifiedArticle, OilPrice, CorrelationResult


def get_db_path() -> str:
    base = os.environ.get("HORMUZ_DATA_DIR", str(Path(__file__).parent.parent / "data"))
    return os.path.join(base, "hormuz.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.close()


def insert_raw_article(conn: sqlite3.Connection, article: RawArticle) -> bool:
    try:
        conn.execute(
            """INSERT OR IGNORE INTO raw_articles
               (id, source_id, url, title, content, published_at, scraped_at, language, raw_metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                article.article_id,
                article.source_id,
                article.url,
                article.title,
                article.content,
                article.published_at.isoformat(),
                article.scraped_at.isoformat(),
                article.language,
                json.dumps(article.raw_metadata),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def insert_classified_article(conn: sqlite3.Connection, article: ClassifiedArticle) -> bool:
    try:
        conn.execute(
            """INSERT OR REPLACE INTO classified_articles
               (article_id, source_id, url, title, content_snippet, published_at,
                classified_at, relevance_score, escalation_score, category,
                key_actors, key_actions, summary_es, price_impact_prediction,
                confidence, claude_raw_response, notified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                article.article_id,
                article.source_id,
                article.url,
                article.title,
                article.content_snippet,
                article.published_at.isoformat(),
                article.classified_at.isoformat(),
                article.relevance_score,
                article.escalation_score,
                article.category,
                json.dumps(article.key_actors),
                json.dumps(article.key_actions),
                article.summary_es,
                article.price_impact_prediction,
                article.confidence,
                article.claude_raw_response,
                1 if article.notified else 0,
            ),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False


def insert_oil_price(conn: sqlite3.Connection, price: OilPrice) -> bool:
    try:
        conn.execute(
            """INSERT OR IGNORE INTO oil_prices
               (timestamp, symbol, open, high, low, close, volume, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                price.timestamp.isoformat(),
                price.symbol,
                price.open,
                price.high,
                price.low,
                price.close,
                price.volume,
                price.source,
            ),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False


def get_unclassified_articles(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(
        """SELECT r.* FROM raw_articles r
           LEFT JOIN classified_articles c ON r.id = c.article_id
           WHERE c.article_id IS NULL
           ORDER BY r.scraped_at DESC"""
    )
    return [dict(row) for row in cursor.fetchall()]


def get_classified_articles(
    conn: sqlite3.Connection,
    since: Optional[datetime] = None,
    category: Optional[str] = None,
    min_relevance: float = 0.0,
) -> list[dict]:
    query = "SELECT * FROM classified_articles WHERE relevance_score >= ?"
    params: list = [min_relevance]

    if since:
        query += " AND published_at >= ?"
        params.append(since.isoformat())
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY published_at DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_oil_prices(
    conn: sqlite3.Connection,
    symbol: str = "CL=F",
    since: Optional[datetime] = None,
) -> list[dict]:
    query = "SELECT * FROM oil_prices WHERE symbol = ?"
    params: list = [symbol]

    if since:
        query += " AND timestamp >= ?"
        params.append(since.isoformat())

    query += " ORDER BY timestamp ASC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_seen_article_ids(conn: sqlite3.Connection, limit: int = 10000) -> set[str]:
    cursor = conn.execute(
        "SELECT id FROM raw_articles ORDER BY scraped_at DESC LIMIT ?",
        (limit,),
    )
    return {row["id"] for row in cursor.fetchall()}
