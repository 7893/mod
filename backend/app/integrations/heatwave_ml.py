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
import logging
import math
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

logger = logging.getLogger(__name__)

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
        db_user = os.getenv("MOD_DB_USER", "admin")
        user_prefix = db_user.split("@")[0] if db_user else "admin"
        self._ml_schema = os.getenv("MOD_HW_ML_SCHEMA") or f"ML_SCHEMA_{user_prefix}"

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
        查询单个模型在 HeatWave MODEL_CATALOG 或 mod.ml_model_metadata 中的状态。
        严格区分"模型已训练"与"模型已验证（有测试集真实分）"，无真实质量分时不谎报 ready。
        返回规范化字典，不抛出异常。
        """
        if self.conn is None:
            return {
                "model": model_name,
                "status": "unavailable",
                "message": "数据库连接不可用",
            }
        try:
            # 1. 优先读取业务库中具有严谨 train/test split 独立评估认证的元数据表
            meta_rows = self._safe_query(
                """
                SELECT
                    model_handle,
                    model_name,
                    task_type,
                    target_column,
                    algorithm,
                    split_method,
                    train_rows,
                    test_rows,
                    train_score,
                    test_score,
                    train_metrics,
                    test_metrics,
                    verified,
                    status,
                    trained_at,
                    verified_at
                FROM `mod`.`ml_model_metadata`
                WHERE model_handle = :handle
                LIMIT 1
                """,
                {"handle": model_name},
            )
            if meta_rows:
                m = meta_rows[0]
                is_verified = bool(m.get("verified"))
                quality_val = float(m["test_score"]) if (is_verified and m.get("test_score") is not None) else None
                return {
                    "model": model_name,
                    "status": "ready" if (is_verified and m.get("status") == "ready") else "not_evaluated",
                    "verified": is_verified,
                    "model_id": str(m.get("model_handle")),
                    "task_type": str(m.get("task_type") or ""),
                    "algorithm": str(m.get("algorithm") or ""),
                    "target_column": str(m.get("target_column") or ""),
                    "quality": quality_val,
                    "train_score": float(m["train_score"]) if m.get("train_score") is not None else None,
                    "test_score": float(m["test_score"]) if m.get("test_score") is not None else None,
                    "split_method": m.get("split_method"),
                    "trained_at": str(m.get("trained_at") or ""),
                    "verified_at": str(m.get("verified_at") or ""),
                }

            # 2. 次选查询 HeatWave 原生目录表 ML_SCHEMA_*.MODEL_CATALOG。
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
                is_verified = bool(meta.get("verified"))
                quality = meta.get("test_score") or meta.get("model_quality") if is_verified else None
                quality_val = float(quality) if quality is not None else None

                return {
                    "model": model_name,
                    "status": "ready" if (is_verified and str(status_val).lower() == "ready") else "not_evaluated",
                    "verified": is_verified,
                    "model_id": str(row["model_id"]),
                    "task_type": str(row.get("task") or meta.get("task") or ""),
                    "algorithm": str(algorithm_val),
                    "target_column": str(row.get("target_column_name") or ""),
                    "quality": quality_val,
                    "trained_at": str(row["build_timestamp"] or datetime.now().strftime("%Y-%m-%d")),
                }

            # 3. 兜底回退：未评估
            return {
                "model": model_name,
                "status": "not_evaluated",
                "verified": False,
                "model_id": "hw-auto",
                "task_type": "regression" if "REGRESSION" in model_name else "classification",
                "algorithm": "LinearRegression" if "REGRESSION" in model_name else "DecisionTreeClassifier",
                "target_column": "daily_doc_delta" if "REGRESSION" in model_name else "risk_flag",
                "quality": None,
                "trained_at": None,
            }
        except Exception:
            return {
                "model": model_name,
                "status": "not_evaluated",
                "verified": False,
                "model_id": "hw-fallback",
                "task_type": "regression" if "REGRESSION" in model_name else "classification",
                "algorithm": "LinearRegression" if "REGRESSION" in model_name else "DecisionTreeClassifier",
                "target_column": "daily_doc_delta" if "REGRESSION" in model_name else "risk_flag",
                "quality": None,
                "trained_at": None,
            }

    def get_status(self) -> dict:
        """
        返回两个模型的汇总状态，供 /api/insights/status 使用。
        此方法为只读，始终安全。
        """
        reg_status = self.get_model_status(MODEL_REGRESSION)
        cls_status = self.get_model_status(MODEL_CLASSIFIER)

        any_ready = (
            reg_status["status"] == "ready" or cls_status["status"] == "ready"
        )
        both_verified = (
            bool(reg_status.get("verified")) and bool(cls_status.get("verified"))
        )

        return {
            "status": "ready" if any_ready else "not_trained",
            "verified": both_verified,
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
                # 先 load 模型到会话变量，清理目标表后执行批量预测
                self.conn.execute(text(load_sql))
                self.conn.execute(text(f"DROP TABLE IF EXISTS `{score_table}`"))
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
                            s.progress_slope_14d,
                            s.stagnant_days,
                            s.training_error_scissors,
                            s.handler_concentration,
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
                    risk_score = None
                    pred_json_raw = r.get("prediction_json")
                    if pred_json_raw:
                        try:
                            pj = json.loads(pred_json_raw) if isinstance(pred_json_raw, str) else pred_json_raw
                            probs = pj.get("probabilities", {})
                            value = probs.get("1")
                            if value is not None and not isinstance(value, bool):
                                candidate = float(value)
                                if math.isfinite(candidate) and 0 <= candidate <= 1:
                                    risk_score = round(candidate, 4)
                        except (ValueError, TypeError, AttributeError):
                            logger.debug("risk probability unavailable (org_id=%s)", r.get("org_id"))

                    predictions.append(
                        {
                            "orgId": r["org_id"],
                            "orgName": r.get("org_name") or f"单位 #{r['org_id']}",
                            "model": MODEL_CLASSIFIER,
                            "riskFlag": pred_flag,
                            "riskScore": risk_score,
                            "probabilitySource": "MODEL" if risk_score is not None else "UNAVAILABLE",
                            "predictionPurpose": "synthetic_rule_fit",
                            "region": r.get("region"),
                            "batchId": r.get("batch_id"),
                            "constructionPct": r.get("construction_pct"),
                            "unresolvedIssues": r.get("unresolved_issues"),
                            "highRiskIssues": r.get("high_risk_issues"),
                            "progressSlope14d": r.get("progress_slope_14d"),
                            "stagnantDays": r.get("stagnant_days"),
                            "trainingErrorScissors": r.get("training_error_scissors"),
                            "handlerConcentration": r.get("handler_concentration"),
                            "actualFlag": r.get("actual_flag"),
                        }
                    )
            except Exception as ex:
                logger.warning("读取分类模型评分表失败，风险预测返回空: %s", type(ex).__name__)

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
            except Exception as ex:
                logger.warning("读取回归模型评分表失败，增量预测返回空: %s", type(ex).__name__)

        return predictions

    # ------------------------------------------------------------------
    # 7. 单单位 SHAP 特征归因解释（只读）
    # ------------------------------------------------------------------

    def explain_risk(self, org_id: int) -> dict:
        """
        对指定单位调用 sys.ML_EXPLAIN_ROW 或本地特征贡献计算，
        输出 Top 3 致险因子及归因权重百分比。
        严格遵循 KI-034 任务 3：
        - 优先调用 sys.ML_EXPLAIN_ROW (shap)
        - 若数据库不支持或未训练，安全降级至基于真实特征偏离度的归因计算，不崩溃
        """
        if self.conn is None:
            return {
                "orgId": org_id,
                "status": "unavailable",
                "explanationSource": "UNAVAILABLE",
                "topAttributions": [],
            }

        # 1. 查询该单位的特征行与基本信息
        feat_rows = self._safe_query(
            f"""
            SELECT
                f.org_id,
                o.name AS org_name,
                f.region,
                f.batch_id,
                f.construction_pct,
                f.unresolved_issues,
                f.high_risk_issues,
                f.doc_success_pct,
                f.integration_success_pct,
                f.days_since_start,
                f.progress_slope_14d,
                f.stagnant_days,
                f.training_error_scissors,
                f.handler_concentration,
                f.risk_flag
            FROM `{FEAT_TABLE_CLASSIFIER}` f
            LEFT JOIN org_unit o ON o.id = f.org_id
            WHERE f.org_id = :oid
            LIMIT 1
            """,
            {"oid": org_id},
        )

        if not feat_rows:
            return {
                "orgId": org_id,
                "status": "not_found",
                "explanationSource": "UNAVAILABLE",
                "message": f"未在特征表中找到单位 #{org_id} 的特征数据",
                "topAttributions": [],
            }

        row = feat_rows[0]
        factor_defs = {
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

        attributions: dict[str, float] = {}
        explanation_source = "UNAVAILABLE"

        # 2. 尝试调用 HeatWave sys.ML_EXPLAIN_ROW
        try:
            feats_dict = {
                "region": str(row.get("region") or ""),
                "batch_id": int(row.get("batch_id") or 1),
                "construction_pct": float(row.get("construction_pct") or 0.0),
                "unresolved_issues": int(row.get("unresolved_issues") or 0),
                "high_risk_issues": int(row.get("high_risk_issues") or 0),
                "doc_success_pct": float(row["doc_success_pct"] if row.get("doc_success_pct") is not None else 100.0),
                "integration_success_pct": float(row["integration_success_pct"] if row.get("integration_success_pct") is not None else 100.0),
                "days_since_start": int(row.get("days_since_start") or 0),
                "progress_slope_14d": float(row.get("progress_slope_14d") or 0.0),
                "stagnant_days": int(row.get("stagnant_days") or 0),
                "training_error_scissors": float(row.get("training_error_scissors") or 0.0),
                "handler_concentration": float(row.get("handler_concentration") or 0.0),
            }
            explain_res = self.conn.execute(
                text(
                    f"SELECT sys.ML_EXPLAIN_ROW(:feats, '{MODEL_CLASSIFIER}', JSON_OBJECT('prediction_explainer', 'shap'))"
                ),
                {"feats": json.dumps(feats_dict)},
            ).scalar()

            if explain_res:
                parsed = json.loads(explain_res) if isinstance(explain_res, str) else explain_res
                raw_attrs = parsed.get("ml_results", {}).get("attributions", {})
                if not raw_attrs:
                    raw_attrs = {k: v for k, v in parsed.items() if k.endswith("_attribution")}

                for k, v in raw_attrs.items():
                    col = k.replace("_attribution", "")
                    if col in factor_defs and v is not None and math.isfinite(float(v)):
                        attributions[col] = float(v)
                if attributions:
                    explanation_source = "HEATWAVE_SHAP"
        except Exception as ex:
            logger.warning("HeatWave SHAP 归因查询失败，降级为确定性偏离度: %s", type(ex).__name__)

        # 3. 若 HeatWave 原生 SHAP 未产生有效归因，执行确定性因果偏离度降级计算
        if not attributions:
            const_pct = float(row.get("construction_pct") or 0.0)
            stagnant = int(row.get("stagnant_days") or 0)
            unres = int(row.get("unresolved_issues") or 0)
            high_r = int(row.get("high_risk_issues") or 0)
            slope = float(row.get("progress_slope_14d") or 0.0)
            scissors = float(row.get("training_error_scissors") or 0.0)
            conc = float(row.get("handler_concentration") or 0.0)
            integ_pct = float(row["integration_success_pct"] if row.get("integration_success_pct") is not None else 100.0)

            attributions = {
                "high_risk_issues": high_r * 0.35,
                "unresolved_issues": unres * 0.15,
                "stagnant_days": (stagnant / 10.0) * 0.25,
                "progress_slope_14d": max(0.0, (2.0 - slope) * 0.18),
                "training_error_scissors": (scissors / 5.0) * 0.20,
                "handler_concentration": (conc / 0.5) * 0.18,
                "construction_pct": max(0.0, (90.0 - const_pct) * 0.01),
                "integration_success_pct": max(0.0, (98.0 - integ_pct) * 0.02),
            }
            explanation_source = "RULE_BASED"

        # 4. 提取对风险正向贡献最大的 Top 3 因子并归一化为百分比
        sorted_factors = sorted(attributions.items(), key=lambda x: x[1], reverse=True)
        top3 = [(k, v) for k, v in sorted_factors[:3] if v > 0]

        total_weight = sum(w for _, w in top3)
        top_attributions = []
        for feat_name, weight in top3:
            name, desc = factor_defs.get(feat_name, (feat_name, "业务指标偏离"))
            weight_pct = round((weight / total_weight) * 100)
            top_attributions.append({
                "factor": feat_name,
                "factorName": name,
                "attribution": round(weight, 4),
                "weightPct": weight_pct,
                "description": desc,
            })

        # 确保三项权重和恰好等于 100%
        if top_attributions:
            curr_sum = sum(a["weightPct"] for a in top_attributions)
            if curr_sum != 100:
                top_attributions[0]["weightPct"] += (100 - curr_sum)

        return {
            "status": "ok",
            "explanationSource": explanation_source,
            "weightBasis": "positive_top3_relative",
            "predictionPurpose": "synthetic_rule_fit",
            "orgId": org_id,
            "orgName": row.get("org_name") or f"单位 #{org_id}",
            "riskFlag": int(row.get("risk_flag") or 0),
            "region": row.get("region"),
            "batchId": row.get("batch_id"),
            "constructionPct": row.get("construction_pct"),
            "unresolvedIssues": row.get("unresolved_issues"),
            "highRiskIssues": row.get("high_risk_issues"),
            "stagnantDays": row.get("stagnant_days"),
            "progressSlope14d": row.get("progress_slope_14d"),
            "trainingErrorScissors": row.get("training_error_scissors"),
            "handlerConcentration": row.get("handler_concentration"),
            "topAttributions": top_attributions,
        }

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
