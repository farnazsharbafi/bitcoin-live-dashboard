import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from td_sequential import calculate_td, new_events

def sample(closes):
    return pd.DataFrame({'open_time':pd.date_range('2026-01-01',periods=len(closes),freq='min',tz='UTC'),
       'open':closes,'high':[x+1 for x in closes],
       'low':[x-1 for x in closes],'close':closes,'volume':[1.0]*len(closes)})

def test_buy_setup_9_and_event():
    closes=[100,110,120,130,140]+list(range(90,81,-1))
    d=calculate_td(sample(closes))
    assert d['buy_setup_9'].sum()==1
    assert d.iloc[-1]['buy_setup']==9
    assert d.iloc[-1]['sell_setup']==0
    assert len(new_events(d,'1m',recent_bars=2))==1

def test_uses_completed_input_only():
    d=calculate_td(sample([100,101,102,103,104,98,97,96]))
    assert not d['buy_cd_13'].any()

def test_empty_short():
    d=calculate_td(sample([100,99,98]))
    assert len(d)==3
