import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import random
import requests
from alpha_vantage.timeseries import TimeSeries
import os
import json

# Set page config
st.set_page_config(
    page_title='Stock Data Visualization',
    layout='wide',
    initial_sidebar_state='expanded',
    menu_items=None
)

# Set page theme
st.markdown(
    '''
    <style>
    .stApp {
        background-color: #000000;
        color: #00FF00;
    }
    </style>
    ''',
    unsafe_allow_html=True
)

# Alpha Vantage API key
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "YOUR_ALPHA_VANTAGE_API_KEY")

# Predefined list of common stock symbols (as fallback)
FALLBACK_SYMBOLS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V', 'NFLX', 'DIS', 'ADBE', 'CRM', 'PYPL', 'NAS.OL']

def fetch_all_stock_symbols():
    return FALLBACK_SYMBOLS

# Use this function to update STOCK_SYMBOLS
@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_stock_symbols():
    return fetch_all_stock_symbols()

STOCK_SYMBOLS = load_stock_symbols()

# Function to fetch stock data with retry mechanism and fallback to Alpha Vantage
def get_stock_data(symbol, start_date, end_date, max_retries=3):
    for attempt in range(max_retries):
        try:
            st.info(f"Attempting to fetch data for {symbol} from Yahoo Finance (Attempt {attempt + 1}/{max_retries})")
            stock = yf.Ticker(symbol)
            hist = stock.history(start=start_date, end=end_date)
            info = stock.info

            # Check if info dictionary is empty or contains only NULL values
            if not info or all(v is None for v in info.values()):
                st.warning(f"Limited or no data available for {symbol} from Yahoo Finance. Falling back to Alpha Vantage.")
                return fetch_alpha_vantage_data(symbol, start_date, end_date)

            # Extract all available financial information
            financial_info = {
                'symbol': symbol,
                'currentPrice': info.get('currentPrice', info.get('regularMarketPrice', 'N/A')),
                'marketCap': info.get('marketCap', info.get('regularMarketCap', 'N/A')),
                'trailingPE': info.get('trailingPE', info.get('forwardPE', 'N/A')),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh', 'N/A'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow', 'N/A'),
                'volume': info.get('volume', info.get('regularMarketVolume', 'N/A')),
                'averageVolume': info.get('averageVolume', 'N/A'),
                'dividendYield': info.get('dividendYield', 'N/A'),
                'beta': info.get('beta', 'N/A'),
                'dayHigh': info.get('dayHigh', info.get('regularMarketDayHigh', 'N/A')),
                'dayLow': info.get('dayLow', info.get('regularMarketDayLow', 'N/A')),
                'longName': info.get('longName', 'N/A'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'country': info.get('country', 'N/A'),
            }

            st.success(f"Successfully fetched data for {symbol} from Yahoo Finance")
            return hist, financial_info, "Yahoo Finance"
        except Exception as e:
            st.warning(f"Error fetching data from Yahoo Finance for {symbol} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                st.info(f"Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                st.error(f"Failed to fetch data from Yahoo Finance for {symbol} after {max_retries} attempts")
                return fetch_alpha_vantage_data(symbol, start_date, end_date)

def fetch_alpha_vantage_data(symbol, start_date, end_date):
    st.info("Attempting to fetch data from Alpha Vantage...")
    try:
        ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY)
        data, _ = ts.get_daily(symbol=symbol, outputsize='full')
        hist = pd.DataFrame(data).T
        hist.index = pd.to_datetime(hist.index)
        hist = hist[(hist.index >= pd.to_datetime(start_date)) & (hist.index <= pd.to_datetime(end_date))]
        hist.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        hist = hist.astype(float)

        # Fetch current price from Alpha Vantage
        current_price_data, _ = ts.get_quote_endpoint(symbol=symbol)
        current_price = current_price_data['Global Quote']['05. price']

        financial_info = {
            "symbol": symbol,
            "currentPrice": current_price,
            "marketCap": 'N/A',
            "trailingPE": 'N/A',
            "fiftyTwoWeekHigh": 'N/A',
            "fiftyTwoWeekLow": 'N/A',
            "volume": 'N/A',
            "averageVolume": 'N/A',
            "dividendYield": 'N/A',
            "beta": 'N/A',
            "dayHigh": 'N/A',
            "dayLow": 'N/A',
            "longName": 'N/A',
            "sector": 'N/A',
            "industry": 'N/A',
            "country": 'N/A',
        }
        st.success(f"Successfully fetched basic data for {symbol} from Alpha Vantage")
        return hist, financial_info, "Alpha Vantage"
    except Exception as av_e:
        st.error(f"Failed to fetch data from Alpha Vantage: {str(av_e)}")
        return None, None, None

# Function to create price history chart
def create_price_chart(data):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name='Price'
    ))
    fig.update_layout(
        title='Stock Price History',
        yaxis_title='Price',
        xaxis_title='Date',
        height=600,
        template='plotly_dark'
    )
    return fig

