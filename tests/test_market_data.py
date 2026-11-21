import pandas as pd
import pytest
from market_data import INTERVALS, aggregate_candles, parse_klines, get_candles


def test_parse_klines():
    raw = [
        [1704067200000, "100", "105", "90", "101", "5", 0, "0", 0, "0", "0", "0"],
        [1704067260000, "101", "109", "95", "107", "8", 0, "0", 0, "0", "0", "0"],
    ]
    df = parse_klines(raw)
    assert len(df) == 2
    assert str(df["open_time"].dt.tz) == "UTC"
    assert df.iloc[-1]["close"] == 107


def test_aggregate_2min_ohlcv():
    times = pd.date_range("2024-01-01T00:00:00Z", periods=4, freq="min")
    df = pd.DataFrame({
        "open_time": times, "open": [100, 102, 101, 104],
        "high": [105, 109, 106, 110], "low": [99, 100, 98, 102],
        "close": [102, 101, 104, 105], "volume": [2, 3, 4, 5],
    })
    out = aggregate_candles(df, "2min")
    assert len(out) == 2
    assert list(out.iloc[0][["open", "high", "low", "close", "volume"]]) == [100, 109, 99, 101, 5]
    assert list(out.iloc[1][["open", "high", "low", "close", "volume"]]) == [101, 110, 98, 105, 9]


def test_custom_intervals():
    assert INTERVALS["2m"] == ("1m", "2min")
    assert INTERVALS["3h"] == ("1h", "3h")
    assert INTERVALS["5h"] == ("1h", "5h")


def test_invalid_interval():
    with pytest.raises(ValueError):
        get_candles("7m")
