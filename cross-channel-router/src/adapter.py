"""
src.adapter — ChannelAdapter 抽象基类 + 三个 reference 实现
(ConsoleAdapter, FeishuAdapter, WeComAdapter)

FeishuAdapter / WeComAdapter:
  - 缺 token 时降级到 fallback ConsoleAdapter (status=queued)
  - 有 token 时通过 http_clients.FeishuClient/WeComClient 真实发送
  - HTTP 调用失败时返回 SendResult(status='failed', error_code=...)
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from .errors import (
    AUTH_EXPIRED, CHANNEL_UNAVAILABLE, INVALID_RECIPIENT,
    MESSAGE_TOO_LARGE, PERMISSION_DENIED, ChannelError, SendResult,
)
from .http_clients import FeishuClient, WeComClient
from .message import OutboundMessage


# ────────────────────────────────────────────
# 抽象基类
# ────────────────────────────────────────────

class ChannelAdapter(ABC):
    """所有渠道适配器必须实现的接口（对应 §5）."""

    channel: str = "unknown"

    @abstractmethod
    def send(self, message: OutboundMessage) -> SendResult:
        """发送消息，返回 SendResult."""

    @abstractmethod
    def capabilities(self) -> dict:
        """声明能力 (对应 §5.3)."""

    # 默认实现：可选
    def edit(self, channel_message_id: str, new_content: dict) -> SendResult:
        raise NotImplementedError(f"{self.channel} adapter does not support edit")

    def delete(self, channel_message_id: str) -> SendResult:
        raise NotImplementedError(f"{self.channel} adapter does not support delete")


# ────────────────────────────────────────────
# 1. ConsoleAdapter — 永远可用的兜底
# ────────────────────────────────────────────

class ConsoleAdapter(ChannelAdapter):
    """打印到 stdout，用于测试 / 降级 / 离线场景."""

    channel = "console"

    def __init__(self, sink=None):
        # sink 默认 print, 可注入 list 收集输出 (测试用)
        self.sink = sink

    def send(self, message: OutboundMessage) -> SendResult:
        start = time.time()
        line = self._format(message)
        if self.sink is None:
            print(line)
        else:
            self.sink.append(line)
        return SendResult(
            status="sent",
            channel=self.channel,
            channel_message_id=f"console_{message.message_id}",
            sent_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=int((time.time() - start) * 1000),
        )

    def capabilities(self) -> dict:
        return {
            "supports": {
                "card": True, "buttons": True, "image": True,
                "voice": True, "file": True, "thread": False,
                "edit_message": False, "delete_message": False,
                "reaction": False, "mention": True,
                "markdown": "full",
                "max_text_length": 100000,
                "max_buttons_per_card": 99,
            },
            "rate_limits": {"per_minute": 100000, "per_hour": 1000000},
        }

    def _format(self, m: OutboundMessage) -> str:
        c = m.content
        title = c.get("title", "")
        body = c.get("body") or c.get("text") or ""
        recipients = ",".join(t.id for t in m.recipients.targets) or "<no targets>"
        return (f"[{m.priority.upper()}] [{m.message_type}] "
                f"to={recipients} | {title}\n  {body}")


# ────────────────────────────────────────────
# 2. FeishuAdapter — Reference 实现 (token 注入式)
# ────────────────────────────────────────────

class FeishuAdapter(ChannelAdapter):
    """
    飞书适配器。真实发送依赖 lark token；缺 token 时降级为 ConsoleAdapter 行为
    并在 SendResult 标注 status='queued' (等待 token)。
    """

    channel = "feishu"

    def __init__(self, app_id: Optional[str] = None,
                 app_secret: Optional[str] = None,
                 fallback: Optional[ChannelAdapter] = None,
                 client: Optional[FeishuClient] = None,
                 timeout: int = 10):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.fallback = fallback or ConsoleAdapter()
        self.timeout = timeout
        self._client = client
        self._sent_log: list[dict] = []   # 测试可读

    @property
    def client(self) -> Optional[FeishuClient]:
        if self._client is not None:
            return self._client
        if self.app_id and self.app_secret:
            self._client = FeishuClient(
                app_id=self.app_id,
                app_secret=self.app_secret,
                timeout=self.timeout,
            )
        return self._client

    def send(self, message: OutboundMessage) -> SendResult:
        start = time.time()
        if self.client is None:
            # 降级：交给 fallback 但标记为 queued
            fb = self.fallback.send(message)
            fb.channel = self.channel
            fb.status = "queued"
            fb.error_code = AUTH_EXPIRED
            fb.error_message = (
                "FEISHU_APP_ID/SECRET not configured; "
                "delegated to fallback adapter."
            )
            return fb

        return self._real_send(message, start)

    def _real_send(self, message: OutboundMessage, start: float) -> SendResult:
        """通过 FeishuClient 真实发送."""
        client = self.client
        assert client is not None
        # 拆解 receive_id
        targets = message.recipients.targets
        if not targets:
            return SendResult(
                status="failed", channel=self.channel,
                error_code=INVALID_RECIPIENT,
                error_message="no targets in message.recipients",
                duration_ms=int((time.time() - start) * 1000),
            )
        receive_id = targets[0].id
        # 推断 receive_id_type: ou_xxx → open_id, oc_xxx → chat_id
        if receive_id.startswith("oc_"):
            receive_id_type = "chat_id"
        elif receive_id.startswith("ou_"):
            receive_id_type = "open_id"
        elif receive_id.startswith("on_"):
            receive_id_type = "union_id"
        elif "@" in receive_id:
            receive_id_type = "email"
        else:
            receive_id_type = "open_id"

        # 拼 payload
        msg_type, content = self._convert_to_feishu(message)
        try:
            data = client.send_message(
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                msg_type=msg_type,
                content=content,
            )
            self._sent_log.append({
                "message_id": message.message_id,
                "trace_id": message.trace_id,
                "feishu_message_id": data.get("message_id"),
            })
            return SendResult(
                status="sent",
                channel=self.channel,
                channel_message_id=data.get("message_id"),
                sent_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=int((time.time() - start) * 1000),
            )
        except ChannelError as e:
            return SendResult(
                status="failed",
                channel=self.channel,
                error_code=e.code,
                error_message=e.message,
                duration_ms=int((time.time() - start) * 1000),
            )

    def _convert_to_feishu(self, m: OutboundMessage):
        """OutboundMessage → (msg_type, content_dict).

        返回的 content 是已结构化的 dict，
        客户端会负责 json.dumps 包装到 'content' 字段。
        """
        c = m.content
        if m.message_type == "text":
            return "text", {"text": c.get("text", "")}
        if m.message_type in ("card", "notify", "alert", "report"):
            card = {
                "elements": [
                    {"tag": "div",
                     "text": {"tag": "lark_md",
                              "content": c.get("body", "")}},
                ],
                "header": {"title": {"tag": "plain_text",
                                     "content": c.get("title", "")}},
            }
            # 添加按钮
            buttons = c.get("buttons") or []
            if buttons:
                actions = []
                for btn in buttons:
                    item = {
                        "tag": "button",
                        "text": {"tag": "plain_text",
                                 "content": btn.get("label",
                                                    btn.get("text", ""))},
                    }
                    if btn.get("url") or btn.get("action_url"):
                        item["url"] = btn.get("url") or btn.get("action_url")
                        item["type"] = "default"
                    actions.append(item)
                card["elements"].append({"tag": "action", "actions": actions})
            return "interactive", card
        if m.message_type == "image":
            return "image", {"image_key": c.get("image_key", "")}
        if m.message_type == "file":
            return "file", {"file_key": c.get("file_key", "")}
        # 兜底：把内容 str 化为 text
        return "text", {"text": str(c)}

    def capabilities(self) -> dict:
        return {
            "supports": {
                "card": True, "buttons": True, "image": True,
                "voice": True, "file": True, "thread": True,
                "edit_message": True, "delete_message": True,
                "reaction": True, "mention": True,
                "markdown": "basic",        # 飞书卡片 markdown 子集
                "max_text_length": 30000,
                "max_buttons_per_card": 5,
            },
            "rate_limits": {"per_minute": 100, "per_hour": 1000},
        }


# ────────────────────────────────────────────
# 3. WeComAdapter — Reference 实现
# ────────────────────────────────────────────

class WeComAdapter(ChannelAdapter):
    """企业微信适配器。同 FeishuAdapter 模式，缺 token 走 fallback."""

    channel = "wecom"

    def __init__(self, corp_id: Optional[str] = None,
                 corp_secret: Optional[str] = None,
                 agent_id: Optional[str] = None,
                 fallback: Optional[ChannelAdapter] = None,
                 client: Optional[WeComClient] = None,
                 timeout: int = 10):
        self.corp_id = corp_id or os.getenv("WECOM_CORP_ID")
        self.corp_secret = corp_secret or os.getenv("WECOM_CORP_SECRET")
        self.agent_id = agent_id or os.getenv("WECOM_AGENT_ID")
        self.fallback = fallback or ConsoleAdapter()
        self.timeout = timeout
        self._client = client
        self._sent_log: list[dict] = []

    @property
    def client(self) -> Optional[WeComClient]:
        if self._client is not None:
            return self._client
        if self.corp_id and self.corp_secret:
            self._client = WeComClient(
                corp_id=self.corp_id,
                corp_secret=self.corp_secret,
                agent_id=self.agent_id,
                timeout=self.timeout,
            )
        return self._client

    def send(self, message: OutboundMessage) -> SendResult:
        start = time.time()
        if self.client is None:
            fb = self.fallback.send(message)
            fb.channel = self.channel
            fb.status = "queued"
            fb.error_code = AUTH_EXPIRED
            fb.error_message = "WECOM credentials not configured"
            return fb

        return self._real_send(message, start)

    def _real_send(self, message: OutboundMessage, start: float) -> SendResult:
        client = self.client
        assert client is not None
        targets = message.recipients.targets
        if not targets:
            return SendResult(
                status="failed", channel=self.channel,
                error_code=INVALID_RECIPIENT,
                error_message="no targets in message.recipients",
                duration_ms=int((time.time() - start) * 1000),
            )
        # 企微: touser 用 | 拼接, 群组用 toparty
        touser = "|".join(t.id for t in targets if t.type == "user")
        toparty = "|".join(t.id for t in targets if t.type == "group")

        msgtype, content = self._convert_to_wecom(message)
        try:
            data = client.send_app_message(
                touser=touser,
                toparty=toparty,
                msgtype=msgtype,
                content=content,
            )
            msg_id = data.get("msgid") or data.get("response_code") or ""
            self._sent_log.append({
                "message_id": message.message_id,
                "trace_id": message.trace_id,
                "wecom_msgid": msg_id,
            })
            return SendResult(
                status="sent",
                channel=self.channel,
                channel_message_id=msg_id or f"wc_{message.message_id}",
                sent_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=int((time.time() - start) * 1000),
            )
        except ChannelError as e:
            return SendResult(
                status="failed",
                channel=self.channel,
                error_code=e.code,
                error_message=e.message,
                duration_ms=int((time.time() - start) * 1000),
            )

    def _convert_to_wecom(self, m: OutboundMessage):
        """OutboundMessage → (msgtype, content_dict)."""
        c = m.content
        if m.message_type == "text":
            return "text", {"content": c.get("text", "")}
        if m.message_type in ("card", "notify", "alert", "report"):
            return "textcard", {
                "title": c.get("title", ""),
                "description": c.get("body", ""),
                "url": c.get("url", "https://example.com"),
                "btntxt": (c.get("buttons") or [{}])[0].get("label", "详情"),
            }
        if m.message_type == "image":
            return "image", {"media_id": c.get("media_id", "")}
        if m.message_type == "file":
            return "file", {"media_id": c.get("media_id", "")}
        return "text", {"content": str(c)}

    def capabilities(self) -> dict:
        return {
            "supports": {
                "card": True, "buttons": False, "image": True,
                "voice": True, "file": True, "thread": False,
                "edit_message": False, "delete_message": False,
                "reaction": False, "mention": True,
                "markdown": "basic",
                "max_text_length": 2048,
                "max_buttons_per_card": 0,
            },
            "rate_limits": {"per_minute": 200, "per_hour": 2000},
        }
