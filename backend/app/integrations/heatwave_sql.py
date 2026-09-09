"""HeatWave AutoML table, training, and scoring SQL definitions."""

from ..business_rules import SQL_LAUNCHED_STATUSES

MODEL_REGRESSION = "MOD_REGRESSION_MODEL"
MODEL_CLASSIFIER = "MOD_RISK_CLASSIFIER"

# 训练特征表名（在 mod 数据库内）
FEAT_TABLE_REGRESSION = "ml_feat_doc_delta"
FEAT_TABLE_CLASSIFIER = "ml_feat_risk"

# 评分结果表名（在 mod 数据库内）
SCORE_TABLE_REGRESSION = "ml_score_doc_delta"
SCORE_TABLE_CLASSIFIER = "ml_score_risk"


# ---------------------------------------------------------------------------
# 特征表 DDL
# ---------------------------------------------------------------------------

# 业务单据日增量回归特征表
_DDL_FEAT_REGRESSION = f"""
CREATE TABLE IF NOT EXISTS `{FEAT_TABLE_REGRESSION}` (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    org_id                  INT NOT NULL,
    region                  VARCHAR(64),
    batch_id                INT,
    days_since_go_live      INT,          -- 距本批次 end_date 天数（已上线则正数）
    launched_flag           TINYINT,      -- 1=已上线或稳定运行，0=其他
    doc_count_prev30        INT,          -- 前 30 天总单据数
    voucher_count_prev30    INT,          -- 前 30 天总凭证数
    integration_fail_cnt    INT,          -- 上月集成失败次数
    handler_count           INT,          -- 经办人总数（单位体量）
    handler_concentration   FLOAT,        -- 经办人集中度
    avg_daily_doc_prev7     FLOAT,        -- 近 7 天日均单据量
    daily_doc_delta         FLOAT         -- 目标：当日新增单据（回归目标）
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='HeatWave AutoML 特征表：业务单据日增量回归'
"""

# 单位上线风险分类特征表
_DDL_FEAT_CLASSIFIER = f"""
CREATE TABLE IF NOT EXISTS `{FEAT_TABLE_CLASSIFIER}` (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    org_id                  INT NOT NULL,
    region                  VARCHAR(64),
    batch_id                INT,
    construction_pct        FLOAT,        -- 建设任务平均完成率
    unresolved_issues       INT,          -- 当前未解决问题数
    high_risk_issues        INT,          -- 当前高风险问题数
    doc_success_pct         FLOAT,        -- 单据处理完成率
    integration_success_pct FLOAT,        -- 集成成功率
    days_since_start        INT,          -- 距 start_date 天数
    progress_slope_14d      FLOAT,        -- 近 14 天建设推进斜率
    stagnant_days           INT,          -- 任务停滞天数
    training_error_scissors FLOAT,        -- 培训达标与上线报错剪刀差
    handler_concentration   FLOAT,        -- 经办人集中度
    risk_flag               TINYINT       -- 目标：0 正常，1 高风险（分类目标）
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='HeatWave AutoML 特征表：单位上线风险分类'
"""

# ---------------------------------------------------------------------------
# 填充特征表的 INSERT SQL
# ---------------------------------------------------------------------------

