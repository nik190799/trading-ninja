import os
import csv
import time
import threading
from datetime import datetime
import schedule
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.search import SearchParameters, x_source

# --- CONFIGURATION ---

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    print("FATAL: XAI_API_KEY not found in .env file.")
    exit()

TARGET_DATE = '2025-09-19'
CSV_FILE = 'predictions.csv'
RUN_INTERVAL_MINUTES = 5
BATCH_SIZE = 10  # Number of assets to process in each API call

# --- HARDCODED ASSET LISTS ---

STOCKS_TO_TRACK = [
    'SOFI', 'GME', 'ADBE', 'TSLA', 'NVDA', 'GOOGL', 'AMZN', 'RCRT', 'REKR',
    'PERF', 'PPTA', 'IMUX', 'QMMM', 'UNH', 'BYNS', 'PATH', 'CAT', 'BLK'
]

CRYPTO_TO_TRACK = [
    {'symbol': 'BTC', 'id': 'bitcoin'}, {'symbol': 'ETH', 'id': 'ethereum'},
    {'symbol': 'SOL', 'id': 'solana'}, {'symbol': 'BNB', 'id': 'binancecoin'},
    {'symbol': 'XRP', 'id': 'ripple'}, {'symbol': 'DOGE', 'id': 'dogecoin'},
    {'symbol': 'TON', 'id': 'the-open-network'}, {'symbol': 'ADA', 'id': 'cardano'},
    {'symbol': 'SHIB', 'id': 'shiba-inu'}, {'symbol': 'AVAX', 'id': 'avalanche-2'},
    {'symbol': 'TRX', 'id': 'tron'}, {'symbol': 'DOT', 'id': 'polkadot'},
    {'symbol': 'LINK', 'id': 'chainlink'}, {'symbol': 'MATIC', 'id': 'matic-network'},
    {'symbol': 'NEAR', 'id': 'near'}, {'symbol': 'LTC', 'id': 'litecoin'},
    {'symbol': 'ICP', 'id': 'internet-computer'}, {'symbol': 'BCH', 'id': 'bitcoin-cash'},
    {'symbol': 'UNI', 'id': 'uniswap'}, {'symbol': 'XLM', 'id': 'stellar'}
]


# --- AI PREDICTION SERVICE ---

def get_predictions_for_batch(assets):
    """Gets predictions from the Grok-4 model for a single batch of assets."""
    if not assets:
        return []

    print(f"Getting predictions for a batch of {len(assets)} assets...")
    client = Client(api_key=XAI_API_KEY)
    asset_list_str = ", ".join(assets)

    prompt = f"""
        Analyze the following financial assets: {asset_list_str}.
        For each asset, provide the current live price and a realistic price target for {TARGET_DATE}.
        The output MUST be in the following format, with each asset on a new line, and nothing else.
        FORMAT: TICKER|CURRENT_PRICE|TARGET_PRICE|PERCENTAGE_CHANGE
    """

    try:
        chat = client.chat.create(model="grok-4", temperature=0.2,
                                  search_parameters=SearchParameters(mode="auto", sources=[x_source()]))
        chat.append(user(prompt))

        print(f"  > Sending prompt for batch: {assets[0]}...")
        response = chat.sample()
        print(f"  < Received response for batch: {assets[0]}.")

        predictions_text = response.content
        parsed_predictions = []
        for line in predictions_text.strip().split('\n'):
            parts = line.strip().split('|')
            if len(parts) == 4:
                try:
                    parsed_predictions.append({
                        'Ticker': parts[0].strip().upper(),
                        'CurrentPrice': float(parts[1]),
                        'TargetPrice': float(parts[2]),
                        'PercentageChange': float(parts[3])
                    })
                except (ValueError, IndexError):
                    print(f"Could not parse line: '{line}'")
        print(f"Successfully parsed {len(parsed_predictions)} predictions for this batch.")
        return parsed_predictions
    except Exception as e:
        print(f"An error occurred with the XAI API for batch {assets[0]}: {e}")
        return []


