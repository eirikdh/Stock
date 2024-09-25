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
import spacy
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    nltk.download('vader_lexicon', quiet=True)
    nlp = spacy.load("en_core_web_sm")
    logger.info("Successfully loaded spaCy NLP model")
except Exception as e:
    logger.error(f"Failed to load spaCy NLP model: {str(e)}")
    nlp = None

st.set_page_config(
    page_title='Stock Data Visualization',
    layout='wide',
    initial_sidebar_state='expanded',
    menu_items=None
)

ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

def fetch_all_stock_symbols():
    try:
        with open('StockTracker/all_tickers.txt', 'r') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        logger.warning("all_tickers.txt not found. Using fallback symbols.")
        return ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V', 'NFLX', 'DIS', 'ADBE', 'CRM', 'PYPL', 'NAS.OL']

@st.cache_data(ttl=86400)
def load_stock_symbols():
    return fetch_all_stock_symbols()

STOCK_SYMBOLS = load_stock_symbols()

def fetch_stock_data(symbol, start_date, end_date):
    try:
        logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_date, end=end_date)
        info = stock.info
        
        detailed_info = {
            'longName': info.get('longName', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'country': info.get('country', 'N/A'),
            'website': info.get('website', 'N/A'),
            'marketCap': info.get('marketCap', 'N/A'),
            'forwardPE': info.get('forwardPE', 'N/A'),
            'trailingPE': info.get('trailingPE', 'N/A'),
            'dividendYield': info.get('dividendYield', 'N/A'),
            'bookValue': info.get('bookValue', 'N/A'),
            'priceToBook': info.get('priceToBook', 'N/A'),
            'returnOnEquity': info.get('returnOnEquity', 'N/A'),
            'returnOnAssets': info.get('returnOnAssets', 'N/A'),
            'debtToEquity': info.get('debtToEquity', 'N/A'),
            'currentRatio': info.get('currentRatio', 'N/A'),
            'quickRatio': info.get('quickRatio', 'N/A'),
            'beta': info.get('beta', 'N/A'),
            'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh', 'N/A'),
            'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow', 'N/A'),
            'averageVolume': info.get('averageVolume', 'N/A'),
            'fullTimeEmployees': info.get('fullTimeEmployees', 'N/A'),
        }
        
        return hist, detailed_info
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {str(e)}")
        return None, None

def check_article_relevance(article, company_name, symbol):
    logger.debug(f"Checking relevance for article: {article.get('title', 'No title')}")
    
    title = article.get('title', '').lower()
    description = article.get('description', '').lower()
    content = title + ' ' + description
    
    if nlp:
        try:
            doc = nlp(content)
            entities = [ent.text.lower() for ent in doc.ents if ent.label_ in ['ORG', 'PRODUCT']]
            
            company_words = company_name.lower().split()
            is_relevant = any(word in entities for word in company_words) or symbol.lower() in entities
        except Exception as e:
            logger.error(f"Error in NLP processing: {str(e)}")
            is_relevant = False
    else:
        company_words = company_name.lower().split()
        is_relevant = any(word in content for word in company_words) or symbol.lower() in content
    
    stock_keywords = ['stock', 'shares', 'market', 'investor', 'finance', 'earnings', 'revenue', 'profit', 'loss']
    has_stock_keyword = any(keyword in content for keyword in stock_keywords)
    
    relevance_score = (is_relevant or has_stock_keyword)
    logger.debug(f"Article relevance: {relevance_score}")
    return relevance_score

def fetch_news_articles_fallback(symbol, company_name):
    logger.info(f"Using fallback method to fetch news for {symbol} ({company_name})")
    try:
        url = f"https://finance.yahoo.com/quote/{symbol}/news"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []
        
        for item in soup.find_all('li', class_='js-stream-content'):
            title = item.find('h3').text if item.find('h3') else ''
            link = item.find('a')['href'] if item.find('a') else ''
            description = item.find('p').text if item.find('p') else ''
            pub_date = item.find('span', class_='C(#959595)').text if item.find('span', class_='C(#959595)') else ''
            
            if title and link:
                articles.append({
                    'title': title,
                    'url': f"https://finance.yahoo.com{link}" if link.startswith('/') else link,
                    'description': description,
                    'source': {'name': 'Yahoo Finance'},
                    'publishedAt': pub_date
                })
        
        logger.info(f"Fetched {len(articles)} articles from Yahoo Finance")
        return articles[:5]
    except Exception as e:
        logger.error(f"Error in fallback news fetching for {symbol}: {str(e)}")
        return []

