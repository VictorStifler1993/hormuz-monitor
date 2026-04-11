"""
Generador de informes en CSV/JSON.
Exporta resultados de análisis para revisión manual.
"""

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from config.settings import EXPORTS_DIR

logger = logging.getLogger(__name__)


def export_to_json(data: dict | list, filename: str) -> str:
    """Exporta datos a JSON en el directorio de exports."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    filepath = EXPORTS_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Exportado: {filepath}")
    return str(filepath)


def export_to_csv(records: list[dict], filename: str) -> str:
    """Exporta una lista de dicts a CSV."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    filepath = EXPORTS_DIR / filename

    if not records:
        logger.warning(f"Sin datos para exportar a {filename}")
        return str(filepath)

    fieldnames = list(records[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: str(v) if isinstance(v, (list, dict)) else v
                            for k, v in record.items()})

    logger.info(f"Exportado: {filepath} ({len(records)} registros)")
    return str(filepath)


def generate_full_report(
    classified_articles: list[dict],
    oil_prices: list[dict],
    correlation_results: list[dict],
    discovery_results: dict,
    backtest_results: dict | None = None,
    source_rankings: list[dict] | None = None,
) -> dict:
    """
    Genera un informe completo y lo exporta en múltiples formatos.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    exported_files = {}

    # 1. Artículos clasificados
    if classified_articles:
        exported_files["classified_articles"] = export_to_csv(
            classified_articles, f"articles_{timestamp}.csv"
        )

    # 2. Correlaciones
    if correlation_results:
        exported_files["correlations"] = export_to_csv(
            correlation_results, f"correlations_{timestamp}.csv"
        )

    # 3. Descubrimiento de patrones
    if discovery_results:
        exported_files["discovery"] = export_to_json(
            discovery_results, f"discovery_{timestamp}.json"
        )

    # 4. Backtest
    if backtest_results:
        exported_files["backtest"] = export_to_json(
            backtest_results, f"backtest_{timestamp}.json"
        )

    # 5. Ranking de fuentes
    if source_rankings:
        exported_files["source_rankings"] = export_to_csv(
            source_rankings, f"source_rankings_{timestamp}.csv"
        )

    # 6. Resumen ejecutivo
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_articles_classified": len(classified_articles),
        "total_price_points": len(oil_prices),
        "exported_files": exported_files,
        "highlights": _extract_highlights(
            discovery_results, correlation_results, backtest_results
        ),
    }
    exported_files["summary"] = export_to_json(
        summary, f"summary_{timestamp}.json"
    )

    logger.info(f"Informe completo generado: {len(exported_files)} archivos")
    return summary


def _extract_highlights(
    discovery: dict,
    correlations: list[dict],
    backtest: dict | None,
) -> list[str]:
    """Extrae los hallazgos más importantes para el resumen."""
    highlights = []

    # Movimientos sin explicar
    unexplained = discovery.get("unexplained_moves", [])
    if unexplained:
        highlights.append(
            f"ATENCIÓN: {len(unexplained)} movimientos de precio sin noticias que los expliquen"
        )

    # Causalidad de Granger
    granger = discovery.get("granger_causality", {})
    if granger.get("is_causal"):
        highlights.append(
            f"CONFIRMADO: Las noticias causan cambios de precio "
            f"(Granger, p={granger['best_p_value']:.4f})"
        )
    elif "best_p_value" in granger:
        highlights.append(
            f"NO CONFIRMADO: Causalidad Granger no significativa "
            f"(p={granger['best_p_value']:.4f})"
        )

    # Keywords emergentes
    emerging = discovery.get("keyword_emergence", {}).get("emerging", [])
    if emerging:
        words = ", ".join(e["word"] for e in emerging[:3])
        highlights.append(f"Nuevos términos emergentes: {words}")

    # Mejor correlación
    if correlations:
        best = max(correlations, key=lambda c: abs(c.get("correlation_coefficient", 0)))
        highlights.append(
            f"Mejor correlación: r={best['correlation_coefficient']:.3f} "
            f"con lag de {best['lag_minutes']} minutos"
        )

    # Cambios de régimen
    regime = discovery.get("regime_changes", [])
    if regime:
        highlights.append(f"Detectados {len(regime)} cambios de régimen en la relación noticias↔precio")

    return highlights
