"""删除已被区块原型（MetricGrid / StatList）取代的旧样式规则。

按顶层规则块扫描各屏级 CSS，凡选择器命中废弃类名的整块删除；
@media 等嵌套块递归处理，块内被删空时连同外层一并移除。
"""
import re
import sys
from pathlib import Path

DEAD = [
    "c4-wrap", "c4-stats-bar", "c4-stat", "type-chart-wrap", "risk-pie-wrap", "risk-notice",
    "t-pill", "type-list-bar", "risk-list", "risk-item", "risk-dot", "risk-info", "risk-title",
    "risk-meta", "bullet-list", "bullet-row", "bullet-metric", "bullet-metric-label",
    "bullet-metric-value", "ai-governance-box", "gov-item", "aux-links", "aux-link", "mini-pie-chart",
    "stage-cards-grid", "stage-card", "stage-head", "stage-pct", "stage-progress",
    "stage-fill", "stage-counts", "province-rank-list", "rank-item", "rank-index",
    "rank-name", "rank-track", "rank-bar", "rank-val", "training-stats-bar", "t-stat",
    "contacts-grid", "c-stat-box", "quality-checks-grid", "q-card", "q-head", "q-val",
    "detail-metrics", "ops-stack", "ops-item", "ops-icon", "ops-data", "ops-label",
    "ops-value", "ops-sub", "stg-kpis",
]
DEAD_RE = re.compile(r"\.(?:%s)(?![\w-])" % "|".join(map(re.escape, DEAD)))


def split_blocks(css: str):
    """把一段 CSS 切成 (selector, body, raw) 三元组与原样保留的片段。"""
    out, depth, start, i = [], 0, 0, 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            if depth == 0:
                head_end = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append((css[start:head_end], css[head_end + 1 : i], css[start : i + 1]))
                start = i + 1
        i += 1
    if start < len(css):
        out.append((None, None, css[start:]))
    return out


def prune(css: str) -> str:
    parts = []
    for head, body, raw in split_blocks(css):
        if head is None:
            parts.append(raw)
            continue
        if head.lstrip().startswith("@") and "{" in body:
            inner = prune(body)
            if not inner.strip():
                continue
            parts.append(f"{head}{{{inner}}}")
            continue
        if DEAD_RE.search(head):
            continue
        parts.append(raw)
    return "".join(parts)


total = 0
for path in map(Path, sys.argv[1:]):
    text = path.read_text()
    new = re.sub(r"\n{3,}", "\n\n", prune(text))
    if new != text:
        path.write_text(new)
        total += 1
        print(f"pruned {path.name}: {len(text) - len(new)} chars")
print(f"{total} file(s) changed")
