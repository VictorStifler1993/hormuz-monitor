"""
Backtester walk-forward sin look-ahead bias.
Simula una estrategia de trading basada en señales de escalación.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Resultados de un backtest."""
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    n_trades: int
    avg_trade_return_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    days_tested: int
    signal_threshold: float


def backtest_escalation_signal(
    classified_articles: list[dict],
    oil_prices: list[dict],
    price_symbol: str = "CL=F",
    signal_threshold: float = 0.5,
    hold_minutes: int = 120,
    initial_capital: float = 100_000,
    transaction_cost_bps: float = 5,
) -> BacktestResult | None:
    """
    Walk-forward backtest:
    - Cuando escalation_score > threshold → posición larga (precio sube)
    - Cuando escalation_score < -threshold → posición corta (precio baja)
    - Mantener posición durante hold_minutes
    - Sin look-ahead bias: solo usa información disponible en el momento
    """
    # Construir serie de precios
    price_records = [
        {"timestamp": pd.Timestamp(p["timestamp"]), "close": p["close"]}
        for p in oil_prices if p["symbol"] == price_symbol
    ]
    if not price_records:
        return None

    prices_df = pd.DataFrame(price_records).set_index("timestamp").sort_index()
    prices_df = prices_df[~prices_df.index.duplicated(keep="first")]

    if len(prices_df) < 10:
        return None

    # Ordenar artículos por fecha
    sorted_articles = sorted(
        classified_articles,
        key=lambda a: a["published_at"],
    )

    trades = []
    tc_rate = transaction_cost_bps / 10000  # basis points a fracción

    for article in sorted_articles:
        esc = article["escalation_score"]
        if abs(esc) < signal_threshold:
            continue

        pub_time = pd.Timestamp(article["published_at"])
        exit_time = pub_time + pd.Timedelta(minutes=hold_minutes)

        # Precio de entrada (más cercano al momento de publicación)
        mask_entry = prices_df.index >= pub_time
        if not mask_entry.any():
            continue
        entry_price = prices_df.loc[mask_entry, "close"].iloc[0]

        # Precio de salida
        mask_exit = prices_df.index >= exit_time
        if not mask_exit.any():
            continue
        exit_price = prices_df.loc[mask_exit, "close"].iloc[0]

        # Dirección: escalada → long, desescalada → short
        direction = 1 if esc > 0 else -1
        raw_return = direction * (exit_price - entry_price) / entry_price
        net_return = raw_return - 2 * tc_rate  # 2x por entrada + salida

        trades.append({
            "entry_time": pub_time,
            "exit_time": exit_time,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "escalation_score": esc,
            "return_pct": net_return * 100,
        })

    if not trades:
        return None

    trades_df = pd.DataFrame(trades)
    returns = trades_df["return_pct"].values

    # Métricas
    total_return = np.prod(1 + returns / 100) - 1
    days = (trades_df["exit_time"].max() - trades_df["entry_time"].min()).days
    days = max(days, 1)
    ann_return = (1 + total_return) ** (365 / days) - 1

    # Sharpe ratio (anualizado)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
    else:
        sharpe = 0

    # Max drawdown
    cumulative = np.cumprod(1 + returns / 100)
    peak = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - peak) / peak
    max_dd = float(np.min(drawdowns)) * 100

    wins = sum(1 for r in returns if r > 0)

    result = BacktestResult(
        total_return_pct=total_return * 100,
        annualized_return_pct=ann_return * 100,
        sharpe_ratio=sharpe,
        max_drawdown_pct=max_dd,
        win_rate=wins / len(returns) if returns.size > 0 else 0,
        n_trades=len(returns),
        avg_trade_return_pct=float(np.mean(returns)),
        best_trade_pct=float(np.max(returns)),
        worst_trade_pct=float(np.min(returns)),
        days_tested=days,
        signal_threshold=signal_threshold,
    )

    logger.info(
        f"Backtest (threshold={signal_threshold}): "
        f"return={result.total_return_pct:.2f}%, "
        f"sharpe={result.sharpe_ratio:.2f}, "
        f"win_rate={result.win_rate:.1%}, "
        f"trades={result.n_trades}"
    )

    return result


def sweep_thresholds(
    classified_articles: list[dict],
    oil_prices: list[dict],
    thresholds: list[float] | None = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Prueba múltiples umbrales de señal para encontrar el óptimo.
    """
    if thresholds is None:
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    results = []
    for threshold in thresholds:
        bt = backtest_escalation_signal(
            classified_articles, oil_prices,
            signal_threshold=threshold, **kwargs
        )
        if bt:
            results.append({
                "threshold": threshold,
                "total_return_pct": bt.total_return_pct,
                "sharpe_ratio": bt.sharpe_ratio,
                "max_drawdown_pct": bt.max_drawdown_pct,
                "win_rate": bt.win_rate,
                "n_trades": bt.n_trades,
            })

    df = pd.DataFrame(results)
    if not df.empty:
        best = df.loc[df["sharpe_ratio"].idxmax()]
        logger.info(
            f"Mejor threshold: {best['threshold']} "
            f"(sharpe={best['sharpe_ratio']:.2f})"
        )

    return df
