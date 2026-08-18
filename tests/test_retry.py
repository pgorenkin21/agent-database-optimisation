"""LLM retry helper tests."""

import pytest
from httpx import ReadTimeout
from openai import APITimeoutError

from google.genai import errors as genai_errors

from src.llm.retry import (
    QuotaExhausted,
    RetryConfig,
    call_with_retry,
    is_retryable_error,
    retry_delay_seconds,
)


def test_is_retryable_503_message() -> None:
    exc = Exception("503 UNAVAILABLE. high demand")
    assert is_retryable_error(exc)


def test_is_retryable_gemini_server_error() -> None:
    exc = genai_errors.ServerError(503, {"error": {"status": "UNAVAILABLE"}})
    assert is_retryable_error(exc)


def test_not_retryable_validation() -> None:
    assert not is_retryable_error(ValueError("bad sql"))


def test_is_retryable_api_timeout() -> None:
    assert is_retryable_error(APITimeoutError(request=None))
    assert is_retryable_error(ReadTimeout("read timed out"))


def test_call_with_retry_succeeds_after_timeout() -> None:
    attempts = {"n": 0}

    def fn() -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise APITimeoutError(request=None)
        return "ok"

    config = RetryConfig(max_attempts=4, base_delay_seconds=0.01, max_delay_seconds=0.05)
    assert call_with_retry(fn, config) == "ok"
    assert attempts["n"] == 2


def test_call_with_retry_succeeds_after_transient() -> None:
    attempts = {"n": 0}

    def fn() -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise Exception("503 UNAVAILABLE")
        return "ok"

    config = RetryConfig(max_attempts=4, base_delay_seconds=0.01, max_delay_seconds=0.05)
    assert call_with_retry(fn, config) == "ok"
    assert attempts["n"] == 2


def test_call_with_retry_raises_non_retryable() -> None:
    def fail() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        call_with_retry(fail, RetryConfig())


def test_retry_delay_bounded() -> None:
    config = RetryConfig(base_delay_seconds=2, max_delay_seconds=10)
    assert retry_delay_seconds(10, config) <= 10


def test_billing_cap_429_is_not_retryable() -> None:
    """The 17 Aug 2026 Gemini rejection: a 429 that retrying cannot clear."""
    msg = (
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Your billing "
        "account has exceeded its monthly spending cap.', 'status': "
        "'RESOURCE_EXHAUSTED'}}"
    )
    assert not is_retryable_error(Exception(msg))


def test_ordinary_429_is_still_retryable() -> None:
    assert is_retryable_error(Exception("429 rate limit exceeded, slow down"))


def test_call_with_retry_raises_quota_exhausted_without_retrying() -> None:
    attempts = {"n": 0}

    def fn() -> str:
        attempts["n"] += 1
        raise Exception("429 billing account has exceeded its monthly spending cap")

    config = RetryConfig(max_attempts=6, base_delay_seconds=0.01, max_delay_seconds=0.05)
    with pytest.raises(QuotaExhausted):
        call_with_retry(fn, config)
    assert attempts["n"] == 1, "must fail on the first call, not retry"


def test_call_with_retry_honours_total_time_budget() -> None:
    attempts = {"n": 0}

    def fn() -> str:
        attempts["n"] += 1
        raise APITimeoutError(request=None)

    # 20 attempts would normally run; the 0.05s budget cuts it far shorter.
    config = RetryConfig(
        max_attempts=20,
        base_delay_seconds=0.02,
        max_delay_seconds=0.05,
        max_total_seconds=0.05,
    )
    with pytest.raises(APITimeoutError):
        call_with_retry(fn, config)
    assert attempts["n"] < 20, f"time budget ignored, made {attempts['n']} attempts"
