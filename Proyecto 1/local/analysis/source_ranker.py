"""
Ranking de fuentes de noticias por poder predictivo.
Responde: ¿qué fuentes predicen mejor los movimientos de precio?
"""

import logging
from collections import defaultdict

import pandas as pd
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


def rank_sources(
    classified_articles: list[dict],
    oil_prices: list[dict],
    price_symbol: str = "CL=F",
    reaction_window_minutes: int = 120,
) -> pd.DataFrame:
    """
    Para cada fuente de noticias, calcula:
    - correlation: correlación entre escalation_score y movimiento de precio posterior
    - hit_rate: % de veces que la dirección predicha fue correcta
    - avg_lead_time: tiempo medio de adelanto respecto al movimiento de precio
    - n_articles: número de artículos de esa fuente
    """
    # Construir serie de precios
    price_records = [
        {"timestamp": pd.Timestamp(p["timestamp"]), "close": p["close"]}
        for p in oil_prices if p["symbol"] == price_symbol
    ]
    if not price_records:
        return pd.DataFrame()

    prices_df = pd.DataFrame(price_records).set_index("timestamp").sort_index()
    prices_df = prices_df[~prices_df.index.duplicated(keep="first")]

    # Agrupar artículos por fuente
    by_source = defaultdict(list)
    for a in classified_articles:
        by_source[a["source_id"]].append(a)

    rankings = []
    for source_id, articles in by_source.items():
        source_results = _evaluate_source(
            articles, prices_df, reaction_window_minutes
        )
        if source_results:
            source_results["source_id"] = source_id
            source_results["n_articles"] = len(articles)
            rankings.append(source_results)

    if not rankings:
        return pd.DataFrame()

    df = pd.DataFrame(rankings)
    df = df.sort_values("abs_correlation", ascending=False)

    logger.info(f"Ranking de {len(df)} fuentes calculado")
    for _, row in df.head(5).iterrows():
        logger.info(
            f"  {row['source_id']}: corr={row['correlation']:.3f}, "
            f"hit_rate={row['hit_rate']:.1%}, n={row['n_articles']}"
        )

    return df


def _evaluate_source(
    articles: list[dict],
    prices_df: pd.DataFrame,
    reaction_window_minutes: int,
) -> dict | None:
    """Evalúa el poder predictivo de una fuente."""
    escalations = []
    price_changes = []
    hits = 0
    total = 0

    for article in articles:
        esc = article["escalation_score"]
        if abs(esc) < 0.1:  # Ignorar artículos neutrales
            continue

        pub_time = pd.Timestamp(article["published_at"])
        end_time = pub_time + pd.Timedelta(minutes=reaction_window_minutes)

        # Precio al publicar y después
        mask_at = prices_df.index <= pub_time
        mask_after = (prices_df.index > pub_time) & (prices_df.index <= end_time)

        if not mask_at.any() or not mask_after.any():
            continue

        price_at = prices_df.loc[mask_at, "close"].iloc[-1]
        price_after = prices_df.loc[mask_after, "close"].iloc[-1]
        change_pct = (price_after - price_at) / price_at * 100

        escalations.append(esc)
        price_changes.append(change_pct)
        total += 1

        # ¿Dirección correcta?
        if (esc > 0 and change_pct > 0) or (esc < 0 and change_pct < 0):
            hits += 1

    if len(escalations) < 5:
        return None

    corr, p_val = stats.spearmanr(escalations, price_changes)

    return {
        "correlation": float(corr),
        "abs_correlation": abs(float(corr)),
        "p_value": float(p_val),
        "hit_rate": hits / total if total > 0 else 0,
        "avg_escalation": float(np.mean(np.abs(escalations))),
        "avg_price_change": float(np.mean(np.abs(price_changes))),
    }
