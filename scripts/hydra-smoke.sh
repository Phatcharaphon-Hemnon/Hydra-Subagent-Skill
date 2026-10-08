#!/usr/bin/env bash
# Controlled live smoke tests: Tier 0 fast path (Test A) and Tier 1 adaptive
# delegation (Test B) on OpenCode, across single / baseline / optimized.
#
# QUOTA GATE: without HYDRA_LIVE_APPROVED=1 this script only prints the exact
# commands it would run (--plan mode) and exits 2. Auth material alone never
# authorizes spending quota.
set -euo pipefail

# Assumption: this script runs WITHOUT shell job control (normal scripts, CI,
# terminals). Background jobs must share the script's process group so that
# `setsid` puts each run in a fresh session whose pgid equals the tracked PID.
# Do not execute with `set -m`; group cleanup would be unreliable there.

hydra_script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hydra_repo_dir="$(cd -- "$hydra_script_dir/.." && pwd)"

hydra_host="opencode"
hydra_dir=""
hydra_baseline_dir=""
hydra_model="${HYDRA_BENCH_MODEL:-}"
hydra_live="${HYDRA_LIVE_APPROVED:-0}"
hydra_tasks_arg=""
hydra_max_runs="${HYDRA_SMOKE_MAX_RUNS:-}"
hydra_max_runs_given=false
hydra_time_budget="${HYDRA_SMOKE_TIME_BUDGET_S:-5400}"
hydra_run_timeout=1800
hydra_kill_grace="${HYDRA_SMOKE_KILL_GRACE_S:-10}"
if [[ ! "$hydra_kill_grace" =~ ^[0-9]+$ ]]; then
  printf 'Invalid HYDRA_SMOKE_KILL_GRACE_S: %s.\n' "$hydra_kill_grace" >&2
  exit 2
fi
hydra_have_setsid=false
if command -v setsid >/dev/null 2>&1; then hydra_have_setsid=true; fi

usage() {
  cat <<'USAGE'
Usage: bash scripts/hydra-smoke.sh --dir DIR [--host opencode]
       [--baseline-dir DIR] [--model NAME] [--tasks T0,T1,T2...]
       [--max-runs N]

  --dir DIR            Bench directory (created by hydra-bench.sh --init).
  --host               Only "opencode" is supported by this script.
  --baseline-dir DIR   REQUIRED: clean worktree at the pinned baseline commit
                       with a project-local setup install, so baseline runs
                       read baseline instructions. Smoke work copies for the
                       baseline condition live under DIR/smoke-runs and never
                       touch the Hydra source repository.
  --model NAME         Overrides HYDRA_BENCH_MODEL (must be pinned).
  --tasks              Comma-separated subset of small-fix,bounded-review,
                       cross-component (default: all three).
  --max-runs           Fail-closed cap on executed runs (default: plan size).
                       HYDRA_SMOKE_MAX_RUNS sets the same cap from the env.
                       HYDRA_SMOKE_TIME_BUDGET_S caps total seconds (default
                       5400); the script aborts when either cap is reached.
                       HYDRA_SMOKE_KILL_GRACE_S bounds post-timeout process
                       termination (default 10).

  Execution deadline: a monotonic clock tracks the shared total budget across
  all runs, stages, and conditions (never reset between baseline/optimized).
  Before each CLI invocation the script computes
  remaining = budget - elapsed and runs with
  effective_timeout = min(per-run timeout 1800s, remaining whole seconds).
  No invocation starts once fewer than one whole second remains. On timeout
  the CLI process group is terminated (TERM, bounded grace, then KILL via
  setsid isolation where available), leftovers are swept so no CLI child
  outlives its run, transcripts are preserved, and the ledger records
  acceptance=timeout. Runs execute without shell job control (normal scripts,
  CI, and terminals satisfy this); `set -m` is unsupported because group
  tracking would be unreliable there. Residual risk: if the OS recycled a dead
  run's pgid within milliseconds of the post-run sweep, the sweep could signal
  an unrelated group; the window is negligible and the target should be empty.
  Wall-clock overrun past the shared deadline is bounded
  by the kill grace period plus timer granularity; cleanup of unkillable
  (D-state) processes and remote provider-side execution cannot be bounded
  by this script.

  Token/spend limits CANNOT be enforced by this script: the host CLI exposes
  no token or spending cap flags. Set provider-side budget caps and supervise
  execution; token telemetry is recorded as unknown unless the host reports it.

  Without HYDRA_LIVE_APPROVED=1: prints the planned runs and exits 2.
USAGE
}

