#!/usr/bin/env python3
"""Verify Phase 0 setup: deps, config, paths, API keys for all configured models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.config import load_config, validate_paths
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config file (default: configs/default.yaml)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    env_path = cfg.repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    registry = load_model_registry(cfg.models_config_path)

    print("BIRD agent coordination - Phase 0 setup check\n")
    print(f"  BIRD split:        {cfg.bird_split}")
    print(f"  Tasks JSON:        {cfg.tasks_json}")
    print(f"  Default model:     {cfg.default_model_key}")
    print(f"  Eval models:       {', '.join(cfg.eval_model_keys)}")
    print(f"  Temperature:       {cfg.llm_temperature}")
    print(f"  Subset limit:      {cfg.subset_limit}")
    print(f"  Budget (USD):      {cfg.budget_usd}")
    print()

    exit_code = 0
    try:
        import duckdb  # noqa: F401
        import openai  # noqa: F401
        import yaml  # noqa: F401

        print("  Dependencies:      OK (duckdb, openai, pyyaml)")
    except ImportError as e:
        print(f"  Dependencies:      FAIL - {e}")
        print("  Run: uv sync --all-groups")
        return 1

    try:
        import google.genai  # noqa: F401

        print("  Gemini SDK:        OK (google-genai)")
    except ImportError:
        print("  Gemini SDK:        missing - run uv sync --all-groups")
        exit_code = 1

    warnings = validate_paths(cfg)
    if warnings:
        print("  BIRD data:")
        for w in warnings:
            print(f"    WARN: {w}")
    else:
        print("  BIRD data:         OK")
        n = len(json.loads(cfg.tasks_json.read_text(encoding="utf-8")))
        print(f"    ({n} tasks)")

    print("  Model API keys:")
    for key in cfg.eval_model_keys:
        try:
            spec = registry.get(key)
        except KeyError as e:
            print(f"    FAIL {key}: {e}")
            exit_code = 1
            continue
        ok, msg = api_key_status(spec)
        api_id = spec.api_model
        status = "OK" if ok else "MISSING"
        print(f"    {status:7} {key:20} ({spec.provider}, {api_id}) - {msg}")
        if not ok:
            exit_code = 1

    cfg.runs_dir.mkdir(parents=True, exist_ok=True)
    print("\nPhase 0 scaffold OK." if exit_code == 0 else "\nFix missing API keys in .env")
    if cfg.bird_split == "mini_dev":
        print("Next: ./scripts/download_bird.sh")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
