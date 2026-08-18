"""Cache-aware chat backends.

New-file version of ``src/llm/chat.py`` that additionally reads provider
prompt-cache usage (cached input tokens) so the prompt-caching win is
measurable. Behaviourally identical request-side; only usage parsing differs,
plus a hook for explicit cache markers (Claude/Gemini explicit caching).

The originals in ``chat.py`` are left untouched as the P0 baseline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.agent.tools import TOOL_DEFINITIONS_OPENAI
from src.llm.chat import (
    ToolCallRequest,
    _log_api_retry,
    _parse_json_args,
    build_gemini_function_declarations,
)
from src.llm.client import create_chat_client
from src.llm.models import ModelSpec
from src.llm.retry import RetryConfig, call_with_retry


@dataclass
class CachedChatResponse:
    """Like ``ChatResponse`` but carries ``cached_prompt_tokens``."""

    assistant_message: dict[str, Any]
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    text: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_prompt_tokens: int | None = None


def _openai_cached_tokens(usage: Any) -> int | None:
    """Read cached input tokens across OpenAI- and DeepSeek-style usage objects."""
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        if cached is not None:
            return int(cached)
    # DeepSeek (OpenAI-compatible) reports a differently named field.
    cached = getattr(usage, "prompt_cache_hit_tokens", None)
    return int(cached) if cached is not None else None


class OpenAIChatBackendCached:
    def __init__(
        self,
        spec: ModelSpec,
        *,
        retry: RetryConfig | None = None,
        request_timeout_seconds: float | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.spec = spec
        self._temperature = temperature
        client_kwargs: dict[str, float] = {}
        if request_timeout_seconds is not None:
            client_kwargs["request_timeout_seconds"] = request_timeout_seconds
        self.client = create_chat_client(spec, **client_kwargs)
        self._retry = retry or RetryConfig(max_attempts=1)

    def complete(self, messages: list[dict[str, Any]]) -> CachedChatResponse:
        return call_with_retry(
            lambda: self._complete_once(messages),
            self._retry,
            on_retry=_log_api_retry,
        )

    def _complete_once(self, messages: list[dict[str, Any]]) -> CachedChatResponse:
        # OpenAI / DeepSeek auto-cache stable prefixes >~1024 tokens with no
        # request-side marker, so the win comes from a byte-stable, append-only
        # prompt (see loop_cached / prompt_cached), not from anything set here.
        response = self.client.chat.completions.create(
            model=self.spec.api_model,
            messages=messages,
            tools=TOOL_DEFINITIONS_OPENAI,
            tool_choice="auto",
            temperature=self._temperature,
        )
        choice = response.choices[0].message
        tool_calls: list[ToolCallRequest] = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=_parse_json_args(tc.function.arguments),
                    )
                )

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": choice.content,
        }
        if choice.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.tool_calls
            ]

        usage = response.usage
        return CachedChatResponse(
            assistant_message=assistant_msg,
            tool_calls=tool_calls,
            text=choice.content,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            cached_prompt_tokens=_openai_cached_tokens(usage),
        )


class GeminiChatBackendCached:
    def __init__(
        self,
        spec: ModelSpec,
        *,
        retry: RetryConfig | None = None,
        request_timeout_seconds: float | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.spec = spec
        self._temperature = temperature
        client_kwargs: dict[str, float] = {}
        if request_timeout_seconds is not None:
            client_kwargs["request_timeout_seconds"] = request_timeout_seconds
        self.client = create_chat_client(spec, **client_kwargs)
        from google.genai import types

        self._types = types
        self._declarations = build_gemini_function_declarations(types)
        self._tools = [types.Tool(function_declarations=self._declarations)]
        self._retry = retry or RetryConfig(max_attempts=1)

    def _to_contents(self, messages: list[dict[str, Any]]) -> list[Any]:
        types = self._types
        contents: list[Any] = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=f"[System]\n{msg['content']}")],
                    )
                )
            elif role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=msg["content"])])
                )
            elif role == "assistant":
                parts: list[Any] = []
                if msg.get("content"):
                    parts.append(types.Part(text=msg["content"]))
                for tc in msg.get("tool_calls") or []:
                    fn = tc["function"]
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=fn["name"],
                                args=_parse_json_args(fn.get("arguments")),
                            )
                        )
                    )
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=msg.get("name", "execute_sql"),
                                    response={"result": msg["content"]},
                                )
                            )
                        ],
                    )
                )
        return contents

    def complete(self, messages: list[dict[str, Any]]) -> CachedChatResponse:
        return call_with_retry(
            lambda: self._complete_once(messages),
            self._retry,
            on_retry=_log_api_retry,
        )

    def _complete_once(self, messages: list[dict[str, Any]]) -> CachedChatResponse:
        types = self._types
        contents = self._to_contents(messages)
        # Gemini implicit-caches a stable prefix automatically. Explicit
        # `cachedContent` (created once per (db_id, model)) would go in the
        # config here for the largest schemas; omitted to avoid extra state.
        response = self.client.models.generate_content(
            model=self.spec.api_model,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=self._tools,
                temperature=self._temperature,
            ),
        )

        tool_calls: list[ToolCallRequest] = []
        text_parts: list[str] = []
        candidate = response.candidates[0] if response.candidates else None
        if candidate and candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        ToolCallRequest(
                            id=None,
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        )
                    )

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": "\n".join(text_parts) if text_parts else None,
        }
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": f"gemini_{i}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for i, tc in enumerate(tool_calls)
            ]

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        completion_tokens = (
            getattr(usage, "candidates_token_count", None) if usage else None
        )
        cached = (
            getattr(usage, "cached_content_token_count", None) if usage else None
        )

        return CachedChatResponse(
            assistant_message=assistant_msg,
            tool_calls=tool_calls,
            text=assistant_msg.get("content"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=int(cached) if cached is not None else None,
        )


def create_chat_backend_cached(
    spec: ModelSpec,
    *,
    retry: RetryConfig | None = None,
    request_timeout_seconds: float | None = None,
    temperature: float = 0.0,
) -> OpenAIChatBackendCached | GeminiChatBackendCached:
    backend_kwargs: dict[str, RetryConfig | float] = {"temperature": temperature}
    if retry is not None:
        backend_kwargs["retry"] = retry
    if request_timeout_seconds is not None:
        backend_kwargs["request_timeout_seconds"] = request_timeout_seconds
    if spec.provider == "google":
        return GeminiChatBackendCached(spec, **backend_kwargs)
    if spec.is_openai_compatible():
        return OpenAIChatBackendCached(spec, **backend_kwargs)
    raise ValueError(f"Unsupported provider: {spec.provider}")
