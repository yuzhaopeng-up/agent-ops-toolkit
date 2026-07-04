"""
src.http_clients — Feishu/WeCom 真实 HTTP 客户端

零额外依赖：仅用 stdlib (urllib + json)
生产可换为 requests/httpx，但保留同样的接口。

错误码归一化:
  - 飞书 code != 0          → ChannelError(code=映射后的标准码)
  - 企微 errcode != 0       → ChannelError(...)
  - HTTP 网络/超时           → ChannelError(CHANNEL_UNAVAILABLE)
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from .errors import (
    AUTH_EXPIRED, CHANNEL_UNAVAILABLE, CONTENT_REJECTED, INVALID_RECIPIENT,
    MESSAGE_TOO_LARGE, PERMISSION_DENIED, RATE_LIMITED, ChannelError,
)

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────
# 通用 HTTP helpers
# ────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 10  # seconds
USER_AGENT = "agent-ops-cross-channel-router/1.0"


def _http_request(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    payload: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """通用 JSON HTTP 请求.

    返回 parsed JSON dict; 抛 ChannelError on 网络/解析错误.
    """
    body = None
    final_headers = {"User-Agent": USER_AGENT}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        final_headers["Content-Type"] = "application/json; charset=utf-8"
    if headers:
        final_headers.update(headers)

    req = urllib.request.Request(url, data=body, headers=final_headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise ChannelError(
                    code=CHANNEL_UNAVAILABLE,
                    message=f"non-json response: {raw[:200]!r} — {e}",
                ) from e
    except urllib.error.HTTPError as e:
        raise ChannelError(
            code=CHANNEL_UNAVAILABLE,
            message=f"HTTP {e.code} — {e.reason}",
        ) from e
    except urllib.error.URLError as e:
        raise ChannelError(
            code=CHANNEL_UNAVAILABLE,
            message=f"URL error: {e.reason}",
        ) from e
    except TimeoutError as e:
        raise ChannelError(
            code=CHANNEL_UNAVAILABLE,
            message=f"timeout after {timeout}s",
        ) from e


# ────────────────────────────────────────────────────────
# Feishu (Lark) — 真实客户端
# ────────────────────────────────────────────────────────

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

# 飞书错误码 → 标准错误码
# 数据源: https://open.feishu.cn/document/server-docs/im-v1/message/server-side-error-code
# 经 P2-3 实测部分项 (live_e2e.py 触发)
FEISHU_ERROR_MAP = {
    99991663: AUTH_EXPIRED,         # token expired
    99991664: AUTH_EXPIRED,         # invalid token
    10003: AUTH_EXPIRED,            # invalid param (常见于 app credentials 错)
    230001: INVALID_RECIPIENT,      # invalid receive_id
    230002: INVALID_RECIPIENT,
    230015: PERMISSION_DENIED,
    230018: PERMISSION_DENIED,      # bot not in chat
    99991400: CONTENT_REJECTED,     # invalid request
    11000: MESSAGE_TOO_LARGE,
    99991672: RATE_LIMITED,
}


class FeishuClient:
    """飞书 Open Platform 客户端.

    主要能力：
      - tenant_access_token 自动获取与缓存（TTL 20 分钟，提前 60s 续期）
      - send_message: 发送 text/post/interactive(card) 三类消息
      - 错误码归一
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        api_base: str = FEISHU_API_BASE,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not app_id or not app_secret:
            raise ValueError("FeishuClient requires app_id and app_secret")
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._lock = threading.Lock()

    # ─────── token ───────

    def _get_token(self) -> str:
        with self._lock:
            now = time.time()
            if self._token and now < self._token_expires_at - 60:
                return self._token
            data = _http_request(
                "POST",
                f"{self.api_base}/auth/v3/tenant_access_token/internal",
                payload={"app_id": self.app_id,
                         "app_secret": self.app_secret},
                timeout=self.timeout,
            )
            code = data.get("code", -1)
            if code != 0:
                raise ChannelError(
                    code=AUTH_EXPIRED,
                    message=f"tenant_access_token failed code={code} "
                            f"msg={data.get('msg')}",
                )
            self._token = data["tenant_access_token"]
            self._token_expires_at = now + int(data.get("expire", 7200))
            assert self._token is not None
            return self._token

    # ─────── 高层 API ───────

    def send_message(
        self,
        receive_id: str,
        receive_id_type: str = "open_id",
        msg_type: str = "text",
        content: Optional[dict] = None,
    ) -> dict:
        """发送消息. content 是已 dict 化的内容, send_message 会 json.dumps."""
        token = self._get_token()
        url = (f"{self.api_base}/im/v1/messages"
               f"?receive_id_type={receive_id_type}")
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content or {}, ensure_ascii=False),
        }
        data = _http_request(
            "POST", url,
            headers={"Authorization": f"Bearer {token}"},
            payload=payload,
            timeout=self.timeout,
        )
        code = data.get("code", -1)
        if code != 0:
            std = FEISHU_ERROR_MAP.get(code, CONTENT_REJECTED)
            raise ChannelError(
                code=std,
                message=f"feishu send_message code={code} "
                        f"msg={data.get('msg')}",
            )
        return data.get("data", {})


