"""Unauthenticated Binance public spot candles and custom OHLCV aggregation."""
from __future__ import annotations

import pandas as pd
import requests

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "BTCUSDT"

# label: (binance interval to download, custom resampling rule or None)
INTERVALS: dict[str, tuple[str, str | None]] = {
    "1m": ("1m", None),
    "2m": ("1m", "2min"),
    "3m": ("3m", None),
    "5m": ("5m", None),
    "10m": ("5m", "10min"),
    "15m": ("15m", None),
    "30m": ("30m", None),
    "1h": ("1h", None),
    "2h": ("2h", None),
    "3h": ("1h", "3h"),
    "4h": ("4h", None),
    "5h": ("1h", "5h"),
    "6h": ("6h", None),
    "8h": ("8h", None),
    "12h": ("12h", None),
    "1d": ("1d", None),
}


def parse_klines(payload: list[list]) -> pd.DataFrame:
    """Convert Binance's standard 12-field kline arrays into OHLCV rows."""
    if not isinstance(payload, list) or not payload:
        raise ValueError("The market-data API returned no candlesticks.")
    if any(not isinstance(row, list) or len(row) < 6 for row in payload):
        raise ValueError("Unexpected candlestick data format from the API.")

    df = pd.DataFrame(payload)
    df = df.rename(columns={
        0: "open_time", 1: "open", 2: "high", 3: "low",
        4: "close", 5: "volume",
    })[["open_time", "open", "high", "low", "close", "volume"]]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open_time", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset=["open_time"], keep="last")
    return df.sort_values("open_time").reset_index(drop=True)


def aggregate_candles(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample candles on UTC-day-aligned boundaries, preserving OHLCV semantics."""
    if df.empty:
        return df.copy()
    indexed = df.set_index("open_time").sort_index()
    agg = indexed.resample(rule, origin="start_day", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    })
    agg = agg.dropna(subset=["open", "high", "low", "close"])
    return agg.reset_index()


def get_candles(interval: str, count: int = 200) -> pd.DataFrame:
    """Load recent spot candles; network failures surface as actionable exceptions."""
    if interval not in INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}")
    if not 25 <= count <= 400:
        raise ValueError("count must be between 25 and 400")

    exchange_interval, resample_rule = INTERVALS[interval]
    multiplier = {
        "2m": 2, "10m": 2, "3h": 3, "5h": 5,
    }.get(interval, 1)

    # Binance allows up to 1000 in one request. We show up to 200 for 5h,
    # and 200-400 for most other intervals, with a few extra source candles.
    limit = min(1000, count * multiplier + 15)
    response = requests.get(
        BASE_URL,
        params={"symbol": SYMBOL, "interval": exchange_interval, "limit": limit},
        timeout=15,
        headers={"Accept": "application/json", "User-Agent": "btc-dashboard-portfolio/1.0"},
    )
    response.raise_for_status()
    df = parse_klines(response.json())
    if resample_rule:
        df = aggregate_candles(df, resample_rule)
    if df.empty:
        raise ValueError("No usable candlestick data was returned.")
    return df.tail(count).reset_index(drop=True)
