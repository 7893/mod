#!/usr/bin/env python3
"""
scripts/agy/train_and_evaluate_models.py
========================================
Phase 1: Real HeatWave AutoML Model Training and Train/Test Split Evaluation.

Key Objectives (KI-015 / KI-023):
1. Train/Test Split:
   - Risk Classification (ml_feat_risk / risk_flag):
     Unit random split (80% train / 20% test = 1600/400, deterministic seed=42).
     Cross-sectional features only; excludes time-series doc volume fluctuations.
   - Document Delta Regression (ml_feat_doc_delta / daily_doc_delta):
     Strict temporal split (80% early train / 20% future test = 1600/400).
     Respects timeline progression; strictly avoids future lookahead leakage.
2. HeatWave AutoML Training:
   - Executes sys.ML_TRAIN natively on train tables.
3. Independent Evaluation:
   - Evaluates real generalization metrics on unseen test set using sys.ML_SCORE
     and sys.ML_PREDICT_TABLE.
   - Compares training set self-score vs test set real score.
   - Classification: Accuracy, Precision, Recall, F1, Confusion Matrix.
   - Regression: R², MAE, RMSE.
4. Full Batch Scoring & Metadata Persistence:
   - Scores full feature tables to update ml_score_risk and ml_score_doc_delta.
   - Persists real test scores, verification status, and metrics into:
     * `mod`.ml_model_metadata
     * `mod`.ml_training_log
     * ML_SCHEMA_admin.MODEL_CATALOG
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

HK_TZ = ZoneInfo("Asia/Hong_Kong")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ml-train-eval")


def load_environment() -> None:
    for env_file in [BASE_DIR / ".env.systemd", BASE_DIR / ".env.local", BASE_DIR / ".env"]:
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            break


def ensure_metadata_tables(conn: Any) -> None:
    """Create dedicated ml_model_metadata and ml_training_log tables if not exists."""
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS `mod`.`ml_model_metadata` (
                `model_handle` VARCHAR(64) NOT NULL PRIMARY KEY,
                `model_name` VARCHAR(64) NOT NULL,
                `task_type` VARCHAR(32) NOT NULL,
                `target_column` VARCHAR(64) NOT NULL,
                `algorithm` VARCHAR(64) DEFAULT NULL,
                `split_method` VARCHAR(64) NOT NULL,
                `train_rows` INT NOT NULL,
                `test_rows` INT NOT NULL,
                `train_score` FLOAT NOT NULL,
                `test_score` FLOAT NOT NULL,
                `train_metrics` JSON DEFAULT NULL,
                `test_metrics` JSON DEFAULT NULL,
                `verified` TINYINT NOT NULL DEFAULT 1,
                `status` VARCHAR(32) NOT NULL DEFAULT 'ready',
                `trained_at` DATETIME NOT NULL,
                `verified_at` DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HeatWave AutoML 模型元数据与真实泛化质量分';
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS `mod`.`ml_training_log` (
                `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
                `model_handle` VARCHAR(64) NOT NULL,
                `run_type` VARCHAR(32) NOT NULL DEFAULT 'manual',
                `train_rows` INT NOT NULL,
                `test_rows` INT NOT NULL,
                `train_score` FLOAT NOT NULL,
                `test_score` FLOAT NOT NULL,
                `metrics` JSON DEFAULT NULL,
                `status` VARCHAR(32) NOT NULL DEFAULT 'success',
                `error_message` TEXT DEFAULT NULL,
                `duration_seconds` FLOAT NOT NULL DEFAULT 0.0,
                `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HeatWave AutoML 训练与重训审计日志';
            """
        )
    )
    conn.commit()


