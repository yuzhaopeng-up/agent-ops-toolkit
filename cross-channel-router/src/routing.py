"""
src.routing — 路由引擎

按规则把 OutboundMessage 决定送到哪些 channels。
规则示例 (YAML):

  rules:
    - match:
        priority: critical
      route:
        channels: [feishu, wecom]
    - match:
        source_skill: alert_engine
        priority: [high, critical]
      route:
        channels: [feishu]
    - match:                            # 兜底
        any: true
      route:
        channels: [console]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .message import OutboundMessage


@dataclass
class RoutingRule:
    match: dict
    route: dict

    def matches(self, m: OutboundMessage) -> bool:
        cond = self.match or {}
        if cond.get("any"):
            return True
        # priority
        if "priority" in cond:
            allowed = cond["priority"]
            if isinstance(allowed, str):
                allowed = [allowed]
            if m.priority not in allowed:
                return False
        # source_skill
        if "source_skill" in cond:
            allowed = cond["source_skill"]
            if isinstance(allowed, str):
                allowed = [allowed]
            src = m.metadata.get("source_skill") or m.sender.get("skill_id")
            if src not in allowed:
                return False
        # message_type
        if "message_type" in cond:
            allowed = cond["message_type"]
            if isinstance(allowed, str):
                allowed = [allowed]
            if m.message_type not in allowed:
                return False
        # tag (metadata.tags)
        if "tag" in cond:
            allowed = cond["tag"]
            if isinstance(allowed, str):
                allowed = [allowed]
            tags = m.metadata.get("tags") or []
            if not any(t in tags for t in allowed):
                return False
        return True


class RoutingEngine:
    """按 first-match 选规则。"""

    def __init__(self, rules: Optional[list[dict]] = None):
        self.rules = [
            RoutingRule(match=r.get("match") or {}, route=r.get("route") or {})
            for r in (rules or [])
        ]

    def decide(self, m: OutboundMessage) -> list[str]:
        # 1) 显式 recipients.channels 优先
        if m.recipients.channels:
            return list(m.recipients.channels)
        # 2) 规则匹配
        for rule in self.rules:
            if rule.matches(m):
                return list(rule.route.get("channels") or [])
        # 3) 兜底
        return ["console"]

    @classmethod
    def from_dict(cls, cfg: dict) -> "RoutingEngine":
        return cls(rules=cfg.get("rules", []))
