"""USD cost estimation from token counts, using per-model prices in the registry."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from src.llm.models import ModelSpec, load_model_registry


@lru_cache(maxsize=1)
def _default_registry():
    return load_model_registry()


def estimate_cost_usd(
    spec: ModelSpec,
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cached_prompt_tokens: int | None = None,
) -> float | None:
    """Cost in USD for one turn/run, or None if the model has no listed price.

    ``cached_prompt_tokens`` is counted at the cached rate and subtracted from
    the uncached portion of ``prompt_tokens`` (it does not double the input
    count); if the model has no cached-input price, cached tokens are billed
    at the standard input rate.
    """
    if spec.price_per_1m_input is None or spec.price_per_1m_output is None:
        return None

    prompt = prompt_tokens or 0
    completion = completion_tokens or 0
    cached = cached_prompt_tokens or 0
    uncached = max(prompt - cached, 0)

    cached_rate = spec.price_per_1m_cached_input
    if cached_rate is None:
        cached_rate = spec.price_per_1m_input

    return (
        uncached * spec.price_per_1m_input
        + cached * cached_rate
        + completion * spec.price_per_1m_output
    ) / 1_000_000


def batch_cost_usd(rows: Iterable[dict[str, Any]], model_key: str) -> float | None:
    """Sum cost across rows carrying ``total_prompt_tokens`` / ``total_completion_tokens``
    / ``total_cached_prompt_tokens`` keys (batch summaries, per-task metrics, ...).

    Returns None if ``model_key`` is unknown or unpriced, rather than reporting $0.
    """
    if not model_key:
        return None
    try:
        spec = _default_registry().get(model_key)
    except KeyError:
        return None
    total = 0.0
    for r in rows:
        cost = estimate_cost_usd(
            spec,
            prompt_tokens=r.get("total_prompt_tokens", 0),
            completion_tokens=r.get("total_completion_tokens", 0),
            cached_prompt_tokens=r.get("total_cached_prompt_tokens", 0),
        )
        if cost is None:
            return None
        total += cost
    return round(total, 4)