def check_feature_integrity(conn: Any) -> dict[str, Any]:
    """Verify feature schemas and check for data leakage."""
    logger.info("Verifying feature table integrity and leakage avoidance...")
    risk_cols = [
        row[0]
        for row in conn.execute(text("DESCRIBE `mod`.`ml_feat_risk`")).fetchall()
    ]
    doc_cols = [
        row[0]
        for row in conn.execute(text("DESCRIBE `mod`.`ml_feat_doc_delta`")).fetchall()
    ]

    # Verify risk model has NO daily transaction/voucher time series features
    forbidden_risk_terms = ["doc_count", "voucher_count", "delta", "daily_"]
    leakage_detected = [
        c for c in risk_cols if any(term in c.lower() for term in forbidden_risk_terms)
    ]
    if leakage_detected:
        raise ValueError(
            f"Leakage detected in risk model features: {leakage_detected}. "
            "Risk features must remain cross-sectional unit state metrics."
        )

    risk_count = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk`")).scalar()
    doc_count = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_doc_delta`")).scalar()

    logger.info(
        "Feature verification passed: ml_feat_risk (%d rows, cross-sectional, 0 time leakage), "
        "ml_feat_doc_delta (%d rows, temporal)",
        risk_count,
        doc_count,
    )
    return {
        "risk_cols": risk_cols,
        "doc_cols": doc_cols,
        "risk_count": risk_count,
        "doc_count": doc_count,
    }


def split_datasets(conn: Any, seed: int = 42) -> dict[str, Any]:
    """
    Perform rigorous train/test split:
    1. Risk model: Random unit split (80% train / 20% test = 1600/400).
    2. Doc delta model: Temporal split (80% train / 20% test = 1600/400).
    """
    logger.info("Executing train/test split on feature tables...")

    # 1. Risk classifier split: random by org (deterministic seed)
    risk_rows = conn.execute(
        text("SELECT id, org_id, risk_flag FROM `mod`.`ml_feat_risk` ORDER BY id")
    ).mappings().all()

    risk_ids = [r["id"] for r in risk_rows]
    rng = random.Random(seed)
    rng.shuffle(risk_ids)

    train_risk_ids = risk_ids[:1600]
    test_risk_ids = risk_ids[1600:]

    # Prepare tables
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_feat_risk_train`"))
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_feat_risk_test`"))
    conn.execute(text("CREATE TABLE `mod`.`ml_feat_risk_train` LIKE `mod`.`ml_feat_risk`"))
    conn.execute(text("CREATE TABLE `mod`.`ml_feat_risk_test` LIKE `mod`.`ml_feat_risk`"))

    # Batch insert into train and test
    train_ids_str = ",".join(map(str, train_risk_ids))
    test_ids_str = ",".join(map(str, test_risk_ids))

    conn.execute(
        text(
            f"INSERT INTO `mod`.`ml_feat_risk_train` SELECT * FROM `mod`.`ml_feat_risk` WHERE id IN ({train_ids_str})"
        )
    )
    conn.execute(
        text(
            f"INSERT INTO `mod`.`ml_feat_risk_test` SELECT * FROM `mod`.`ml_feat_risk` WHERE id IN ({test_ids_str})"
        )
    )

    train_risk_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk_train`")).scalar()
    test_risk_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk_test`")).scalar()
    train_risk_pos = conn.execute(
        text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk_train` WHERE risk_flag = 1")
    ).scalar()
    test_risk_pos = conn.execute(
        text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk_test` WHERE risk_flag = 1")
    ).scalar()

    logger.info(
        "Risk split complete: Train %d (pos: %d, %.1f%%), Test %d (pos: %d, %.1f%%)",
        train_risk_cnt,
        train_risk_pos,
        (train_risk_pos / train_risk_cnt * 100) if train_risk_cnt else 0,
        test_risk_cnt,
        test_risk_pos,
        (test_risk_pos / test_risk_cnt * 100) if test_risk_cnt else 0,
    )

    # 2. Doc delta regression split: strictly temporal
    # Earliest batches / highest days_since_go_live -> Train; latest -> Test
    doc_rows = conn.execute(
        text(
            """
            SELECT id, org_id, batch_id, days_since_go_live, daily_doc_delta
            FROM `mod`.`ml_feat_doc_delta`
            ORDER BY days_since_go_live DESC, batch_id ASC, id ASC
            """
        )
    ).mappings().all()

    train_doc_ids = [r["id"] for r in doc_rows[:1600]]
    test_doc_ids = [r["id"] for r in doc_rows[1600:]]

    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_feat_doc_delta_train`"))
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_feat_doc_delta_test`"))
    conn.execute(text("CREATE TABLE `mod`.`ml_feat_doc_delta_train` LIKE `mod`.`ml_feat_doc_delta`"))
    conn.execute(text("CREATE TABLE `mod`.`ml_feat_doc_delta_test` LIKE `mod`.`ml_feat_doc_delta`"))

    train_doc_str = ",".join(map(str, train_doc_ids))
    test_doc_str = ",".join(map(str, test_doc_ids))

    conn.execute(
        text(
            f"INSERT INTO `mod`.`ml_feat_doc_delta_train` SELECT * FROM `mod`.`ml_feat_doc_delta` WHERE id IN ({train_doc_str})"
        )
    )
    conn.execute(
        text(
            f"INSERT INTO `mod`.`ml_feat_doc_delta_test` SELECT * FROM `mod`.`ml_feat_doc_delta` WHERE id IN ({test_doc_str})"
        )
    )

    train_doc_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_doc_delta_train`")).scalar()
    test_doc_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_doc_delta_test`")).scalar()

    logger.info(
        "Doc delta temporal split complete: Train %d rows (earlier timeline), Test %d rows (future timeline)",
        train_doc_cnt,
        test_doc_cnt,
    )
    conn.commit()

    return {
        "risk": {
            "train_count": train_risk_cnt,
            "test_count": test_risk_cnt,
            "train_pos": train_risk_pos,
            "test_pos": test_risk_pos,
            "split_method": f"unit_random_80_20(seed={seed})",
        },
        "doc": {
            "train_count": train_doc_cnt,
            "test_count": test_doc_cnt,
            "split_method": "temporal_80_20(days_since_go_live_desc)",
        },
    }


