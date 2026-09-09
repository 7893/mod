from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_SCRIPTS))

from check_doc_sync import check_sync, is_core_file  # noqa: E402
from check_history_integrity import load_manifest, validate as validate_history  # noqa: E402
from check_semantic_contracts import validate_contracts  # noqa: E402
from check_document_governance import (  # noqa: E402
    check_changes,
    missing_metadata,
    is_document_path,
    parse_board,
    parse_detail_status,
    preserves_frozen_body,
)


class DocumentGovernanceTests(unittest.TestCase):
    def test_high_risk_semantic_contracts_match(self) -> None:
        self.assertEqual(validate_contracts(), [])

    def test_history_integrity_manifest_matches_local_archive(self) -> None:
        self.assertEqual(validate_history(require_all=True), [])

    def test_history_manifest_rejects_malformed_entries(self) -> None:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "MANIFEST.sha256"
            path.write_text("not-a-hash  docs/history/a.md\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_parses_board_and_detail_status(self) -> None:
        board = "| KI-054 | 标题 | IN-PROGRESS | P1 | [详情](issues/KI-054-title.md) |"
        self.assertEqual(
            parse_board(board),
            {"KI-054": ("IN-PROGRESS", "issues/KI-054-title.md")},
        )
        self.assertEqual(parse_detail_status("# 标题\n\n- 状态：DONE（已完成）"), "DONE")

    def test_rejects_duplicate_board_identifier(self) -> None:
        row = "| KI-054 | 标题 | OPEN | P1 | [详情](issues/KI-054-title.md) |"
        with self.assertRaises(ValueError):
            parse_board(f"{row}\n{row}")

    def test_requires_living_document_metadata(self) -> None:
        complete = (
            "# 标题\n\n更新日期：2026-09-08\n状态：现行\n适用范围：测试"
        )
        self.assertEqual(missing_metadata(complete), [])
        self.assertEqual(missing_metadata("# 标题\n\n状态：现行"), ["更新日期", "适用范围"])

    def test_frozen_body_may_only_be_appended(self) -> None:
        old = "# 决策\n\n- 状态：采纳\n\n原始结论"
        marked = "# 决策\n\n- 状态：被取代\n\n原始结论\n\n## 勘误\n补充说明"
        rewritten = "# 决策\n\n- 状态：被取代\n\n改写后的结论"
        self.assertTrue(preserves_frozen_body(old, marked))
        self.assertFalse(preserves_frozen_body(old, rewritten))

    def test_document_paths_include_root_governance_files(self) -> None:
        self.assertTrue(is_document_path("docs/history/record.md"))
        self.assertTrue(is_document_path("README.md"))
        self.assertTrue(is_document_path("AGENTS.md"))
        self.assertTrue(is_document_path("scripts/project/README.md"))
        self.assertTrue(is_document_path("archive/legacy/instructions.txt"))
        self.assertFalse(is_document_path("backend/app/api.py"))

    def test_document_deletion_is_rejected(self) -> None:
        errors: list[str] = []
        check_changes(errors, [("D", "docs/old.md", None)], None, "HEAD")
        self.assertEqual(len(errors), 1)
        self.assertIn("禁止删除已跟踪文档", errors[0])

    def test_frozen_document_rewrite_is_rejected(self) -> None:
        errors: list[str] = []
        with patch(
            "check_document_governance.read_revision",
            side_effect=["# 历史\n\n原始结论", "# 历史\n\n改写结论"],
        ):
            check_changes(
                errors,
                [("M", "docs/history/record.md", None)],
                None,
                "HEAD",
            )
        self.assertEqual(len(errors), 1)
        self.assertIn("冻结文档正文被删减或改写", errors[0])

    def test_fact_sync_covers_all_behavior_domains(self) -> None:
        for path in (
            "backend/app/api.py",
            "frontend/src/views/Dashboard.vue",
            "simulation/runtime_service.py",
            "deploy/mod-api.service",
            "schema.sql",
        ):
            self.assertTrue(is_core_file(path))
        self.assertTrue(check_sync(["frontend/src/App.vue"]))
        self.assertFalse(
            check_sync(["frontend/src/App.vue", "docs/CURRENT-STATE.md"])
        )


if __name__ == "__main__":
    unittest.main()
