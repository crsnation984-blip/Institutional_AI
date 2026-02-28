"""
Institutional Swing AI – Balanced Mode
Features:
- High-probability trade signals
- Multi-timeframe trend + order block + liquidity
- 50/200 SMA + volume + ATR
- Performance tracker (win rate + total R)
- Auto-refresh every hour
- Currency strength heatmap
- Uses NewsAPI for bias
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime
import time

# ===============================
# SETTINGS
# ===============================
PAIRS = [
    "EURUSD=X","GBPUSD=X","USDJPY=X","USDCHF=X",
    "AUDUSD=X","NZDUSD=X","USDCAD=X","GC=F"
]

NEWS_API_KEY = "628bc068ae804152a07be8cb93f86204"  # Your NewsAPI key
AUTO_REFRESH_INTERVAL = 3600  # seconds
TRADE_LOG = "trade_history.csv"

# ===============================
# FUNCTIONS
# ===============================

def get_usd_news_bias():
    url = (
        "https://newsapi.org/v2/everything?"
        "q=USD OR Federal Reserve OR CPI OR NFP OR GDP OR Interest Rates"
        f"&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10).json()
        articles = r.get("articles", [])[:15]
        hawkish = dovish = 0
        for a in articles:
            t = a["title"].lower()
            if any(w in t for w in ["rate hike","inflation rising","strong jobs","hawkish"]):
                hawkish += 1
            if any(w in t for w in ["rate cut","inflation falling","weak jobs","dovish"]):
                dovish += 1
        if hawkish > dovish: return {"bias":"bullish","score":min(60+hawkish*5,90)}
        if dovish > hawkish: return {"bias":"bearish","score":min(60+dovish*5,90)}
        return {"bias":"neutral","score":50}
    except: return {"bias":"neutral","score":50}

def add_indicators(df):
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
    df["Vol_MA20"] = df["Volume"].rolling(20).mean()
    return df

def trend_direction(df):
    last = df.iloc[-1]
    if last["SMA50"] > last["SMA200"]: return 1
    if last["SMA50"] < last["SMA200"]: return -1
    return 0

def detect_liquidity_sweep(df):
    highs = df["High"].tail(40)
    lows = df["Low"].tail(40)
    if df.iloc[-1]["High"] > highs.max(): return -1
    if df.iloc[-1]["Low"] < lows.min(): return 1
    return 0

def detect_order_block(df):
    for i in range(len(df)-6,20,-1):
        c = df.iloc[i]
        n = df.iloc[i+1:i+4]
        if c["Close"] < c["Open"] and n["High"].max()>df["High"].iloc[i-10:i].max(): return 1
        if c["Close"] > c["Open"] and n["Low"].min()<df["Low"].iloc[i-10:i].min(): return -1
    return 0

def volatility_regime_ok(df):
    return df["ATR"].rank(pct=True).iloc[-1] > 0.4

def calculate_mtf_score(symbol):
    weights = {"1wk":0.4,"1d":0.3,"4h":0.2,"1h":0.1}
    score = 0
    details = {}
    for tf,w in weights.items():
        df = yf.download(symbol,period="2y",interval=tf,progress=False)
        if df.empty: continue
        df.dropna(inplace=True)
        df = add_indicators(df)
        t = trend_direction(df)
        score += t*w
        details[tf] = "Bullish" if t==1 else "Bearish" if t==-1 else "Neutral"
    return score,details

def calculate_risk_model(df,direction):
    entry = df.iloc[-1]["Close"]
    atr = df.iloc[-1]["ATR"]
    if direction>0:
        sl = entry - atr
        tp = entry + (atr*4)
    else:
        sl = entry + atr
        tp = entry - (atr*4)
    return round(entry,5), round(sl,5), round(tp,5)

def high_probability_filter(mtf,ob,sweep,vol_confirm,news,vol_ok):
    direction = np.sign(mtf)
    strong = abs(mtf) >= 0.5
    news_ok = news["score"] >= 50
    ob_ok = (direction>0 and ob==1) or (direction<0 and ob==-1)
    sweep_ok = (direction>0 and sweep==1) or (direction<0 and sweep==-1)
    if strong and news_ok and ob_ok and sweep_ok and vol_confirm and vol_ok:
        confidence = int(70 + abs(mtf)*20)
        return True,confidence,int(direction)
    return False,0,0

def log_trade(pair,direction,entry,sl,tp,confidence):
    columns=["Date","Pair","Direction","Entry","SL","TP","Confidence","Result","R_multiple"]
    if os.path.exists(TRADE_LOG):
        df = pd.read_csv(TRADE_LOG)
    else:
        df = pd.DataFrame(columns=columns)
    df = df.append({
        "Date":datetime.now(),
        "Pair":pair,
        "Direction":"BUY" if direction>0 else "SELL",
        "Entry":entry,
        "SL":sl,
        "TP":tp,
        "Confidence":confidence,
        "Result":None,
        "R_multiple":None
    },ignore_index=True)
    df.to_csv(TRADE_LOG,index=False)

def win_rate():
    if os.path.exists(TRADE_LOG):
        df = pd.read_csv(TRADE_LOG)
        if "Result" in df.columns:
            wins = df[df["Result"]=="WIN"].shape[0]
            total = df[df["Result"].notnull()].shape[0]
            return round((wins/total)*100,2) if total>0 else 0
    return 0

def total_r():
    if os.path.exists(TRADE_LOG):
        df = pd.read_csv(TRADE_LOG)
        if "R_multiple" in df.columns:
            return round(df["R_multiple"].sum(),2)
    return 0

def calculate_currency_strength(pairs):
    strength = {}
    for p in pairs:
        df = yf.download(p,period="6mo",interval="1d",progress=False)
        if df.empty: continue
        ret = float(df["Close"].pct_change().dropna().mean())  # FIXED: convert to float
        base = p[:3]
        strength[base] = strength.get(base,0)+ret
    # sort numerically
    strength = {k:v for k,v in sorted(strength.items(), key=lambda item:item[1], reverse=True)}
    return strength

# ===============================
# MAIN FUNCTION
# ===============================

def main():
    st.set_page_config(layout="wide")
    st.title("Institutional Swing AI – Balanced Mode + Heatmap")
    
    news = get_usd_news_bias()
    col1,col2 = st.columns(2)
    col1.metric("USD Bias", news["bias"].upper())
    col2.metric("News Impact Score", news["score"])
    st.divider()
    
    signals_found=False
    all_strength = calculate_currency_strength(PAIRS)
    
    for pair in PAIRS:
        mtf_score, mtf_details = calculate_mtf_score(pair)
        df = yf.download(pair,period="5y",interval="1d",progress=False)
        if df.empty: continue
        df.dropna(inplace=True)
        df = add_indicators(df)
        ob = detect_order_block(df)
        sweep = detect_liquidity_sweep(df)
        vol_confirm = df.iloc[-1]["Volume"] > df.iloc[-1]["Vol_MA20"]
        vol_ok = volatility_regime_ok(df)
        trade,confidence,direction = high_probability_filter(
            mtf_score, ob, sweep, vol_confirm, news, vol_ok
        )
        if trade:
            signals_found=True
            entry, sl, tp = calculate_risk_model(df, direction)
            log_trade(pair,direction,entry,sl,tp,confidence)
            
            st.subheader(f"🔥 {pair}")
            c1,c2 = st.columns(2)
            with c1:
                st.write("Direction:", "BUY" if direction>0 else "SELL")
                st.write("Confidence:",f"{confidence}%")
                st.write("Entry:",entry)
            with c2:
                st.write("Stop Loss:",sl)
                st.write("Take Profit (4R):",tp)
                st.write("Volatility Regime:","Normal")
            st.write("MTF Alignment:",mtf_details)
            st.progress(confidence/100)
            st.divider()
            
    if not signals_found:
        st.warning("No High Probability Trades Today")
    
    st.divider()
    st.subheader("📊 Performance Stats")
    st.write(f"Win Rate: {win_rate()}%")
    st.write(f"Total R-Multiple: {total_r()}")
    
    st.subheader("💹 Currency Strength Heatmap")
    df_heat = pd.DataFrame.from_dict(all_strength,orient="index",columns=["Strength"])
    st.bar_chart(df_heat)

# ===============================
# AUTO-REFRESH
# ===============================

if __name__=="__main__":
    while True:
        main()
        st.experimental_rerun()
        time.sleep(AUTO_REFRESH_INTERVAL)
