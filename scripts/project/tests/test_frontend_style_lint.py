from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_SCRIPTS))

from lint_frontend_styles import lint  # noqa: E402

REPO_ROOT = PROJECT_SCRIPTS.parent.parent


def make_repo(root: Path, *, styles: dict[str, str], sources: dict[str, str]) -> None:
    styles_dir = root / "frontend" / "src" / "styles"
    styles_dir.mkdir(parents=True)
    for name in ("theme.css", "base.css", "shell.css", "blocks.css"):
        (styles_dir / name).write_text(styles.get(name, ""), encoding="utf-8")
    for rel, body in sources.items():
        path = root / "frontend" / "src" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


class FrontendStyleLintTests(unittest.TestCase):
    def test_repository_conforms(self) -> None:
        self.assertEqual(lint(REPO_ROOT), [])

    def test_clean_fixture_passes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(
                root,
                styles={
                    "theme.css": "@theme { --color-surface-base: #070a0f; }",
                    "blocks.css": ".stat-row { color: var(--color-slate-50); } .stat-row.is-danger { color: red; }",
                    "shell.css": "@media (max-width: 1200px) { .command-header { gap: clamp(4px, 1vw, 8px); } }",
                },
                sources={"App.vue": '<template><div class="stat-row command-header"></div></template>'},
            )
            self.assertEqual(lint(root), [])

    def test_detects_each_contract_violation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(
                root,
                styles={
                    "blocks.css": (
                        ".dead-rule { color: #fff; }\n"
                        ".live-rule { padding: var(--space-3); }\n"
                        "@media (max-width: 900px) { .live-rule { display: none; } }\n"
                    ),
                },
                sources={
                    "App.vue": (
                        '<template><div class="live-rule"></div></template>\n'
                        "<style scoped>\n.live-rule { color: var(--color-sky-400); }\n</style>\n"
                    ),
                    "charts/x.ts": "export const c = '#38bdf8'\n",
                },
            )
            (root / "frontend" / "src" / "styles" / "legacy.css").write_text("", encoding="utf-8")
            problems = "\n".join(lint(root))
            self.assertIn("legacy.css: unexpected global stylesheet", problems)
            self.assertIn("blocks.css:1: colour literal outside theme.css", problems)
            self.assertIn("blocks.css:2: legacy token variable", problems)
            self.assertIn("blocks.css:3: media query / clamp() only allowed in shell.css", problems)
            self.assertIn("unreferenced selector '.dead-rule'", problems)
            self.assertIn("App.vue: <style> uses tokens without @reference", problems)
            self.assertIn("charts/x.ts:1: colour literal outside charts/theme.ts", problems)

    def test_line_numbers_survive_comment_stripping(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(
                root,
                styles={"blocks.css": "/* a\n   b\n   c */\n.x { color: #fff; }\n"},
                sources={"App.vue": '<template><i class="x"></i></template>'},
            )
            self.assertIn("blocks.css:4: colour literal outside theme.css", "\n".join(lint(root)))


if __name__ == "__main__":
    unittest.main()