# Function to format large numbers
def format_number(num):
    if num is None or num == 'N/A':
        return "N/A"
    try:
        num = float(num)
        if num >= 1e9:
            return f"{num/1e9:.2f}B"
        elif num >= 1e6:
            return f"{num/1e6:.2f}M"
        elif num >= 1e3:
            return f"{num/1e3:.2f}K"
        else:
            return f"{num:.2f}"
    except ValueError:
        return "N/A"

# Function to format P/E Ratio
def format_pe_ratio(pe_ratio):
    if isinstance(pe_ratio, (int, float)) and pe_ratio > 0:
        return f"{pe_ratio:.2f}"
    else:
        return "N/A"

# Main app
def main():
    st.title("Stock Data Visualization App")
    st.write("Main function called successfully!")

    try:
        st.info("Enter a stock symbol. For certain stocks, you can use extended symbols like 'NAS.OL' for Norwegian Air Shuttle.")

        # User input
        input_type = "Stock Symbol" # Assuming the intention was to default to "Stock Symbol"
        symbol = st.text_input("Enter stock symbol (e.g., AAPL, 'GOOGL, MSFT, AMZN, META, TSLA, NVDA, JPM, JNJ, V, NFLX, DIS, ADBE, CRM, PYPL, NAS.OL):", "AAPL").upper()

        # Date range selection with input validation
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", datetime.now() - timedelta(days=365))
        with col2:
            end_date = st.date_input("End date", datetime.now())

        if start_date and end_date and start_date >= end_date:
            st.error("Error: Start date must be before end date.")
            return

        if st.button("Fetch Data"):
            if not symbol:
                st.error("Please enter a stock symbol.")
                return

            # Fetch stock data
            hist_data, info, data_source = get_stock_data(symbol, start_date, end_date)

            if hist_data is not None and info is not None:
                st.success(f"Data retrieved successfully from {data_source}")

                if data_source == "Alpha Vantage":
                    st.warning("Limited data available. Some financial metrics may not be displayed.")

                # Display key financial information
                st.subheader(f"Key Financial Information for {symbol}")
                col1, col2, col3, col4 = st.columns(4)

                current_price = info.get('currentPrice', 'N/A')
                col1.metric("Current Price", f"${format_number(current_price)}")

                market_cap = info.get('marketCap', 'N/A')
                col2.metric("Market Cap", format_number(market_cap))

                pe_ratio = info.get('trailingPE', 'N/A')
                col3.metric("P/E Ratio", format_pe_ratio(pe_ratio))

                fifty_two_week_high = info.get('fiftyTwoWeekHigh', 'N/A')
                col4.metric("52 Week High", f"${format_number(fifty_two_week_high)}")

                # Additional financial information
                st.subheader("Additional Financial Information")
                col5, col6, col7, col8 = st.columns(4)

                fifty_two_week_low = info.get('fiftyTwoWeekLow', 'N/A')
                col5.metric("52 Week Low", f"${format_number(fifty_two_week_low)}")

                volume = info.get('volume', 'N/A')
                col6.metric("Volume", format_number(volume))

                avg_volume = info.get('averageVolume', 'N/A')
                col7.metric("Avg Volume", format_number(avg_volume))

                dividend_yield = info.get('dividendYield', 'N/A')
                if dividend_yield != 'N/A':
                    dividend_yield = f"{float(dividend_yield) * 100:.2f}%"
                col8.metric("Dividend Yield", dividend_yield)

                # New section for additional company information
                st.subheader("Company Information")
                with st.expander("View Company Details"):
                    col9, col10 = st.columns(2)
                    col9.metric("Company Name", info.get('longName', 'N/A'))
                    col10.metric("Country", info.get('country', 'N/A'))
                    col11, col12 = st.columns(2)
                    col11.metric("Sector", info.get('sector', 'N/A'))
                    col12.metric("Industry", info.get('industry', 'N/A'))

                # Display price history chart
                st.subheader("Price History Chart")
                fig = create_price_chart(hist_data)
                st.plotly_chart(fig, use_container_width=True)

                # Display financial data table
                st.subheader("Financial Data Table")
                df_display = hist_data[['Open', 'High', 'Low', 'Close', 'Volume']].reset_index()
                df_display['Date'] = pd.to_datetime(df_display['Date']).dt.date
                st.dataframe(df_display)

                # Download button for CSV
                csv = df_display.to_csv(index=False)
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name=f"{symbol}_stock_data.csv",
                    mime="text/csv",
                )
            else:
                st.error(f"Failed to retrieve data for {symbol} from both Yahoo Finance and Alpha Vantage.")
                st.info("Please try again later or with a different stock symbol.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        st.info("Please try again or contact support if the problem persists.")

if __name__ == "__main__":
    main()
