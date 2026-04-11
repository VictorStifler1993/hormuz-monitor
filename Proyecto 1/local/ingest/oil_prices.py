"""
Ingesta de precios de futuros del petróleo.
Fuente primaria: yfinance (gratis). Fallback: Alpha Vantage.
"""

import logging
from datetime import datetime, timezone, timedelta

import yfinance as yf

from config.settings import ALPHA_VANTAGE_KEY, OIL_SYMBOLS
from shared.models import OilPrice

logger = logging.getLogger(__name__)


def fetch_oil_prices_yfinance(
    symbol: str = "CL=F",
    period: str = "1mo",
    interval: str = "1h",
) -> list[OilPrice]:
    """
    Obtiene precios del petróleo desde Yahoo Finance.
    - symbol: "CL=F" (WTI) o "BZ=F" (Brent)
    - period: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"
    - interval: "1m", "5m", "15m", "30m", "1h", "1d", "1wk"
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            logger.warning(f"Sin datos de yfinance para {symbol}")
            return []

        prices = []
        for timestamp, row in df.iterrows():
            ts = timestamp.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            prices.append(
                OilPrice(
                    timestamp=ts,
                    symbol=symbol,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row.get("Volume", 0)),
                    source="yfinance",
                )
            )

        logger.info(f"yfinance {symbol}: {len(prices)} registros de precio")
        return prices

    except Exception as e:
        logger.error(f"Error obteniendo precios de yfinance ({symbol}): {e}")
        return []


def fetch_oil_prices_alphavantage(
    symbol: str = "CL=F",
    interval: str = "60min",
) -> list[OilPrice]:
    """
    Fallback: obtiene precios desde Alpha Vantage.
    Free tier: 25 requests/día.
    """
    if not ALPHA_VANTAGE_KEY:
        logger.warning("ALPHA_VANTAGE_KEY no configurada")
        return []

    try:
        import requests

        # Alpha Vantage usa sus propios símbolos
        av_symbol_map = {"CL=F": "WTI", "BZ=F": "BRENT"}
        av_symbol = av_symbol_map.get(symbol, symbol)

        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "WTI" if av_symbol == "WTI" else "BRENT",
                "interval": "monthly",
                "apikey": ALPHA_VANTAGE_KEY,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        prices = []
        for entry in data.get("data", []):
            try:
                ts = datetime.strptime(entry["date"], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                value = float(entry["value"])
                prices.append(
                    OilPrice(
                        timestamp=ts,
                        symbol=symbol,
                        open=value,
                        high=value,
                        low=value,
                        close=value,
                        volume=0,
                        source="alphavantage",
                    )
                )
            except (ValueError, KeyError):
                continue

        logger.info(f"Alpha Vantage {symbol}: {len(prices)} registros de precio")
        return prices

    except Exception as e:
        logger.error(f"Error en Alpha Vantage ({symbol}): {e}")
        return []


def fetch_all_oil_prices(period: str = "1mo", interval: str = "1h") -> list[OilPrice]:
    """Obtiene precios de WTI y Brent con fallback."""
    all_prices = []

    for name, symbol in OIL_SYMBOLS.items():
        prices = fetch_oil_prices_yfinance(symbol, period, interval)

        if not prices:
            logger.info(f"Fallback a Alpha Vantage para {name}")
            prices = fetch_oil_prices_alphavantage(symbol)

        all_prices.extend(prices)
        logger.info(f"{name} ({symbol}): {len(prices)} registros totales")

    return all_prices
