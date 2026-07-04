# TaskFlow Patterns

## Common Patterns for L2/L3 Skill Orchestration

These patterns use the **TaskFlow** L2 engine to implement reusable multi-step workflows.

---

## Pattern 1: Inbox Triage (Already Exists)

```
[New Messages] → [Classify] → [Business?] → [Post to Slack + Wait] → [Resume]
                          → [Personal?] → [Notify Now]
                          → [Other?] → [Queue for EOD Summary]
```

**Reference**: `taskflow-inbox-triage` Skill (already implemented)

---

## Pattern 2: Scheduled Report Generation

```
[Cron Trigger] → [Gather Data] → [Analyze] → [Generate Report] → [Deliver] → [Archive]
      ↓                ↓              ↓            ↓              ↓            ↓
   08:55 daily    Tavily Search   LLM Summarize  MD-to-PDF     Channel      Git Commit
                  Finance API     Pattern Match  Template      Router     (versioning)
```

**Use Cases**: daily-report, stock-assistant pre-market sentiment, weekly portfolio review

**TaskFlow State**:
```json
{
  "report_type": "daily",
  "gathered_data": { "news": [...], "markets": {...} },
  "analysis_result": { "themes": [...], "risks": [...] },
  "report_path": "/tmp/daily_20260620.pdf",
  "delivery_status": "delivered",
  "archive_commit": "abc123"
}
```

---

## Pattern 3: Alert Escalation Chain

```
[Alert Trigger] → [Send Primary] → [Wait 5min] → [Read?] → [Yes] → [Done]
                                     ↓            ↓
                                  [No]       [Send Secondary]
                                     ↓            ↓
                                  [Wait 10min] → [Read?] → [Yes] → [Done]
                                     ↓            ↓
                                  [No]       [Escalate to Manager]
                                     ↓
                                  [Log Escalation]
```

**Use Cases**: stock-assistant critical alerts, system health alerts, SLA breaches

**TaskFlow State**:
```json
{
  "alert_id": "alert-123",
  "severity": "critical",
  "primary_channel": "feishu",
  "secondary_channel": "wecom",
  "escalation_channel": "sms",
  "sent_at": "2026-06-20T09:00:00Z",
  "read_at": null,
  "escalated_at": null,
  "status": "waiting_for_read"
}
```

---

## Pattern 4: Approval Workflow

```
[Request] → [Send to Approver] → [Wait for Reply] → [Approved?] → [Yes] → [Execute]
                                                    ↓
                                                 [No] → [Log Rejection] → [Notify Requester]
                                                    ↓
                                                 [Timeout] → [Escalate] → [Auto-Approve?]
```

**Use Cases**: Expense reimbursement, document approval, budget overruns

---

## Pattern 5: Data Pipeline with Retry

```
[Source API] → [Fetch] → [Validate] → [Transform] → [Store] → [Notify]
     ↓           ↓          ↓            ↓          ↓
  [Fail]      [Retry]    [Retry]      [Retry]    [Retry]
     ↓           ↓          ↓            ↓          ↓
  [Max Retry] → [Alert Admin] → [Log] → [Skip] → [Continue]
```

**Use Cases**: Data sync pipelines, ETL workflows, batch processing

---

## Pattern 6: Multi-Agent Collaboration

```
[User Request] → [Decompose] → [Agent A: Research] → [Agent B: Analysis] → [Agent C: Writing]
                                     ↓                       ↓                     ↓
                                  [Partial]               [Partial]               [Partial]
                                     ↓                       ↓                     ↓
                                    [Merge Results] → [Review] → [Deliver]
```

**Use Cases**: Research report generation, due diligence, complex analysis

**TaskFlow State**:
```json
{
  "task": "Generate Q2 Investment Report",
  "agents": {
    "researcher": { "status": "done", "output": "..." },
    "analyst": { "status": "done", "output": "..." },
    "writer": { "status": "running", "output": null }
  },
  "merged_output": null,
  "review_status": "pending"
}
```

---

## Pattern 7: Human-in-the-Loop Confirmation

```
[AI Generated Draft] → [Send to User] → [Wait for Feedback] → [Approved?] → [Yes] → [Send]
                                            ↓
                                         [Edit Request] → [Revise] → [Send Back] → [Loop]
                                            ↓
                                         [Rejected] → [Start Over]
```

**Use Cases**: Email drafts, report generation, content creation, contract review

---

## Implementation Notes

All patterns use the **TaskFlow** engine with these common patterns:

1. **State Management**: `stateJson` persists across steps
2. **Waiting**: `setWaiting` for external events (reply, API callback, timer)
3. **Resume**: `resume` when external event arrives
4. **Child Tasks**: `runTask` for parallel agent work
5. **Finish**: `finish` when workflow complete

See `taskflow/SKILL.md` for full API reference.
