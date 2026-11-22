"""BTC/USDT MEXC perpetual — live chart, TD 9/13 scanner, event log."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from market_data import INTERVALS, get_candles, only_closed, next_close_time
from td_sequential import calculate_td, recent_status, new_events
from alerts import store_events, load_history

st.set_page_config(page_title='BTC TD Sequential | MEXC',page_icon='₿',layout='wide')
st.markdown('''<style>.block-container{padding-top:1.6rem;max-width:1500px;}
[data-testid="stMetric"]{background:rgba(128,128,128,.06);padding:.7rem 1rem;border-radius:12px;}</style>''',unsafe_allow_html=True)
st.title('₿ Bitcoin Perpetual · TD Sequential')
st.caption('MEXC BTC/USDT Perpetual · UTC · TD counts on closed candles · No trading execution')

TF_LABELS={k:k for k in INTERVALS}
SCAN_TFS=[k for k in INTERVALS if k not in ('1m','2m','3m','5m')]

@st.cache_data(ttl=3,show_spinner=False)
def chart_candles(tf,n):return get_candles(tf,n)

@st.cache_data(ttl=90,show_spinner=False)
def scan_candles(tf):return get_candles(tf,250)



with st.sidebar:
    st.header('Chart controls')
    interval=st.selectbox('Timeframe',list(INTERVALS),index=3,format_func=lambda x:TF_LABELS[x])
    kind=st.radio('Chart type',['Candlestick','Line'],horizontal=True)
    count=st.slider('Candles displayed',50,250,150,step=25)
    show_setup=st.checkbox('Show TD Setup numbers',True)
    show_cd=st.checkbox('Show TD Countdown numbers',True)
    recycle=st.checkbox('Simplified same-side recycling',True,
                        help='An unfinished countdown restarts when another same-side Setup 9 completes.')
    auto=st.toggle('Auto-refresh chart every 3 seconds',True)
    auto_scan=st.toggle('Scan higher timeframes every 90 seconds',False,
                        help='Additional public API calls; enable when you want continuous scanning while this page is open.')
    enable_log=st.toggle('Record newly detected alerts',True)
    if st.button('Refresh market data now',use_container_width=True):
        chart_candles.clear(); scan_candles.clear(); st.rerun()
    st.caption('Custom intervals are aggregated from MEXC candles in UTC. Scanner fetches extra history; only recent closed-bar events are logged.')

def add_number_layer(fig, d, count_col, anchor_col, name, color, above=False, distance=1.0):
    active=d[d[count_col]>0]
    if active.empty:return
    span=(d['high']-d['low']).median()
    span=max(float(span), max(float(d['close'].median()),1)*0.00025)
    offset=span*distance
    y=active[anchor_col]+(offset if above else -offset)
    fig.add_trace(go.Scatter(x=active['open_time'],y=y,mode='text',
        text=active[count_col].astype(str),textfont={'size':11,'color':color},
        name=name,hovertemplate=f'{name}: '+'%{text}<extra></extra>',showlegend=True))


def build_chart(raw, calculated, type_, tf):
    fig=go.Figure()
    if type_=='Candlestick':
        fig.add_trace(go.Candlestick(x=raw['open_time'],open=raw['open'],high=raw['high'],
          low=raw['low'],close=raw['close'],name='BTC/USDT',
          increasing_line_color='#119c86',decreasing_line_color='#d95a64'))
    else:
        fig.add_trace(go.Scatter(x=raw['open_time'],y=raw['close'],mode='lines',
            line={'color':'#119c86','width':2},name='Close'))
    if show_setup:
        add_number_layer(fig,calculated,'buy_setup','low','Buy Setup','#078a73',False,1)
        add_number_layer(fig,calculated,'sell_setup','high','Sell Setup','#d65c65',True,1)
    if show_cd:
        add_number_layer(fig,calculated,'buy_countdown','low','Buy Countdown','#4776cf',False,2.2)
        add_number_layer(fig,calculated,'sell_countdown','high','Sell Countdown','#a16fd4',True,2.2)
    fig.update_layout(title=f'MEXC Perpetual · {tf} · {type_}',height=610,template='plotly_white',
        xaxis_rangeslider_visible=False,dragmode='pan',hovermode='closest',
        xaxis_title='UTC',yaxis_title='USDT',margin=dict(t=50,b=15,l=10,r=15),
        legend=dict(orientation='h',y=-0.18))
    return fig


def fetch_td(tf,n=250):
    raw=scan_candles(tf) if n==250 else get_candles(tf,n)
    closed=only_closed(raw,tf)
    if len(closed)<20:raise ValueError('Insufficient completed candles')
    d=calculate_td(closed,recycle=recycle)
    return raw,d


@st.fragment(run_every='3s' if auto else None)
def live_panel():
    try:
        raw=chart_candles(interval,max(count,160))
        closed=only_closed(raw,interval)
        calc=calculate_td(closed,recycle=recycle)
        last=raw.iloc[-1]
        prev=raw.iloc[-2] if len(raw)>1 else last
        pct=(last['close']/prev['close']-1)*100 if prev['close'] else 0
        m1,m2,m3=st.columns(3)
        m1.metric('Latest reported close',f"${last['close']:,.2f}",f'{pct:+.2f}% vs previous bar')
        m2.metric('Current high',f"${last['high']:,.2f}")
        m3.metric('Current low',f"${last['low']:,.2f}")
        st.plotly_chart(build_chart(raw.tail(count),calc.tail(count),kind,interval),
                        use_container_width=True,config={'scrollZoom':True,'displaylogo':False})
        st.caption('TD labels use completed candles only; the forming last candle is not assigned a confirmed TD count.')
    except Exception as exc:
        st.error(f'MEXC chart unavailable: {type(exc).__name__}: {exc}')


@st.fragment(run_every='1s')
def clock_panel():
    now=pd.Timestamp.now(tz='UTC')
    # Uses UTC candle grid. Custom candle boundaries may differ from MEXC's own grouping.
    if interval.endswith('M'):
        n=int(interval[:-1]); month_idx=now.year*12+now.month-1
        next_idx=((month_idx//n)+1)*n
        year,idx=divmod(next_idx,12)
        close=pd.Timestamp(year=year,month=idx+1,day=1,tz='UTC')
    elif interval=='1w':
        close=now.normalize()-pd.Timedelta(days=now.weekday())+pd.Timedelta(days=7)
    else:
        seconds=int(pd.Timedelta(interval).total_seconds())
        elapsed=int((now-now.normalize()).total_seconds())
        close=now.normalize()+pd.Timedelta(seconds=((elapsed//seconds)+1)*seconds)
    remain=max(0,int((close-now).total_seconds())+1)
    days,rest=divmod(remain,86400); hours,rest=divmod(rest,3600); mins,secs=divmod(rest,60)
    label=f'{days}d {hours:02d}:{mins:02d}:{secs:02d}' if days else (f'{hours:02d}:{mins:02d}:{secs:02d}' if hours else f'{mins:02d}:{secs:02d}')
    st.metric(f'⏳ {interval} candle closes in (UTC)',label)


def run_scan():
    def worker(tf):
        try:
            _,data=fetch_td(tf)
            return tf,data,None
        except Exception as e:return tf,None,str(e)
    results={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for tf,d,err in pool.map(worker,SCAN_TFS):
            results[tf]=(d,err)
    rows=[]; events=[]
    for tf in SCAN_TFS:
        d,err=results[tf]
        if err:
            rows.append({'Timeframe':tf,'Setup':'—','Countdown':'—','Last close':'—','Status':f'API unavailable: {err[:60]}'})
            continue
        info=recent_status(d)
        rows.append({'Timeframe':tf,'Setup':info['setup'],'Countdown':info['countdown'],
                     'Last close':f"${info['last_close']:,.2f}",'Status':'OK'})
        events.extend(new_events(d,tf,recent_bars=2))
    if enable_log and events:
        try:
            stored=store_events(events)
            if stored:st.toast(f'{stored} new TD alert(s) recorded',icon='🔔')
        except Exception as e:st.warning(f'Alert storage unavailable: {e}')
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.caption('All timeframes above 5m; each is evaluated from its own closed candles. A dash means no recent count. '
               'Scanner results may show partial historical context when MEXC limits candle downloads.')


st.subheader('Main chart')
clock_panel()
live_panel()
st.divider()
st.subheader('Multi-timeframe TD Scanner')
st.caption('The scan runs on request, or every 90 seconds when enabled. This avoids sending ~18 API requests every 3 seconds.')

@st.fragment(run_every='90s' if auto_scan else None)
def scanner_panel():
    if not auto_scan:
        if not st.button('Scan all timeframes now',type='primary'):
            st.info('Click Scan all timeframes now to start.')
            return
    run_scan()
scanner_panel()

st.divider()
st.subheader('Alert history')
st.caption('Setup 9 and Countdown 13 completion events on *closed* candles. Duplicate events are suppressed.')
@st.fragment(run_every='10s')
def history_panel():
    try:
        history=load_history()
        st.dataframe(history,use_container_width=True,hide_index=True)
        if len(history):
            st.download_button('Download alert history CSV',history.to_csv(index=False).encode(),
                               'td_alert_history.csv','text/csv')
        else:st.info('No alerts recorded yet. Run the multi-timeframe scan to check for recent completions.')
    except Exception as exc:st.warning(f'Alert history unavailable: {exc}')
history_panel()
with st.expander('Methodology and limitations'):
    st.markdown('''**Public-rule TD Sequential 9/13 interpretation.** Setup uses price flips and nine consecutive comparisons
    of close versus close four bars before. Countdown compares close to high/low two bars before and is nonconsecutive.
    Countdown 13 is deferred until its bar-13 qualifier passes. Setup perfection is tracked independently.

    This is **not a licensed or fully equivalent DeMARK reference engine**. Full official cancellation/recycling
    qualifiers, TDST rules, and vendor-specific differences are not all implemented. Optional same-side recycling
    follows the simplified policy documented in `td_sequential.py`.

    Only **closed candles** count toward TD. API outages, incomplete lookback, and custom-interval aggregation
    can affect results. Alerts are logged only when scans run, while the dashboard session is active.
    A local SQLite alert database is temporary on Streamlit Community Cloud; set a private `DATABASE_URL`
    to persist history in PostgreSQL. This dashboard does not place trades.''')
