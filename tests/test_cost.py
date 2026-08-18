"""Tests for src/llm/cost.py cost estimation."""

from src.llm.cost import estimate_cost_usd
from src.llm.models import ModelSpec, load_model_registry


def _spec(**overrides: object) -> ModelSpec:
    base = dict(
        key="test-model",
        label="Test Model",
        provider="openai",
        api_model="test-model",
        api_key_env="TEST_API_KEY",
        price_per_1m_input=1.0,
        price_per_1m_output=2.0,
        price_per_1m_cached_input=0.5,
    )
    base.update(overrides)
    return ModelSpec(**base)  # type: ignore[arg-type]


def test_cost_with_no_cache() -> None:
    spec = _spec()
    cost = estimate_cost_usd(spec, prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == 1.0 + 2.0


def test_cost_with_cached_tokens_billed_at_cached_rate() -> None:
    spec = _spec()
    cost = estimate_cost_usd(
        spec,
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_prompt_tokens=1_000_000,
    )
    assert cost == 0.5


def test_cost_splits_cached_and_uncached_prompt_tokens() -> None:
    spec = _spec()
    cost = estimate_cost_usd(
        spec,
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_prompt_tokens=400_000,
    )
    # 600k uncached @ $1/1M + 400k cached @ $0.5/1M
    assert cost == 0.6 * 1.0 + 0.4 * 0.5


def test_cost_falls_back_to_input_rate_when_no_cached_price() -> None:
    spec = _spec(price_per_1m_cached_input=None)
    cost = estimate_cost_usd(
        spec,
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_prompt_tokens=1_000_000,
    )
    assert cost == 1.0


def test_cost_none_when_model_has_no_price() -> None:
    spec = _spec(price_per_1m_input=None, price_per_1m_output=None)
    cost = estimate_cost_usd(spec, prompt_tokens=100, completion_tokens=100)
    assert cost is None


def test_cost_handles_none_token_counts() -> None:
    spec = _spec()
    cost = estimate_cost_usd(spec, prompt_tokens=None, completion_tokens=None)
    assert cost == 0.0


def test_registry_models_have_prices() -> None:
    reg = load_model_registry()
    for key in ("gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2"):
        spec = reg.get(key)
        assert spec.price_per_1m_input is not None
        assert spec.price_per_1m_output is not None
