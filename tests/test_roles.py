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
        result = subprocess.run(["opencode", "--pure", "agent", "list"], cwd=PACKAGE,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        decoder = json.JSONDecoder()
        agents = {}
        for match in re.finditer(r"^([\w-]+) \(([^)]+)\)\n", result.stdout, re.M):
            if match[1].startswith("hydra-"):
                agents[match[1]], _ = decoder.raw_decode(result.stdout[match.end():].lstrip())

        def action(name, tool, target):
            matching = [rule for rule in agents[name]
                        if fnmatch.fnmatchcase(tool, rule["permission"])
                        and fnmatch.fnmatchcase(target, rule["pattern"])]
            return matching[-1]["action"] if matching else "ask"

        for name in HEADS | {"hydra-plan"}:
            for tool, target in (("edit", "example.txt"), ("bash", "touch example.txt"),
                                 ("mcp_example_write", "example.txt")):
                with self.subTest(agent=name, tool=tool):
                    self.assertEqual(action(name, tool, target), "deny")
            for delegate in HEADS | {"hydra-work", "hydra-verify", "hydra-plan", "unknown"}:
                expected = "allow" if name == "hydra-plan" and delegate in HEADS else "deny"
                self.assertEqual(action(name, "task", delegate), expected)
        self.assertEqual(action("hydra-work", "edit", "example.txt"), "allow")
        self.assertEqual(action("hydra-plan", "external_directory",
                                "/tmp/user/.agents/skills/hydra-review/SKILL.md"), "allow")
        self.assertEqual(action("hydra-plan", "external_directory", "/tmp/unrelated"), "deny")
        for delegate in HEADS | {"hydra-plan", "hydra-verify", "unknown"}:
            self.assertEqual(action("hydra-work", "task", delegate),
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

    def test_work_profiles_have_handoff_gate_and_scope_rules(self):
        for cli in ("codex", "claude", "gemini", "opencode"):
            with self.subTest(cli=cli):
                if cli == "codex":
                    body = tomllib.loads((PACKAGE / ".codex/agents/hydra-work.toml").read_text())["developer_instructions"]
                else:
                    folder = "agent" if cli == "opencode" else "agents"
                    _, body = markdown_config(PACKAGE / f".{cli}/{folder}/hydra-work.md")
                for rule in ("Before any mutation", "stop before mutation", "never ask for duplicate approval",
                             "Never create a new plan", "request authorization", "hydra-verify"):
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


if __name__ == "__main__":
    unittest.main()
