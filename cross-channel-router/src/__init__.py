"""Cross Channel Router — L2 reference implementation."""
from .adapter import ChannelAdapter, ConsoleAdapter, FeishuAdapter, WeComAdapter
from .audit import AuditLogger, IdempotencyStore
from .degradation import degrade
from .errors import ChannelError, SendResult
from .message import InboundMessage, OutboundMessage, Recipient, Recipients
from .router import ChannelDelivery, CrossChannelRouter, RouteResult
from .routing import RoutingEngine, RoutingRule

__version__ = "1.0.0"
__all__ = [
    "ChannelAdapter", "ConsoleAdapter", "FeishuAdapter", "WeComAdapter",
    "AuditLogger", "IdempotencyStore",
    "degrade",
    "ChannelError", "SendResult",
    "InboundMessage", "OutboundMessage", "Recipient", "Recipients",
    "ChannelDelivery", "CrossChannelRouter", "RouteResult",
    "RoutingEngine", "RoutingRule",
]
