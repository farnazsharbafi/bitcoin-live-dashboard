import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from alerts import SQLITE_DDL

def test_sqlite_unique():
    e=create_engine('sqlite://')
    with e.begin() as c:
        c.execute(text(SQLITE_DDL))
        params=dict(symbol='BTC_USDT',interval='1m',event_type='Setup 9',direction='Buy',candle_time='2026-01-01T00:00Z',price=100.)
        sql=text('INSERT OR IGNORE INTO td_alerts (symbol,interval,event_type,direction,candle_time,price) VALUES (:symbol,:interval,:event_type,:direction,:candle_time,:price)')
        c.execute(sql,params); c.execute(sql,params)
        assert c.execute(text('select count(*) from td_alerts')).scalar()==1
