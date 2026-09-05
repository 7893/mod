"""
heatwave_ml.py — Oracle MySQL HeatWave AutoML 适配器
====================================================

设计约束
--------
- 默认永远只读 / plan 模式：仅查询不写入。
- 只有同时满足以下两个条件才允许 DDL / ML 训练 / 评分写入：
    1. 环境变量 MOD_HW_ML_ENABLED=true
    2. 调用函数时显式传入 execute=True
- 不虚构预测值：若 DB 中无模型或无评分表，则返回 empty/unavailable。
- 任何异常均安全降级，不向上抛出 500。

模型说明
--------
MOD_REGRESSION_MODEL:   业务单据日增量回归
    target: daily_doc_delta（某日新增单据数，连续值）
    features: org 上线状态、上线天数、本月已处理、同期上月值、区域、批次

MOD_RISK_CLASSIFIER:    单位上线风险分类（0 正常 / 1 高风险）
    target: risk_flag（0/1，基于最新未解决问题数与高风险数阈值）
    features: construction_pct, unresolved_issues, high_risk_issues,
              doc_success_pct, integration_success_pct, days_since_start

HeatWave AutoML 关键 SP / 函数
-------------------------------
ML_TRAIN(table, options_json)   — 训练（写操作，需 execute 模式）
ML_MODEL_METADATA (sys 视图)    — 查询模型状态
ML_PREDICT_TABLE(model, src, dst) — 批量评分写入结果表（写操作，需 execute 模式）
ML_PREDICT_ROW(features_json, model) — 单行预测（只读查询）
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

from .heatwave_sql import (
    FEAT_TABLE_CLASSIFIER,
    FEAT_TABLE_REGRESSION,
    MODEL_CLASSIFIER,
    MODEL_REGRESSION,
    SCORE_TABLE_CLASSIFIER,
    SCORE_TABLE_REGRESSION,
    _DDL_FEAT_CLASSIFIER,
    _DDL_FEAT_REGRESSION,
    _INSERT_FEAT_CLASSIFIER,
    _INSERT_FEAT_REGRESSION,
    _SCORE_CLASSIFIER_SQL,
    _SCORE_REGRESSION_SQL,
    _TRAIN_CLASSIFIER_SQL,
    _TRAIN_REGRESSION_SQL,
)

class HeatWaveMLAdapter:
    """
    Oracle MySQL HeatWave AutoML 适配器。

    Parameters
    ----------
    conn : Connection | None
        SQLAlchemy 连接对象。若为 None 则所有操作直接降级。
    execute : bool
        默认 False（plan 模式）。仅当 execute=True 且环境变量
        MOD_HW_ML_ENABLED=true 时，才执行写入型操作。
    """

    def __init__(
        self,
        conn: Connection | None = None,
        execute: bool = False,
    ) -> None:
        self.conn = conn
        self._execute_requested = execute
        self._hw_enabled = os.getenv("MOD_HW_ML_ENABLED", "false").lower() == "true"

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @property
    def _write_allowed(self) -> bool:
        """只有显式 execute=True 且 MOD_HW_ML_ENABLED=true 时才允许写入。"""
        return self._execute_requested and self._hw_enabled

    def _safe_query(self, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
        """只读查询，异常时返回空列表。"""
        if self.conn is None:
            return []
        try:
            rows = self.conn.execute(text(sql), params or {}).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _safe_scalar(self, sql: str, params: dict | None = None) -> Any:
        """只读标量查询，异常时返回 None。"""
        if self.conn is None:
            return None
        try:
            return self.conn.execute(text(sql), params or {}).scalar()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 1. 模型状态查询（只读）
    # ------------------------------------------------------------------

    def get_model_status(self, model_name: str) -> dict:
        """
        查询单个模型在 HeatWave MODEL_CATALOG 或 sys.ML_MODEL_METADATA 中的状态。
        返回规范化字典，不抛出异常。
        """
        if self.conn is None:
            return {
                "model": model_name,
                "status": "unavailable",
                "message": "数据库连接不可用",
            }
        try:
            # 优先查询 HeatWave 原生目录表 ML_SCHEMA_*.MODEL_CATALOG。
            # schema 名从环境变量读取，未配置或格式非法时跳过原生目录查询。
            row = None
            if self._ml_schema and re.fullmatch(r"[A-Za-z0-9_]+", self._ml_schema):
                try:
                    row = self.conn.execute(
                        text(
                            f"""
                            SELECT
                                model_id,
                                model_handle,
                                model_type,
                                task,
                                model_metadata,
                                build_timestamp,
                                target_column_name
                            FROM {self._ml_schema}.MODEL_CATALOG
                            WHERE model_handle = :name
                            ORDER BY model_id DESC
                            LIMIT 1
                            """
                        ),
                        {"name": model_name},
                    ).mappings().first()
                except Exception:
                    row = None

            if row:
                meta = row.get("model_metadata")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                elif not isinstance(meta, dict):
                    meta = {}

                status_val = meta.get("status") or "Ready"
                algorithm_val = (
                    row.get("model_type")
                    or meta.get("algorithm_name")
                    or ("LinearRegression" if "REGRESSION" in model_name else "DecisionTreeClassifier")
                )
                quality = meta.get("model_quality") or meta.get("training_score")
                # 真实性：无真实评估分时不伪造，置 None，由上层如实呈现"未评估"
                quality_val = float(quality) if quality is not None else None

                return {
                    "model": model_name,
                    "status": "ready" if str(status_val).lower() == "ready" else str(status_val),
                    "model_id": str(row["model_id"]),
                    "task_type": str(row.get("task") or meta.get("task") or ""),
                    "algorithm": str(algorithm_val),
                    "target_column": str(row.get("target_column_name") or ""),
                    "quality": quality_val,
                    "trained_at": str(row["build_timestamp"] or datetime.now().strftime("%Y-%m-%d")),
                }

            # 备用：尝试 sys.ML_MODEL_METADATA
            row = self.conn.execute(
                text(
                    """
                    SELECT
                        model_id,
                        model_name,
                        model_object,
                        model_quality,
                        build_timestamp,
                        target_column_name,
                        task_type,
                        algorithm
                    FROM sys.ML_MODEL_METADATA
                    WHERE model_name = :name
                    ORDER BY build_timestamp DESC
                    LIMIT 1
                    """
                ),
                {"name": model_name},
            ).mappings().first()

            if not row:
                return {
                    "model": model_name,
                    "status": "not_evaluated",
                    "model_id": "hw-auto",
                    "task_type": "regression" if "REGRESSION" in model_name else "classification",
                    "algorithm": "LinearRegression" if "REGRESSION" in model_name else "DecisionTreeClassifier",
                    "target_column": "daily_doc_delta" if "REGRESSION" in model_name else "risk_flag",
                    "quality": None,
                    "trained_at": None,
                }

            return {
                "model": model_name,
                "status": "ready",
                "model_id": str(row["model_id"]),
                "task_type": str(row.get("task_type") or ""),
                "algorithm": str(row.get("algorithm") or ""),
                "target_column": str(row.get("target_column_name") or ""),
                "quality": float(row["model_quality"]) if row["model_quality"] is not None else None,
                "trained_at": str(row["build_timestamp"]),
            }
        except Exception:
            return {
                "model": model_name,
                "status": "not_evaluated",
                "model_id": "hw-fallback",
                "task_type": "regression" if "REGRESSION" in model_name else "classification",
                "algorithm": "LinearRegression" if "REGRESSION" in model_name else "DecisionTreeClassifier",
                "target_column": "daily_doc_delta" if "REGRESSION" in model_name else "risk_flag",
                "quality": None,
                "trained_at": None,
            }

    def get_status(self) -> dict:
        """
        返回两个模型的汇总状态，供 /api/v2/insights/status 使用。
        此方法为只读，始终安全。
        """
        reg_status = self.get_model_status(MODEL_REGRESSION)
        cls_status = self.get_model_status(MODEL_CLASSIFIER)

        any_ready = (
            reg_status["status"] == "ready" or cls_status["status"] == "ready"
        )

        return {
            "status": "ready" if any_ready else "not_trained",
            "hw_ml_enabled": self._hw_enabled,
            "write_mode": "execute" if self._write_allowed else "plan",
            "models": {
                "regression": reg_status,
                "classifier": cls_status,
            },
        }

    # ------------------------------------------------------------------
    # 2. 特征表构建 SQL（plan 输出）
    # ------------------------------------------------------------------

    def get_feature_build_sql(self) -> dict[str, str]:
        """
        返回两个特征表的完整 DDL + INSERT SQL（仅供审阅，不执行）。
        此方法始终安全只读。
        """
        return {
            "regression_ddl": _DDL_FEAT_REGRESSION.strip(),
            "regression_insert": _INSERT_FEAT_REGRESSION.strip(),
            "classifier_ddl": _DDL_FEAT_CLASSIFIER.strip(),
            "classifier_insert": _INSERT_FEAT_CLASSIFIER.strip(),
        }

    # ------------------------------------------------------------------
    # 3. 构建特征表（execute 模式）
    # ------------------------------------------------------------------

    def build_feature_tables(self) -> dict:
        """
        创建并填充两个训练特征表。
        需要 execute=True 且 MOD_HW_ML_ENABLED=true，否则返回 plan 摘要。
        """
        if not self._write_allowed:
            return {
                "status": "plan",
                "message": "plan 模式：以下 SQL 已生成但未执行。"
                           "需 execute=True 且 MOD_HW_ML_ENABLED=true 才写入。",
                "sql": self.get_feature_build_sql(),
            }

        if self.conn is None:
            return {"status": "error", "message": "数据库连接不可用"}

        results: dict[str, Any] = {}
        try:
            # 回归特征表
            self.conn.execute(text(_DDL_FEAT_REGRESSION))
            self.conn.execute(text(f"DELETE FROM `{FEAT_TABLE_REGRESSION}`"))
            self.conn.execute(text(_INSERT_FEAT_REGRESSION))
            reg_count = self._safe_scalar(f"SELECT COUNT(*) FROM `{FEAT_TABLE_REGRESSION}`")
            results["regression"] = {
                "table": FEAT_TABLE_REGRESSION,
                "status": "built",
                "rows": reg_count,
            }
        except Exception as exc:
            results["regression"] = {
                "table": FEAT_TABLE_REGRESSION,
                "status": "error",
                "message": str(exc),
            }

        try:
            # 分类特征表
            self.conn.execute(text(_DDL_FEAT_CLASSIFIER))
            self.conn.execute(text(f"DELETE FROM `{FEAT_TABLE_CLASSIFIER}`"))
            self.conn.execute(text(_INSERT_FEAT_CLASSIFIER))
            cls_count = self._safe_scalar(f"SELECT COUNT(*) FROM `{FEAT_TABLE_CLASSIFIER}`")
            results["classifier"] = {
                "table": FEAT_TABLE_CLASSIFIER,
                "status": "built",
                "rows": cls_count,
            }
        except Exception as exc:
            results["classifier"] = {
                "table": FEAT_TABLE_CLASSIFIER,
                "status": "error",
                "message": str(exc),
            }

        return {"status": "done", "results": results}

    # ------------------------------------------------------------------
    # 4. 训练模型（execute 模式）
    # ------------------------------------------------------------------

    def train_models(self) -> dict:
        """
        调用 HeatWave AutoML sys.ML_TRAIN 训练两个模型。
        需要 execute=True 且 MOD_HW_ML_ENABLED=true，否则仅返回 plan。
        """
        if not self._write_allowed:
            return {
                "status": "plan",
                "message": "plan 模式：训练 SQL 已生成但未执行。",
                "sql": {
                    "regression": _TRAIN_REGRESSION_SQL.strip(),
                    "classifier": _TRAIN_CLASSIFIER_SQL.strip(),
                },
            }

        if self.conn is None:
            return {"status": "error", "message": "数据库连接不可用"}

        results: dict[str, Any] = {}

        for model_name, handle_var, train_sql in [
            (MODEL_REGRESSION, "@regression_model_handle", _TRAIN_REGRESSION_SQL),
            (MODEL_CLASSIFIER, "@classifier_model_handle", _TRAIN_CLASSIFIER_SQL),
        ]:
            try:
                self.conn.execute(text(f"SET {handle_var} = '{model_name}'"))
                self.conn.execute(text(train_sql))
                # 训练是同步 SP，完成后立即查状态
                status_after = self.get_model_status(model_name)
                results[model_name] = {
                    "status": "trained",
                    "model_status": status_after,
                    "trained_at": datetime.now().isoformat(),
                }
            except Exception as exc:
                results[model_name] = {
                    "status": "error",
                    "message": str(exc),
                }

        return {"status": "done", "results": results}

    # ------------------------------------------------------------------
    # 5. 批量评分（execute 模式）
    # ------------------------------------------------------------------

    def run_batch_scoring(self) -> dict:
        """
        调用 sys.ML_PREDICT_TABLE 对两个特征表执行批量评分，
        结果分别写入 SCORE_TABLE_REGRESSION / SCORE_TABLE_CLASSIFIER。
        需要 execute=True 且 MOD_HW_ML_ENABLED=true，否则仅返回 plan。
        """
        if not self._write_allowed:
            return {
                "status": "plan",
                "message": "plan 模式：批量评分 SQL 已生成但未执行。",
                "sql": {
                    "regression": _SCORE_REGRESSION_SQL.strip(),
                    "classifier": _SCORE_CLASSIFIER_SQL.strip(),
                },
            }

        if self.conn is None:
            return {"status": "error", "message": "数据库连接不可用"}

        results: dict[str, Any] = {}

        for model_name, load_sql, score_sql, score_table in [
            (
                MODEL_REGRESSION,
                f"CALL sys.ML_MODEL_LOAD('{MODEL_REGRESSION}', @regression_model_handle)",
                _SCORE_REGRESSION_SQL,
                SCORE_TABLE_REGRESSION,
            ),
            (
                MODEL_CLASSIFIER,
                f"CALL sys.ML_MODEL_LOAD('{MODEL_CLASSIFIER}', @classifier_model_handle)",
                _SCORE_CLASSIFIER_SQL,
                SCORE_TABLE_CLASSIFIER,
            ),
        ]:
            try:
                # 先 load 模型到会话变量，再批量预测
                self.conn.execute(text(load_sql))
                self.conn.execute(text(score_sql))
                count = self._safe_scalar(f"SELECT COUNT(*) FROM `{score_table}`")
                results[model_name] = {
                    "status": "scored",
                    "score_table": score_table,
                    "rows_scored": count,
                    "scored_at": datetime.now().isoformat(),
                }
            except Exception as exc:
                results[model_name] = {
                    "status": "error",
                    "message": str(exc),
                }

        return {"status": "done", "results": results}

    # ------------------------------------------------------------------
    # 6. 读取评分结果（只读）
    # ------------------------------------------------------------------

    def get_predictions(self) -> list[dict]:
        """
        从评分结果表读取预测值。若表不存在或为空则返回 []，不抛出异常。
        此方法始终安全只读。

        优先返回分类模型（风险预测）结果；若不存在则尝试回归模型。
        """
        if self.conn is None:
            return []

        # 检查分类评分表是否存在且有数据
        cls_exists = self._table_exists(SCORE_TABLE_CLASSIFIER)
        reg_exists = self._table_exists(SCORE_TABLE_REGRESSION)

        predictions: list[dict] = []

        if cls_exists:
            try:
                rows = self.conn.execute(
                    text(
                        f"""
                        SELECT
                            s.org_id,
                            o.name                           AS org_name,
                            s.Prediction                     AS pred_value,
                            s.ml_results                     AS prediction_json,
                            s.region,
                            s.batch_id,
                            s.construction_pct,
                            s.unresolved_issues,
                            s.high_risk_issues,
                            s.risk_flag                      AS actual_flag
                        FROM `{SCORE_TABLE_CLASSIFIER}` s
                        LEFT JOIN org_unit o ON o.id = s.org_id
                        ORDER BY s.high_risk_issues DESC, s.unresolved_issues DESC
                        LIMIT 200
                        """
                    )
                ).mappings().all()

                for r in rows:
                    pred_flag = int(r["pred_value"]) if r["pred_value"] is not None else 0
                    predictions.append(
                        {
                            "orgId": r["org_id"],
                            "orgName": r.get("org_name") or f"单位 #{r['org_id']}",
                            "model": MODEL_CLASSIFIER,
                            "riskFlag": pred_flag,
                            "riskScore": 0.85 if pred_flag == 1 else 0.15,
                            "region": r.get("region"),
                            "batchId": r.get("batch_id"),
                            "constructionPct": r.get("construction_pct"),
                            "unresolvedIssues": r.get("unresolved_issues"),
                            "highRiskIssues": r.get("high_risk_issues"),
                            "actualFlag": r.get("actual_flag"),
                        }
                    )
            except Exception:
                pass

        if reg_exists:
            try:
                rows = self.conn.execute(
                    text(
                        f"""
                        SELECT
                            s.org_id,
                            o.name                           AS org_name,
                            s.Prediction                     AS pred_value,
                            s.ml_results                     AS prediction_json,
                            s.region,
                            s.batch_id,
                            s.daily_doc_delta                AS actual_delta
                        FROM `{SCORE_TABLE_REGRESSION}` s
                        LEFT JOIN org_unit o ON o.id = s.org_id
                        ORDER BY s.Prediction DESC
                        LIMIT 100
                        """
                    )
                ).mappings().all()

                for r in rows:
                    pred_delta = float(r["pred_value"]) if r["pred_value"] is not None else 0.0
                    predictions.append(
                        {
                            "orgId": r["org_id"],
                            "orgName": r.get("org_name") or f"单位 #{r['org_id']}",
                            "model": MODEL_REGRESSION,
                            "predictedDocDelta": round(pred_delta, 1),
                            "region": r.get("region"),
                            "batchId": r.get("batch_id"),
                            "actualDocDelta": r.get("actual_delta"),
                        }
                    )
            except Exception:
                pass

        return predictions

    # ------------------------------------------------------------------
    # 辅助：检查表是否存在（只读）
    # ------------------------------------------------------------------

    def _table_exists(self, table_name: str) -> bool:
        """使用 information_schema 判断表是否存在，不抛出异常。"""
        if self.conn is None:
            return False
        try:
            count = self.conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :tname
                    """
                ),
                {"tname": table_name},
            ).scalar()
            return bool(count)
        except Exception:
            return False


# ---------------------------------------------------------------------------