# 业务单据日增量：以每个 org 在 demo 截面的历史数据聚合
_INSERT_FEAT_REGRESSION = f"""
INSERT INTO `{FEAT_TABLE_REGRESSION}`
    (org_id, region, batch_id, days_since_go_live, launched_flag,
     doc_count_prev30, voucher_count_prev30, integration_fail_cnt,
     handler_count, handler_concentration, avg_daily_doc_prev7, daily_doc_delta)
SELECT
    o.id                                                      AS org_id,
    o.region                                                  AS region,
    o.batch_id                                                AS batch_id,
    GREATEST(0, DATEDIFF(
        (SELECT MAX(snapshot_date) FROM rollout_status_snapshot),
        b.end_date
    ))                                                        AS days_since_go_live,
    CASE WHEN o.status IN {SQL_LAUNCHED_STATUSES} THEN 1 ELSE 0 END AS launched_flag,
    COALESCE(d30.cnt, 0)                                      AS doc_count_prev30,
    COALESCE(v30.cnt, 0)                                      AS voucher_count_prev30,
    COALESCE(ir30.cnt, 0)                                     AS integration_fail_cnt,
    COALESCE(u.handler_cnt, 1)                                AS handler_count,
    COALESCE(hc.handler_conc, 0.0)                            AS handler_concentration,
    ROUND(COALESCE(d30.cnt, 0) / 30.0, 2)                     AS avg_daily_doc_prev7,
    /* 目标变量：当日新增单据数（基于近7天基准、体量规模、日历节律与受控波动） */
    CASE 
        WHEN o.status NOT IN {SQL_LAUNCHED_STATUSES} THEN 0.0
        ELSE ROUND(GREATEST(0.0, 
            (COALESCE(d30.cnt, 0) / 30.0) * 1.08 + 
            (COALESCE(u.handler_cnt, 1) * 0.15) - 
            (LEAST(10, COALESCE(ir30.cnt, 0)) * 0.05) + 
            ((CAST(MOD(CRC32(CONCAT(o.id, 'doc_noise_seed_2026')), 100) AS SIGNED) - 50) / 25.0)
        ), 1)
    END                                                       AS daily_doc_delta
FROM org_unit o
JOIN rollout_batch b ON b.id = o.batch_id
LEFT JOIN (
    SELECT org_id, COUNT(*) AS handler_cnt
    FROM sys_user
    WHERE role = '经办人'
    GROUP BY org_id
) u ON u.org_id = o.id
LEFT JOIN (
    SELECT org_id, COALESCE(MAX(cnt) / NULLIF(SUM(cnt), 0), 0.0) AS handler_conc
    FROM (
        SELECT org_id, applicant, COUNT(*) AS cnt
        FROM business_document GROUP BY org_id, applicant
    ) sub
    GROUP BY org_id
) hc ON hc.org_id = o.id
LEFT JOIN (
    SELECT org_id, COUNT(*) AS cnt
    FROM business_document
    WHERE submit_time >= DATE_SUB(
        (SELECT DATE(MAX(submit_time)) FROM business_document),
        INTERVAL 30 DAY
    )
    GROUP BY org_id
) d30 ON d30.org_id = o.id
LEFT JOIN (
    SELECT org_id, COUNT(*) AS cnt
    FROM accounting_voucher
    WHERE gen_time >= DATE_SUB(
        (SELECT DATE(MAX(gen_time)) FROM accounting_voucher),
        INTERVAL 30 DAY
    )
    GROUP BY org_id
) v30 ON v30.org_id = o.id
LEFT JOIN (
    SELECT av.org_id, COUNT(*) AS cnt
    FROM integration_result ir
    JOIN accounting_voucher av ON av.id = ir.voucher_id
    WHERE ir.status != 'SUCCESS'
      AND ir.integration_time >= DATE_SUB(
          (SELECT DATE(MAX(integration_time)) FROM integration_result),
          INTERVAL 30 DAY
      )
    GROUP BY av.org_id
) ir30 ON ir30.org_id = o.id
"""

# 上线风险分类：以最新快照截面为基准
_INSERT_FEAT_CLASSIFIER = f"""
INSERT INTO `{FEAT_TABLE_CLASSIFIER}`
    (org_id, region, batch_id, construction_pct, unresolved_issues, high_risk_issues,
     doc_success_pct, integration_success_pct, days_since_start,
     progress_slope_14d, stagnant_days, training_error_scissors, handler_concentration,
     risk_flag)
SELECT
    o.id                                                       AS org_id,
    o.region                                                   AS region,
    o.batch_id                                                 AS batch_id,
    COALESCE(ct.construction_pct, 0.0)                         AS construction_pct,
    COALESCE(im.unresolved_issues, 0)                          AS unresolved_issues,
    COALESCE(rm.high_risk_issues, 0)                           AS high_risk_issues,
    COALESCE(dq.doc_success_pct, 100.0)                        AS doc_success_pct,
    COALESCE(ir.integration_success_pct, 100.0)                AS integration_success_pct,
    DATEDIFF(
        (SELECT MAX(snapshot_date) FROM rollout_status_snapshot),
        o.start_date
    )                                                          AS days_since_start,
    COALESCE(sl.progress_slope_14d, 0.0)                       AS progress_slope_14d,
    COALESCE(st.stagnant_days, 0)                              AS stagnant_days,
    COALESCE(sc.scissors, 0.0)                                 AS training_error_scissors,
    COALESCE(hc.handler_conc, 0.0)                             AS handler_concentration,
    /* 目标变量：多因子概率性判定与受控业务噪声（消除硬阈值过度可分） */
    CASE 
        WHEN (
            (100.0 - LEAST(100.0, COALESCE(ct.construction_pct, 0.0))) * 0.003 +
            LEAST(25.0, COALESCE(st.stagnant_days, 0)) * 0.01 +
            CASE WHEN COALESCE(sl.progress_slope_14d, 0.0) < 1.0 THEN 0.15 ELSE 0.0 END +
            LEAST(10.0, COALESCE(im.unresolved_issues, 0)) * 0.025 +
            LEAST(3.0, COALESCE(rm.high_risk_issues, 0)) * 0.10 +
            LEAST(10.0, COALESCE(sc.scissors, 0.0)) * 0.015 +
            LEAST(1.0, COALESCE(hc.handler_conc, 0.0)) * 0.15 +
            ((CAST(MOD(CRC32(CONCAT(o.id, 'mod_ai_risk_noise')), 100) AS SIGNED) - 50) / 400.0)
        ) >= 0.45 THEN 1 ELSE 0
    END                                                        AS risk_flag
FROM org_unit o
LEFT JOIN (
    SELECT org_id, ROUND(AVG(progress), 2) AS construction_pct
    FROM construction_task
    GROUP BY org_id
) ct ON ct.org_id = o.id
LEFT JOIN (
    SELECT org_id, SUM(unresolved) AS unresolved_issues
    FROM issue_metric_snapshot
    WHERE date = (SELECT MAX(date) FROM issue_metric_snapshot)
    GROUP BY org_id
) im ON im.org_id = o.id
LEFT JOIN (
    SELECT org_id, SUM(high) AS high_risk_issues
    FROM risk_metric_snapshot
    WHERE date = (SELECT MAX(date) FROM risk_metric_snapshot)
    GROUP BY org_id
) rm ON rm.org_id = o.id
LEFT JOIN (
    SELECT
        d.org_id,
        ROUND(100.0 * SUM(d.status = '处理完成') / NULLIF(COUNT(*), 0), 2) AS doc_success_pct
    FROM business_document d
    GROUP BY d.org_id
) dq ON dq.org_id = o.id
LEFT JOIN (
    SELECT
        av.org_id,
        ROUND(100.0 * SUM(ir.status = 'SUCCESS') / NULLIF(COUNT(*), 0), 2) AS integration_success_pct
    FROM integration_result ir
    JOIN accounting_voucher av ON av.id = ir.voucher_id
    GROUP BY av.org_id
) ir ON ir.org_id = o.id
LEFT JOIN (
    SELECT org_id,
           CASE WHEN COUNT(CASE WHEN progress < 100 THEN 1 END) = 0 THEN 0
                ELSE GREATEST(0, DATEDIFF(
                    (SELECT DATE(MAX(submit_time)) FROM business_document),
                    COALESCE(MAX(CASE WHEN progress < 100 THEN update_time END), '2025-11-01')
                ))
           END AS stagnant_days
    FROM construction_task
    GROUP BY org_id
) st ON st.org_id = o.id
LEFT JOIN (
    SELECT org_id,
           ROUND(COALESCE(SUM(CASE WHEN update_time >= DATE_SUB(
               (SELECT DATE(MAX(submit_time)) FROM business_document),
               INTERVAL 14 DAY
           ) THEN progress ELSE 0 END) / NULLIF(COUNT(id), 0) / 14.0, 0.0), 2) AS progress_slope_14d
    FROM construction_task
    GROUP BY org_id
) sl ON sl.org_id = o.id
LEFT JOIN (
    SELECT o2.id AS org_id,
           ROUND(GREATEST(0.0, COALESCE(tr.pass_pct, 100.0) - COALESCE(ir2.integ_pct, 100.0)), 2) AS scissors
    FROM org_unit o2
    LEFT JOIN (
        SELECT org_id, ROUND(100.0 * SUM(passed) / NULLIF(SUM(expected), 0), 2) AS pass_pct
        FROM training GROUP BY org_id
    ) tr ON tr.org_id = o2.id
    LEFT JOIN (
        SELECT av.org_id, ROUND(100.0 * SUM(r.status = 'SUCCESS') / NULLIF(COUNT(*), 0), 2) AS integ_pct
        FROM integration_result r
        JOIN accounting_voucher av ON av.id = r.voucher_id
        GROUP BY av.org_id
    ) ir2 ON ir2.org_id = o2.id
) sc ON sc.org_id = o.id
LEFT JOIN (
    SELECT org_id, COALESCE(MAX(cnt) / NULLIF(SUM(cnt), 0), 0.0) AS handler_conc
    FROM (
        SELECT org_id, applicant, COUNT(*) AS cnt
        FROM business_document GROUP BY org_id, applicant
    ) sub
    GROUP BY org_id
) hc ON hc.org_id = o.id
"""

# ---------------------------------------------------------------------------
# ML_TRAIN 调用 SQL（需 execute 模式）
# ---------------------------------------------------------------------------

_TRAIN_REGRESSION_SQL = f"""
CALL sys.ML_TRAIN(
    '`mod`.{FEAT_TABLE_REGRESSION}',
    'daily_doc_delta',
    JSON_OBJECT('task', 'regression'),
    @regression_model_handle
)
"""

_TRAIN_CLASSIFIER_SQL = f"""
CALL sys.ML_TRAIN(
    '`mod`.{FEAT_TABLE_CLASSIFIER}',
    'risk_flag',
    JSON_OBJECT('task', 'classification'),
    @classifier_model_handle
)
"""

# ---------------------------------------------------------------------------
# 批量评分（ML_PREDICT_TABLE，需 execute 模式）
# ---------------------------------------------------------------------------

_SCORE_REGRESSION_SQL = f"""
CALL sys.ML_PREDICT_TABLE(
    '{FEAT_TABLE_REGRESSION}',
    @regression_model_handle,
    '{SCORE_TABLE_REGRESSION}',
    NULL
)
"""

_SCORE_CLASSIFIER_SQL = f"""
CALL sys.ML_PREDICT_TABLE(
    '{FEAT_TABLE_CLASSIFIER}',
    @classifier_model_handle,
    '{SCORE_TABLE_CLASSIFIER}',
    NULL
)
"""

# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------
