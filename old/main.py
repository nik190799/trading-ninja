# trade_main.py
import os
import json
import argparse
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from GROK import call_grok4
from GPT import call_gpt5

# ----------------------------
# Defaults / Config
# ----------------------------
DEFAULT_MODEL_XAI = os.getenv("MODEL_XAI", "grok-4")
DEFAULT_MODEL_OPENAI = os.getenv("MODEL_OPENAI", "gpt-5")
DEFAULT_TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
DEFAULT_SEED = int(os.getenv("SEED", "12345"))

# ----------------------------
# Prompt builder (shared)
# ----------------------------
def build_prompt(ticker: str, target_date: str) -> str:
    """
    Build a prompt that requires the model to:
      • Determine whether the ticker is a STOCK or CRYPTO asset.
      • Fetch the current live price (with currency and timestamp) via web research/tools.
      • Return a single, most-likely predicted price for target_date and concise reasoning.
      • Output ONLY one clean JSON object with the exact schema below.
    """
    today = date.today().isoformat()
    return f"""
You are a markets researcher. The user provides a single ticker that may be either a STOCK (e.g., TSLA) or a CRYPTO asset (e.g., BTC, ETH).

1) Determine the asset type (exactly "stock" or "crypto").
2) Fetch the current live price **yourself** using reliable sources. Include currency (e.g., "USD") and an ISO 8601 timestamp for when that price is valid.
3) Provide a single, most-likely predicted price for {target_date}.
4) Provide a concise, single-paragraph reason summarizing the key drivers behind your prediction.

Ticker: {ticker}
Today: {today}

STRICT OUTPUT RULES — return ONLY one JSON object with this exact schema (no extra text):
{{
  "ticker": "{ticker}",
  "asset_type": "stock" | "crypto",
  "current_price": <number>,              // current live price you found
  "price_currency": "<ISO code, e.g., USD>",
  "price_timestamp": "<ISO8601 datetime>", // when that current price was observed
  "target_date": "{target_date}",
  "predicted_price": <number>,
  "reasoning": "<single paragraph>"
}}
""".strip()

# ----------------------------
# Utilities
# ----------------------------
def parse_model_json(raw: str) -> Dict[str, Any]:
    """
    Strictly parse a single JSON object from model output.
    If the model wrapped JSON in text, try to extract the first JSON object.
    """
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        return json.loads(raw)

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = raw[start : end + 1]
        return json.loads(snippet)

    raise json.JSONDecodeError("No valid JSON object found", raw, 0)

def format_currency(val) -> str:
    try:
        return f"${float(val):.2f}"
    except Exception:
        return str(val)

