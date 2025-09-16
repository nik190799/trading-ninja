# grok4_call.py
import os
import time
from typing import Tuple

def call_grok4(
    prompt: str,
    model: str = "grok-4",
    temperature: float = 0.2,
    seed: int = 12345,
    retries: int = 2,
) -> Tuple[str, float]:
    """
    Calls Grok-4 with search enabled.
    Returns (raw_content_string, elapsed_seconds).
    Env: XAI_API_KEY
    """
    last_err = None
    try:
        from xai_sdk import Client
        from xai_sdk.chat import user
        from xai_sdk.search import SearchParameters, x_source, web_source, news_source
    except Exception as e:
        raise RuntimeError("xai-sdk is not installed. `pip install xai-sdk>=0.3.0`") from e

    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("XAI_API_KEY is not set")

    client = Client(api_key=api_key)

    start = time.perf_counter()
    try:
        for _ in range(max(1, retries + 1)):
            try:
                chat = client.chat.create(
                    model=model,
                    temperature=temperature,
                    seed=seed,
                    search_parameters=SearchParameters(
                        mode="on",
                        sources=[x_source(), news_source(), web_source()],
                    ),
                )
                chat.append(user(prompt))
                response = chat.sample()
                elapsed = time.perf_counter() - start
                return (response.content if hasattr(response, "content") else str(response), elapsed)
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Grok-4 call failed after retries. Last error: {last_err}")
    finally:
        pass
