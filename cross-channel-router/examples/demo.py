"""
demo.py — Cross Channel Router 端到端演示

跑法:
    cd skills/cross_channel_router
    python3 examples/demo.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# 演示走 fallback，清空环境变量
for v in ("FEISHU_APP_ID", "FEISHU_APP_SECRET",
          "WECOM_CORP_ID", "WECOM_CORP_SECRET"):
    os.environ.pop(v, None)

from src import CrossChannelRouter, OutboundMessage  # noqa: E402

router = CrossChannelRouter.from_yaml(str(HERE / "routing.yaml"))

print("━" * 60)
print("场景 1: 普通通知（normal 优先级 → console）")
print("━" * 60)
result = router.send(OutboundMessage(
    message_type="text",
    priority="normal",
    content={"text": "今日工单已全部处理完成。"},
    recipients={"targets": [{"type": "user", "id": "ou_normal_user"}]},
))
print(f"\n→ status={result.status} delivered={[d.channel for d in result.delivered]}\n")

print("━" * 60)
print("场景 2: 紧急告警（critical → 飞书 + 企微 双通道）")
print("━" * 60)
result = router.send(OutboundMessage(
    message_type="card",
    priority="critical",
    content={
        "title": "🚨 网点 A 设备异常",
        "body": "**故障类型**: 路由器掉线\n**影响范围**: 50+ 台终端\n**预计恢复**: 30min",
        "buttons": [
            {"label": "查看详情", "url": "https://example.com/incident/1"},
            {"label": "确认接收"},
            {"label": "升级"},
        ],
    },
    recipients={"targets": [
        {"type": "user", "id": "ou_dispatcher"},
        {"type": "group", "id": "oc_ops_team"},
    ]},
    metadata={"source_skill": "alert_engine"},
))
print(f"\n→ status={result.status}")
for d in result.delivered:
    print(f"   • [{d.channel}] {d.status} (parts={d.parts}, "
          f"{d.duration_ms}ms) "
          f"{('err='+str(d.error_code)) if d.error_code else ''}")

print()
print("━" * 60)
print("场景 3: 长文本自动分片（演示降级矩阵）")
print("━" * 60)
long = "第" + "X" * 5000 + "段"
result = router.send(OutboundMessage(
    message_type="text",
    priority="normal",
    content={"text": long},
    recipients={"channels": ["wecom"],   # WeCom max_text_length=2048
                "targets": [{"type": "user", "id": "ou_wc"}]},
))
print(f"\n→ status={result.status}")
for d in result.delivered:
    print(f"   • [{d.channel}] {d.status} parts={d.parts}")

print()
print("━" * 60)
print("场景 4: 幂等性（重发同一消息）")
print("━" * 60)
m = OutboundMessage(
    message_type="text",
    content={"text": "幂等测试"},
    idempotency_key="demo-idem-001",
    recipients={"channels": ["console"],
                "targets": [{"type": "user", "id": "ou_idem"}]},
)
r1 = router.send(m)
r2 = router.send(m)
print(f"   first  send: status={r1.status} channel={r1.delivered[0].channel}")
print(f"   second send: status={r2.status} channel={r2.delivered[0].channel} "
      f"err={r2.delivered[0].error_code}")

print()
print("━" * 60)
print("审计日志路径: /tmp/router-demo-audit.jsonl")
print("━" * 60)
