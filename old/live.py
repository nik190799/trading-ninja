import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup


def get_sp500_tickers():
    """
    Scrapes the list of S&P 500 tickers from the Wikipedia page.
    This version is more robust to handle potential HTML structure changes.
    Returns a list of tickers.
    """
    print("Fetching list of S&P 500 tickers from Wikipedia...")
    try:
        url = 'http://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        soup = BeautifulSoup(response.text, 'html.parser')
        # Target the specific table by its ID for more reliability
        table = soup.find('table', {'id': 'constituents'})

        tickers = []
        # Iterate over all table rows, skipping the header row
        for row in table.findAll('tr')[1:]:
            # Find all data cells in the row
            cells = row.findAll('td')
            # Check if the row has data cells to prevent errors
            if len(cells) > 0:
                ticker = cells[0].text.strip()
                # Replace '.' with '-' for yfinance compatibility (e.g., BRK.B -> BRK-B)
                tickers.append(ticker.replace('.', '-'))

        print(f"Successfully fetched {len(tickers)} S&P 500 tickers.")
        return tickers
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Wikipedia page: {e}")
        return []
    except Exception as e:
        print(f"An error occurred while parsing S&P 500 tickers: {e}")
        return []


def get_crypto_tickers():
    """
    Returns a hardcoded list of top 10 cryptocurrency tickers.
    """
    print("Using hardcoded list for top 10 cryptocurrencies.")
    return [
        'BTC-USD', 'ETH-USD', 'USDT-USD', 'BNB-USD', 'SOL-USD',
        'XRP-USD', 'USDC-USD', 'ADA-USD', 'DOGE-USD', 'AVAX-USD'
    ]


def get_live_values(tickers):
    """
    Fetches the last closing price for a given list of tickers.
    Returns a pandas Series with the data.
    """
    if not tickers:
        print("Ticker list is empty. Cannot fetch data.")
        return pd.Series(dtype=float)

    try:
        print(f"Fetching market data for {len(tickers)} tickers...")
        data = yf.download(tickers, period="1d", progress=True, auto_adjust=True)

        if data.empty:
            print("No data downloaded. Please check the tickers.")
            return pd.Series(dtype=float)

        live_prices = data['Close'].iloc[-1]
        return live_prices.dropna()

    except Exception as e:
        print(f"An error occurred while fetching data with yfinance: {e}")
        return pd.Series(dtype=float)


def save_data_to_file(data, filename):
    """
    Saves the given data to a text file.
    """
    if data.empty:
        print(f"No data to save to {filename}.")
        return

    try:
        with open(filename, 'w') as f:
            f.write(data.to_string())
        print(f"Data successfully saved to {filename}")
    except Exception as e:
        print(f"Error saving data to {filename}: {e}")


if __name__ == "__main__":
    # --- Process S&P 500 Stocks ---
    print("--- Fetching S&P 500 Stock Data ---")
    sp500_tickers = get_sp500_tickers()
    sp500_data = get_live_values(sp500_tickers)
    save_data_to_file(sp500_data, "sp500_prices.txt")

    print("\n" + "=" * 40 + "\n")

    # --- Process Crypto Coins ---
    print("--- Fetching Top 10 Crypto Coin Data ---")
    crypto_tickers = get_crypto_tickers()
    crypto_data = get_live_values(crypto_tickers)
    save_data_to_file(crypto_data, "crypto_prices.txt")

