"""
Talking to the language model.

Deliberately thin, and deliberately written against the OpenAI
/v1/chat/completions shape rather than any vendor SDK. Ollama, Groq, OpenAI,
LM Studio and vLLM all speak it, so switching provider is three environment
variables and no code:

    LLM_BASE_URL=http://ollama:11434/v1     LLM_MODEL=qwen2.5:1.5b
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_BASE_URL=https://api.openai.com/v1

That matters here because the local 1.5B model is the weakest link: if it keeps
choosing the wrong tool, pointing the same code at a bigger model tells you
immediately whether the bug is yours or the model's.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

BASE_URL = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1").rstrip("/")
MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
API_KEY = os.getenv("LLM_API_KEY", "not-needed")

# CPU inference is slow and shares two cores with YOLO. nginx allows 180s on
# /ai/, so stay under that or the browser gives up before we do.
TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))


class LLMError(Exception):
    """The model could not be reached or refused the request."""


def chat(messages: list, tools: list = None) -> dict:
    """One round trip. Returns the assistant message dict."""
    payload = {
        "model": MODEL,
        "messages": messages,
        # Near-zero: this job is picking a tool and reporting numbers, not
        # writing prose. Creativity here shows up as invented data.
        "temperature": 0.1,
    }
    if tools:
        payload["tools"] = tools

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=TIMEOUT,
        )
    except requests.Timeout:
        raise LLMError(f"the model took longer than {TIMEOUT}s - it is running on CPU")
    except requests.RequestException as exc:
        raise LLMError(f"cannot reach the model at {BASE_URL}: {exc}")

    if response.status_code == 404:
        # By far the most common first-run failure: the server is up but the
        # weights were never pulled into it.
        raise LLMError(
            f"model '{MODEL}' is not available at this endpoint. Check "
            f"LLM_MODEL, and if the endpoint is a local runtime make sure the "
            f"weights have been pulled into it.")
    if response.status_code == 429:
        # Groq's free tier is 8k tokens/minute. One question costs roughly
        # 2k (schemas + system prompt + tool results), so three in quick
        # succession trip it. Say that, rather than leaking the raw error.
        retry = response.headers.get("retry-after", "a few")
        raise LLMError(
            f"rate limit reached on {MODEL}. Hosted endpoints cap tokens per "
            f"minute, and one question costs roughly 2k - wait {retry} seconds "
            f"and ask again.")
    if response.status_code in (401, 403):
        raise LLMError("the API key was rejected. Check LLM_API_KEY in .setup/.env")
    if not response.ok:
        raise LLMError(f"model returned {response.status_code}: {response.text[:200]}")

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise LLMError("model returned no choices")
    return choices[0]["message"]


def health() -> dict:
    """Is the runtime up, and is the configured model actually present?"""
    try:
        # The header matters: Ollama ignores it, every hosted provider returns
        # 401 without it. Omitting it here made a working key look invalid.
        response = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=5,
        )
        response.raise_for_status()
        names = [m.get("id", "") for m in response.json().get("data", [])]
    except requests.RequestException as exc:
        return {"reachable": False, "model": MODEL, "error": str(exc)[:200]}

    # Some endpoints report the bare name, others append a suffix.
    present = any(n == MODEL or n.startswith(MODEL) for n in names)
    return {
        "reachable": True,
        "model": MODEL,
        "modelPulled": present,
        "available": names[:10],
        "hint": None if present else ("model not present at this endpoint - "
                                      "check LLM_MODEL, or pull the weights if "
                                      "the endpoint is a local runtime"),
    }
