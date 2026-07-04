"""
src.template — 轻量 Jinja2-like 模板渲染器

支持:
  {{ var }}            —— 变量插值（支持 a.b.c 链式）
  {{ var | filter }}   —— 过滤器（默认 default/upper/lower/round/format/join）
  {% if expr %}        —— 条件
  {% else %}
  {% endif %}
  {% for x in xs %}    —— 循环（支持 loop.index, loop.first, loop.last）
  {% endfor %}

不支持子模板/继承/include — 保持简单足够内置 6 模板使用。
生产环境建议换 jinja2 包。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional


# ────────── Filters ──────────

DEFAULT_FILTERS: dict[str, Callable[..., Any]] = {
    "default": lambda v, default="": default if v in (None, "") else v,
    "upper": lambda v: str(v).upper() if v is not None else "",
    "lower": lambda v: str(v).lower() if v is not None else "",
    "round": lambda v, n=0: round(float(v), int(n)) if v is not None else "",
    "format": lambda v, fmt: format(v, fmt) if v is not None else "",
    "join": lambda v, sep=", ": sep.join(str(x) for x in (v or [])),
    "len": lambda v: len(v or []),
    "or": lambda v, alt: v if v else alt,
}


def _resolve(expr: str, ctx: dict) -> Any:
    """解析 a.b.c 或字面量(常量数字/字符串)."""
    expr = expr.strip()
    # 字符串字面量
    if (expr.startswith('"') and expr.endswith('"')) \
            or (expr.startswith("'") and expr.endswith("'")):
        return expr[1:-1]
    # 数字字面量
    if re.fullmatch(r"-?\d+", expr):
        return int(expr)
    if re.fullmatch(r"-?\d+\.\d+", expr):
        return float(expr)
    if expr in ("true", "True"):
        return True
    if expr in ("false", "False"):
        return False
    if expr in ("none", "None", "null"):
        return None
    # 变量路径
    cur: Any = ctx
    for seg in expr.split("."):
        if isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            cur = getattr(cur, seg, None)
        if cur is None:
            return None
    return cur


def _apply_filters(value: Any, filter_chain: str, ctx: dict,
                   filters: dict) -> Any:
    """value | filter1 | filter2(arg)."""
    if not filter_chain.strip():
        return value
    for spec in filter_chain.split("|"):
        spec = spec.strip()
        if not spec:
            continue
        # filter or filter(args)
        m = re.match(r"^(\w+)(?:\((.*)\))?$", spec)
        if not m:
            continue
        fname, args_str = m.group(1), m.group(2) or ""
        fn = filters.get(fname)
        if fn is None:
            continue
        args = []
        if args_str:
            for arg in args_str.split(","):
                args.append(_resolve(arg.strip(), ctx))
        value = fn(value, *args)
    return value


def _eval_expr(expr: str, ctx: dict, filters: dict) -> Any:
    """解析 var | filter1 | filter2."""
    if "|" in expr:
        var_part, filter_part = expr.split("|", 1)
    else:
        var_part, filter_part = expr, ""
    val = _resolve(var_part.strip(), ctx)
    return _apply_filters(val, filter_part, ctx, filters)


# ────────── Tokenizer ──────────

TOKEN_RE = re.compile(
    r"(?P<expr>\{\{\s*.+?\s*\}\})|"
    r"(?P<tag>\{%\s*.+?\s*%\})",
    re.DOTALL,
)


@dataclass
class Token:
    kind: str        # "text" | "expr" | "tag"
    value: str


def _tokenize(template: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    for m in TOKEN_RE.finditer(template):
        if m.start() > pos:
            tokens.append(Token("text", template[pos:m.start()]))
        if m.group("expr"):
            tokens.append(Token("expr", m.group("expr")[2:-2].strip()))
        elif m.group("tag"):
            tokens.append(Token("tag", m.group("tag")[2:-2].strip()))
        pos = m.end()
    if pos < len(template):
        tokens.append(Token("text", template[pos:]))
    return tokens


# ────────── Renderer ──────────

class TemplateRenderer:
    """简化版 Jinja2 renderer (足够本 Skill 6 模板使用)."""

    def __init__(self, filters: Optional[dict] = None):
        self.filters = {**DEFAULT_FILTERS, **(filters or {})}

    def render(self, template: str, context: dict) -> str:
        tokens = _tokenize(template)
        out, _ = self._render_block(tokens, 0, context, stop=None)
        return out

    # ── 递归块渲染 ──
    def _render_block(self, tokens: list[Token], idx: int, ctx: dict,
                      stop: Optional[set]) -> tuple[str, int]:
        out = []
        while idx < len(tokens):
            tok = tokens[idx]
            if tok.kind == "text":
                out.append(tok.value)
                idx += 1
            elif tok.kind == "expr":
                val = _eval_expr(tok.value, ctx, self.filters)
                out.append("" if val is None else str(val))
                idx += 1
            elif tok.kind == "tag":
                tag = tok.value
                # stop tag?
                head = tag.split()[0]
                if stop and head in stop:
                    return "".join(out), idx

                if head == "if":
                    cond_expr = tag[2:].strip()
                    val = _eval_expr(cond_expr, ctx, self.filters)
                    truthy = bool(val)

                    # 找 {% else %} 和 {% endif %}
                    if_body, else_body, idx = self._collect_if_else(
                        tokens, idx + 1
                    )
                    if truthy:
                        rendered, _ = self._render_block(
                            if_body, 0, ctx, stop=None
                        )
                    else:
                        rendered, _ = self._render_block(
                            else_body, 0, ctx, stop=None
                        )
                    out.append(rendered)
                elif head == "for":
                    # for x in xs
                    m = re.match(r"^for\s+(\w+)\s+in\s+(.+)$", tag)
                    if not m:
                        idx += 1
                        continue
                    varname, listexpr = m.group(1), m.group(2).strip()
                    items = _eval_expr(listexpr, ctx, self.filters) or []
                    body, idx = self._collect_loop(tokens, idx + 1)
                    n = len(items)
                    for i, item in enumerate(items):
                        loop_ctx = {
                            **ctx, varname: item,
                            "loop": {"index": i + 1,
                                     "index0": i,
                                     "first": i == 0,
                                     "last": i == n - 1,
                                     "length": n},
                        }
                        rendered, _ = self._render_block(
                            body, 0, loop_ctx, stop=None
                        )
                        out.append(rendered)
                else:
                    # 未知标签按字面输出，便于调试
                    idx += 1
        return "".join(out), idx

    def _collect_if_else(self, tokens: list[Token], idx: int):
        """收集 if/else 主体和分支体，返回 (if_body, else_body, new_idx)."""
        if_body: list[Token] = []
        else_body: list[Token] = []
        in_else = False
        depth = 0
        while idx < len(tokens):
            tok = tokens[idx]
            if tok.kind == "tag":
                head = tok.value.split()[0]
                if head == "if":
                    depth += 1
                elif head == "endif":
                    if depth == 0:
                        return if_body, else_body, idx + 1
                    depth -= 1
                elif head == "else" and depth == 0:
                    in_else = True
                    idx += 1
                    continue
            (else_body if in_else else if_body).append(tok)
            idx += 1
        return if_body, else_body, idx  # unterminated

    def _collect_loop(self, tokens: list[Token], idx: int):
        body: list[Token] = []
        depth = 0
        while idx < len(tokens):
            tok = tokens[idx]
            if tok.kind == "tag":
                head = tok.value.split()[0]
                if head == "for":
                    depth += 1
                elif head == "endfor":
                    if depth == 0:
                        return body, idx + 1
                    depth -= 1
            body.append(tok)
            idx += 1
        return body, idx
