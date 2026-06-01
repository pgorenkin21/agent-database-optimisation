#!/usr/bin/env bash
# Download full BIRD dev split into data/bird/full_dev/ (large download).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${ROOT}/data/bird/full_dev"
URL="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"

mkdir -p "${DATA}"
cd "${DATA}"

echo "Downloading full BIRD dev into ${DATA} (this is large) ..."
if [[ ! -f dev.zip ]]; then
  wget -q --show-progress -O dev.zip "${URL}"
fi

if [[ ! -f dev.json ]]; then
  unzip -o dev.zip
fi

if [[ -d dev ]] && [[ ! -f dev.json ]]; then
  shopt -s dotglob
  mv dev/* . 2>/dev/null || true
  shopt -u dotglob
fi

if [[ -f dev/dev.json ]] && [[ ! -f dev.json ]]; then
  cp dev/dev.json .
fi

if [[ -f dev/dev_databases.zip ]] && [[ ! -d dev_databases ]]; then
  unzip -o dev/dev_databases.zip -d .
fi

if [[ -d dev/dev_databases ]] && [[ ! -d dev_databases ]]; then
  mv dev/dev_databases .
fi

echo ""
echo "Done. Use config: configs/full_dev.yaml"
echo "  uv run python scripts/check_setup.py --config configs/full_dev.yaml"
