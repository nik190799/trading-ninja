# trade-gpt.py
# ---------------------------------------------------------
# Uses GPT-5 + web_search to emit strict rows:
#   ticker, current_price, expected_price_on_given_date, reasons
#
# Features
#  - Few-shot examples (system + user) to lock format
#  - Strict validation (regex) + corrective re-prompt (auto-retry)
#  - Saves clean CSV
#  - Prints ESTIMATED API COST (tokens) for the whole run
#
# Pricing used (per 1M tokens):
#   Input:        $1.25
#   Cached input: $0.125
#   Output:       $10.00
#
# NOTE: Tool-specific fees (e.g., web_search) may apply separately.
#       If you know a per-call fee, set WEB_SEARCH_FEE_USD to include it.
#
# Setup:
#   pip install "openai>=1.40.0" "httpx>=0.27.0" python-dotenv
#   Set OPENAI_API_KEY in env or .env
# Run:
#   python trade-gpt.py
# ---------------------------------------------------------

import os
import re
import csv
from datetime import date
from typing import Dict, Tuple, List, Any
from dotenv import load_dotenv
from openai import OpenAI

# ------------ Config ------------

STOCKS_TO_TRACK = [
    "SOFI","GME","ADBE","TSLA","NVDA","GOOGL","AMZN","RCRT","REKR",
    "PERF","PPTA","IMUX","QMMM","UNH","PATH","CAT","BLK"
]

TARGET_DATE_STR = "September 19, 2025"
MAX_RETRIES = 2
OUTFILE = f"predictions_{date.today().isoformat()}.csv"

# Pricing (per 1M tokens)
INPUT_RATE = 1.25
CACHED_INPUT_RATE = 0.125
OUTPUT_RATE = 10.00

# Optional: include a flat per-call fee for web_search (if known).
# e.g., set WEB_SEARCH_FEE_USD=0.002 in your environment.
WEB_SEARCH_FEE_USD = float(os.getenv("WEB_SEARCH_FEE_USD", "0") or 0)

# ------------ Helpers ------------

ROW_RE = re.compile(
    r'^\s*([A-Z]{1,5})\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*(.+?)\s*$'
)

def _to_dict(maybe_obj: Any) -> dict:
    """Best-effort convert Pydantic/SDK models to plain dicts."""
    if maybe_obj is None:
        return {}
    if isinstance(maybe_obj, dict):
        return maybe_obj
    # Pydantic v2 models
    if hasattr(maybe_obj, "model_dump"):
        try:
            return maybe_obj.model_dump()
        except Exception:
            pass
    # Lists / tuples
    if isinstance(maybe_obj, (list, tuple)):
        return {"_items": [ _to_dict(x) for x in maybe_obj ]}
    # Fallback for objects with __dict__
    try:
        return dict(getattr(maybe_obj, "__dict__", {}) or {})
    except Exception:
        return {}

def estimate_cost_from_usage(usage_obj) -> float:
    """
    Estimate token cost in USD from a Responses API usage object/dict.

    Pricing (per 1M tokens):
      - Input:        $1.25
      - Cached input: $0.125
      - Output:       $10.00
    """
    usage = _to_dict(usage_obj)

    input_tokens  = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)

    # Cached tokens can be present in different fields depending on SDK version
    cached_tokens = int(usage.get("cached_tokens", 0) or 0)
    itd = _to_dict(usage.get("input_token_details", {}))
    cached_tokens += int(itd.get("cached_tokens", 0) or 0)
    # If you want finer granularity, you could optionally include:
    # cached_tokens += int(itd.get("cache_read_tokens", 0) or 0)
    # cached_tokens += int(itd.get("cache_creation_tokens", 0) or 0)

    cost = (
        input_tokens  * (INPUT_RATE       / 1_000_000.0) +
        cached_tokens * (CACHED_INPUT_RATE / 1_000_000.0) +
        output_tokens * (OUTPUT_RATE      / 1_000_000.0)
    )
    return float(cost)

