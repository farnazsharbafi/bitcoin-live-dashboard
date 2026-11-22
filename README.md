# BTC/USDT Perpetual · TD Sequential Multi-Timeframe Dashboard

A public **MEXC BTC/USDT Perpetual** market-data dashboard built with Streamlit, Plotly and pandas.

## Features

- Candlestick and line charts across 1m–12M intervals, including custom aggregated timeframes.
- Price chart refresh every ~3 seconds, candle countdown every ~1 second (while an active browser session is connected).
- Independent Setup and Countdown labels on closed candles, with separate colors and vertical offsets.
- Multi-timeframe panel examining **every configured interval above 5 minutes**; optional refresh every 90 seconds.
- Recent Setup 9 / Countdown 13 alerts with de-duplication and downloadable history.
- Local SQLite demonstration; optional PostgreSQL persistence with `DATABASE_URL` in private deployment secrets.

## Important TD methodology disclosure

`td_sequential.py` is an **auditable implementation of published TD Sequential 9/13 rules**, **not** an official/licensed or feature-complete DeMARK implementation. Implements price-flip-gated 9-bar setups, a simple setup perfection flag, nonconsecutive countdown, 13-vs-8 countdown deferral and opposite-setup cancellation. Optional simplified same-direction recycling restarts an active countdown on another Setup 9. It **does not** implement the full official TDST cancellation and all qualified recycling methods. Read code comments before comparing it to commercial indicators.

Labels and alerts reflect **closed** candles only. Some custom aggregation intervals have partial left-edge buckets or limited history (MEXC maximum 2000 native candles per call). Alerts are generated during a scan, not while the browser is closed. This app does not execute trades or claim predictive accuracy.

## Files

- `market_data.py` — MEXC candles and custom intervals.
- `td_sequential.py` — TD calculations and event detection.
- `alerts.py` — deduplicated SQLite/PostgreSQL alert log.
- `app.py` — chart, 1s timer, scanner, alert history.
- `tests/` — unit tests without external API access.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Run tests

```bash
python -m pip install pytest
python -m pytest -q
```

## Deploy on Streamlit Community Cloud

1. Upload these files to the root of your existing Bitcoin project repository. Do not remove your published URL/repository.
2. App entrypoint: `app.py`.
3. To make alert history durable, create a private PostgreSQL database and add a root-level `DATABASE_URL` secret in Streamlit Cloud Settings → Secrets (SQLAlchemy-compatible connection URI, URL-encode special password characters). Never commit this value.
4. Without a database URL, alerts are saved locally to `td_alerts_local.sqlite3`, which may be lost whenever Streamlit restarts.
5. With Streamlit Community Cloud, checks do **not** continue after the app goes to sleep. True 24/7 alerts require an independent worker or scheduled job.

## API

MEXC public futures klines: `https://api.mexc.com/api/v1/contract/kline/BTC_USDT`. No credential needed for public candle reads. Exchange limits / regional availability can change. Data collection is best effort and may fail with HTTP errors. Scanner makes many requests; it is optional and cached.

## Disclaimer

For technical experimentation and portfolio demonstration, not trading advice. Historic counts and alerts are not validated trade signals.

## Updating from the supplied November 2026 repository snapshot

This package is built from the uploaded `bitcoin-live-dashboard-main.zip`. It replaces the dashboard and preserves all 22 existing selectable intervals, both chart types, 3-second refresh, and the 1-second candle countdown. The new files are `td_sequential.py` and `alerts.py`. The existing original GitHub repo remains your deployment target.

The unit tests cover local logic only; a successful live MEXC HTTP response and Streamlit Cloud runtime cannot be guaranteed by offline tests.
