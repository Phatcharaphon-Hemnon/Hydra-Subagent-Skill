#!/usr/bin/env bash
# Isolated virtual environment for benchmark fixture checks.
# Never touches system Python packages (PEP 668 safe): everything lives
# inside the created venv directory.
set -euo pipefail

hydra_venv="${1:-bench/.venv}"
hydra_repo_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -e "$hydra_venv" ]]; then
  printf 'Reusing existing venv: %s\n' "$hydra_venv"
else
  python3 -m venv "$hydra_venv"
  printf 'Created venv: %s\n' "$hydra_venv"
fi

"$hydra_venv/bin/pip" install -q pytest
if [[ -f "$hydra_repo_dir/requirements-dev.txt" ]]; then
  "$hydra_venv/bin/pip" install -q -r "$hydra_repo_dir/requirements-dev.txt"
fi
"$hydra_venv/bin/python" -m pytest --version
printf 'Use it via: HYDRA_BENCH_PYTHON=%s/bin/python bash <fixture>/checks.sh <work-copy>\n' "$hydra_venv"
