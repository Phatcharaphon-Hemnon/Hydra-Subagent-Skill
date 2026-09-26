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


if __name__ == "__main__":
    unittest.main()