def count_web_search_calls(resp) -> int:
    """
    Best-effort count of web_search tool calls from a Responses object.
    Treat as approximate — SDKs may differ in how tool calls are surfaced.
    """
    rd = _to_dict(resp)
    count = 0

    # Try a flat 'output' list
    output = rd.get("output")
    if output is None and "_items" in rd:
        output = rd["_items"]
    if isinstance(output, list):
        for item in output:
            d = _to_dict(item)
            if (d.get("type") in ("tool_use", "tool_call")) and d.get("name") == "web_search":
                count += 1

    # Also try nested messages->content
    messages = rd.get("messages") or []
    for msg in messages:
        md = _to_dict(msg)
        for part in md.get("content", []) or []:
            pd = _to_dict(part)
            if (pd.get("type") in ("tool_use", "tool_call")) and pd.get("name") == "web_search":
                count += 1

    return count

def parse_rows(text: str, expected_tickers: List[str]) -> Tuple[Dict[str, Tuple[float, float, str]], List[str]]:
    ok_rows: Dict[str, Tuple[float, float, str]] = {}
    errors: List[str] = []
    seen = set()

    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        errors.append("No lines returned.")
        return ok_rows, errors

    for line in lines:
        m = ROW_RE.match(line)
        if not m:
            errors.append(f"Invalid line: {line!r}")
            continue
        tkr, cur_s, exp_s, reasons = m.groups()
        try:
            cur = float(cur_s)
            exp = float(exp_s)
        except ValueError:
            errors.append(f"Non-numeric price: {line!r}")
            continue
        ok_rows[tkr] = (cur, exp, reasons.strip())
        seen.add(tkr)

    missing = [t for t in expected_tickers if t not in seen]
    if missing:
        errors.append("Missing tickers: " + ", ".join(missing))

    unexpected = [t for t in ok_rows.keys() if t not in expected_tickers]
    if unexpected:
        errors.append("Unexpected tickers: " + ", ".join(unexpected))

    return ok_rows, errors

def rows_to_csv(rows: Dict[str, Tuple[float, float, str]], outfile: str) -> None:
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker","current_price","expected_price_on_given_date","reasons"])
        for t in STOCKS_TO_TRACK:
            if t in rows:
                cur, exp, reason = rows[t]
                w.writerow([t, f"{cur:.2f}", f"{exp:.2f}", reason])

# ------------ Prompts ------------

def build_system_prompt() -> str:
    return (
        "You are a markets researcher. You may use web_search to ground facts.\n"
        "Your FINAL answer must be ONLY rows in this format:\n"
        "ticker, current_price, expected_price_on_given_date, reasons\n\n"
        "STRICT RULES:\n"
        "- One line per ticker (no extras).\n"
        "- Ticker: uppercase letters only.\n"
        "- Prices: plain numbers (e.g., 255.12). No $ sign, no commas, no %.\n"
        "- Reasons: 5–12 words, concise, no leading punctuation.\n"
        "- No markdown, no headers, no explanations, no citations, no URLs.\n\n"
        "### Format Examples (values illustrative only):\n"
        "TSLA, 255.12, 310.45, EV demand growth and margin expansion\n"
        "NVDA, 452.30, 525.60, AI chip demand boosts revenue pipeline\n"
        "GOOGL, 132.88, 140.50, Cloud contracts offset antitrust risk\n"
        "AMZN, 135.22, 148.00, AWS growth and advertising strength\n"
        "MSFT, 332.15, 345.70, AI services drive productivity software"
    )

def build_user_prompt(tickers: List[str], target_date: str) -> str:
    stocks_str = ", ".join(tickers)
    return (
        f"For each ticker ({stocks_str}), determine today's current price, "
        f"then estimate the expected price on {target_date}.\n\n"
        "Output ONLY rows in the format shown below. Do not add commentary.\n\n"
        "### Example rows (values are placeholders):\n"
        "AAPL, 189.23, 200.10, iPhone refresh cycle and services growth\n"
        "NFLX, 440.55, 465.30, ad tier expansion boosts global subscribers\n"
        "META, 302.88, 325.00, strong AR/VR momentum with ad recovery\n"
        "INTC, 33.15, 36.70, new chip launches and cost reductions\n"
        "ORCL, 119.75, 122.50, cloud database adoption drives revenues"
    )

