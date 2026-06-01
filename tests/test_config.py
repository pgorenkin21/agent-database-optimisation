"""Config loading smoke tests."""

from pathlib import Path

from src.config import load_config, validate_paths


def test_load_default_mini_dev_config() -> None:
    cfg = load_config()
    assert cfg.bird_split == "mini_dev"
    assert cfg.tasks_json.name == "mini_dev_sqlite.json"
    assert cfg.default_model_key == "gpt-4o-mini"
    assert len(cfg.eval_model_keys) == 3
    assert cfg.seed == 42
    assert cfg.subset_limit == 50


def test_load_full_dev_config() -> None:
    cfg = load_config(Path("configs/full_dev.yaml"))
    assert cfg.bird_split == "full_dev"
    assert cfg.tasks_json.name == "dev.json"


def test_validate_paths_returns_warnings_without_data() -> None:
    cfg = load_config()
    warnings = validate_paths(cfg)
    if not cfg.tasks_json.exists():
        assert any("mini_dev" in w or "download_bird" in w for w in warnings)