def train_heatwave_models(conn: Any) -> dict[str, str]:
    """Train classification and regression models using HeatWave AutoML sys.ML_TRAIN."""
    logger.info("Executing native HeatWave AutoML sys.ML_TRAIN for both models...")

    models = {}

    # 1. Train Classification Model: MOD_RISK_CLASSIFIER
    cls_handle = "MOD_RISK_CLASSIFIER"
    logger.info("Training %s on `mod`.ml_feat_risk_train...", cls_handle)
    try:
        conn.execute(text(f"CALL sys.ML_MODEL_UNLOAD('{cls_handle}')"))
    except Exception:
        pass
    conn.execute(
        text(f"DELETE FROM `ML_SCHEMA_admin`.`MODEL_CATALOG` WHERE `model_handle` = '{cls_handle}'")
    )
    conn.commit()

    t0 = time.time()
    conn.execute(text(f"SET @cls_handle = '{cls_handle}'"))
    conn.execute(
        text(
            """
            CALL sys.ML_TRAIN(
                '`mod`.ml_feat_risk_train',
                'risk_flag',
                JSON_OBJECT(
                    'task', 'classification',
                    'exclude_column_list', JSON_ARRAY('id', 'org_id')
                ),
                @cls_handle
            )
            """
        )
    )
    conn.commit()
    cls_duration = time.time() - t0
    logger.info("Classifier %s trained in %.2f seconds", cls_handle, cls_duration)
    models[cls_handle] = "trained"

    # 2. Train Regression Model: MOD_REGRESSION_MODEL
    reg_handle = "MOD_REGRESSION_MODEL"
    logger.info("Training %s on `mod`.ml_feat_doc_delta_train...", reg_handle)
    try:
        conn.execute(text(f"CALL sys.ML_MODEL_UNLOAD('{reg_handle}')"))
    except Exception:
        pass
    conn.execute(
        text(f"DELETE FROM `ML_SCHEMA_admin`.`MODEL_CATALOG` WHERE `model_handle` = '{reg_handle}'")
    )
    conn.commit()

    t0 = time.time()
    conn.execute(text(f"SET @reg_handle = '{reg_handle}'"))
    conn.execute(
        text(
            """
            CALL sys.ML_TRAIN(
                '`mod`.ml_feat_doc_delta_train',
                'daily_doc_delta',
                JSON_OBJECT(
                    'task', 'regression',
                    'exclude_column_list', JSON_ARRAY('id', 'org_id')
                ),
                @reg_handle
            )
            """
        )
    )
    conn.commit()
    reg_duration = time.time() - t0
    logger.info("Regression %s trained in %.2f seconds", reg_handle, reg_duration)
    models[reg_handle] = "trained"

    return models


