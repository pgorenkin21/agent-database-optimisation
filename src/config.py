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
