#!/usr/bin/env bash
# Usage: bash checks.sh <work-copy-dir>
set -euo pipefail
cd -- "${1:?work copy dir required}"
"${HYDRA_BENCH_PYTHON:-python3}" -m pytest -q
count="$(grep -c 'Subtotal:' orders.py)"
if [[ "$count" -ne 1 ]]; then
  echo "expected 1 shared implementation, found $count" >&2
  exit 1
fi
