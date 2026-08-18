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
    "timed out",
    "timeout",
)
_RETRYABLE_EXCEPTION_NAMES = frozenset(
    {
        "APITimeoutError",
        "APIConnectionError",
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "WriteTimeout",
        "PoolTimeout",
    }
)

# A 429 normally means "too fast, back off" and is worth retrying. A 429 that
# names a billing ceiling means "this account is done until a human acts", and
# retrying it can never succeed. On 17 Aug 2026 a Gemini run spent ~65 minutes
# and 1,069 rejections retrying the latter, producing 27 task failures and
# collapsing throughput from 7 to 1.9 tasks/min. These phrases make that class
# of 429 fail immediately instead.
_FATAL_PHRASES = (
    "spending cap",
    "spend cap",
    "billing account",
    "billing account has exceeded",
)


class QuotaExhausted(RuntimeError):
    """A provider quota rejection that retrying cannot clear."""


def is_fatal_quota_message(text: str) -> bool:
    """True if a rejection names a billing ceiling rather than a rate limit."""
    upper = text.upper()
    return any(phrase.upper() in upper for phrase in _FATAL_PHRASES)


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 6
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0
    # Ceiling on time spent retrying ONE request. Without it, 6 attempts at
    # 2s base and a 60s cap can burn ~2 minutes on a single call; with 10
    # replicas per task that is what stalled the 17 Aug run.
    max_total_seconds: float = 90.0


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
    name = type(exc).__name__

    # Checked before anything else: a billing-ceiling rejection also carries a
    # 429 and the word "quota", so every other rule below would call it
    # retryable.
    if is_fatal_quota_message(str(exc)):
        return False

    if name in _RETRYABLE_EXCEPTION_NAMES:
        return True

    status = _status_from_exception(exc)
    if status is not None and status in _RETRYABLE_STATUS:
        return True

    if name in ("APIStatusError", "RateLimitError", "InternalServerError"):
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
    """Call fn(); retry transient errors until attempts or the time budget run out.

    Stops early on a billing-ceiling rejection (see QuotaExhausted) and once
    max_total_seconds of wall clock has been spent on this one request, so a
    single call cannot stall a batch indefinitely.
    """
    last_exc: BaseException | None = None
    started = time.monotonic()
    for attempt in range(config.max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if is_fatal_quota_message(str(exc)):
                raise QuotaExhausted(
                    f"provider quota rejection is not retryable: {exc}"
                ) from exc
            if attempt >= config.max_attempts - 1 or not is_retryable_error(exc):
                raise
            wait = retry_delay_seconds(attempt, config)
            elapsed = time.monotonic() - started
            if elapsed + wait > config.max_total_seconds:
                raise
            if on_retry:
                on_retry(attempt + 1, exc, wait)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc
