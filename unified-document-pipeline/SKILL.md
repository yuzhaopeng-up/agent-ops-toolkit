---
name: unified_document_pipeline
description: "L2 文档流水线 reference 实现：标准化 7 阶段（Ingest→Normalize→Extract→Render→Distribute→Archive→Audit），自带 6 个开箱即用模板（事故通报/运营日报/风控评审/会议纪要/客户简报/KPI总结）。"
version: 1.0.0
author: BetaAgent
license: MIT
layer: L2
capability_domain: [C02, C04, C03]
industry: universal
metadata:
  beta-agent:
    tags: [document, pipeline, template, report]
    related_skills: [cross_channel_router, alert_engine]
  reference_impl: true
  blueprint_doc: 00-methodology/skill-architecture/l2-patterns/unified-document-pipeline.md
prerequisites:
  commands: [python3]
---

# Unified Document Pipeline (L2 Reference 实现)

> 把"输入数据 → 渲染输出 → 分发归档"做成可插拔流水线，业务 Skill 只关心数据。

## 核心能力

把"输入数据 → 渲染输出 → 分发归档"做成可插拔流水线，业务 Skill 只关心数据。

## 流水线 7 阶段

```
[Source] → Ingest → Normalize → Extract → Render → Distribute → Archive → Audit
                                            ↓
                                       [6 内置模板]
```

| 阶段 | 类 | 职责 |
|------|-----|------|
| Ingest | `Ingestor` | 加载原始数据（dict/json/yaml/csv） |
| Normalize | `Normalizer` | 字段标准化、空值填充、类型校验 |
| Extract | `Extractor` | 从原始数据中抽取模板需要的关键指标 |
| Render | `TemplateRenderer` | 用 Jinja2-like 语法渲染 markdown |
| Distribute | `Distributor` | 调用 cross_channel_router 多渠道分发 |
| Archive | `Archiver` | 保存渲染结果到本地/对象存储 |
| Audit | `AuditLogger` | 记录每阶段耗时、错误、产物指纹 |

## 6 个内置模板

| 模板 | 文件 | 适用场景 |
|------|------|----------|
| `incident_report` | templates/incident_report.md.tpl | 故障/告警事故通报 |
| `operations_daily` | templates/operations_daily.md.tpl | 运营日报（工单/故障/营销/呼叫） |
| `risk_review` | templates/risk_review.md.tpl | 信贷/风控评审、合规检查报告 |
| `meeting_minutes` | templates/meeting_minutes.md.tpl | 会议纪要（议题/决议/Action） |
| `customer_brief` | templates/customer_brief.md.tpl | 客户档案 / 尽调简报 |
| `kpi_summary` | templates/kpi_summary.md.tpl | 月度/季度 KPI 业绩总结 |

## 使用示例

```python
from src.pipeline import DocumentPipeline

pipeline = DocumentPipeline()
result = pipeline.run(
    template="incident_report",
    data={
        "incident_id": "INC-20260620-001",
        "severity": "P1",
        "title": "网点 A 路由器掉线",
        "started_at": "2026-06-20 14:23",
        "impact": "50+ 终端断网 30 分钟",
        "root_cause": "电源故障",
        "actions": ["更换电源模块", "切换备用线路"],
        "assignee": "张工",
    },
    distribute=False,   # demo 不分发
)
print(result.rendered)
```

## 测试

```bash
cd skills/unified_document_pipeline
python3 -m unittest tests.test_pipeline -v
python3 examples/demo.py
```

## 已知限制

- 内置渲染器是简化版 Jinja2（仅支持 `{{ var }}` / `{% for %}` / `{% if %}`）。生产建议换 jinja2 包。
- Distributor 通过依赖注入接 cross_channel_router；如未安装 router 则跳过分发。
- Archiver 默认本地文件系统；S3/COS 适配器留作扩展点。
