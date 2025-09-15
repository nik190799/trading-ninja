# trade.py
import os
import json
from datetime import date
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.search import SearchParameters, x_source, web_source, news_source

# ----------------------------
# Config
# ----------------------------
MODEL_NAME = "grok-4"
TEMPERATURE = 0.2
SEED = 12345

TICKER = "TSLA"
CURRENT_PRICE = 396  # Update if needed
TARGET_DATE = "2025-09-19"  # YYYY-MM-DD


# ----------------------------
# Prompt builder
# ----------------------------
def build_prompt(ticker: str, current_price: float, target_date: str) -> str:
    """
    Build a prompt to get a single price prediction and reasoning.
    The model is asked to:
      • Perform research on the ticker.
      • Return a single, most-likely predicted price.
      • Provide a concise reason for the prediction.
      • Return a clean JSON object with the results.
    """
    today = date.today().isoformat()

    prompt = f"""
Analyze the stock ticker: {ticker}.
The current price as of {today} is ${current_price:.2f}.

Your task is to do all the necessary research and provide a single predicted target price for the date {target_date}.
This prediction should be your most likely scenario (i.e., your base case).
Alongside the prediction, provide a concise, single-paragraph reason for the predicted change, summarizing the key drivers you found during your research.

Constraints & Output rules:
- Return ONLY a single JSON object.
- Do not add any text before or after the JSON block.
- The JSON object must follow this exact schema:
{{
  "ticker": "{ticker}",
  "current_price": {current_price},
  "target_date": "{target_date}",
  "predicted_price": "<number>",
  "reasoning": "<string: a single paragraph summarizing your research>"
}}
"""
    return prompt


# ----------------------------
# Client init
# ----------------------------
def make_client() -> Client:
    load_dotenv()
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "XAI_API_KEY is not set. Create a .env with XAI_API_KEY=... or export it in your environment."
        )
    return Client(api_key=api_key)


# ----------------------------
# Chat call with retry
# ----------------------------
def call_model(client: Client, prompt: str, retries: int = 2) -> str:
    last_err = None
    for _ in range(max(1, retries + 1)):
        try:
            chat = client.chat.create(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                seed=SEED,
                search_parameters=SearchParameters(
                    mode="on",
                    sources=[x_source(), news_source(), web_source()],
                ),
            )
            chat.append(user(prompt))
            response = chat.sample()
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Model call failed after retries. Last error: {last_err}")


# ----------------------------
# Main
# ----------------------------
def main():
    client = make_client()
    prompt = build_prompt(TICKER, CURRENT_PRICE, TARGET_DATE)

    print("Fetching analysis, please wait...")
    raw_response = call_model(client, prompt, retries=2)

    try:
        # The model should return a clean JSON string, which we can parse
        data = json.loads(raw_response)

        # Print the results in the user-requested format
        print("\n--- Stock Price Prediction ---")
        print(f"Ticker Name: {data.get('ticker', 'N/A')}")

        # Safely format currency values
        current_price_val = data.get('current_price')
        predicted_price_val = data.get('predicted_price')

        current_price_str = f"${current_price_val:.2f}" if isinstance(current_price_val, (int, float)) else "N/A"
        predicted_price_str = f"${predicted_price_val:.2f}" if isinstance(predicted_price_val, (int, float)) else "N/A"

        print(f"Current Price: {current_price_str}")
        print(f"Predicted Price for {data.get('target_date', 'N/A')}: {predicted_price_str}")
        print(f"Reason for Predicted Changes: {data.get('reasoning', 'No reasoning provided.')}")
        print("----------------------------\n")

    except json.JSONDecodeError:
        print("\n(Error) Failed to parse the model's response as JSON.")
        print("This can happen if the model's output is not perfectly formatted.")
        print("\n--- Raw Response from Model ---")
        print(raw_response)
        print("---------------------------------")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("\n--- Raw Response from Model ---")
        print(raw_response)
        print("---------------------------------")


if __name__ == "__main__":
    main()
