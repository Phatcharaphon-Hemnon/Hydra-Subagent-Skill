"""Behavioral checks for Hydra's public setup commands."""

import os
import pty
import subprocess
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SETUP = PACKAGE / "scripts/setup.sh"
LEGACY = PACKAGE / "scripts/install-global.sh"


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hydra-setup-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.user = self.base / "user"
        self.xdg = self.base / "config"
        self.env = os.environ.copy()
        self.env["HYDRA_INSTALL_HOME"] = str(self.user)
        self.env["HYDRA_INSTALL_XDG_CONFIG_HOME"] = str(self.xdg)

    def run_setup(self, *args, script=SETUP):
        return subprocess.run(
            ["bash", str(script), *args],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_selected_global_clis_only(self):
        first = self.run_setup("--cli", "codex, gemini")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((self.user / ".agents/skills/hydra-review/SKILL.md").is_file())
        self.assertTrue((self.user / ".codex/agents/hydra-correctness.toml").is_file())
        self.assertTrue((self.user / ".gemini/commands/hydra.toml").is_file())
        self.assertFalse((self.user / ".claude").exists())
        self.assertFalse((self.xdg / "opencode").exists())
        second = self.run_setup("--cli", "codex,gemini")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0 installed, 14 unchanged", second.stdout)

    def test_project_install_does_not_touch_global_destination(self):
        project = self.base / "my project"
        project.mkdir()
        result = self.run_setup("--cli", "claude,opencode", "--project", str(project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((project / ".agents/skills/hydra-review/SKILL.md").is_file())
        self.assertTrue((project / ".claude/commands/hydra.md").is_file())
        self.assertTrue((project / ".opencode/agent/hydra-orchestrator.md").is_file())
        self.assertFalse((project / ".codex").exists())
        self.assertFalse(self.user.exists())

    def test_conflict_stops_before_changes_and_replace_backs_up(self):
        self.assertEqual(self.run_setup("--cli", "claude,gemini").returncode, 0)
        claude = self.user / ".claude/commands/hydra.md"
        gemini = self.user / ".gemini/commands/hydra.toml"
        claude.write_text("my custom command\n")
        gemini.unlink()
        gemini.symlink_to(PACKAGE / ".gemini/commands/hydra.toml")
        conflict = self.run_setup("--cli", "claude,gemini")
        self.assertEqual(conflict.returncode, 1)
        self.assertIn(str(claude), conflict.stderr)
        self.assertIn(str(gemini), conflict.stderr)
        self.assertEqual(claude.read_text(), "my custom command\n")
        self.assertTrue(gemini.is_symlink())
        replaced = self.run_setup("--cli", "claude,gemini", "--replace")
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        self.assertIn("2 backed up", replaced.stdout)
        self.assertEqual(claude.read_text(), (PACKAGE / ".claude/commands/hydra.md").read_text())
        self.assertFalse(gemini.is_symlink())
        self.assertEqual(len(list(claude.parent.glob("hydra.md.hydra-backup-*"))), 1)
        self.assertEqual(len(list(gemini.parent.glob("hydra.toml.hydra-backup-*"))), 1)

    def test_unattended_run_requires_selection(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --cli or --all", result.stderr)
        self.assertFalse(self.user.exists())
        self.assertEqual(self.run_setup("--all", "--cli", "codex").returncode, 2)
        self.assertEqual(self.run_setup("--project", str(self.base / "absent"), "--all").returncode, 2)

    def test_interactive_multi_selection(self):
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(
                ["bash", str(SETUP)],
                env=self.env,
                stdin=slave,
                stdout=slave,
                stderr=slave,
            )
            os.close(slave)
            slave = -1
            os.write(master, b"1,4\n")
            self.assertEqual(process.wait(timeout=15), 0)
        finally:
            os.close(master)
            if slave >= 0:
                os.close(slave)
        self.assertTrue((self.user / ".codex/agents/hydra-correctness.toml").is_file())
        self.assertTrue((self.xdg / "opencode/agent/hydra-orchestrator.md").is_file())
        self.assertFalse((self.user / ".claude").exists())

    def test_legacy_command_installs_all(self):
        result = self.run_setup(script=LEGACY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("28 installed", result.stdout)


if __name__ == "__main__":
    unittest.main()
