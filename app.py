import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Stock Analyser", page_icon="📈", layout="wide")


def get_api_key():
    # Real key lives in .streamlit/secrets.toml locally, or in the app's Secrets on Streamlit Cloud.
    # Falls back to Alpha Vantage's "demo" key, which only works for IBM.
    try:
        return st.secrets["ALPHA_VANTAGE_KEY"]
    except Exception:
        return "demo"


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_daily_prices(symbol, api_key):
    """Fetch ~100 days of daily prices. Cached for an hour to save API requests."""
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "apikey": api_key,
        },
        timeout=15,
    )
    data = response.json()

    if "Error Message" in data:
        raise ValueError(f"Couldn't find a stock called '{symbol}'. Check the ticker and try again.")
    if "Time Series (Daily)" not in data:
        # Alpha Vantage sends "Note" or "Information" when the daily limit is hit
        message = data.get("Note") or data.get("Information") or "Unexpected response from Alpha Vantage."
        raise RuntimeError(message)

    df = pd.DataFrame.from_dict(data["Time Series (Daily)"], orient="index")
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


st.title("📈 Stock Analyser")

api_key = get_api_key()
if api_key == "demo":
    st.info("Using the demo key, which only works for **IBM**. Add your own Alpha Vantage key to look up other stocks.")

symbol = st.text_input("Stock ticker", value="IBM", max_chars=10).strip().upper()

if not symbol:
    st.stop()

try:
    with st.spinner(f"Fetching {symbol}..."):
        prices = fetch_daily_prices(symbol, api_key)
except Exception as error:
    st.error(str(error))
    st.stop()

prices["MA 20"] = prices["Close"].rolling(20).mean()
prices["MA 50"] = prices["Close"].rolling(50).mean()

latest = prices.iloc[-1]
previous = prices.iloc[-2]
change = latest["Close"] - previous["Close"]
change_pct = change / previous["Close"] * 100

st.subheader(symbol)
st.caption(f"Last trading day: {prices.index[-1]:%d %b %Y}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Price", f"${latest['Close']:,.2f}", f"{change:+,.2f} ({change_pct:+.2f}%)")
col2.metric("100-day high", f"${prices['High'].max():,.2f}")
col3.metric("100-day low", f"${prices['Low'].min():,.2f}")
col4.metric("Volume", f"{latest['Volume']:,.0f}")

st.markdown("#### Price and moving averages")
st.line_chart(prices[["Close", "MA 20", "MA 50"]])

st.markdown("#### Volume")
st.bar_chart(prices["Volume"])

with st.expander("Show raw data"):
    st.dataframe(prices.sort_index(ascending=False), width="stretch")
