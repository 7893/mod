"""每日指挥部决策简报服务。

设计（ADR-0010 第二期）：
- 后台离线生成：由定时任务调用 generate_and_store()，把宏观聚合指标
  喂给 Cloudflare AI（经 mod-gateway），生成一段自然语言研判，写入 daily_briefing 表。
- 前台零交互：大屏只读最新简报（get_latest），绝不在渲染时同步调外部模型。
- 诚实：模型未达标时简报不谎报预测；simulated=聚合指标为演示数据。
- 表结构幂等建表，一天一条（同 briefing_date 覆盖更新）。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from app.config import get_display_timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

TABLE_NAME = "daily_briefing"

_DDL_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    briefing_date   DATE         NOT NULL COMMENT '简报所属日期(展示时区)',
    content         MEDIUMTEXT   NOT NULL COMMENT 'LLM 生成的研判正文',
    model           VARCHAR(128)          DEFAULT NULL COMMENT '生成模型标识',
    source          VARCHAR(32)  NOT NULL DEFAULT 'llm' COMMENT 'llm / template',
    metrics_fingerprint VARCHAR(64)       DEFAULT NULL COMMENT '输入聚合指标指纹',
    generated_at    DATETIME     NOT NULL COMMENT '生成时刻',
    PRIMARY KEY (briefing_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日指挥部决策简报(AI 生成，只读展示)';
"""


def ensure_table(conn: Connection) -> None:
    """幂等建表。写操作，需在具备写权限的连接上调用。"""
    conn.execute(text(_DDL_CREATE))


def _fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def get_latest(conn: Connection | None) -> dict:
    """只读返回最新一条简报；无则返回 status=no_briefing。不触发任何外部请求。"""
    if conn is None:
        return {"status": "no_briefing", "message": "无数据库连接"}
    try:
        row = conn.execute(text(
            f"SELECT briefing_date, content, model, source, generated_at "
            f"FROM {TABLE_NAME} ORDER BY briefing_date DESC LIMIT 1"
        )).mappings().first()
    except Exception:
        # 表不存在或查询失败，安全降级
        return {"status": "no_briefing", "message": "简报表尚未就绪"}
    if not row:
        return {"status": "no_briefing", "message": "尚未生成任何简报"}
    is_stale = str(row["briefing_date"]) != datetime.now(get_display_timezone()).date().isoformat()
    return {
        "status": "ok",
        "isStale": is_stale,
        "freshness": "stale" if is_stale else "current",
        "briefingDate": str(row["briefing_date"]),
        "content": row["content"],
        "model": row["model"],
        "source": row["source"],
        "generatedAt": str(row["generated_at"]),
    }


def generate_and_store(conn: Connection, overview: dict, cf_adapter, display_tz: str = "Asia/Hong_Kong") -> dict:
    """
    生成并存储当日简报（写操作）。

    - overview：脱敏后的宏观聚合指标（仅数字，来自 dashboard overview）。
    - cf_adapter：CloudflareAIAdapter 实例，经 mod-gateway 调用。
    - 返回生成结果 dict（含 status）。
    LLM 不可用/降级时不写入假内容，返回对应 status。
    """
    from zoneinfo import ZoneInfo

    ensure_table(conn)

    result = cf_adapter.generate_insights(overview)
    status = result.get("status")
    content = result.get("content") or result.get("insight")

    if status not in ("ok", "cache_hit") or not content:
        # 不写假简报，如实返回降级状态
        return {"status": status or "unavailable", "message": result.get("message", "LLM 未产生有效简报")}

    today = datetime.now(ZoneInfo(display_tz)).date()
    generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    fp = _fingerprint({k: v for k, v in overview.items() if isinstance(v, (int, float))})

    conn.execute(text(
        f"REPLACE INTO {TABLE_NAME} "
        f"(briefing_date, content, model, source, metrics_fingerprint, generated_at) "
        f"VALUES (:d, :c, :m, :s, :fp, :g)"
    ), {
        "d": today, "c": content, "m": result.get("model"),
        "s": "llm", "fp": fp, "g": generated_at,
    })

    return {
        "status": "ok",
        "briefingDate": str(today),
        "content": content,
        "model": result.get("model"),
        "generatedAt": str(generated_at),
    }