def evaluate_classifier(conn: Any, handle: str = "MOD_RISK_CLASSIFIER") -> dict[str, Any]:
    """Evaluate classification model on train set (self-score) and test set (real score)."""
    logger.info("Evaluating classifier %s on train vs test datasets...", handle)

    conn.execute(text(f"CALL sys.ML_MODEL_LOAD('{handle}', NULL)"))

    # Train predictions (self-score)
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_eval_risk_train`"))
    conn.execute(
        text(
            f"""
            CALL sys.ML_PREDICT_TABLE(
                '`mod`.ml_feat_risk_train',
                '{handle}',
                '`mod`.ml_eval_risk_train',
                NULL
            )
            """
        )
    )

    # Test predictions (unseen generalization)
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_eval_risk_test`"))
    conn.execute(
        text(
            f"""
            CALL sys.ML_PREDICT_TABLE(
                '`mod`.ml_feat_risk_test',
                '{handle}',
                '`mod`.ml_eval_risk_test',
                NULL
            )
            """
        )
    )
    conn.commit()

    # Calculate metrics helper
    def calc_metrics(table: str) -> dict[str, Any]:
        rows = conn.execute(
            text(f"SELECT Prediction, risk_flag FROM `mod`.`{table}`")
        ).mappings().all()
        tp = sum(1 for r in rows if r["Prediction"] == 1 and r["risk_flag"] == 1)
        fp = sum(1 for r in rows if r["Prediction"] == 1 and r["risk_flag"] == 0)
        tn = sum(1 for r in rows if r["Prediction"] == 0 and r["risk_flag"] == 0)
        fn = sum(1 for r in rows if r["Prediction"] == 0 and r["risk_flag"] == 1)
        total = len(rows)
        accuracy = (tp + tn) / total if total else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
        return {
            "total": total,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "confusion_matrix": {
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
            },
        }

    train_metrics = calc_metrics("ml_eval_risk_train")
    test_metrics = calc_metrics("ml_eval_risk_test")

    # Call native sys.ML_SCORE to confirm test accuracy
    conn.execute(text("SET @test_score = 0.0"))
    conn.execute(
        text(
            f"""
            CALL sys.ML_SCORE(
                '`mod`.ml_feat_risk_test',
                'risk_flag',
                '{handle}',
                'accuracy',
                @test_score,
                NULL
            )
            """
        )
    )
    native_test_score = conn.execute(text("SELECT @test_score")).scalar()

    logger.info(
        "Classifier Train (Self-Score) Accuracy: %.2f%% | Test (Real) Accuracy: %.2f%% (native: %s)",
        train_metrics["accuracy"] * 100,
        test_metrics["accuracy"] * 100,
        str(native_test_score),
    )

    return {
        "handle": handle,
        "task": "classification",
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "train_score": train_metrics["accuracy"],
        "test_score": test_metrics["accuracy"],
        "native_test_score": native_test_score,
    }


