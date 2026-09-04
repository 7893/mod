"""
业务事件模拟器 - 五层模型

架构：
1. 目标区间控制 - 长期趋势，允许波动
2. 时间规律系统 - 工作日/时段/月末/节假日
3. 业务事件链 - 单据→审批→凭证→集成
4. 概率分布 - 非固定比例，自然波动
5. 情景系统 - 偶发事件制造真实感

AI 定位：
- 不参与增长计算
- 只做解释和摘要生成
- 完全关闭 AI 后系统仍正常运行

运行方式：每分钟计算活跃度 → 产生事件 → 推进状态 → 批量写库
"""

import random
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio

from .simulation.models import (
    ActiveScenario as ActiveScenario,
    BusinessEvent,
    BusinessEventChain,
    EventStatus,
    GrowthTarget,
    ProbabilityDistributions,
    ScenarioSystem,
    ScenarioType as ScenarioType,
    TimePatternSystem,
)

logger = logging.getLogger(__name__)

# ===== 主模拟器 =====

class BusinessSimulator:
    """业务模拟器 - 整合五层模型"""
    
    # 基础参数：每分钟每单位平均产生的单据数
    # 1002 个单位，每分钟约产生 1002 * 0.01 = 10 个事件
    BASE_DOCS_PER_ORG_PER_MINUTE = 0.01
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.growth_target = GrowthTarget()
        self.scenario_system = ScenarioSystem()
        
        # 内存中的待处理事件
        self.pending_events: Dict[str, BusinessEvent] = {}
        
        # 统计
        self.stats = {
            "documents_created": 0,
            "vouchers_created": 0,
            "integrations_created": 0,
            "integrations_failed": 0,
            "last_tick": None,
        }
        
        self._engine = None
        self._org_cache: List[Tuple[int, str]] = []  # (org_id, province)
        self._org_cache_time: Optional[datetime] = None
    
    def _get_engine(self):
        """获取数据库引擎"""
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(self.db_url)
        return self._engine
    
    def _refresh_org_cache(self, now: datetime):
        """刷新单位缓存（每小时一次）"""
        if (self._org_cache_time is None or 
            (now - self._org_cache_time).seconds > 3600):
            from sqlalchemy import text
            engine = self._get_engine()
            with engine.connect() as conn:
                # 选择已上线或运行中的单位
                rows = conn.execute(text(
                    "SELECT id, region FROM org_unit WHERE status IN ('稳定运行', '双轨运行中', '已上线', '已具备双轨条件') LIMIT 5000"
                )).fetchall()
                self._org_cache = [(r[0], r[1]) for r in rows]
                self._org_cache_time = now
                logger.info(f"Refreshed org cache: {len(self._org_cache)} orgs")
    
    def _get_current_counts(self) -> Tuple[int, int, int]:
        """获取当前数据量"""
        from sqlalchemy import text
        engine = self._get_engine()
        with engine.connect() as conn:
            doc_count = conn.execute(text(
                "SELECT COUNT(*) FROM business_document"
            )).scalar() or 0
            voucher_count = conn.execute(text(
                "SELECT COUNT(*) FROM accounting_voucher"
            )).scalar() or 0
            integration_count = conn.execute(text(
                "SELECT COUNT(*) FROM integration_result"
            )).scalar() or 0
        return doc_count, voucher_count, integration_count
    
    async def tick(self, now: datetime = None) -> Dict:
        """
        执行一个时间片（每分钟调用一次）
        
        返回本次 tick 的统计信息
        """
        now = now or datetime.utcnow()
        tick_stats = {
            "time": now.isoformat(),
            "new_documents": 0,
            "new_vouchers": 0,
            "new_integrations": 0,
            "events_advanced": 0,
        }
        
        # 刷新缓存
        self._refresh_org_cache(now)
        if not self._org_cache:
            logger.warning("No organizations in cache, skipping tick")
            return tick_stats
        
        # 1. 更新情景
        self.scenario_system.update(now)
        
        # 2. 计算当前活跃度
        base_activity = TimePatternSystem.get_activity_level(now)
        scenario_mult = self.scenario_system.get_activity_multiplier()
        activity = base_activity * scenario_mult
        
        # 3. 获取当前数据量，计算进度因子
        doc_count, voucher_count, integration_count = self._get_current_counts()
        progress_factor = self.growth_target.get_progress_factor("document", doc_count, now)
        
        # 4. 生成新业务事件
        base_rate = self.BASE_DOCS_PER_ORG_PER_MINUTE * len(self._org_cache)
        adjusted_rate = base_rate * activity * progress_factor
        new_doc_count = ProbabilityDistributions.document_arrival_count(adjusted_rate, 1.0)
        
        new_events = self._generate_new_events(new_doc_count, now)
        tick_stats["new_documents"] = len(new_events)
        
        # 5. 推进已有事件状态
        advanced = self._advance_events(now)
        tick_stats["events_advanced"] = advanced
        
        # 6. 批量写入数据库
        write_result = await self._batch_write(now)
        tick_stats["new_vouchers"] = write_result.get("vouchers", 0)
        tick_stats["new_integrations"] = write_result.get("integrations", 0)
        
        self.stats["last_tick"] = now.isoformat()
        
        return tick_stats
    
    def _generate_new_events(self, count: int, now: datetime) -> List[BusinessEvent]:
        """生成新的业务事件（单据提交）"""
        events = []
        event_types = ["expense", "payment", "receipt", "transfer"]
        type_weights = [0.45, 0.25, 0.15, 0.15]
        
        for _ in range(count):
            # 选择单位（考虑单位活跃度权重）
            org_id, province = random.choice(self._org_cache)
            org_weight = ProbabilityDistributions.org_activity_weight(org_id)
            
            # 根据权重决定是否真的产生事件
            if random.random() > org_weight:
                continue
            
            # 选择事件类型
            event_type = random.choices(event_types, weights=type_weights, k=1)[0]
            
            # 生成金额
            amount = ProbabilityDistributions.amount_distribution(event_type)
            
            # 创建事件
            event_id = f"evt_{now.strftime('%Y%m%d%H%M%S')}_{random.randint(10000, 99999)}"
            event = BusinessEvent(
                event_id=event_id,
                org_id=org_id,
                event_type=event_type,
                amount=amount,
                status=EventStatus.DOC_SUBMITTED,
                created_at=now,
                updated_at=now,
                applicant=f"User{random.randint(1000, 9999)}",
                province=province,
            )
            
            # 计算审批时间
            approval_minutes = BusinessEventChain.generate_approval_time(event_type)
            event.approval_time = now + timedelta(minutes=approval_minutes)
            
            self.pending_events[event_id] = event
            events.append(event)
        
        return events
    
    def _advance_events(self, now: datetime) -> int:
        """推进事件状态"""
        advanced_count = 0
        events_to_remove = []
        
        for event_id, event in self.pending_events.items():
            old_status = event.status
            
            # 状态机转换
            if event.status == EventStatus.DOC_SUBMITTED:
                # 等待审批
                if event.approval_time and now >= event.approval_time:
                    if BusinessEventChain.should_approve(event.event_type):
                        event.status = EventStatus.DOC_APPROVED
                    else:
                        event.status = EventStatus.DOC_REJECTED
                        event.rejection_reason = random.choice([
                            "金额超限", "附件不全", "预算不足", "审批流程不符"
                        ])
                    event.updated_at = now
            
            elif event.status == EventStatus.DOC_APPROVED:
                # 生成凭证（几乎立即）
                event.status = EventStatus.VOUCHER_GENERATED
                event.updated_at = now
            
            elif event.status == EventStatus.VOUCHER_GENERATED:
                # 准备集成
                event.status = EventStatus.INTEGRATION_PENDING
                event.updated_at = now
            
            elif event.status == EventStatus.INTEGRATION_PENDING:
                # 执行集成
                failure_rate = self.scenario_system.get_integration_failure_rate()
                if BusinessEventChain.should_integration_fail(failure_rate):
                    event.status = EventStatus.INTEGRATION_FAILED
                    event.retry_count += 1
                    event.next_retry_at = BusinessEventChain.get_next_retry_time(
                        event.retry_count, now
                    )
                else:
                    event.status = EventStatus.INTEGRATION_SUCCESS
                event.updated_at = now
            
            elif event.status == EventStatus.INTEGRATION_FAILED:
                # 检查重试
                if event.retry_count >= 5:
                    event.status = EventStatus.CANCELLED
                    event.updated_at = now
                elif event.next_retry_at and now >= event.next_retry_at:
                    event.status = EventStatus.INTEGRATION_RETRY
                    event.updated_at = now
            
            elif event.status == EventStatus.INTEGRATION_RETRY:
                # 重试
                failure_rate = self.scenario_system.get_integration_failure_rate()
                if BusinessEventChain.should_integration_fail(failure_rate * 0.5):  # 重试成功率更高
                    event.status = EventStatus.INTEGRATION_FAILED
                    event.retry_count += 1
                    event.next_retry_at = BusinessEventChain.get_next_retry_time(
                        event.retry_count, now
                    )
                else:
                    event.status = EventStatus.INTEGRATION_SUCCESS
                event.updated_at = now
            
            elif event.status in [EventStatus.INTEGRATION_SUCCESS, 
                                  EventStatus.DOC_REJECTED,
                                  EventStatus.CANCELLED]:
                # 终态，标记删除
                events_to_remove.append(event_id)
            
            if event.status != old_status:
                advanced_count += 1
        
        # 清理已完成的事件（保留一段时间用于写库）
        # 实际写库在 _batch_write 中处理
        
        return advanced_count
    
    async def _batch_write(self, now: datetime) -> Dict:
        """批量写入数据库"""
        from sqlalchemy import text
        
        result = {"documents": 0, "vouchers": 0, "integrations": 0}
        
        docs_to_write = []
        vouchers_to_write = []
        integrations_to_write = []
        events_to_remove = []
        
        for event_id, event in self.pending_events.items():
            # 写入单据（已审批）
            if event.status in [EventStatus.DOC_APPROVED, EventStatus.VOUCHER_GENERATED,
                               EventStatus.INTEGRATION_PENDING, EventStatus.INTEGRATION_SUCCESS,
                               EventStatus.INTEGRATION_FAILED] and event.doc_id is None:
                docs_to_write.append(event)
            
            # 写入凭证
            if event.status in [EventStatus.VOUCHER_GENERATED, EventStatus.INTEGRATION_PENDING,
                               EventStatus.INTEGRATION_SUCCESS, EventStatus.INTEGRATION_FAILED] \
               and event.voucher_id is None and event.doc_id is not None:
                vouchers_to_write.append(event)
            
            # 写入集成记录
            if event.status in [EventStatus.INTEGRATION_SUCCESS, EventStatus.INTEGRATION_FAILED] \
               and event.integration_id is None and event.voucher_id is not None:
                integrations_to_write.append(event)
            
            # 标记完成的事件
            if event.status in [EventStatus.INTEGRATION_SUCCESS, EventStatus.CANCELLED,
                               EventStatus.DOC_REJECTED]:
                if event.integration_id is not None or event.status != EventStatus.INTEGRATION_SUCCESS:
                    events_to_remove.append(event_id)
        
        # 批量写入
        engine = self._get_engine()
        try:
            with engine.connect() as conn:
                # 获取当前最大 ID
                max_doc_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM business_document")).scalar() or 0
                max_voucher_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM accounting_voucher")).scalar() or 0
                max_integ_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM integration_result")).scalar() or 0
                
                # 写入单据
                for i, event in enumerate(docs_to_write):
                    doc_id = uuid.uuid4().hex[:12].upper()
                    new_id = max_doc_id + i + 1
                    conn.execute(text("""
                        INSERT INTO business_document 
                        (id, org_id, type, doc_no, applicant, nature, amount, submit_time, approve_time, status)
                        VALUES (:id, :org_id, :type, :doc_no, :applicant, :nature, :amount, :submit_time, :approve_time, :status)
                    """), {
                        "id": new_id,
                        "org_id": event.org_id,
                        "type": event.event_type,
                        "doc_no": f"DOC-{doc_id}",
                        "applicant": event.applicant,
                        "nature": random.choice(["正式业务", "双轨测试"]),
                        "amount": event.amount,
                        "submit_time": event.created_at + timedelta(hours=8),
                        "approve_time": event.approval_time + timedelta(hours=8) if event.approval_time else None,
                        "status": "处理完成" if event.status != EventStatus.DOC_REJECTED else "已驳回",
                    })
                    event.doc_id = new_id
                    result["documents"] += 1
                
                # 更新最大 ID
                max_doc_id += len(docs_to_write)
                
                # 写入凭证
                for i, event in enumerate(vouchers_to_write):
                    v_id = uuid.uuid4().hex[:12].upper()
                    new_id = max_voucher_id + i + 1
                    conn.execute(text("""
                        INSERT INTO accounting_voucher 
                        (id, org_id, voucher_no, type, gen_time, status, debit, credit)
                        VALUES (:id, :org_id, :voucher_no, :type, :gen_time, :status, :debit, :credit)
                    """), {
                        "id": new_id,
                        "org_id": event.org_id,
                        "voucher_no": f"VCH-{v_id}",
                        "type": random.choice(["收款凭证", "付款凭证", "转账凭证"]),
                        "gen_time": event.updated_at + timedelta(hours=8),
                        "status": "已生成",
                        "debit": event.amount,
                        "credit": event.amount,
                    })
                    event.voucher_id = new_id
                    result["vouchers"] += 1
                
                # 更新最大 ID
                max_voucher_id += len(vouchers_to_write)
                
                # 写入集成记录
                for i, event in enumerate(integrations_to_write):
                    status = "成功" if event.status == EventStatus.INTEGRATION_SUCCESS else "失败"
                    new_id = max_integ_id + i + 1
                    params = {
                        "id": new_id,
                        "voucher_id": event.voucher_id,
                        "status": status,
                        "retry_count": event.retry_count,
                        "integration_time": event.updated_at + timedelta(hours=8),
                    }
                    if status == "失败":
                        params["error_code"] = f"ERR_{random.randint(1000, 9999)}"
                        params["error_message"] = random.choice([
                            "连接超时", "服务不可用", "响应格式错误"
                        ])
                        conn.execute(text("""
                            INSERT INTO integration_result 
                            (id, voucher_id, status, retry_count, error_code, error_message, integration_time)
                            VALUES (:id, :voucher_id, :status, :retry_count, :error_code, :error_message, :integration_time)
                        """), params)
                    else:
                        conn.execute(text("""
                            INSERT INTO integration_result 
                            (id, voucher_id, status, retry_count, integration_time)
                            VALUES (:id, :voucher_id, :status, :retry_count, :integration_time)
                        """), params)
                    event.integration_id = new_id
                    result["integrations"] += 1
                
                conn.commit()
        
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
        
        # 清理已完成的事件
        for event_id in events_to_remove:
            self.pending_events.pop(event_id, None)
        
        # 更新统计
        self.stats["documents_created"] += result["documents"]
        self.stats["vouchers_created"] += result["vouchers"]
        self.stats["integrations_created"] += result["integrations"]
        
        return result
    
    def get_status(self) -> Dict:
        """获取模拟器状态"""
        return {
            "pending_events": len(self.pending_events),
            "active_scenarios": [
                {
                    "type": s.scenario_type.value,
                    "ends_at": s.ends_at.isoformat(),
                    "intensity": s.intensity,
                }
                for s in self.scenario_system.active_scenarios
            ],
            "stats": self.stats,
            "org_cache_size": len(self._org_cache),
        }


