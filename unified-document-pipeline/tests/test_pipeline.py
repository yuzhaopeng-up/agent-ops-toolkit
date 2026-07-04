"""单元测试 — 流水线 + 6 模板."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from src import DocumentPipeline, TemplateRenderer  # noqa: E402


# ────────── 模板渲染器 ──────────

class TestTemplateRenderer(unittest.TestCase):
    def setUp(self):
        self.r = TemplateRenderer()

    def test_simple_var(self):
        self.assertEqual(self.r.render("Hello {{ name }}!",
                                        {"name": "Yu"}), "Hello Yu!")

    def test_default_filter(self):
        self.assertEqual(
            self.r.render("X={{ x | default('-') }}", {}),
            "X=-",
        )

    def test_upper_filter(self):
        self.assertEqual(
            self.r.render("{{ s | upper }}", {"s": "hi"}), "HI"
        )

    def test_chained_filters(self):
        self.assertEqual(
            self.r.render("{{ x | default('Y') | upper }}", {"x": ""}),
            "Y",
        )

    def test_dotted_path(self):
        self.assertEqual(
            self.r.render("{{ user.name }}",
                          {"user": {"name": "Yu"}}), "Yu"
        )

    def test_if_truthy(self):
        out = self.r.render(
            "{% if active %}YES{% else %}NO{% endif %}",
            {"active": True},
        )
        self.assertEqual(out, "YES")

    def test_if_falsy_with_else(self):
        out = self.r.render(
            "{% if x %}A{% else %}B{% endif %}",
            {"x": False},
        )
        self.assertEqual(out, "B")

    def test_for_loop(self):
        out = self.r.render(
            "{% for item in items %}{{ item }},{% endfor %}",
            {"items": [1, 2, 3]},
        )
        self.assertEqual(out, "1,2,3,")

    def test_for_with_loop_var(self):
        out = self.r.render(
            "{% for x in xs %}{{ loop.index }}.{{ x }} "
            "{% if loop.last %}END{% endif %}{% endfor %}",
            {"xs": ["a", "b"]},
        )
        self.assertIn("1.a", out)
        self.assertIn("2.b", out)
        self.assertIn("END", out)

    def test_nested_for_in_if(self):
        out = self.r.render(
            "{% if items %}{% for x in items %}{{ x }} "
            "{% endfor %}{% endif %}",
            {"items": ["A", "B"]},
        )
        # 容忍空格变化
        self.assertIn("A", out)
        self.assertIn("B", out)
        self.assertEqual(out.split(), ["A", "B"])


# ────────── 流水线整合 ──────────

class TestPipeline(unittest.TestCase):

    def setUp(self):
        # 测试用临时归档/审计目录
        self.tmp = tempfile.mkdtemp()
        from src.pipeline import Archiver, AuditTrail
        self.pipeline = DocumentPipeline(
            archiver=Archiver(root=self.tmp),
            audit=AuditTrail(log_path=str(Path(self.tmp) / "audit.jsonl")),
        )

    def test_list_templates(self):
        names = self.pipeline.list_templates()
        # 6 个模板都注册
        for expected in ("incident_report", "operations_daily",
                         "risk_review", "meeting_minutes",
                         "customer_brief", "kpi_summary"):
            self.assertIn(expected, names)

    def test_run_minimal(self):
        result = self.pipeline.run(
            template="incident_report",
            data={"title": "测试事件", "severity": "P1"},
            archive=False,
        )
        self.assertIn("测试事件", result.rendered)
        self.assertIn("P1", result.rendered)
        self.assertEqual(len(result.fingerprint), 64)

    def test_archive_writes_file(self):
        result = self.pipeline.run(
            template="incident_report",
            data={"title": "归档测试"},
            archive=True,
        )
        self.assertIsNotNone(result.archive_path)
        assert result.archive_path is not None  # for type checker
        self.assertTrue(Path(result.archive_path).exists())
        self.assertIn("归档测试",
                      Path(result.archive_path).read_text(encoding="utf-8"))

    def test_unknown_template_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.pipeline.run(template="bogus", data={})


# ────────── 6 模板渲染（minimum viable + full data 各一遍） ──────────

class TestAllTemplates(unittest.TestCase):
    """每个模板：空数据 + 完整数据都能渲染、无未替换的 {{ 残留."""

    def setUp(self):
        from src.pipeline import Archiver, AuditTrail
        self.tmp = tempfile.mkdtemp()
        self.pipeline = DocumentPipeline(
            archiver=Archiver(root=self.tmp),
            audit=AuditTrail(log_path=str(Path(self.tmp) / "a.jsonl")),
        )

    def _check(self, template, data):
        result = self.pipeline.run(template=template, data=data,
                                    archive=False)
        # 不能有未替换的占位符
        self.assertNotIn("{{", result.rendered,
                         f"{template}: unresolved {{{{ in output")
        self.assertNotIn("{%", result.rendered,
                         f"{template}: unresolved {{% in output")
        # 至少几十字节
        self.assertGreater(len(result.rendered), 100,
                           f"{template}: output too short")

    def test_incident_report_empty(self):
        self._check("incident_report", {})

    def test_incident_report_full(self):
        self._check("incident_report", {
            "incident_id": "INC-001", "severity": "P1",
            "title": "网点A路由器故障",
            "started_at": "2026-06-20 14:00",
            "impact": "50终端断网",
            "root_cause": "电源故障",
            "actions": ["更换电源", "切换备线"],
            "assignee": "张工",
            "affected_systems": ["核心网", "BOSS"],
        })

    def test_operations_daily_empty(self):
        self._check("operations_daily", {})

    def test_operations_daily_full(self):
        self._check("operations_daily", {
            "report_date": "2026-06-20",
            "tickets_today": 120, "tickets_yesterday": 100,
            "tickets_delta": "+20%",
            "faults_today": 3, "faults_yesterday": 2,
            "top_faults": [
                {"type": "宽带断网", "count": 12},
                {"type": "ITV 卡顿", "count": 5, "note": "周末高峰"},
            ],
            "highlights": ["FCR 提升 5pp", "投诉率下降"],
            "risks": ["明日有施工"],
            "priorities": ["跟进 X 项目", "优化派单"],
        })

    def test_risk_review_empty(self):
        self._check("risk_review", {})

    def test_risk_review_full(self):
        self._check("risk_review", {
            "review_id": "RR-2026-001", "subject": "客户 A 授信申请",
            "review_date": "2026-06-20",
            "reviewer": "李审批",
            "overall_conclusion": "通过",
            "dimensions": [
                {"name": "信用风险", "score": 4, "comment": "正常"},
                {"name": "操作风险", "score": 3, "comment": "—"},
            ],
            "findings": [
                {"title": "现金流压力", "severity": "中",
                 "description": "Q2 现金流为负", "recommendation": "增加担保"},
            ],
            "remediation": [{"action": "补充抵押", "owner": "客户经理",
                              "due": "2026-07-01"}],
        })

    def test_meeting_minutes_empty(self):
        self._check("meeting_minutes", {})

    def test_meeting_minutes_full(self):
        self._check("meeting_minutes", {
            "title": "Q3 启动会",
            "meeting_at": "2026-06-20 10:00",
            "host": "trainer",
            "attendees": ["张三", "李四", "王五"],
            "topics": [
                {"title": "目标对齐",
                 "points": ["收入 +15%", "客户数 +20%"],
                 "conclusion": "通过"},
            ],
            "decisions": ["启动新产品线"],
            "actions": [
                {"task": "完成方案", "owner": "李四",
                 "due": "2026-06-30", "status": "进行中"},
            ],
        })

    def test_customer_brief_empty(self):
        self._check("customer_brief", {})

    def test_customer_brief_full(self):
        self._check("customer_brief", {
            "customer_name": "甲公司",
            "customer_id": "C-001",
            "industry": "制造业",
            "rm": "张经理",
            "risk_grade": "A",
            "overview": "全国 TOP10 设备制造商",
            "financials": [
                {"name": "营收", "current": "10 亿", "yoy": "+8%"},
            ],
            "cooperation": [
                {"year": "2024", "product": "授信", "amount": "5000 万",
                 "status": "正常"},
            ],
            "risk_signals": ["主要客户集中度过高"],
            "opportunities": [{"title": "供应链金融", "note": "覆盖上下游"}],
        })

    def test_kpi_summary_empty(self):
        self._check("kpi_summary", {})

    def test_kpi_summary_full(self):
        self._check("kpi_summary", {
            "period": "2026 Q2",
            "org": "华东大区",
            "owner": "张总",
            "kpis": [
                {"name": "新签合同", "target": "1 亿",
                 "actual": "1.2 亿", "completion": "120%", "status": "✅"},
            ],
            "overall_completion": "115%",
            "highlights": [{"title": "客户 X 突破",
                            "detail": "签下千万级合同"}],
            "shortfalls": [{"kpi": "续约率", "gap": "5pp",
                            "reason": "竞品挖角", "action": "提升服务"}],
            "lessons": ["快速响应能赢单"],
            "next_targets": [{"kpi": "新签", "target": "1.5 亿"}],
        })


if __name__ == "__main__":
    unittest.main(verbosity=2)
