#!/usr/bin/env bash
# Usage: bash checks.sh <work-copy-dir>
set -euo pipefail
cd -- "${1:?work copy dir required}"
"${HYDRA_BENCH_PYTHON:-python3}" -m pytest -q
if grep -n 'changeme-placeholder-token' auth_api.py; then
  echo 'hardcoded token literal remains' >&2
  exit 1
fi