def evaluate_regression(conn: Any, handle: str = "MOD_REGRESSION_MODEL") -> dict[str, Any]:
    """Evaluate regression model on train set (self-score) and test set (real score)."""
    logger.info("Evaluating regression %s on train vs test datasets...", handle)

    conn.execute(text(f"CALL sys.ML_MODEL_LOAD('{handle}', NULL)"))

    # Train predictions (self-score)
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_eval_doc_delta_train`"))
    conn.execute(
        text(
            f"""
            CALL sys.ML_PREDICT_TABLE(
                '`mod`.ml_feat_doc_delta_train',
                '{handle}',
                '`mod`.ml_eval_doc_delta_train',
                NULL
            )
            """
        )
    )

    # Test predictions (unseen generalization)
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_eval_doc_delta_test`"))
    conn.execute(
        text(
            f"""
            CALL sys.ML_PREDICT_TABLE(
                '`mod`.ml_feat_doc_delta_test',
                '{handle}',
                '`mod`.ml_eval_doc_delta_test',
                NULL
            )
            """
        )
    )
    conn.commit()

    # Calculate regression metrics
    def calc_reg_metrics(table: str) -> dict[str, Any]:
        rows = conn.execute(
            text(f"SELECT Prediction, daily_doc_delta FROM `mod`.`{table}`")
        ).mappings().all()
        y_true = [float(r["daily_doc_delta"]) for r in rows]
        y_pred = [float(r["Prediction"]) for r in rows]
        n = len(y_true)
        if n == 0:
            return {"total": 0, "r2": 0.0, "mae": 0.0, "rmse": 0.0}

        mean_y = sum(y_true) / n
        ss_tot = sum((y - mean_y) ** 2 for y in y_true)
        ss_res = sum((y - p) ** 2 for y, p in zip(y_true, y_pred))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        mae = sum(abs(y - p) for y, p in zip(y_true, y_pred)) / n
        rmse = math.sqrt(ss_res / n)

        return {
            "total": n,
            "r2": round(r2, 4),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
        }

    train_metrics = calc_reg_metrics("ml_eval_doc_delta_train")
    test_metrics = calc_reg_metrics("ml_eval_doc_delta_test")

    # Call native sys.ML_SCORE to confirm test r2
    conn.execute(text("SET @test_score = 0.0"))
    conn.execute(
        text(
            f"""
            CALL sys.ML_SCORE(
                '`mod`.ml_feat_doc_delta_test',
                'daily_doc_delta',
                '{handle}',
                'r2',
                @test_score,
                NULL
            )
            """
        )
    )
    native_test_score = conn.execute(text("SELECT @test_score")).scalar()

    logger.info(
        "Regression Train (Self-Score) R²: %.4f, MAE: %.4f | Test (Real) R²: %.4f, MAE: %.4f (native R²: %s)",
        train_metrics["r2"],
        train_metrics["mae"],
        test_metrics["r2"],
        test_metrics["mae"],
        str(native_test_score),
    )

    return {
        "handle": handle,
        "task": "regression",
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "train_score": train_metrics["r2"],
        "test_score": test_metrics["r2"],
        "native_test_score": native_test_score,
    }


