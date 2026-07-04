# 📈 KPI 业绩总结 — {{ period | default("本期") }}

> {{ org | default("某团队") }} · 报告人：{{ owner | default("未指定") }}

## 一、核心 KPI 完成度

| KPI | 目标 | 实际 | 完成率 | 状态 |
|-----|------|------|--------|------|
{% if kpis %}{% for k in kpis %}| {{ k.name }} | {{ k.target }} | {{ k.actual }} | {{ k.completion | default("—") }} | {{ k.status | default("—") }} |
{% endfor %}{% else %}| — | — | — | — | 数据缺失 |
{% endif %}

**总体完成度**：**{{ overall_completion | default("待计算") }}**

## 二、亮点

{% if highlights %}{% for h in highlights %}### ✨ {{ h.title | default(h) }}

{% if h.detail %}{{ h.detail }}{% endif %}
{% endfor %}{% else %}*暂无突出亮点*
{% endif %}

## 三、未达成项 & 原因

{% if shortfalls %}{% for s in shortfalls %}### ⚠️ {{ s.kpi | default("未命名") }}

- **缺口**：{{ s.gap | default("—") }}
- **原因**：{{ s.reason | default("待分析") }}
- **改进措施**：{{ s.action | default("待制定") }}

{% endfor %}{% else %}*所有 KPI 均达成 ✅*
{% endif %}

## 四、关键经验

{% if lessons %}{% for l in lessons %}{{ loop.index }}. {{ l }}
{% endfor %}{% else %}*待沉淀*
{% endif %}

## 五、下期目标

{% if next_targets %}{% for t in next_targets %}- **{{ t.kpi }}**：{{ t.target }}{% if t.note %} ({{ t.note }}){% endif %}
{% endfor %}{% else %}*待对齐*
{% endif %}

---

> 本总结由文档流水线自动生成 · {{ generated_at }} · 模板: kpi_summary
