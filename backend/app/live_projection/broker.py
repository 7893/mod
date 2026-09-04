"""In-memory event scheduler for a shared, read-only dashboard projection."""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from datetime import UTC, date, datetime
from typing import Any

from .models import DISPLAY_TIMEZONE, ProjectionEvent, ProjectionIncrements


def _enabled_from_environment() -> bool:
    return os.getenv("MOD_LIVE_PROJECTION_ENABLED", "true").strip().lower() in {"1", "true", "yes"}

DEFAULT_UNITS_POOL = [
    {"name": "奉天林业研究院", "province": "辽宁"},
    {"name": "漓江文理书院", "province": "广西"},
    {"name": "天涯投资数字工坊", "province": "海南"},
    {"name": "武夷能源技术服务部", "province": "福建"},
    {"name": "洱海生物科技事业部", "province": "云南"},
    {"name": "河湟水务技术服务部", "province": "青海"},
    {"name": "许昌制造研究所", "province": "河南"},
    {"name": "甬上金融设计院", "province": "浙江"},
    {"name": "荆楚发展控股有限公司", "province": "湖北"},
    {"name": "黄山金融数字工坊", "province": "安徽"},
    {"name": "齐鲁重工装备制造", "province": "山东"},
    {"name": "三晋焦煤综合服务中心", "province": "山西"},
    {"name": "巴蜀数智科技实验室", "province": "四川"},
    {"name": "岭南先进制造工程院", "province": "广东"},
    {"name": "申城现代物流供应链", "province": "上海"},
    {"name": "金陵微电子技术创新中心", "province": "江苏"},
    {"name": "白山黑水装备技术部", "province": "吉林"},
    {"name": "天山新能源一体化站", "province": "新疆"},
    {"name": "长安智造精密仪器所", "province": "陕西"},
    {"name": "贵州大数据算力枢纽中心", "province": "贵州"},
    {"name": "赣江新材料科技研究院", "province": "江西"},
    {"name": "龙江极寒工程技术测试站", "province": "黑龙江"},
    {"name": "内蒙古草业乳业创新中心", "province": "内蒙古"},
    {"name": "津门港口智慧物流研究所", "province": "天津"},
    {"name": "燕赵轨道交通技术研究院", "province": "河北"},
    {"name": "塞上枸杞特色农业实验室", "province": "宁夏"},
    {"name": "拉萨雪域生态研究院", "province": "西藏"},
    {"name": "山城两江工业互联技术部", "province": "重庆"},
    {"name": "京华软件工程实验室", "province": "北京"},
    {"name": "三江源生态监测站", "province": "青海"},
]


def _load_units_pool() -> list[dict[str, Any]]:
    try:
        from ..db import get_v2_engine
        from sqlalchemy import text
        with get_v2_engine().connect() as conn:
            sql = """
            WITH batch_mapped AS (
                SELECT 
                    o.id,
                    o.name,
                    o.region,
                    o.status,
                    CASE
                        WHEN o.status = '稳定运行' AND o.id <= 150 THEN 1
                        WHEN o.status = '稳定运行' AND o.id <= 330 THEN 2
                        WHEN o.status = '稳定运行' THEN 3
                        WHEN o.status = '已上线' AND o.id <= 580 THEN 4
                        WHEN o.status = '已上线' THEN 5
                        WHEN o.status = '双轨运行中' THEN 6
                        WHEN o.id > 1600 THEN 7
                        ELSE 8
                    END AS batch_id
                FROM org_unit o
            )
            SELECT id, name, region, status, batch_id FROM batch_mapped
            """
            rows = conn.execute(text(sql)).fetchall()
            if rows:
                clean_rows = []
                for r in rows:
                    prov = r[2].replace("省", "").replace("市", "").replace("壮族自治区", "").replace("回族自治区", "").replace("维吾尔自治区", "").replace("特别行政区", "").replace("自治区", "")
                    clean_rows.append({
                        "id": r[0],
                        "name": r[1],
                        "region": r[2],
                        "province": prov,
                        "status": r[3],
                        "batch_id": r[4],
                        "batch_name": f"第{r[4]}批",
                    })
                return clean_rows
    except Exception:
        pass
    return DEFAULT_UNITS_POOL