def execute_full_batch_scoring(conn: Any) -> None:
    """Score the full 2,000 units so downstream dashboard displays real predictions."""
    logger.info("Executing full batch scoring for ml_score_risk and ml_score_doc_delta...")
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_score_risk`"))
    conn.execute(
        text(
            """
            CALL sys.ML_PREDICT_TABLE(
                '`mod`.ml_feat_risk',
                'MOD_RISK_CLASSIFIER',
                '`mod`.ml_score_risk',
                NULL
            )
            """
        )
    )
    conn.execute(text("DROP TABLE IF EXISTS `mod`.`ml_score_doc_delta`"))
    conn.execute(
        text(
            """
            CALL sys.ML_PREDICT_TABLE(
                '`mod`.ml_feat_doc_delta',
                'MOD_REGRESSION_MODEL',
                '`mod`.ml_score_doc_delta',
                NULL
            )
            """
        )
    )
    conn.commit()
    risk_scored = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_score_risk`")).scalar()
    doc_scored = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_score_doc_delta`")).scalar()
    logger.info("Full batch scoring complete: %d risk units, %d doc units", risk_scored, doc_scored)


def persist_metadata_and_audit(
    conn: Any,
    cls_eval: dict[str, Any],
    reg_eval: dict[str, Any],
    run_type: str = "manual",
    total_duration: float = 0.0,
) -> None:
    """Persist real quality scores and audit history into MySQL tables and MODEL_CATALOG."""
    logger.info("Persisting real model quality and verification status...")
    now = datetime.now()

    models_to_save = [
        (cls_eval, "MOD_RISK_CLASSIFIER", "批次延期风险智能分类模型", "risk_flag", "unit_random_80_20"),
        (reg_eval, "MOD_REGRESSION_MODEL", "业务单据日增量预测模型", "daily_doc_delta", "temporal_80_20"),
    ]

    for ev, handle, name, target, split_method in models_to_save:
        row = conn.execute(
            text(
                f"""
                SELECT model_type, model_metadata
                FROM `ML_SCHEMA_admin`.`MODEL_CATALOG`
                WHERE model_handle = '{handle}'
                LIMIT 1
                """
            )
        ).mappings().first()

        algo = row.get("model_type") if row else "HeatWave AutoML"
        raw_meta = row.get("model_metadata") if row else None
        meta_dict = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})

        # 1. Update ML_SCHEMA_admin.MODEL_CATALOG model_metadata
        # Crucial: replace false self-score with real test score and mark verified=True
        meta_dict["model_quality"] = ev["test_score"]
        meta_dict["test_score"] = ev["test_score"]
        meta_dict["train_score"] = ev["train_score"]
        meta_dict["verified"] = True
        meta_dict["verified_at"] = now.isoformat()
        meta_dict["test_metrics"] = ev["test_metrics"]
        meta_dict["train_metrics"] = ev["train_metrics"]
        meta_dict["split_method"] = split_method

        conn.execute(
            text(
                """
                UPDATE `ML_SCHEMA_admin`.`MODEL_CATALOG`
                SET model_metadata = :meta
                WHERE model_handle = :handle
                """
            ),
            {"meta": json.dumps(meta_dict, ensure_ascii=False), "handle": handle},
        )

        # 2. Upsert into `mod`.ml_model_metadata
        conn.execute(
            text(
                """
                INSERT INTO `mod`.`ml_model_metadata` (
                    model_handle, model_name, task_type, target_column, algorithm,
                    split_method, train_rows, test_rows, train_score, test_score,
                    train_metrics, test_metrics, verified, status, trained_at, verified_at
                ) VALUES (
                    :handle, :name, :task, :target, :algo,
                    :split, :train_rows, :test_rows, :train_score, :test_score,
                    :train_metrics, :test_metrics, 1, 'ready', :trained_at, :verified_at
                ) ON DUPLICATE KEY UPDATE
                    algorithm = VALUES(algorithm),
                    split_method = VALUES(split_method),
                    train_rows = VALUES(train_rows),
                    test_rows = VALUES(test_rows),
                    train_score = VALUES(train_score),
                    test_score = VALUES(test_score),
                    train_metrics = VALUES(train_metrics),
                    test_metrics = VALUES(test_metrics),
                    verified = 1,
                    status = 'ready',
                    trained_at = VALUES(trained_at),
                    verified_at = VALUES(verified_at)
                """
            ),
            {
                "handle": handle,
                "name": name,
                "task": ev["task"],
                "target": target,
                "algo": algo or ("DecisionTreeClassifier" if ev["task"] == "classification" else "LinearRegression"),
                "split": split_method,
                "train_rows": ev["train_metrics"]["total"],
                "test_rows": ev["test_metrics"]["total"],
                "train_score": ev["train_score"],
                "test_score": ev["test_score"],
                "train_metrics": json.dumps(ev["train_metrics"]),
                "test_metrics": json.dumps(ev["test_metrics"]),
                "trained_at": now,
                "verified_at": now,
            },
        )

        # 3. Append to `mod`.ml_training_log
        conn.execute(
            text(
                """
                INSERT INTO `mod`.`ml_training_log` (
                    model_handle, run_type, train_rows, test_rows, train_score, test_score,
                    metrics, status, duration_seconds, created_at
                ) VALUES (
                    :handle, :run_type, :train_rows, :test_rows, :train_score, :test_score,
                    :metrics, 'success', :duration, :created_at
                )
                """
            ),
            {
                "handle": handle,
                "run_type": run_type,
                "train_rows": ev["train_metrics"]["total"],
                "test_rows": ev["test_metrics"]["total"],
                "train_score": ev["train_score"],
                "test_score": ev["test_score"],
                "metrics": json.dumps(
                    {
                        "train": ev["train_metrics"],
                        "test": ev["test_metrics"],
                        "native_test_score": ev.get("native_test_score"),
                    }
                ),
                "duration": round(total_duration / 2.0, 2),
                "created_at": now,
            },
        )

    conn.commit()
    logger.info("Metadata and audit persistence completed successfully.")


def print_comparison_report(cls_eval: dict[str, Any], reg_eval: dict[str, Any]) -> None:
    """Print clean comparison report highlighting true generalization vs self-score."""
    print("\n" + "=" * 80)
    print("      KI-015 HEATWAVE AUTOML 真实训练评估基线报告 (TRAIN/TEST SPLIT)")
    print("=" * 80)

    # Classification Table
    cm = cls_eval["test_metrics"]["confusion_matrix"]
    cm_train = cls_eval["train_metrics"]["confusion_matrix"]
    print("\n[模型 1 · 批次延期风险智能分类 (MOD_RISK_CLASSIFIER)]")
    print("  - 特征表: `mod`.ml_feat_risk | 目标列: risk_flag (0 正常 / 1 高风险)")
    print("  - 切分方式: 按单位随机切分 (80% 训练 1600 行 / 20% 测试 400 行, seed=42)")
    print("  - 特征审查: 无时间序列单据量波动特征，杜绝业务节律造成的误判泄漏")
    print("  " + "-" * 70)
    print(f"  {'指标':<16} | {'训练集自评分 (虚高假象)':<24} | {'测试集独立评估 (真实泛化)':<24}")
    print("  " + "-" * 70)
    print(
        f"  {'准确率 (Accuracy)':<14} | {cls_eval['train_metrics']['accuracy']*100:>19.2f}% | {cls_eval['test_metrics']['accuracy']*100:>19.2f}%"
    )
    print(
        f"  {'精确率 (Precision)':<14} | {cls_eval['train_metrics']['precision']*100:>19.2f}% | {cls_eval['test_metrics']['precision']*100:>19.2f}%"
    )
    print(
        f"  {'召回率 (Recall)':<17} | {cls_eval['train_metrics']['recall']*100:>19.2f}% | {cls_eval['test_metrics']['recall']*100:>19.2f}%"
    )
    print(
        f"  {'F1-Score':<18} | {cls_eval['train_metrics']['f1']*100:>19.2f}% | {cls_eval['test_metrics']['f1']*100:>19.2f}%"
    )
    print("  " + "-" * 70)
    print(f"  训练集混淆矩阵: TP={cm_train['tp']}, FP={cm_train['fp']}, TN={cm_train['tn']}, FN={cm_train['fn']}")
    print(f"  测试集混淆矩阵: TP={cm['tp']}, FP={cm['fp']}, TN={cm['tn']}, FN={cm['fn']}")

    # Regression Table
    print("\n[模型 2 · 业务单据日增量预测 (MOD_REGRESSION_MODEL)]")
    print("  - 特征表: `mod`.ml_feat_doc_delta | 目标列: daily_doc_delta")
    print("  - 切分方式: 严格按时间先后切分 (早期批次 1600 行训练 / 晚期批次 400 行测试)")
    print("  - 特征审查: 严禁打乱时序，前瞻窗口严格限制于截面以前，杜绝未来泄漏")
    print("  " + "-" * 70)
    print(f"  {'指标':<16} | {'训练集自评分 (虚高拟合)':<24} | {'测试集独立评估 (真实泛化)':<24}")
    print("  " + "-" * 70)
    print(
        f"  {'R² 拟合优度':<16} | {reg_eval['train_metrics']['r2']:>23.4f} | {reg_eval['test_metrics']['r2']:>23.4f}"
    )
    print(
        f"  {'MAE 平均绝对误差':<14} | {reg_eval['train_metrics']['mae']:>23.4f} | {reg_eval['test_metrics']['mae']:>23.4f}"
    )
    print(
        f"  {'RMSE 均方根误差':<15} | {reg_eval['train_metrics']['rmse']:>23.4f} | {reg_eval['test_metrics']['rmse']:>23.4f}"
    )
    print("  " + "-" * 70)
    print("\n结论: 真实测试集独立评估完成，彻底消除 100% 自评分虚假指标，已将真实质量分落库。")
    print("=" * 80 + "\n")


def run_full_pipeline(run_type: str = "manual") -> dict[str, Any]:
    """Orchestrate the full train/split/eval/persist pipeline."""
    load_environment()
    engine = get_engine()
    t_start = time.time()

    with engine.connect() as conn:
        ensure_metadata_tables(conn)
        check_feature_integrity(conn)
        split_info = split_datasets(conn)
        train_heatwave_models(conn)
        cls_eval = evaluate_classifier(conn)
        reg_eval = evaluate_regression(conn)
        execute_full_batch_scoring(conn)
        duration = time.time() - t_start
        persist_metadata_and_audit(conn, cls_eval, reg_eval, run_type=run_type, total_duration=duration)
        print_comparison_report(cls_eval, reg_eval)

    return {
        "status": "success",
        "split_info": split_info,
        "classifier_eval": cls_eval,
        "regression_eval": reg_eval,
        "duration_seconds": round(duration, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="KI-015 HeatWave Model Real Training & Evaluation")
    parser.add_argument("--split-only", action="store_true", help="Only perform train/test split")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate existing models and persist metadata")
    parser.add_argument("--dry-run", action="store_true", help="Validate features and print plan without training")
    parser.add_argument("--run-type", default="manual", help="Run type for audit log (manual / scheduled)")
    args = parser.parse_args()

    load_environment()
    engine = get_engine()

    if args.dry_run:
        with engine.connect() as conn:
            check_feature_integrity(conn)
            print("Dry run feature integrity check passed. Plan validated.")
        return

    if args.eval_only:
        with engine.connect() as conn:
            ensure_metadata_tables(conn)
            t_start = time.time()
            cls_eval = evaluate_classifier(conn)
            reg_eval = evaluate_regression(conn)
            execute_full_batch_scoring(conn)
            duration = time.time() - t_start
            persist_metadata_and_audit(conn, cls_eval, reg_eval, run_type="manual", total_duration=duration)
            print_comparison_report(cls_eval, reg_eval)
        return

    if args.split_only:
        with engine.connect() as conn:
            ensure_metadata_tables(conn)
            check_feature_integrity(conn)
            split_datasets(conn)
            print("Split datasets completed.")
        return

    run_full_pipeline(run_type=args.run_type)


if __name__ == "__main__":
    main()
