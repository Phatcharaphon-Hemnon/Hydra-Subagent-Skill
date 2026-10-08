# Hydra benchmark runbook

Reproducible live runs for `docs/BENCHMARKS.md`, executed with the harness in
`scripts/hydra-bench.sh` and the frozen fixtures in `bench/fixtures/`.

## Prerequisites

- Authenticated CLI (`codex`, `claude`, `gemini`, or `opencode`) with quota
  the operator is willing to spend: 54 runs per host (3 conditions x
  6 categories x 3 repetitions), each run making several model calls.
- Pinned model and configuration, recorded for every run; never change models
  between conditions. Export it as `HYDRA_BENCH_MODEL`.
- Isolated fixture Python (system Python is never modified):
  `bash bench/bootstrap.sh` creates `bench/.venv/` (git-ignored) with pytest.
  Checks honor `HYDRA_BENCH_PYTHON`, defaulting to `python3`.
- Baseline Hydra instructions pinned at `bf8f80a`; optimized instructions are
  the current working tree.

## Baseline worktree

Baseline-condition runs must read baseline instructions, not the current
tree. Prepare once per benchmark:

```bash
git worktree add /tmp/opencode/hydra-baseline bf8f80a
cd /tmp/opencode/hydra-baseline
bash scripts/setup.sh --cli <cli> --project /tmp/opencode/hydra-baseline
```

Pass that directory as `--baseline-dir`. All baseline fixture copies live
under `<baseline-dir>/smoke-runs/` (or per-run temp dirs for the full
matrix); benchmark work copies never touch the Hydra source repository.

## Smoke tests (quota-gated)

```bash
bash scripts/hydra-bench.sh --init --dir /tmp/opencode/smoke --host opencode \
  --fixtures bench/fixtures
bash scripts/hydra-smoke.sh --dir /tmp/opencode/smoke \
  --baseline-dir /tmp/opencode/hydra-baseline --model <pinned-model>
```

Without `HYDRA_LIVE_APPROVED=1`, the smoke script prints its exact plan and
stops. With approval it runs Test A (Tier 0 direct `hydra-work`, zero heads,
on small-fix), Tier 1 (`hydra-plan` with exactly two heads, then authorized
`hydra-work`, on bounded-review), and Tier 2 (`hydra-plan` with three heads,
then authorized `hydra-work`, on cross-component), each across
single/baseline/optimized. `--tasks` selects a subset; `--max-runs` and
`HYDRA_SMOKE_TIME_BUDGET_S` enforce fail-closed run and total-time caps
(per-run timeout is 1800 s). Token and spend caps cannot be enforced by the
host CLI: set provider-side budget caps and supervise execution.

Execution deadline: a monotonic clock tracks one shared total budget across
all runs, stages, and conditions (single, baseline, optimized) — it is never
reset between runs. Before every CLI invocation the script computes
`remaining = budget - elapsed` and enforces
`effective_timeout = min(1800 s, remaining whole seconds)`; nothing starts
with less than one whole second left. On timeout the CLI process group is
terminated (TERM, a bounded `HYDRA_SMOKE_KILL_GRACE_S` grace period defaulting
to 10 s, then KILL via `setsid` isolation where available), leftover group
members are swept so no CLI child outlives its run, transcripts are kept, and
the ledger records `acceptance=timeout`. A run that never starts (budget
already exhausted, or `--max-runs` reached) is recorded `not_executed`
(explicitly not a result) and the script stops without further model calls. Wall-clock overrun past the shared
deadline is bounded by the kill grace period plus timer granularity; D-state
(uninterruptible) processes and remote provider-side execution cannot be
bounded by this script. Wall-time limits are unrelated to token or monetary
spending, which this script cannot hard-cap.

Ledger outcomes: `pass` (checks green), `fail` (checks red), `timeout` (a
started stage hit its effective timeout), `incomplete` (planning ran but the
work stage never started), `not_executed` (a planned run never started).
Re-running into the same bench directory never reuses a run id (attempt
suffixes `-a1`, …). `agent_calls` counts top-level CLI model invocations per
run (1 for single/Tier 0, up to 2 for planning tiers); in-session head and
verification calls stay `unknown` unless the host reports them. The report
prints per-group outcome counts, medians over measured elapsed times only,
and guarded time-improvement / model-call-reduction percentages (`unknown`
on missing data or zero denominators, never fabricated).

