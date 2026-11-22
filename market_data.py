
"""MEXC BTC_USDT perpetual futures OHLCV data."""

from __future__ import annotations

import pandas as pd
import requests

BASE_URL = "https://api.mexc.com/api/v1/contract/kline/BTC_USDT"
SYMBOL = "BTC_USDT"

# Selected interval: (MEXC interval, custom aggregation)
INTERVALS = {
    "1m": ("Min1", None),
    "2m": ("Min1", "2min"),
    "3m": ("Min1", "3min"),
    "5m": ("Min5", None),
    "10m": ("Min5", "10min"),
    "15m": ("Min15", None),
    "30m": ("Min30", None),
    "45m": ("Min15", "45min"),

    "1h": ("Min60", None),
    "2h": ("Min60", "2h"),
    "3h": ("Min60", "3h"),
    "4h": ("Hour4", None),
    "5h": ("Min60", "5h"),
    "6h": ("Min60", "6h"),
    "8h": ("Hour8", None),
    "12h": ("Hour4", "12h"),

    "1d": ("Day1", None),
    "1w": ("Week1", None),

    "1M": ("Month1", None),
    "3M": ("Month1", "3mo"),
    "6M": ("Month1", "6mo"),
    "12M": ("Month1", "12mo"),
}

BASE_SECONDS = {
    "Min1": 60,
    "Min5": 300,
    "Min15": 900,
    "Min30": 1800,
    "Min60": 3600,
    "Hour4": 14400,
    "Hour8": 28800,
    "Day1": 86400,
    "Week1": 604800,
    "Month1": 30 * 86400,
}

MULTIPLIER = {
    "2m": 2,
    "3m": 3,
    "10m": 2,
    "45m": 3,
    "2h": 2,
    "3h": 3,
    "5h": 5,
    "6h": 6,
    "12h": 3,
    "3M": 3,
    "6M": 6,
    "12M": 12,
}


def parse_klines(payload) -> pd.DataFrame:
    """Convert MEXC parallel arrays to OHLCV records."""

    if not isinstance(payload, dict):
        raise ValueError("Unexpected MEXC response format.")

    if not payload.get("success"):
        raise RuntimeError(
            f"MEXC API error: {payload.get('code')} "
            f"{payload.get('message', '')}"
        )

    data = payload.get("data")

    required = [
        "time", "open", "high", "low",
        "close", "vol"
    ]

    if not isinstance(data, dict):
        raise ValueError("MEXC returned no candle data.")

    if any(key not in data for key in required):
        raise ValueError("Missing MEXC candle fields.")

    lengths = [len(data[key]) for key in required]

    if not lengths or min(lengths) == 0:
        raise ValueError("MEXC returned empty candles.")

    if len(set(lengths)) != 1:
        raise ValueError("Inconsistent MEXC candle lengths.")

    df = pd.DataFrame({
        "open_time": pd.to_datetime(
            data["time"], unit="s", utc=True
        ),
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "close": data["close"],
        "volume": data["vol"],
    })

    for col in [
        "open", "high", "low", "close", "volume"
    ]:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    df = df.dropna(
        subset=[
            "open_time", "open", "high",
            "low", "close", "volume"
        ]
    )

    df = df.drop_duplicates(
        subset=["open_time"], keep="last"
    )

    return df.sort_values(
        "open_time"
    ).reset_index(drop=True)


def aggregate_candles(
    df: pd.DataFrame,
    rule: str
) -> pd.DataFrame:
    """Aggregate source candles into custom UTC buckets."""

    if df.empty:
        return df.copy()

    aggregation = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    if rule in ("3mo", "6mo", "12mo"):
        months = int(rule.replace("mo", ""))
        data = df.copy()

        timestamps = data["open_time"]

        bucket_month = (
            ((timestamps.dt.month - 1) // months)
            * months + 1
        )

        data["open_time"] = pd.to_datetime(
            {
                "year": timestamps.dt.year,
                "month": bucket_month,
                "day": 1,
            },
            utc=True,
        )

        result = (
            data.groupby("open_time", as_index=False)
            .agg(aggregation)
        )

    else:
        result = (
            df.set_index("open_time")
            .sort_index()
            .resample(
                rule,
                origin="start_day",
                label="left",
                closed="left",
            )
            .agg(aggregation)
            .dropna(
                subset=[
                    "open", "high", "low", "close"
                ]
            )
            .reset_index()
        )

    return result


def get_candles(
    interval: str,
    count: int = 200
) -> pd.DataFrame:
    """Retrieve recent MEXC perpetual candles."""

    if interval not in INTERVALS:
        raise ValueError(
            f"Unsupported interval: {interval}"
        )

    if not 25 <= count <= 400:
        raise ValueError(
            "count must be between 25 and 400"
        )

    exchange_interval, rule = INTERVALS[interval]
    multiplier = MULTIPLIER.get(interval, 1)

    # MEXC returns at most 2000 points per request.
    source_count = min(
        2000,
        count * multiplier + 20
    )

    now = pd.Timestamp.now(tz="UTC")
    end_time = int(now.timestamp())

    # Include extra time for partially formed buckets.
    duration = BASE_SECONDS[exchange_interval]

    start_time = end_time - (
        (source_count + 5) * duration
    )

    response = requests.get(
        BASE_URL,
        params={
            "interval": exchange_interval,
            "start": start_time,
            "end": end_time,
        },
        timeout=15,
        headers={
            "Accept": "application/json",
            "User-Agent": "btc-dashboard-portfolio/1.0",
        },
    )

    response.raise_for_status()

    df = parse_klines(response.json())

    if rule:
        df = aggregate_candles(df, rule)

    if df.empty:
        raise ValueError(
            "No usable MEXC candles were returned."
        )

    return df.tail(count).reset_index(drop=True)
