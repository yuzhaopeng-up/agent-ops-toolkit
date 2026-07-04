"""
src.message — 统一消息模型

与 governance/im-channel-interface-spec.md v1.0 一致。
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Union

VALID_MESSAGE_TYPES = {
    "text", "card", "notify", "alert", "report",
    "file", "image", "voice", "video", "location",
    "quick_reply", "human_decision",
}
VALID_PRIORITIES = {"critical", "high", "normal", "low"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "msg") -> str:
    # 时间戳 + 随机后缀，可读且全局唯一
    ts = int(time.time() * 1000)
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:8]}"


@dataclass
class Recipient:
    type: str         # user | group | chat
    id: str
    thread_id: Optional[str] = None

    @classmethod
    def parse(cls, raw: Any) -> "Recipient":
        if isinstance(raw, Recipient):
            return raw
        if isinstance(raw, str):
            # 简易语法：'@duty', 'ou_xxxx', 'oc_xxxx'
            if raw.startswith("@"):
                return cls(type="user", id=raw)
            return cls(type="user", id=raw)
        if isinstance(raw, dict):
            return cls(
                type=raw.get("type", "user"),
                id=raw["id"],
                thread_id=raw.get("thread_id"),
            )
        raise TypeError(f"Cannot parse recipient from {raw!r}")


@dataclass
class Recipients:
    """消息收件人集合."""
    channels: list[str] = field(default_factory=list)   # 渠道码列表
    targets: list[Recipient] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: Any) -> "Recipients":
        if isinstance(raw, Recipients):
            return raw
        raw = raw or {}
        return cls(
            channels=list(raw.get("channels", [])),
            targets=[Recipient.parse(t) for t in raw.get("targets", [])],
        )


@dataclass
class OutboundMessage:
    """出站消息。所有字段对应 IM 渠道接口标准 §4.1."""
    # MUST 字段
    message_type: str = "text"
    content: dict = field(default_factory=dict)
    recipients: Any = field(default_factory=Recipients)

    # 自动填充
    message_id: str = field(default_factory=lambda: _new_id("msg"))
    trace_id: str = field(default_factory=lambda: _new_id("tr"))
    created_at: str = field(default_factory=_now_iso)

    # 可选
    priority: str = "normal"
    idempotency_key: Optional[str] = None
    sender: dict = field(default_factory=dict)   # {skill_id, agent}
    schedule: dict = field(default_factory=dict)
    reply_to: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # 校验
        if self.message_type not in VALID_MESSAGE_TYPES:
            raise ValueError(
                f"invalid message_type: {self.message_type} "
                f"(allowed: {sorted(VALID_MESSAGE_TYPES)})"
            )
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(
                f"invalid priority: {self.priority} "
                f"(allowed: {sorted(VALID_PRIORITIES)})"
            )
        # 收件人归一化
        if not isinstance(self.recipients, Recipients):
            self.recipients = Recipients.parse(self.recipients)
        # 默认幂等键 = message_id（强制不会重复）
        if self.idempotency_key is None:
            self.idempotency_key = self.message_id

    def for_channel(self, channel: str) -> "OutboundMessage":
        """复制一份只针对单渠道的消息（路由器拆分用）."""
        copy = OutboundMessage(
            message_type=self.message_type,
            content=dict(self.content),
            recipients=Recipients(
                channels=[channel],
                targets=list(self.recipients.targets),
            ),
            message_id=f"{self.message_id}.{channel}",
            trace_id=self.trace_id,
            created_at=self.created_at,
            priority=self.priority,
            # 幂等性按渠道独立
            idempotency_key=f"{self.idempotency_key}:{channel}",
            sender=dict(self.sender),
            schedule=dict(self.schedule),
            reply_to=self.reply_to,
            metadata=dict(self.metadata),
        )
        return copy

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "trace_id": self.trace_id,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "message_type": self.message_type,
            "priority": self.priority,
            "sender": self.sender,
            "content": self.content,
            "recipients": {
                "channels": self.recipients.channels,
                "targets": [
                    {"type": t.type, "id": t.id, "thread_id": t.thread_id}
                    for t in self.recipients.targets
                ],
            },
            "schedule": self.schedule,
            "reply_to": self.reply_to,
            "metadata": self.metadata,
        }


# ───────────── 入站消息（contract，先占位） ─────────────

@dataclass
class InboundMessage:
    message_id: str
    received_at: str
    channel: str
    sender: dict           # {type, id, name, attributes}
    chat: dict             # {type, id, thread_id, name}
    message_type: str
    content: dict
    mentions: list = field(default_factory=list)
    reply_to: Optional[str] = None
    attachments: list = field(default_factory=list)