while (($# > 0)); do
  case "$1" in
    --dir) hydra_dir="$2"; shift 2 ;;
    --host) hydra_host="$2"; shift 2 ;;
    --baseline-dir) hydra_baseline_dir="$2"; shift 2 ;;
    --model) hydra_model="$2"; shift 2 ;;
    --tasks) hydra_tasks_arg="$2"; shift 2 ;;
    --max-runs) hydra_max_runs="$2"; hydra_max_runs_given=true; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$hydra_dir" ]]; then printf 'Missing --dir.\n' >&2; exit 2; fi
if [[ "$hydra_host" != "opencode" ]]; then printf 'Only --host opencode is supported.\n' >&2; exit 2; fi
if [[ -z "$hydra_model" ]]; then printf 'Pin the model via --model or HYDRA_BENCH_MODEL.\n' >&2; exit 2; fi

# Test plan: Tier 0 (small-fix), Tier 1 (bounded-review), Tier 2
# (cross-component) x 3 conditions. Tier 0 runs direct hydra-work with zero
# heads; Tier 1 expects exactly two heads; Tier 2 expects three heads.
hydra_all_tasks=("small-fix" "bounded-review" "cross-component")
hydra_tasks=()
if [[ -n "$hydra_tasks_arg" ]]; then
  IFS=',' read -r -a hydra_tasks <<< "$hydra_tasks_arg"
  for task in "${hydra_tasks[@]}"; do
    known=false
    for candidate in "${hydra_all_tasks[@]}"; do
      [[ "$task" == "$candidate" ]] && known=true
    done
    if [[ "$known" != true ]]; then
      printf 'Unknown task: %s (choose from %s).\n' "$task" "${hydra_all_tasks[*]}" >&2
      exit 2
    fi
  done
else
  hydra_tasks=("${hydra_all_tasks[@]}")
fi
hydra_conditions=("single" "baseline" "optimized")

hydra_tier_for() {
  case "$1" in
    small-fix) printf 'Tier0' ;;
    bounded-review) printf 'Tier1' ;;
    *) printf 'Tier2' ;;
  esac
}

hydra_heads_for() {
  case "$1" in
    Tier0) printf '0' ;;
    Tier1) printf '2' ;;
    *) printf '3' ;;
  esac
}

hydra_prompt_for() {
  # $1 = condition, $2 = task
  local condition="$1" prompt
  prompt="$(cat "$hydra_repo_dir/bench/fixtures/$2/prompt.md")"
  case "$condition" in
    single) printf '%s' "$prompt" ;;
    baseline|optimized)
      printf 'Use Hydra for the request below, following the installed hydra-review workflow. The request is authorized for implementation and verification within its stated scope.\n\n%s' "$prompt" ;;
  esac
}

hydra_baseline_sha="$(git -C "${hydra_baseline_dir:-/nonexistent}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
hydra_optimized_sha="$(git -C "$hydra_repo_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)"
if [[ -n "$(git -C "$hydra_repo_dir" status --short 2>/dev/null)" ]]; then
  hydra_optimized_sha="$hydra_optimized_sha-dirty"
fi

hydra_tagged_workflow() {
  # $1 = condition -> workflow id pinned to its instruction revision.
  case "$1" in
    single) printf 'single-agent' ;;
    baseline) printf 'baseline-hydra:%s' "$hydra_baseline_sha" ;;
    optimized) printf 'optimized-hydra:%s' "$hydra_optimized_sha" ;;
  esac
}

printf 'Smoke plan: host=%s model=%s runs=%d\n' \
  "$hydra_host" "$hydra_model" "$(( ${#hydra_tasks[@]} * ${#hydra_conditions[@]} ))"
rep=1
for task in "${hydra_tasks[@]}"; do
  for condition in "${hydra_conditions[@]}"; do
    tier="$(hydra_tier_for "$task")"
    if [[ "$tier" == Tier0 && "$condition" != single ]]; then
      steps="hydra-work direct, $tier, 0 heads"
    elif [[ "$condition" == single ]]; then
      steps="build direct, no Hydra"
    else
      steps="hydra-plan ($tier, $(hydra_heads_for "$tier") heads), then authorized hydra-work"
    fi
    printf '  [%s-%s] %s workflow=%s prompt=bench/fixtures/%s/prompt.md\n' \
      "$condition" "$task" "$steps" "$(hydra_tagged_workflow "$condition")" "$task"
  done
