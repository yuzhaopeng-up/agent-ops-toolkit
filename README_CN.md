# Agent Ops Toolkit

> **企业级 Agent 运维基础设施 — 跨渠道路由、文档流水线、告警引擎、工作流编排**
>
> 生产就绪的 Python 实现 + 设计模式，构建可靠、可审计的 Agent 系统

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Patterns](https://img.shields.io/badge/Patterns-7-orange.svg)]()
[![Adapters](https://img.shields.io/badge/Channel_Adapters-3-blue.svg)]()
[![Templates](https://img.shields.io/badge/Doc_Templates-6-purple.svg)]()

**中文** | [English](./README.md)

---

## 为什么做这个项目

构建 AI Agent 很容易，**运维** Agent 很难。

每个 Agent 都需要往多个渠道发消息（飞书、企微、短信），用模板生成格式化文档，管理告警且避免骚扰，编排多步骤工作流并持久化状态。大多数团队每次都从头重建这些模式。

**Agent Ops Toolkit** 提供了 Agent 系统最需要的 4 大运维模式的**参考实现**：

| 模式 | 状态 | 代码行数 |
|------|------|---------|
| 跨渠道路由器 | 完整实现 + 测试 | 1,500+ |
| 统一文档流水线 | 完整实现 + 测试 | 1,200+ |
| 告警引擎 | 设计 + API 规范 | 140 |
| TaskFlow 工作流 | 7 种蓝图 | 160 |

---

## 快速演示

### 1. 跨渠道路由器 — 消息自动路由到任意渠道

```python
from src.router import CrossChannelRouter
from src.message import OutboundMessage

router = CrossChannelRouter.from_config("config/routing.yaml")

result = router.send(OutboundMessage(
    message_type="card",
    priority="high",
    content={"title": "严重告警", "body": "服务器 CPU > 95%"},
    recipients={"channels": ["feishu", "wecom"], "targets": ["@duty"]},
    metadata={"source_skill": "alert_engine"},
))

print(result.status, result.delivered)
```

核心能力：统一消息模型、降级矩阵、幂等性、3 个适配器（飞书/企微/控制台）、审计日志

### 2. 统一文档流水线 — 从模板生成报告

```python
from src.pipeline import DocumentPipeline

pipeline = DocumentPipeline()
result = pipeline.run(
    template="incident_report",
    data={
        "incident_id": "INC-20260620-001",
        "severity": "P1",
        "title": "网点A路由器掉线",
        "root_cause": "电源故障",
        "actions": ["更换电源模块", "切换备用线路"],
    },
    distribute=False,
)
print(result.rendered)
```

核心能力：7 阶段流水线、6 个内置模板、可插拔阶段、渠道路由集成

### 3. 告警引擎 — 设计规范

完整的通用告警服务 API 设计：冷却/去重（防告警疲劳）、升级链（飞书→企微→短信→主管）、告警聚合、限流 & 审计

### 4. TaskFlow 工作流 — 7 种蓝图

| # | 模式 | 场景 |
|---|------|------|
| 1 | 收件箱分诊 | 分类 + 路由收到的消息 |
| 2 | 定时报告 | 定时→采集→分析→生成→投递→归档 |
| 3 | 告警升级 | 主渠道→等待→副渠道→等待→升级 |
| 4 | 审批流程 | 申请→审批/驳回→执行/记录 |
| 5 | 带重试的数据管道 | 采集→校验→转换→存储，含重试逻辑 |
| 6 | 多 Agent 协作 | 拆解→并行→合并→评审 |
| 7 | 人在回路 | AI 草稿→人工审查→修订→批准→发送 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Ops Toolkit                            │
├────────────────────┬────────────────────┬───────────────────────┤
│  跨渠道路由器      │  文档流水线        │  告警引擎              │
│  (飞书/企微/       │  (7阶段, 6模板)    │  (冷却/去重/           │
│   控制台)          │                    │   升级/聚合)           │
├────────────────────┴────────────────────┴───────────────────────┤
│                   TaskFlow 工作流模式                             │
│  (7种蓝图: 分诊/报告/升级/审批/重试/多Agent/人在回路)            │
├─────────────────────────────────────────────────────────────────┤
│               共享基础设施                                        │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
│  │  幂等性      │  │  审计日志     │  │  降级矩阵            │ │
│  └──────────────┘  └───────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 快速开始

```bash
git clone https://github.com/yuzhaopeng-up/agent-ops-toolkit.git
cd agent-ops-toolkit
# 无需 pip install！
```

### 运行测试

```bash
# 跨渠道路由器
cd cross-channel-router && python -m pytest tests/ -v

# 文档流水线
cd unified-document-pipeline
python -m unittest tests.test_pipeline -v
python examples/demo.py
```

### 实时演示

```bash
cd cross-channel-router && python scripts/live_e2e.py
```

---

## 对比

| 特性 | 每个Agent自己写 | Agent Ops Toolkit |
|------|---------------|-------------------|
| 渠道路由 | 硬编码 | **可配置路由 + 降级** |
| 文档生成 | 字符串拼接 | **7阶段流水线 + 模板** |
| 告警管理 | 阈值+sleep | **冷却+去重+升级+审计** |
| 工作流模式 | 临时状态机 | **7种蓝图 + 状态JSON** |
| 审计日志 | 无或手写 | **自动记录 trace_id** |
| 幂等性 | 未实现 | **内置 idempotency_key** |
| 降级 | 渠道不通就崩 | **优雅降级矩阵** |

---

## 项目结构

```
agent-ops-toolkit/
├── cross-channel-router/          # 完整实现
│   ├── src/                       # 核心代码（适配器/路由/消息/降级/审计/错误码）
│   ├── tests/                     # 单元 & 集成测试
│   ├── examples/                  # 演示脚本 & 配置
│   └── scripts/                   # 实时E2E测试
│
├── unified-document-pipeline/     # 完整实现
│   ├── src/                       # 流水线 + 模板渲染器
│   ├── templates/                 # 6个内置模板
│   ├── tests/
│   └── examples/
│
├── alert-engine/                  # 设计 + API 规范
│   └── README.md
│
└── taskflow-patterns/             # 7种工作流蓝图
    └── README.md
```

---

## 相关项目

| 仓库 | 描述 |
|------|------|
| [financial-ai-skills](https://github.com/yuzhaopeng-up/financial-ai-skills) | 104 个金融 AI 技能 |
| [soe-compliant-office](https://github.com/yuzhaopeng-up/soe-compliant-office) | 20 个央国企合规办公技能 |
| [skill-framework](https://github.com/yuzhaopeng-up/skill-framework) | L0-L4 技能治理框架 |
| [fintech-h5-demos](https://github.com/yuzhaopeng-up/fintech-h5-demos) | 12 个零依赖 H5 演示 |
| [regulated-rag](https://github.com/yuzhaopeng-up/regulated-rag) | 监管行业零依赖 RAG 工具包 |
| **agent-ops-toolkit**（本仓库） | 企业级 Agent 运维基础设施 |

## 贡献指南

欢迎 PR！请确保：
1. 不含公司内部信息
2. 新适配器遵循 `ChannelAdapter` 基类接口
3. 新模板遵循标准流水线阶段接口
4. 提交前运行测试

## 许可证

[MIT License](LICENSE) — 自由使用、修改和分发，需保留署名。
