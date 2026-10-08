#!/usr/bin/env bash
# Hydra overhead benchmark harness (see docs/BENCHMARKS.md).
# Compares single-agent, baseline Hydra, and optimized Hydra across five task
# categories with three repetitions each. Authenticated model runs are manual:
# this harness plans the matrix, records per-run evidence, and reports medians
# with speedup ratios. It never invents telemetry: missing values stay "unknown".
set -euo pipefail

hydra_script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hydra_repo_dir="$(cd -- "$hydra_script_dir/.." && pwd)"

hydra_conditions=("single" "baseline" "optimized")
hydra_categories=("small-fix" "bounded-review" "cross-component" "refactor" "security-api" "debugging")
hydra_reps=3

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/hydra-bench.sh --list
      Print the run matrix (3 conditions x 5 categories x 3 repetitions).

  bash scripts/hydra-bench.sh --init --dir DIR --host CLI [--fixtures DIR]
      Create DIR with ledger.csv and a rotated run order for one host/CLI.
      With --fixtures, validate the five frozen fixture categories exist and
      record the fixtures path for the runbook.

  bash scripts/hydra-bench.sh --record --dir DIR [FIELD FLAGS...]
      Append one per-run record. Required: --run-id, --task, --condition,
      --rep, --host, --elapsed. Optional timings/tokens/calls default to
      "unknown". --acceptance pass|fail|timeout|incomplete|not_executed, --security pass|fail|na.

  bash scripts/hydra-bench.sh --report --dir DIR
      Print medians by task category and condition plus speedup ratios.

  bash scripts/hydra-bench.sh --dry-run --dir DIR --host CLI
      Offline validation: build the matrix with placeholder runs (no models,
      telemetry recorded as unknown) and print the report. Proves the
      harness works; never presented as a performance result.
USAGE
}

hydra_cmd="${1:-}"
case "$hydra_cmd" in
  --list)
    for condition in "${hydra_conditions[@]}"; do
      for category in "${hydra_categories[@]}"; do
        for ((rep = 1; rep <= hydra_reps; rep++)); do
          printf '%s %s rep%d\n' "$condition" "$category" "$rep"
        done
      done
    done
    printf 'Total per host: %d runs\n' "$(( ${#hydra_conditions[@]} * ${#hydra_categories[@]} * hydra_reps ))"
    exit 0
    ;;
esac

hydra_dir=""
hydra_host=""
hydra_fixtures=""
if [[ "$hydra_cmd" == "--init" || "$hydra_cmd" == "--report" || "$hydra_cmd" == "--dry-run" ]]; then
  while (($# > 0)); do
    case "$1" in
      --init|--report|--dry-run) shift ;;
      --dir) hydra_dir="$2"; shift 2 ;;
      --host) hydra_host="$2"; shift 2 ;;
      --fixtures) hydra_fixtures="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
  done
  if [[ -z "$hydra_dir" ]]; then
    printf 'Missing --dir.\n' >&2
    exit 2
  fi
fi

ledger_header="run_id,task,condition,rep,host,model,cli_version,workflow_id,elapsed_s,planning_s,implementation_s,verification_s,repair_s,routing_s,in_tokens,out_tokens,duplicated_tokens,agent_calls,tool_calls,repair_loops,acceptance,security_result"

