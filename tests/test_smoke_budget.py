"""Fail-closed time-budget enforcement for scripts/hydra-smoke.sh.

Uses a fake `opencode` binary (controlled sleeps, call log, lingering child
processes) so no test consumes API quota or touches the network.
"""

import csv
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SMOKE = PACKAGE / "scripts" / "hydra-smoke.sh"
BENCH = PACKAGE / "scripts" / "hydra-bench.sh"

FAKE_OPENCODE = """#!/usr/bin/env bash
# Fake opencode: no network, no quota. Controlled sleeps only.
if [[ "$1" == "--version" ]]; then echo "opencode-test v0"; exit 0; fi
echo "CALL $*" >> "${FAKE_CALL_LOG:?}"
agent=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "--agent" ]]; then agent="$arg"; fi
  prev="$arg"
done
case "$agent" in
  build) nap="${FAKE_SLEEP_BUILD:-$FAKE_RUN_SLEEP}" ;;
  *) nap="${FAKE_RUN_SLEEP:-60}" ;;
esac
exec -a hydra-test-sleeper sleep "${FAKE_CHILD_SLEEP:-300}" &
sleep "$nap"
"""


def sleeper_processes():
    result = subprocess.run(["pgrep", "-f", "[h]ydra-test-sleeper"],
                            capture_output=True, text=True, timeout=10)
    return [line for line in result.stdout.splitlines() if line.strip()]


class SmokeBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hydra-smoke-budget-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.fakebin = self.base / "fakebin"
        self.fakebin.mkdir()
        (self.fakebin / "opencode").write_text(FAKE_OPENCODE)
        (self.fakebin / "opencode").chmod(0o755)
        self.call_log = self.base / "calls.log"
        self.call_log.write_text("")
        self.env = os.environ.copy()
        self.env["PATH"] = str(self.fakebin) + os.pathsep + self.env["PATH"]
        self.env["HYDRA_LIVE_APPROVED"] = "1"
        self.env["FAKE_CALL_LOG"] = str(self.call_log)
        venv_python = PACKAGE / "bench" / ".venv" / "bin" / "python"
        if venv_python.exists():
            self.env["HYDRA_BENCH_PYTHON"] = str(venv_python)
        self.bench_dir = str(self.base / "bench")
        self.baseline = self.base / "baseline"
        for stub in (".agents/skills/hydra-review/SKILL.md",
                     ".opencode/agent/hydra-plan.md",
                     ".opencode/agent/hydra-work.md",
                     ".opencode/agent/hydra-verify.md"):
            path = self.baseline / stub
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stub\n")
        init = subprocess.run(
            ["bash", str(BENCH), "--init", "--dir", self.bench_dir,
             "--host", "opencode", "--fixtures", str(PACKAGE / "bench" / "fixtures")],
            text=True, capture_output=True, timeout=30, env=self.env)
        self.assertEqual(init.returncode, 0, init.stderr)

    def run_smoke(self, *args, extra_env=None):
        env = dict(self.env)
        env.update(extra_env or {})
        return subprocess.run(
            ["bash", str(SMOKE), "--dir", self.bench_dir, "--model", "test-model",
             "--baseline-dir", str(self.baseline), *args],
            text=True, capture_output=True, timeout=300, env=env)

    def ledger_rows(self):
        with open(Path(self.bench_dir) / "ledger.csv") as handle:
            return list(csv.DictReader(handle))

    def run_calls(self):
        return [line for line in self.call_log.read_text().splitlines()
                if " run " in line]

    def test_long_run_bounded_by_remaining_budget(self):
        env = {"FAKE_RUN_SLEEP": "60", "HYDRA_SMOKE_TIME_BUDGET_S": "8"}
        start = time.monotonic()
        result = self.run_smoke("--tasks", "small-fix", extra_env=env)
        wall = time.monotonic() - start
        self.assertEqual(result.returncode, 1)
        rows = self.ledger_rows()
        # First run hits the effective timeout; the rest are recorded
        # not_executed and no further model calls begin.
        by_outcome = {}
        for r in rows:
            by_outcome[r["acceptance"]] = by_outcome.get(r["acceptance"], 0) + 1
        self.assertEqual(by_outcome.get("timeout"), 1)
        self.assertEqual(by_outcome.get("not_executed"), 2)
        self.assertEqual(len(rows), 3)
        elapsed = float(rows[0]["elapsed_s"])
        self.assertGreaterEqual(elapsed, 7.0)
        self.assertLess(elapsed, 1800.0)
        self.assertEqual(len(self.run_calls()), 1)
        self.assertLess(wall, 8 + 10 + 15)
        self.assertEqual(sleeper_processes(), [])

    def test_zero_budget_starts_nothing(self):
        result = self.run_smoke("--tasks", "small-fix",
                                extra_env={"HYDRA_SMOKE_TIME_BUDGET_S": "0"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("exhausted", result.stdout)
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["acceptance"] == "not_executed" for r in rows))
        self.assertEqual(self.run_calls(), [])

    def test_max_runs_zero_starts_nothing(self):
        result = self.run_smoke("--tasks", "small-fix", "--max-runs", "0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("max_runs=0 reached", result.stdout)
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["acceptance"] == "not_executed" for r in rows))
        self.assertEqual(self.run_calls(), [])

    def test_budget_shared_across_conditions(self):
        # Budget 2s with 1s runs: executed rows plus not_executed rows cover
        # the whole plan; the shared deadline (never reset) stops the rest.
        env = {"FAKE_RUN_SLEEP": "1", "HYDRA_SMOKE_TIME_BUDGET_S": "2"}
        result = self.run_smoke("--tasks", "small-fix", extra_env=env)
        self.assertEqual(result.returncode, 1)
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 3)
        executed = [r for r in rows if r["acceptance"] != "not_executed"]
        skipped = [r for r in rows if r["acceptance"] == "not_executed"]
        self.assertGreaterEqual(len(executed), 1)
        self.assertGreaterEqual(len(skipped), 1)
        total = sum(float(r["elapsed_s"]) for r in executed)
        self.assertLessEqual(total, 2 + 10 + 5)
        self.assertEqual(len(self.run_calls()), len(executed))
        self.assertEqual(sleeper_processes(), [])

    def test_fitting_runs_complete_and_report(self):
        env = {"FAKE_RUN_SLEEP": "1", "HYDRA_SMOKE_TIME_BUDGET_S": "60"}
        result = self.run_smoke("--tasks", "small-fix", extra_env=env)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["acceptance"] != "not_executed" for r in rows))
        self.assertEqual(len(self.run_calls()), 3)
        self.assertTrue(all(r["agent_calls"] == "1" for r in rows))
        report = subprocess.run(
            ["bash", str(BENCH), "--report", "--dir", self.bench_dir],
            text=True, capture_output=True, timeout=30, env=self.env)
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertEqual(sleeper_processes(), [])

    def test_mid_run_abort_marks_incomplete(self):
        # Single finishes instantly (build naps 0); the baseline plan fits but
        # the work stage cannot start: the partial result is incomplete (not
        # fail), the rest is not_executed, and work is never invoked.
        env = {"FAKE_RUN_SLEEP": "2", "FAKE_SLEEP_BUILD": "0",
               "HYDRA_SMOKE_TIME_BUDGET_S": "3"}
        result = self.run_smoke("--tasks", "bounded-review", extra_env=env)
        self.assertEqual(result.returncode, 1)
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["acceptance"], "fail")
        self.assertEqual(rows[1]["acceptance"], "incomplete")
        self.assertEqual(rows[2]["acceptance"], "not_executed")
        agents = [line.split("--agent ")[1].split()[0] for line in self.run_calls()]
        self.assertEqual(agents, ["build", "hydra-plan"])
        self.assertEqual(sleeper_processes(), [])

    def test_cli_receives_agent_name_and_prompt_content(self):
        # Regression: a past `shift` bug sent the prompt path as the agent
        # name and an empty prompt. The fake CLI would have hidden it.
        env = {"FAKE_RUN_SLEEP": "0", "HYDRA_SMOKE_TIME_BUDGET_S": "60"}
        result = self.run_smoke("--tasks", "small-fix", "--max-runs", "1",
                                extra_env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("max_runs=1 reached", result.stdout)
        calls = self.run_calls()
        self.assertEqual(len(calls), 1)
        log = self.call_log.read_text()
        self.assertIn("--agent build", log)
        self.assertIn("total(", log)
        self.assertNotIn("prompt.txt", log)

    def test_six_run_smoke_makes_exactly_eight_model_invocations(self):
        # Six-run plan: 2 single + 2 Tier0-work + 2x(plan+work) = 8 top-level
        # CLI model invocations. Internal head/verify calls are the agent's
        # own and remain unknown; only top-level invocations are counted.
        env = {"FAKE_RUN_SLEEP": "0", "FAKE_SLEEP_BUILD": "0",
               "HYDRA_SMOKE_TIME_BUDGET_S": "3600"}
        result = self.run_smoke("--tasks", "small-fix,bounded-review",
                                extra_env=env)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        calls = self.run_calls()
        self.assertEqual(len(calls), 8)
        agents = [line.split("--agent ")[1].split()[0] for line in calls]
        self.assertEqual(agents, ["build", "hydra-work", "hydra-work",
                                 "build", "hydra-plan", "hydra-work",
                                 "hydra-plan", "hydra-work"])
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 6)
        self.assertEqual([r["agent_calls"] for r in rows],
                         ["1", "1", "1", "1", "2", "2"])
        self.assertEqual(sleeper_processes(), [])

    def test_duplicate_run_ids_get_attempt_suffix(self):
        pre = subprocess.run(
            ["bash", str(BENCH), "--record", "--dir", self.bench_dir,
             "--run-id", "smoke-single-small-fix-rep1",
             "--task", "small-fix", "--condition", "single",
             "--rep", "1", "--host", "opencode",
             "--elapsed", "1.0", "--acceptance", "pass"],
            text=True, capture_output=True, timeout=30, env=self.env)
        self.assertEqual(pre.returncode, 0, pre.stderr)
        env = {"FAKE_RUN_SLEEP": "1", "HYDRA_SMOKE_TIME_BUDGET_S": "60"}
        result = self.run_smoke("--tasks", "small-fix", extra_env=env)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        ids = [r["run_id"] for r in self.ledger_rows()
               if r["task"] == "small-fix" and r["condition"] == "single"]
        self.assertIn("smoke-single-small-fix-rep1", ids)
        self.assertIn("smoke-single-small-fix-rep1-a1", ids)

    def test_no_job_control_assumption_is_documented(self):
        help_text = subprocess.run(
            ["bash", str(SMOKE), "--help"],
            text=True, capture_output=True, timeout=30, env=self.env)
        self.assertEqual(help_text.returncode, 0)
        self.assertIn("job control", help_text.stdout)
        self.assertIn("set -m", help_text.stdout)

    def test_baseline_missing_agent_file_is_refused(self):
        (self.baseline / ".opencode" / "agent" / "hydra-plan.md").unlink()
        env = dict(self.env)
        env["HYDRA_LIVE_APPROVED"] = "1"
        result = subprocess.run(
            ["bash", str(SMOKE), "--dir", self.bench_dir, "--model", "m",
             "--baseline-dir", str(self.baseline)],
            text=True, capture_output=True, timeout=60, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Baseline instructions missing", result.stderr)
        self.assertEqual(self.run_calls(), [])


if __name__ == "__main__":
    unittest.main()
