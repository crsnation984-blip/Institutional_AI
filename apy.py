import streamlit as st
import requests
from datetime import datetime

# ------------------------------
# Settings
# ------------------------------
NEWS_API_KEY = "628bc068ae804152a07be8cb93f86204"  # Replace with your key
NUM_ARTICLES = 20  # Articles per currency

CURRENCIES = {
    "USD": ["USD","Federal Reserve","CPI","NFP","GDP","Interest Rates"],
    "EUR": ["EUR","ECB","European Central Bank","Eurozone","Inflation"],
    "GBP": ["GBP","BOE","Bank of England","UK CPI","UK GDP"],
    "JPY": ["JPY","BoJ","Bank of Japan","Japan CPI","Japan GDP"],
    "AUD": ["AUD","RBA","Reserve Bank","Australia CPI","Australia GDP"],
    "CAD": ["CAD","BoC","Bank of Canada","Canada CPI","Canada GDP"],
    "CHF": ["CHF","SNB","Swiss National Bank","Switzerland CPI","Switzerland GDP"],
    "NZD": ["NZD","RBNZ","Reserve Bank of NZ","NZ CPI","NZ GDP"]
}

BULLISH_KEYWORDS = ["rate hike","inflation rising","strong jobs","hawkish","growth","positive"]
BEARISH_KEYWORDS = ["rate cut","inflation falling","weak jobs","dovish","recession","negative"]

# ------------------------------
# Functions
# ------------------------------
def get_news_bias(currency, keywords):
    query = " OR ".join(keywords)
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        articles = r.get("articles", [])[:NUM_ARTICLES]
        bullish = bearish = 0
        for a in articles:
            title = a["title"].lower()
            if any(w in title for w in BULLISH_KEYWORDS):
                bullish += 1
            if any(w in title for w in BEARISH_KEYWORDS):
                bearish += 1
        if bullish > bearish:
            return "Bullish", min(60 + bullish*5, 90)
        if bearish > bullish:
            return "Bearish", min(60 + bearish*5, 90)
        return "Neutral", 50
    except:
        return "Neutral", 50

# ------------------------------
# Streamlit UI
# ------------------------------
st.set_page_config(page_title="Currency News Bias", layout="wide")
st.title("💹 Major Currency High-Impact News Bias")

st.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.divider()

for curr, keywords in CURRENCIES.items():
    bias, confidence = get_news_bias(curr, keywords)
    col1, col2 = st.columns([1,3])
    col1.metric(f"{curr} Bias", bias)
    col2.progress(confidence/100)
    col2.write(f"Confidence: {confidence}%")
    st.divider()

st.write("This dashboard analyses the most recent high-impact news for each major currency and gauges bullish, bearish, or neutral bias based on keyword analysis.")