if [[ "$hydra_cmd" == "--init" ]]; then
  if [[ -z "$hydra_host" ]]; then
    printf 'Missing --host.\n' >&2
    exit 2
  fi
  mkdir -p "$hydra_dir"
  if [[ -e "$hydra_dir/ledger.csv" ]]; then
    printf 'Ledger already exists: %s/ledger.csv\n' "$hydra_dir" >&2
    exit 1
  fi
  if [[ -n "$hydra_fixtures" ]]; then
    for category in "${hydra_categories[@]}"; do
      for needed in prompt.md acceptance.md checks.sh starting; do
        if [[ ! -e "$hydra_fixtures/$category/$needed" ]]; then
          printf 'Missing fixture: %s/%s/%s\n' "$hydra_fixtures" "$category" "$needed" >&2
          exit 1
        fi
      done
    done
    printf '%s\n' "$hydra_fixtures" > "$hydra_dir/fixtures.path"
  fi
  printf '%s\n' "$ledger_header" > "$hydra_dir/ledger.csv"
  # Rotated run order reduces order effects; one rotation per repetition.
  : > "$hydra_dir/run-order.txt"
  for ((rep = 1; rep <= hydra_reps; rep++)); do
    for category in "${hydra_categories[@]}"; do
      shift_n=$(( (rep - 1) % ${#hydra_conditions[@]} ))
      ordered=("${hydra_conditions[@]:$shift_n}" "${hydra_conditions[@]:0:$shift_n}")
      for condition in "${ordered[@]}"; do
        printf '%s-%s-rep%d %s\n' "$condition" "$category" "$rep" "$hydra_host" >> "$hydra_dir/run-order.txt"
      done
    done
  done
  printf 'Initialized %s for host %s: %d planned runs.\n' "$hydra_dir" "$hydra_host" "$(wc -l < "$hydra_dir/run-order.txt")"
  exit 0
fi

if [[ "$hydra_cmd" == "--record" ]]; then
  shift
  hydra_run_id="" hydra_task="" hydra_condition="" hydra_rep="" hydra_host=""
  hydra_elapsed="" hydra_acceptance="" hydra_security="na"
  hydra_model="unknown" hydra_cli_version="unknown" hydra_workflow="unknown"
  hydra_planning="unknown" hydra_implementation="unknown" hydra_verification="unknown"
  hydra_repair="unknown" hydra_routing="unknown"
  hydra_in="unknown" hydra_out="unknown" hydra_dup="unknown"
  hydra_agent_calls="unknown" hydra_tool_calls="unknown" hydra_repair_loops="unknown"
  while (($# > 0)); do
    case "$1" in
      --dir) hydra_dir="$2"; shift 2 ;;
      --run-id) hydra_run_id="$2"; shift 2 ;;
      --task) hydra_task="$2"; shift 2 ;;
      --condition) hydra_condition="$2"; shift 2 ;;
      --rep) hydra_rep="$2"; shift 2 ;;
      --host) hydra_host="$2"; shift 2 ;;
      --elapsed) hydra_elapsed="$2"; shift 2 ;;
      --planning) hydra_planning="$2"; shift 2 ;;
      --implementation) hydra_implementation="$2"; shift 2 ;;
      --verification) hydra_verification="$2"; shift 2 ;;
      --repair) hydra_repair="$2"; shift 2 ;;
      --routing) hydra_routing="$2"; shift 2 ;;
      --in-tokens) hydra_in="$2"; shift 2 ;;
      --out-tokens) hydra_out="$2"; shift 2 ;;
      --dup-tokens) hydra_dup="$2"; shift 2 ;;
      --agent-calls) hydra_agent_calls="$2"; shift 2 ;;
      --tool-calls) hydra_tool_calls="$2"; shift 2 ;;
      --repair-loops) hydra_repair_loops="$2"; shift 2 ;;
      --acceptance) hydra_acceptance="$2"; shift 2 ;;
      --security) hydra_security="$2"; shift 2 ;;
      --model) hydra_model="$2"; shift 2 ;;
      --cli-version) hydra_cli_version="$2"; shift 2 ;;
      --workflow) hydra_workflow="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
  done
  for field in hydra_dir hydra_run_id hydra_task hydra_condition hydra_rep hydra_host hydra_elapsed hydra_acceptance; do
    if [[ -z "${!field}" ]]; then
      printf 'Missing required field for --%s.\n' "${field#hydra_}" >&2
      exit 2
    fi
  done
  case "$hydra_acceptance" in pass|fail|timeout|incomplete|not_executed) ;; *) printf 'Use --acceptance pass|fail|timeout|incomplete|not_executed.\n' >&2; exit 2 ;; esac
  case "$hydra_security" in pass|fail|na) ;; *) printf 'Use --security pass|fail|na.\n' >&2; exit 2 ;; esac
  if [[ ! -f "$hydra_dir/ledger.csv" ]]; then
    printf 'No ledger at %s; run --init first.\n' "$hydra_dir" >&2
    exit 1
  fi
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$hydra_run_id" "$hydra_task" "$hydra_condition" "$hydra_rep" "$hydra_host" \
    "$hydra_model" "$hydra_cli_version" "$hydra_workflow" \
    "$hydra_elapsed" "$hydra_planning" "$hydra_implementation" "$hydra_verification" \
    "$hydra_repair" "$hydra_routing" "$hydra_in" "$hydra_out" "$hydra_dup" \
    "$hydra_agent_calls" "$hydra_tool_calls" "$hydra_repair_loops" \
    "$hydra_acceptance" "$hydra_security" >> "$hydra_dir/ledger.csv"
  printf 'Recorded %s.\n' "$hydra_run_id"
  exit 0
