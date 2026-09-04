"""HeatWave AutoML table, training, and scoring SQL definitions."""

MODEL_REGRESSION = "MOD_REGRESSION_MODEL"
MODEL_CLASSIFIER = "MOD_RISK_CLASSIFIER"

# 训练特征表名（在 mod_s_v2 数据库内）
FEAT_TABLE_REGRESSION = "ml_feat_doc_delta"
FEAT_TABLE_CLASSIFIER = "ml_feat_risk"

# 评分结果表名（在 mod_s_v2 数据库内）
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
     doc_count_prev30, voucher_count_prev30, integration_fail_cnt, daily_doc_delta)
SELECT
    o.id                                                      AS org_id,
    o.region                                                  AS region,
    o.batch_id                                                AS batch_id,
    DATEDIFF(
        (SELECT MAX(snapshot_date) FROM rollout_status_snapshot),
        b.end_date
    )                                                         AS days_since_go_live,
    CASE WHEN s.status IN ('已上线','稳定运行') THEN 1 ELSE 0 END AS launched_flag,
    COALESCE(
        (SELECT COUNT(*) FROM business_document d
         WHERE d.org_id = o.id
           AND DATE(d.submit_time) >= DATE_SUB(
               (SELECT MAX(DATE(submit_time)) FROM business_document),
               INTERVAL 30 DAY)), 0)                          AS doc_count_prev30,
    COALESCE(
        (SELECT COUNT(*) FROM accounting_voucher v
         WHERE v.org_id = o.id
           AND DATE(v.gen_time) >= DATE_SUB(
               (SELECT MAX(DATE(gen_time)) FROM accounting_voucher),
               INTERVAL 30 DAY)), 0)                          AS voucher_count_prev30,
    COALESCE(
        (SELECT COUNT(*) FROM integration_result ir
         JOIN accounting_voucher av ON av.id = ir.voucher_id
         WHERE av.org_id = o.id
           AND ir.status != 'SUCCESS'
           AND DATE(ir.integration_time) >= DATE_SUB(
               (SELECT MAX(DATE(integration_time)) FROM integration_result),
               INTERVAL 30 DAY)), 0)                          AS integration_fail_cnt,
    /* 目标变量：最后一日新增单据数 */
    COALESCE(
        (SELECT COUNT(*) FROM business_document d2
         WHERE d2.org_id = o.id
           AND DATE(d2.submit_time) = (SELECT MAX(DATE(submit_time)) FROM business_document)
        ), 0) * 1.0                                           AS daily_doc_delta
FROM org_unit o
JOIN rollout_batch b ON b.id = o.batch_id
LEFT JOIN (
    SELECT org_id, status
    FROM rollout_status_snapshot
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rollout_status_snapshot)
) s ON s.org_id = o.id
"""

# 上线风险分类：以最新快照截面为基准
_INSERT_FEAT_CLASSIFIER = f"""
INSERT INTO `{FEAT_TABLE_CLASSIFIER}`
    (org_id, region, batch_id, construction_pct, unresolved_issues, high_risk_issues,
     doc_success_pct, integration_success_pct, days_since_start, risk_flag)
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
    /* 目标变量：未解决问题 >= 5 或高风险 >= 2 则标为高风险 */
    CASE
        WHEN COALESCE(im.unresolved_issues, 0) >= 5
          OR COALESCE(rm.high_risk_issues, 0) >= 2
        THEN 1
        ELSE 0
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
"""

# ---------------------------------------------------------------------------
# ML_TRAIN 调用 SQL（需 execute 模式）
# ---------------------------------------------------------------------------

_TRAIN_REGRESSION_SQL = f"""
CALL sys.ML_TRAIN(
    'mod_s_v2.{FEAT_TABLE_REGRESSION}',
    'daily_doc_delta',
    JSON_OBJECT('task', 'regression'),
    @regression_model_handle
)
"""

_TRAIN_CLASSIFIER_SQL = f"""
CALL sys.ML_TRAIN(
    'mod_s_v2.{FEAT_TABLE_CLASSIFIER}',
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
    JSON_OBJECT('run_confirmed', 1)
)
"""

_SCORE_CLASSIFIER_SQL = f"""
CALL sys.ML_PREDICT_TABLE(
    '{FEAT_TABLE_CLASSIFIER}',
    @classifier_model_handle,
    '{SCORE_TABLE_CLASSIFIER}',
    JSON_OBJECT('run_confirmed', 1)
)
"""

# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------
