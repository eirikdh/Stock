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
import logging

# Download NLTK data
nltk.download('vader_lexicon', quiet=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "YOUR_NEWS_API_KEY")

def fetch_all_stock_symbols():
    try:
        with open('/StockTracker/all_tickers.txt', 'r') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        logger.warning("all_tickers.txt not found. Using fallback symbols.")
        return ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V', 'NFLX', 'DIS', 'ADBE', 'CRM', 'PYPL', 'NAS.OL']

# Use this function to update STOCK_SYMBOLS
@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_stock_symbols():
    return fetch_all_stock_symbols()

STOCK_SYMBOLS = load_stock_symbols()

# Function to fetch stock data
def fetch_stock_data(symbol, start_date, end_date):
    try:
        logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_date, end=end_date)
        info = stock.info
        return hist, info
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {str(e)}")
        return None, None

# Function to fetch news articles
def fetch_news_articles(symbol, num_articles=5):
    try:
        url = f"https://newsapi.org/v2/everything?q={symbol}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize={num_articles}"
        response = requests.get(url)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        return articles
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {str(e)}")
        return []

# Function to perform sentiment analysis
def analyze_sentiment(text):
    sia = SentimentIntensityAnalyzer()
    sentiment_scores = sia.polarity_scores(text)
    compound_score = sentiment_scores['compound']
    
    if compound_score > 0.05:
        sentiment = "Positive"
    elif compound_score < -0.05:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"
    
    return sentiment, compound_score

# Function to get overall sentiment from articles
def get_overall_sentiment(articles):
    if not articles:
        return "N/A", 0

    total_score = 0
    for article in articles:
        text = article['title'] + ' ' + article['description']
        _, score = analyze_sentiment(text)
        total_score += score

    avg_score = total_score / len(articles)
    overall_sentiment, _ = analyze_sentiment(str(avg_score))
    return overall_sentiment, avg_score

# Main app
def main():
    st.title("Stock Data Visualization App")
    st.write("Main function called successfully!")

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
        st.info("Select a stock symbol from the dropdown or enter a custom symbol.")

        # User input
        input_type = st.radio("Choose input method:", ("Dropdown", "Custom"))
        
        if input_type == "Dropdown":
            symbol = st.selectbox("Select a stock symbol:", STOCK_SYMBOLS)
        else:
            symbol = st.text_input("Enter custom stock symbol:", "").upper()

        # Validate the entered symbol
        if symbol and symbol not in STOCK_SYMBOLS:
            st.warning(f"The symbol '{symbol}' is not in our list of known stocks. Please make sure it's correct.")

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

            with st.spinner(f"Fetching data for {symbol}..."):
                hist_data, info = fetch_stock_data(symbol, start_date, end_date)

                if hist_data is not None and info is not None:
                    # Display basic information
                    st.subheader(f"Stock Information for {symbol}")
                    st.write(f"Company Name: {info.get('longName', 'N/A')}")
                    st.write(f"Current Price: ${info.get('currentPrice', 'N/A')}")
                    st.write(f"Market Cap: ${info.get('marketCap', 'N/A'):,}")

                    # Display price history chart
                    st.subheader("Price History")
                    fig = go.Figure(data=go.Scatter(x=hist_data.index, y=hist_data['Close'], mode='lines'))
                    fig.update_layout(title=f"{symbol} Stock Price", xaxis_title="Date", yaxis_title="Price")
                    st.plotly_chart(fig)

                    # Display data table
                    st.subheader("Historical Data")
                    st.dataframe(hist_data)

                    # Fetch and display sentiment analysis
                    st.subheader("Sentiment Analysis")
                    with st.spinner("Fetching and analyzing news articles..."):
                        articles = fetch_news_articles(symbol)
                        if articles:
                            overall_sentiment, avg_score = get_overall_sentiment(articles)
                            st.write(f"Overall Sentiment: {overall_sentiment} {':slight_frown:' if overall_sentiment == 'Negative' else ':neutral_face:' if overall_sentiment == 'Neutral' else ':slight_smile:'}")
                            st.write(f"Average Sentiment Score: {avg_score:.2f}")

                            st.subheader("Recent News Articles")
                            for article in articles[:3]:  # Display top 3 articles
                                st.write(f"**{article['title']}**")
                                st.write(f"Source: {article['source']['name']}")
                                st.write(f"Published: {article['publishedAt']}")
                                st.write(article['description'])
                                st.markdown(f"[Read More]({article['url']})")
                                st.write('---')
                        else:
                            st.warning("No recent news articles found for this stock.")
                else:
                    st.error(f"Failed to retrieve data for {symbol}. Please try again.")

    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        logger.error(f"Unexpected error in main function: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
