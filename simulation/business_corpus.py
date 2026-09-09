"""
simulation/business_corpus.py
=============================
Zero-runtime-cost enterprise financial domain corpus for MOD simulation.
Reads pre-compiled static JSON asset from simulation/assets/business_corpus.json.
Provides deterministic, hash-based retrieval by org_id and category/stage.
Strictly zero runtime LLM calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

ASSET_PATH = Path(__file__).resolve().parent / "assets" / "business_corpus.json"

_corpus_lock = Lock()
_corpus_data: dict | None = None

# Hardcoded fallback in case JSON file is missing or corrupted
_FALLBACK_FRICTIONS = [
    "历史账套期初科目余额存在核销差异，需组织专项清查小组开展人工数据清洗与映射修复。",
    "跨行银企直联接口专线网络间歇性超时，已派驻技术专班协调网络与银行安全专家联合排障。",
    "老系统月末高频单据核对存在长尾差异，核算中心与技术专家介入进行凭证规则逻辑微调对齐。",
    "兼任两家二级子公司的财务主管在统一身份认证中存在映射冲突，人力与内控部门正紧急修订权签矩阵。",
    "大额采购合同多期款项支付事前审批单关联阻断，现已提请业务推进督导会审定解决方案。",
]

_FALLBACK_REVIEWS = [
    "【阶段跃迁评审决议】经系统推广指挥部与推进办公室联合审查，该单位各项前置准备工作扎实，具备阶段跃迁准入条件。",
    "【阶段跃迁评审决议】经数据质量专家组与实施工作组现场联合验收评审，该单位核心数据核对平账，业务验证无阻断缺陷。",
    "【阶段跃迁评审决议】经技术接口联调验收组与培训考核委员会综合评估，各项通信与实操达标，准予正式并网并轨运行。",
    "【阶段跃迁评审决议】经双轨试运行成果评审专家组严肃复核，单据凭证一致率持续达标，专家组一致同意正式单轨投产上线。",
    "【阶段跃迁评审决议】经单轨投产成效综合考评专家组终审，顺利完成月度无差错关账结转，已达成常态化稳定运行标准。",
]


def load_corpus() -> dict:
    """Thread-safe lazy loader for the business corpus JSON asset."""
    global _corpus_data
    if _corpus_data is not None:
        return _corpus_data

    with _corpus_lock:
        if _corpus_data is not None:
            return _corpus_data

        if ASSET_PATH.exists():
            try:
                with open(ASSET_PATH, "r", encoding="utf-8") as f:
                    _corpus_data = json.load(f)
                    return _corpus_data
            except (OSError, ValueError) as ex:
                logger.warning("业务语料资产加载失败，回退内置最小词典: %s", type(ex).__name__)

        # Fallback minimal dictionary
        _corpus_data = {
            "meta": {"version": "fallback", "totalCount": 10},
            "frictions": {"default": _FALLBACK_FRICTIONS},
            "transition_reviews": {"default": _FALLBACK_REVIEWS},
        }
        return _corpus_data


def get_friction_reason(org_id: int, category: Optional[str] = None) -> str:
    """
    Deterministically retrieve an authentic SOE financial friction reason for a unit.
    - Same org_id always yields the same category and reason across simulation days.
    - Different org_ids distribute evenly across categories and individual phrases.
    """
    corpus = load_corpus()
    frictions = corpus.get("frictions", {})
    if not frictions:
        return _FALLBACK_FRICTIONS[org_id % len(_FALLBACK_FRICTIONS)]

    cats = sorted(frictions.keys())
    if not category or category not in frictions:
        # Pick category deterministically by org_id hash
        cat_hash = hashlib.md5(f"mod_fric_cat_{org_id}".encode("utf-8")).hexdigest()  # noqa: S324
        cat_idx = int(cat_hash[:6], 16) % len(cats)
        category = cats[cat_idx]

    items = frictions.get(category, [])
    if not items:
        return _FALLBACK_FRICTIONS[org_id % len(_FALLBACK_FRICTIONS)]

    item_hash = hashlib.md5(f"mod_fric_item_{org_id}_{category}".encode("utf-8")).hexdigest()  # noqa: S324
    item_idx = int(item_hash[:6], 16) % len(items)
    return items[item_idx]


def get_transition_review_notes(from_status: str, to_status: str, org_id: int) -> str:
    """
    Deterministically retrieve an authentic milestone transition review note.
    - Keyed by transition milestone: f"{from_status}->{to_status}".
    - Deterministically selected by org_id and transition key hash.
    - Includes standard resolution identifier "阶段跃迁评审决议".
    """
    corpus = load_corpus()
    reviews = corpus.get("transition_reviews", {})
    key = f"{from_status}->{to_status}"

    items = reviews.get(key)
    if not items:
        # Try generic match or fallback
        all_lists = [v for k, v in reviews.items() if isinstance(v, list) and v]
        if all_lists:
            # Flatten or pick first available
            items = all_lists[org_id % len(all_lists)]
        else:
            items = _FALLBACK_REVIEWS

    item_hash = hashlib.md5(f"mod_review_note_{org_id}_{key}".encode("utf-8")).hexdigest()  # noqa: S324
    item_idx = int(item_hash[:6], 16) % len(items)
    return items[item_idx]


def get_corpus_stats() -> dict:
    """Return summary metadata of loaded corpus for diagnostics and testing."""
    corpus = load_corpus()
    meta = corpus.get("meta", {})
    frictions = corpus.get("frictions", {})
    reviews = corpus.get("transition_reviews", {})

    return {
        "version": meta.get("version", "unknown"),
        "totalCount": meta.get("totalCount", 0),
        "frictionCategories": {k: len(v) for k, v in frictions.items()},
        "totalFrictions": sum(len(v) for v in frictions.values()),
        "reviewTransitions": {k: len(v) for k, v in reviews.items()},
        "totalReviews": sum(len(v) for v in reviews.values()),
    }
