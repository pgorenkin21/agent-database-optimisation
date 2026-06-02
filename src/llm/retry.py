"""Retry transient LLM API failures (503, 429, rate limits)."""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
# Standalone HTTP status codes (word-bounded so e.g. an id "15031" never matches).
_RETRYABLE_STATUS_RE = re.compile(r"\b(?:408|429|500|502|503|504)\b")
# Provider-specific overload/rate-limit phrases (matched case-insensitively).
_RETRYABLE_PHRASES = (
    "UNAVAILABLE",
    "high demand",
    "rate limit",
    "temporarily unavailable",
    "overloaded",
)


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 6
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0


def _status_from_exception(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
    return None


def is_retryable_message(text: str) -> bool:
    """True if an error *message* names a transient status code or overload phrase."""
    if _RETRYABLE_STATUS_RE.search(text):
        return True
    upper = text.upper()
    return any(phrase.upper() in upper for phrase in _RETRYABLE_PHRASES)


def is_retryable_error(exc: BaseException) -> bool:
    """True for transient provider errors worth backing off and retrying."""
    status = _status_from_exception(exc)
    if status is not None and status in _RETRYABLE_STATUS:
        return True

    name = type(exc).__name__
    if name in ("APIStatusError", "RateLimitError", "InternalServerError", "APIConnectionError"):
        if status is None or status in _RETRYABLE_STATUS:
            return True

    if name in ("ServerError", "APIError"):
        if status is None or status in _RETRYABLE_STATUS:
            return True

    return is_retryable_message(str(exc))


def retry_delay_seconds(attempt: int, config: RetryConfig) -> float:
    """Exponential backoff with jitter (attempt is 0-based after a failure).

    max_delay_seconds is a hard ceiling: jitter is applied first, then clamped.
    """
    delay = config.base_delay_seconds * (2**attempt) * (0.5 + random.random())
    return min(delay, config.max_delay_seconds)


def call_with_retry(
    fn: Callable[[], T],
    config: RetryConfig,
    *,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    """Call fn(); retry on transient errors until max_attempts is exhausted."""
    last_exc: BaseException | None = None
    for attempt in range(config.max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= config.max_attempts - 1 or not is_retryable_error(exc):
                raise
            wait = retry_delay_seconds(attempt, config)
            if on_retry:
                on_retry(attempt + 1, exc, wait)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc
