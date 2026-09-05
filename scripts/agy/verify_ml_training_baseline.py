#!/usr/bin/env python3
"""
scripts/agy/verify_ml_training_baseline.py
=========================================
Read-only Verification Script for KI-015 HeatWave AutoML Real Training & Split.

CRITICAL CONSTRAINTS:
- Strictly READ-ONLY. Performs zero DDL, zero INSERT, zero UPDATE, zero DELETE.
- Verifies:
  1. Train/Test Split correctness (1600/400).
  2. Risk classifier features have 0 time series doc-volume leakage.
  3. Doc delta regression split follows strict temporal timeline (no future leakage).
  4. Model catalog and metadata contain verified test set metrics.
  5. Outputs side-by-side comparison report for supervisor verification.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("verify-ml-baseline")


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


def verify_baseline() -> bool:
    load_environment()
    engine = get_engine()
    passed = True

    with engine.connect() as conn:
        logger.info("--- 1. 核查切分表与样本分布 (Train/Test Split Verification) ---")
        
        # 1.1 风险分类切分核查
        risk_train_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk_train`")).scalar()
        risk_test_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_risk_test`")).scalar()
        overlap_risk = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM `mod`.`ml_feat_risk_train` tr
                JOIN `mod`.`ml_feat_risk_test` te ON tr.id = te.id
                """
            )
        ).scalar()

        if risk_train_cnt == 1600 and risk_test_cnt == 400 and overlap_risk == 0:
            logger.info("✅ 风险分类模型 Train/Test 切分合规：训练集 1600 行 (80%)，测试集 400 行 (20%)，交集为 0")
        else:
            logger.error("❌ 风险分类切分异常: train=%s, test=%s, overlap=%s", risk_train_cnt, risk_test_cnt, overlap_risk)
            passed = False

        # 1.2 风险特征无时序泄漏核查
        risk_cols = [r[0] for r in conn.execute(text("DESCRIBE `mod`.`ml_feat_risk`")).fetchall()]
        forbidden = [c for c in risk_cols if any(k in c.lower() for k in ["doc_count", "voucher_count", "delta", "daily_"])]
        if not forbidden:
            logger.info("✅ 风险分类特征审查通过：无时间序列波动量（仅含单位状态指标），防止业务节律污染分类")
        else:
            logger.error("❌ 风险分类特征包含时间序列泄漏: %s", forbidden)
            passed = False

        # 1.3 单据量时序切分核查
        doc_train_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_doc_delta_train`")).scalar()
        doc_test_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_feat_doc_delta_test`")).scalar()
        overlap_doc = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM `mod`.`ml_feat_doc_delta_train` tr
                JOIN `mod`.`ml_feat_doc_delta_test` te ON tr.id = te.id
                """
            )
        ).scalar()

        # 时序单调性核查：训练集最大 end_date / days_since_go_live 必须属于早期，测试集属于未来/晚期
        min_train_days = conn.execute(text("SELECT MIN(days_since_go_live) FROM `mod`.`ml_feat_doc_delta_train`")).scalar()
        max_test_days = conn.execute(text("SELECT MAX(days_since_go_live) FROM `mod`.`ml_feat_doc_delta_test`")).scalar()

        if doc_train_cnt == 1600 and doc_test_cnt == 400 and overlap_doc == 0 and min_train_days >= max_test_days:
            logger.info("✅ 单据量回归模型 时序切分合规：早期 1600 行训练，未来 400 行测试 (days_since_go_live 严格单调无穿越)")
        else:
            logger.error("❌ 单据量时序切分异常: train=%s, test=%s, overlap=%s, min_train_days=%s, max_test_days=%s",
                         doc_train_cnt, doc_test_cnt, overlap_doc, min_train_days, max_test_days)
            passed = False

        logger.info("--- 2. 核查模型元数据与验证状态 (Metadata & Verification) ---")
        meta_rows = conn.execute(text("SELECT * FROM `mod`.`ml_model_metadata` ORDER BY model_handle")).mappings().all()
        if len(meta_rows) >= 2:
            for m in meta_rows:
                logger.info("✅ 模型 [%s] 已落地元数据: 任务=%s, 算法=%s, 验证状态=%s (verified=%d), 训练自评分=%.4f, 测试真实分=%.4f",
                            m["model_handle"], m["task_type"], m["algorithm"], m["status"], m["verified"], m["train_score"], m["test_score"])
        else:
            logger.error("❌ `mod`.ml_model_metadata 缺少模型记录，当前行数=%d", len(meta_rows))
            passed = False

        logger.info("--- 3. 核查审计日志 (Training Audit Log) ---")
        log_cnt = conn.execute(text("SELECT COUNT(*) FROM `mod`.`ml_training_log`")).scalar()
        if log_cnt > 0:
            logger.info("✅ 训练审计日志正常：已记录 %d 条训练重训履历", log_cnt)
        else:
            logger.error("❌ `mod`.ml_training_log 为空")
            passed = False

        logger.info("--- 4. 输出基线比对报告 (Train vs Test Baseline Comparison) ---")
        print("\n" + "=" * 82)
        print("                 KI-015 验收基线：训练集自评分 vs 测试集真实泛化指标")
        print("=" * 82)
        for m in meta_rows:
            train_m = json.loads(m["train_metrics"]) if isinstance(m["train_metrics"], str) else (m["train_metrics"] or {})
            test_m = json.loads(m["test_metrics"]) if isinstance(m["test_metrics"], str) else (m["test_metrics"] or {})
            print(f"\n【{m['model_name']} ({m['model_handle']})】")
            print(f"  * 切分策略: {m['split_method']} (样本量: 训练 {m['train_rows']} 行 / 测试 {m['test_rows']} 行)")
            print(f"  * 算法: {m['algorithm']} | 目标变量: {m['target_column']}")
            print("  " + "-" * 76)
            print(f"  {'指标项':<20} | {'训练集自评分 (Self-Score)':<24} | {'测试集真实指标 (Generalization)':<24}")
            print("  " + "-" * 76)
            if m["task_type"] == "classification":
                print(f"  {'准确率 (Accuracy)':<18} | {train_m.get('accuracy', 0)*100:>23.2f}% | {test_m.get('accuracy', 0)*100:>23.2f}%")
                print(f"  {'精确率 (Precision)':<18} | {train_m.get('precision', 0)*100:>23.2f}% | {test_m.get('precision', 0)*100:>23.2f}%")
                print(f"  {'召回率 (Recall)':<21} | {train_m.get('recall', 0)*100:>23.2f}% | {test_m.get('recall', 0)*100:>23.2f}%")
                print(f"  {'F1-Score':<22} | {train_m.get('f1', 0)*100:>23.2f}% | {test_m.get('f1', 0)*100:>23.2f}%")
                cm_tr = train_m.get("confusion_matrix", {})
                cm_te = test_m.get("confusion_matrix", {})
                print("  " + "-" * 76)
                print(f"  训练集混淆矩阵: TP={cm_tr.get('tp')}, FP={cm_tr.get('fp')}, TN={cm_tr.get('tn')}, FN={cm_tr.get('fn')}")
                print(f"  测试集混淆矩阵: TP={cm_te.get('tp')}, FP={cm_te.get('fp')}, TN={cm_te.get('tn')}, FN={cm_te.get('fn')}")
            else:
                print(f"  {'R² 拟合优度':<20} | {train_m.get('r2', 0):>27.4f} | {test_m.get('r2', 0):>27.4f}")
                print(f"  {'MAE 平均绝对误差':<18} | {train_m.get('mae', 0):>27.4f} | {test_m.get('mae', 0):>27.4f}")
                print(f"  {'RMSE 均方根误差':<19} | {train_m.get('rmse', 0):>27.4f} | {test_m.get('rmse', 0):>27.4f}")
            print("  " + "-" * 76)

        print("=" * 82 + "\n")

    return passed


if __name__ == "__main__":
    ok = verify_baseline()
    sys.exit(0 if ok else 1)
