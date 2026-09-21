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
from datetime import date, datetime, timedelta, timezone

from app.config import get_display_timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

TABLE_NAME = "daily_briefing"

_DDL_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    briefing_date   DATE         NOT NULL COMMENT '日报统计日期(展示时区)',
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


def _as_utc_datetime(value: object) -> datetime:
    """Interpret the database's naive DATETIME as UTC."""
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: object) -> str:
    """Serialize the database's naive UTC DATETIME without browser-local ambiguity."""
    return _as_utc_datetime(value).isoformat()


def _is_closed_day_record(row: dict, display_tz) -> bool:
    """Reject legacy rows generated on the same local date they claim to summarize."""
    try:
        reporting_date = date.fromisoformat(str(row["briefing_date"]))
        generated_local_date = _as_utc_datetime(row["generated_at"]).astimezone(display_tz).date()
    except (KeyError, TypeError, ValueError):
        return False
    return generated_local_date > reporting_date


def get_latest(conn: Connection | None) -> dict:
    """只读返回不晚于上一完整自然日的最新简报；不触发任何外部请求。"""
    if conn is None:
        return {"status": "no_briefing", "message": "无数据库连接"}
    display_tz = get_display_timezone()
    expected_date = datetime.now(display_tz).date() - timedelta(days=1)
    try:
        rows = conn.execute(text(
            f"SELECT briefing_date, content, model, source, generated_at "
            f"FROM {TABLE_NAME} WHERE briefing_date <= :expected_date "
            f"ORDER BY briefing_date DESC LIMIT 31"
        ), {"expected_date": expected_date}).mappings().all()
    except Exception:
        # 表不存在或查询失败，安全降级
        return {"status": "no_briefing", "message": "简报表尚未就绪"}
    row = next((candidate for candidate in rows if _is_closed_day_record(candidate, display_tz)), None)
    if not row:
        return {"status": "no_briefing", "message": "尚无上一完整自然日口径的日报"}
    is_stale = str(row["briefing_date"]) != expected_date.isoformat()
    return {
        "status": "ok",
        "isStale": is_stale,
        "freshness": "stale" if is_stale else "current",
        "briefingDate": str(row["briefing_date"]),
        "content": row["content"],
        "model": row["model"],
        "source": row["source"],
        "generatedAt": _utc_iso(row["generated_at"]),
    }


def generate_and_store(conn: Connection, overview: dict, cf_adapter, display_tz: str = "Asia/Hong_Kong") -> dict:
    """
    生成并存储上一完整自然日的简报（写操作）。

    - overview：脱敏后的宏观聚合指标（仅数字，来自 dashboard overview）。
    - cf_adapter：CloudflareAIAdapter 实例，经 mod-gateway 调用。
    - 返回生成结果 dict（含 status）。
    LLM 不可用/降级时不写入假内容，返回对应 status。
    """
    from zoneinfo import ZoneInfo

    ensure_table(conn)

    today = datetime.now(ZoneInfo(display_tz)).date()
    reporting_date = today - timedelta(days=1)
    daily_row = conn.execute(text("""
        SELECT doc_today, voucher_today
        FROM daily_stats
        WHERE stat_date = :reporting_date
    """), {"reporting_date": reporting_date}).mappings().first()
    if not daily_row:
        return {"status": "unavailable", "message": "上一完整自然日尚无统计数据"}

    metrics = dict(overview)
    metrics.pop("docsTodayAdded", None)
    metrics.pop("vouchersTodayAdded", None)
    metrics["docsClosedDayAdded"] = int(daily_row["doc_today"] or 0)
    metrics["vouchersClosedDayAdded"] = int(daily_row["voucher_today"] or 0)

    result = cf_adapter.generate_insights(metrics, reporting_date=reporting_date.isoformat())
    status = result.get("status")
    content = result.get("content") or result.get("insight")

    if status not in ("ok", "cache_hit") or not content:
        # 不写假简报，如实返回降级状态
        return {"status": status or "unavailable", "message": result.get("message", "LLM 未产生有效简报")}

    generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    fp = _fingerprint({k: v for k, v in metrics.items() if isinstance(v, (int, float))})

    conn.execute(text(
        f"REPLACE INTO {TABLE_NAME} "
        f"(briefing_date, content, model, source, metrics_fingerprint, generated_at) "
        f"VALUES (:d, :c, :m, :s, :fp, :g)"
    ), {
        "d": reporting_date, "c": content, "m": result.get("model"),
        "s": "llm", "fp": fp, "g": generated_at,
    })

    return {
        "status": "ok",
        "briefingDate": str(reporting_date),
        "content": content,
        "model": result.get("model"),
        "generatedAt": _utc_iso(generated_at),
    }
