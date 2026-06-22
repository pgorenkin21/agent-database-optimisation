#!/usr/bin/env python3
"""Compare P1+P2 vs P0, P1, and P2 at r=10 (convenience wrapper)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "compare_middleware_stack.py"),
        "--replicas",
        "10",
        "--report-id",
        "p1p2_stack_r10",
        *sys.argv[1:],
    ]
    raise SystemExit(subprocess.call(cmd))
