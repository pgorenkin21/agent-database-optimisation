"""Trace with cached-input-token attribution.

New-file version that extends ``RunTrace`` with a per-turn ``cached_prompt_tokens``
field. The base ``RunTrace`` is left unchanged; the run-end total is carried via
the existing ``finish(extra=...)`` channel, so only the per-turn ``llm_turn``
event needs an override.
"""

from __future__ import annotations

from src.logging.trace import RunTrace


class CachedRunTrace(RunTrace):
    """RunTrace that records cached input tokens on each ``llm_turn`` event."""

    def log_llm_turn(  # type: ignore[override]
        self,
        *,
        turn_idx: int,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        tool_calls: list[str],
        cached_prompt_tokens: int | None = None,
    ) -> None:
        self._append(
            {
                "event": "llm_turn",
                "run_id": self.run_id,
                "turn_idx": turn_idx,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cached_prompt_tokens": cached_prompt_tokens,
                "tool_calls": tool_calls,
            }
        )
