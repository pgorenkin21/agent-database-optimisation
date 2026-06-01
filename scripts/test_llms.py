#!/usr/bin/env python3
"""Smoke-test configured LLMs with a minimal prompt (requires .env API keys)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.config import load_config
from src.llm.client import api_key_status, create_chat_client
from src.llm.models import ModelSpec, load_model_registry

PROMPT = "Reply with exactly one word: OK"


def smoke_openai_compatible(client, spec: ModelSpec) -> tuple[str, int]:
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=spec.api_model,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=16,
        temperature=0,
    )
    ms = int((time.perf_counter() - start) * 1000)
    text = (response.choices[0].message.content or "").strip()
    return text, ms


def smoke_gemini(client, spec: ModelSpec) -> tuple[str, int]:
    start = time.perf_counter()
    response = client.models.generate_content(
        model=spec.api_model,
        contents=PROMPT,
    )
    ms = int((time.perf_counter() - start) * 1000)
    text = (response.text or "").strip()
    return text, ms


def run_one(spec: ModelSpec) -> int:
    ok_key, key_msg = api_key_status(spec)
    if not ok_key:
        print(f"  SKIP  {spec.key:20} - {key_msg}")
        return 1

    try:
        client = create_chat_client(spec)
        if spec.provider == "google":
            text, latency_ms = smoke_gemini(client, spec)
        else:
            text, latency_ms = smoke_openai_compatible(client, spec)
        preview = text.replace("\n", " ")[:80]
        print(f"  OK    {spec.key:20} ({spec.api_model}) {latency_ms}ms - {preview!r}")
        return 0
    except Exception as e:
        print(f"  FAIL  {spec.key:20} ({spec.api_model}) - {type(e).__name__}: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Registry key (repeatable). Default: all llm.eval_models",
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    registry = load_model_registry(cfg.models_config_path)
    keys = args.models or cfg.eval_model_keys

    print("LLM smoke tests\n")
    print(f"  Prompt: {PROMPT!r}\n")

    failures = 0
    for key in keys:
        try:
            spec = registry.get(key)
        except KeyError as e:
            print(f"  FAIL  {key:20} - {e}")
            failures += 1
            continue
        failures += run_one(spec)

    print()
    if failures:
        print(f"{failures} model(s) failed or skipped.")
        return 1
    print("All models responded successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
