"""
Motor de descubrimiento de patrones: "lo que no sabemos que no sabemos".

Busca:
1. Anomalías: movimientos de precio SIN noticias que los expliquen
2. Emergencia de keywords: términos nuevos apareciendo en noticias
3. Períodos de silencio: cómo se comporta el precio sin noticias
4. Causalidad de Granger: ¿las noticias realmente CAUSAN cambios de precio?
5. Detección de régimen: cuándo cambian las "reglas del juego"
6. Interacciones cruzadas: efectos combinados entre categorías
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class PatternDiscoverer:
    """Motor de descubrimiento de patrones ocultos."""

    def __init__(self, classified_articles: list[dict], oil_prices: list[dict],
                 price_symbol: str = "CL=F"):
        self.articles = classified_articles
        self.prices_raw = oil_prices
        self.symbol = price_symbol
        self._build_dataframes()

    def _build_dataframes(self):
        """Construye DataFrames desde los datos en bruto."""
        # Precios
        price_records = [
            {"timestamp": pd.Timestamp(p["timestamp"]), "close": p["close"]}
            for p in self.prices_raw if p["symbol"] == self.symbol
        ]
        if price_records:
            self.prices = pd.DataFrame(price_records).set_index("timestamp").sort_index()
            self.prices = self.prices[~self.prices.index.duplicated(keep="first")]
            self.prices["return_pct"] = self.prices["close"].pct_change() * 100
        else:
            self.prices = pd.DataFrame(columns=["close", "return_pct"])

        # Artículos
        if self.articles:
            self.articles_df = pd.DataFrame(self.articles)
            self.articles_df["timestamp"] = pd.to_datetime(self.articles_df["published_at"])
        else:
            self.articles_df = pd.DataFrame()

    def find_unexplained_price_moves(
        self,
        min_move_pct: float = 2.0,
        news_window_hours: int = 4,
    ) -> pd.DataFrame:
        """
        Encuentra movimientos de precio grandes SIN noticias que los expliquen.
        Estos son los "unknown unknowns" más importantes: algo movió el mercado
        pero no capturamos la causa.
        """
        if self.prices.empty:
            return pd.DataFrame()

        # Encontrar movimientos grandes
        big_moves = self.prices[self.prices["return_pct"].abs() >= min_move_pct].copy()

        if big_moves.empty:
            return pd.DataFrame()

        unexplained = []
        for ts, row in big_moves.iterrows():
            # Buscar noticias en ventana cercana
            window_start = ts - pd.Timedelta(hours=news_window_hours)
            window_end = ts + pd.Timedelta(hours=1)

            if not self.articles_df.empty:
                mask = (
                    (self.articles_df["timestamp"] >= window_start) &
                    (self.articles_df["timestamp"] <= window_end) &
                    (self.articles_df["relevance_score"] >= 0.5)
                )
                nearby_news = self.articles_df.loc[mask]
            else:
                nearby_news = pd.DataFrame()

            if nearby_news.empty:
                unexplained.append({
                    "timestamp": ts,
                    "price_move_pct": row["return_pct"],
                    "close_price": row["close"],
                    "nearby_news_count": 0,
                    "explanation": "SIN NOTICIAS - Investigar manualmente",
                })

        result = pd.DataFrame(unexplained)
        if not result.empty:
            logger.info(
                f"Encontrados {len(result)} movimientos de precio sin explicación "
                f"(>{min_move_pct}% sin noticias en {news_window_hours}h)"
            )
        return result

    def detect_keyword_emergence(
        self,
        window_days: int = 7,
        min_frequency: int = 3,
    ) -> dict:
        """
        Detecta términos nuevos apareciendo en noticias que NO estaban
        en nuestro diccionario de keywords.
        Estos pueden revelar nuevos factores que no habíamos considerado.
        """
        if self.articles_df.empty:
            return {"emerging": [], "declining": []}

        from config.keywords import HORMUZ_KEYWORDS, OIL_KEYWORDS
        known_keywords = set(kw.lower() for kw in HORMUZ_KEYWORDS + OIL_KEYWORDS)

        # Dividir en ventanas temporales
        now = self.articles_df["timestamp"].max()
        recent_start = now - pd.Timedelta(days=window_days)

        recent = self.articles_df[self.articles_df["timestamp"] >= recent_start]
        older = self.articles_df[self.articles_df["timestamp"] < recent_start]

        # Contar palabras
        recent_words = _count_words(recent)
        older_words = _count_words(older)

        # Encontrar palabras emergentes (nuevas o con aumento significativo)
        emerging = []
        for word, count in recent_words.most_common(100):
            if word in known_keywords or len(word) < 4:
                continue
            old_count = older_words.get(word, 0)
            old_rate = old_count / max(len(older), 1)
            new_rate = count / max(len(recent), 1)

            if count >= min_frequency and (old_count == 0 or new_rate > old_rate * 2):
                emerging.append({
                    "word": word,
                    "recent_count": count,
                    "older_count": old_count,
                    "growth_factor": new_rate / old_rate if old_rate > 0 else float("inf"),
                })

        emerging.sort(key=lambda x: x["recent_count"], reverse=True)

        if emerging:
            logger.info(
                f"Términos emergentes detectados: "
                f"{', '.join(e['word'] for e in emerging[:5])}"
            )

        return {"emerging": emerging[:20]}

    def analyze_silent_periods(
        self,
        min_silence_hours: int = 24,
    ) -> dict:
        """
        Analiza períodos sin noticias relevantes.
        ¿El precio se comporta diferente durante "desiertos de noticias"?
        La ausencia de noticias puede ser una señal en sí misma.
        """
        if self.articles_df.empty or self.prices.empty:
            return {}

        # Encontrar gaps en noticias
        sorted_times = self.articles_df["timestamp"].sort_values()
        gaps = sorted_times.diff()

        silent_periods = []
        for i, gap in enumerate(gaps):
            if pd.isna(gap):
                continue
            if gap.total_seconds() / 3600 >= min_silence_hours:
                start = sorted_times.iloc[i - 1] if i > 0 else sorted_times.iloc[0]
                end = sorted_times.iloc[i]
                silent_periods.append({"start": start, "end": end, "hours": gap.total_seconds() / 3600})

        # Comparar volatilidad durante silencio vs con noticias
        silent_volatilities = []
        active_volatilities = []

        for period in silent_periods:
            mask = (self.prices.index >= period["start"]) & (self.prices.index <= period["end"])
            period_returns = self.prices.loc[mask, "return_pct"].dropna()
            if len(period_returns) >= 3:
                silent_volatilities.extend(period_returns.abs().tolist())

        # Períodos activos (con noticias)
        if not self.articles_df.empty:
            for _, article in self.articles_df.iterrows():
                t = article["timestamp"]
                mask = (self.prices.index >= t - pd.Timedelta(hours=2)) & \
                       (self.prices.index <= t + pd.Timedelta(hours=2))
                period_returns = self.prices.loc[mask, "return_pct"].dropna()
                if len(period_returns) >= 2:
                    active_volatilities.extend(period_returns.abs().tolist())

        result = {
            "n_silent_periods": len(silent_periods),
            "avg_silence_hours": np.mean([p["hours"] for p in silent_periods]) if silent_periods else 0,
            "silent_avg_volatility": np.mean(silent_volatilities) if silent_volatilities else 0,
            "active_avg_volatility": np.mean(active_volatilities) if active_volatilities else 0,
        }

        if silent_volatilities and active_volatilities:
            ratio = result["active_avg_volatility"] / max(result["silent_avg_volatility"], 0.001)
            result["volatility_ratio"] = ratio
            logger.info(
                f"Volatilidad activa/silencio: {ratio:.2f}x "
                f"(silencio={result['silent_avg_volatility']:.3f}%, "
                f"activo={result['active_avg_volatility']:.3f}%)"
            )

        return result

    def granger_causality_test(
        self,
        max_lag: int = 10,
        freq: str = "1D",
    ) -> dict:
        """
        Test de causalidad de Granger.
        ¿Los scores de escalación ayudan a predecir cambios de precio
        más allá de lo que los propios precios pasados ya predicen?
        """
        if self.articles_df.empty or self.prices.empty:
            return {"error": "Datos insuficientes"}

        try:
            from statsmodels.tsa.stattools import grangercausalitytests
        except ImportError:
            return {"error": "statsmodels no instalado"}

        # Construir series diarias
        news_daily = self.articles_df.set_index("timestamp").resample(freq).agg({
            "escalation_score": "mean",
        }).fillna(0)

        price_daily = self.prices.resample(freq).agg({
            "return_pct": "mean",
        }).fillna(0)

        # Alinear
        combined = pd.concat([price_daily["return_pct"], news_daily["escalation_score"]],
                            axis=1, join="inner").dropna()
        combined.columns = ["price_return", "escalation"]

        if len(combined) < max_lag + 5:
            return {"error": f"Solo {len(combined)} observaciones, necesario >= {max_lag + 5}"}

        try:
            results = grangercausalitytests(
                combined[["price_return", "escalation"]].values,
                maxlag=max_lag,
                verbose=False,
            )

            granger_results = {}
            for lag, result in results.items():
                f_test = result[0]["ssr_ftest"]
                granger_results[lag] = {
                    "f_statistic": float(f_test[0]),
                    "p_value": float(f_test[1]),
                    "significant": f_test[1] < 0.05,
                }

            # Encontrar el lag más significativo
            best_lag = min(granger_results, key=lambda l: granger_results[l]["p_value"])
            best = granger_results[best_lag]

            logger.info(
                f"Granger causality: mejor lag={best_lag} días, "
                f"F={best['f_statistic']:.2f}, p={best['p_value']:.4f}, "
                f"significativo={'SÍ' if best['significant'] else 'NO'}"
            )

            return {
                "results_by_lag": granger_results,
                "best_lag": best_lag,
                "best_p_value": best["p_value"],
                "is_causal": best["significant"],
                "interpretation": (
                    f"Las noticias SÍ causan cambios de precio (lag={best_lag} días, p={best['p_value']:.4f})"
                    if best["significant"]
                    else f"No se encontró causalidad significativa (mejor p={best['p_value']:.4f})"
                ),
            }

        except Exception as e:
            return {"error": str(e)}

    def detect_regime_changes(self, window_days: int = 30) -> list[dict]:
        """
        Detección de cambios de régimen usando ventanas móviles.
        Detecta cuándo la relación noticias↔precio cambia fundamentalmente.
        """
        if self.articles_df.empty or self.prices.empty:
            return []

        # Construir series diarias
        news_daily = self.articles_df.set_index("timestamp").resample("1D").agg({
            "escalation_score": "mean",
        }).fillna(0)

        price_daily = self.prices.resample("1D").agg({
            "return_pct": "mean",
        }).fillna(0)

        combined = pd.concat(
            [price_daily["return_pct"], news_daily["escalation_score"]],
            axis=1, join="inner"
        ).dropna()
        combined.columns = ["price", "escalation"]

        if len(combined) < window_days * 2:
            return []

        # Correlación móvil
        rolling_corr = combined["price"].rolling(window_days).corr(
            combined["escalation"]
        )

        # Detectar cambios bruscos en la correlación
        corr_changes = rolling_corr.diff().abs()
        threshold = corr_changes.quantile(0.95)

        regime_changes = []
        for ts, change in corr_changes.items():
            if pd.notna(change) and change > threshold:
                corr_before = rolling_corr.loc[:ts].iloc[-2] if len(rolling_corr.loc[:ts]) > 1 else 0
                corr_after = rolling_corr.loc[ts:].iloc[0] if len(rolling_corr.loc[ts:]) > 0 else 0

                regime_changes.append({
                    "timestamp": ts,
                    "correlation_change": float(change),
                    "correlation_before": float(corr_before) if pd.notna(corr_before) else 0,
                    "correlation_after": float(corr_after) if pd.notna(corr_after) else 0,
                    "interpretation": (
                        f"Cambio de régimen detectado: correlación pasó de "
                        f"{corr_before:.2f} a {corr_after:.2f}"
                    ),
                })

        if regime_changes:
            logger.info(f"Detectados {len(regime_changes)} cambios de régimen")

        return regime_changes

    def cross_category_interactions(self) -> dict:
        """
        ¿Los eventos militares después de fracasos diplomáticos tienen
        más impacto que los militares aislados?
        Busca interacciones entre categorías.
        """
        if self.articles_df.empty or self.prices.empty:
            return {}

        categories = ["military", "diplomatic", "economic", "sanctions"]
        results = {}

        for cat in categories:
            cat_articles = self.articles_df[self.articles_df["category"] == cat]
            if len(cat_articles) < 3:
                continue

            # Impacto aislado
            impacts = []
            for _, article in cat_articles.iterrows():
                t = article["timestamp"]
                mask = (self.prices.index >= t) & \
                       (self.prices.index <= t + pd.Timedelta(hours=4))
                period_returns = self.prices.loc[mask, "return_pct"].dropna()
                if not period_returns.empty:
                    impacts.append(period_returns.abs().mean())

            # Impacto cuando precedido por otra categoría (en 48h)
            preceded_impacts = defaultdict(list)
            for _, article in cat_articles.iterrows():
                t = article["timestamp"]
                window_start = t - pd.Timedelta(hours=48)

                preceding = self.articles_df[
                    (self.articles_df["timestamp"] >= window_start) &
                    (self.articles_df["timestamp"] < t) &
                    (self.articles_df["category"] != cat)
                ]

                if not preceding.empty:
                    for prev_cat in preceding["category"].unique():
                        mask = (self.prices.index >= t) & \
                               (self.prices.index <= t + pd.Timedelta(hours=4))
                        period_returns = self.prices.loc[mask, "return_pct"].dropna()
                        if not period_returns.empty:
                            preceded_impacts[prev_cat].append(
                                period_returns.abs().mean()
                            )

            results[cat] = {
                "standalone_avg_impact": float(np.mean(impacts)) if impacts else 0,
                "n_standalone": len(impacts),
                "preceded_by": {
                    prev: {
                        "avg_impact": float(np.mean(imps)),
                        "n_events": len(imps),
                        "amplification": float(np.mean(imps)) / max(np.mean(impacts), 0.001)
                    }
                    for prev, imps in preceded_impacts.items()
                    if len(imps) >= 2
                },
            }

        return results

    def run_full_discovery(self) -> dict:
        """Ejecuta todos los análisis de descubrimiento y devuelve un informe completo."""
        logger.info("=== Iniciando descubrimiento de patrones ===")

        report = {
            "unexplained_moves": self.find_unexplained_price_moves().to_dict("records"),
            "keyword_emergence": self.detect_keyword_emergence(),
            "silent_periods": self.analyze_silent_periods(),
            "granger_causality": self.granger_causality_test(),
            "regime_changes": self.detect_regime_changes(),
            "cross_category": self.cross_category_interactions(),
        }

        logger.info("=== Descubrimiento de patrones completado ===")
        return report


def _count_words(df: pd.DataFrame) -> Counter:
    """Cuenta palabras en títulos y contenido de artículos."""
    import re
    words = Counter()
    for _, row in df.iterrows():
        text = f"{row.get('title', '')} {row.get('content_snippet', '')}".lower()
        tokens = re.findall(r'\b[a-záéíóúñ]{4,}\b', text)
        words.update(tokens)
    return words