def print_result_block(title: str, data: Dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    if "error" in data:
        print("Status: ERROR (see raw response below)")
    print(f"Ticker: {data.get('ticker', 'N/A')}")
    atype = data.get("asset_type")
    if atype:
        print(f"Asset Type: {atype}")
    cp = data.get("current_price")
    curr = data.get("price_currency") or "USD"
    ts = data.get("price_timestamp")
    if cp is not None:
        print(f"Current Price: {format_currency(cp)} {f'({curr})' if curr else ''}{f' @ {ts}' if ts else ''}")
    print(f"Predicted Price for {data.get('target_date', 'N/A')}: {format_currency(data.get('predicted_price'))}")
    print(f"Reason: {data.get('reasoning', 'N/A')}")
    elapsed = data.get("_elapsed_seconds")
    if elapsed is not None:
        print(f"Elapsed (s): {elapsed:.3f}")
    if "raw" in data:
        print("\n--- Raw Response ---")
        print(data.get("raw", ""))
        print("--------------------")

def print_comparison_table(a_name: str, a: Dict[str, Any], b_name: str, b: Dict[str, Any]) -> None:
    def safe(v): return v if v is not None else "N/A"
    rows = [
        ("Ticker", safe(a.get("ticker")), safe(b.get("ticker"))),
        ("Asset Type", safe(a.get("asset_type")), safe(b.get("asset_type"))),
        ("Current Price", f"{format_currency(a.get('current_price'))} {a.get('price_currency', '')}".strip(),
                           f"{format_currency(b.get('current_price'))} {b.get('price_currency', '')}".strip()),
        ("Price Timestamp", safe(a.get("price_timestamp")), safe(b.get("price_timestamp"))),
        ("Target Date", safe(a.get("target_date")), safe(b.get("target_date"))),
        ("Predicted Price", format_currency(a.get('predicted_price')), format_currency(b.get('predicted_price'))),
        ("Elapsed (s)", f"{a.get('_elapsed_seconds', float('nan')):.3f}" if isinstance(a.get('_elapsed_seconds'), (int, float)) else "N/A",
                         f"{b.get('_elapsed_seconds', float('nan')):.3f}" if isinstance(b.get('_elapsed_seconds'), (int, float)) else "N/A"),
    ]
    col1 = max(len(r[0]) for r in rows) + 2
    col2 = max(len(str(r[1])) for r in rows) + 2
    print("\n--- Side-by-side Comparison ---")
    print(f"{'Field'.ljust(col1)}{a_name.ljust(col2)}{b_name}")
    print("-" * (col1 + col2 + max(12, len(b_name))))
    for field, a_val, b_val in rows:
        print(f"{field.ljust(col1)}{str(a_val).ljust(col2)}{b_val}")
    print("")

# ----------------------------
# Main
# ----------------------------
def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Predict a stock or crypto price using Grok-4 (xAI), GPT-5 (OpenAI), or both, with timing.")
    parser.add_argument("--provider", choices=["xai", "openai", "both"], default="both")
    parser.add_argument("--ticker", default=os.getenv("TICKER", "TSLA"))
    parser.add_argument("--target-date", default=os.getenv("TARGET_DATE", "2025-09-19"))
    # temperature used only for Grok-4
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--model-xai", default=DEFAULT_MODEL_XAI)
    parser.add_argument("--model-openai", default=DEFAULT_MODEL_OPENAI)
    parser.add_argument("--retries", type=int, default=int(os.getenv("RETRIES", "2")))
    parser.add_argument("--json", action="store_true", help="Print a single JSON object (including elapsed seconds) to stdout.")
    args = parser.parse_args()

    prompt = build_prompt(args.ticker, args.target_date)

    results: Dict[str, Dict[str, Any]] = {}
    overall_start = time.perf_counter()

    if args.provider in ("xai", "both"):
        raw, elapsed = call_grok4(
            prompt,
            model=args.model_xai,
            temperature=args.temperature,
            seed=args.seed,
            retries=args.retries,
        )
        try:
            parsed = parse_model_json(raw)
            parsed["_elapsed_seconds"] = elapsed
            results["Grok-4"] = parsed
        except json.JSONDecodeError:
            results["Grok-4"] = {"error": "JSON parse failed", "_elapsed_seconds": elapsed, "raw": raw}

    if args.provider in ("openai", "both"):
        raw, elapsed = call_gpt5(prompt, model=args.model_openai, retries=args.retries)
        try:
            parsed = parse_model_json(raw)
            parsed["_elapsed_seconds"] = elapsed
            results["GPT-5"] = parsed
        except json.JSONDecodeError:
            results["GPT-5"] = {"error": "JSON parse failed", "_elapsed_seconds": elapsed, "raw": raw}

    overall_elapsed = time.perf_counter() - overall_start

    # Output
    if args.json:
        out: Dict[str, Any] = {
            "provider": args.provider,
            "ticker": args.ticker,
            "target_date": args.target_date,
            "overall_elapsed_seconds": round(overall_elapsed, 3),
            "results": results,
        }
        for v in out["results"].values():
            if isinstance(v.get("_elapsed_seconds"), (int, float)):
                v["_elapsed_seconds"] = round(float(v["_elapsed_seconds"]), 3)
        print(json.dumps(out, ensure_ascii=False))
        return

    # Human-friendly console output
    if args.provider == "both" and "Grok-4" in results and "GPT-5" in results:
        a = results.get("Grok-4", {})
        b = results.get("GPT-5", {})
        if "error" not in a and "error" not in b:
            print_comparison_table("Grok-4", a, "GPT-5", b)
        print_result_block("Grok-4 Result", a)
        print_result_block("GPT-5 Result", b)
    else:
        for name, data in results.items():
            print_result_block(name, data)

    print(f"\nTotal runtime (s): {overall_elapsed:.3f}")

if __name__ == "__main__":
    main()
