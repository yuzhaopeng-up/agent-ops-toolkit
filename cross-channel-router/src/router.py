"""
src.router — 主路由器

把 OutboundMessage 路由到一个或多个 ChannelAdapter，处理：
- 路由决策（RoutingEngine）
- 幂等性（IdempotencyStore）
- 降级矩阵（degrade）
- 审计日志（AuditLogger）
- 多渠道汇总返回
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .adapter import ChannelAdapter, ConsoleAdapter, FeishuAdapter, WeComAdapter
from .audit import AuditLogger, IdempotencyStore
from .degradation import degrade
from .errors import IDEMPOTENT_RETURN, SendResult
from .message import OutboundMessage
from .routing import RoutingEngine


@dataclass
class ChannelDelivery:
    channel: str
    status: str
    channel_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    parts: int = 1     # 降级分片数


@dataclass
class RouteResult:
    status: str        # "sent" | "partial" | "failed"
    delivered: list[ChannelDelivery] = field(default_factory=list)
    audit_id: Optional[str] = None
    trace_id: Optional[str] = None
    total_duration_ms: int = 0


class CrossChannelRouter:
    """把消息根据规则发到多个渠道."""

    def __init__(
        self,
        adapters: dict[str, ChannelAdapter],
        engine: Optional[RoutingEngine] = None,
        audit: Optional[AuditLogger] = None,
        idempotency: Optional[IdempotencyStore] = None,
    ):
        self.adapters = adapters
        self.engine = engine or RoutingEngine()
        self.audit = audit or AuditLogger()
        self.idempotency = idempotency or IdempotencyStore()

    # ─────────────── public API ───────────────

    def send(self, message: OutboundMessage) -> RouteResult:
        t0 = time.time()
        # 0) 幂等
        if self.idempotency.seen(message.idempotency_key or message.message_id):
            self.audit.log(
                "idempotent_skip",
                trace_id=message.trace_id,
                message_id=message.message_id,
                idempotency_key=message.idempotency_key,
            )
            return RouteResult(
                status="sent",
                delivered=[ChannelDelivery(
                    channel="<idempotent>",
                    status="idempotent",
                    error_code=IDEMPOTENT_RETURN,
                    error_message="message already sent",
                )],
                trace_id=message.trace_id,
                audit_id=None,
                total_duration_ms=int((time.time() - t0) * 1000),
            )

        # 1) 路由决策
        channels = self.engine.decide(message)
        self.audit.log(
            "route_decided",
            trace_id=message.trace_id,
            message_id=message.message_id,
            priority=message.priority,
            message_type=message.message_type,
            channels=channels,
            source=message.metadata.get("source_skill"),
        )

        deliveries: list[ChannelDelivery] = []

        # 2) 逐渠道发送
        for ch in channels:
            adapter = self.adapters.get(ch)
            if adapter is None:
                deliveries.append(ChannelDelivery(
                    channel=ch, status="failed",
                    error_code="CHANNEL_UNAVAILABLE",
                    error_message=f"adapter '{ch}' not registered",
                ))
                self.audit.log(
                    "adapter_missing",
                    trace_id=message.trace_id,
                    channel=ch,
                )
                continue

            # 2.1 拷贝并按渠道降级
            single = message.for_channel(ch)
            caps = adapter.capabilities()
            parts = degrade(single, caps)

            # 2.2 发送（降级后可能多片）
            success = 0
            last_err = None
            ch_msg_ids = []
            t_ch = time.time()
            for part in parts:
                try:
                    res: SendResult = adapter.send(part)
                except Exception as e:                       # noqa: BLE001
                    res = SendResult(
                        status="failed", channel=ch,
                        error_code="ADAPTER_EXCEPTION",
                        error_message=str(e),
                    )
                if res.status in ("sent", "queued"):
                    success += 1
                    if res.channel_message_id:
                        ch_msg_ids.append(res.channel_message_id)
                else:
                    last_err = (res.error_code, res.error_message)
                self.audit.log(
                    "channel_send",
                    trace_id=message.trace_id,
                    message_id=part.message_id,
                    channel=ch,
                    status=res.status,
                    error_code=res.error_code,
                    duration_ms=res.duration_ms,
                )

            duration_ms = int((time.time() - t_ch) * 1000)
            if success == len(parts):
                deliveries.append(ChannelDelivery(
                    channel=ch, status="sent",
                    channel_message_id=",".join(ch_msg_ids) or None,
                    duration_ms=duration_ms, parts=len(parts),
                ))
            elif success > 0:
                deliveries.append(ChannelDelivery(
                    channel=ch, status="partial",
                    error_code=last_err[0] if last_err else None,
                    error_message=last_err[1] if last_err else None,
                    duration_ms=duration_ms, parts=len(parts),
                ))
            else:
                deliveries.append(ChannelDelivery(
                    channel=ch, status="failed",
                    error_code=last_err[0] if last_err else None,
                    error_message=last_err[1] if last_err else None,
                    duration_ms=duration_ms, parts=len(parts),
                ))

        # 3) 汇总
        statuses = {d.status for d in deliveries}
        if statuses == {"sent"}:
            overall = "sent"
        elif "sent" in statuses or "partial" in statuses:
            overall = "partial"
        else:
            overall = "failed"

        result = RouteResult(
            status=overall,
            delivered=deliveries,
            trace_id=message.trace_id,
            audit_id=message.message_id,
            total_duration_ms=int((time.time() - t0) * 1000),
        )
        self.audit.log(
            "route_done",
            trace_id=message.trace_id,
            status=overall,
            channels=[d.channel for d in deliveries],
            duration_ms=result.total_duration_ms,
        )
        return result

    # ─────────────── factories ───────────────

    @classmethod
    def from_config(cls, cfg: dict) -> "CrossChannelRouter":
        """通过 dict 构建 router."""
        adapters: dict[str, ChannelAdapter] = {}
        for ch, opts in (cfg.get("adapters") or {}).items():
            opts = opts or {}
            adapters[ch] = _build_adapter(ch, opts)

        # default fallback
        if "console" not in adapters:
            adapters["console"] = ConsoleAdapter()

        engine = RoutingEngine.from_dict({"rules": cfg.get("rules", [])})
        audit = AuditLogger(cfg.get("audit_log_path"))
        return cls(adapters=adapters, engine=engine, audit=audit)

    @classmethod
    def from_yaml(cls, path: str) -> "CrossChannelRouter":
        try:
            import yaml
        except ImportError as e:
            raise RuntimeError("PyYAML required for from_yaml") from e
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_config(cfg)


def _build_adapter(channel: str, opts: dict) -> ChannelAdapter:
    if channel == "console":
        return ConsoleAdapter()
    if channel == "feishu":
        return FeishuAdapter(
            app_id=opts.get("app_id"),
            app_secret=opts.get("app_secret"),
        )
    if channel == "wecom":
        return WeComAdapter(
            corp_id=opts.get("corp_id"),
            corp_secret=opts.get("corp_secret"),
            agent_id=opts.get("agent_id"),
        )
    raise ValueError(f"unknown channel: {channel}")
