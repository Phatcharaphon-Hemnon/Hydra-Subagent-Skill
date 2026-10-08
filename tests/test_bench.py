"""Checks for the benchmark harness (structure and math, not model runs)."""

import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
BENCH = PACKAGE / "scripts/hydra-bench.sh"


class BenchHarnessTests(unittest.TestCase):
    def run_bench(self, *args):
        return subprocess.run(
            ["bash", str(BENCH), *args],
            text=True,
            capture_output=True,
            timeout=60,
        )

    def test_matrix_lists_45_runs_per_host(self):
        result = self.run_bench("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in result.stdout.splitlines() if line and not line.startswith("Total")]
        fixture_dirs = sorted(p.name for p in (PACKAGE / "bench" / "fixtures").iterdir()
                              if p.is_dir())
        self.assertEqual(len(lines), 3 * len(fixture_dirs) * 3)
        self.assertIn(f"Total per host: {3 * len(fixture_dirs) * 3} runs", result.stdout)
        for condition in ("single", "baseline", "optimized"):
            self.assertIn(condition, result.stdout)
        for category in ("small-fix", "cross-component", "refactor", "security-api", "debugging"):
            self.assertIn(category, result.stdout)

    def test_init_record_report_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            init = self.run_bench("--init", "--dir", bench_dir, "--host", "codex")
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertEqual(sum(1 for _ in open(Path(bench_dir) / "run-order.txt")), 54)
            for condition, elapsed in (("baseline", "10.0"), ("optimized", "5.0")):
                record = self.run_bench(
                    "--record", "--dir", bench_dir,
                    "--run-id", f"{condition}-small-fix-rep1",
                    "--task", "small-fix", "--condition", condition,
                    "--rep", "1", "--host", "codex",
                    "--elapsed", elapsed, "--acceptance", "pass",
                    "--security", "na",
                    "--in-tokens", "100", "--out-tokens", "50",
                    "--agent-calls", "1", "--tool-calls", "4",
                )
                self.assertEqual(record.returncode, 0, record.stderr)
            report = self.run_bench("--report", "--dir", bench_dir)
            self.assertEqual(report.returncode, 0, report.stderr)
            # Speedup = Baseline / Optimized = 10 / 5; improvement = 50%.
            self.assertIn("speedup=2.000", report.stdout)
            self.assertIn("time_improvement_pct=50.0", report.stdout)
            with open(Path(bench_dir) / "ledger.csv") as handle:
                header = next(csv.reader(handle))
            for field in ("elapsed_s", "in_tokens", "out_tokens", "acceptance",
                          "security_result", "repair_loops"):
                self.assertIn(field, header)

    def test_missing_telemetry_stays_unknown(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            self.assertEqual(
                self.run_bench("--init", "--dir", bench_dir, "--host", "codex").returncode, 0)
            record = self.run_bench(
                "--record", "--dir", bench_dir,
                "--run-id", "single-small-fix-rep1",
                "--task", "small-fix", "--condition", "single",
                "--rep", "1", "--host", "codex",
                "--elapsed", "7.5", "--acceptance", "pass")
            self.assertEqual(record.returncode, 0, record.stderr)
            with open(Path(bench_dir) / "ledger.csv") as handle:
                row = list(csv.DictReader(handle))[0]
            self.assertEqual(row["in_tokens"], "unknown")
            self.assertEqual(row["security_result"], "na")
            self.assertNotIn("0", (row["in_tokens"], row["out_tokens"]))

    def test_record_rejects_incomplete_runs(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            self.assertEqual(
                self.run_bench("--init", "--dir", bench_dir, "--host", "codex").returncode, 0)
            incomplete = self.run_bench(
                "--record", "--dir", bench_dir,
                "--run-id", "x", "--task", "small-fix", "--condition", "single",
                "--rep", "1", "--host", "codex", "--acceptance", "pass")
            self.assertEqual(incomplete.returncode, 2)
            with open(Path(bench_dir) / "ledger.csv") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 0)

    def test_init_with_fixtures_validates_categories(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            good = self.run_bench("--init", "--dir", bench_dir, "--host", "codex",
                                  "--fixtures", str(PACKAGE / "bench" / "fixtures"))
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(
                (Path(bench_dir) / "fixtures.path").read_text().strip(),
                str(PACKAGE / "bench" / "fixtures"))
            bench_dir2 = str(Path(base) / "bench2")
            bad = self.run_bench("--init", "--dir", bench_dir2, "--host", "codex",
                                 "--fixtures", str(Path(base) / "absent"))
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("Missing fixture", bad.stderr)

    def test_fixtures_are_present_and_initially_failing(self):
        import shutil
        categories = sorted(p.name for p in (PACKAGE / "bench" / "fixtures").iterdir()
                            if p.is_dir())
        self.assertGreaterEqual(len(categories), 6)
        for category in categories:
            with self.subTest(category=category):
                fixture = PACKAGE / "bench" / "fixtures" / category
                for needed in ("prompt.md", "acceptance.md", "checks.sh"):
                    content = (fixture / needed).read_text().strip()
                    self.assertTrue(content, f"{category}/{needed} is empty")
                self.assertTrue((fixture / "starting").is_dir())
                syntax = subprocess.run(
                    ["bash", "-n", str(fixture / "checks.sh")],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                with tempfile.TemporaryDirectory(prefix="hydra-fixture-test-") as work:
                    shutil.copytree(fixture / "starting", Path(work) / "copy")
                    check = subprocess.run(
                        ["bash", str(fixture / "checks.sh"), str(Path(work) / "copy")],
                        capture_output=True, text=True, timeout=120)
                    self.assertNotEqual(
                        check.returncode, 0,
                        f"{category} checks.sh passes on the broken starting state")

    def test_ledger_records_model_cli_and_workflow_identity(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            self.assertEqual(
                self.run_bench("--init", "--dir", bench_dir, "--host", "opencode").returncode, 0)
            record = self.run_bench(
                "--record", "--dir", bench_dir,
                "--run-id", "optimized-small-fix-rep1",
                "--task", "small-fix", "--condition", "optimized",
                "--rep", "1", "--host", "opencode",
                "--model", "pinned-model", "--cli-version", "v9",
                "--workflow", "optimized-hydra",
                "--elapsed", "5.0", "--acceptance", "pass")
            self.assertEqual(record.returncode, 0, record.stderr)
            with open(Path(bench_dir) / "ledger.csv") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["model"], "pinned-model")
            self.assertEqual(rows[0]["cli_version"], "v9")
            self.assertEqual(rows[0]["workflow_id"], "optimized-hydra")

    def test_fixture_checks_cannot_touch_the_repo(self):
        import shutil
        import subprocess as sp
        before = sp.run(["git", "status", "--short", "bench/"], cwd=str(PACKAGE),
                        capture_output=True, text=True, timeout=15).stdout
        for category in sorted(p.name for p in (PACKAGE / "bench" / "fixtures").iterdir()
                               if p.is_dir()):
            with self.subTest(category=category):
                fixture = PACKAGE / "bench" / "fixtures" / category
                text = (fixture / "checks.sh").read_text()
                self.assertIn('"${1', text)
                self.assertNotIn("rm ", text)
                self.assertNotIn(str(PACKAGE), text)
                with tempfile.TemporaryDirectory(prefix="hydra-fixture-test-") as work:
                    shutil.copytree(fixture / "starting", Path(work) / "copy")
                    sp.run(["bash", str(fixture / "checks.sh"), str(Path(work) / "copy")],
                           capture_output=True, timeout=120)
        after = sp.run(["git", "status", "--short", "bench/"], cwd=str(PACKAGE),
                       capture_output=True, text=True, timeout=15).stdout
        self.assertEqual(before, after)

    def test_smoke_script_refuses_without_quota_approval(self):
        smoke = PACKAGE / "scripts" / "hydra-smoke.sh"
        with tempfile.TemporaryDirectory(prefix="hydra-smoke-test-") as base:
            plan = subprocess.run(
                ["bash", str(smoke), "--dir", str(Path(base) / "bench"),
                 "--model", "test-model"],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(plan.returncode, 2)
            self.assertIn("HYDRA_LIVE_APPROVED", plan.stdout)
            self.assertIn("Tier0, 0 heads", plan.stdout)
            self.assertIn("Tier1, 2 heads", plan.stdout)
            self.assertIn("Tier2, 3 heads", plan.stdout)
            self.assertIn("token/spend caps are NOT enforceable", plan.stdout)
            subset = subprocess.run(
                ["bash", str(smoke), "--dir", str(Path(base) / "bench"),
                 "--model", "test-model", "--tasks", "small-fix"],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(subset.returncode, 2)
            self.assertIn("runs=3", subset.stdout)
            self.assertNotIn("bounded-review", subset.stdout)
            bad = subprocess.run(
                ["bash", str(smoke), "--dir", str(Path(base) / "bench"),
                 "--model", "test-model", "--tasks", "nope"],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(bad.returncode, 2)

    def test_smoke_budget_gates_stop_before_any_model_call(self):
        smoke = PACKAGE / "scripts" / "hydra-smoke.sh"
        with tempfile.TemporaryDirectory(prefix="hydra-smoke-test-") as base:
            bench_dir = str(Path(base) / "bench")
            baseline = Path(base) / "baseline"
            for stub in (".agents/skills/hydra-review/SKILL.md",
                         ".opencode/agent/hydra-plan.md",
                         ".opencode/agent/hydra-work.md",
                         ".opencode/agent/hydra-verify.md"):
                path = baseline / stub
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("stub\n")
            init = subprocess.run(
                ["bash", str(PACKAGE / "scripts" / "hydra-bench.sh"),
                 "--init", "--dir", bench_dir, "--host", "opencode"],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(init.returncode, 0, init.stderr)
            env = os.environ.copy()
            env["HYDRA_LIVE_APPROVED"] = "1"
            for extra in (["--max-runs", "0"],):
                with self.subTest(extra=extra):
                    result = subprocess.run(
                        ["bash", str(smoke), "--dir", bench_dir, "--model", "m",
                         "--baseline-dir", str(baseline), *extra],
                        text=True, capture_output=True, timeout=60, env=env)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("max_runs=0 reached", result.stdout)
            env["HYDRA_SMOKE_TIME_BUDGET_S"] = "0"
            result = subprocess.run(
                ["bash", str(smoke), "--dir", bench_dir, "--model", "m",
                 "--baseline-dir", str(baseline)],
                text=True, capture_output=True, timeout=60, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn("time budget 0s exhausted", result.stdout)
            with open(Path(bench_dir) / "ledger.csv") as handle:
                rows = list(csv.DictReader(handle))
            # Aborted runs are recorded not_executed, never silently absent.
            self.assertGreater(len(rows), 0)
            self.assertTrue(all(r["acceptance"] == "not_executed" for r in rows))

    def test_report_distinguishes_outcomes_and_guards_math(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            self.assertEqual(
                self.run_bench("--init", "--dir", bench_dir, "--host", "codex").returncode, 0)
            records = [
                ("b-pass", "small-fix", "baseline", "10.0", "pass"),
                ("o-timeout", "small-fix", "optimized", "5.0", "timeout"),
                ("o-missing", "small-fix", "optimized", "unknown", "not_executed"),
                ("b-partial", "small-fix", "baseline", "4.0", "incomplete"),
            ]
            for run_id, task, condition, elapsed, acceptance in records:
                record = self.run_bench(
                    "--record", "--dir", bench_dir, "--run-id", run_id,
                    "--task", task, "--condition", condition, "--rep", "1",
                    "--host", "codex", "--elapsed", elapsed,
                    "--acceptance", acceptance)
                self.assertEqual(record.returncode, 0, record.stderr)
            report = self.run_bench("--report", "--dir", bench_dir)
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertIn("'pass': 1", report.stdout)
            self.assertIn("'timeout': 1", report.stdout)
            self.assertIn("'not_executed': 1", report.stdout)
            self.assertIn("'incomplete': 1", report.stdout)
            # Medians use measured elapsed only; zero-division is guarded.
            self.assertIn("speedup=", report.stdout)

    def test_dry_run_validates_offline(self):
        with tempfile.TemporaryDirectory(prefix="hydra-bench-test-") as base:
            bench_dir = str(Path(base) / "bench")
            result = self.run_bench("--dry-run", "--dir", bench_dir, "--host", "codex")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DRY RUN ONLY", result.stdout)
            with open(Path(bench_dir) / "ledger.csv") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 54)
            self.assertTrue(all(row["in_tokens"] == "unknown" for row in rows))


if __name__ == "__main__":
    unittest.main()
