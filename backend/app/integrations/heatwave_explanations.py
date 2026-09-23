"""Persisted HeatWave SHAP generation and response helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

from sqlalchemy import text

from .heatwave_sql import FEAT_TABLE_CLASSIFIER, MODEL_CLASSIFIER

RISK_EXPLANATION_TABLE = "ml_risk_explanation"
RISK_EXPLANATION_PREVIOUS_TABLE = "ml_risk_explanation_previous"
_RISK_EXPLANATION_NEXT_TABLE = "ml_risk_explanation_next"
_RISK_EXPLANATION_INPUT_TABLE = "ml_risk_explanation_batch_input"
_RISK_EXPLANATION_OUTPUT_TABLE = "ml_risk_explanation_batch_output"

# MySQL 9.4.1+ limits ML_EXPLAIN_TABLE inputs with more than ten columns to
# ten rows. The risk feature table has more than ten columns.
MAX_EXPLANATION_BATCH_SIZE = 10

RISK_FACTOR_DEFS = {
    "unresolved_issues": ("未解决问题积压", "当前存在未闭环业务与数据问题工单"),
    "high_risk_issues": ("高危风险阻断", "存在阻断系统正常推进的重大缺陷事项"),
    "stagnant_days": ("工期停滞过久", "近期缺乏持续推进记录，任务长时间未更新"),
    "progress_slope_14d": ("推进速度滞后", "近14天施工推进斜率落后于全网批次基线"),
    "training_error_scissors": ("培训与上线报错剪刀差", "全员考核通过但实际系统运行接口报错率偏高"),
    "handler_concentration": ("经办人单点集中瓶颈", "单人集中承揽绝大部分单据，推广覆盖面不足"),
    "construction_pct": ("建设任务完成度偏低", "基础任务总体完成率显著落后于批次门禁"),
    "integration_success_pct": ("凭证入账集成受阻", "双轨财务凭证自动集成成功率偏离达标线"),
    "doc_success_pct": ("业务单据处理流转异常", "单据审批流转与凭证闭环率偏低"),
    "days_since_start": ("启动入池耗时过长", "自批次启动以来持续时间较长未达成跃迁"),
}

_DDL_RISK_EXPLANATION = f"""
CREATE TABLE IF NOT EXISTS `mod`.`{RISK_EXPLANATION_TABLE}` (
    `org_id` INT NOT NULL,
    `model_handle` VARCHAR(64) NOT NULL,
    `model_trained_at` DATETIME(6) NOT NULL,
    `feature_fingerprint` CHAR(64) NOT NULL,
    `ml_results` JSON NOT NULL,
    `generated_at` DATETIME(6) NOT NULL,
    PRIMARY KEY (`org_id`),
    KEY `idx_risk_explanation_model` (`model_handle`, `generated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='HeatWave AutoML 预生成 SHAP 风险解释（只读 API 消费）'
"""


def risk_feature_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical classifier feature payload used for freshness checks."""
    return {
        "region": str(row.get("region") or ""),
        "batch_id": int(row.get("batch_id") or 1),
        "construction_pct": float(row.get("construction_pct") or 0.0),
        "unresolved_issues": int(row.get("unresolved_issues") or 0),
        "high_risk_issues": int(row.get("high_risk_issues") or 0),
        "doc_success_pct": float(
            row["doc_success_pct"] if row.get("doc_success_pct") is not None else 100.0
        ),
        "integration_success_pct": float(
            row["integration_success_pct"] if row.get("integration_success_pct") is not None else 100.0
        ),
        "days_since_start": int(row.get("days_since_start") or 0),
        "progress_slope_14d": float(row.get("progress_slope_14d") or 0.0),
        "stagnant_days": int(row.get("stagnant_days") or 0),
        "training_error_scissors": float(row.get("training_error_scissors") or 0.0),
        "handler_concentration": float(row.get("handler_concentration") or 0.0),
    }


def risk_feature_fingerprint(row: dict[str, Any]) -> str:
    """Return a stable SHA-256 for exactly the features consumed by the model."""
    canonical = json.dumps(risk_feature_payload(row), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_model_trained_at(value: Any) -> str:
    """Normalize model timestamps to the second precision stored by metadata."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat(sep=" ")
    raw = str(value).strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).replace(microsecond=0).isoformat(sep=" ")
    except ValueError:
        return raw


def model_timestamps_match(left: Any, right: Any) -> bool:
    """Compare model timestamps at the precision supported by ml_model_metadata."""
    normalized_left = normalize_model_trained_at(left)
    normalized_right = normalize_model_trained_at(right)
    return bool(normalized_left and normalized_left == normalized_right)


def parse_shap_attributions(raw_result: Any) -> dict[str, float]:
    """Normalize ML_EXPLAIN_ROW and ML_EXPLAIN_TABLE JSON shapes."""
    if raw_result is None:
        return {}
    try:
        parsed = json.loads(raw_result) if isinstance(raw_result, (str, bytes, bytearray)) else raw_result
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}

    raw_attrs = parsed.get("attributions")
    if not isinstance(raw_attrs, dict):
        ml_results = parsed.get("ml_results")
        raw_attrs = ml_results.get("attributions") if isinstance(ml_results, dict) else None
    if not isinstance(raw_attrs, dict):
        raw_attrs = {key: value for key, value in parsed.items() if key.endswith("_attribution")}

    attributions: dict[str, float] = {}
    for key, value in raw_attrs.items():
        feature = key.removesuffix("_attribution")
        if feature not in RISK_FACTOR_DEFS or value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric_value):
            attributions[feature] = numeric_value
    return attributions


def top_risk_attributions(attributions: dict[str, float]) -> list[dict[str, Any]]:
    """Return positive Top-3 SHAP factors normalized to a 100% relative share."""
    top_three = [
        (name, value)
        for name, value in sorted(attributions.items(), key=lambda item: item[1], reverse=True)[:3]
        if value > 0
    ]
    total = sum(value for _, value in top_three)
    if total <= 0:
        return []

    result: list[dict[str, Any]] = []
    for feature, value in top_three:
        name, description = RISK_FACTOR_DEFS.get(feature, (feature, "业务指标偏离"))
        result.append(
            {
                "factor": feature,
                "factorName": name,
                "attribution": round(value, 4),
                "weightPct": round(value / total * 100),
                "description": description,
            }
        )
    difference = 100 - sum(item["weightPct"] for item in result)
    if difference:
        result[0]["weightPct"] += difference
    return result


def refresh_persisted_shap_explanations(
    conn: Any,
    *,
    model_trained_at: datetime,
    batch_size: int = MAX_EXPLANATION_BATCH_SIZE,
) -> dict[str, Any]:
    """Generate a complete SHAP snapshot and atomically publish it.

    Work tables are isolated from the API-facing table. Any exception leaves
    the current snapshot untouched; the last published snapshot is retained.
    """
    if not 1 <= batch_size <= MAX_EXPLANATION_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_EXPLANATION_BATCH_SIZE}")
    model_trained_at = model_trained_at.replace(microsecond=0)

    conn.execute(text(_DDL_RISK_EXPLANATION))
    source_rows = [
        dict(row)
        for row in conn.execute(
            text(
                f"SELECT `id`, `org_id`, `region`, `batch_id`, `construction_pct`, "
                "`unresolved_issues`, `high_risk_issues`, `doc_success_pct`, "
                "`integration_success_pct`, `days_since_start`, `progress_slope_14d`, "
                "`stagnant_days`, `training_error_scissors`, `handler_concentration` "
                f"FROM `mod`.`{FEAT_TABLE_CLASSIFIER}` ORDER BY `id`"
            )
        )
        .mappings()
        .all()
    ]
    if not source_rows:
        raise RuntimeError("Risk feature table is empty; refusing to replace SHAP snapshot")
    source_ids = [int(row["id"]) for row in source_rows]
    source_by_org = {int(row["org_id"]): row for row in source_rows}
    if len(source_by_org) != len(source_rows):
        raise RuntimeError("Risk feature table contains duplicate org_id values")

    conn.execute(text(f"DROP TABLE IF EXISTS `mod`.`{_RISK_EXPLANATION_NEXT_TABLE}`"))
    conn.execute(
        text(f"CREATE TABLE `mod`.`{_RISK_EXPLANATION_NEXT_TABLE}` LIKE `mod`.`{RISK_EXPLANATION_TABLE}`")
    )
    conn.execute(text(f"DROP TABLE IF EXISTS `mod`.`{_RISK_EXPLANATION_INPUT_TABLE}`"))
    conn.execute(
        text(f"CREATE TABLE `mod`.`{_RISK_EXPLANATION_INPUT_TABLE}` LIKE `mod`.`{FEAT_TABLE_CLASSIFIER}`")
    )

    generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    batch_count = 0
    for offset in range(0, len(source_ids), batch_size):
        batch_ids = source_ids[offset : offset + batch_size]
        bind_names = [f"id_{index}" for index in range(len(batch_ids))]
        placeholders = ", ".join(f":{name}" for name in bind_names)
        params = dict(zip(bind_names, batch_ids))

        conn.execute(text(f"TRUNCATE TABLE `mod`.`{_RISK_EXPLANATION_INPUT_TABLE}`"))
        conn.execute(
            text(
                f"INSERT INTO `mod`.`{_RISK_EXPLANATION_INPUT_TABLE}` "
                f"SELECT * FROM `mod`.`{FEAT_TABLE_CLASSIFIER}` WHERE `id` IN ({placeholders})"
            ),
            params,
        )
        conn.execute(text(f"DROP TABLE IF EXISTS `mod`.`{_RISK_EXPLANATION_OUTPUT_TABLE}`"))
        conn.execute(
            text(
                "CALL sys.ML_EXPLAIN_TABLE("
                f"'mod.{_RISK_EXPLANATION_INPUT_TABLE}', "
                f"'{MODEL_CLASSIFIER}', "
                f"'mod.{_RISK_EXPLANATION_OUTPUT_TABLE}', "
                "JSON_OBJECT('prediction_explainer', 'shap'))"
            )
        )
        output_rows = [
            dict(row)
            for row in conn.execute(
                text(
                    f"SELECT `org_id`, `ml_results` "
                    f"FROM `mod`.`{_RISK_EXPLANATION_OUTPUT_TABLE}` ORDER BY `org_id`"
                )
            )
            .mappings()
            .all()
        ]
        if len(output_rows) != len(batch_ids):
            raise RuntimeError(
                f"SHAP batch row mismatch: expected {len(batch_ids)}, received {len(output_rows)}"
            )
        insert_rows = []
        for output_row in output_rows:
            org_id = int(output_row["org_id"])
            source_row = source_by_org.get(org_id)
            if source_row is None or not parse_shap_attributions(output_row.get("ml_results")):
                raise RuntimeError(f"SHAP batch contains an invalid explanation for org_id={org_id}")
            insert_rows.append(
                {
                    "org_id": org_id,
                    "model_handle": MODEL_CLASSIFIER,
                    "model_trained_at": model_trained_at,
                    "feature_fingerprint": risk_feature_fingerprint(source_row),
                    "ml_results": output_row["ml_results"],
                    "generated_at": generated_at,
                }
            )
        conn.execute(
            text(
                f"INSERT INTO `mod`.`{_RISK_EXPLANATION_NEXT_TABLE}` "
                "(`org_id`, `model_handle`, `model_trained_at`, `feature_fingerprint`, "
                "`ml_results`, `generated_at`) VALUES "
                "(:org_id, :model_handle, :model_trained_at, :feature_fingerprint, "
                ":ml_results, :generated_at)"
            ),
            insert_rows,
        )
        conn.commit()
        batch_count += 1

    generated_count = int(
        conn.execute(text(f"SELECT COUNT(*) FROM `mod`.`{_RISK_EXPLANATION_NEXT_TABLE}`")).scalar() or 0
    )
    invalid_count = int(
        conn.execute(
            text(
                f"SELECT COUNT(*) FROM `mod`.`{_RISK_EXPLANATION_NEXT_TABLE}` "
                "WHERE COALESCE(JSON_TYPE(JSON_EXTRACT(`ml_results`, '$.attributions')), '') <> 'OBJECT' "
        "OR COALESCE(JSON_LENGTH(JSON_EXTRACT(`ml_results`, '$.attributions')), 0) = 0 "
        "OR `feature_fingerprint` NOT REGEXP '^[0-9a-f]{64}$'"
            )
        ).scalar()
        or 0
    )
    if generated_count != len(source_ids) or invalid_count:
        raise RuntimeError(
            "Incomplete SHAP snapshot: "
            f"source={len(source_ids)}, generated={generated_count}, invalid={invalid_count}"
        )

    conn.execute(text(f"DROP TABLE IF EXISTS `mod`.`{_RISK_EXPLANATION_INPUT_TABLE}`"))
    conn.execute(text(f"DROP TABLE IF EXISTS `mod`.`{_RISK_EXPLANATION_OUTPUT_TABLE}`"))
    conn.execute(text(f"DROP TABLE IF EXISTS `mod`.`{RISK_EXPLANATION_PREVIOUS_TABLE}`"))
    conn.execute(
        text(
            "RENAME TABLE "
            f"`mod`.`{RISK_EXPLANATION_TABLE}` TO `mod`.`{RISK_EXPLANATION_PREVIOUS_TABLE}`, "
            f"`mod`.`{_RISK_EXPLANATION_NEXT_TABLE}` TO `mod`.`{RISK_EXPLANATION_TABLE}`"
        )
    )
    conn.commit()
    return {
        "status": "published",
        "model": MODEL_CLASSIFIER,
        "rows": generated_count,
        "batches": batch_count,
        "generated_at": generated_at.isoformat() + "Z",
    }
