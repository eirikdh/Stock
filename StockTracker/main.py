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
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "YOUR_ALPHA_VANTAGE_API_KEY")

# NewsAPI key
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "YOUR_NEWS_API_KEY")

# Predefined list of common stock symbols (as fallback)
FALLBACK_SYMBOLS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V', 'NFLX', 'DIS', 'ADBE', 'CRM', 'PYPL', 'NAS.OL']

def fetch_all_stock_symbols():
    return FALLBACK_SYMBOLS

# Use this function to update STOCK_SYMBOLS
@st.cache_data(ttl=80)  # Cache for 24 hours
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
        height=300 if is_mobile() else 600,
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

# Function to detect mobile view
def is_mobile():
    return st.session_state.get('is_mobile', False)

# Updated function for sentiment analysis with improved error handling, delays, and fallback methods
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_sentiment_analysis(symbol, max_retries=3):
    # Check cache first
    cache_key = f"sentiment_{symbol}"
    cached_result = st.session_state.get(cache_key)
    if cached_result:
        logger.info(f"Returning cached sentiment analysis for {symbol}")
        return cached_result

    def fetch_news_yahoo(symbol, max_retries=3):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        url = f"https://finance.yahoo.com/quote/{symbol}/news"
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                articles = Article(url)
                articles.download()
                articles.parse()
                return articles.text
            except Exception as e:
                logger.warning(f"Error fetching news from Yahoo Finance (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Retrying Yahoo Finance in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch news from Yahoo Finance after {max_retries} attempts")
                    raise

    def fetch_news_alpha_vantage(symbol):
        try:
            fd = FundamentalData(key=ALPHA_VANTAGE_API_KEY)
            data, _ = fd.get_company_overview(symbol)
            news = data.get('Description', '')
            return news
        except Exception as e:
            logger.error(f"Error fetching news from Alpha Vantage: {str(e)}")
            raise

    def fetch_news_newsapi(symbol):
        try:
            url = f"https://newsapi.org/v2/everything?q={symbol}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize=5"
            response = requests.get(url)
            response.raise_for_status()
            articles = response.json().get('articles', [])
            return ' '.join([article.get('title', '') + ' ' + article.get('description', '') for article in articles])
        except Exception as e:
            logger.error(f"Error fetching news from NewsAPI: {str(e)}")
            raise

    def improved_keyword_sentiment(text):
        positive_words = ['up', 'rise', 'gain', 'positive', 'profit', 'growth', 'increase', 'improved', 'recovery', 'bullish', 'outperform', 'beat', 'exceed', 'strong', 'success']
        negative_words = ['down', 'fall', 'loss', 'negative', 'decline', 'decrease', 'drop', 'bearish', 'underperform', 'miss', 'below', 'concern', 'weak', 'fail', 'risk']
        neutral_words = ['stable', 'steady', 'unchanged', 'flat', 'maintain', 'hold', 'mixed', 'balanced', 'neutral', 'fair']
        
        words = text.lower().split()
        positive_count = sum(word in positive_words for word in words)
        negative_count = sum(word in negative_words for word in words)
        neutral_count = sum(word in neutral_words for word in words)
        
        total_count = positive_count + negative_count + neutral_count
        if total_count == 0:
            return "Neutral", {'pos': 0.33, 'neu': 0.34, 'neg': 0.33, 'compound': 0}, "Improved Keyword Analysis"
        
        pos_score = positive_count / total_count
        neg_score = negative_count / total_count
        neu_score = neutral_count / total_count
        compound_score = (pos_score - neg_score) / (1 - min(pos_score, neg_score))
        
        if compound_score > 0.05:
            overall_sentiment = "Positive"
        elif compound_score < -0.05:
            overall_sentiment = "Negative"
        else:
            overall_sentiment = "Neutral"
        
        return overall_sentiment, {'pos': pos_score, 'neu': neu_score, 'neg': neg_score, 'compound': compound_score}, "Improved Keyword Analysis"

    default_sentiment = "Neutral"
    default_scores = {'pos': 0.33, 'neu': 0.34, 'neg': 0.33, 'compound': 0}
    default_source = "Default"

    news_sources = [
        ("Yahoo Finance", fetch_news_yahoo),
        ("Alpha Vantage", fetch_news_alpha_vantage),
        ("NewsAPI", fetch_news_newsapi)
    ]

    for source_name, fetch_function in news_sources:
        try:
            logger.info(f"Attempting to fetch news for {symbol} from {source_name}")
            news_text = fetch_function(symbol)
            if not news_text:
                logger.warning(f"No news content found from {source_name}")
                continue
            
            sia = SentimentIntensityAnalyzer()
            sentiment_scores = sia.polarity_scores(news_text)
            
            if sentiment_scores['compound'] > 0.05:
                overall_sentiment = "Positive"
            elif sentiment_scores['compound'] < -0.05:
                overall_sentiment = "Negative"
            else:
                overall_sentiment = "Neutral"
            
            logger.info(f"Successfully analyzed sentiment for {symbol} using {source_name}")
            result = (overall_sentiment, sentiment_scores, source_name)
            st.session_state[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Error performing sentiment analysis using {source_name}: {str(e)}")

    logger.warning(f"All news sources failed. Using improved keyword-based sentiment analysis for {symbol}")
    result = improved_keyword_sentiment(symbol)
    st.session_state[cache_key] = result
    return result

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
                st.error(f"Failed to retrieve data for {symbol} from both Yahoo Finance and Alpha Vantage.")
                st.info("Please try again later or with a different stock symbol.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        st.info("Please try again or contact support if the problem persists.")

if __name__ == "__main__":
    main()
