"""
Deduplicador de artículos. Dos niveles:
1. Hash de URL: detecta duplicados exactos.
2. Similitud de título: detecta la misma noticia de diferentes fuentes.
"""

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from shared.models import RawArticle


def normalize_url(url: str) -> str:
    """Normaliza URL eliminando parámetros de tracking."""
    tracking_params = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source", "ncid",
    }
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    clean_params = {k: v for k, v in params.items() if k.lower() not in tracking_params}
    clean_query = urlencode(clean_params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query, fragment=""))


def title_words(title: str) -> set[str]:
    """Extrae palabras significativas de un título (>3 chars, lowercase)."""
    words = re.findall(r'\b\w+\b', title.lower())
    return {w for w in words if len(w) > 3}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Similitud de Jaccard entre dos conjuntos."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def deduplicate_articles(
    articles: list[RawArticle],
    seen_ids: set[str] | None = None,
    title_threshold: float = 0.8,
) -> list[RawArticle]:
    """
    Elimina duplicados de una lista de artículos.
    - seen_ids: IDs ya procesados anteriormente (por URL hash)
    - title_threshold: umbral de similitud Jaccard para títulos (0.8 = 80% overlap)
    """
    if seen_ids is None:
        seen_ids = set()

    unique = []
    local_ids = set()
    title_sets: list[set[str]] = []

    for article in articles:
        article_id = article.article_id

        # Nivel 1: duplicado exacto por URL
        if article_id in seen_ids or article_id in local_ids:
            continue

        # Nivel 2: similitud de título
        words = title_words(article.title)
        is_duplicate = False
        for existing_words in title_sets:
            if jaccard_similarity(words, existing_words) >= title_threshold:
                is_duplicate = True
                break

        if is_duplicate:
            continue

        unique.append(article)
        local_ids.add(article_id)
        title_sets.append(words)

    return unique
