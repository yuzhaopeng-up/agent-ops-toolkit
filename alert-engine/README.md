# Alert Engine

## Problem Statement

L3 Skills that send alerts (stock-assistant, daily-report, etc.) each implement **their own alerting logic**:
- stock-assistant: Threshold-based alerts with cooldown timers, price state machines, trailing stops
- daily-report: Scheduled push (no real-time alerting)
- financial-intelligence: Unknown alert patterns

This means:
1. No unified alerting framework across all Skills
2. No escalation chains (alert → SMS → call → manager)
3. No alert aggregation (5 stock alerts → 1 consolidated digest)
4. No alert history / audit trail
5. No alert fatigue management (throttling, deduplication)

## Solution: L2 Alert Engine

A reusable L2 Skill that provides **generic alerting primitives** that any L3 Skill can use.

### Design

```python
class AlertEngine:
    """
    L2 Building Block: Generic Alert Engine
    
    Usage:
        engine = AlertEngine(
            policy=AlertPolicy(
                cooldown=timedelta(minutes=10),
                dedup_window=timedelta(hours=1),
                escalation_chain=["feishu", "wecom", "sms"],
                max_daily_alerts=50
            )
        )
        
        # Register a source
        source = engine.register_source(
            name="stock-monitor",
            owner="ou_xxx",
            channels=["feishu", "wecom"]
        )
        
        # Trigger an alert
        alert = await source.trigger(
            severity="warning",  # info, warning, critical, emergency
            title="AAPL up 3%",
            body="...",
            metadata={"stock": "AAPL", "change_pct": 3.0}
        )
        
        # Engine handles:
        # - Cooldown check (don't spam)
        # - Deduplication (same alert in window? suppress)
        # - Aggregation (batch 5 alerts into 1 digest)
        # - Escalation (if unread after 5min, escalate)
        # - Throttling (max 50 alerts/day)
        # - Audit logging (all alerts logged)
    """
    
    class AlertPolicy:
        cooldown: timedelta
        dedup_window: timedelta
        escalation_chain: List[str]  # channel names
        max_daily_alerts: int
        digest_mode: bool  # aggregate alerts into digests
        digest_interval: timedelta
        
    class AlertSource:
        name: str
        owner: str
        channels: List[str]
        alert_count_today: int
        last_alert: datetime
        
    async def trigger(self, source: AlertSource, 
                     severity: str, title: str, body: str,
                     metadata: dict = None) -> AlertResult:
        """Trigger an alert with full policy enforcement."""
        ...
    
    async def register_source(self, name: str, owner: str,
                             channels: List[str]) -> AlertSource:
        """Register a new alert source."""
        ...
    
    async def get_history(self, source: str = None,
                         since: datetime = None,
                         severity: str = None) -> List[AlertRecord]:
        """Get alert history for audit/debugging."""
        ...
    
    async def create_digest(self, source: str = None,
                           interval: timedelta = None) -> Digest:
        """Create a digest of recent alerts."""
        ...
```

### Integration with L3 Skills

```python
# In stock-assistant/monitor.py (refactored)
from skill_patterns.alert_engine import AlertEngine

engine = AlertEngine.from_config(config["alert_policy"])
source = engine.register_source(
    name="stock-monitor",
    owner=config["user_id"],
    channels=config["channels"]
)

# Instead of:
# if time_since_last_alert > cooldown:
#     send_feishu_message(user_id, card)

# Use:
await source.trigger(
    severity="warning" if abs(change_pct) < 5 else "critical",
    title=f"{stock.name} {change_pct:+.1f}%",
    body=generate_alert_body(stock, alert),
    metadata={"stock": stock.code, "change_pct": change_pct}
)
```

### Benefits

| Benefit | Impact |
|---------|--------|
| Alert Fatigue Prevention | Cooldown, dedup, throttling prevent spam |
| Escalation Chains | Unread alerts auto-escalate to higher channels |
| Audit Trail | All alerts logged with metadata for compliance |
| Aggregation | Multiple small alerts → 1 consolidated digest |
| Channel Agnostic | Uses Cross-Channel Router for delivery |
| Configurable | Policies per source, per user, per severity |

## Implementation Priority

**P2** — High impact for operational Skills (stock-assistant, daily-report). Would significantly improve user experience by reducing alert fatigue and adding professionalism.
