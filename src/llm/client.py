"""Create provider clients and check API keys."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from src.llm.models import ModelSpec

# google-genai is optional until first Gemini call; imported lazily in create_chat_client


def resolve_api_key(spec: ModelSpec) -> str | None:
    """Return API key from environment, or None if unset."""
    value = os.environ.get(spec.api_key_env, "").strip()
    if value:
        return value
    if spec.provider == "google":
        # Google SDK also accepts GOOGLE_API_KEY
        value = os.environ.get("GOOGLE_API_KEY", "").strip()
        if value:
            return value
    return None


def api_key_status(spec: ModelSpec) -> tuple[bool, str]:
    key = resolve_api_key(spec)
    if not key:
        return False, f"{spec.api_key_env} not set"
    if spec.provider == "openai" and not key.startswith("sk-"):
        return True, f"{spec.api_key_env} set (non-sk prefix)"
    return True, f"{spec.api_key_env} set"


def create_openai_client(spec: ModelSpec) -> OpenAI:
    api_key = resolve_api_key(spec)
    if not api_key:
        raise RuntimeError(f"Missing API key: set {spec.api_key_env} in .env")
    kwargs: dict[str, Any] = {"api_key": api_key}
    if spec.base_url:
        kwargs["base_url"] = spec.base_url
    return OpenAI(**kwargs)


def create_gemini_client(spec: ModelSpec) -> Any:
    api_key = resolve_api_key(spec)
    if not api_key:
        raise RuntimeError(
            f"Missing API key: set {spec.api_key_env} or GOOGLE_API_KEY in .env"
        )
    from google import genai

    return genai.Client(api_key=api_key)


def create_chat_client(spec: ModelSpec) -> OpenAI | Any:
    """Return a provider client (OpenAI SDK for openai/deepseek, google.genai for Gemini)."""
    if spec.provider == "google":
        return create_gemini_client(spec)
    if spec.is_openai_compatible():
        return create_openai_client(spec)
    raise ValueError(f"Unsupported provider: {spec.provider}")
