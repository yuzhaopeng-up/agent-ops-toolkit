# Agent Ops Toolkit

> **Enterprise-grade agent infrastructure patterns — cross-channel routing, document pipelines, alerting, and workflow orchestration**
>
> Production-ready Python implementations + design patterns for building reliable, auditable agent systems

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Patterns](https://img.shields.io/badge/Patterns-7-orange.svg)]()
[![Adapters](https://img.shields.io/badge/Channel_Adapters-3-blue.svg)]()
[![Templates](https://img.shields.io/badge/Doc_Templates-6-purple.svg)]()

[中文文档](./README_CN.md) | **English**

---

## Why This Exists

Building AI agents is easy. **Operating** them reliably is hard.

Every agent needs to send messages to multiple channels (Feishu, WeCom, SMS), generate formatted documents from templates, manage alerts without spamming, and orchestrate multi-step workflows with state persistence. Most teams rebuild these patterns from scratch each time.

**Agent Ops Toolkit** provides **reference implementations** for the 4 most common operational patterns every agent system needs:

| Pattern | Status | Lines of Code |
|---------|--------|--------------|
| Cross-Channel Router | Full implementation + tests | 1,500+ |
| Unified Document Pipeline | Full implementation + tests | 1,200+ |
| Alert Engine | Design + API specification | 140 |
| TaskFlow Patterns | 7 workflow blueprints | 160 |

---

## Quick Demo

### 1. Cross-Channel Router — Route Messages to Any Channel

```python
from src.router import CrossChannelRouter
from src.message import OutboundMessage

router = CrossChannelRouter.from_config("config/routing.yaml")

result = router.send(OutboundMessage(
    message_type="card",
    priority="high",
    content={"title": "Critical Alert", "body": "Server CPU > 95%"},
    recipients={"channels": ["feishu", "wecom"], "targets": ["@duty"]},
    metadata={"source_skill": "alert_engine"},
))

print(result.status, result.delivered)
```

Features:
- **Unified message model** (`OutboundMessage`) — decouple "what to send" from "where to send"
- **Degradation matrix** — cards → plain text, buttons → numbered lists, long text → paginated
- **Idempotency** — same `idempotency_key` never sends twice
- **3 adapters**: Feishu, WeCom, Console (test fallback)
- **Audit logging** — every send recorded with trace_id

### 2. Unified Document Pipeline — Generate Reports from Templates

```python
from src.pipeline import DocumentPipeline

pipeline = DocumentPipeline()
result = pipeline.run(
    template="incident_report",
    data={
        "incident_id": "INC-20260620-001",
        "severity": "P1",
        "title": "Router Offline at Site A",
        "root_cause": "Power supply failure",
        "actions": ["Replaced PSU", "Switched to backup line"],
    },
    distribute=False,
)
print(result.rendered)
```

Features:
- **7-stage pipeline**: Ingest → Normalize → Extract → Render → Distribute → Archive → Audit
- **6 built-in templates**: incident report, operations daily, risk review, meeting minutes, customer brief, KPI summary
- **Pluggable stages** — swap renderer, add custom extractors
- **Channel integration** — feeds into Cross-Channel Router for delivery

### 3. Alert Engine — Design Specification

A complete API design for a generic alerting service with:
- Cooldown & deduplication (prevent alert fatigue)
- Escalation chains (Feishu → WeCom → SMS → Manager)
- Alert aggregation (5 alerts → 1 digest)
- Per-source throttling & audit trail

### 4. TaskFlow Patterns — 7 Workflow Blueprints

| # | Pattern | Use Case |
|---|---------|----------|
| 1 | Inbox Triage | Classify + route incoming messages |
| 2 | Scheduled Report | Cron → Gather → Analyze → Generate → Deliver → Archive |
| 3 | Alert Escalation | Primary → Wait → Secondary → Wait → Escalate |
| 4 | Approval Workflow | Request → Approve/Reject → Execute/Log |
| 5 | Data Pipeline with Retry | Fetch → Validate → Transform → Store with retry logic |
| 6 | Multi-Agent Collaboration | Decompose → Parallel agents → Merge → Review |
| 7 | Human-in-the-Loop | AI Draft → Human Review → Revise → Approve → Send |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Ops Toolkit                            │
├────────────────────┬────────────────────┬───────────────────────┤
│  Cross-Channel     │  Document Pipeline │  Alert Engine         │
│  Router            │  (7 stages, 6      │  (Cooldown/Dedup/     │
│  (Feishu/WeCom/    │   templates)       │   Escalation/Aggregate)│
│   Console)         │                    │                        │
├────────────────────┴────────────────────┴───────────────────────┤
│                   TaskFlow Patterns                              │
│  (7 workflow blueprints: Triage / Report / Escalation /         │
│   Approval / Retry / Multi-Agent / Human-in-Loop)               │
├─────────────────────────────────────────────────────────────────┤
│               Shared Infrastructure                              │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
│  │ Idempotency  │  │ Audit Logger  │  │ Degradation Matrix   │ │
│  └──────────────┘  └───────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
git clone https://github.com/yuzhaopeng-up/agent-ops-toolkit.git
cd agent-ops-toolkit
# No pip install needed for core functionality!
```

### Run Tests

```bash
# Cross-channel router
cd cross-channel-router
python -m pytest tests/ -v

# Document pipeline
cd unified-document-pipeline
python -m unittest tests.test_pipeline -v
python examples/demo.py
```

### Run Live Demo

```bash
cd cross-channel-router
python scripts/live_e2e.py
```

---

## Comparison

| Feature | Custom per-agent logic | Agent Ops Toolkit |
|---------|----------------------|-------------------|
| Channel routing | Hardcoded per skill | **Configurable router with degradation** |
| Document generation | String formatting | **7-stage pipeline with templates** |
| Alert management | Threshold + sleep | **Cooldown + dedup + escalation + audit** |
| Workflow patterns | Ad-hoc state machines | **7 proven blueprints with state JSON** |
| Audit trail | None or manual | **Auto-logged with trace_id** |
| Idempotency | Not implemented | **Built-in idempotency_key dedup** |
| Degradation | Crashes on missing channel | **Graceful fallback matrix** |

---

## Project Structure

```
agent-ops-toolkit/
├── cross-channel-router/          # Full implementation
│   ├── src/
│   │   ├── adapter.py             # ChannelAdapter base + Feishu/WeCom/Console
│   │   ├── router.py              # CrossChannelRouter orchestration
│   │   ├── message.py             # OutboundMessage unified model
│   │   ├── routing.py             # Routing decision engine
│   │   ├── degradation.py         # Capability degradation matrix
│   │   ├── http_clients.py        # Feishu/WeCom HTTP clients
│   │   ├── audit.py               # Audit logging
│   │   └── errors.py              # Error code definitions
│   ├── tests/                     # Unit & integration tests
│   ├── examples/                  # Demo scripts & configs
│   └── scripts/                   # Live E2E test
│
├── unified-document-pipeline/     # Full implementation
│   ├── src/
│   │   ├── pipeline.py            # 7-stage DocumentPipeline
│   │   └── template.py            # Jinja2-like template renderer
│   ├── templates/                 # 6 built-in templates
│   ├── tests/
│   └── examples/
│
├── alert-engine/                  # Design + API specification
│   └── README.md
│
└── taskflow-patterns/             # 7 workflow blueprints
    └── README.md
```

---

## Ecosystem

| Repo | Description |
|------|------------|
| [financial-ai-skills](https://github.com/yuzhaopeng-up/financial-ai-skills) | 104 financial AI skills (rule engines) |
| [soe-compliant-office](https://github.com/yuzhaopeng-up/soe-compliant-office) | 20 SOE-compliant office skills |
| [skill-framework](https://github.com/yuzhaopeng-up/skill-framework) | L0-L4 skill governance framework |
| [fintech-h5-demos](https://github.com/yuzhaopeng-up/fintech-h5-demos) | 12 zero-dependency H5 demos |
| [regulated-rag](https://github.com/yuzhaopeng-up/regulated-rag) | Zero-dependency RAG for regulated industries |
| **agent-ops-toolkit** (this repo) | Enterprise agent infrastructure patterns |

## Contributing

PRs welcome! Please ensure:
1. No company-internal information
2. New adapters follow the `ChannelAdapter` base class interface
3. New templates use the standard pipeline stage interface
4. Run tests before submitting

## License

[MIT License](LICENSE) — Free to use, modify, and distribute with attribution.
