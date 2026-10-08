#!/usr/bin/env bash
# Offline preflight for live Hydra benchmarks. Makes NO model calls, prints NO
# secrets, spends NO quota. Exit 0 when ready for authorized live runs.
set -uo pipefail

hydra_script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hydra_repo_dir="$(cd -- "$hydra_script_dir/.." && pwd)"
hydra_ready=true

fail() {
  printf 'NOT READY: %s\n' "$1"
  hydra_ready=false
}

printf '== CLI hosts ==\n'
for cli in codex claude gemini opencode; do
  if command -v "$cli" >/dev/null 2>&1; then
    printf '%s: %s\n' "$cli" "$("$cli" --version 2>&1 | head -n 1)"
  else
    printf '%s: missing\n' "$cli"
  fi
done

printf '\n== model pin ==\n'
if [[ -n "${HYDRA_BENCH_MODEL:-}" ]]; then
  printf 'HYDRA_BENCH_MODEL=%s\n' "$HYDRA_BENCH_MODEL"
else
  fail 'HYDRA_BENCH_MODEL is unset; pin the model and reasoning config first.'
fi

printf '\n== authentication (presence only, no values) ==\n'
if [[ -f "$HOME/.codex/auth.json" ]]; then
  printf 'codex: auth file present (keys: %s)\n' \
    "$(python3 -c "import json;print(','.join(sorted(json.load(open('$HOME/.codex/auth.json')).keys())))" 2>/dev/null || echo unreadable)"
else
  printf 'codex: no auth file\n'
fi
if command -v opencode >/dev/null 2>&1; then
  printf 'opencode auth: %s\n' "$(timeout 30 opencode auth list 2>/dev/null | awk '{print $1}' | paste -sd, -)"
else
  printf 'opencode: binary missing\n'
fi
for var in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY GOOGLE_API_KEY; do
  if [[ -n "${!var:-}" ]]; then printf '%s: set\n' "$var"; else printf '%s: unset\n' "$var"; fi
done

printf '\n== fixture python ==\n'
hydra_python="${HYDRA_BENCH_PYTHON:-$hydra_repo_dir/bench/.venv/bin/python}"
hydra_pytest_ok=false
if "$hydra_python" -m pytest --version >/dev/null 2>&1; then
  printf 'pytest OK via %s\n' "$hydra_python"
  export HYDRA_BENCH_PYTHON="$hydra_python"
  hydra_pytest_ok=true
else
  fail "no working pytest at $hydra_python; run: bash bench/bootstrap.sh"
fi

printf '\n== fixtures ==\n'
for fixture in "$hydra_repo_dir"/bench/fixtures/*/; do
  category="$(basename "$fixture")"
  fixture="${fixture%/}"
  for needed in prompt.md acceptance.md checks.sh starting; do
    if [[ ! -e "$fixture/$needed" ]]; then
      fail "missing $fixture/$needed"
    fi
  done
  work="$(mktemp -d)"
  cp -r "$fixture/starting/." "$work/"
  if [[ "$hydra_pytest_ok" != true ]]; then
    printf '%s: skipped (no working pytest)\n' "$category"
  elif bash "$fixture/checks.sh" "$work" >/dev/null 2>&1; then
    fail "$category checks.sh passes on the broken starting state"
  else
    printf '%s: fails on starting state as expected\n' "$category"
  fi
  rm -rf "$work"
done

printf '\n== harness ==\n'
probe="$(mktemp -d)"
if bash "$hydra_repo_dir/scripts/hydra-bench.sh" --init --dir "$probe/bench" \
    --host codex --fixtures "$hydra_repo_dir/bench/fixtures" >/dev/null 2>&1 \
  && bash "$hydra_repo_dir/scripts/hydra-bench.sh" --record --dir "$probe/bench" \
    --run-id preflight --task small-fix --condition single --rep 1 \
    --host codex --elapsed 1.0 --acceptance pass >/dev/null 2>&1 \
  && bash "$hydra_repo_dir/scripts/hydra-bench.sh" --report --dir "$probe/bench" \
    | grep -q 'median_elapsed_s'; then
  printf 'harness init/record/report roundtrip OK\n'
else
  fail 'benchmark harness roundtrip failed'
fi
rm -rf "$probe"

printf '\n== quota estimate (model calls, tokens unknown until first run) ==\n'
printf 'smoke (3 tasks x 3 conditions): ~45-70 calls\n'
printf 'minimal bench (3 tasks x 3 conditions x 1 rep): ~45-70 calls\n'
printf 'full matrix (54 runs/host): ~300-450 calls/host\n'
printf 'Live runs require HYDRA_LIVE_APPROVED=1 (see scripts/hydra-smoke.sh).\n'
printf 'Auth material alone is NOT permission to spend quota.\n'

printf '\n== verdict ==\n'
if [[ "$hydra_ready" == true ]]; then
  printf 'READY for authorized live runs.\n'
  exit 0
else
  printf 'NOT READY (see reasons above).\n'
  exit 1
fi
