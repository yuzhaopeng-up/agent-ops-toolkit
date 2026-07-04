"""demo.py — 文档流水线端到端演示，6 模板各跑一次."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from src import DocumentPipeline  # noqa: E402

pipeline = DocumentPipeline()
print("可用模板:", pipeline.list_templates())
print()

# ─── 1. 事故通报 ───
r1 = pipeline.run(template="incident_report", data={
    "incident_id": "INC-20260620-001",
    "severity": "P1",
    "title": "网点 A 路由器掉线",
    "started_at": "2026-06-20 14:23",
    "impact": "50+ 终端断网 30 分钟",
    "root_cause": "电源模块故障",
    "actions": ["更换电源模块", "切换备用线路", "复盘演练"],
    "assignee": "张工",
    "affected_systems": ["核心网", "BOSS", "ITV"],
})
print("=" * 64)
print("📄 incident_report")
print("=" * 64)
print(r1.rendered[:500] + "...")
print(f"\n→ 归档: {r1.archive_path}\n")

# ─── 2. 运营日报 ───
r2 = pipeline.run(template="operations_daily", data={
    "report_date": "2026-06-20",
    "org": "南昌分公司",
    "tickets_today": 142, "tickets_yesterday": 120, "tickets_delta": "+18%",
    "faults_today": 3, "faults_yesterday": 5, "faults_delta": "-40%",
    "fcr": "82%", "fcr_yesterday": "78%", "fcr_delta": "+4pp",
    "top_faults": [
        {"type": "宽带断网", "count": 12, "note": "周末高峰"},
        {"type": "ITV 卡顿", "count": 7},
        {"type": "5G 掉线", "count": 3},
    ],
    "highlights": ["FCR 提升 4pp", "重大事件 0 起"],
    "risks": ["明日西湖区有大型活动"],
    "priorities": ["跟进活动保障", "推进 FCR 月度计划"],
})
print("=" * 64)
print("📄 operations_daily")
print("=" * 64)
print(r2.rendered[:500] + "...")
print(f"\n→ 归档: {r2.archive_path}\n")

# ─── 3. 风控评审 ───
r3 = pipeline.run(template="risk_review", data={
    "review_id": "RR-2026-Q2-007",
    "subject": "甲公司 5000万 流动资金贷款",
    "review_date": "2026-06-20",
    "reviewer": "李审批",
    "overall_conclusion": "原则同意",
    "dimensions": [
        {"name": "信用风险", "score": 4, "comment": "客户经营稳健"},
        {"name": "合规风险", "score": 5, "comment": "无负面记录"},
        {"name": "操作风险", "score": 3, "comment": "需补充资料"},
    ],
    "findings": [
        {"title": "客户集中度偏高", "severity": "中",
         "description": "前 3 大客户占比 60%",
         "recommendation": "建议分散客户结构"},
    ],
    "remediation": [
        {"action": "补充近 3 月银行流水",
         "owner": "客户经理王某", "due": "2026-06-30"},
    ],
})
print("=" * 64)
print("📄 risk_review (前 500 字)")
print("=" * 64)
print(r3.rendered[:500] + "...")
print()

# ─── 4. 会议纪要 ───
r4 = pipeline.run(template="meeting_minutes", data={
    "title": "Q3 启动会",
    "meeting_at": "2026-06-20 10:00",
    "host": "trainer",
    "recorder": "张三",
    "attendees": ["张三 (PM)", "李四 (Tech)", "王五 (UX)"],
    "topics": [
        {"title": "Q2 复盘",
         "points": ["收入超预期 15%", "客户数达成 100%"],
         "conclusion": "整体良好"},
        {"title": "Q3 重点项目",
         "points": ["新产品发布", "客户拓展计划"],
         "conclusion": "按计划推进"},
    ],
    "decisions": ["立项 Project X", "招聘 2 名工程师"],
    "actions": [
        {"task": "Project X 方案输出", "owner": "李四",
         "due": "2026-06-30", "status": "进行中"},
    ],
    "next_meeting": "2026-07-01 月度复盘",
})
print("=" * 64)
print("📄 meeting_minutes (前 500 字)")
print("=" * 64)
print(r4.rendered[:500] + "...")
print()

# ─── 5. 客户简报 ───
r5 = pipeline.run(template="customer_brief", data={
    "customer_name": "甲电子科技股份有限公司",
    "customer_id": "C-202601-0042",
    "customer_type": "对公大客户",
    "industry": "智能制造",
    "rm": "张经理",
    "risk_grade": "AA",
    "overview": "国家级专精特新「小巨人」，年营收 8 亿，员工 400+",
    "financials": [
        {"name": "营业收入", "current": "8.2 亿", "yoy": "+12%"},
        {"name": "净利润", "current": "9000 万", "yoy": "+8%"},
        {"name": "资产负债率", "current": "42%", "yoy": "-2pp"},
    ],
    "cooperation": [
        {"year": "2024", "product": "授信", "amount": "5000万", "status": "正常"},
        {"year": "2025", "product": "票据贴现", "amount": "1.2亿", "status": "正常"},
    ],
    "risk_signals": ["主要客户集中度 60%", "海外应收账款占比上升"],
    "opportunities": [
        {"title": "供应链金融", "note": "覆盖上下游 30+ 家"},
        {"title": "并购贷款", "note": "客户有横向并购意向"},
    ],
})
print("=" * 64)
print("📄 customer_brief (前 500 字)")
print("=" * 64)
print(r5.rendered[:500] + "...")
print()

# ─── 6. KPI 总结 ───
r6 = pipeline.run(template="kpi_summary", data={
    "period": "2026 Q2",
    "org": "华东大区",
    "owner": "张总",
    "kpis": [
        {"name": "新签合同", "target": "1 亿",
         "actual": "1.2 亿", "completion": "120%", "status": "✅"},
        {"name": "续约率", "target": "85%",
         "actual": "80%", "completion": "94%", "status": "⚠️"},
        {"name": "NPS", "target": "60",
         "actual": "65", "completion": "108%", "status": "✅"},
    ],
    "overall_completion": "108%",
    "highlights": [
        {"title": "客户 X 突破",
         "detail": "签下 3000 万级战略合同，行业标杆"},
    ],
    "shortfalls": [
        {"kpi": "续约率", "gap": "5pp", "reason": "竞品挖角",
         "action": "Q3 启动客户成功项目"},
    ],
    "lessons": ["快速响应是赢单关键", "跨团队协作显著提升签约速度"],
    "next_targets": [
        {"kpi": "新签合同", "target": "1.5 亿"},
        {"kpi": "续约率", "target": "88%"},
    ],
})
print("=" * 64)
print("📄 kpi_summary (前 500 字)")
print("=" * 64)
print(r6.rendered[:500] + "...")
print()

# ─── 总结 ───
print("=" * 64)
print("✅ 6 个模板渲染完成")
print("=" * 64)
for r in (r1, r2, r3, r4, r5, r6):
    stages = " → ".join(f"{s.stage}({s.duration_ms}ms)" for s in r.stages)
    print(f"  {r.template:20s} | {stages} | sha256={r.fingerprint[:12]}")
