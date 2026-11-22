"""Public MEXC BTC_USDT perpetual OHLCV, normalized to UTC.

MEXC supports a restricted set of native kline intervals. Custom intervals
are aggregated from available native candles. 2000-source-candle API cap.
"""
from __future__ import annotations
import os
import pandas as pd
import requests

SYMBOL = 'BTC_USDT'
BASE_URL = os.getenv('MEXC_KLINE_URL', 'https://api.mexc.com/api/v1/contract/kline/BTC_USDT')
INTERVALS = {
    '1m': ('Min1', None, 1), '2m': ('Min1', '2min', 2), '3m': ('Min1', '3min', 3),
    '5m': ('Min5', None, 1), '10m': ('Min5', '10min', 2),
    '15m': ('Min15', None, 1), '30m': ('Min30', None, 1), '45m': ('Min15', '45min', 3),
    '1h': ('Min60', None, 1), '2h': ('Min60', '2h', 2), '3h': ('Min60', '3h', 3),
    '4h': ('Hour4', None, 1), '5h': ('Min60', '5h', 5), '6h': ('Min60', '6h', 6),
    '8h': ('Hour8', None, 1), '12h': ('Hour4', '12h', 3),
    '1d': ('Day1', None, 1), '1w': ('Week1', None, 1),
    '1M': ('Month1', None, 1), '3M': ('Month1', '3mo', 3),
    '6M': ('Month1', '6mo', 6), '12M': ('Month1', '12mo', 12),
}
BASE_SECONDS = {'Min1':60,'Min5':300,'Min15':900,'Min30':1800,'Min60':3600,
                'Hour4':14400,'Hour8':28800,'Day1':86400,'Week1':604800,'Month1':2678400}
COLS = ['open_time','open','high','low','close','volume']


def parse_klines(payload: dict) -> pd.DataFrame:
    if not isinstance(payload, dict) or not payload.get('success'):
        raise ValueError(f'MEXC API error: {str(payload)[:240]}')
    data = payload.get('data')
    fields = ['time','open','high','low','close','vol']
    if not isinstance(data, dict) or any(k not in data for k in fields):
        raise ValueError('Invalid MEXC OHLCV response.')
    if not data['time'] or len({len(data[k]) for k in fields}) != 1:
        raise ValueError('MEXC OHLCV arrays empty or inconsistent.')
    df = pd.DataFrame({
        'open_time':pd.to_datetime(data['time'],unit='s',utc=True),
        **{out:data[k] for out,k in zip(['open','high','low','close','volume'], fields[1:])},
    })
    for c in COLS[1:]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return (df.dropna(subset=COLS).drop_duplicates('open_time',keep='last')
              .sort_values('open_time').reset_index(drop=True))


def aggregate_candles(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty: return df.copy()
    agg = {'open':'first','high':'max','low':'min','close':'last','volume':'sum'}
    d = df.copy()
    if rule in ('3mo','6mo','12mo'):
        n = int(rule[:-2]); ts = d['open_time'].dt
        d['open_time'] = pd.to_datetime({
            'year':ts.year, 'month':((ts.month-1)//n)*n+1, 'day':1}, utc=True)
        return d.groupby('open_time',as_index=False).agg(agg)
    return (d.set_index('open_time').resample(
        rule, origin='start_day', label='left', closed='left')
        .agg(agg).dropna(subset=['open','high','low','close']).reset_index())


def next_close_time(open_time, interval: str):
    t = pd.Timestamp(open_time)
    if t.tzinfo is None: t = t.tz_localize('UTC')
    else: t = t.tz_convert('UTC')
    if interval.endswith('M'):
        months=int(interval[:-1]); return t + pd.DateOffset(months=months)
    if interval.endswith('w'):
        return t + pd.Timedelta(weeks=int(interval[:-1]))
    return t + pd.Timedelta(interval)


def only_closed(df: pd.DataFrame, interval: str, now=None) -> pd.DataFrame:
    now = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if now.tzinfo is None: now=now.tz_localize('UTC')
    completed = [next_close_time(t, interval) <= now for t in df['open_time']]
    return df.loc[completed].reset_index(drop=True)


def get_candles(interval: str, count: int=200) -> pd.DataFrame:
    if interval not in INTERVALS: raise ValueError(f'Unsupported interval {interval}')
    if not 20 <= count <= 500: raise ValueError('count must be 20..500')
    native, rule, factor=INTERVALS[interval]
    requested = min(2000, count * factor + factor * 3 + 12)
    end = int(pd.Timestamp.now(tz='UTC').timestamp())
    # Margin for missing candles and calendar-length months.
    seconds = BASE_SECONDS[native]
    start = end - (requested+3)*seconds
    r=requests.get(BASE_URL,params={'interval':native,'start':start,'end':end},
                   headers={'Accept':'application/json','User-Agent':'btc-td-portfolio/1.0'},timeout=18)
    r.raise_for_status()
    df=parse_klines(r.json())
    if rule: df=aggregate_candles(df,rule)
    if df.empty: raise ValueError('No candles returned by MEXC')
    return df.tail(count).reset_index(drop=True)
