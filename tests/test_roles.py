"""Parse native role permissions; these checks do not simulate model behavior."""

import fnmatch
import json
import os
import re
import shutil
import subprocess
import tomllib
import unittest
from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
HEADS = {f"hydra-{lens}" for lens in (
    "architecture", "correctness", "security", "performance", "maintainability"
)}


def markdown_config(path):
    text = path.read_text()
    _, frontmatter, body = text.split("---\n", 2)
    return yaml.safe_load(frontmatter), body


class RoleTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("HYDRA_NATIVE_ROLE_CHECK") == "1" and shutil.which("opencode"),
                         "set HYDRA_NATIVE_ROLE_CHECK=1 to check installed OpenCode")
    def test_native_opencode_effective_permissions(self):
        result = subprocess.run(["opencode", "debug", "agents"], cwd=PACKAGE,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        agents = {entry["id"]: entry.get("permissions", [])
                  for entry in json.loads(result.stdout)
                  if entry.get("id", "").startswith("hydra-")}
        self.assertTrue(HEADS | {"hydra-plan", "hydra-work", "hydra-verify"} <= set(agents))

        def effect(name, action, resource):
            matching = [rule for rule in agents[name]
                        if fnmatch.fnmatchcase(action, rule["action"])
                        and fnmatch.fnmatchcase(resource, rule["resource"])]
            return matching[-1]["effect"] if matching else "ask"

        for name in HEADS | {"hydra-plan"}:
            for tool, target in (("edit", "example.txt"), ("shell", "touch example.txt"),
                                 ("mcp_example_write", "example.txt")):
                with self.subTest(agent=name, tool=tool):
                    self.assertEqual(effect(name, tool, target), "deny")
            # Delegation tool is "task"; "task*" rules glob-match it.
            for delegate in HEADS | {"hydra-work", "hydra-verify", "hydra-plan", "unknown"}:
                expected = "allow" if name == "hydra-plan" and delegate in HEADS else "deny"
                self.assertEqual(effect(name, "task", delegate), expected)
        self.assertEqual(effect("hydra-work", "edit", "example.txt"), "allow")
        self.assertEqual(effect("hydra-plan", "external_directory",
                                "/tmp/user/.agents/skills/hydra-review/SKILL.md"), "allow")
        self.assertEqual(effect("hydra-plan", "external_directory", "/tmp/unrelated"), "deny")
        for delegate in HEADS | {"hydra-plan", "hydra-verify", "unknown"}:
            # The host translates the "task:" map into "subagent" rules.
            self.assertEqual(effect("hydra-work", "subagent", delegate),
                             "allow" if delegate == "hydra-verify" else "deny")

    def test_opencode_planning_is_read_only_transitively(self):
        for name in HEADS | {"hydra-plan"}:
            with self.subTest(agent=name):
                config, _ = markdown_config(PACKAGE / f".opencode/agent/{name}.md")
                permissions = config["permission"]
                self.assertEqual(permissions["*"], "deny")
                self.assertEqual(permissions["edit"], "deny")
                self.assertEqual(permissions["bash"], "deny")
                self.assertEqual(permissions["read"], "allow")
                if name == "hydra-plan":
                    self.assertEqual(permissions["task"], "deny")
                    self.assertEqual({k for k, v in permissions["task*"].items()
                                      if v == "allow"}, HEADS)
                    self.assertEqual(permissions["task*"]["*"], "deny")
                else:
                    self.assertEqual(permissions["task"], "deny")

    def test_opencode_work_can_edit_and_delegate_only_verification(self):
        config, _ = markdown_config(PACKAGE / ".opencode/agent/hydra-work.md")
        self.assertEqual(config["permission"]["edit"], "allow")
        task = config["permission"]["task"]
        self.assertEqual(task["*"], "deny")
        self.assertEqual({k for k, v in task.items() if v == "allow"}, {"hydra-verify"})

    def test_codex_sandbox_and_no_escalation(self):
        for name in HEADS | {"hydra-plan", "hydra-work"}:
            with self.subTest(agent=name):
                config = tomllib.loads((PACKAGE / f".codex/agents/{name}.toml").read_text())
                self.assertEqual(config["name"], name)
                self.assertEqual(config["sandbox_mode"],
                                 "workspace-write" if name == "hydra-work" else "read-only")
                if name == "hydra-plan":
                    self.assertEqual(config["approval_policy"], "never")

    def test_claude_explicit_tool_and_delegate_allowlists(self):
        for name in HEADS | {"hydra-plan", "hydra-work"}:
            config, _ = markdown_config(PACKAGE / f".claude/agents/{name}.md")
            tools = config["tools"]
            if name in HEADS:
                self.assertEqual({t.strip() for t in tools.split(",")}, {"Read", "Grep", "Glob"})
            else:
                basic, delegates = tools.split("Agent(")
                delegates = {t.strip() for t in delegates.rstrip(")").split(",")}
                self.assertEqual(delegates, HEADS if name == "hydra-plan" else {"hydra-verify"})
                self.assertEqual({t.strip() for t in basic.rstrip(", ").split(",")},
                                 {"Read", "Grep", "Glob"} if name == "hydra-plan" else
                                 {"Read", "Grep", "Glob", "Edit", "Write", "Bash"})

    def test_gemini_explicit_tools_without_nested_delegation(self):
        read_tools = {"read_file", "list_directory", "glob", "grep_search"}
        for name in HEADS | {"hydra-plan", "hydra-work"}:
            config, body = markdown_config(PACKAGE / f".gemini/agents/{name}.md")
            expected = read_tools | ({"write_file", "replace", "run_shell_command"}
                                     if name == "hydra-work" else set())
            self.assertEqual(set(config["tools"]), expected)
            if name in ("hydra-plan", "hydra-work"):
                self.assertIn("Gemini subagents cannot delegate", body)

    def test_work_profiles_require_authorization_not_handoff(self):
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                if cli == "codex":
                    body = tomllib.loads((PACKAGE / ".codex/agents/hydra-work.toml").read_text())["developer_instructions"]
                else:
                    folder = "agent" if cli == "opencode" else "agents"
                    _, body = markdown_config(PACKAGE / f".{cli}/{folder}/hydra-work.md")
                for rule in ("explicit user authorization", "handoff is optional", "brief scope",
                             "Before any mutation", "stop before mutation",
                             "never ask for duplicate approval", "Never create a new plan",
                             "request authorization", "hydra-verify"):
                    self.assertIn(rule, body)

    def test_command_formats_and_routing(self):
        _, claude = markdown_config(PACKAGE / ".claude/commands/hydra.md")
        gemini = tomllib.loads((PACKAGE / ".gemini/commands/hydra.toml").read_text())["prompt"]
        self.assertIn("$ARGUMENTS", claude)
        self.assertIn("{{args}}", gemini)
        self.assertIn("claude --agent hydra-plan", claude)
        self.assertIn("never spawn them as", claude)
        self.assertIn("Gemini subagents cannot delegate", gemini)
        for command in (claude, gemini):
            self.assertIn("planning-only", command)
            self.assertIn("hydra-work", command)
            self.assertIn("hydra-verify", command)


class AdaptivePolicyTests(unittest.TestCase):
    """Instruction/configuration consistency, not a simulation of model routing."""

    @staticmethod
    def body(cli, name):
        if cli == "codex":
            return tomllib.loads((PACKAGE / f".codex/agents/{name}.toml").read_text())["developer_instructions"]
        folder = "agent" if cli == "opencode" else "agents"
        return markdown_config(PACKAGE / f".{cli}/{folder}/{name}.md")[1]

    @staticmethod
    def table(text, header):
        lines = text[text.index(header):].splitlines()[2:]
        rows = []
        for line in lines:
            if not line.startswith("|"):
                break
            rows.append(tuple(cell.strip() for cell in line.strip("|").split("|")))
        return rows

    def test_canonical_routing_and_required_lenses(self):
        text = (PACKAGE / ".agents/skills/hydra-review/SKILL.md").read_text()
        rows = self.table(text, "| Task class |")
        self.assertEqual([(r[0], int(r[1])) for r in rows], [
            ("Bounded low-risk", 2), ("Broader", 3),
            ("Comprehensive or high-risk architecture", 5)])
        for term in ("Limited affected area", "clear acceptance", "no broad architectural", "no comprehensive"):
            self.assertIn(term, rows[0][2])
        for term in ("Cross-component", "unclear root", "refactors", "integration", "performance investigations"):
            self.assertIn(term, rows[1][2])
        self.assertIn("Explicit comprehensive/full review", rows[2][2])
        self.assertIn("broad, architectural, and high-risk", rows[2][2])
        lenses = {r[0]: r[1:] for r in self.table(text, "| Task property |")}
        self.assertEqual(lenses, {
            "Behavior-changing": ("correctness", "Required"),
            "Security-sensitive": ("security", "Required"),
            "Performance-focused": ("performance", "Normally include"),
            "Architectural": ("architecture", "Normally include")})

    def test_adapter_contracts_and_verification_evidence(self):
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                plan = self.body(cli, "hydra-plan")
                self.assertIn("adaptive head selection policy", plan)
                for name in HEADS:
                    head = self.body(cli, name)
                    for rule in ("250 words", "three material", "evidence-backed", "No relevant concern", "chain-of-thought"):
                        self.assertIn(rule, head)
                work = self.body(cli, "hydra-work")
                for field in ("changed files/components", "checked code/worktree/revision state", "untracked files", "check commands", "exit codes", "failures", "checks not executed", "coverage gaps"):
                    self.assertIn(field, work)
                verify = self.body(cli, "hydra-verify")
                for rule in ("same code state", "command and result", "coverage is adequate", "Independently inspect", "stale pre-repair", "do not edit project source" if cli != "codex" else "must not edit project source"):
                    self.assertIn(rule.lower(), verify.lower())
                self.assertIn("weaken tests", verify)
                self.assertIn("do not reuse unsupported checks", verify)
        router = tomllib.loads((PACKAGE / ".gemini/commands/hydra.toml").read_text())["prompt"]
        for rule in ("adaptive head selection policy", "2 relevant heads", "3 for broader", "5 only", "correctness", "security", "compact factual packet", "updated checked"):
            self.assertIn(rule, router)

    def test_verifier_native_configs_preserve_separation(self):
        opencode, _ = markdown_config(PACKAGE / ".opencode/agent/hydra-verify.md")
        for tool in ("edit", "task"):
            self.assertEqual(opencode["permission"][tool], "deny")
        claude, _ = markdown_config(PACKAGE / ".claude/agents/hydra-verify.md")
        self.assertEqual({t.strip() for t in claude["tools"].split(",")},
                         {"Read", "Grep", "Glob", "Bash"})
        gemini, _ = markdown_config(PACKAGE / ".gemini/agents/hydra-verify.md")
        self.assertEqual(set(gemini["tools"]),
                         {"read_file", "list_directory", "glob", "grep_search", "run_shell_command"})
        codex = tomllib.loads((PACKAGE / ".codex/agents/hydra-verify.toml").read_text())
        self.assertEqual(codex["sandbox_mode"], "workspace-write")
        self.assertIn("must not edit project source or weaken tests", codex["developer_instructions"])

    def test_scoped_handoff_carries_facts_and_uncertainties(self):
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                plan = self.body(cli, "hydra-plan")
                for term in ("source references", "established facts", "relevant uncertainties",
                             "acceptance criteria"):
                    self.assertIn(term, plan)
                work = self.body(cli, "hydra-work")
                self.assertIn("Re-read the handed-off source before editing", work)
                self.assertIn("without pulling in redundant planning transcripts", work)

    def test_scheduling_and_check_serialization(self):
        serial = ("Run independent checks concurrently only when resources and mutable fixtures, "
                  "caches, outputs, and services cannot conflict; otherwise run them sequentially.")
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                plan = self.body(cli, "hydra-plan")
                self.assertIn("parallel within host limits", plan)
                self.assertIn("batch independent reads", plan)
                self.assertIn("every check result before verification", self.body(cli, "hydra-work"))
                for name in ("hydra-work", "hydra-verify"):
                    self.assertIn(serial, self.body(cli, name))

    def test_routing_dispatch_and_session_boundaries(self):
        claude = markdown_config(PACKAGE / ".claude/commands/hydra.md")[1]
        gemini = tomllib.loads((PACKAGE / ".gemini/commands/hydra.toml").read_text())["prompt"]
        for text in (claude, gemini):
            self.assertIn("parallel within host limits", text)
            self.assertIn("handoff is optional", text)
        # Claude's main-session boundary is unchanged.
        self.assertIn("claude --agent hydra-plan", claude)
        self.assertIn("never spawn them as", claude)
        # Gemini's main-session routing is unchanged.
        self.assertIn("Gemini subagents cannot delegate", gemini)
        self.assertIn("updated checked", gemini)

    def test_role_permissions_unchanged_by_latency_work(self):
        """Latency edits must not loosen any role's permission surface."""
        self.assertEqual(markdown_config(PACKAGE / ".opencode/agent/hydra-plan.md")[0]["permission"]["edit"], "deny")
        self.assertEqual(markdown_config(PACKAGE / ".opencode/agent/hydra-work.md")[0]["permission"]["edit"], "allow")
        self.assertEqual(markdown_config(PACKAGE / ".opencode/agent/hydra-verify.md")[0]["permission"]["edit"], "deny")
        self.assertEqual(tomllib.loads((PACKAGE / ".codex/agents/hydra-plan.toml").read_text())["sandbox_mode"],
                         "read-only")
        plan_tools = {t.strip() for t in
                      markdown_config(PACKAGE / ".claude/agents/hydra-plan.md")[0]["tools"].split("Agent(")[0].rstrip(", ").split(",")}
        self.assertEqual(plan_tools, {"Read", "Grep", "Glob"})
        for name in ("hydra-plan", "hydra-verify"):
            self.assertNotIn("write_file", set(markdown_config(PACKAGE / f".gemini/agents/{name}.md")[0]["tools"]))
        self.assertIn("write_file", set(markdown_config(PACKAGE / ".gemini/agents/hydra-work.md")[0]["tools"]))

    def test_no_stale_fixed_head_count_and_valid_workflow_asset(self):
        paths = [PACKAGE / "README.md", PACKAGE / ".agents/skills/hydra-review/SKILL.md"]
        for folder in (".codex/agents", ".claude/agents", ".claude/commands", ".gemini/agents", ".gemini/commands", ".opencode/agent", "docs"):
            paths.extend(p for p in (PACKAGE / folder).rglob("*") if p.is_file())
        stale = re.compile(r"3\s*[-–—]\s*5\s+(?:relevant\s+|independent\s+|planning\s+)*heads", re.I)
        for path in paths:
            with self.subTest(path=path.relative_to(PACKAGE)):
                self.assertIsNone(stale.search(path.read_text()))
        import xml.etree.ElementTree as ET
        svg = ET.parse(PACKAGE / "docs/assets/hydra-flow.svg")
        text = " ".join(svg.getroot().itertext())
        for term in ("2 / 3 / 5", "classify scope/risk", "authorization gate", "reverify"):
            self.assertIn(term, text)


class FastPathAndSecurityTests(unittest.TestCase):
    """Tier 0 fast path and lazy security-skill routing contracts."""

    def test_tier_table_and_fast_path(self):
        text = (PACKAGE / ".agents/skills/hydra-review/SKILL.md").read_text()
        for term in ("Tier 0", "Tier 1", "Tier 2", "Tier 3",
                     "Skip multi-agent planning entirely",
                     "reclassify to Tier 1",
                     "proportional verification"):
            self.assertIn(term, text)
        self.assertIn("independent of head count", text)

    def test_adapters_route_tier_zero(self):
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                self.assertIn("Tier 0 tasks bypass planning entirely",
                              AdaptivePolicyTests.body(cli, "hydra-plan"))
                self.assertIn("Tier 0 tasks enter here directly",
                              AdaptivePolicyTests.body(cli, "hydra-work"))
        claude = markdown_config(PACKAGE / ".claude/commands/hydra.md")[1]
        gemini = tomllib.loads((PACKAGE / ".gemini/commands/hydra.toml").read_text())["prompt"]
        for command in (claude, gemini):
            self.assertIn("Tier 0", command)

    def test_security_discovery_contract(self):
        text = (PACKAGE / ".agents/skills/hydra-review/SKILL.md").read_text()
        for term in ("docs/SECURITY-SKILLS.md",
                     "untrusted instructions",
                     "grants no shell",
                     "never copy it into an auto-discovered skills directory",
                     "Offensive procedures apply only within explicitly authorized scope"):
            self.assertIn(term, text)
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                self.assertIn("docs/SECURITY-SKILLS.md",
                              AdaptivePolicyTests.body(cli, "hydra-plan"))
                self.assertIn("never the whole external library",
                              AdaptivePolicyTests.body(cli, "hydra-work"))

    def test_converge_once_and_required_reviews(self):
        text = (PACKAGE / ".agents/skills/hydra-review/SKILL.md").read_text()
        self.assertIn("Converge once", text)
        self.assertIn("Never cancel a required independent review purely for speed", text)

    def test_verify_security_acceptance(self):
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                self.assertIn("security acceptance criteria",
                              AdaptivePolicyTests.body(cli, "hydra-verify"))


if __name__ == "__main__":
    unittest.main()
