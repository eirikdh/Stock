# Stock Data Visualization App

This is a Streamlit app that visualizes stock data using data from Yahoo Finance.

## Deploying to Heroku

To deploy this app to Heroku, follow these steps:

1. Sign up for a Heroku account if you haven't already: https://signup.heroku.com/

2. Install the Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli

3. Open a terminal and log in to Heroku:
   ```
   heroku login
   ```

4. Clone this repository to your local machine:
   ```
   git clone <repository-url>
   cd <repository-name>
   ```

5. Create a new Heroku app:
   ```
   heroku create your-app-name
   ```

6. Set the Python version in `runtime.txt`:
   ```
   echo "python-3.9.16" > runtime.txt
   ```

7. Commit the changes:
   ```
   git add .
   git commit -m "Add runtime.txt for Heroku"
   ```

8. Push the code to Heroku:
   ```
   git push heroku main
   ```

9. Open the app in your browser:
   ```
   heroku open
   ```

Your Stock Data Visualization App should now be live on Heroku!

## Local Development

To run the app locally:

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the Streamlit app:
   ```
   streamlit run main.py
   ```

The app will be available at `http://localhost:5000`.
