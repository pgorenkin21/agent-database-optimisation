#!/usr/bin/env bash
# Download BIRD mini-dev (~500 tasks, 11 DBs) into data/bird/mini_dev/
# Official: https://github.com/BIRD-bench/mini_dev
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${ROOT}/data/bird/mini_dev"
URL="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"

mkdir -p "${DATA}"
cd "${DATA}"

echo "Downloading BIRD mini-dev into ${DATA} ..."
if [[ ! -f minidev.zip ]]; then
  wget -q --show-progress -O minidev.zip "${URL}"
fi

if [[ ! -f mini_dev_sqlite.json ]]; then
  unzip -o minidev.zip
fi

# Normalise common zip layouts
if [[ -f mini_dev_data/mini_dev_sqlite.json ]] && [[ ! -f mini_dev_sqlite.json ]]; then
  shopt -s dotglob
  mv mini_dev_data/* .
  shopt -u dotglob
  rmdir mini_dev_data 2>/dev/null || true
fi

if [[ -d mini_dev_data/dev_databases ]] && [[ ! -d dev_databases ]]; then
  mv mini_dev_data/dev_databases .
fi

# Layout from minidev.zip (2024+): minidev/MINIDEV/{mini_dev_sqlite.json, dev_databases}
if [[ -f minidev/MINIDEV/mini_dev_sqlite.json ]] && [[ ! -f mini_dev_sqlite.json ]]; then
  cp minidev/MINIDEV/mini_dev_sqlite.json .
fi
if [[ -d minidev/MINIDEV/dev_databases ]] && [[ ! -d dev_databases ]]; then
  cp -r minidev/MINIDEV/dev_databases .
fi

echo ""
echo "Done. Expected layout:"
echo "  ${DATA}/mini_dev_sqlite.json"
echo "  ${DATA}/dev_databases/<db_id>/sqlite/*.sqlite"
echo ""
echo "Verify:"
echo "  uv run python scripts/check_setup.py"
echo ""
echo "Optional 50-task ID list:"
echo "  uv run python scripts/list_question_ids.py --limit 50 > configs/subsets/smoke_50.txt"
echo ""
echo "Full dev later: ./scripts/download_bird_full_dev.sh"
