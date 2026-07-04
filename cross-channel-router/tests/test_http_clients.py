"""测试 http_clients: FeishuClient / WeComClient.

使用 unittest.mock 拦截 urllib 调用，无需真发 HTTP。
"""
import io
import json
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# 让 src.* 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.errors import (
    AUTH_EXPIRED, CHANNEL_UNAVAILABLE, CONTENT_REJECTED,
    INVALID_RECIPIENT, RATE_LIMITED, ChannelError,
)
from src.http_clients import FeishuClient, WeComClient


def _fake_response(payload: dict):
    """构造 urllib.request.urlopen 返回的伪造对象."""
    body = json.dumps(payload).encode("utf-8")
    fake = MagicMock()
    fake.__enter__ = MagicMock(return_value=fake)
    fake.__exit__ = MagicMock(return_value=False)
    fake.read = MagicMock(return_value=body)
    return fake


class TestFeishuClient(unittest.TestCase):

    def test_constructor_requires_credentials(self):
        with self.assertRaises(ValueError):
            FeishuClient(app_id="", app_secret="x")
        with self.assertRaises(ValueError):
            FeishuClient(app_id="x", app_secret="")

    @patch("src.http_clients.urllib.request.urlopen")
    def test_get_token_success_and_cache(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "code": 0,
            "tenant_access_token": "t_test_abc",
            "expire": 7200,
        })
        c = FeishuClient(app_id="a", app_secret="s")
        tok1 = c._get_token()
        tok2 = c._get_token()  # 应命中缓存
        self.assertEqual(tok1, "t_test_abc")
        self.assertEqual(tok2, "t_test_abc")
        # 缓存命中：urlopen 应只被调用 1 次
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_get_token_failure_raises(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "code": 99991663, "msg": "token expired",
        })
        c = FeishuClient(app_id="a", app_secret="s")
        with self.assertRaises(ChannelError) as ctx:
            c._get_token()
        self.assertEqual(ctx.exception.code, AUTH_EXPIRED)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_send_message_success(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _fake_response({"code": 0, "tenant_access_token": "tok",
                            "expire": 7200}),
            _fake_response({"code": 0, "msg": "success",
                            "data": {"message_id": "om_xxx"}}),
        ]
        c = FeishuClient(app_id="a", app_secret="s")
        r = c.send_message(
            receive_id="ou_user", msg_type="text",
            content={"text": "hi"},
        )
        self.assertEqual(r["message_id"], "om_xxx")

    @patch("src.http_clients.urllib.request.urlopen")
    def test_send_message_error_mapping(self, mock_urlopen):
        # 230018 = bot 不在群 → PERMISSION_DENIED
        mock_urlopen.side_effect = [
            _fake_response({"code": 0, "tenant_access_token": "tok",
                            "expire": 7200}),
            _fake_response({"code": 230018, "msg": "bot not in chat"}),
        ]
        c = FeishuClient(app_id="a", app_secret="s")
        with self.assertRaises(ChannelError) as ctx:
            c.send_message(receive_id="oc_x", msg_type="text",
                           content={"text": "hi"})
        from src.errors import PERMISSION_DENIED
        self.assertEqual(ctx.exception.code, PERMISSION_DENIED)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_network_error_maps_to_channel_unavailable(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        c = FeishuClient(app_id="a", app_secret="s")
        with self.assertRaises(ChannelError) as ctx:
            c._get_token()
        self.assertEqual(ctx.exception.code, CHANNEL_UNAVAILABLE)


class TestWeComClient(unittest.TestCase):

    def test_constructor_requires_credentials(self):
        with self.assertRaises(ValueError):
            WeComClient(corp_id="", corp_secret="x")

    @patch("src.http_clients.urllib.request.urlopen")
    def test_get_token_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "errcode": 0, "access_token": "ac_xxx", "expires_in": 7200,
        })
        c = WeComClient(corp_id="cid", corp_secret="sec", agent_id=1000001)
        self.assertEqual(c._get_token(), "ac_xxx")

    @patch("src.http_clients.urllib.request.urlopen")
    def test_send_app_message_requires_agent_id(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "errcode": 0, "access_token": "ac", "expires_in": 7200,
        })
        c = WeComClient(corp_id="cid", corp_secret="sec")  # 无 agent_id
        with self.assertRaises(ChannelError) as ctx:
            c.send_app_message(touser="u1", msgtype="text",
                               content={"content": "hi"})
        self.assertEqual(ctx.exception.code, CONTENT_REJECTED)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_send_app_message_success(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _fake_response({"errcode": 0, "access_token": "ac",
                            "expires_in": 7200}),
            _fake_response({"errcode": 0, "errmsg": "ok",
                            "msgid": "MSG_ID_123"}),
        ]
        c = WeComClient(corp_id="cid", corp_secret="sec",
                        agent_id=1000001)
        r = c.send_app_message(touser="u1", msgtype="text",
                               content={"content": "hi"})
        self.assertEqual(r["msgid"], "MSG_ID_123")

    @patch("src.http_clients.urllib.request.urlopen")
    def test_send_app_message_rate_limited(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _fake_response({"errcode": 0, "access_token": "ac",
                            "expires_in": 7200}),
            _fake_response({"errcode": 45009, "errmsg": "api freq out of limit"}),
        ]
        c = WeComClient(corp_id="cid", corp_secret="sec",
                        agent_id=1000001)
        with self.assertRaises(ChannelError) as ctx:
            c.send_app_message(touser="u1", msgtype="text",
                               content={"content": "hi"})
        self.assertEqual(ctx.exception.code, RATE_LIMITED)