# ────────────────────────────────────────────────────────
# WeCom (企业微信) — 真实客户端
# ────────────────────────────────────────────────────────

WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

WECOM_ERROR_MAP = {
    40014: AUTH_EXPIRED,             # invalid access_token
    42001: AUTH_EXPIRED,             # access_token timed out
    40029: AUTH_EXPIRED,
    60011: PERMISSION_DENIED,
    60020: PERMISSION_DENIED,
    81013: INVALID_RECIPIENT,        # not a member
    45009: RATE_LIMITED,
    45033: RATE_LIMITED,
    45007: MESSAGE_TOO_LARGE,        # voice/file size
}


class WeComClient:
    """企业微信 (Work) 客户端.

    主要能力：
      - access_token 自动获取与缓存
      - send_app_message: text / textcard / news 等
      - 错误码归一
    """

    def __init__(
        self,
        corp_id: str,
        corp_secret: str,
        agent_id: Optional[Any] = None,    # str 或 int 都可
        api_base: str = WECOM_API_BASE,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not corp_id or not corp_secret:
            raise ValueError("WeComClient requires corp_id and corp_secret")
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._lock = threading.Lock()

    def _get_token(self) -> str:
        with self._lock:
            now = time.time()
            if self._token and now < self._token_expires_at - 60:
                return self._token
            url = (f"{self.api_base}/gettoken"
                   f"?corpid={self.corp_id}&corpsecret={self.corp_secret}")
            data = _http_request("GET", url, timeout=self.timeout)
            errcode = data.get("errcode", -1)
            if errcode != 0:
                raise ChannelError(
                    code=AUTH_EXPIRED,
                    message=f"wecom gettoken errcode={errcode} "
                            f"errmsg={data.get('errmsg')}",
                )
            self._token = data["access_token"]
            self._token_expires_at = now + int(data.get("expires_in", 7200))
            assert self._token is not None
            return self._token

    def send_app_message(
        self,
        touser: str = "",
        toparty: str = "",
        totag: str = "",
        msgtype: str = "text",
        content: Optional[dict] = None,
        agentid: Optional[int] = None,
        safe: int = 0,
    ) -> dict:
        """发送企业应用消息.

        参考: https://developer.work.weixin.qq.com/document/path/90236
        """
        token = self._get_token()
        url = f"{self.api_base}/message/send?access_token={token}"
        agent = agentid or self.agent_id
        if agent is None:
            raise ChannelError(
                code=CONTENT_REJECTED,
                message="WeCom send requires agent_id",
            )
        payload = {
            "touser": touser or "",
            "toparty": toparty or "",
            "totag": totag or "",
            "msgtype": msgtype,
            "agentid": int(agent),
            "safe": safe,
            msgtype: content or {},
        }
        data = _http_request(
            "POST", url, payload=payload, timeout=self.timeout,
        )
        errcode = data.get("errcode", -1)
        if errcode != 0:
            std = WECOM_ERROR_MAP.get(errcode, CONTENT_REJECTED)
            raise ChannelError(
                code=std,
                message=f"wecom message/send errcode={errcode} "
                        f"errmsg={data.get('errmsg')}",
            )
        return data
