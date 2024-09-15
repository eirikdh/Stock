import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from fuzzywuzzy import process
import time
import random
import requests
from alpha_vantage.timeseries import TimeSeries
import os

# Set page config
st.set_page_config(page_title="Stock Data Visualization", layout="wide")

# Alpha Vantage API key
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "YOUR_ALPHA_VANTAGE_API_KEY")

# Function to check Yahoo Finance API status
def check_yahoo_finance_status():
    try:
        response = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/AAPL", timeout=5)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.RequestException:
        return False

# Function to search for company symbols with fallback
def search_company(query):
    try:
        # Search for companies using yfinance
        ticker = yf.Ticker(query)
        company_info = ticker.info
        if company_info and 'symbol' in company_info:
            return company_info['symbol']
        
        # If no exact match, use fuzzy matching on a predefined list of popular stocks
        popular_stocks = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'FB', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V']
        matches = process.extract(query, popular_stocks, limit=5)
        
        st.warning(f"No exact match found for '{query}'. Did you mean one of these?")
        for match, score in matches:
            if st.button(f"{match} (Similarity: {score}%)"):
                return match
        
        # Fallback: return a default stock symbol
        st.warning(f"No selection made. Falling back to default stock (AAPL).")
        return 'AAPL'
    except Exception as e:
        st.error(f"Error searching for company: {str(e)}")
        st.warning("Falling back to default stock (AAPL).")
        return 'AAPL'

# Function to fetch stock data with retry mechanism and fallback to Alpha Vantage
def get_stock_data(symbol, start_date, end_date, max_retries=3):
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(start=start_date, end=end_date)
            info = stock.info
            return hist, info, "Yahoo Finance"
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                st.warning(f"Error fetching data from Yahoo Finance for {symbol}. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                st.error(f"Failed to fetch data from Yahoo Finance for {symbol} after {max_retries} attempts: {str(e)}")
                st.info("Attempting to fetch data from Alpha Vantage...")
                try:
                    ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY)
                    data, _ = ts.get_daily(symbol=symbol, outputsize='full')
                    hist = pd.DataFrame(data).T
                    hist.index = pd.to_datetime(hist.index)
                    hist = hist[(hist.index >= start_date) & (hist.index <= end_date)]
                    hist.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                    hist = hist.astype(float)
                    info = {"symbol": symbol}  # Alpha Vantage doesn't provide detailed info
                    return hist, info, "Alpha Vantage"
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
        template='plotly_white'
    )
    return fig

# Function to format large numbers
def format_number(num):
    if num >= 1e9:
        return f"{num/1e9:.2f}B"
    elif num >= 1e6:
        return f"{num/1e6:.2f}M"
    elif num >= 1e3:
        return f"{num/1e3:.2f}K"
    else:
        return f"{num:.2f}"

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

    # Check Yahoo Finance API status
    if not check_yahoo_finance_status():
        st.warning("Yahoo Finance API might be experiencing issues. Data retrieval may be slower or use the fallback source.")

    try:
        # User input
        input_type = st.radio("Search by:", ("Stock Symbol", "Company Name"))
        if input_type == "Stock Symbol":
            symbol = st.text_input("Enter stock symbol (e.g., AAPL, GOOGL):", "AAPL").upper()
        else:
            company_name = st.text_input("Enter company name:", "Apple Inc.")
            symbol = search_company(company_name)
            if symbol:
                st.success(f"Using symbol: {symbol}")

        # Date range selection with input validation
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", datetime.now() - timedelta(days=365))
        with col2:
            end_date = st.date_input("End date", datetime.now())

        if start_date >= end_date:
            st.error("Error: Start date must be before end date.")
            return

        if st.button("Fetch Data"):
            # Fetch stock data
            hist_data, info, data_source = get_stock_data(symbol, start_date, end_date)

            if hist_data is not None and info is not None:
                st.success(f"Data retrieved successfully from {data_source}")
                
                # Display key financial information
                st.subheader(f"Key Financial Information for {symbol}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Current Price", f"${info.get('currentPrice', 'N/A'):.2f}" if isinstance(info.get('currentPrice'), (int, float)) else 'N/A')
                col2.metric("Market Cap", format_number(info.get('marketCap', 0)))
                col3.metric("P/E Ratio", format_pe_ratio(info.get('trailingPE', 'N/A')))
                col4.metric("52 Week High", f"${info.get('fiftyTwoWeekHigh', 'N/A'):.2f}" if isinstance(info.get('fiftyTwoWeekHigh'), (int, float)) else 'N/A')

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