# ===== 全局单例和调度 =====

_simulator_instance: Optional[BusinessSimulator] = None


def get_simulator_instance() -> Optional[BusinessSimulator]:
    """
    仅返回已存在的模拟器单例，不创建新实例，不接受 db_url。

    用途：只读状态查询。
    返回 None 表示模拟器从未启动（MOD_SIMULATOR_ENABLED 未启用时的正常状态）。
    """
    return _simulator_instance


def _create_simulator(db_url: str) -> BusinessSimulator:
    """
    创建（或复用）模拟器单例。

    仅供 run_simulator_loop() 调用，外部不得直接调用。
    db_url 必须来自 SimulatorConfig，不得含硬编码凭据。
    """
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = BusinessSimulator(db_url)
    return _simulator_instance


async def run_simulator_loop(db_url: str) -> None:
    """
    运行模拟器主循环（每分钟执行一次）。

    仅由 main.py lifespan 在 MOD_SIMULATOR_ENABLED=true 时调用。
    db_url 由 SimulatorConfig 提供，本函数不包含任何硬编码凭据。
    """
    simulator = _create_simulator(db_url)
    logger.info("业务模拟器已启动（后台循环运行中）")

    while True:
        try:
            now = datetime.utcnow()
            tick_result = await simulator.tick(now)

            if tick_result["new_documents"] > 0 or tick_result["events_advanced"] > 0:
                logger.info(
                    f"Tick: docs={tick_result['new_documents']}, "
                    f"vouchers={tick_result['new_vouchers']}, "
                    f"integrations={tick_result['new_integrations']}, "
                    f"advanced={tick_result['events_advanced']}"
                )
        except Exception as e:
            logger.error(f"Simulator tick failed: {e}")

        # 等待到下一分钟
        await asyncio.sleep(60)
