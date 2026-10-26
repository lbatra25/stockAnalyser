from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Stock Analyser", page_icon="📈", layout="wide")

API_URL = "https://api.twelvedata.com"


def get_api_key():
    # Real key lives in .streamlit/secrets.toml locally, or in the app's Secrets on Streamlit Cloud.
    # Falls back to Twelve Data's "demo" key, which only works for AAPL.
    try:
        return st.secrets["TWELVE_DATA_KEY"]
    except Exception:
        return "demo"


def call_twelve_data(endpoint, params, api_key):
    response = requests.get(f"{API_URL}/{endpoint}", params={**params, "apikey": api_key}, timeout=15)
    data = response.json()
    if data.get("status") == "error":
        if data.get("code") == 429:
            raise RuntimeError("Too many requests — the free plan allows 8 per minute. Wait a minute and try again.")
        if data.get("code") in (400, 404):
            raise ValueError("Couldn't find that stock. Check the ticker (US stocks only, e.g. AAPL, MSFT, VOO).")
        raise RuntimeError(data.get("message", "Unexpected response from Twelve Data."))
    return data


@st.cache_data(ttl=60, show_spinner=False)
def fetch_quote(symbol, api_key):
    """Latest price. Cached for a minute so refreshing doesn't use up requests."""
    return call_twelve_data("quote", {"symbol": symbol}, api_key)


@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_daily_prices(symbol, api_key):
    """About a year of daily prices. Cached for 15 minutes."""
    data = call_twelve_data(
        "time_series", {"symbol": symbol, "interval": "1day", "outputsize": 252}, api_key
    )
    df = pd.DataFrame(data["values"]).set_index("datetime")
    df.index = pd.to_datetime(df.index)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    return df.sort_index()


st.title("📈 Stock Analyser")

api_key = get_api_key()
if api_key == "demo":
    st.info("Using the demo key, which only works for **AAPL**. Add your own Twelve Data key to look up other stocks.")

symbol = st.text_input("Stock ticker (US)", value="AAPL", max_chars=10).strip().upper()

if not symbol:
    st.stop()

try:
    with st.spinner(f"Fetching {symbol}..."):
        quote = fetch_quote(symbol, api_key)
        prices = fetch_daily_prices(symbol, api_key)
except Exception as error:
    st.error(str(error))
    st.stop()

prices["MA 20"] = prices["Close"].rolling(20).mean()
prices["MA 50"] = prices["Close"].rolling(50).mean()

price = float(quote["close"])
change = float(quote["change"])
change_pct = float(quote["percent_change"])
updated = datetime.fromtimestamp(quote.get("last_quote_at") or quote["timestamp"], tz=timezone.utc)
market_status = "🟢 Market open" if quote.get("is_market_open") else "🔴 Market closed"

st.subheader(f"{quote.get('name', symbol)} ({symbol})")
st.caption(f"{quote.get('exchange', '')} · {market_status} · Price as of {updated:%d %b %Y, %H:%M} UTC")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Price", f"${price:,.2f}", f"{change:+,.2f} ({change_pct:+.2f}%)")
col2.metric("52-week high", f"${float(quote['fifty_two_week']['high']):,.2f}")
col3.metric("52-week low", f"${float(quote['fifty_two_week']['low']):,.2f}")
col4.metric("Volume today", f"{float(quote['volume']):,.0f}")

st.markdown("#### Price and moving averages (last year)")
st.line_chart(prices[["Close", "MA 20", "MA 50"]])

st.markdown("#### Volume")
st.bar_chart(prices["Volume"])

with st.expander("Show raw data"):
    st.dataframe(prices.sort_index(ascending=False), width="stretch")
