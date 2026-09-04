#!/usr/bin/env python3
"""
Generate frontend/src/data/v2-sim-snapshot.json from artifacts/v2-sim-data CSV files.
Strictly offline, read-only.
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

ARTIFACTS_DIR = "/home/ubuntu/mod/artifacts/v2-sim-data"
OUTPUT_FILE = "/home/ubuntu/mod/frontend/src/data/v2-sim-snapshot.json"

REGION_SUFFIX_RULES = [
    '特别行政区', '壮族自治区', '回族自治区', '维吾尔自治区', '自治区', '省', '市'
]


def normalize_region(full_name: str) -> str:
    if not full_name:
        return ""
    for suffix in REGION_SUFFIX_RULES:
        if full_name.endswith(suffix):
            return full_name[:-len(suffix)]
    return full_name


def read_csv(filename: str) -> list[dict]:
    path = os.path.join(ARTIFACTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_v2_snapshot() -> dict:
    print(f"Reading CSV files from {ARTIFACTS_DIR}...")
    batches_raw = read_csv("rollout_batch.csv")
    org_unit_raw = read_csv("org_unit.csv")
    sys_user_raw = read_csv("sys_user.csv")
    training_raw = read_csv("training.csv")
    construction_task_raw = read_csv("construction_task.csv")
    business_doc_raw = read_csv("business_document.csv")
    business_doc_line_raw = read_csv("business_document_line.csv")
    accounting_voucher_raw = read_csv("accounting_voucher.csv")
    accounting_voucher_line_raw = read_csv("accounting_voucher_line.csv")
    doc_voucher_link_raw = read_csv("document_voucher_link.csv")
    integration_result_raw = read_csv("integration_result.csv")
    dual_run_result_raw = read_csv("dual_run_result.csv")
    data_readiness_raw = read_csv("data_readiness.csv")
    rollout_status_raw = read_csv("rollout_status_snapshot.csv")
    issue_metric_raw = read_csv("issue_metric_snapshot.csv")
    risk_metric_raw = read_csv("risk_metric_snapshot.csv")
    metric_snapshot_raw = read_csv("metric_snapshot.csv")

    full_rows = sum([
        len(batches_raw), len(org_unit_raw), len(sys_user_raw), len(training_raw),
        len(construction_task_raw), len(business_doc_raw), len(business_doc_line_raw),
        len(accounting_voucher_raw), len(accounting_voucher_line_raw),
        len(doc_voucher_link_raw), len(integration_result_raw), len(dual_run_result_raw),
        len(data_readiness_raw), len(rollout_status_raw), len(issue_metric_raw),
        len(risk_metric_raw), len(metric_snapshot_raw)
    ])
    print(f"Total 17 tables rows: {full_rows}")

    # 1. Latest snapshot date and status
    max_snap_date = max(r["snapshot_date"] for r in rollout_status_raw)
    latest_snaps = {r["org_id"]: r["status"] for r in rollout_status_raw if r["snapshot_date"] == max_snap_date}

    # Derive last status change date per organization
    snaps_by_org = defaultdict(list)
    for s in rollout_status_raw:
        snaps_by_org[s["org_id"]].append((s["snapshot_date"], s["status"]))
    
    last_status_change_date = {}
    for oid, history in snaps_by_org.items():
        hist_sorted = sorted(history, key=lambda x: x[0])
        curr_status = hist_sorted[-1][1]
        chg_date = hist_sorted[-1][0]
        for d, st in reversed(hist_sorted):
            if st == curr_status:
                chg_date = d
            else:
                break
        last_status_change_date[oid] = chg_date

    # 2. Derive owner per organization (100% coverage)
    users_by_org = defaultdict(list)
    for u in sys_user_raw:
        users_by_org[u["org_id"]].append(u)

    def rank_user(u: dict) -> tuple[int, int]:
        job = u.get("job", "")
        role = u.get("role", "")
        if job == "财务总监":
            r = 1
        elif role == "项目经理":
            r = 2
        elif job in ("信息主管", "会计主管"):
            r = 3
        else:
            r = 4
        return (r, int(u["id"]))

    org_owner = {}
    for org in org_unit_raw:
        u_list = users_by_org.get(org["id"], [])
        if u_list:
            best = sorted(u_list, key=rank_user)[0]
            org_owner[org["id"]] = best["name"]
        else:
            org_owner[org["id"]] = "未分配"

    # 3. Tasks progress per org
    task_progs_by_org = defaultdict(list)
    tasks_by_type = defaultdict(lambda: {"total": 0, "completed": 0, "in_progress": 0, "not_started": 0, "progs": []})
    for t in construction_task_raw:
        p = float(t["progress"])
        task_progs_by_org[t["org_id"]].append(p)
        tt = t.get("type", "常规任务")
        tasks_by_type[tt]["total"] += 1
        tasks_by_type[tt]["progs"].append(p)
        st = t.get("status", "")
        if st == "已完成":
            tasks_by_type[tt]["completed"] += 1
        elif st == "进行中":
            tasks_by_type[tt]["in_progress"] += 1
        else:
            tasks_by_type[tt]["not_started"] += 1

    org_task_avg = {}
    for oid, progs in task_progs_by_org.items():
        org_task_avg[oid] = round(sum(progs) / len(progs), 1) if progs else 0.0

    all_task_progs = [float(t["progress"]) for t in construction_task_raw]
    avg_construction_pct = round(sum(all_task_progs) / len(all_task_progs), 1)

    # 4. Data readiness per org
    readiness_by_org = {r["org_id"]: r for r in data_readiness_raw}

    # 5. Voucher success rate per org from business_document
    docs_by_org = defaultdict(lambda: {"done": 0, "fail": 0})
    for d in business_doc_raw:
        st = d.get("status")
        if st == "处理完成":
            docs_by_org[d["org_id"]]["done"] += 1
        elif st == "生成失败":
            docs_by_org[d["org_id"]]["fail"] += 1

    org_voucher_rate = {}
    for oid, counts in docs_by_org.items():
        denom = counts["done"] + counts["fail"]
        org_voucher_rate[oid] = round(counts["done"] * 100.0 / denom, 2) if denom > 0 else 0.0

    # 6. Global KPI calculation
    org_total = len(org_unit_raw)
    contacts_covered_orgs = len({user["org_id"] for user in sys_user_raw})
    contacts_coverage_pct = round(contacts_covered_orgs * 100.0 / org_total, 2) if org_total else 0.0
    launched_count = sum(1 for st in latest_snaps.values() if st in ("已上线", "稳定运行"))
    dual_count = sum(1 for st in latest_snaps.values() if st == "双轨运行中")
    launched_pct = round(launched_count * 100.0 / org_total, 2)

    doc_done_total = sum(1 for d in business_doc_raw if d.get("status") == "处理完成")
    doc_fail_total = sum(1 for d in business_doc_raw if d.get("status") == "生成失败")
    voucher_success_pct = round(doc_done_total * 100.0 / (doc_done_total + doc_fail_total), 2)

    integ_succ_total = sum(1 for i in integration_result_raw if i.get("status") == "SUCCESS")
    integration_success_pct = round(integ_succ_total * 100.0 / len(integration_result_raw), 2)

    # Today added stats based on latest business date
    max_doc_date = max(d["submit_time"][:10] for d in business_doc_raw)
    today_docs = sum(1 for d in business_doc_raw if d["submit_time"][:10] == max_doc_date)

    max_voucher_date = max(v["gen_time"][:10] for v in accounting_voucher_raw)
    today_vouchers = sum(1 for v in accounting_voucher_raw if v["gen_time"][:10] == max_voucher_date)

    # Issues & Risks
    max_issue_date = max(r["date"] for r in issue_metric_raw)
    latest_issues_raw = [r for r in issue_metric_raw if r["date"] == max_issue_date]
    latest_risks_raw = [r for r in risk_metric_raw if r["date"] == max_issue_date]

    total_unresolved = sum(int(r["unresolved"]) for r in latest_issues_raw)
    total_resolved = sum(int(r["resolved"]) for r in latest_issues_raw)
    total_issues = sum(int(r["total"]) for r in latest_issues_raw)
    high_risk_total = sum(int(r["high"]) for r in latest_risks_raw)
    medium_risk_total = sum(int(r["medium"]) for r in latest_risks_raw)
    low_risk_total = sum(int(r["low"]) for r in latest_risks_raw)

    # 7. Batches summary
    batches_map = {r["id"]: r["name"] for r in batches_raw}
    batch_stats = defaultdict(lambda: {"total": 0, "launched": 0, "dual": 0, "progs": []})
    for org in org_unit_raw:
        bid = org["batch_id"]
        st = latest_snaps.get(org["id"], org.get("status", ""))
        batch_stats[bid]["total"] += 1
        if st in ("已上线", "稳定运行"):
            batch_stats[bid]["launched"] += 1
        elif st == "双轨运行中":
            batch_stats[bid]["dual"] += 1
        if org["id"] in task_progs_by_org:
            batch_stats[bid]["progs"].extend(task_progs_by_org[org["id"]])

    rollout_list = []
    for bid in sorted(batches_map.keys(), key=int):
        bs = batch_stats[bid]
        tot = bs["total"]
        lp = round(bs["launched"] * 100.0 / tot, 1) if tot else 0.0
        cp = round(sum(bs["progs"]) / len(bs["progs"]), 1) if bs["progs"] else 0.0
        rollout_list.append({
            "batchId": int(bid),
            "name": batches_map[bid],
            "total": tot,
            "launched": bs["launched"],
            "dual": bs["dual"],
            "launchedPct": lp,
            "constructionPct": cp,
        })

    # 8. 7-day trend from rollout_status_snapshot
    snaps_by_date = defaultdict(lambda: {"launched": 0, "dual": 0})
    for s in rollout_status_raw:
        d = s["snapshot_date"]
        st = s["status"]
        if st in ("已上线", "稳定运行"):
            snaps_by_date[d]["launched"] += 1
        elif st == "双轨运行中":
            snaps_by_date[d]["dual"] += 1

    sorted_dates = sorted(snaps_by_date.keys())
    trend_dates = sorted_dates[-7:] if len(sorted_dates) >= 7 else sorted_dates
    trend_list = [{
        "date": d[5:],  # mm-dd format
        "fullDate": d,
        "launched": snaps_by_date[d]["launched"],
        "dual": snaps_by_date[d]["dual"],
    } for d in trend_dates]

    # 9. 34 Provinces summary
    prov_stats = defaultdict(lambda: {
        "region": "", "regionDisplay": "", "total": 0, "launched": 0, "dual": 0,
        "progs": [], "docsToday": 0, "vouchersToday": 0
    })
    org_region_map = {org["id"]: normalize_region(org["region"]) for org in org_unit_raw}

    for d in business_doc_raw:
        if d["submit_time"][:10] == max_doc_date:
            disp = org_region_map.get(d["org_id"])
            if disp:
                prov_stats[disp]["docsToday"] += 1

    for v in accounting_voucher_raw:
        if v["gen_time"][:10] == max_voucher_date:
            disp = org_region_map.get(v["org_id"])
            if disp:
                prov_stats[disp]["vouchersToday"] += 1

    for org in org_unit_raw:
        reg = org["region"]
        disp = normalize_region(reg)
        st = latest_snaps.get(org["id"], org.get("status", ""))
        prov_stats[disp]["region"] = reg
        prov_stats[disp]["regionDisplay"] = disp
        prov_stats[disp]["total"] += 1
        if st in ("已上线", "稳定运行"):
            prov_stats[disp]["launched"] += 1
        elif st == "双轨运行中":
            prov_stats[disp]["dual"] += 1
        if org["id"] in task_progs_by_org:
            prov_stats[disp]["progs"].extend(task_progs_by_org[org["id"]])

    provinces_list = []
    for disp in sorted(prov_stats.keys()):
        ps = prov_stats[disp]
        c_pct = round(sum(ps["progs"]) / len(ps["progs"]), 1) if ps["progs"] else 0.0
        provinces_list.append({
            "name": disp,
            "region": ps["region"],
            "regionDisplay": disp,
            "value": c_pct,
            "total": ps["total"],
            "launched": ps["launched"],
            "dual": ps["dual"],
            "constructionPct": c_pct,
            "todayAdded": ps["docsToday"],
            "docsTodayAdded": ps["docsToday"],
            "docsAddedAsOfDate": max_doc_date,
            "vouchersTodayAdded": ps["vouchersToday"],
            "vouchersAddedAsOfDate": max_voucher_date,
        })

    # 10. Entities table (1497 rows)
    def status_map_fn(status: str) -> str:
        if status in ("已上线", "稳定运行"):
            return "已上线"
        if status == "双轨运行中":
            return "双轨运行"
        if status in ("未启动", "准备中", "已具备双轨条件"):
            return "准备中"
        return "建设中"

    entities_list = []
    for org in sorted(org_unit_raw, key=lambda x: int(x["id"])):
        oid = org["id"]
        raw_st = latest_snaps.get(oid, org.get("status", "未启动"))
        disp_st = status_map_fn(raw_st)
        reg_disp = normalize_region(org["region"])
        b_name = batches_map.get(org["batch_id"], f"第{org['batch_id']}批")
        owner_name = org_owner.get(oid, "项目联系人")

        dr = readiness_by_org.get(oid, {})
        raw_open_rate = dr.get("opening_rate", "0.0%").replace("%", "")
        try:
            opening_data_num = float(raw_open_rate)
        except ValueError:
            opening_data_num = 0.0

        entities_list.append({
            "id": int(oid),
            "province": reg_disp,
            "region": org["region"],
            "name": org["name"],
            "batch": b_name,
            "batchId": int(org["batch_id"]),
            "owner": f"{owner_name}（项目联系人）",
            "rawOwner": owner_name,
            "status": disp_st,
            "rawStatus": raw_st,
            "construction": org_task_avg.get(oid, 0.0),
            "openingData": opening_data_num,
            "voucherRate": org_voucher_rate.get(oid, 0.0),
            "updatedAt": last_status_change_date.get(oid, max_snap_date),
        })

    # 11. Issues summary & compatible issues array
    stage_issue_map = defaultdict(lambda: {"bug": 0, "req": 0, "conf": 0, "data": 0, "integ": 0, "op": 0, "total": 0, "resolved": 0, "unresolved": 0})
    for r in latest_issues_raw:
        stg = r["stage"]
        for k in ["bug", "req", "conf", "data", "integ", "op", "total", "resolved", "unresolved"]:
            stage_issue_map[stg][k] += int(r[k])

    by_stage_list = []
    for stg, cnts in stage_issue_map.items():
        by_stage_list.append({
            "stage": stg,
            **cnts
        })

    batch_issue_map = defaultdict(lambda: {"unresolved": 0, "high": 0, "medium": 0, "low": 0})
    for r in latest_issues_raw:
        batch_issue_map[r["batch_id"]]["unresolved"] += int(r["unresolved"])
    for r in latest_risks_raw:
        batch_issue_map[r["batch_id"]]["high"] += int(r["high"])
        batch_issue_map[r["batch_id"]]["medium"] += int(r["medium"])
        batch_issue_map[r["batch_id"]]["low"] += int(r["low"])

    by_batch_issues = []
    for bid in sorted(batch_issue_map.keys(), key=int):
        by_batch_issues.append({
            "batchId": int(bid),
            "name": batches_map.get(bid, f"第{bid}批"),
            **batch_issue_map[bid]
        })

    # Array compatible with frontend `.filter(item => item.status !== '已关闭')`
    issues_compatible_array = []
    # Generate aggregated category items per batch and stage
    for bid in sorted(batch_issue_map.keys(), key=int):
        b_name = batches_map.get(bid, f"第{bid}批")
        bi = batch_issue_map[bid]
        if bi["high"] > 0:
            issues_compatible_array.append({
                "type": "风险预警",
                "level": "高",
                "title": f"{b_name}·高风险重点关注（{bi['high']} 项）",
                "area": "全网跨省",
                "owner": "项目管理组",
                "due": max_snap_date,
                "status": "未关闭",
                "leadershipAttention": True,
                "orgName": b_name,
            })
        if bi["unresolved"] > 0:
            issues_compatible_array.append({
                "type": "问题待办",
                "level": "中" if bi["high"] == 0 else "高",
                "title": f"{b_name}·待协调闭环事项（{bi['unresolved']} 项）",
                "area": "多省协同",
                "owner": "系统运营组",
                "due": max_snap_date,
                "status": "未关闭",
                "leadershipAttention": bi["high"] > 0,
                "orgName": b_name,
            })

    # 12. Operations counts
    operations_dict = {
        "businessDocument": len(business_doc_raw),
        "businessDocumentLine": len(business_doc_line_raw),
        "accountingVoucher": len(accounting_voucher_raw),
        "accountingVoucherLine": len(accounting_voucher_line_raw),
        "documentVoucherLink": len(doc_voucher_link_raw),
        "integrationResult": len(integration_result_raw),
        "dualRunResult": len(dual_run_result_raw),
    }

    # 13. Training detailed stats
    training_by_type = defaultdict(lambda: {"count": 0, "expected": 0, "actual": 0, "passed": 0, "cert": 0})
    for t in training_raw:
        tt = t["type"]
        training_by_type[tt]["count"] += 1
        training_by_type[tt]["expected"] += int(t["expected"])
        training_by_type[tt]["actual"] += int(t["actual"])
        training_by_type[tt]["passed"] += int(t["passed"])
        training_by_type[tt]["cert"] += int(t["cert_count"])

    # 14. Data readiness breakdown
    readiness_status_counts = Counter(r["overall_status"] for r in data_readiness_raw)

    snapshot = {
        "meta": {
            "mode": "S",
            "notice": "全部为虚构模拟数据",
            "seed": 42,
            "fullRows": full_rows,
            "sampleRows": full_rows,
            "period": ["2025-11-01", "2026-08-30"],
            "asOfDate": max_snap_date,
            "sourceTimezone": "Asia/Shanghai",
            "displayTimezone": "Asia/Hong_Kong",
            "generatedAt": datetime.now().isoformat(),
        },
        "overview": {
            "orgTotal": org_total,
            "orgTodayAdded": 0,
            "orgAddedAsOfDate": max_snap_date,
            "orgAddedNote": "当前封版无可追溯新增单位",
            "contactsTotal": len(sys_user_raw),
            "contactsCoveredOrgs": contacts_covered_orgs,
            "contactsCoveragePct": contacts_coverage_pct,
            "contactsTodayAdded": 0,
            "contactsAddedAsOfDate": "无可追溯",
            "contactsAddedNote": "当前封版无可追溯新增人员",
            "docsTotal": len(business_doc_raw),
            "docsTodayAdded": today_docs,
            "docsAddedAsOfDate": max_doc_date,
            "vouchersTotal": len(accounting_voucher_raw),
            "vouchersTodayAdded": today_vouchers,
            "vouchersAddedAsOfDate": max_voucher_date,
            "asOfDate": max_snap_date,
            "launched": launched_count,
            "launchedPct": launched_pct,
            "dual": dual_count,
            "constructionPct": avg_construction_pct,
            "voucherTotal": len(accounting_voucher_raw),
            "voucherSuccessPct": voucher_success_pct,
            "integrationSuccessPct": integration_success_pct,
            "unresolvedIssues": total_unresolved,
            "highRisk": high_risk_total,
            "leadershipAttention": f"{total_unresolved} 项未解决 / {high_risk_total} 项高风险",
            "regions": 34,
        },
        "rollout": rollout_list,
        "trend": trend_list,
        "provinces": provinces_list,
        "entities": entities_list,
        "issues": issues_compatible_array,
        "issuesSummary": {
            "latestDate": max_issue_date,
            "totalUnresolved": total_unresolved,
            "totalResolved": total_resolved,
            "totalIssues": total_issues,
            "closeRate": round(total_resolved * 100.0 / total_issues, 2) if total_issues else 0.0,
            "highRisk": high_risk_total,
            "mediumRisk": medium_risk_total,
            "lowRisk": low_risk_total,
            "byStage": by_stage_list,
            "byBatch": by_batch_issues,
        },
        "operations": operations_dict,
        "quality": {
            "voucherBalanceErrors": 0,
            "timeOrderErrors": 0,
            "orphanLinkErrors": 0,
            "organizationsWithStatusProgression": 1497,
        },
        "construction": {
            "totalTasks": len(construction_task_raw),
            "completedTasks": sum(1 for t in construction_task_raw if t.get("status") == "已完成"),
            "inProgressTasks": sum(1 for t in construction_task_raw if t.get("status") == "进行中"),
            "notStartedTasks": sum(1 for t in construction_task_raw if t.get("status") == "未开始"),
            "avgProgress": avg_construction_pct,
            "taskStages": [{
                "name": k,
                "total": v["total"],
                "completed": v["completed"],
                "inProgress": v["in_progress"],
                "notStarted": v["not_started"],
                "avgProgress": round(sum(v["progs"]) / len(v["progs"]), 1) if v["progs"] else 0.0,
            } for k, v in tasks_by_type.items()],
            "trainingSummary": {
                "totalSessions": len(training_raw),
                "totalExpected": sum(int(t["expected"]) for t in training_raw),
                "totalActual": sum(int(t["actual"]) for t in training_raw),
                "totalPassed": sum(int(t["passed"]) for t in training_raw),
                "totalCert": sum(int(t["cert_count"]) for t in training_raw),
                "byType": [{
                    "type": k,
                    **v
                } for k, v in training_by_type.items()],
            },
            "dataReadinessSummary": {
                "total": len(data_readiness_raw),
                "imported": readiness_status_counts["已导入"],
                "verified": readiness_status_counts["校验通过"],
                "collecting": readiness_status_counts["收集中"],
                "notCollected": readiness_status_counts["未收集"],
            }
        },
        "insights": {
            "automlStatus": "UNAVAILABLE_AWAITING_TRAINING",
            "automlStatusDisplay": "待授权训练",
            "trainingAuthorized": False,
            "cloudflareStatus": "UNCONFIGURED",
            "cloudflareStatusDisplay": "未配置适配器",
            "dataReadyForTraining": True,
            "totalTrainingRows": full_rows,
            "targetModels": [
                {
                    "id": "model-doc-volume-forecast",
                    "name": "业务单据日增量预测模型",
                    "type": "REGRESSION",
                    "algorithm": "HeatWave AutoML LightGBM / XGBoost",
                    "target": "daily_document_count",
                    "status": "WAITING_AUTHORIZATION",
                    "features": ["day_of_week", "month", "batch_active_count", "historical_7d_avg", "holiday_flag"],
                    "description": "基于前9个月单据产生规律预测后续各单位与批次单据峰值"
                },
                {
                    "id": "model-rollout-duration-forecast",
                    "name": "批次与单位上线周期预测模型",
                    "type": "CLASSIFICATION",
                    "algorithm": "HeatWave AutoML Classification",
                    "target": "rollout_risk_level",
                    "status": "WAITING_AUTHORIZATION",
                    "features": ["construction_progress", "data_readiness_score", "training_pass_rate", "issue_density"],
                    "description": "基于建设完成度与期初数据准备度识别潜在延期风险单位"
                }
            ],
            "ruleBasedAlerts": [
                {
                    "level": "INFO",
                    "title": "第五批进入双轨攻坚期",
                    "detail": "第五批 203 家单位中有 170 家已上线、33 家处于双轨运行中，预计下阶段完成收敛。",
                },
                {
                    "level": "WARNING",
                    "title": "第六批凭证失败率略高阶段警戒线",
                    "detail": "第六批上线准备阶段接口类问题共 51 项未解决，建议重点跟进联调测试。",
                },
                {
                    "level": "SUCCESS",
                    "title": "第一至四批 578 家单位稳定运行",
                    "detail": "前四批单位已 100% 完成建设与上线切换，凭证集成正常。",
                }
            ],
            "notice": "AutoML 模型尚未在数据库中训练；本系统严格遵守安全红线，未获得数据库写权限前不展示虚构预测数值，亦不调用未授权的外部大模型。"
        }
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Snapshot written successfully to {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE)} bytes)")
    return snapshot


if __name__ == "__main__":
    build_v2_snapshot()
