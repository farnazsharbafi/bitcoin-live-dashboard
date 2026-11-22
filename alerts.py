"""Optional persistent alert history (PostgreSQL); SQLite for local-only demos.

Streamlit Community Cloud local SQLite data may disappear on restart.
Setting DATABASE_URL to a private Supabase pooler URI enables durable storage.
"""
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

DDL = '''CREATE TABLE IF NOT EXISTS td_alerts (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    event_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    candle_time TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, interval, event_type, direction, candle_time)
)'''
SQLITE_DDL = DDL.replace('BIGSERIAL PRIMARY KEY','INTEGER PRIMARY KEY AUTOINCREMENT').replace('TIMESTAMPTZ','TEXT')


def get_engine():
    uri=os.environ.get('DATABASE_URL','').strip()
    if not uri:
        try:
            import streamlit as st
            uri = str(st.secrets.get('DATABASE_URL', '')).strip()
        except (FileNotFoundError, KeyError):
            pass
    if uri:
        # SQLAlchemy defaults postgresql:// to psycopg2; our requirements install psycopg3.
        if uri.startswith('postgresql://'):
            uri = 'postgresql+psycopg://' + uri[len('postgresql://'):]
        elif uri.startswith('postgres://'):
            uri = 'postgresql+psycopg://' + uri[len('postgres://'):]
        return create_engine(uri,connect_args={'sslmode':'require'},pool_pre_ping=True)
    return create_engine('sqlite:///' + str(Path(__file__).with_name('td_alerts_local.sqlite3')))


def store_events(events: list[dict]) -> int:
    if not events:return 0
    engine=get_engine()
    dialect=engine.dialect.name
    with engine.begin() as con:
        con.execute(text(DDL if dialect=='postgresql' else SQLITE_DDL))
        n=0
        for e in events:
            if dialect=='postgresql':
                query='''INSERT INTO td_alerts (symbol,interval,event_type,direction,candle_time,price)
                  VALUES (:symbol,:interval,:event_type,:direction,:candle_time,:price)
                  ON CONFLICT (symbol,interval,event_type,direction,candle_time) DO NOTHING'''
            else:
                query='''INSERT OR IGNORE INTO td_alerts
                  (symbol,interval,event_type,direction,candle_time,price)
                  VALUES (:symbol,:interval,:event_type,:direction,:candle_time,:price)'''
            n+=con.execute(text(query),e).rowcount
    engine.dispose()
    return n


def load_history(limit: int=300) -> pd.DataFrame:
    engine=get_engine()
    try:
        with engine.begin() as con:
            con.execute(text(DDL if engine.dialect.name=='postgresql' else SQLITE_DDL))
            return pd.read_sql(text('''SELECT symbol,interval,event_type,direction,candle_time,
                price,detected_at FROM td_alerts ORDER BY detected_at DESC, id DESC LIMIT :lim'''),
                con,params={'lim':limit})
    finally:engine.dispose()
