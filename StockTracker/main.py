import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from fuzzywuzzy import process
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page config
st.set_page_config(page_title="Stock Data Visualization", layout="wide")

# List of international stock exchanges and their suffixes
EXCHANGES = {
    'Paris': '.PA',
    'Frankfurt': '.F',
    'London': '.L',
    'Tokyo': '.T',
    'Hong Kong': '.HK',
    'Shanghai': '.SS',
    'Shenzhen': '.SZ',
    'Toronto': '.TO',
    'Sydney': '.AX',
    'Oslo': '.OL'
}

# Function to search for company symbols
def search_company(query):
    common_stocks = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft Corporation',
        'GOOGL': 'Alphabet Inc.',
        'AMZN': 'Amazon.com Inc.',
        'META': 'Meta Platforms, Inc.',
        'TSLA': 'Tesla, Inc.',
        'NVDA': 'NVIDIA Corporation',
        'JPM': 'JPMorgan Chase & Co.',
        'V': 'Visa Inc.',
        'JNJ': 'Johnson & Johnson',
        'WMT': 'Walmart Inc.',
        'KO': 'The Coca-Cola Company',
        'DIS': 'The Walt Disney Company',
        'NFLX': 'Netflix, Inc.',
        'PYPL': 'PayPal Holdings, Inc.',
        'PEP': 'PepsiCo, Inc.',
        'CRM': 'Salesforce.com Inc.',
        'COST': 'Costco Wholesale Corporation',
        'BAC': 'Bank of America Corporation',
        'C': 'Citigroup Inc.',
        'WFC': 'Wells Fargo & Company',
        'UNH': 'UnitedHealth Group Incorporated',
        'PG': 'Procter & Gamble Company',
        'T': 'AT&T Inc.',
        'BMY': 'Bristol-Myers Squibb Company',
        'STLAM': 'Stellantis N.V.',
        'XOM': 'Exxon Mobil Corporation',
        'CVX': 'Chevron Corporation',
        'MCD': 'McDonald\'s Corporation',
        'BA': 'The Boeing Company',
    }

    known_stock_symbols = set(common_stocks.keys())

    # Try direct symbol lookup
    try:
        ticker = yf.Ticker(query)
        info = ticker.info
        logger.info(f"Raw info for {query}: {info}")

        if info and 'symbol' in info:
            if info['symbol'] in known_stock_symbols:
                logger.info(f"{query} is a known stock symbol. Returning it directly.")
                return info['symbol']
            elif info.get('quoteType') == 'EQUITY':
                logger.info(f"{query} is identified as an EQUITY. Returning it.")
                return info['symbol']
            else:
                logger.warning(f"{query} is not identified as a stock. Quote type: {info.get('quoteType')}")

                # Fallback: Check if it's listed on a major exchange
                if info.get('exchange') in ['NYSE', 'NASDAQ', 'AMEX']:
                    logger.info(f"{query} is listed on {info.get('exchange')}. Treating it as a stock.")
                    return info['symbol']

                st.warning(f"'{query}' is not identified as a stock. It appears to be a {info.get('quoteType', 'different financial instrument')}.")
                return None
    except Exception as e:
        logger.error(f"Error during direct symbol lookup for {query}: {str(e)}")
        st.warning(f"Error during direct symbol lookup: {str(e)}")

    # Fuzzy matching
    best_match = process.extractOne(query, list(common_stocks.values()) + list(common_stocks.keys()), score_cutoff=70)
    if best_match:
        matched_name = best_match[0]
        for symbol, name in common_stocks.items():
            if name == matched_name or symbol == matched_name:
                logger.info(f"Fuzzy match found for {query}: {symbol}")
                return symbol

    # Try with exchange suffixes
    for exchange, suffix in EXCHANGES.items():
        symbol_with_suffix = f"{query}{suffix}"
        try:
            ticker = yf.Ticker(symbol_with_suffix)
            info = ticker.info
            logger.info(f"Raw info for {symbol_with_suffix}: {info}")
            if info and 'symbol' in info:
                if info.get('quoteType') == 'EQUITY' or info['symbol'] in known_stock_symbols:
                    logger.info(f"Found stock with exchange suffix: {symbol_with_suffix}")
                    return symbol_with_suffix
                else:
                    logger.warning(f"{symbol_with_suffix} is not identified as a stock. Quote type: {info.get('quoteType')}")
        except Exception as e:
            logger.error(f"Error during exchange suffix lookup for {symbol_with_suffix}: {str(e)}")

    # Fallback: Use yfinance search function
    try:
        search_results = yf.Ticker(query).search()
        if search_results:
            top_result = search_results[0]
            logger.info(f"Fallback search found: {top_result}")
            return top_result['symbol']
    except Exception as e:
        logger.error(f"Error during fallback search for {query}: {str(e)}")

    # If no match found
    logger.warning(f"No match found for {query}")
    st.error(f"Unable to find stock data for '{query}'. It may not be a valid stock symbol or the company name might be incorrect.")
    st.info("Please try the following:")
    st.info("1. Check the spelling of the company name or stock symbol.")
    st.info("2. For international stocks, try adding the exchange suffix (e.g., .PA for Paris, .L for London).")
    st.info("3. Use the official stock symbol if you know it.")
    st.info("4. For less common stocks, you may need to use a more specialized financial data source.")
    return None

# ... (rest of the code remains the same)

if __name__ == '__main__':
    main()
