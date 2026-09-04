-- ========================================================
-- MOD Platform V2 Simulation Database Schema Definition (V2.5)
-- Generated strictly according to Docs 02, 08, 09
-- ========================================================

-- 1. 推广批次表
CREATE TABLE rollout_batch (
    id INT PRIMARY KEY COMMENT '批次ID',
    name VARCHAR(50) NOT NULL COMMENT '批次名称',
    start_date DATE NOT NULL COMMENT '计划开始日期',
    end_date DATE NOT NULL COMMENT '计划结束日期',
    status VARCHAR(50) NOT NULL COMMENT '批次总体状态'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='推广批次字典表';

-- 2. 组织单位表
CREATE TABLE org_unit (
    id INT PRIMARY KEY COMMENT '单位ID',
    name VARCHAR(255) NOT NULL UNIQUE COMMENT '单位名称',
    batch_id INT NOT NULL COMMENT '所属推广批次ID',
    status VARCHAR(50) NOT NULL COMMENT '当前推广阶段状态',
    region VARCHAR(50) NOT NULL COMMENT '所属省份/地区',
    start_date DATE NOT NULL COMMENT '推广启动日期',
    end_date DATE NOT NULL COMMENT '推广计划完成日期',
    FOREIGN KEY (batch_id) REFERENCES rollout_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织单位基础表';

-- 3. 系统人员表
CREATE TABLE sys_user (
    id INT PRIMARY KEY COMMENT '用户ID',
    name VARCHAR(255) NOT NULL COMMENT '姓名',
    org_id INT NOT NULL COMMENT '所属单位ID',
    role VARCHAR(50) NOT NULL COMMENT '项目角色',
    job VARCHAR(50) NOT NULL COMMENT '岗位职务',
    FOREIGN KEY (org_id) REFERENCES org_unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统人员与项目角色表';

-- 4. 培训记录表
CREATE TABLE training (
    id INT PRIMARY KEY COMMENT '培训场次ID',
    org_id INT NOT NULL COMMENT '参训单位ID',
    batch_id INT NOT NULL COMMENT '所属批次ID',
    type VARCHAR(100) NOT NULL COMMENT '培训类型',
    date DATE NOT NULL COMMENT '培训实施日期',
    mode VARCHAR(50) NOT NULL COMMENT '培训方式',
    expected INT NOT NULL COMMENT '应到人数',
    actual INT NOT NULL COMMENT '实到人数',
    absent INT NOT NULL COMMENT '缺席人数',
    passed INT NOT NULL COMMENT '通关考核人数',
    makeup INT NOT NULL COMMENT '补训人数',
    cert_count INT NOT NULL DEFAULT 0 COMMENT '关键用户认证人数',
    FOREIGN KEY (org_id) REFERENCES org_unit(id),
    FOREIGN KEY (batch_id) REFERENCES rollout_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='推广培训记录表';

-- 5. 建设任务表
CREATE TABLE construction_task (
    id INT PRIMARY KEY COMMENT '任务ID',
    org_id INT NOT NULL COMMENT '所属单位ID',
    name VARCHAR(255) NOT NULL COMMENT '任务名称',
    type VARCHAR(50) NOT NULL COMMENT '任务所属阶段类别',
    owner VARCHAR(255) NOT NULL COMMENT '责任人姓名(必须为所属单位人员)',
    plan_time DATE NOT NULL COMMENT '计划完成日期',
    actual_time DATE COMMENT '实际完成日期',
    status VARCHAR(50) NOT NULL COMMENT '任务状态(未开始/进行中/已完成)',
    progress INT NOT NULL DEFAULT 0 COMMENT '任务进度百分比',
    update_time DATE NOT NULL COMMENT '最后更新日期',
    FOREIGN KEY (org_id) REFERENCES org_unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='建设任务明细表';

-- 6. 业务单据主表
CREATE TABLE business_document (
    id INT PRIMARY KEY COMMENT '单据ID',
    org_id INT NOT NULL COMMENT '经办单位ID',
    type VARCHAR(50) NOT NULL COMMENT '单据类型',
    doc_no VARCHAR(50) NOT NULL UNIQUE COMMENT '单据业务编号',
    applicant VARCHAR(50) NOT NULL COMMENT '经办申请人(必须为所属单位人员)',
    nature VARCHAR(50) NOT NULL COMMENT '业务性质(正式业务/双轨测试)',
    amount DECIMAL(14,2) NOT NULL COMMENT '单据总金额',
    submit_time DATETIME NOT NULL COMMENT '提交时间',
    approve_time DATETIME COMMENT '审批完成时间',
    status VARCHAR(50) NOT NULL COMMENT '单据状态(处理完成/审批中/已驳回/待生成凭证/生成失败)',
    FOREIGN KEY (org_id) REFERENCES org_unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业务单据主表';

-- 7. 业务单据明细表
CREATE TABLE business_document_line (
    id INT PRIMARY KEY COMMENT '明细ID',
    doc_id INT NOT NULL COMMENT '所属单据ID',
    item_name VARCHAR(100) NOT NULL COMMENT '商品/款项明细名称',
    amount DECIMAL(14,2) NOT NULL COMMENT '明细金额',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    FOREIGN KEY (doc_id) REFERENCES business_document(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业务单据明细行表';

-- 8. 会计凭证主表
CREATE TABLE accounting_voucher (
    id INT PRIMARY KEY COMMENT '凭证ID',
    org_id INT NOT NULL COMMENT '核算单位ID',
    voucher_no VARCHAR(50) NOT NULL UNIQUE COMMENT '凭证编号',
    type VARCHAR(50) NOT NULL COMMENT '凭证类型',
    gen_time DATETIME NOT NULL COMMENT '凭证生成时间',
    int_time DATETIME COMMENT '集成传输时间',
    status VARCHAR(50) NOT NULL COMMENT '凭证状态(已集成/集成失败/生成成功/已冲销)',
    debit DECIMAL(14,2) NOT NULL COMMENT '借方发生额合计',
    credit DECIMAL(14,2) NOT NULL COMMENT '贷方发生额合计',
    FOREIGN KEY (org_id) REFERENCES org_unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会计凭证主表';

-- 9. 会计凭证分录行表
CREATE TABLE accounting_voucher_line (
    id INT PRIMARY KEY COMMENT '分录ID',
    voucher_id INT NOT NULL COMMENT '所属凭证ID',
    subject_code VARCHAR(50) NOT NULL COMMENT '会计科目编码',
    subject_name VARCHAR(100) NOT NULL COMMENT '会计科目名称',
    debit DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '借方金额',
    credit DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '贷方金额',
    FOREIGN KEY (voucher_id) REFERENCES accounting_voucher(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会计凭证分录表';

-- 10. 单据-凭证关联关系表 (支持 1-1, N-1, 1-N)
CREATE TABLE document_voucher_link (
    doc_id INT NOT NULL COMMENT '单据ID',
    voucher_id INT NOT NULL COMMENT '凭证ID',
    PRIMARY KEY (doc_id, voucher_id),
    FOREIGN KEY (doc_id) REFERENCES business_document(id),
    FOREIGN KEY (voucher_id) REFERENCES accounting_voucher(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单据凭证多对多关系表';

-- 11. 凭证接口集成结果表
CREATE TABLE integration_result (
    id INT PRIMARY KEY COMMENT '集成流水ID',
    voucher_id INT NOT NULL COMMENT '凭证ID',
    status VARCHAR(50) NOT NULL COMMENT '集成状态(SUCCESS/FAIL)',
    retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数',
    error_code VARCHAR(50) COMMENT '错误码',
    error_message VARCHAR(255) COMMENT '错误信息或成功提示',
    integration_time DATETIME NOT NULL COMMENT '集成响应时间',
    FOREIGN KEY (voucher_id) REFERENCES accounting_voucher(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='凭证接口集成结果明细表';

-- 12. 双轨运行核对结果表
CREATE TABLE dual_run_result (
    id INT PRIMARY KEY COMMENT '核对流水ID',
    org_id INT NOT NULL COMMENT '单位ID',
    check_type VARCHAR(50) NOT NULL COMMENT '比对核对类型',
    v1_amount DECIMAL(14,2) NOT NULL COMMENT '旧系统金额',
    v2_amount DECIMAL(14,2) NOT NULL COMMENT '新系统金额',
    diff_amount DECIMAL(14,2) NOT NULL COMMENT '差异金额',
    result VARCHAR(50) NOT NULL COMMENT '核对结论(一致/不一致)',
    check_date DATE NOT NULL COMMENT '比对核对日期',
    FOREIGN KEY (org_id) REFERENCES org_unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='双轨运行比对核对结果表';

-- 13. 数据准备度综合指标表
CREATE TABLE data_readiness (
    org_id INT PRIMARY KEY COMMENT '单位ID',
    batch_id INT NOT NULL COMMENT '批次ID',
    static_total INT NOT NULL COMMENT '静态数据应备项数',
    static_completed INT NOT NULL COMMENT '静态数据完成项数',
    static_rate VARCHAR(20) NOT NULL COMMENT '静态数据完成率',
    opening_total INT NOT NULL COMMENT '期初数据应备项数',
    opening_completed INT NOT NULL COMMENT '期初数据完成项数',
    opening_rate VARCHAR(20) NOT NULL COMMENT '期初数据完成率',
    opening_diff_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '期初差异金额',
    dynamic_total INT NOT NULL COMMENT '动态数据应备项数',
    dynamic_completed INT NOT NULL COMMENT '动态数据完成项数',
    dynamic_sync_success INT NOT NULL DEFAULT 0 COMMENT '动态同步成功项数',
    dynamic_sync_fail INT NOT NULL DEFAULT 0 COMMENT '动态同步失败项数',
    dynamic_sync_pending INT NOT NULL DEFAULT 0 COMMENT '动态同步待处理项数',
    dynamic_rate VARCHAR(20) NOT NULL COMMENT '动态数据完成率',
    last_sync_time VARCHAR(50) COMMENT '最近一次同步时间',
    overall_status VARCHAR(50) NOT NULL COMMENT '总体准备状态(已导入/校验通过/收集中/未收集)',
    FOREIGN KEY (org_id) REFERENCES org_unit(id),
    FOREIGN KEY (batch_id) REFERENCES rollout_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单位数据准备度指标表';

-- 14. 推广状态全量历史快照表
CREATE TABLE rollout_status_snapshot (
    org_id INT NOT NULL COMMENT '单位ID',
    snapshot_date DATE NOT NULL COMMENT '快照日期',
    status VARCHAR(50) NOT NULL COMMENT '当日推广状态',
    PRIMARY KEY (org_id, snapshot_date),
    FOREIGN KEY (org_id) REFERENCES org_unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单位推广状态历史快照表';

-- 15. 问题统计历史快照表
CREATE TABLE issue_metric_snapshot (
    org_id INT NOT NULL COMMENT '单位ID',
    batch_id INT NOT NULL COMMENT '批次ID',
    date DATE NOT NULL COMMENT '统计日期',
    stage VARCHAR(50) NOT NULL COMMENT '项目阶段(上线准备/上线后运行)',
    bug INT NOT NULL DEFAULT 0,
    req INT NOT NULL DEFAULT 0,
    conf INT NOT NULL DEFAULT 0,
    data INT NOT NULL DEFAULT 0,
    integ INT NOT NULL DEFAULT 0,
    op INT NOT NULL DEFAULT 0,
    total INT NOT NULL DEFAULT 0,
    resolved INT NOT NULL DEFAULT 0,
    unresolved INT NOT NULL DEFAULT 0,
    PRIMARY KEY (org_id, date),
    FOREIGN KEY (org_id) REFERENCES org_unit(id),
    FOREIGN KEY (batch_id) REFERENCES rollout_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问题数量及分类历史快照表';

-- 16. 风险统计历史快照表
CREATE TABLE risk_metric_snapshot (
    org_id INT NOT NULL COMMENT '单位ID',
    batch_id INT NOT NULL COMMENT '批次ID',
    date DATE NOT NULL COMMENT '统计日期',
    stage VARCHAR(50) NOT NULL COMMENT '项目阶段',
    high INT NOT NULL DEFAULT 0,
    medium INT NOT NULL DEFAULT 0,
    low INT NOT NULL DEFAULT 0,
    PRIMARY KEY (org_id, date),
    FOREIGN KEY (org_id) REFERENCES org_unit(id),
    FOREIGN KEY (batch_id) REFERENCES rollout_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风险等级历史快照表';

-- 17. 宏观全局指标历史快照表
CREATE TABLE metric_snapshot (
    snapshot_date DATE PRIMARY KEY COMMENT '快照日期',
    target_units INT NOT NULL COMMENT '有效推广总单位数',
    online_units INT NOT NULL COMMENT '已上线单位数',
    dual_run_units INT NOT NULL COMMENT '双轨运行单位数',
    online_rate VARCHAR(20) NOT NULL COMMENT '全网上线完成率',
    voucher_generate_success_rate VARCHAR(20) NOT NULL COMMENT '凭证生成成功率',
    integration_success_rate VARCHAR(20) NOT NULL COMMENT '接口集成成功率'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大屏全局核心KPI快照表';
