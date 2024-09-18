import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import random
from alpha_vantage.timeseries import TimeSeries
import os
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from newspaper import Article
import requests
from requests.exceptions import RequestException
from alpha_vantage.fundamentaldata import FundamentalData
import hashlib
import json
from bs4 import BeautifulSoup

# Download NLTK data
nltk.download('vader_lexicon', quiet=True)

# Set page config
st.set_page_config(
    page_title='Stock Data Visualization',
    layout='wide',
    initial_sidebar_state='expanded',
    menu_items=None
)

# Alpha Vantage API key
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")

# NewsAPI key
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

# Predefined list of common stock symbols
FALLBACK_SYMBOLS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V', 'NFLX', 'DIS', 'ADBE', 'CRM', 'PYPL', 'NAS.OL']

def load_stock_symbols():
    try:
        with open('StockTracker/all_tickers.txt', 'r') as file:
            symbols = [line.strip() for line in file]
        return symbols
    except Exception as e:
        st.error(f"Error loading stock symbols: {str(e)}")
        return FALLBACK_SYMBOLS

STOCK_SYMBOLS = load_stock_symbols()

# ... [rest of the code remains unchanged]

# Main app
def main():
    st.title("Stock Data Visualization App")

    # Add mobile view toggle
    st.session_state.is_mobile = st.checkbox('Mobile view', value=st.session_state.get('is_mobile', False))

    # Adjust font sizes and padding for better readability on small screens
    st.markdown('''
        <style>
        @media (max-width: 768px) {
            .stApp {
                font-size: 14px;
            }
            .stButton>button {
                padding: 0.5rem 1rem;
            }
        }
        </style>
    ''', unsafe_allow_html=True)

    try:
        # User input
        col1, col2 = st.columns(2)
        with col1:
            symbol_dropdown = st.selectbox("Select a stock symbol:", STOCK_SYMBOLS)
        with col2:
            symbol_input = st.text_input("Or enter a custom stock symbol:")
        
        symbol = symbol_input.upper() if symbol_input else symbol_dropdown

        # Date range selection with input validation
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", datetime.now() - timedelta(days=365))
        with col2:
            end_date = st.date_input("End date", datetime.now())

        if start_date and end_date and start_date >= end_date:
            st.error("Start date must be before end date.")
            return

        if st.button("Fetch Data"):
            if not symbol:
                st.error("Please enter a stock symbol.")
                return

            # Fetch stock data
            hist_data, info, data_source = get_stock_data(symbol, start_date, end_date)

            if hist_data is not None and info is not None:
                # Display key financial information
                st.subheader(f"Key Financial Information for {symbol}")
                cols = st.columns(1 if is_mobile() else 4)

                current_price = info.get('currentPrice', 'N/A')
                cols[0].metric("Current Price", f"${format_number(current_price)}")

                market_cap = info.get('marketCap', 'N/A')
                cols[1 if not is_mobile() else 0].metric("Market Cap", format_number(market_cap))

                pe_ratio = info.get('trailingPE', 'N/A')
                cols[2 if not is_mobile() else 0].metric("P/E Ratio", format_pe_ratio(pe_ratio))

                fifty_two_week_high = info.get('fiftyTwoWeekHigh', 'N/A')
                cols[3 if not is_mobile() else 0].metric("52 Week High", f"${format_number(fifty_two_week_high)}")

                # Additional financial information
                with st.expander("Additional Financial Information"):
                    cols = st.columns(1 if is_mobile() else 4)

                    fifty_two_week_low = info.get('fiftyTwoWeekLow', 'N/A')
                    cols[0].metric("52 Week Low", f"${format_number(fifty_two_week_low)}")

                    volume = info.get('volume', 'N/A')
                    cols[1 if not is_mobile() else 0].metric("Volume", format_number(volume))

                    avg_volume = info.get('averageVolume', 'N/A')
                    cols[2 if not is_mobile() else 0].metric("Avg Volume", format_number(avg_volume))

                    dividend_yield = info.get('dividendYield', 'N/A')
                    if dividend_yield != 'N/A':
                        dividend_yield = f"{float(dividend_yield) * 100:.2f}%"
                    cols[3 if not is_mobile() else 0].metric("Dividend Yield", dividend_yield)

                # Company information
                with st.expander("Company Information"):
                    cols = st.columns(1 if is_mobile() else 2)
                    cols[0].metric("Company Name", info.get('longName', 'N/A'))
                    cols[1 if not is_mobile() else 0].metric("Country", info.get('country', 'N/A'))
                    cols = st.columns(1 if is_mobile() else 2)
                    cols[0].metric("Sector", info.get('sector', 'N/A'))
                    cols[1 if not is_mobile() else 0].metric("Industry", info.get('industry', 'N/A'))

                # Sentiment Analysis
                st.subheader("Sentiment Analysis")
                overall_sentiment, sentiment_scores, sentiment_source = get_sentiment_analysis(symbol)

                # Add emojis to sentiment display
                sentiment_emojis = {
                    "Positive": "😊",
                    "Neutral": "😐",
                    "Negative": "☹️"
                }

                st.write(f"Overall Sentiment: {sentiment_emojis[overall_sentiment]} {overall_sentiment}")
                st.write(f"Sentiment Source: {sentiment_source}")
                if sentiment_scores:
                    st.write("Sentiment Scores:")
                    cols = st.columns(4)
                    cols[0].metric("Positive", f"{sentiment_scores['pos']:.2f}")
                    cols[1].metric("Neutral", f"{sentiment_scores['neu']:.2f}")
                    cols[2].metric("Negative", f"{sentiment_scores['neg']:.2f}")
                    cols[3].metric("Compound", f"{sentiment_scores['compound']:.2f}")

                # Display price history chart
                st.subheader("Price History Chart")
                fig = create_price_chart(hist_data)
                st.plotly_chart(fig, use_container_width=True)

                # Display financial data table
                st.subheader("Financial Data Table")
                df_display = hist_data[['Open', 'High', 'Low', 'Close', 'Volume']].reset_index()
                df_display['Date'] = pd.to_datetime(df_display['Date']).dt.date
                if is_mobile():
                    st.dataframe(df_display[['Date', 'Close', 'Volume']], use_container_width=True)
                else:
                    st.dataframe(df_display, use_container_width=True)

                # Download button for CSV
                csv = df_display.to_csv(index=False)
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name=f"{symbol}_stock_data.csv",
                    mime="text/csv",
                )
            else:
                st.error("Failed to retrieve data. Please try again or use a different stock symbol.")
    except Exception as e:
        st.error("An unexpected error occurred. Please try again or contact support.")

if __name__ == "__main__":
    main()
