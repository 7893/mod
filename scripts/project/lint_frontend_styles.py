#!/usr/bin/env python3
"""
Lint the frontend style layer against the token and file contracts.

Enforces docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md:
- frontend/src/styles/ contains exactly theme/base/shell/blocks.
- theme.css is the only place a colour literal may appear in global CSS.
- Legacy variable names (--c-*, --space-*, --text-xs ...) must not return.
- Media queries and clamp() live only in shell.css (outside the scaled canvas).
- Every class selector in global CSS is referenced by a .vue/.ts file.
- Colour literals in .vue/.ts (styles or ECharts options) live only in charts/theme.ts.
- SFC <style> blocks that use tokens must start with @reference.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ALLOWED_STYLE_FILES = {"theme.css", "base.css", "shell.css", "blocks.css"}
COLOR_LITERAL = re.compile(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b|rgba?\((?!\s*0\s+0\s+0\s*/)")
LEGACY_VAR = re.compile(
    r"var\(--(?:c-[\w-]+|space-\d+|grid-gap|panel-pad|duration-(?:fast|normal)|"
    r"text-(?:xxs|xs|sm|base|md|lg|metric|stat|kpi|hero))\)"
)
CLASS_IN_SELECTOR = re.compile(r"\.([a-zA-Z_][\w-]*)")
DYNAMIC_CLASS_PREFIXES = ("is-", "metric-grid--", "stat-list--", "status-list--", "chart-facts--")
COMMENT = re.compile(r"/\*.*?\*/", re.S)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S)


def strip_comments(css: str) -> str:
    """Blank out comments while preserving line numbers."""
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), css)


def split_rules(css: str) -> list[str]:
    """Return selector text for every top-level or nested rule."""
    selectors: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in css:
        if ch == "{":
            sel = "".join(buf).strip()
            if sel and not sel.startswith("@"):
                selectors.append(sel)
            buf = []
            depth += 1
        elif ch == "}":
            depth -= 1
            buf = []
        elif ch == ";" and depth >= 0:
            buf = []
        else:
            buf.append(ch)
    return selectors


def source_corpus(frontend_src: Path) -> str:
    parts: list[str] = []
    for path in list(frontend_src.rglob("*.vue")) + list(frontend_src.rglob("*.ts")):
        if "__tests__" in path.parts:
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def lint(repo_root: Path) -> list[str]:
    frontend_src = repo_root / "frontend" / "src"
    styles_dir = frontend_src / "styles"
    problems: list[str] = []

    present = {p.name for p in styles_dir.glob("*.css")}
    for extra in sorted(present - ALLOWED_STYLE_FILES):
        problems.append(f"frontend/src/styles/{extra}: unexpected global stylesheet (allowed: {sorted(ALLOWED_STYLE_FILES)})")
    for missing in sorted(ALLOWED_STYLE_FILES - present):
        problems.append(f"frontend/src/styles/{missing}: required stylesheet missing")

    corpus = source_corpus(frontend_src)

    for css_path in sorted(styles_dir.glob("*.css")):
        rel = css_path.relative_to(repo_root)
        raw = css_path.read_text(encoding="utf-8")
        css = strip_comments(raw)
        for idx, line in enumerate(css.splitlines(), start=1):
            if css_path.name != "theme.css" and COLOR_LITERAL.search(line):
                problems.append(f"{rel}:{idx}: colour literal outside theme.css")
            if LEGACY_VAR.search(line):
                problems.append(f"{rel}:{idx}: legacy token variable")
            if css_path.name != "shell.css" and ("@media" in line or "clamp(" in line):
                problems.append(f"{rel}:{idx}: media query / clamp() only allowed in shell.css")
        for selector in split_rules(css):
            classes = CLASS_IN_SELECTOR.findall(selector)
            if not classes:
                continue
            live = False
            for cls in classes:
                if cls.startswith(DYNAMIC_CLASS_PREFIXES):
                    live = True
                    break
                if re.search(r"(?<![\w-])" + re.escape(cls) + r"(?![\w-])", corpus):
                    live = True
                    break
            if not live:
                problems.append(f"{rel}: unreferenced selector '{selector.strip()}'")

    for path in sorted(list(frontend_src.rglob("*.vue")) + list(frontend_src.rglob("*.ts"))):
        if "__tests__" in path.parts or path == frontend_src / "charts" / "theme.ts":
            continue
        rel = path.relative_to(repo_root)
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("//", "*", "/*")):
                continue
            if COLOR_LITERAL.search(line):
                problems.append(f"{rel}:{idx}: colour literal outside charts/theme.ts")
            if LEGACY_VAR.search(line):
                problems.append(f"{rel}:{idx}: legacy token variable")
        if path.suffix == ".vue":
            for block in STYLE_BLOCK.findall(text):
                body = strip_comments(block)
                uses_tokens = "var(--" in body or "--spacing(" in body
                if uses_tokens and "@reference" not in body:
                    problems.append(f"{rel}: <style> uses tokens without @reference")
                if "@media" in body or "clamp(" in body:
                    problems.append(f"{rel}: media query / clamp() inside component style")
    return problems


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    problems = lint(repo_root)
    if problems:
        for p in problems:
            print(p)
        print(f"\n[style-lint] Failed: {len(problems)} contract violation(s).", file=sys.stderr)
        print("       See docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md (Contract 3 / 全局样式文件契约).", file=sys.stderr)
        return 1
    print("[style-lint] Passed: stylesheet set, tokens, colour literals and selector references all conform.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
