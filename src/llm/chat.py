"""Chat completions with tool calling (OpenAI-compatible + Gemini)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.agent.tools import TOOL_DEFINITIONS_OPENAI
from src.llm.client import create_chat_client
from src.llm.models import ModelSpec
from src.llm.retry import RetryConfig, call_with_retry


@dataclass
class ToolCallRequest:
    id: str | None
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    assistant_message: dict[str, Any]
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    text: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _parse_json_args(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _log_api_retry(attempt: int, exc: BaseException, wait: float) -> None:
    print(
        f"  LLM retry {attempt} in {wait:.1f}s ({type(exc).__name__}: {exc})",
        flush=True,
    )


class OpenAIChatBackend:
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

    def complete(self, messages: list[dict[str, Any]]) -> ChatResponse:
        return call_with_retry(
            lambda: self._complete_once(messages),
            self._retry,
            on_retry=_log_api_retry,
        )

    def _complete_once(self, messages: list[dict[str, Any]]) -> ChatResponse:
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
        return ChatResponse(
            assistant_message=assistant_msg,
            tool_calls=tool_calls,
            text=choice.content,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )


def _gemini_sql_parameters_schema(types: Any) -> Any:
    """Object schema { sql: string } for Gemini FunctionDeclaration.parameters."""
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "sql": types.Schema(
                type=types.Type.STRING,
                description="SQLite SELECT query.",
            ),
        },
        required=["sql"],
    )


def build_gemini_function_declarations(types: Any) -> list[Any]:
    """Tool declarations for google-genai (uses Schema, not JSON-schema dict)."""
    sql_params = _gemini_sql_parameters_schema(types)
    return [
        types.FunctionDeclaration(
            name="execute_sql",
            description=(
                "Execute a read-only SQL query (SELECT or WITH) on the task database. "
                "Use for exploration; results are returned as text."
            ),
            parameters=sql_params,
        ),
        types.FunctionDeclaration(
            name="submit_sql",
            description=(
                "Submit the final SQL query that answers the user's question. "
                "Call this when you are confident in the answer."
            ),
            parameters=sql_params,
        ),
    ]


class GeminiChatBackend:
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

    def complete(self, messages: list[dict[str, Any]]) -> ChatResponse:
        return call_with_retry(
            lambda: self._complete_once(messages),
            self._retry,
            on_retry=_log_api_retry,
        )

    def _complete_once(self, messages: list[dict[str, Any]]) -> ChatResponse:
        types = self._types
        contents = self._to_contents(messages)
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
        completion_tokens = getattr(usage, "candidates_token_count", None) if usage else None

        return ChatResponse(
            assistant_message=assistant_msg,
            tool_calls=tool_calls,
            text=assistant_msg.get("content"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def create_chat_backend(
    spec: ModelSpec,
    *,
    retry: RetryConfig | None = None,
    request_timeout_seconds: float | None = None,
    temperature: float = 0.0,
) -> OpenAIChatBackend | GeminiChatBackend:
    backend_kwargs: dict[str, RetryConfig | float] = {"temperature": temperature}
    if retry is not None:
        backend_kwargs["retry"] = retry
    if request_timeout_seconds is not None:
        backend_kwargs["request_timeout_seconds"] = request_timeout_seconds
    if spec.provider == "google":
        return GeminiChatBackend(spec, **backend_kwargs)
    if spec.is_openai_compatible():
        return OpenAIChatBackend(spec, **backend_kwargs)
    raise ValueError(f"Unsupported provider: {spec.provider}")
