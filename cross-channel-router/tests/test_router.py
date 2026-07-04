"""单元测试 — 覆盖路由/降级/幂等/审计."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 让 import 找得到本地 src/
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from src import (  # noqa: E402
    ChannelDelivery, ConsoleAdapter, CrossChannelRouter, FeishuAdapter,
    OutboundMessage, RouteResult, RoutingEngine, WeComAdapter,
    degrade,
)
from src.audit import AuditLogger, IdempotencyStore  # noqa: E402


# ─────────────────────────────────────────────────────
# 1) 消息模型 & 校验
# ─────────────────────────────────────────────────────

class TestOutboundMessage(unittest.TestCase):

    def test_invalid_message_type_raises(self):
        with self.assertRaises(ValueError):
            OutboundMessage(message_type="bogus")

    def test_invalid_priority_raises(self):
        with self.assertRaises(ValueError):
            OutboundMessage(priority="ultra-high")

    def test_default_idempotency_key(self):
        m = OutboundMessage()
        self.assertEqual(m.idempotency_key, m.message_id)

    def test_for_channel_isolation(self):
        m = OutboundMessage(message_type="text", content={"text": "hi"})
        m1 = m.for_channel("feishu")
        m2 = m.for_channel("wecom")
        self.assertNotEqual(m1.message_id, m2.message_id)
        self.assertNotEqual(m1.idempotency_key, m2.idempotency_key)
        self.assertEqual(m1.trace_id, m2.trace_id)  # trace_id 共享

    def test_to_dict_roundtrip(self):
        m = OutboundMessage(
            message_type="card",
            content={"title": "T", "body": "B"},
            recipients={"channels": ["feishu"], "targets": [{"type": "user", "id": "u1"}]},
        )
        d = m.to_dict()
        self.assertEqual(d["message_type"], "card")
        self.assertEqual(d["recipients"]["targets"][0]["id"], "u1")


# ─────────────────────────────────────────────────────
# 2) 路由引擎
# ─────────────────────────────────────────────────────

class TestRoutingEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RoutingEngine([
            {"match": {"priority": "critical"},
             "route": {"channels": ["feishu", "wecom"]}},
            {"match": {"source_skill": "alert_engine",
                       "priority": ["high", "critical"]},
             "route": {"channels": ["feishu"]}},
            {"match": {"any": True},
             "route": {"channels": ["console"]}},
        ])

    def test_critical_to_both(self):
        m = OutboundMessage(priority="critical")
        self.assertEqual(set(self.engine.decide(m)), {"feishu", "wecom"})

    def test_alert_high_to_feishu(self):
        m = OutboundMessage(priority="high",
                            metadata={"source_skill": "alert_engine"})
        self.assertEqual(self.engine.decide(m), ["feishu"])

    def test_default_to_console(self):
        m = OutboundMessage(priority="low")
        self.assertEqual(self.engine.decide(m), ["console"])

    def test_explicit_recipients_overrides_rules(self):
        m = OutboundMessage(
            priority="critical",
            recipients={"channels": ["console"]},
        )
        self.assertEqual(self.engine.decide(m), ["console"])


# ─────────────────────────────────────────────────────
# 3) 降级矩阵
# ─────────────────────────────────────────────────────

class TestDegradation(unittest.TestCase):

    def test_card_to_text_when_unsupported(self):
        m = OutboundMessage(
            message_type="card",
            content={"title": "T", "body": "B", "url": "https://x"},
        )
        caps = {"supports": {"card": False, "buttons": False,
                             "max_text_length": 1000, "markdown": "none"}}
        out = degrade(m, caps)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].message_type, "text")
        self.assertIn("【T】", out[0].content["text"])
        self.assertIn("https://x", out[0].content["text"])

    def test_buttons_dropped_to_inline(self):
        m = OutboundMessage(
            message_type="card",
            content={"title": "T", "body": "B",
                     "buttons": [{"label": "同意"}, {"label": "拒绝"}]},
        )
        caps = {"supports": {"card": True, "buttons": False,
                             "max_text_length": 1000, "markdown": "full"}}
        out = degrade(m, caps)
        self.assertNotIn("buttons", out[0].content)
        self.assertIn("1. 同意", out[0].content["body"])

    def test_long_text_split(self):
        long_text = "X" * 1500
        m = OutboundMessage(message_type="text", content={"text": long_text})
        caps = {"supports": {"max_text_length": 500, "markdown": "full"}}
        out = degrade(m, caps)
        self.assertGreater(len(out), 1)
        # 每一片含分页标记
        for i, part in enumerate(out, 1):
            self.assertIn(f"[{i}/{len(out)}]", part.content["text"])
        # 分片消息 id 唯一
        ids = {p.message_id for p in out}
        self.assertEqual(len(ids), len(out))

    def test_markdown_strip_basic(self):
        m = OutboundMessage(
            message_type="text",
            content={"text": "# 标题\n## 子\n~~删~~\n**粗**"},
        )
        caps = {"supports": {"max_text_length": 1000, "markdown": "basic"}}
        out = degrade(m, caps)
        text = out[0].content["text"]
        self.assertNotIn("# 标题", text)
        self.assertIn("标题", text)
        self.assertNotIn("~~", text)


# ─────────────────────────────────────────────────────
# 4) 幂等性
# ─────────────────────────────────────────────────────

class TestIdempotency(unittest.TestCase):

    def test_seen_returns_false_first_then_true(self):
        store = IdempotencyStore(ttl_seconds=60)
        self.assertFalse(store.seen("key1"))
        self.assertTrue(store.seen("key1"))
        self.assertFalse(store.seen("key2"))

    def test_router_skips_duplicate(self):
        sink = []
        adapter = ConsoleAdapter(sink=sink)
        router = CrossChannelRouter(
            adapters={"console": adapter},
            audit=AuditLogger(log_path=tempfile.mktemp(suffix=".jsonl")),
        )
        m = OutboundMessage(
            message_type="text",
            content={"text": "hi"},
            recipients={"channels": ["console"]},
        )
        r1 = router.send(m)
        r2 = router.send(m)
        self.assertEqual(r1.status, "sent")
        # 第二次因为幂等命中，没有真正发送
        self.assertEqual(len(sink), 1)
        self.assertEqual(r2.delivered[0].status, "idempotent")


# ─────────────────────────────────────────────────────
# 5) 路由器整合
# ─────────────────────────────────────────────────────

class TestRouter(unittest.TestCase):

    def setUp(self):
        # 强制清空环境变量，确保两个适配器走 fallback
        for v in ("FEISHU_APP_ID", "FEISHU_APP_SECRET",
                  "WECOM_CORP_ID", "WECOM_CORP_SECRET", "WECOM_AGENT_ID"):
            os.environ.pop(v, None)
        self.audit_path = tempfile.mktemp(suffix=".jsonl")
        self.console_sink = []
        self.feishu = FeishuAdapter(fallback=ConsoleAdapter(sink=self.console_sink))
        self.wecom = WeComAdapter(fallback=ConsoleAdapter(sink=self.console_sink))
        self.console = ConsoleAdapter(sink=self.console_sink)
        self.router = CrossChannelRouter(
            adapters={"feishu": self.feishu,
                      "wecom": self.wecom,
                      "console": self.console},
            engine=RoutingEngine([
                {"match": {"priority": "critical"},
                 "route": {"channels": ["feishu", "wecom"]}},
                {"match": {"any": True},
                 "route": {"channels": ["console"]}},
            ]),
            audit=AuditLogger(log_path=self.audit_path),
        )

    def test_critical_fans_out(self):
        m = OutboundMessage(
            message_type="text",
            priority="critical",
            content={"text": "alert!"},
            recipients={"targets": [{"type": "user", "id": "u1"}]},
        )
        result = self.router.send(m)
        channels = {d.channel for d in result.delivered}
        self.assertEqual(channels, {"feishu", "wecom"})
        # 没 token，会走 fallback console
        self.assertEqual(len(self.console_sink), 2)

    def test_default_routes_to_console(self):
        m = OutboundMessage(
            message_type="text", priority="normal",
            content={"text": "hi"},
            recipients={"targets": [{"type": "user", "id": "u1"}]},
        )
        result = self.router.send(m)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.delivered[0].channel, "console")

    def test_unregistered_channel_returns_failed(self):
        m = OutboundMessage(
            message_type="text",
            recipients={"channels": ["sms"], "targets": [{"type": "user", "id": "u1"}]},
        )
        result = self.router.send(m)
        self.assertEqual(result.delivered[0].status, "failed")
        self.assertEqual(result.delivered[0].error_code, "CHANNEL_UNAVAILABLE")

    def test_audit_log_written(self):
        m = OutboundMessage(
            message_type="text",
            content={"text": "hi"},
            recipients={"targets": [{"type": "user", "id": "u1"}]},
        )
        self.router.send(m)
        # 至少包含 route_decided + channel_send + route_done 三条
        log_lines = Path(self.audit_path).read_text().strip().split("\n")
        events = {l for l in log_lines if l}
        self.assertGreaterEqual(len(events), 3)
        text = "\n".join(events)
        self.assertIn("route_decided", text)
        self.assertIn("channel_send", text)
        self.assertIn("route_done", text)


# ─────────────────────────────────────────────────────
# 6) From-config 工厂
# ─────────────────────────────────────────────────────

class TestFromConfig(unittest.TestCase):

    def test_from_config_dict(self):
        router = CrossChannelRouter.from_config({
            "adapters": {
                "feishu": {},
                "console": {},
            },
            "rules": [
                {"match": {"any": True}, "route": {"channels": ["console"]}},
            ],
            "audit_log_path": tempfile.mktemp(suffix=".jsonl"),
        })
        self.assertIn("feishu", router.adapters)
        self.assertIn("console", router.adapters)


if __name__ == "__main__":
    unittest.main(verbosity=2)
