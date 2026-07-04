# 🚨 事故通报 — {{ title | default("(未命名事件)") }}

| 字段 | 值 |
|------|----|
| 事件编号 | {{ incident_id | default("N/A") }} |
| 严重等级 | **{{ severity | default("P3") | upper }}** |
| 发生时间 | {{ started_at | default("待补充") }} |
| 当前状态 | {{ status | default("处理中") }} |
| 负责人 | {{ assignee | default("未指派") }} |
| 影响范围 | {{ impact | default("评估中") }} |

## 一、事件描述

{{ description | default(title | default("（无描述）")) }}

## 二、影响评估

{{ impact_detail | default(impact | default("待评估")) }}

{% if affected_systems %}
**受影响系统/网点**：
{% for s in affected_systems %}- {{ s }}
{% endfor %}{% endif %}

## 三、根因分析

{{ root_cause | default("初步排查中，待补充") }}

## 四、处置动作

{% if actions %}{% for a in actions %}{{ loop.index }}. {{ a }}
{% endfor %}{% else %}- 暂无已记录动作
{% endif %}

## 五、后续计划

{{ follow_up | default("- 持续观察 24h\n- 召开复盘会\n- 更新应急预案") }}

---

> 本通报由文档流水线自动生成 · {{ generated_at }} · 模板: incident_report
