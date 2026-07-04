"""
src.degradation — 降级矩阵

当目标渠道不支持某能力时，自动转换 OutboundMessage：
  - card → text + url（卡片不支持 → 拼接标题/正文/链接）
  - buttons → 编号列表（"1. 同意 2. 拒绝 3. 转人工"）
  - 长文本 → 分片（超过 max_text_length 切多条，加 1/N 标记）
  - markdown=full → markdown=basic 时，剥离不支持的标记
"""
from __future__ import annotations

import re
from copy import deepcopy

from .message import OutboundMessage


def degrade(message: OutboundMessage, capabilities: dict) -> list[OutboundMessage]:
    """根据 capabilities 把 message 降级为兼容版本，可能拆成多条."""
    supports = (capabilities or {}).get("supports", {})
    msgs = [deepcopy(message)]

    # 1) card → text 降级（如果 card 但渠道不支持卡片）
    if message.message_type in ("card", "notify", "alert", "report") \
            and not supports.get("card", False):
        msgs = [_card_to_text(m) for m in msgs]

    # 2) buttons 降级
    if not supports.get("buttons", False):
        msgs = [_drop_buttons(m) for m in msgs]
    else:
        max_btn = supports.get("max_buttons_per_card", 99)
        msgs = [_cap_buttons(m, max_btn) for m in msgs]

    # 3) 长文本分片
    max_len = supports.get("max_text_length", 100000)
    new_msgs = []
    for m in msgs:
        new_msgs.extend(_split_long_text(m, max_len))
    msgs = new_msgs

    # 4) markdown 降级
    md_support = supports.get("markdown", "full")
    if md_support != "full":
        msgs = [_strip_markdown(m, md_support) for m in msgs]

    return msgs


def _card_to_text(m: OutboundMessage) -> OutboundMessage:
    c = m.content
    parts = []
    if c.get("title"):
        parts.append(f"【{c['title']}】")
    if c.get("body"):
        parts.append(c["body"])
    if c.get("url"):
        parts.append(f"\n详情: {c['url']}")
    btns = c.get("buttons") or []
    if btns:
        parts.append("\n操作:")
        for i, b in enumerate(btns, 1):
            label = b.get("label") or b.get("text") or str(b)
            url = b.get("url") or b.get("action_url")
            if url:
                parts.append(f"  {i}. {label} → {url}")
            else:
                parts.append(f"  {i}. {label} (回复编号)")
    text = "\n".join(parts)
    m.message_type = "text"
    m.content = {"text": text}
    m.metadata.setdefault("degraded_from", []).append("card→text")
    return m


def _drop_buttons(m: OutboundMessage) -> OutboundMessage:
    if "buttons" in m.content and m.content["buttons"]:
        btns = m.content["buttons"]
        body = m.content.get("body", "")
        body += "\n\n操作:\n"
        for i, b in enumerate(btns, 1):
            body += f"  {i}. {b.get('label') or b.get('text') or str(b)}\n"
        m.content["body"] = body.rstrip()
        m.content.pop("buttons", None)
        m.metadata.setdefault("degraded_from", []).append("buttons→inline")
    return m


def _cap_buttons(m: OutboundMessage, max_btn: int) -> OutboundMessage:
    btns = m.content.get("buttons") or []
    if len(btns) > max_btn:
        m.content["buttons"] = btns[:max_btn]
        # 多余的按钮转成正文末尾
        extra = btns[max_btn:]
        body = m.content.get("body", "")
        body += "\n\n更多操作:\n"
        for i, b in enumerate(extra, max_btn + 1):
            body += f"  {i}. {b.get('label') or b.get('text') or str(b)}\n"
        m.content["body"] = body.rstrip()
        m.metadata.setdefault("degraded_from", []).append(
            f"buttons[{len(btns)}]→cap[{max_btn}]"
        )
    return m


def _split_long_text(m: OutboundMessage, max_len: int) -> list[OutboundMessage]:
    """文本/卡片正文超长时分片."""
    body = m.content.get("text") or m.content.get("body") or ""
    if len(body) <= max_len:
        return [m]

    parts = []
    chunk_size = max_len - 20  # 留出 (i/N) 标记空间
    chunks = [body[i:i + chunk_size] for i in range(0, len(body), chunk_size)]
    n = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        copy = deepcopy(m)
        marker = f"\n[{i}/{n}]"
        if "text" in copy.content:
            copy.content["text"] = chunk + marker
        else:
            copy.content["body"] = chunk + marker
        copy.message_id = f"{m.message_id}.p{i}"
        copy.idempotency_key = f"{m.idempotency_key}:p{i}"
        copy.metadata.setdefault("degraded_from", []).append(f"split[{i}/{n}]")
        parts.append(copy)
    return parts


# 简单的 markdown 降级映射
_MD_FULL_TO_BASIC = [
    (re.compile(r"^### (.+)$", re.M), r"\1"),
    (re.compile(r"^## (.+)$", re.M), r"\1"),
    (re.compile(r"^# (.+)$", re.M), r"\1"),
    (re.compile(r"~~([^~]+)~~"), r"\1"),       # 删除线
    (re.compile(r"!\[[^\]]*\]\([^)]+\)"), ""), # 图片
]

_MD_BASIC_TO_NONE = [
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"\*([^*]+)\*"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r"\1 (\2)"),
]


def _strip_markdown(m: OutboundMessage, level: str) -> OutboundMessage:
    body = m.content.get("text") or m.content.get("body") or ""
    if not body:
        return m
    if level == "basic":
        for pat, repl in _MD_FULL_TO_BASIC:
            body = pat.sub(repl, body)
    elif level == "none":
        for pat, repl in _MD_FULL_TO_BASIC + _MD_BASIC_TO_NONE:
            body = pat.sub(repl, body)
    if "text" in m.content:
        m.content["text"] = body
    else:
        m.content["body"] = body
    m.metadata.setdefault("degraded_from", []).append(f"md→{level}")
    return m
