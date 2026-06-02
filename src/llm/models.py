"""Model registry loaded from configs/models.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.config import REPO_ROOT


@dataclass(frozen=True)
class ModelSpec:
    """One LLM entry in the model registry."""

    key: str
    label: str
    provider: str
    api_model: str
    api_key_env: str
    base_url: str | None = None

    def is_openai_compatible(self) -> bool:
        return self.provider in ("openai", "deepseek")


# Deprecated registry keys -> current key (same ModelSpec instance).
_MODEL_ALIASES: dict[str, str] = {
    "gemini-2.0-flash": "gemini-2.5-flash",
}


@dataclass(frozen=True)
class ModelRegistry:
    models: dict[str, ModelSpec]

    def get(self, key: str) -> ModelSpec:
        resolved = _MODEL_ALIASES.get(key, key)
        if resolved not in self.models:
            known = ", ".join(sorted(self.models))
            aliases = ", ".join(f"{a}->{b}" for a, b in sorted(_MODEL_ALIASES.items()))
            hint = f" Aliases: {aliases}." if _MODEL_ALIASES else ""
            raise KeyError(f"Unknown model key {key!r}. Known: {known}.{hint}")
        return self.models[resolved]

    def keys(self) -> list[str]:
        return list(self.models.keys())


def load_model_registry(path: Path | None = None) -> ModelRegistry:
    registry_path = path or (REPO_ROOT / "configs" / "models.yaml")
    with registry_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict) or "models" not in raw:
        raise ValueError(f"Invalid model registry: {registry_path}")

    models: dict[str, ModelSpec] = {}
    for key, spec in raw["models"].items():
        if not isinstance(spec, dict):
            raise ValueError(f"Invalid spec for model {key!r}")
        models[key] = _parse_spec(key, spec)
    return ModelRegistry(models=models)


def _parse_spec(key: str, spec: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        key=key,
        label=str(spec.get("label", key)),
        provider=str(spec["provider"]),
        api_model=str(spec["api_model"]),
        api_key_env=str(spec["api_key_env"]),
        base_url=str(spec["base_url"]) if spec.get("base_url") else None,
    )
