# server.py
import os
import json
import time
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from collections import deque

# --- Import logic from your existing Python files ---
from GPT import call_gpt5
from GROK import call_grok4
from main import build_prompt, parse_model_json

# --- App Setup ---
load_dotenv()
app = Flask(__name__)
CORS(app)

# --- Configuration & In-Memory Storage ---
TARGET_DATE = "2025-09-19"
DEFAULT_MODEL_XAI = os.getenv("MODEL_XAI", "grok-4")
DEFAULT_MODEL_OPENAI = os.getenv("MODEL_OPENAI", "gpt-5")
DEFAULT_TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
DEFAULT_SEED = int(os.getenv("SEED", "12345"))
DEFAULT_RETRIES = int(os.getenv("RETRIES", "2"))
CACHE_EXPIRATION_SECONDS = 5 * 60  # 5 minutes

# In-memory stores
# For a real app, you'd replace these with a database (e.g., Redis, SQLite, Firestore)
cache = {}
predictions_history = {}  # Stores historical prediction data for charts
user_portfolios = {}  # Stores paper trading data for each user


# --- HTML Serving ---
@app.route('/', methods=['GET'])
def home():
    """Serves the main stock_predictions.html file."""
    return send_from_directory('..', 'stock_predictions.html')


# --- API Endpoints ---
@app.route('/predict/<ticker>', methods=['GET'])
def get_prediction(ticker):
    """
    API endpoint to get a prediction for a single stock ticker.
    Now includes historical prediction data for trend analysis.
    """
    print(f"--- Received request for ticker: {ticker.upper()} ---")
    ticker = ticker.upper()
    provider = request.args.get('provider', 'gpt').lower()

    # Check cache first
    cache_key = f"{ticker}-{provider}"
    cached_item = cache.get(cache_key)
    if cached_item and (time.time() - cached_item['timestamp']) < CACHE_EXPIRATION_SECONDS:
        print(f"Cache HIT for {ticker}.")
        # Return cached data along with history
        cached_item['data']['history'] = list(predictions_history.get(ticker, []))
        return jsonify(cached_item['data'])

    print(f"Cache MISS for {ticker}. Fetching new prediction from provider: {provider}...")
    prompt = build_prompt(ticker, TARGET_DATE)
    results = {}

    # For this example, we'll primarily use GPT-5 as requested in the HTML.
    # The logic for Grok is retained if you wish to switch providers.
    if provider in ('gpt', 'both'):
        try:
            raw, elapsed = call_gpt5(prompt, model=DEFAULT_MODEL_OPENAI, retries=DEFAULT_RETRIES)
            parsed = parse_model_json(raw)
            parsed["_elapsed_seconds"] = elapsed
            results["GPT-5"] = parsed
        except Exception as e:
            print(f"ERROR: GPT-5 call failed for {ticker}: {e}")
            results["GPT-5"] = {"error": "Failed to get prediction from GPT-5.", "raw": str(e)}

    # Store prediction in history
    if "GPT-5" in results and "error" not in results["GPT-5"]:
        if ticker not in predictions_history:
            predictions_history[ticker] = deque(maxlen=20)  # Store last 20 predictions

        history_entry = {
            "timestamp": int(time.time()),
            "current_price": results["GPT-5"].get("current_price"),
            "predicted_price": results["GPT-5"].get("predicted_price")
        }
        predictions_history[ticker].append(history_entry)

    # Build response and update cache
    response_data = {
        "ticker": ticker,
        "target_date": TARGET_DATE,
        "results": results,
        "history": list(predictions_history.get(ticker, []))
    }
    cache[cache_key] = {'timestamp': time.time(), 'data': response_data}
    return jsonify(response_data)


@app.route('/portfolio/<user_id>', methods=['GET'])
def get_portfolio(user_id):
    """Gets the paper trading portfolio for a given user."""
    if user_id not in user_portfolios:
        # Create a new portfolio if one doesn't exist
        user_portfolios[user_id] = {
            "cash": 100000,  # Start with $100,000
            "positions": {}  # e.g., {"TSLA": {"shares": 10, "avg_price": 180.50}}
        }
    return jsonify(user_portfolios[user_id])


@app.route('/trade', methods=['POST'])
def execute_trade():
    """Executes a buy or sell trade for a user."""
    data = request.get_json()
    user_id = data.get('userId')
    ticker = data.get('ticker')
    action = data.get('action')
    shares = int(data.get('shares', 0))
    price = float(data.get('price', 0))

    if not all([user_id, ticker, action, shares > 0, price > 0]):
        return jsonify({"error": "Missing required trade data."}), 400

    # Ensure portfolio exists
    if user_id not in user_portfolios:
        get_portfolio(user_id)  # Creates a default one

    portfolio = user_portfolios[user_id]
    total_cost = shares * price

    if action == 'buy':
        if portfolio['cash'] < total_cost:
            return jsonify({"error": "Not enough cash to complete purchase."}), 400

        portfolio['cash'] -= total_cost

        # Update position
        if ticker in portfolio['positions']:
            pos = portfolio['positions'][ticker]
            new_total_shares = pos['shares'] + shares
            new_total_cost = (pos['shares'] * pos['avg_price']) + total_cost
            pos['avg_price'] = new_total_cost / new_total_shares
            pos['shares'] = new_total_shares
        else:
            portfolio['positions'][ticker] = {"shares": shares, "avg_price": price}

    elif action == 'sell':
        if ticker not in portfolio['positions'] or portfolio['positions'][ticker]['shares'] < shares:
            return jsonify({"error": "Not enough shares to sell."}), 400

        portfolio['cash'] += total_cost

        # Update position
        portfolio['positions'][ticker]['shares'] -= shares
        if portfolio['positions'][ticker]['shares'] == 0:
            del portfolio['positions'][ticker]

    user_portfolios[user_id] = portfolio
    return jsonify(portfolio)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)