# gpt5_call.py
import os
import time

def call_gpt5(prompt: str, model: str = "gpt-5", retries: int = 2):
    """
    Uses OpenAI Responses API with optional web_search tool.
    Returns (raw_text_output, elapsed_seconds).
    NOTE: Do NOT pass temperature — unsupported for GPT-5 Responses API.
    Env: OPENAI_API_KEY
    """
    last_err = None
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("openai package is not installed. `pip install openai>=1.40.0`") from e

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)

    sys_msg = (
        "You are a markets researcher. You may use web_search to ground facts. "
        "Return ONLY one JSON object per the schema in the user's instructions."
    )

    start = time.perf_counter()
    try:
        for _ in range(max(1, retries + 1)):
            try:
                resp = client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": prompt},
                    ],
                    tools=[{"type": "web_search"}],
                    reasoning={"effort": "medium"},
                )
                elapsed = time.perf_counter() - start
                # Best path for SDKs >= 1.40
                if hasattr(resp, "output_text"):
                    return resp.output_text, elapsed
                # Fallback parsing (covers older/alt response shapes)
                data = getattr(resp, "output", None)
                if data:
                    parts = []
                    for item in data:
                        if getattr(item, "type", None) == "message":
                            for c in getattr(item, "content", []) or []:
                                if getattr(c, "type", None) == "output_text":
                                    parts.append(getattr(c, "text", ""))
                    if parts:
                        return "\n".join(parts), elapsed
                return str(resp), elapsed
            except Exception as e:
                last_err = e
        raise RuntimeError(f"GPT-5 call failed after retries. Last error: {last_err}")
    finally:
        pass