class TestFeishuAdapterIntegration(unittest.TestCase):
    """测试 adapter ↔ client 集成."""

    def setUp(self):
        # 清空任何可能污染的环境变量
        for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET",
                  "WECOM_CORP_ID", "WECOM_CORP_SECRET", "WECOM_AGENT_ID"):
            os.environ.pop(k, None)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_feishu_adapter_real_send(self, mock_urlopen):
        from src.adapter import FeishuAdapter
        from src.message import OutboundMessage, Recipients, Recipient

        mock_urlopen.side_effect = [
            _fake_response({"code": 0, "tenant_access_token": "tok",
                            "expire": 7200}),
            _fake_response({"code": 0, "data": {"message_id": "om_abc"}}),
        ]

        adapter = FeishuAdapter(app_id="aid", app_secret="sec")
        msg = OutboundMessage(
            message_id="m1", trace_id="t1",
            message_type="text",
            content={"text": "hello"},
            recipients=Recipients(targets=[Recipient(type="user", id="ou_aaa")]),
        )
        result = adapter.send(msg)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.channel_message_id, "om_abc")

    @patch("src.http_clients.urllib.request.urlopen")
    def test_feishu_adapter_chat_id_inferred(self, mock_urlopen):
        from src.adapter import FeishuAdapter
        from src.message import OutboundMessage, Recipients, Recipient

        captured = {}

        def side_effect(req, timeout=10):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            captured.setdefault("urls", []).append(url)
            if "tenant_access_token" in url:
                return _fake_response({"code": 0,
                                       "tenant_access_token": "tok",
                                       "expire": 7200})
            return _fake_response({"code": 0,
                                   "data": {"message_id": "om_x"}})

        mock_urlopen.side_effect = side_effect

        adapter = FeishuAdapter(app_id="aid", app_secret="sec")
        msg = OutboundMessage(
            message_id="m2", trace_id="t2",
            message_type="text",
            content={"text": "hello chat"},
            recipients=Recipients(targets=[Recipient(type="group",
                                                  id="oc_chat_xxx")]),
        )
        result = adapter.send(msg)
        self.assertEqual(result.status, "sent")
        # 第二次请求应包含 receive_id_type=chat_id
        send_url = [u for u in captured["urls"] if "im/v1/messages" in u][0]
        self.assertIn("receive_id_type=chat_id", send_url)

    def test_feishu_adapter_no_credentials_falls_back(self):
        from src.adapter import FeishuAdapter
        from src.message import OutboundMessage, Recipients, Recipient

        adapter = FeishuAdapter()  # 无 token
        self.assertIsNone(adapter.client)
        msg = OutboundMessage(
            message_id="m3", trace_id="t3",
            message_type="text", content={"text": "hi"},
            recipients=Recipients(targets=[Recipient(type="user", id="ou_x")]),
        )
        result = adapter.send(msg)
        self.assertEqual(result.status, "queued")
        self.assertEqual(result.channel, "feishu")
        self.assertEqual(result.error_code, AUTH_EXPIRED)


if __name__ == "__main__":
    unittest.main()
