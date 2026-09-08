from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_SCRIPTS))

from check_changelog import (  # noqa: E402
    ACTION_SHA,
    GENERATED_MARKER,
    validate_baseline,
    validate_changelog,
    validate_config,
    validate_workflow,
)
from generate_changelog import build_command  # noqa: E402


class ChangelogTests(unittest.TestCase):
    def test_baseline_requires_full_lowercase_sha(self) -> None:
        self.assertEqual(validate_baseline("a" * 40), [])
        self.assertTrue(validate_baseline("v0.1.0"))
        self.assertTrue(validate_baseline("A" * 40))

    def test_configuration_requires_marker_and_conventional_commits(self) -> None:
        valid = {
            "changelog": {"header": GENERATED_MARKER},
            "git": {"conventional_commits": True},
        }
        self.assertEqual(validate_config(valid), [])
        self.assertTrue(validate_config({"changelog": {}, "git": {}}))

    def test_changelog_rejects_old_tag_claim(self) -> None:
        valid = f"# 变更日志\n\n<!-- {GENERATED_MARKER} -->\n"
        self.assertEqual(validate_changelog(valid), [])
        self.assertTrue(validate_changelog(valid + "\nv0.1.0"))

    def test_generator_uses_explicit_revision_range(self) -> None:
        command = build_command("git-cliff", "a" * 40, "HEAD", Path("out.md"))
        self.assertIn(f"{'a' * 40}..HEAD", command)
        self.assertEqual(command[-2:], ["--output", "out.md"])

    def test_workflow_is_pinned_and_read_only(self) -> None:
        workflow = (
            f"uses: orhun/git-cliff-action@{ACTION_SHA}\n"
            "version: v2.13.1\npermissions:\n  contents: read\n"
        )
        self.assertEqual(validate_workflow(workflow), [])
        self.assertTrue(validate_workflow("uses: orhun/git-cliff-action@v4"))


if __name__ == "__main__":
    unittest.main()
