import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from market_data import INTERVALS,parse_klines,aggregate_candles,only_closed,next_close_time

def test_parse():
    p={'success':True,'data':{'time':[1704067200,1704067260], 'open':['10','11'],
        'high':['12','13'],'low':['9','10'],'close':['11','12'],'vol':['2','3']}}
    d=parse_klines(p)
    assert len(d)==2 and d.iloc[-1]['close']==12
    assert str(d['open_time'].dt.tz)=='UTC'

def test_2m():
    d=pd.DataFrame({'open_time':pd.date_range('2026-01-01',periods=4,freq='min',tz='UTC'),
        'open':[1,2,3,4],'high':[3,4,5,6],'low':[0,1,2,3],
        'close':[2,3,4,5],'volume':[1,2,3,4]})
    a=aggregate_candles(d,'2min')
    assert len(a)==2 and a.iloc[0]['volume']==3
    assert len(only_closed(a,'2m',pd.Timestamp('2026-01-01T00:02:10Z')))==1

def test_month_close():
    assert str(next_close_time('2026-01-01T00:00Z','3M'))[:10]=='2026-04-01'
    assert INTERVALS['45m'][0]=='Min15'
