# 📊 运营日报 — {{ report_date | default(generated_at) }}

> {{ org | default("某分公司") }} · {{ scope | default("综合") }}

## 一、关键指标速览

| 指标 | 今日 | 昨日 | 环比 |
|------|------|------|------|
| 工单总数 | {{ tickets_today | default("—") }} | {{ tickets_yesterday | default("—") }} | {{ tickets_delta | default("—") }} |
| 故障总数 | {{ faults_today | default("—") }} | {{ faults_yesterday | default("—") }} | {{ faults_delta | default("—") }} |
| 平均处理时长(min) | {{ avg_handle_min | default("—") }} | {{ avg_handle_min_yesterday | default("—") }} | {{ avg_handle_delta | default("—") }} |
| 一次性解决率 | {{ fcr | default("—") }} | {{ fcr_yesterday | default("—") }} | {{ fcr_delta | default("—") }} |

## 二、TOP 故障类型

{% if top_faults %}{% for f in top_faults %}{{ loop.index }}. **{{ f.type }}** — {{ f.count }} 起{% if f.note %}（{{ f.note }}）{% endif %}
{% endfor %}{% else %}今日无 TOP 故障数据
{% endif %}

## 三、亮点 & 风险

### ✅ 亮点
{% if highlights %}{% for h in highlights %}- {{ h }}
{% endfor %}{% else %}- 无
{% endif %}

### ⚠️ 风险
{% if risks %}{% for r in risks %}- {{ r }}
{% endfor %}{% else %}- 无
{% endif %}

## 四、明日重点

{% if priorities %}{% for p in priorities %}{{ loop.index }}. {{ p }}
{% endfor %}{% else %}- 暂未规划
{% endif %}

---

> 本日报由文档流水线自动生成 · {{ generated_at }} · 模板: operations_daily
