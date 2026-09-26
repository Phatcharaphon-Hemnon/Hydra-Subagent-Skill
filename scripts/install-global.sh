#!/usr/bin/env bash
set -euo pipefail

hydra_script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$hydra_script_dir/setup.sh" --all "$@"
