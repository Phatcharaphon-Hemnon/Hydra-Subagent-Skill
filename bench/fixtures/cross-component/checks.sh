#!/usr/bin/env bash
# Usage: bash checks.sh <work-copy-dir>
set -euo pipefail
cd -- "${1:?work copy dir required}"
"${HYDRA_BENCH_PYTHON:-python3}" -m pytest -q
if grep -nE 'DISCOUNT_RATE *= *0' receipt.py; then
  echo 'receipt.py still defines its own rate' >&2
  exit 1
fi
