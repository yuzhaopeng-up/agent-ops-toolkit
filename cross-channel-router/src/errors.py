"""
src.errors — 错误码 (与 IM 渠道接口标准 §8 一致)
"""

from dataclasses import dataclass
from typing import Optional


class ChannelError(Exception):
    """适配器层错误。"""

    def __init__(self, code: str, message: str, retry_after: Optional[int] = None):
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(f"[{code}] {message}")


# 错误码常量
RATE_LIMITED = "RATE_LIMITED"
INVALID_RECIPIENT = "INVALID_RECIPIENT"
PERMISSION_DENIED = "PERMISSION_DENIED"
CONTENT_REJECTED = "CONTENT_REJECTED"
MESSAGE_TOO_LARGE = "MESSAGE_TOO_LARGE"
CHANNEL_UNAVAILABLE = "CHANNEL_UNAVAILABLE"
AUTH_EXPIRED = "AUTH_EXPIRED"
IDEMPOTENT_RETURN = "IDEMPOTENT_RETURN"

ALL_ERROR_CODES = {
    RATE_LIMITED, INVALID_RECIPIENT, PERMISSION_DENIED, CONTENT_REJECTED,
    MESSAGE_TOO_LARGE, CHANNEL_UNAVAILABLE, AUTH_EXPIRED, IDEMPOTENT_RETURN,
}


@dataclass
class SendResult:
    """适配器 send() 的返回，对应 IM 渠道接口标准 §5.1."""
    status: str                          # "sent" | "queued" | "failed" | "idempotent"
    channel: str
    channel_message_id: Optional[str] = None
    sent_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_after: Optional[int] = None
    duration_ms: Optional[int] = None
