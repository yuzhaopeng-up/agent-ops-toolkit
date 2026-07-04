---
name: cross_channel_router
description: "L2 跨渠道路由器 reference 实现：基于统一 OutboundMessage 模型，按规则路由到多渠道适配器（feishu/wecom/console），支持降级矩阵、幂等性、审计日志。"
version: 1.0.0
author: BetaAgent
license: MIT
layer: L2
capability_domain: [C07, C09]
industry: universal
metadata:
  beta-agent:
    tags: [router, multi-channel, im, adapter]
    related_skills: [alert_engine, taskflow_patterns, unified_document_pipeline]
  reference_impl: true
  blueprint_doc: 00-methodology/skill-architecture/l2-patterns/cross-channel-router.md
prerequisites:
  commands: [python3]
---

# Cross Channel Router (L2 Reference 实现)

> 把"哪个渠道发"从业务 Skill 里抽离出来，让 L3/L4 只关心"发什么"。

## 核心能力

| 能力 | 说明 |
|------|------|
| 统一消息模型 | `OutboundMessage` 与 [IM 渠道接口标准](../../00-methodology/skill-architecture/governance/im-channel-interface-spec.md) v1.0 一致 |
| 路由决策引擎 | YAML/字典配置规则，按 priority/source_skill/time_window 路由 |
| 渠道适配器框架 | 抽象 `ChannelAdapter` 基类 + Feishu/WeCom/Console 三个 ref 适配器 |
| 降级矩阵 | 渠道不支持的能力自动降级（卡片→纯文本+链接、按钮→编号、长文本→分片） |
| 幂等性 | 相同 `idempotency_key` 不重复发送 |
| 审计日志 | 每次发送记录 sender/recipient/message_id/trace_id/duration |
| 可观测 | trace_id 串联整条调用链 |

## 输入 (OutboundMessage)

见 [IM 渠道接口标准 §4.1](../../00-methodology/skill-architecture/governance/im-channel-interface-spec.md#41-出站消息-outboundmessage--must)。

## 输出 (RouteResult)

```python
@dataclass
class RouteResult:
    status: str                  # "sent" | "partial" | "failed"
    delivered: list[ChannelDelivery]   # 各渠道送达详情
    audit_id: str
    trace_id: str
    total_duration_ms: int
```

## 使用示例

```python
from src.router import CrossChannelRouter
from src.message import OutboundMessage

router = CrossChannelRouter.from_config("config/routing.yaml")

result = router.send(OutboundMessage(
    message_type="card",
    priority="high",
    content={"title": "异常告警", "body": "..."},
    recipients={"channels": ["feishu", "wecom"], "targets": ["@duty"]},
    metadata={"source_skill": "alert_engine"},
))

print(result.status, result.delivered)
```

## 架构

```
[Skill] ──▶ OutboundMessage ──▶ Router
                                  │
                                  ├─ RoutingEngine: 按规则决定 channels
                                  ├─ Capabilities check: 不支持 → 降级
                                  ├─ Idempotency check: 已发过 → 直接返回
                                  └─ ChannelAdapter.send() → 真实渠道
                                                              │
                                                              ▼
                                                          Audit log
```

## 已实现的渠道适配器

| Adapter | 状态 | 说明 |
|---------|------|------|
| `ConsoleAdapter` | ✅ 完整 | 日志输出，不真实发送，用于测试/降级兜底 |
| `FeishuAdapter` | ✅ live | 真实发送 (`http_clients.FeishuClient`)；缺 token 时降级 fallback (status=queued) |
| `WeComAdapter` | ✅ live | 真实发送 (`http_clients.WeComClient`)；缺 token 时降级 fallback |

## 测试

```bash
cd skills/cross_channel_router
python3 -m pytest tests/ -v
```

## 与蓝图的对应

| 蓝图节 | 实现位置 |
|--------|----------|
| §3 五个核心组件 | `src/router.py` 中的 `CrossChannelRouter` |
| §4 OutboundMessage / InboundMessage | `src/message.py` |
| §5 适配器接口契约 | `src/adapter.py` 抽象基类 |
| §6 降级矩阵 | `src/degradation.py` |
| §7 安全与合规 | `src/audit.py` 审计日志，`secrets/` 占位 |
| §8 错误码规范 | `src/errors.py` |

## 已知限制（Reference 范畴）

1. 真实 Feishu/WeCom 发送需要在 `secrets/` 下提供 token（demo 用 ConsoleAdapter）
2. 频控仅本地内存计数，多实例需换成 Redis
3. 升级路径（escalation）由 alert_engine 实现，本 Skill 仅做单次路由
