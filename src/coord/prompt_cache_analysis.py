"""Load prompt-cache baseline vs --prompt-cache batch comparison pairs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.llm.cost import estimate_cost_usd
from src.llm.models import ModelSpec, load_model_registry


def _rows_by_qid(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for r in payload.get("rows", []):
        out[int(r["question_id"])] = r
    return out


def _pct_delta(base: float, new: float) -> float | None:
    if base <= 0:
        return None
    return 100.0 * (new - base) / base


def compare_batches(
    baseline: dict[str, Any],
    cached: dict[str, Any],
    *,
    cache_discount: float,
    model_spec: ModelSpec | None = None,
) -> dict[str, Any]:
    """Aggregate over tasks present (and non-errored) in BOTH batches."""
    b_rows = _rows_by_qid(baseline)
    c_rows = _rows_by_qid(cached)
    shared_qids = sorted(set(b_rows) & set(c_rows))

    matched = 0
    b_prompt = b_completion = 0
    c_prompt = c_completion = c_cached = 0
    b_ex = c_ex = 0
    for qid in shared_qids:
        b, c = b_rows[qid], c_rows[qid]
        if b.get("error") or c.get("error"):
            continue
        matched += 1
        b_prompt += int(b.get("total_prompt_tokens", 0))
        b_completion += int(b.get("total_completion_tokens", 0))
        c_prompt += int(c.get("total_prompt_tokens", 0))
        c_completion += int(c.get("total_completion_tokens", 0))
        c_cached += int(c.get("total_cached_prompt_tokens", 0))
        b_ex += int(b.get("ex_correct", 0))
        c_ex += int(c.get("ex_correct", 0))

    c_effective_input = (c_prompt - c_cached) + c_cached * cache_discount
    cached_pct = (100.0 * c_cached / c_prompt) if c_prompt else 0.0
    input_saving_pct = _pct_delta(b_prompt, c_effective_input)
    within_run_saving_pct = (
        100.0 * (c_prompt - c_effective_input) / c_prompt if c_prompt else 0.0
    )

    b_cost = c_cost = cost_saving_pct = None
    if model_spec is not None:
        b_cost = estimate_cost_usd(
            model_spec, prompt_tokens=b_prompt, completion_tokens=b_completion
        )
        c_cost = estimate_cost_usd(
            model_spec,
            prompt_tokens=c_prompt,
            completion_tokens=c_completion,
            cached_prompt_tokens=c_cached,
        )
        if b_cost is not None and c_cost is not None:
            cost_saving_pct = _pct_delta(b_cost, c_cost)

    return {
        "matched_tasks": matched,
        "cache_discount": cache_discount,
        "baseline": {
            "ex_correct": b_ex,
            "ex_pct": round(100.0 * b_ex / matched, 1) if matched else 0.0,
            "prompt_tokens": b_prompt,
            "completion_tokens": b_completion,
            "cost_usd": round(b_cost, 4) if b_cost is not None else None,
        },
        "cached": {
            "ex_correct": c_ex,
            "ex_pct": round(100.0 * c_ex / matched, 1) if matched else 0.0,
            "prompt_tokens": c_prompt,
            "completion_tokens": c_completion,
            "cached_prompt_tokens": c_cached,
            "cached_prompt_pct": round(cached_pct, 1),
            "effective_input_tokens": round(c_effective_input, 1),
            "within_run_input_saving_pct": round(within_run_saving_pct, 1),
            "cost_usd": round(c_cost, 4) if c_cost is not None else None,
        },
        "deltas": {
            "ex_pp": round(
                (100.0 * c_ex / matched) - (100.0 * b_ex / matched), 1
            )
            if matched
            else 0.0,
            "raw_prompt_token_pct": round(_pct_delta(b_prompt, c_prompt) or 0.0, 1),
            "effective_input_token_pct": (
                round(input_saving_pct, 1) if input_saving_pct is not None else None
            ),
            "cost_usd_pct": (
                round(cost_saving_pct, 1) if cost_saving_pct is not None else None
            ),
        },
    }

# Default smoke-50 ablations (batch_id stem → model_key). Prefer N=25 pairs.
DEFAULT_PAIRS: list[tuple[str, str, str]] = [
    ("pc50_r25_base", "pc50_r25_cached", "gpt-4o-mini"),
    ("pc50_r25_gem_base", "pc50_r25_gem_cached", "gemini-2.5-flash"),
    ("pc50_r25_ds_base", "pc50_r25_ds_cached", "deepseek-v3.2"),
]


@dataclass
class PromptCacheComparison:
    model_key: str
    baseline_batch_id: str
    cached_batch_id: str
    baseline_path: Path
    cached_path: Path
    summary: dict[str, Any]
    baseline_meta: dict[str, Any]
    cached_meta: dict[str, Any]


def _find_batch(batch_dir: Path, batch_id: str, model_key: str, *, prompt_cache: bool) -> Path | None:
    suffix = "_promptcache" if prompt_cache else ""
    pattern = f"parallel_{batch_id}_{model_key}_r*_best_of_n{suffix}.json"
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def load_default_comparisons(
    batch_dir: Path,
    *,
    cache_discount: float = 0.5,
    pairs: list[tuple[str, str, str]] | None = None,
) -> list[PromptCacheComparison]:
    registry = load_model_registry()
    batch_dir = batch_dir.resolve()
    out: list[PromptCacheComparison] = []
    for base_id, cache_id, model_key in pairs or DEFAULT_PAIRS:
        base_path = _find_batch(batch_dir, base_id, model_key, prompt_cache=False)
        cache_path = _find_batch(batch_dir, cache_id, model_key, prompt_cache=True)
        if base_path is None or cache_path is None:
            continue
        base_meta = json.loads(base_path.read_text(encoding="utf-8"))
        cache_meta = json.loads(cache_path.read_text(encoding="utf-8"))
        summary = compare_batches(
            base_meta,
            cache_meta,
            cache_discount=cache_discount,
            model_spec=registry.get(model_key),
        )
        if summary["matched_tasks"] == 0:
            continue
        out.append(
            PromptCacheComparison(
                model_key=model_key,
                baseline_batch_id=base_id,
                cached_batch_id=cache_id,
                baseline_path=base_path,
                cached_path=cache_path,
                summary=summary,
                baseline_meta=base_meta,
                cached_meta=cache_meta,
            )
        )
    return out