done
if [[ "$hydra_max_runs_given" != true ]]; then
  if [[ -z "$hydra_max_runs" ]]; then
    hydra_max_runs=$(( ${#hydra_tasks[@]} * ${#hydra_conditions[@]} ))
  fi
elif [[ -z "$hydra_max_runs" ]]; then
  printf 'Empty --max-runs; refusing to run.\n' >&2
  exit 2
fi
if [[ ! "$hydra_max_runs" =~ ^[0-9]+$ ]]; then
  printf 'Invalid --max-runs: %s (non-negative integer required).\n' "$hydra_max_runs" >&2
  exit 2
fi
if [[ ! "$hydra_time_budget" =~ ^[0-9]+$ ]]; then
  printf 'Invalid HYDRA_SMOKE_TIME_BUDGET_S: %s.\n' "$hydra_time_budget" >&2
  exit 2
fi
printf 'Budget: max_runs=%s time_budget_s=%s run_timeout_s=%s\n' \
  "$hydra_max_runs" "$hydra_time_budget" "$hydra_run_timeout"
printf 'Limitation: token/spend caps are NOT enforceable here; set provider-side budget caps.\n'

if [[ "$hydra_live" != "1" ]]; then
  printf 'Set HYDRA_LIVE_APPROVED=1 to execute (quota will be spent).\n'
  exit 2
fi

if [[ ! -f "$hydra_dir/ledger.csv" ]]; then
  printf 'No ledger at %s; run hydra-bench.sh --init first.\n' "$hydra_dir" >&2
  exit 1
fi
hydra_baseline_needs=(
  ".agents/skills/hydra-review/SKILL.md"
  ".opencode/agent/hydra-plan.md"
  ".opencode/agent/hydra-work.md"
  ".opencode/agent/hydra-verify.md"
)
for hydra_need in "${hydra_baseline_needs[@]}"; do
  if [[ ! -f "$hydra_baseline_dir/$hydra_need" ]]; then
    printf 'Baseline instructions missing: %s/%s\n' "$hydra_baseline_dir" "$hydra_need" >&2
    printf 'Create a clean worktree at the pinned baseline commit and run setup.sh --project there.\n' >&2
    exit 1
  fi
done
hydra_cli_version="$(opencode --version 2>/dev/null | head -n 1)"

hydra_run() {
  # $1 = workdir, $2 = agent, $3 = prompt file, $4 = transcript path,
  # $5 = effective timeout in whole seconds (>= 1).
  # Runs the CLI in its own session when setsid exists so the whole process
  # group can be terminated; `timeout` bounds the run to the effective
  # timeout. Prints elapsed seconds on line 1 and 1/0 (timed out or not) on
  # line 2. Always exits 0 so command substitution never trips set -e.
  local leader pgid status timed_out
  hydra_timed_out=0
  timed_out=0
  local start end
  start="$(date +%s%N)"
  if [[ "$hydra_have_setsid" == true ]]; then
    if (( hydra_kill_grace > 0 )); then
      setsid timeout -k "${hydra_kill_grace}" "$5" bash -c 'cd "$0" && exec opencode run --agent "$1" "$(cat "$2")"' \
        "$1" "$2" "$3" >"$4" 2>&1 &
    else
      setsid timeout "$5" bash -c 'cd "$0" && exec opencode run --agent "$1" "$(cat "$2")"' \
        "$1" "$2" "$3" >"$4" 2>&1 &
    fi
    leader=$!
    pgid="$leader"
  else
    printf 'WARNING: setsid missing; child-process group cleanup unavailable.\n' >>"$4"
    timeout "$5" bash -c 'cd "$0" && exec opencode run --agent "$1" "$(cat "$2")"' \
      "$1" "$2" "$3" >"$4" 2>&1 &
    leader=$!
    pgid=""
  fi
  # Supervise: `timeout` enforces the effective timeout (which never exceeds
  # the remaining shared budget by construction). After the leader exits, the
  # group sweep below guarantees no CLI child outlives the run. Wall-clock
  # overrun past the shared deadline is bounded by the kill grace period.
  if wait "$leader" 2>/dev/null; then
    status=0
  else
    status=$?
    if (( status == 124 || status == 137 )); then
      timed_out=1
      printf 'effective timeout (%ss) reached; agent terminated.\n' "$5" >>"$4"
    else
      printf 'agent exited %d (see %s)\n' "$status" "$4" >&2
    fi
  fi
  # Sweep leftover group members so no model CLI child outlives the run.
  if [[ -n "$pgid" ]]; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
  fi
  hydra_timed_out="$timed_out"
  end="$(date +%s%N)"
  awk "BEGIN {printf \"%.1f\\n%d\\n\", ($end - $start) / 1000000000, $timed_out}"
}

hydra_exec_bounded() {
  # $1 = workdir, $2 = agent, $3 = prompt file, $4 = transcript path.
  # Bounds one CLI invocation by min(per-run timeout, remaining shared
  # budget). Returns 2 without starting anything when the shared budget is
  # exhausted. Sets hydra_elapsed and hydra_timed_out.
  local now remaining_ns eff_s
  now="$(date +%s%N)"
  remaining_ns=$(( hydra_budget_ns - (now - smoke_start) ))
  if (( remaining_ns < 1000000000 )); then
    return 2
  fi
  eff_s=$(( remaining_ns / 1000000000 ))
  if (( eff_s > hydra_run_timeout )); then
    eff_s="$hydra_run_timeout"
  fi
  local out
  out="$(hydra_run "$1" "$2" "$3" "$4" "$eff_s")"
  hydra_elapsed="$(head -n 1 <<<"$out")"
  hydra_timed_out="$(tail -n 1 <<<"$out")"
  return 0
}

hydra_budget_ok() {
  # $1 = runs completed, $2 = smoke start (ns) -> 0 when over budget.
  local now
  now="$(date +%s%N)"
  if (( $1 >= hydra_max_runs )); then
    printf 'STOP: max_runs=%s reached; aborting remaining runs.\n' "$hydra_max_runs"
    return 1
  fi
  if (( (now - $2) / 1000000000 >= hydra_time_budget )); then
    printf 'STOP: time budget %ss exhausted; aborting remaining runs.\n' "$hydra_time_budget"
    return 1
  fi
  return 0
}

run_id=0
smoke_start="$(date +%s%N)"
hydra_budget_ns=$(( hydra_time_budget * 1000000000 ))
hydra_aborted=false
hydra_planned_pairs=()
for task in "${hydra_tasks[@]}"; do
  for condition in "${hydra_conditions[@]}"; do
    hydra_planned_pairs+=("$task|$condition")
  done
done

hydra_unique_run_id() {
  # $1 = base run id -> prints an id absent from the ledger (appends -aN).
  local base="$1" candidate="$1" attempt=0
  while grep -q "^${candidate}," "$hydra_dir/ledger.csv" 2>/dev/null; do
    attempt=$((attempt + 1))
    candidate="$base-a$attempt"
  done
  printf '%s' "$candidate"
}

hydra_record_not_executed() {
  # $1 = first pair index to mark not_executed (runs never started).
  local pi task condition run_id
  for ((pi = $1; pi < ${#hydra_planned_pairs[@]}; pi++)); do
    task="${hydra_planned_pairs[$pi]%%|*}"
    condition="${hydra_planned_pairs[$pi]##*|}"
    run_id="$(hydra_unique_run_id "smoke-$condition-$task-rep$rep")"
    bash "$hydra_repo_dir/scripts/hydra-bench.sh" --record --dir "$hydra_dir" \
      --run-id "$run_id" --task "$task" --condition "$condition" \
      --rep "$rep" --host "$hydra_host" --model "$hydra_model" \
      --cli-version "$hydra_cli_version" --workflow "$(hydra_tagged_workflow "$condition")" \
      --elapsed unknown --acceptance not_executed --security na >/dev/null
  done
}

for ((hydra_pi = 0; hydra_pi < ${#hydra_planned_pairs[@]}; hydra_pi++)); do
  task="${hydra_planned_pairs[$hydra_pi]%%|*}"
  condition="${hydra_planned_pairs[$hydra_pi]##*|}"
  if ! hydra_budget_ok "$run_id" "$smoke_start"; then
    printf 'Budget gate stopped the smoke run after %d completed runs.\n' "$run_id"
    hydra_record_not_executed "$hydra_pi"
    exit 1
  fi
  run_id=$((run_id + 1))
  smoke_run_id="$(hydra_unique_run_id "smoke-$condition-$task-rep$rep")"
  hydra_invocations=0
    if [[ "$condition" == baseline ]]; then
      root="$hydra_baseline_dir/smoke-runs"
      mkdir -p "$root"
      work="$(mktemp -d "$root/run-XXXXXX")"
    else
      work="$(mktemp -d /tmp/opencode/hydra-smoke-XXXXXX)"
    fi
    cp -r "$hydra_repo_dir/bench/fixtures/$task/starting/." "$work/"
    prompt_file="$work/prompt.txt"
    hydra_prompt_for "$condition" "$task" > "$prompt_file"
    printf -- '--- run %d: %s/%s work=%s ---\n' "$run_id" "$condition" "$task" "$work"
    hydra_stage_timed_out=0
    acceptance=""
    if [[ "$condition" == single ]]; then
      if ! hydra_exec_bounded "$work" build "$prompt_file" "$work/transcript.log"; then
        printf 'Shared time budget exhausted before run %d; no further model calls.\n' "$run_id"
        hydra_record_not_executed "$hydra_pi"
        exit 1
      fi
      hydra_invocations=$((hydra_invocations + 1))
      elapsed="$hydra_elapsed"
      if (( hydra_timed_out == 1 )); then hydra_stage_timed_out=1; fi
    elif [[ "$(hydra_tier_for "$task")" == Tier0 ]]; then
      if ! hydra_exec_bounded "$work" hydra-work "$prompt_file" "$work/transcript.log"; then
        printf 'Shared time budget exhausted before run %d; no further model calls.\n' "$run_id"
        hydra_record_not_executed "$hydra_pi"
        exit 1
      fi
      hydra_invocations=$((hydra_invocations + 1))
      elapsed="$hydra_elapsed"
      if (( hydra_timed_out == 1 )); then hydra_stage_timed_out=1; fi
    else
      if ! hydra_exec_bounded "$work" hydra-plan "$prompt_file" "$work/transcript-plan.log"; then
        printf 'Shared time budget exhausted before run %d; no further model calls.\n' "$run_id"
        hydra_record_not_executed "$hydra_pi"
        exit 1
      fi
      hydra_invocations=$((hydra_invocations + 1))
      plan_elapsed="$hydra_elapsed"
      if (( hydra_timed_out == 1 )); then hydra_stage_timed_out=1; fi
      {
        printf 'Execution is authorized for the scope in the handoff below. Implement it and verify the result.\n\nPlanning handoff (full hydra-plan transcript):\n\n'
        cat "$work/transcript-plan.log"
      } > "$work/work-prompt.txt"
      if ! hydra_exec_bounded "$work" hydra-work "$work/work-prompt.txt" "$work/transcript-work.log"; then
        printf 'Shared time budget exhausted mid-run %d; recording partial result with no further model calls.\n' "$run_id"
        hydra_aborted=true
        elapsed="$plan_elapsed"
        acceptance=incomplete
      else
        hydra_invocations=$((hydra_invocations + 1))
        work_elapsed="$hydra_elapsed"
        if (( hydra_timed_out == 1 )); then hydra_stage_timed_out=1; fi
        elapsed="$(awk "BEGIN {printf \"%.1f\", $plan_elapsed + $work_elapsed}")"
      fi
    fi
    if [[ -z "$acceptance" ]]; then
      if (( hydra_stage_timed_out == 1 )); then
        acceptance=timeout
      elif HYDRA_BENCH_PYTHON="${HYDRA_BENCH_PYTHON:-}" bash "$hydra_repo_dir/bench/fixtures/$task/checks.sh" "$work" >/dev/null 2>&1; then
        acceptance=pass
      else
        acceptance=fail
      fi
    fi
    bash "$hydra_repo_dir/scripts/hydra-bench.sh" --record --dir "$hydra_dir" \
      --run-id "$smoke_run_id" --task "$task" --condition "$condition" \
      --rep "$rep" --host "$hydra_host" --model "$hydra_model" \
      --cli-version "$hydra_cli_version" --workflow "$(hydra_tagged_workflow "$condition")" \
      --elapsed "$elapsed" --acceptance "$acceptance" --security na \
      --agent-calls "$hydra_invocations" >/dev/null
    printf 'recorded %s elapsed=%ss acceptance=%s work=%s\n' \
      "$smoke_run_id" "$elapsed" "$acceptance" "$work"
    if [[ "$hydra_aborted" == true ]]; then
      printf 'Shared budget expired mid-run; stopping with no further model calls.\n'
      hydra_record_not_executed $((hydra_pi + 1))
      exit 1
    fi
done

printf 'Smoke runs complete. Evaluate the exit gate in bench/README.md:\n'
printf 'routing match, authorization boundaries, verification evidence, telemetry, quota.\n'
