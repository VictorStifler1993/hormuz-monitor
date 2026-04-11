"""
Calibrador dinámico de la escala de escalación.
Analiza qué scores de escalación realmente precedieron movimientos de precio
y ajusta los umbrales automáticamente basándose en datos reales.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import CALIBRATION_DIR
from shared.models import CalibrationRecord

logger = logging.getLogger(__name__)

# Escala inicial (punto de partida, se recalibrará)
DEFAULT_SCALE = {
    "extreme_escalation": {"min": 0.9, "max": 1.0, "label": "Ataque militar, bloqueo, hundimiento"},
    "high_escalation": {"min": 0.6, "max": 0.89, "label": "Captura de petrolero, despliegue mayor"},
    "moderate_escalation": {"min": 0.3, "max": 0.59, "label": "Amenazas directas, ejercicios militares"},
    "neutral": {"min": -0.29, "max": 0.29, "label": "Neutral, rutina"},
    "moderate_deescalation": {"min": -0.59, "max": -0.3, "label": "Conversaciones diplomáticas"},
    "high_deescalation": {"min": -0.89, "max": -0.6, "label": "Acuerdo parcial, retirada de fuerzas"},
    "extreme_deescalation": {"min": -1.0, "max": -0.9, "label": "Acuerdo de paz, levantamiento de sanciones"},
}


def load_current_scale() -> dict:
    """Carga la escala calibrada más reciente, o la default si no hay calibración."""
    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    cal_file = CALIBRATION_DIR / "current_scale.json"

    if cal_file.exists():
        with open(cal_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SCALE.copy()


def save_calibrated_scale(scale: dict, metadata: dict | None = None) -> str:
    """Guarda la nueva escala calibrada."""
    os.makedirs(CALIBRATION_DIR, exist_ok=True)

    # Guardar como escala actual
    current_file = CALIBRATION_DIR / "current_scale.json"
    with open(current_file, "w", encoding="utf-8") as f:
        json.dump(scale, f, ensure_ascii=False, indent=2)

    # Guardar historial
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    history_file = CALIBRATION_DIR / f"scale_{timestamp}.json"
    history_data = {"scale": scale, "metadata": metadata or {}, "timestamp": timestamp}
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Escala calibrada guardada: {history_file}")
    return str(history_file)


def recalibrate_scale(
    classified_articles: list[dict],
    oil_prices: list[dict],
    price_symbol: str = "CL=F",
    reaction_window_minutes: int = 120,
) -> dict:
    """
    Recalibra la escala de escalación basándose en datos reales.

    Proceso:
    1. Para cada artículo clasificado, mide el movimiento real del precio posterior
    2. Agrupa por rangos de escalation_score
    3. Calcula el impacto medio real de cada rango
    4. Redefine los umbrales para que coincidan con impactos reales
    """
    # Construir serie de precios
    price_records = [
        {"timestamp": pd.Timestamp(p["timestamp"]), "close": p["close"]}
        for p in oil_prices if p["symbol"] == price_symbol
    ]
    if not price_records:
        logger.warning("Sin datos de precio para calibración")
        return load_current_scale()

    prices_df = pd.DataFrame(price_records).set_index("timestamp").sort_index()
    prices_df = prices_df[~prices_df.index.duplicated(keep="first")]

    # Medir impacto real de cada artículo
    impacts = []
    for article in classified_articles:
        esc = article["escalation_score"]
        pub_time = pd.Timestamp(article["published_at"])
        end_time = pub_time + pd.Timedelta(minutes=reaction_window_minutes)

        mask_at = prices_df.index <= pub_time
        mask_after = (prices_df.index > pub_time) & (prices_df.index <= end_time)

        if not mask_at.any() or not mask_after.any():
            continue

        price_at = prices_df.loc[mask_at, "close"].iloc[-1]
        price_after = prices_df.loc[mask_after, "close"].iloc[-1]
        change_pct = (price_after - price_at) / price_at * 100

        impacts.append({
            "escalation_score": esc,
            "price_change_pct": change_pct,
            "abs_change": abs(change_pct),
            "category": article.get("category", "unknown"),
        })

    if len(impacts) < 20:
        logger.warning(f"Solo {len(impacts)} puntos de datos, insuficiente para calibrar")
        return load_current_scale()

    df = pd.DataFrame(impacts)

    # Calcular percentiles de impacto real
    current_scale = load_current_scale()
    new_scale = {}

    # Recalibrar basándose en el impacto real
    # Los umbrales se ajustan para que reflejen el impacto observado
    sorted_by_impact = df.sort_values("abs_change", ascending=False)

    # Top 5% → extremo, top 15% → alto, top 35% → moderado, resto → neutral
    n = len(sorted_by_impact)
    percentiles = {
        "extreme": sorted_by_impact.iloc[:max(1, int(n * 0.05))],
        "high": sorted_by_impact.iloc[int(n * 0.05):int(n * 0.15)],
        "moderate": sorted_by_impact.iloc[int(n * 0.15):int(n * 0.35)],
        "neutral": sorted_by_impact.iloc[int(n * 0.35):],
    }

    calibration_records = []

    for level, data in percentiles.items():
        if data.empty:
            continue

        avg_esc = data["escalation_score"].abs().mean()
        avg_impact = data["abs_change"].mean()

        # Registrar calibración
        for sign, prefix in [(1, "escalation"), (-1, "deescalation")]:
            if level == "neutral":
                old_min = current_scale.get("neutral", {}).get("min", -0.29)
                old_max = current_scale.get("neutral", {}).get("max", 0.29)
                new_scale["neutral"] = {
                    "min": -round(avg_esc, 2),
                    "max": round(avg_esc, 2),
                    "label": f"Neutral (impacto medio: {avg_impact:.3f}%)",
                    "avg_price_impact_pct": round(avg_impact, 4),
                }
            else:
                key = f"{'extreme' if level == 'extreme' else level}_{prefix}"
                old_entry = current_scale.get(key, {})
                old_min = old_entry.get("min", 0)

                if sign > 0:
                    new_min = round(avg_esc * 0.8, 2)
                    new_max = 1.0 if level == "extreme" else round(avg_esc * 1.2, 2)
                else:
                    new_max = -round(avg_esc * 0.8, 2)
                    new_min = -1.0 if level == "extreme" else -round(avg_esc * 1.2, 2)

                new_scale[key] = {
                    "min": new_min,
                    "max": new_max,
                    "label": old_entry.get("label", level),
                    "avg_price_impact_pct": round(avg_impact, 4),
                    "sample_size": len(data),
                }

    # Guardar
    metadata = {
        "total_articles": len(classified_articles),
        "articles_with_price_data": len(impacts),
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "reaction_window_minutes": reaction_window_minutes,
    }

    save_calibrated_scale(new_scale, metadata)

    logger.info(
        f"Escala recalibrada con {len(impacts)} puntos de datos. "
        f"Guardada con {len(new_scale)} niveles."
    )

    return new_scale