fi

if [[ "$hydra_cmd" == "--report" ]]; then
  if [[ ! -f "$hydra_dir/ledger.csv" ]]; then
    printf 'No ledger at %s.\n' "$hydra_dir" >&2
    exit 1
  fi
  python3 - "$hydra_dir/ledger.csv" <<'PYEOF'
import csv, statistics, sys
path = sys.argv[1]
rows = list(csv.DictReader(open(path)))
if not rows:
    print("Ledger is empty: no runs recorded.")
    sys.exit(0)
def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
groups = {}
for r in rows:
    groups.setdefault((r["task"], r["condition"]), []).append(r)
for (task, condition) in sorted(groups):
    members = groups[(task, condition)]
    vals = [v for v in (num(r["elapsed_s"]) for r in members) if v is not None]
    outcomes = {}
    for r in members:
        outcomes[r["acceptance"]] = outcomes.get(r["acceptance"], 0) + 1
    med = statistics.median(vals) if vals else "unknown"
    print(f"{task} {condition}: n={len(vals)} median_elapsed_s={med} outcomes={outcomes}")
print("--- comparisons use elapsed medians only; unknown/timeout/incomplete/not_executed excluded ---")
def med_elapsed(task, condition):
    vals = [v for v in (num(r["elapsed_s"]) for r in groups.get((task, condition), [])) if v is not None]
    return statistics.median(vals) if vals else None
def med_calls(task, condition):
    vals = [v for v in (num(r.get("agent_calls", "unknown")) for r in groups.get((task, condition), [])) if v is not None]
    return statistics.median(vals) if vals else None
print("--- speedup (baseline / optimized median elapsed, per task) ---")
for task in sorted({t for (t, _) in groups}):
    bm, om = med_elapsed(task, "baseline"), med_elapsed(task, "optimized")
    if bm is None or om is None:
        print(f"{task}: unknown (missing matched baseline/optimized elapsed runs)")
        continue
    if om == 0:
        print(f"{task}: unknown (zero optimized elapsed)")
        continue
    speedup = bm / om
    improvement = (bm - om) / bm * 100 if bm != 0 else 0.0
    line = f"{task}: speedup={speedup:.3f} time_improvement_pct={improvement:.1f}"
    bcalls, ocalls = med_calls(task, "baseline"), med_calls(task, "optimized")
    if bcalls is None or ocalls is None:
        line += " model_call_reduction_pct=unknown (agent_calls telemetry missing)"
    elif bcalls == 0:
        line += " model_call_reduction_pct=unknown (zero baseline calls)"
    else:
        line += f" model_call_reduction_pct={(bcalls - ocalls) / bcalls * 100:.1f}"
    print(line)
PYEOF
  exit 0
fi

if [[ "$hydra_cmd" == "--dry-run" ]]; then
  if [[ -z "$hydra_host" ]]; then
    printf 'Missing --host.\n' >&2
    exit 2
  fi
  rm -rf -- "$hydra_dir"
  bash "$hydra_script_dir/hydra-bench.sh" --init --dir "$hydra_dir" --host "$hydra_host" >/dev/null
  while IFS= read -r line; do
    run_id="${line%% *}"
    condition="${run_id%%-*}"
    rest="${run_id#*-}"
    task="${rest%-rep*}"
    rep="${run_id##*rep}"
    start="$(date +%s%N)"
    : # placeholder run: no model, no tools, no telemetry
    end="$(date +%s%N)"
    elapsed="$(awk "BEGIN {printf \"%.3f\", ($end - $start) / 1000000000}")"
    bash "$hydra_script_dir/hydra-bench.sh" --record --dir "$hydra_dir" \
      --run-id "$run_id-dry" --task "$task" --condition "$condition" --rep "$rep" \
      --host "$hydra_host" --elapsed "$elapsed" --acceptance pass --security na >/dev/null
  done < "$hydra_dir/run-order.txt"
  bash "$hydra_script_dir/hydra-bench.sh" --report --dir "$hydra_dir"
  printf 'DRY RUN ONLY: placeholder timings, telemetry unknown; not a performance result.\n'
  exit 0
fi

usage >&2
exit 2
