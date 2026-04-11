"""
Analizador de lag (retardo) entre eventos noticiosos y movimientos de precio.
Responde a la pregunta: ¿cuánto tarda el mercado en reaccionar a una noticia?
"""

import logging
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


def analyze_event_impact(
    events: list[dict],
    prices: pd.DataFrame,
    window_before_minutes: int = 60,
    window_after_minutes: int = 240,
    min_escalation: float = 0.5,
) -> pd.DataFrame:
    """
    Para cada evento significativo, mide el movimiento del precio
    antes y después del evento.

    Devuelve DataFrame con:
    - event_time, escalation_score, category
    - price_before, price_after, price_change_pct
    - max_impact_minutes (cuándo se alcanzó el máximo impacto)
    """
    results = []

    for event in events:
        esc = event["escalation_score"]
        if abs(esc) < min_escalation:
            continue

        event_time = event["published_at"]
        if isinstance(event_time, str):
            event_time = datetime.fromisoformat(event_time)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        event_time_pd = pd.Timestamp(event_time)

        # Ventana temporal
        t_before = event_time_pd - pd.Timedelta(minutes=window_before_minutes)
        t_after = event_time_pd + pd.Timedelta(minutes=window_after_minutes)

        # Filtrar precios en la ventana
        mask = (prices.index >= t_before) & (prices.index <= t_after)
        window_prices = prices.loc[mask, "close"]

        if len(window_prices) < 3:
            continue

        # Precio en el momento del evento (más cercano)
        idx_at_event = window_prices.index.get_indexer(
            [event_time_pd], method="nearest"
        )[0]
        price_at_event = window_prices.iloc[idx_at_event]

        # Precio antes del evento
        before_mask = window_prices.index < event_time_pd
        if before_mask.any():
            price_before = window_prices.loc[before_mask].iloc[-1]
        else:
            price_before = price_at_event

        # Precio después y máximo impacto
        after_mask = window_prices.index > event_time_pd
        after_prices = window_prices.loc[after_mask]

        if after_prices.empty:
            continue

        # Cambio porcentual respecto al precio en el evento
        changes = (after_prices - price_at_event) / price_at_event * 100
        max_abs_idx = changes.abs().idxmax()
        max_change = changes.loc[max_abs_idx]
        max_impact_minutes = (max_abs_idx - event_time_pd).total_seconds() / 60

        results.append({
            "event_time": event_time,
            "escalation_score": esc,
            "category": event.get("category", "unknown"),
            "title": event.get("title", "")[:80],
            "price_at_event": price_at_event,
            "price_change_pct": float(max_change),
            "max_impact_minutes": float(max_impact_minutes),
            "direction_correct": (esc > 0 and max_change > 0) or (esc < 0 and max_change < 0),
        })

    df = pd.DataFrame(results)
    if not df.empty:
        logger.info(
            f"Análisis de impacto: {len(df)} eventos analizados, "
            f"dirección correcta en {df['direction_correct'].mean():.1%} de los casos"
        )

    return df


def find_optimal_reaction_time(
    events: list[dict],
    prices: pd.DataFrame,
    check_minutes: list[int] | None = None,
) -> dict:
    """
    Determina el tiempo medio de reacción del mercado.
    Prueba diferentes ventanas y encuentra cuándo el impacto es máximo.
    """
    if check_minutes is None:
        check_minutes = [5, 15, 30, 60, 120, 240, 480, 1440]

    correlations_by_window = {}

    for minutes in check_minutes:
        impact_df = analyze_event_impact(
            events, prices, window_after_minutes=minutes
        )
        if impact_df.empty:
            continue

        # Correlación entre escalation_score y price_change
        if len(impact_df) >= 5:
            corr, p_val = stats.spearmanr(
                impact_df["escalation_score"],
                impact_df["price_change_pct"],
            )
            correlations_by_window[minutes] = {
                "correlation": corr,
                "p_value": p_val,
                "n_events": len(impact_df),
            }

    if not correlations_by_window:
        return {"optimal_minutes": None, "results": {}}

    # Encontrar ventana con mayor correlación
    best_minutes = max(
        correlations_by_window,
        key=lambda m: abs(correlations_by_window[m]["correlation"]),
    )

    logger.info(
        f"Tiempo de reacción óptimo: {best_minutes} minutos "
        f"(r={correlations_by_window[best_minutes]['correlation']:.4f})"
    )

    return {
        "optimal_minutes": best_minutes,
        "results": correlations_by_window,
    }
