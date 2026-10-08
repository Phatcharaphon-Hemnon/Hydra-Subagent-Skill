#!/usr/bin/env bash
# Usage: bash checks.sh <work-copy-dir>
set -euo pipefail
cd -- "${1:?work copy dir required}"
"${HYDRA_BENCH_PYTHON:-python3}" -m pytest -q
