"""
Thin Gemini wrapper: structured JSON output, retry/backoff, and a model fallback chain.

Free-tier quotas are per model and per day, so when one model's daily quota is spent
we move on to the next model instead of sleeping for an hour.
"""

import logging
import random
import re
import threading
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from signalscout.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None
_client_lock = threading.Lock()
_exhausted: set[str] = set()  # models whose daily quota is spent (this process)


class LLMUnavailable(RuntimeError):
    pass


class RateLimiter:
    """Shared across worker threads: space requests to stay under the per-minute quota
    instead of hammering the API and burning retries."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / max(1, per_minute)
        self.next_at = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_at)
            self.next_at = slot + self.interval
        time.sleep(max(0.0, slot - now))


_limiter = RateLimiter(get_settings().llm_requests_per_minute)


def client() -> genai.Client:
    # Locked: worker threads racing here would each build a client, and the losers get
    # garbage-collected (and closed) while their requests are still in flight.
    global _client
    with _client_lock:
        if _client is None:
            key = get_settings().gemini_api_key
            if not key:
                raise LLMUnavailable("GEMINI_API_KEY is not set (backend/.env)")
            _client = genai.Client(api_key=key)
    return _client


def models() -> list[str]:
    s = get_settings()
    chain = [s.gemini_model] + [m.strip() for m in s.gemini_fallback_models.split(",") if m.strip()]
    return [m for m in dict.fromkeys(chain) if m not in _exhausted]


def _is_daily_quota(e: errors.APIError) -> bool:
    text = str(e.details) + str(e.message)
    if "PerDay" in text:
        return True
    delay = re.search(r"retryDelay['\"]?:\s*['\"](\d+)s", text)
    return bool(delay and int(delay.group(1)) > 120)


def _config(model: str, schema, system: str | None) -> types.GenerateContentConfig:
    kwargs = {}
    if "lite" not in model:
        # Extraction is reading comprehension, not reasoning: low thinking ~3x fewer tokens
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
    return types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.1,
        **kwargs,
    )


def generate_json(prompt: str, schema: type[T], *, system: str | None = None, retries: int = 3) -> T:
    while True:
        chain = models()
        if not chain:
            raise LLMUnavailable("Daily quota exhausted on every configured Gemini model")
        model = chain[0]
        for attempt in range(retries + 1):
            _limiter.wait()
            try:
                resp = client().models.generate_content(
                    model=model, contents=prompt, config=_config(model, schema, system)
                )
                if resp.parsed is not None:
                    return resp.parsed
                return schema.model_validate_json(resp.text)
            except errors.APIError as e:
                if e.code == 429 and _is_daily_quota(e):
                    if model not in _exhausted:
                        log.warning("Gemini daily quota spent on %s, falling back", model)
                    _exhausted.add(model)
                    break  # next model in the chain
                if e.code == 404:
                    log.warning("Gemini model %s unavailable, falling back", model)
                    _exhausted.add(model)
                    break
                if e.code not in (429, 500, 503) or attempt == retries:
                    raise
                hinted = re.search(r"retry in ([\d.]+)s", str(e.message))  # server tells us how long
                wait = (float(hinted.group(1)) if hinted else min(30, 2 ** attempt * 3)) + random.random() * 2
                log.warning("Gemini %s on %s, retrying in %.0fs", e.code, model, wait)
                time.sleep(wait)
