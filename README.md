# Bitcoin Live Price Dashboard

A public, interactive **BTC/USDT** dashboard built with Streamlit and Plotly. Shows candlestick/line charts, selectable intervals from one minute to one day, and automatic 15-second refreshing while the page is open.

## Features

- BTC/USDT spot-market OHLCV candles from Binance public market-data REST endpoint, **without an API key**.
- Candlestick or line display; zoom, pan, and hover.
- Intervals: **1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 3h, 4h, 5h, 6h, 8h, 12h, 1d**.
- Custom **2m, 10m, 3h, 5h** OHLCV candles are resampled from shorter native candles.
- Automatically refreshes every 15 seconds while an active browser session is connected; no continuous background data collection.

## Get started

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit.

## Deployment

1. Push `app.py`, `market_data.py`, `requirements.txt` and this README to a GitHub repository.
2. Open https://share.streamlit.io/ and select **Create app → Deploy from GitHub**.
3. Set the entrypoint to `app.py` and deploy.

## Data, limitations, and design

- Market: **BTCUSDT on Binance Spot**. Price is denominated in USDT, not exactly USD.
- Public endpoint: `https://data-api.binance.vision/api/v3/klines`.
- No API key, user accounts, order placement, database, or trading features.
- This is **periodic REST polling, not streaming tick-by-tick data**. The current candle is not necessarily closed.
- Custom candles are UTC-day-aligned. Because the public endpoint returns a limited recent window, custom intervals and count settings can display fewer bars than requested.
- Network or regional restrictions and API availability can affect data retrieval.
- This is an educational analytics dashboard and not investment advice.
