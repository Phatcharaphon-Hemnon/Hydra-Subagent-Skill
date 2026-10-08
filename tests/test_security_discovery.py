"""Checks for the optional pinned security-skill installer.

These tests validate installer behavior and safeguards; they do not clone the
external repository and require no network.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
INSTALL = PACKAGE / "scripts/install-security-skills.sh"


class SecurityDiscoveryTests(unittest.TestCase):
    def run_install(self, *args, cwd=None):
        return subprocess.run(
            ["bash", str(INSTALL), *args],
            text=True,
            capture_output=True,
            timeout=30,
            cwd=str(cwd) if cwd else None,
        )

    def test_pin_is_required(self):
        with tempfile.TemporaryDirectory(prefix="hydra-sec-test-") as base:
            result = self.run_install()
            self.assertEqual(result.returncode, 2)
            self.assertIn("--pin", result.stderr)
            self.assertFalse((PACKAGE / "vendor").exists())

    def test_check_only_accepts_clean_tree(self):
        with tempfile.TemporaryDirectory(prefix="hydra-sec-test-") as base:
            root = Path(base) / "skills"
            (root / "auth").mkdir(parents=True)
            (root / "auth" / "SKILL.md").write_text("# auth\n")
            os.symlink("SKILL.md", root / "auth" / "local-link.md")
            result = self.run_install("--check-only", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_only_rejects_absolute_symlink(self):
        with tempfile.TemporaryDirectory(prefix="hydra-sec-test-") as base:
            root = Path(base) / "skills"
            root.mkdir()
            os.symlink("/etc/passwd", root / "evil.md")
            result = self.run_install("--check-only", str(root))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("absolute symlink", result.stderr)

    def test_check_only_rejects_escaping_symlink(self):
        with tempfile.TemporaryDirectory(prefix="hydra-sec-test-") as base:
            root = Path(base) / "skills"
            root.mkdir(parents=True)
            (Path(base) / "secret.txt").write_text("secret\n")
            os.symlink("../secret.txt", root / "escape.md")
            result = self.run_install("--check-only", str(root))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escaping symlink", result.stderr)

    def test_check_only_rejects_traversal_name(self):
        with tempfile.TemporaryDirectory(prefix="hydra-sec-test-") as base:
            root = Path(base) / "skills"
            root.mkdir()
            (root / "evil..txt").write_text("x\n")
            result = self.run_install("--check-only", str(root))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("traversal", result.stderr)

    def test_installer_safeguards_in_script(self):
        text = INSTALL.read_text()
        # Immutable pinning: tags resolved to SHAs, floating refs never used.
        self.assertIn("ls-remote", text)
        self.assertIn(".hydra-pin", text)
        self.assertIn("floating refs", text)
        # Validation of paths and symlinks.
        self.assertIn("traversal", text)
        self.assertIn("symlink", text)
        # Never bulk-copied into an auto-discovered skills directory.
        self.assertIn("vendor/anthropic-cybersecurity-skills", text)
        self.assertNotIn("cp ", text)
        self.assertNotIn("rsync", text)
        # Third-party content is untrusted; scripts never run automatically.
        self.assertIn("never executed", text.lower())

    def test_security_index_exists_and_routes_by_relevance(self):
        index = PACKAGE / "docs/SECURITY-SKILLS.md"
        self.assertTrue(index.is_file())
        text = index.read_text()
        for domain in ("Authentication and Authorization", "API Security",
                       "Secret Detection", "Supply Chain Security",
                       "Prompt Injection Defense", "MCP Security"):
            self.assertIn(domain, text)
        self.assertIn("independent of planning-head count", text)
        self.assertIn("untrusted", text)


if __name__ == "__main__":
    unittest.main()
