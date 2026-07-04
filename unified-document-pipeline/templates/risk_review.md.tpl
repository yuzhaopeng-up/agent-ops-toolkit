# 🛡️ 风险评审报告 — {{ subject | default("(待补充)") }}

| 字段 | 值 |
|------|----|
| 评审编号 | {{ review_id | default("RR-" ~ generated_at) | default("N/A") }} |
| 评审对象 | {{ subject | default("待补充") }} |
| 评审类型 | {{ review_type | default("综合风险评审") }} |
| 评审日期 | {{ review_date | default(generated_at) }} |
| 评审人 | {{ reviewer | default("未指派") }} |
| **总体结论** | **{{ overall_conclusion | default("待评审") | upper }}** |

## 一、评审范围

{{ scope | default("范围待补充") }}

## 二、风险维度评估

| 维度 | 评分(1-5) | 说明 |
|------|-----------|------|
{% if dimensions %}{% for d in dimensions %}| {{ d.name }} | {{ d.score }} | {{ d.comment | default("—") }} |
{% endfor %}{% else %}| 信用风险 | — | 待评估 |
| 操作风险 | — | 待评估 |
| 合规风险 | — | 待评估 |
{% endif %}

## 三、关键发现

{% if findings %}{% for f in findings %}### {{ loop.index }}. {{ f.title }}

- **严重度**：{{ f.severity | default("中") }}
- **描述**：{{ f.description | default("—") }}
- **建议**：{{ f.recommendation | default("—") }}

{% endfor %}{% else %}*暂无关键发现*
{% endif %}

## 四、整改要求

{% if remediation %}{% for r in remediation %}{{ loop.index }}. **{{ r.action }}** — 责任人：{{ r.owner | default("未指派") }} · 截止：{{ r.due | default("待定") }}
{% endfor %}{% else %}- 无强制整改项
{% endif %}

## 五、复审计划

{{ next_review | default("12 个月后或触发条件变化时复审") }}

---

> 本报告由文档流水线自动生成 · {{ generated_at }} · 模板: risk_review
