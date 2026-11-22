"""BTC/USDT live price dashboard — charts and interval selection only."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from datetime import datetime, timedelta, timezone
import math

from market_data import INTERVALS, get_candles

st.set_page_config(
    page_title="Bitcoin Live | BTC/USDT",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.8rem; max-width: 1450px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.06); padding: .75rem 1rem; border-radius: .7rem;}
</style>
""", unsafe_allow_html=True)

st.title("₿ Bitcoin Live Dashboard")

st.caption(
    "BTC/USDT · MEXC Perpetual Futures · "
    "Public market data · UTC chart times"
)


@st.cache_data(ttl=3, show_spinner=False)
def get_cached_candles(interval: str, count: int) -> pd.DataFrame:
    return get_candles(interval, count)


with st.sidebar:
    st.header("Chart controls")
    
    INTERVAL_LABELS = {
        "1m": "1 minute",
        "2m": "2 minutes",
        "3m": "3 minutes",
        "5m": "5 minutes",
        "10m": "10 minutes",
        "15m": "15 minutes",
        "30m": "30 minutes",
        "45m": "45 minutes",
        "1h": "1 hour",
        "2h": "2 hours",
        "3h": "3 hours",
        "4h": "4 hours",
        "5h": "5 hours",
        "6h": "6 hours",
        "8h": "8 hours",
        "12h": "12 hours",
        "1d": "1 day",
        "1w": "1 week",
        "1M": "1 month",
        "3M": "3 months",
        "6M": "6 months",
        "12M": "12 months",
    }
    
    interval = st.selectbox(
        "Time interval",
        options=list(INTERVALS.keys()),
        index=3,
        format_func=lambda x: INTERVAL_LABELS[x]
    )

    chart_type = st.radio("Chart type", ["Candlestick", "Line"], horizontal=True)
    count = st.slider("Candles displayed", min_value=50, max_value=200, value=150, step=25)
    auto_refresh = st.toggle("Auto-refresh every 3 seconds", value=True)
    if st.button("Refresh now", use_container_width=True):
        # The live data call is cached for 10 sec; clearing bypasses the cache.
        get_cached_candles.clear()
        st.rerun()
    st.caption(
    "Custom intervals are calculated from shorter "
    "Binance candles. All times use UTC.")
    st.caption("No API keys, trading accounts, or database required.")




def build_chart(df: pd.DataFrame, kind: str, interval: str) -> go.Figure:
    fig = go.Figure()
    if kind == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df["open_time"],
            open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="BTC/USDT",
            increasing_line_color="#14a38b",
            decreasing_line_color="#e05f66",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=df["open_time"], y=df["close"],
            mode="lines", name="BTC/USDT Close",
            line={"color": "#14a38b", "width": 2.5},
            hovertemplate="%{x|%Y-%m-%d %H:%M} UTC<br>$%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        title=f"BTC/USDT · {interval} · {kind}",
        height=590,
        margin=dict(l=10, r=10, t=55, b=15),
        hovermode="x unified" if kind == "Line" else "closest",
        xaxis_title="Time (UTC)",
        yaxis_title="Price (USDT)",
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        template="plotly_white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(140,140,140,.12)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(140,140,140,.12)", tickprefix="$")
    return fig

def get_candle_close_time(interval):
    now = datetime.now(timezone.utc)

    # Calendar-based timeframes
    if interval in ["1M", "3M", "6M", "12M"]:
        months = int(interval.replace("M", ""))
        current_month_index = now.year * 12 + now.month - 1

        next_index = (
            current_month_index // months + 1
        ) * months

        year, month_index = divmod(next_index, 12)

        return datetime(
            year, month_index + 1, 1,
            tzinfo=timezone.utc
        )

    # Weekly candles: Monday 00:00 UTC
    if interval == "1w":
        start_of_week = (
            now.replace(
                hour=0, minute=0,
                second=0, microsecond=0
            )
            - timedelta(days=now.weekday())
        )
        return start_of_week + timedelta(days=7)

    # Fixed-length timeframes
    seconds_map = {
        "1m": 60,
        "2m": 120,
        "3m": 180,
        "5m": 300,
        "10m": 600,
        "15m": 900,
        "30m": 1800,
        "45m": 2700,
        "1h": 3600,
        "2h": 7200,
        "3h": 10800,
        "4h": 14400,
        "5h": 18000,
        "6h": 21600,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
    }

    duration = seconds_map[interval]

    midnight = now.replace(
        hour=0, minute=0,
        second=0, microsecond=0
    )

    elapsed = (now - midnight).total_seconds()
    next_bucket = (
        math.floor(elapsed / duration) + 1
    ) * duration

    return midnight + timedelta(seconds=next_bucket)


@st.fragment(run_every="1s")
def candle_countdown():
    now = datetime.now(timezone.utc)
    close_time = get_candle_close_time(interval)

    remaining = max(
        0,
        math.ceil((close_time - now).total_seconds())
    )

    days, remainder = divmod(remaining, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days:
        countdown = f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    elif hours:
        countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        countdown = f"{minutes:02d}:{seconds:02d}"

    st.metric(
        label=f"⏳ Candle closes in ({interval})",
        value=countdown
    )


@st.fragment(run_every="3s" if auto_refresh else None)
def live_chart() -> None:
    try:
        df = get_cached_candles(interval, count)
    except Exception as exc:
        
        st.error("Could not load BTC/USDT Perpetual candles from MEXC. "
            "The API may be temporarily unavailable, "
            "rate-limited, or restricted from this network.")
        st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
        st.info("Try clicking Refresh now. No API key is required.")
        return

    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else latest
    change = ((latest["close"] / previous["close"] - 1) * 100) if previous["close"] else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Latest candle close", f"${latest['close']:,.2f}", f"{change:+.2f}% vs prior candle")
    c2.metric("Current candle high", f"${latest['high']:,.2f}")
    c3.metric("Current candle low", f"${latest['low']:,.2f}")

    st.plotly_chart(build_chart(df, chart_type, interval), use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": True})
    st.caption(
        "Last available candle starts: "
        f"{latest['open_time'].strftime('%Y-%m-%d %H:%M:%S UTC')} · "
        "The most recent candle may still be forming. "
        "Data refreshes while this page is open and connected."
    )



candle_countdown()
live_chart()



with st.expander("About this dashboard"):
    st.write(
        "This dashboard displays BTC/USDT Perpetual Futures "
        "market data from MEXC. It supports candlestick and "
        "line charts, multiple timeframes, and automatic "
        "updates every 3 seconds while the session is active. "
        "Custom intervals are aggregated from shorter candles. "
        "The dashboard does not execute trades."
    )