def build_correction_prompt(errors: List[str], remaining_tickers: List[str], target_date: str) -> str:
    stocks_str = ", ".join(remaining_tickers)
    reasons = "\n".join(f"- {e}" for e in errors)
    return (
        "Your previous output was invalid.\n"
        "Issues to fix:\n"
        f"{reasons}\n\n"
        "Re-emit ONLY valid rows for these tickers:\n"
        f"{stocks_str}\n\n"
        "### Example rows (values are placeholders):\n"
        "TSLA, 255.12, 310.45, EV demand growth and margin expansion\n"
        "NVDA, 452.30, 525.60, AI chip demand boosts revenue pipeline\n"
        "GOOGL, 132.88, 140.50, Cloud contracts offset antitrust risk\n"
        f"Use {target_date} as the expected date."
    )

# ------------ Main ------------

def main():
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    system = build_system_prompt()
    user = build_user_prompt(STOCKS_TO_TRACK, TARGET_DATE_STR)

    total_cost_usd = 0.0
    total_web_search_calls = 0

    # First call
    resp = client.responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        tools=[{"type": "web_search"}],
        reasoning={"effort": "medium"},
    )

    # Estimate cost for first call
    call_cost = estimate_cost_from_usage(getattr(resp, "usage", None))
    web_calls = count_web_search_calls(resp)
    total_cost_usd += call_cost + (web_calls * WEB_SEARCH_FEE_USD)
    total_web_search_calls += web_calls

    text = resp.output_text
    parsed, errs = parse_rows(text, STOCKS_TO_TRACK)

    # Corrective retries
    retries = 0
    while errs and retries < MAX_RETRIES:
        missing = [t for t in STOCKS_TO_TRACK if t not in parsed]
        correction_user = build_correction_prompt(errs, missing, TARGET_DATE_STR)

        resp = client.responses.create(
            model="gpt-5",
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": correction_user},
            ],
            tools=[{"type": "web_search"}],
            reasoning={"effort": "medium"},
        )

        # Cost for this retry
        call_cost = estimate_cost_from_usage(getattr(resp, "usage", None))
        web_calls = count_web_search_calls(resp)
        total_cost_usd += call_cost + (web_calls * WEB_SEARCH_FEE_USD)
        total_web_search_calls += web_calls

        add_text = resp.output_text
        add_parsed, _ = parse_rows(add_text, missing)

        # Merge valid additions
        for t, vals in add_parsed.items():
            parsed[t] = vals

        # Re-validate full set by synthesizing the merged rows
        synth_text = "\n".join(
            f"{t},{parsed[t][0]},{parsed[t][1]},{parsed[t][2]}" for t in parsed
        )
        _, errs = parse_rows(synth_text, STOCKS_TO_TRACK)

        retries += 1

    # Print results
    if errs:
        print("Model output could not be fully validated. Errors:")
        for e in errs:
            print(" -", e)
    else:
        print("All rows validated successfully:")

    for t in STOCKS_TO_TRACK:
        if t in parsed:
            cur, exp, reason = parsed[t]
            print(f"{t}, {cur:.2f}, {exp:.2f}, {reason}")
        else:
            print(f"{t}, , , ")

    # Save CSV
    if parsed:
        rows_to_csv(parsed, OUTFILE)
        print(f"\nSaved {len(parsed)} row(s) to {OUTFILE}")

    # Cost summary
    print("\n=== Cost Estimate ===")
    print(f"Total web_search calls (approx.): {total_web_search_calls}")
    if WEB_SEARCH_FEE_USD:
        print(f"Included web_search fee: ${WEB_SEARCH_FEE_USD:.4f} per call")
    else:
        print("No per-call web_search fee included (set WEB_SEARCH_FEE_USD to add).")

    print(f"Estimated token cost: ${total_cost_usd:.6f} (input/cached/output tokens only)")

if __name__ == "__main__":
    main()
