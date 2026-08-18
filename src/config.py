"""Load and validate project configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProjectConfig:
    """Typed view of configs/default.yaml (or configs/full_dev.yaml)."""

    raw: dict[str, Any]
    repo_root: Path

    @property
    def seed(self) -> int:
        return int(self.raw["project"]["seed"])

    @property
    def bird_split(self) -> str:
        return str(self.raw["bird"].get("split", "mini_dev"))

    @property
    def bird_root(self) -> Path:
        return self.repo_root / self.raw["bird"]["root"]

    @property
    def tasks_json(self) -> Path:
        return self.repo_root / self.raw["bird"]["tasks_json"]

    @property
    def dev_json(self) -> Path:
        """Alias for tasks_json (legacy name)."""
        return self.tasks_json

    @property
    def databases_dir(self) -> Path:
        return self.repo_root / self.raw["bird"]["databases_dir"]

    @property
    def subset_file(self) -> Path | None:
        rel = self.raw["bird"].get("subset_file") or ""
        if not str(rel).strip():
            return None
        path = self.repo_root / rel
        return path if path.exists() and path.stat().st_size > 0 else None

    @property
    def subset_limit(self) -> int:
        return int(self.raw["bird"].get("subset_limit", 0))

    @property
    def use_evidence(self) -> bool:
        return bool(self.raw.get("use_evidence", True))

    @property
    def models_config_path(self) -> Path:
        rel = self.raw["llm"].get("models_config", "configs/models.yaml")
        return self.repo_root / rel

    @property
    def default_model_key(self) -> str:
        llm = self.raw["llm"]
        return str(llm.get("default") or llm.get("model", "gpt-4o-mini"))

    @property
    def llm_model(self) -> str:
        """Default model registry key (alias for default_model_key)."""
        return self.default_model_key

    @property
    def eval_model_keys(self) -> list[str]:
        llm = self.raw["llm"]
        models = llm.get("eval_models")
        if models:
            return [str(m) for m in models]
        return [self.default_model_key]

    @property
    def llm_temperature(self) -> float:
        return float(self.raw["llm"]["temperature"])

    @property
    def max_turns(self) -> int:
        return int(self.raw["llm"]["max_turns"])

    @property
    def budget_usd(self) -> float:
        return float(self.raw["llm"]["budget_usd"])

    @property
    def llm_retry_max_attempts(self) -> int:
        return int(self.raw["llm"].get("retry_max_attempts", 6))

    @property
    def llm_retry_base_delay_seconds(self) -> float:
        return float(self.raw["llm"].get("retry_base_delay_seconds", 2.0))

    @property
    def llm_retry_max_delay_seconds(self) -> float:
        return float(self.raw["llm"].get("retry_max_delay_seconds", 60.0))

    @property
    def batch_inter_task_delay_seconds(self) -> float:
        return float(self.raw["llm"].get("batch_inter_task_delay_seconds", 0.0))

    @property
    def llm_request_timeout_seconds(self) -> float:
        return float(self.raw["llm"].get("request_timeout_seconds", 120.0))

    def llm_retry_config(self) -> "RetryConfig":
        from src.llm.retry import RetryConfig

        return RetryConfig(
            max_attempts=self.llm_retry_max_attempts,
            base_delay_seconds=self.llm_retry_base_delay_seconds,
            max_delay_seconds=self.llm_retry_max_delay_seconds,
        )

    @property
    def schema_pruning(self) -> bool:
        return bool(self.raw.get("schema_pruning", False))

    @property
    def schema_pruning_mode(self) -> str:
        return str(self.raw.get("schema_pruning_mode", "keyword"))

    @property
    def schema_pruning_semantic_min_score(self) -> float:
        return float(self.raw.get("schema_pruning_semantic_min_score", 0.05))

    @property
    def db_profile(self) -> bool:
        return bool(self.raw.get("db_profile", False))

    @property
    def profiles_dir(self) -> Path:
        return self.repo_root / self.raw.get("profiles_dir", "data/profiles")

    @property
    def db_profile_char_budget(self) -> int:
        return int(self.raw.get("db_profile_char_budget", 1500))

    @property
    def explore_suppressor(self) -> bool:
        return bool(self.raw.get("explore_suppressor", False))

    @property
    def explore_suppressor_max_suppressions(self) -> int:
        return int(self.raw.get("explore_suppressor_max_suppressions", 64))

    @property
    def semantic_store_config(self) -> dict[str, Any]:
        raw = self.raw.get("semantic_store", {})
        return raw if isinstance(raw, dict) else {}

    @property
    def runs_dir(self) -> Path:
        return self.repo_root / self.raw["logging"]["runs_dir"]

    @property
    def read_only_sql(self) -> bool:
        return bool(self.raw["database"]["read_only"])

    @property
    def query_timeout_seconds(self) -> int:
        return int(self.raw["database"]["query_timeout_seconds"])


def load_config(path: Path | None = None) -> ProjectConfig:
    config_path = path or (REPO_ROOT / "configs" / "default.yaml")
    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected mapping in {config_path}")
    return ProjectConfig(raw=raw, repo_root=REPO_ROOT)


def validate_paths(cfg: ProjectConfig) -> list[str]:
    """Return human-readable warnings for missing paths (non-fatal during Phase 0)."""
    warnings: list[str] = []
    if not cfg.tasks_json.exists():
        script = (
            "scripts/download_bird.sh"
            if cfg.bird_split == "mini_dev"
            else "scripts/download_bird_full_dev.sh"
        )
        warnings.append(f"BIRD tasks JSON not found: {cfg.tasks_json} - run {script}")
    if not cfg.databases_dir.exists():
        warnings.append(f"BIRD databases dir not found: {cfg.databases_dir}")
    rel = cfg.raw["bird"].get("subset_file") or ""
    if str(rel).strip() and cfg.subset_file is None:
        warnings.append(f"Subset file configured but missing/empty: {cfg.repo_root / rel}")
    return warnings
