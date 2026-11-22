"""Auditable public-rule TD Sequential 9/13 engine.

Implements price-flip-gated consecutive setups, setup perfection,
nonconsecutive countdown with 13th-bar qualifier, opposite-setup cancellation,
and a *configurable simplified* same-direction recycle policy.
Not a licensed DeMARK reference implementation; proprietary variants may differ.
All input bars MUST be closed.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_td(df: pd.DataFrame, recycle: bool=True) -> pd.DataFrame:
    d = df.copy().sort_values('open_time').reset_index(drop=True)
    for name in ['buy_setup','sell_setup','buy_countdown','sell_countdown']:
        d[name] = 0
    for name in ['buy_setup_9','sell_setup_9','buy_cd_13','sell_cd_13',
                 'buy_perfected','sell_perfected']:
        d[name] = False
    if len(d)<6: return d
    close=d['close'].to_numpy(dtype=float)
    high=d['high'].to_numpy(dtype=float)
    low=d['low'].to_numpy(dtype=float)
    # one active countdown on each side; starts only after setup 9.
    active={'buy':None,'sell':None}
    run_dir=None; run_count=0
    perfection={'buy':None,'sell':None}
    for i in range(5,len(d)):
        # Pending setup perfection can occur after bar 9.
        for side in ('buy','sell'):
            pending=perfection[side]
            if pending is not None:
                extreme=low[i] if side=='buy' else high[i]
                good=extreme <= pending['compare'] if side=='buy' else extreme >= pending['compare']
                if good:
                    d.at[i,f'{side}_perfected']=True
                    perfection[side]=None
        side = ('buy' if close[i]<close[i-4] else
                'sell' if close[i]>close[i-4] else None)
        # Price flip: first qualifying bar must reverse the preceding C vs C[-4] direction.
        flip=(side=='buy' and close[i-1]>=close[i-5]) or (side=='sell' and close[i-1]<=close[i-5])
        if side is None:
            run_dir=None; run_count=0
        elif side==run_dir:
            run_count+=1
        elif flip:
            run_dir=side; run_count=1
        else:
            run_dir=None; run_count=0
        if run_dir and run_count<=9:
            d.at[i,f'{run_dir}_setup']=run_count
        new_setup = run_dir if run_count==9 else None
        if new_setup:
            d.at[i,f'{new_setup}_setup_9']=True
            # Setup perfection checks bars 8/9 vs bars 6/7 (zero-based -1,-2 vs -3,-4).
            compare=(min(low[i-3],low[i-2]) if new_setup=='buy'
                     else max(high[i-3],high[i-2]))
            good=(min(low[i-1],low[i])<=compare if new_setup=='buy'
                  else max(high[i-1],high[i])>=compare)
            if good: d.at[i,f'{new_setup}_perfected']=True
            else: perfection[new_setup]={'compare':compare}
            # opposite completed setup cancels active countdown
            opposite='sell' if new_setup=='buy' else 'buy'
            active[opposite]=None
            perfection[opposite]=None
            if active[new_setup] is None or recycle:
                # simplified recycle: replace previous unfinished same-side countdown
                active[new_setup]={'count':0,'close8':None}
        # Setup bar 9 can itself count toward TD Countdown.
        for direction in ('buy','sell'):
            cd=active[direction]
            if cd is None: continue
            qualifies=(close[i]<=low[i-2] if direction=='buy'
                       else close[i]>=high[i-2])
            if not qualifies: continue
            next_count=cd['count']+1
            if next_count==13:
                # Official bar-13 deferral: compare bar13 extreme with close of countdown bar8.
                qualified=(low[i]<=cd['close8'] if direction=='buy'
                           else high[i]>=cd['close8'])
                if not qualified: continue  # remain at 12 until qualified
                d.at[i,f'{direction}_countdown']=13
                d.at[i,f'{direction}_cd_13']=True
                active[direction]=None
            else:
                cd['count']=next_count
                if next_count==8: cd['close8']=close[i]
                d.at[i,f'{direction}_countdown']=next_count
        # A completed 9 is the final bar of this particular setup.
        if run_count==9:
            run_count=0; run_dir=None
    return d


def recent_status(d: pd.DataFrame) -> dict:
    if d.empty: return {'setup':'—','countdown':'—','last_close':None}
    row=d.iloc[-1]
    setup='—'; countdown='—'
    # most recent nonzero setup/countdown in the last 30 bars
    for prefix,key in (('setup','setup'),('countdown','countdown')):
        series=[]
        for direction in ('buy','sell'):
            col=f'{direction}_{prefix}'
            hits=d[d[col]>0]
            if not hits.empty:
                hit=hits.iloc[-1]
                series.append((hit['open_time'],f"{direction.title()} {int(hit[col])}/{9 if prefix=='setup' else 13}"))
        if series:
            val=max(series,key=lambda x:x[0])
            if val[0]>=d.iloc[-min(30,len(d))]['open_time']:
                if prefix=='setup':setup=val[1]
                else:countdown=val[1]
    return {'setup':setup,'countdown':countdown,'last_close':float(row['close'])}


def new_events(d: pd.DataFrame, interval: str, recent_bars: int=2) -> list[dict]:
    """Only newly completed events, not provisional current-candle events."""
    if d.empty:return []
    events=[]
    for _,row in d.tail(recent_bars).iterrows():
        for side in ('buy','sell'):
            for key,event in ((f'{side}_setup_9','Setup 9'),(f'{side}_cd_13','Countdown 13')):
                if bool(row[key]):
                    events.append({'symbol':'BTC_USDT','interval':interval,
                        'event_type':event,'direction':side.title(),
                        'candle_time':row['open_time'].isoformat(),
                        'price':float(row['close'])})
    return events