def run_prediction_cycle():
    """Fetches assets, gets predictions in batches, and saves them."""
    print(f"[{datetime.now()}] --- Starting new prediction cycle ---")

    stock_tickers = STOCKS_TO_TRACK
    crypto_tickers = [item['symbol'] for item in CRYPTO_TO_TRACK]
    all_asset_tickers = stock_tickers + crypto_tickers
    all_predictions = []

    # Process assets in batches
    for i in range(0, len(all_asset_tickers), BATCH_SIZE):
        batch = all_asset_tickers[i:i + BATCH_SIZE]
        print(f"\nProcessing Batch {i // BATCH_SIZE + 1} of {len(all_asset_tickers) // BATCH_SIZE + 1}")
        batch_predictions = get_predictions_for_batch(batch)
        all_predictions.extend(batch_predictions)

        if i + BATCH_SIZE < len(all_asset_tickers):
            print("Waiting 10 seconds before next batch...")
            time.sleep(10)

    if not all_predictions:
        print("No predictions were returned from the model. Cycle ending.")
        return

    timestamp = datetime.now().isoformat()
    crypto_ticker_set = set(crypto_tickers)

    final_data = []
    for p in all_predictions:
        p['Type'] = 'Crypto' if p['Ticker'] in crypto_ticker_set else 'Stock'
        p['PredictionDate'] = timestamp
        p['TargetDate'] = TARGET_DATE
        p['CurrentPriceAtPrediction'] = p.pop('CurrentPrice', None)
        final_data.append(p)

    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, 'a', newline='') as f:
        fieldnames = ['Ticker', 'Type', 'PredictionDate', 'TargetDate', 'TargetPrice', 'PercentageChange',
                      'CurrentPriceAtPrediction']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists or os.path.getsize(CSV_FILE) == 0:
            writer.writeheader()
        writer.writerows(final_data)

    print(f"\n[{datetime.now()}] --- Prediction cycle finished. Saved {len(final_data)} new predictions. ---")


# --- BACKGROUND SCHEDULER ---

def run_scheduler():
    schedule.every(RUN_INTERVAL_MINUTES).minutes.do(run_prediction_cycle)
    while True:
        schedule.run_pending()
        time.sleep(1)


# --- WEB SERVER (FLASK) ---

app = Flask(__name__, template_folder='.')


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/predictions')
def get_prediction_data():
    if not os.path.exists(CSV_FILE):
        return jsonify([])
    try:
        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            predictions = sorted(list(reader), key=lambda x: x['PredictionDate'], reverse=True)
        return jsonify(predictions)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return jsonify({"error": "Could not read data."}), 500


@app.route('/api/discover', methods=['POST'])
def discover_stocks():
    """Endpoint to discover new high-gain stocks using the AI model."""
    print("--- Received request for new stock discovery ---")
    client = Client(api_key=XAI_API_KEY)

    prompt = f"""
        Analyze the current stock market for high-gain opportunities.
        Identify 5 stock tickers that have strong potential for significant growth by {TARGET_DATE}.
        For each stock, provide its current live price, a realistic price target for {TARGET_DATE}, and the percentage change.
        The output MUST be in the following format, with each asset on a new line, and nothing else.
        FORMAT: TICKER|CURRENT_PRICE|TARGET_PRICE|PERCENTAGE_CHANGE
    """

    try:
        chat = client.chat.create(model="grok-4", temperature=0.3,
                                  search_parameters=SearchParameters(mode="auto", sources=[x_source()]))
        chat.append(user(prompt))
        response = chat.sample()

        parsed_suggestions = []
        for line in response.content.strip().split('\n'):
            parts = line.strip().split('|')
            if len(parts) == 4:
                try:
                    parsed_suggestions.append({
                        'Ticker': parts[0].strip().upper(),
                        'CurrentPrice': float(parts[1]),
                        'TargetPrice': float(parts[2]),
                        'PercentageChange': float(parts[3])
                    })
                except (ValueError, IndexError):
                    print(f"Could not parse discovery line: '{line}'")

        print(f"Successfully discovered {len(parsed_suggestions)} new stocks.")
        return jsonify(parsed_suggestions)

    except Exception as e:
        print(f"An error occurred during discovery: {e}")
        return jsonify({"error": "Failed to get suggestions from the model."}), 500


# --- MAIN EXECUTION ---

if __name__ == '__main__':
    if not os.path.isfile(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        print("No data found. Running initial prediction cycle before server starts...")
        run_prediction_cycle()
    else:
        print("Existing data found. Server starting immediately.")

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    print("\n--- Starting Flask Web Server ---")
    print("Your dashboard is running at: http://12.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000)