Smallest practical live smoke (6 runs: Tier 0 + Tier 1, all conditions):

```bash
bash scripts/hydra-bench.sh --init --dir /tmp/opencode/smoke --host opencode \
  --fixtures bench/fixtures
HYDRA_LIVE_APPROVED=1 HYDRA_SMOKE_MAX_RUNS=6 HYDRA_SMOKE_TIME_BUDGET_S=3600 \
bash scripts/hydra-smoke.sh --dir /tmp/opencode/smoke \
  --baseline-dir /tmp/opencode/hydra-baseline --model <pinned-model> \
  --tasks small-fix,bounded-review
bash scripts/hydra-bench.sh --report --dir /tmp/opencode/smoke
```

Invocation accounting for the six-run smoke (verified by regression test):
6 benchmark runs → 8 top-level CLI model invocations (2 single + 2 Tier 0
work + 2 × (Tier 1 plan + work)), plus one no-model `opencode --version`
probe. Internal model requests (planning heads, verification, repairs) fan
out inside those sessions and stay `unknown` unless the host reports them;
estimate ~30–50 total model calls. Token usage is estimated only, never an
enforceable limit.
```

Exit gate before any wider benchmark: routing matches the tier, boundary
violations absent from transcripts, verification evidence recorded, telemetry
present, spend within approved limits. Test C (task/task*/subagent runtime
mapping) is read from Test B transcripts: confirm the planner actually
delegated to heads and work actually reached verification.

## One run

1. Create a fresh disposable directory; copy one fixture's `starting/` into it
   (never run inside `bench/fixtures/` itself).
2. Start a new CLI session in that directory and paste `prompt.md`:
   - **single**: work the prompt directly, no Hydra roles.
   - **baseline**: follow the Hydra instructions from the pinned baseline.
   - **optimized**: follow the Hydra instructions from the current tree.
3. Keep the model, permissions, and CLI version identical across conditions.
   Reset the fixture copy before every run; rotate condition order per
   repetition (the harness `--init` writes the rotated order).
4. Evaluate `acceptance.md` with the same independent evaluator for all
   conditions. Time with a monotonic clock from request through final
   verification; count parallel overlap once.
5. Record the run (missing telemetry stays `unknown`):

```bash
bash scripts/hydra-bench.sh --record --dir <bench-dir> \
  --run-id <condition>-<task>-rep<N> --task <task> --condition <condition> \
  --rep <N> --host <cli> --model <pinned-model> \
  --cli-version <version> --workflow <single-agent|baseline-hydra|optimized-hydra> \
  --elapsed <seconds> --acceptance pass \
  [--planning <s> --implementation <s> --verification <s> --repair <s> \
   --routing <s> --in-tokens <n> --out-tokens <n> --dup-tokens <n|unknown> \
   --agent-calls <n> --tool-calls <n> --repair-loops <n> --security pass|fail|na]
```

6. After all runs: `bash scripts/hydra-bench.sh --report --dir <bench-dir>`.

## Fixture map

| Harness task | Fixture | Tier | Check |
| --- | --- | --- | --- |
| small-fix | bench/fixtures/small-fix | Tier 0 | pytest |
| bounded-review | bench/fixtures/bounded-review | Tier 1 | pytest |
| cross-component | bench/fixtures/cross-component | Tier 2 | pytest + no duplicate rate literal |
| refactor | bench/fixtures/refactor | Tier 2 | pytest + single shared implementation |
| security-api | bench/fixtures/security-api | Tier 1–2 | pytest + no hardcoded token literal |
| debugging | bench/fixtures/debugging | Tier 1–2 | pytest |

All fixtures use inert placeholder secrets only. Every `checks.sh` fails on
its `starting/` copy and passes on the intended fix (validated 2026-10-08).
`--dry-run` output is harness validation only and must never be reported as a
performance result.