class LiveProjectionBroker:
    """Generate one coherent event timeline shared by all connected dashboards."""

    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        mean_interval_seconds: float = 12.0,
        min_interval_seconds: float = 3.0,
        max_interval_seconds: float = 60.0,
        daily_document_cap: int = 20_000,
        units_pool: list[dict[str, Any]] | None = None,
    ) -> None:
        from .simulation_engine import RealisticSimulationEngine

        self.enabled = _enabled_from_environment()
        self._rng = rng or random.Random()
        self._mean_interval = mean_interval_seconds
        self._min_interval = min_interval_seconds
        self._max_interval = max_interval_seconds
        self._daily_document_cap = daily_document_cap
        self._projection_id = uuid.uuid4().hex[:12]
        self._sequence = 0
        self._cumulative = ProjectionIncrements()
        self._subscribers: set[asyncio.Queue[ProjectionEvent]] = set()
        self._task: asyncio.Task[None] | None = None
        self._budget_date: date | None = None
        self._documents_today = 0
        # Injectable pool keeps tests deterministic and DB-independent; default
        # falls back to the database-backed loader, preserving production behavior.
        self._units_pool = units_pool if units_pool is not None else _load_units_pool()
        self._simulation_engine = RealisticSimulationEngine(self._units_pool, self._rng)

    @property
    def cumulative(self) -> ProjectionIncrements:
        return self._cumulative

    def next_interval(self, now: datetime) -> float:
        interval, _ = self._simulation_engine.next_interval(now)
        return interval

    def create_event(self, now: datetime) -> ProjectionEvent | None:
        """Create one bounded event via the realistic simulation engine."""
        local_date = now.astimezone(DISPLAY_TIMEZONE).date()
        if self._budget_date != local_date:
            self._budget_date = local_date
            self._documents_today = 0

        if self._documents_today >= self._daily_document_cap:
            return None

        sim_res = self._simulation_engine.generate_next_event(now)
        if not sim_res:
            return None

        inc = ProjectionIncrements(
            documents=sim_res.doc_increment,
            vouchers=sim_res.voucher_increment,
            integrations=sim_res.integration_increment,
        )
        self._documents_today += inc.documents
        self._sequence += 1
        self._cumulative = ProjectionIncrements(
            documents=self._cumulative.documents + inc.documents,
            vouchers=self._cumulative.vouchers + inc.vouchers,
            integrations=self._cumulative.integrations + inc.integrations,
        )

        return ProjectionEvent(
            id=f"{self._projection_id}-{self._sequence}",
            sequence=self._sequence,
            occurred_at=now,
            business_type=sim_res.business_type,
            increments=inc,
            cumulative=self._cumulative,
            projection_id=self._projection_id,
            unit_name=sim_res.unit_name,
            province=sim_res.province,
            story_title=sim_res.story_title,
            story_desc=sim_res.story_desc,
            amount=sim_res.amount,
            badge_tone=sim_res.badge_tone,
            batch_name=sim_res.batch_name,
        )

    async def start(self) -> None:
        if self.enabled and self._task is None:
            self._task = asyncio.create_task(self._run(), name="live-projection")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def subscribe(self) -> asyncio.Queue[ProjectionEvent]:
        queue: asyncio.Queue[ProjectionEvent] = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ProjectionEvent]) -> None:
        self._subscribers.discard(queue)

    def state_payload(self) -> dict:
        return {
            "id": f"{self._projection_id}-state-{self._sequence}",
            "sequence": self._sequence,
            "occurred_at": datetime.now(UTC).isoformat(),
            "business_type": "projection_state",
            "increments": {"documents": 0, "vouchers": 0, "integrations": 0},
            "cumulative": {
                "documents": self._cumulative.documents,
                "vouchers": self._cumulative.vouchers,
                "integrations": self._cumulative.integrations,
            },
            "projection_id": self._projection_id,
            "unit_name": None,
            "province": None,
            "mode": "display_projection",
        }

    async def stream(self):
        queue = self.subscribe()
        try:
            yield self._sse(self.state_payload())
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield self._sse(event.as_payload())
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(queue)

    async def _run(self) -> None:
        while True:
            now = datetime.now(UTC)
            await asyncio.sleep(self.next_interval(now))
            event = self.create_event(datetime.now(UTC))
            if event is not None:
                self._publish(event)

    def _publish(self, event: ProjectionEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    @staticmethod
    def _sse(payload: dict) -> str:
        return f"id: {payload['id']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_broker = LiveProjectionBroker()


def get_live_projection_broker() -> LiveProjectionBroker:
    return _broker
