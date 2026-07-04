"""
test_error_code_coverage — 系统性验证 FEISHU_ERROR_MAP / WECOM_ERROR_MAP 的真实性

对每条映射构造 mock response，验证 ChannelError.code 落到正确的标准码上。
这是 P2-3 离线部分：在拿到 sandbox token 之前先把映射表的"翻译"逻辑跑通。
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.errors import (
    AUTH_EXPIRED, CHANNEL_UNAVAILABLE, CONTENT_REJECTED,
    INVALID_RECIPIENT, MESSAGE_TOO_LARGE, PERMISSION_DENIED,
    RATE_LIMITED, ChannelError,
)
from src.http_clients import (
    FEISHU_ERROR_MAP, WECOM_ERROR_MAP, FeishuClient, WeComClient,
)


def _fake_response(payload: dict):
    body = json.dumps(payload).encode("utf-8")
    fake = MagicMock()
    fake.__enter__ = MagicMock(return_value=fake)
    fake.__exit__ = MagicMock(return_value=False)
    fake.read = MagicMock(return_value=body)
    return fake


class TestFeishuErrorMapCoverage(unittest.TestCase):
    """
    覆盖 FEISHU_ERROR_MAP 中每条映射，外加未映射的兜底情况。
    """

    EXPECTED_MAP = {
        # token 类
        99991663: AUTH_EXPIRED,
        99991664: AUTH_EXPIRED,
        10003: AUTH_EXPIRED,        # 经 live_e2e 实测发现
        # 接收方类
        230001: INVALID_RECIPIENT,
        230002: INVALID_RECIPIENT,
        # 权限类
        230015: PERMISSION_DENIED,
        230018: PERMISSION_DENIED,
        # 内容/请求格式
        99991400: CONTENT_REJECTED,
        # 大小
        11000: MESSAGE_TOO_LARGE,
        # 限流
        99991672: RATE_LIMITED,
    }

    def test_map_completeness(self):
        """确保 EXPECTED_MAP 与实际 FEISHU_ERROR_MAP 完全一致 (没有漏挂或多挂)."""
        self.assertEqual(self.EXPECTED_MAP, FEISHU_ERROR_MAP)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_each_feishu_code_routes_correctly(self, mock_urlopen):
        """对 FEISHU_ERROR_MAP 中每个 code 触发一次 send_message，验证标准码."""
        for feishu_code, expected_std in self.EXPECTED_MAP.items():
            with self.subTest(feishu_code=feishu_code):
                # 第一次 urlopen → token, 第二次 → 错误
                mock_urlopen.side_effect = [
                    _fake_response({"code": 0,
                                    "tenant_access_token": "tok",
                                    "expire": 7200}),
                    _fake_response({"code": feishu_code,
                                    "msg": f"feishu_{feishu_code}"}),
                ]
                c = FeishuClient(app_id="a", app_secret="s")
                with self.assertRaises(ChannelError) as ctx:
                    c.send_message(receive_id="ou_x", msg_type="text",
                                   content={"text": "hi"})
                self.assertEqual(
                    ctx.exception.code, expected_std,
                    f"feishu code {feishu_code} should map to {expected_std} "
                    f"but got {ctx.exception.code}",
                )

    @patch("src.http_clients.urllib.request.urlopen")
    def test_unknown_feishu_code_falls_back_to_content_rejected(
            self, mock_urlopen):
        """未知错误码兜底 → CONTENT_REJECTED (设计假设)."""
        mock_urlopen.side_effect = [
            _fake_response({"code": 0, "tenant_access_token": "tok",
                            "expire": 7200}),
            _fake_response({"code": 99999999, "msg": "unknown"}),
        ]
        c = FeishuClient(app_id="a", app_secret="s")
        with self.assertRaises(ChannelError) as ctx:
            c.send_message(receive_id="ou_x", msg_type="text",
                           content={"text": "hi"})
        self.assertEqual(ctx.exception.code, CONTENT_REJECTED)


class TestWeComErrorMapCoverage(unittest.TestCase):

    EXPECTED_MAP = {
        # token 类
        40014: AUTH_EXPIRED,
        42001: AUTH_EXPIRED,
        40029: AUTH_EXPIRED,
        # 权限
        60011: PERMISSION_DENIED,
        60020: PERMISSION_DENIED,
        # 接收方
        81013: INVALID_RECIPIENT,
        # 限流
        45009: RATE_LIMITED,
        45033: RATE_LIMITED,
        # 大小
        45007: MESSAGE_TOO_LARGE,
    }

    def test_map_completeness(self):
        self.assertEqual(self.EXPECTED_MAP, WECOM_ERROR_MAP)

    @patch("src.http_clients.urllib.request.urlopen")
    def test_each_wecom_code_routes_correctly(self, mock_urlopen):
        for wecom_code, expected_std in self.EXPECTED_MAP.items():
            with self.subTest(wecom_code=wecom_code):
                mock_urlopen.side_effect = [
                    _fake_response({"errcode": 0, "access_token": "ac",
                                    "expires_in": 7200}),
                    _fake_response({"errcode": wecom_code,
                                    "errmsg": f"wecom_{wecom_code}"}),
                ]
                c = WeComClient(corp_id="cid", corp_secret="sec",
                                agent_id="1000001")
                with self.assertRaises(ChannelError) as ctx:
                    c.send_app_message(touser="u1", msgtype="text",
                                       content={"content": "hi"})
                self.assertEqual(
                    ctx.exception.code, expected_std,
                    f"wecom code {wecom_code} should map to {expected_std} "
                    f"but got {ctx.exception.code}",
                )

    @patch("src.http_clients.urllib.request.urlopen")
    def test_unknown_wecom_code_falls_back_to_content_rejected(
            self, mock_urlopen):
        mock_urlopen.side_effect = [
            _fake_response({"errcode": 0, "access_token": "ac",
                            "expires_in": 7200}),
            _fake_response({"errcode": 99999, "errmsg": "unknown"}),
        ]
        c = WeComClient(corp_id="cid", corp_secret="sec",
                        agent_id="1000001")
        with self.assertRaises(ChannelError) as ctx:
            c.send_app_message(touser="u1", msgtype="text",
                               content={"content": "hi"})
        self.assertEqual(ctx.exception.code, CONTENT_REJECTED)


class TestStandardErrorCodeUniverse(unittest.TestCase):
    """
    确保我们在 errors.py 里定义的标准错误码全部有用武之地。
    若某个标准码两个平台都不会映射到它，可能意味着规范设计过度。
    """

    STANDARD_CODES = {
        AUTH_EXPIRED, CHANNEL_UNAVAILABLE, CONTENT_REJECTED,
        INVALID_RECIPIENT, MESSAGE_TOO_LARGE, PERMISSION_DENIED,
        RATE_LIMITED,
    }

    def test_all_std_codes_used_at_least_once(self):
        used = set(FEISHU_ERROR_MAP.values()) | set(WECOM_ERROR_MAP.values())
        # CHANNEL_UNAVAILABLE 由网络层兜底,不在 ERROR_MAP 中
        # 其余应有至少一个映射
        expected_used = self.STANDARD_CODES - {CHANNEL_UNAVAILABLE}
        unused = expected_used - used
        self.assertEqual(
            set(), unused,
            f"标准码 {unused} 在 FEISHU/WECOM 任一映射表中都没出现，"
            "可能是规范过度设计或映射缺失",
        )


if __name__ == "__main__":
    unittest.main()
