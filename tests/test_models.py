"""Model registry and config tests."""

from pathlib import Path

import pytest

from src.config import load_config
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def test_registry_has_three_eval_models() -> None:
    reg = load_model_registry()
    assert set(reg.keys()) >= {"gpt-4o-mini", "gemini-2.0-flash", "deepseek-v3.2"}


def test_deepseek_maps_to_chat_api_model() -> None:
    spec = load_model_registry().get("deepseek-v3.2")
    assert spec.provider == "deepseek"
    assert spec.api_model == "deepseek-chat"
    assert spec.base_url == "https://api.deepseek.com"


def test_default_config_eval_models() -> None:
    cfg = load_config()
    assert cfg.default_model_key == "gpt-4o-mini"
    assert cfg.eval_model_keys == [
        "gpt-4o-mini",
        "gemini-2.0-flash",
        "deepseek-v3.2",
    ]


def test_api_key_status_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = load_model_registry().get("gpt-4o-mini")
    monkeypatch.delenv(spec.api_key_env, raising=False)
    ok, _ = api_key_status(spec)
    assert ok is False


def test_full_dev_config_uses_same_models() -> None:
    cfg = load_config(Path("configs/full_dev.yaml"))
    assert "gemini-2.0-flash" in cfg.eval_model_keys
