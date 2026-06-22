"""LLM client factory tests."""

from unittest.mock import MagicMock, patch

from httpx import Timeout

from src.llm.client import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    create_gemini_client,
    create_openai_client,
)
from src.llm.models import ModelSpec


def _openai_spec() -> ModelSpec:
    return ModelSpec(
        key="gpt-4o-mini",
        label="GPT-4o mini",
        provider="openai",
        api_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )


@patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
@patch("src.llm.client.OpenAI")
def test_create_openai_client_sets_timeout_and_disables_sdk_retries(
    mock_openai: MagicMock,
) -> None:
    create_openai_client(_openai_spec(), request_timeout_seconds=90.0)
    mock_openai.assert_called_once()
    kwargs = mock_openai.call_args.kwargs
    assert kwargs["max_retries"] == 0
    timeout = kwargs["timeout"]
    assert isinstance(timeout, Timeout)
    assert timeout.read == 90.0


@patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
@patch("google.genai.Client")
def test_create_gemini_client_sets_http_timeout_ms(mock_client: MagicMock) -> None:
    create_gemini_client(
        ModelSpec(
            key="gemini-2.5-flash",
            label="Gemini 2.5 Flash",
            provider="google",
            api_model="gemini-2.5-flash",
            api_key_env="GEMINI_API_KEY",
        ),
        request_timeout_seconds=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
    mock_client.assert_called_once()
    http_options = mock_client.call_args.kwargs["http_options"]
    assert http_options.timeout == 120_000
