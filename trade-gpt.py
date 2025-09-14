# requirements:
#   pip install openai python-dotenv
import os
from datetime import date
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # reads OPENAI_API_KEY from your .env
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

STOCKS_TO_TRACK = [
    "SOFI","GME","ADBE","TSLA","NVDA","GOOGL","AMZN","RCRT","REKR",
    "PERF","PPTA","IMUX","QMMM","UNH","BYNS","PATH","CAT","BLK"
]

target_date = "September 19, 2025"
stocks_str = ", ".join(STOCKS_TO_TRACK)

system = (
    "You are a cautious markets researcher. Use web_search to ground claims, "
    "and output one line per stock as: TICKER — target: $PRICE (Δ PCT%). "
    "Cite 1–3 sources per line inline with bracketed URLs."
)

user = (
    f"For each ticker ({stocks_str}), suggest a plausible **price target** for {target_date}. "
    "Briefly justify with 3–8 words (e.g., 'EPS beat; new guidance'), and include % change vs today. "
    "If coverage is thin, say 'insufficient recent data' and still give your best effort with extra caution."
)

resp = client.responses.create(
    model="gpt-5",
    input=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ],
    tools=[{"type": "web_search"}],   # lets GPT-5 search & cite the web
    reasoning={"effort": "medium"},   # optional; GPT-5 supports reasoning controls
)

# Print the assistant’s final text (citations included by the model)
print(resp.output_text)
