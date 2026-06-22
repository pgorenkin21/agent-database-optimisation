"""LLM retry helper tests."""

import pytest
from httpx import ReadTimeout
from openai import APITimeoutError

from google.genai import errors as genai_errors

from src.llm.retry import RetryConfig, call_with_retry, is_retryable_error, retry_delay_seconds


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
