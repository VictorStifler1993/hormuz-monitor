"""
Motor de correlación entre noticias clasificadas y precios del petróleo.
Usa correlación de Spearman (más robusta que Pearson para datos no lineales).
"""

import logging
import hashlib
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from scipy import stats

from shared.models import CorrelationResult

logger = logging.getLogger(__name__)


def build_news_series(
    classified_articles: list[dict],
    freq_minutes: int = 60,
) -> pd.Series:
    """
    Construye una serie temporal de escalación agregada.
    Agrupa artículos por ventana temporal y calcula el score medio ponderado.
    """
    if not classified_articles:
        return pd.Series(dtype=float)

    records = []
    for a in classified_articles:
        ts = a["published_at"] if isinstance(a["published_at"], datetime) else datetime.fromisoformat(a["published_at"])
        records.append({
            "timestamp": ts,
            "escalation": a["escalation_score"],
            "relevance": a["relevance_score"],
        })

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()

    # Agregar por ventana: media ponderada por relevancia
    resampled = df.resample(f"{freq_minutes}min").apply(
        lambda x: np.average(x["escalation"], weights=x["relevance"])
        if len(x) > 0 and x["relevance"].sum() > 0
        else np.nan
    )

    return resampled.dropna()


def build_price_returns(
    oil_prices: list[dict],
    symbol: str = "CL=F",
) -> pd.Series:
    """
    Construye serie de retornos porcentuales del petróleo.
    """
    if not oil_prices:
        return pd.Series(dtype=float)

    records = [
        {
            "timestamp": p["timestamp"] if isinstance(p["timestamp"], datetime) else datetime.fromisoformat(p["timestamp"]),
            "close": p["close"],
        }
        for p in oil_prices
        if p["symbol"] == symbol
    ]

    if not records:
        return pd.Series(dtype=float)

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    returns = df["close"].pct_change().dropna()
    return returns


def compute_correlation(
    news_series: pd.Series,
    price_returns: pd.Series,
    lag_minutes: int = 0,
    method: str = "spearman",
) -> CorrelationResult | None:
    """
    Calcula correlación entre serie de noticias y retornos de precio.
    - lag_minutes: desplaza las noticias hacia atrás (positivo = noticias antes que precio)
    """
    if news_series.empty or price_returns.empty:
        logger.warning("Series vacías, no se puede calcular correlación")
        return None

    # Aplicar lag a la serie de noticias
    if lag_minutes > 0:
        news_shifted = news_series.shift(freq=f"{lag_minutes}min")
    else:
        news_shifted = news_series

    # Alinear series por timestamp (inner join)
    aligned = pd.concat([news_shifted, price_returns], axis=1, join="inner")
    aligned.columns = ["news", "price"]
    aligned = aligned.dropna()

    if len(aligned) < 5:
        logger.warning(f"Menos de 5 puntos alineados (lag={lag_minutes}min)")
        return None

    # Calcular correlación
    if method == "spearman":
        corr, p_value = stats.spearmanr(aligned["news"], aligned["price"])
    elif method == "pearson":
        corr, p_value = stats.pearsonr(aligned["news"], aligned["price"])
    else:
        raise ValueError(f"Método no soportado: {method}")

    analysis_id = hashlib.sha256(
        f"{method}_{lag_minutes}_{len(aligned)}_{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12]

    result = CorrelationResult(
        analysis_id=analysis_id,
        computed_at=datetime.now(timezone.utc),
        news_window_hours=int((news_series.index.max() - news_series.index.min()).total_seconds() / 3600),
        price_window_hours=int((price_returns.index.max() - price_returns.index.min()).total_seconds() / 3600),
        lag_minutes=lag_minutes,
        correlation_coefficient=float(corr),
        p_value=float(p_value),
        sample_size=len(aligned),
        method=method,
        notes=f"Correlación {method} con lag de {lag_minutes} minutos",
    )

    logger.info(
        f"Correlación {method} (lag={lag_minutes}min): "
        f"r={corr:.4f}, p={p_value:.4f}, n={len(aligned)}"
    )

    return result


def sweep_lags(
    news_series: pd.Series,
    price_returns: pd.Series,
    lag_range_minutes: range | None = None,
    method: str = "spearman",
) -> list[CorrelationResult]:
    """
    Prueba múltiples lags para encontrar el óptimo.
    Default: de 0 a 24 horas en pasos de 15 minutos.
    """
    if lag_range_minutes is None:
        lag_range_minutes = range(0, 1440, 15)

    results = []
    for lag in lag_range_minutes:
        result = compute_correlation(news_series, price_returns, lag, method)
        if result:
            results.append(result)

    # Ordenar por correlación absoluta (más fuerte primero)
    results.sort(key=lambda r: abs(r.correlation_coefficient), reverse=True)

    if results:
        best = results[0]
        logger.info(
            f"Mejor lag encontrado: {best.lag_minutes} min "
            f"(r={best.correlation_coefficient:.4f}, p={best.p_value:.4f})"
        )

    return results