@st.cache_data(ttl=3600)
def fetch_news_articles(symbol, company_name, num_articles=5):
    logger.info(f"Fetching news articles for {symbol} ({company_name})")
    try:
        if not NEWS_API_KEY:
            logger.warning("NEWS_API_KEY is not set. Using fallback method.")
            return fetch_news_articles_fallback(symbol, company_name)

        query = f'"{company_name}" OR {symbol}'
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize=20"
        
        logger.debug(f"Sending request to News API: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        logger.info(f"Fetched {len(articles)} articles from News API")

        if not articles:
            logger.warning("No articles found from News API, using fallback method")
            return fetch_news_articles_fallback(symbol, company_name)

        relevant_articles = []
        for article in articles:
            if check_article_relevance(article, company_name, symbol):
                try:
                    news_article = Article(article['url'])
                    news_article.download()
                    news_article.parse()
                    article['full_text'] = news_article.text
                    logger.debug(f"Successfully fetched full text for article: {article['url']}")
                except Exception as e:
                    logger.warning(f"Failed to fetch full text for article: {str(e)}")
                    article['full_text'] = article.get('description', '')
                
                relevant_articles.append(article)
                if len(relevant_articles) == num_articles:
                    break
        
        logger.info(f"Found {len(relevant_articles)} relevant articles")
        return relevant_articles
    except RequestException as e:
        logger.error(f"Error fetching news for {symbol}: {str(e)}")
        return fetch_news_articles_fallback(symbol, company_name)
    except Exception as e:
        logger.error(f"Unexpected error fetching news for {symbol}: {str(e)}", exc_info=True)
        return fetch_news_articles_fallback(symbol, company_name)

def analyze_sentiment(text):
    try:
        if text is None:
            return {'compound': 0, 'pos': 0, 'neu': 0, 'neg': 0}
        sia = SentimentIntensityAnalyzer()
        sentiment_scores = sia.polarity_scores(text)
        return sentiment_scores
    except Exception as e:
        logger.error(f'Error in sentiment analysis: {str(e)}')
        return {'compound': 0, 'pos': 0, 'neu': 0, 'neg': 0}

@st.cache_data(ttl=3600)
def get_overall_sentiment(articles):
    if not articles:
        return "N/A", {'compound': 0, 'pos': 0, 'neu': 0, 'neg': 0}

    try:
        total_scores = {'compound': 0, 'pos': 0, 'neu': 0, 'neg': 0}
        for article in articles:
            scores = analyze_sentiment((article.get('title') or '') + ' ' + (article.get('description') or '') + ' ' + (article.get('full_text') or ''))
            for key in total_scores:
                total_scores[key] += scores[key]
        
        num_articles = len(articles)
        avg_scores = {key: value / num_articles for key, value in total_scores.items()}
        
        compound_score = avg_scores['compound']
        if compound_score > 0.5:
            overall_sentiment = "Very Positive"
        elif 0.1 <= compound_score <= 0.5:
            overall_sentiment = "Positive"
        elif -0.1 < compound_score < 0.1:
            overall_sentiment = "Neutral"
        elif -0.5 <= compound_score <= -0.1:
            overall_sentiment = "Negative"
        else:
            overall_sentiment = "Very Negative"
        
        return overall_sentiment, avg_scores
    except Exception as e:
        logger.error(f"Error in overall sentiment calculation: {str(e)}")
        return "Error", {'compound': 0, 'pos': 0, 'neu': 0, 'neg': 0}

def main():
    st.title("Stock Data Visualization App")

    is_mobile = st.checkbox('Mobile view', value=False, key='mobile_view')

    if is_mobile:
        st.markdown("""
            <style>
            .stApp {
                max-width: 100%;
                padding: 1rem;
                font-size: 14px;
            }
            .stButton > button {
                width: 100%;
                margin-bottom: 1rem;
            }
            .stPlotlyChart {
                height: 300px !important;
            }
            .dataframe {
                font-size: 10px;
            }
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
            .stApp {
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }
            </style>
        """, unsafe_allow_html=True)

    try:
        st.info("Select a stock symbol from the dropdown or enter a custom symbol.")

        input_type = st.radio("Choose input method:", ("Dropdown", "Custom"))
        
        if input_type == "Dropdown":
            symbol = st.selectbox("Select a stock symbol:", STOCK_SYMBOLS)
        else:
            symbol = st.text_input("Enter custom stock symbol:", "").upper()

        if symbol and symbol not in STOCK_SYMBOLS:
            st.warning(f"The symbol '{symbol}' is not in our list of known stocks. Please make sure it's correct.")

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
                    st.subheader(f"Stock Information for {symbol}")
                    
                    st.write("### Company Overview")
                    st.write(f"Company Name: {info['longName']}")
                    st.write(f"Sector: {info['sector']}")
                    st.write(f"Industry: {info['industry']}")
                    st.write(f"Country: {info['country']}")
                    st.write(f"Website: [{info['website']}]({info['website']})")
                    st.write(f"Full-time Employees: {info['fullTimeEmployees']:,}")

                    st.write("### Financial Metrics")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Market Cap", f"${info['marketCap']:,.0f}" if isinstance(info['marketCap'], (int, float)) else 'N/A')
                        st.metric("Forward P/E", f"{info['forwardPE']:.2f}" if isinstance(info['forwardPE'], (int, float)) else 'N/A')
                        st.metric("Trailing P/E", f"{info.get('trailingPE', 'N/A')}" if isinstance(info.get('trailingPE'), (int, float)) else 'N/A')
                    with col2:
                        st.metric("Price to Book", f"{info['priceToBook']:.2f}" if isinstance(info['priceToBook'], (int, float)) else 'N/A')
                        st.metric("Return on Equity", f"{info['returnOnEquity']:.2%}" if isinstance(info['returnOnEquity'], (int, float)) else 'N/A')
                        st.metric("Return on Assets", f"{info['returnOnAssets']:.2%}" if isinstance(info['returnOnAssets'], (int, float)) else 'N/A')
                    with col3:
                        st.metric("Debt to Equity", f"{info['debtToEquity']:.2f}" if isinstance(info['debtToEquity'], (int, float)) else 'N/A')
                        st.metric("Current Ratio", f"{info['currentRatio']:.2f}" if isinstance(info['currentRatio'], (int, float)) else 'N/A')
                        st.metric("Quick Ratio", f"{info['quickRatio']:.2f}" if isinstance(info['quickRatio'], (int, float)) else 'N/A')

                    st.write("### Stock Performance")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("52 Week High", f"${info['fiftyTwoWeekHigh']:.2f}" if isinstance(info['fiftyTwoWeekHigh'], (int, float)) else 'N/A')
                    with col2:
                        st.metric("52 Week Low", f"${info['fiftyTwoWeekLow']:.2f}" if isinstance(info['fiftyTwoWeekLow'], (int, float)) else 'N/A')
                    with col3:
                        st.metric("Average Volume", f"{info['averageVolume']:,.0f}" if isinstance(info['averageVolume'], (int, float)) else 'N/A')

                    st.write("### Price History")
                    fig = go.Figure(data=go.Scatter(x=hist_data.index, y=hist_data['Close'], mode='lines'))
                    fig.update_layout(
                        title=f"{symbol} Stock Price",
                        xaxis_title="Date",
                        yaxis_title="Price",
                        height=500 if not is_mobile else 300
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Historical Data")
                    st.dataframe(hist_data, height=300 if not is_mobile else 200)

                    st.subheader("Sentiment Analysis")
                    with st.spinner("Fetching and analyzing news articles..."):
                        articles = fetch_news_articles(symbol, info['longName'], num_articles=5)
                        if articles:
                            overall_sentiment, avg_scores = get_overall_sentiment(articles)
                            sentiment_emoji = {
                                "Very Positive": ":star-struck:",
                                "Positive": ":smile:",
                                "Neutral": ":neutral_face:",
                                "Negative": ":slightly_frowning_face:",
                                "Very Negative": ":worried:",
                                "Error": ":warning:"
                            }
                            st.write(f"Overall Sentiment: {overall_sentiment} {sentiment_emoji.get(overall_sentiment, '')}")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Compound Score", f"{avg_scores['compound']:.2f}")
                            col2.metric("Positive", f"{avg_scores['pos']:.2f}")
                            col3.metric("Neutral", f"{avg_scores['neu']:.2f}")
                            col4.metric("Negative", f"{avg_scores['neg']:.2f}")

                            st.subheader("Recent News Articles")
                            for article in articles:
                                with st.expander(f"{article['title']} - {article['source']['name']}"):
                                    st.write(f"Published: {article['publishedAt']}")
                                    st.write(article.get('description', 'No description available'))
                                    article_sentiment = analyze_sentiment((article.get('title') or '') + ' ' + (article.get('description') or '') + ' ' + (article.get('full_text') or ''))
                                    st.write(f"Article Sentiment: {article_sentiment['compound']:.2f}")
                                    st.markdown(f"[Read More at {article['source']['name']} ↗]({article['url']})", unsafe_allow_html=True)
                        else:
                            st.warning("No recent news articles found for this stock.")
                else:
                    st.error(f"Failed to retrieve data for {symbol}. Please try again.")

    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        logger.error(f"Unexpected error in main function: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
