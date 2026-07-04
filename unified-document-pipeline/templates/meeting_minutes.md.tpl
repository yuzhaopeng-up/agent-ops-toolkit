# 📝 会议纪要 — {{ title | default("(未命名会议)") }}

| 字段 | 值 |
|------|----|
| 会议时间 | {{ meeting_at | default(generated_at) }} |
| 会议地点 | {{ location | default("线上") }} |
| 主持人 | {{ host | default("未指定") }} |
| 记录人 | {{ recorder | default("未指定") }} |

## 一、参会人员

{% if attendees %}{% for a in attendees %}- {{ a }}
{% endfor %}{% else %}*待补充*
{% endif %}

## 二、议题与讨论

{% if topics %}{% for t in topics %}### 议题 {{ loop.index }}：{{ t.title }}

**讨论要点**：
{% if t.points %}{% for p in t.points %}- {{ p }}
{% endfor %}{% else %}*（无记录）*
{% endif %}

**结论**：{{ t.conclusion | default("待定") }}

{% endfor %}{% else %}*本次会议未记录议题*
{% endif %}

## 三、决议事项

{% if decisions %}{% for d in decisions %}{{ loop.index }}. {{ d }}
{% endfor %}{% else %}- 暂无明确决议
{% endif %}

## 四、Action Items

| # | 行动项 | 责任人 | 截止日期 | 状态 |
|---|--------|--------|----------|------|
{% if actions %}{% for a in actions %}| {{ loop.index }} | {{ a.task }} | {{ a.owner | default("未指派") }} | {{ a.due | default("待定") }} | {{ a.status | default("待启动") }} |
{% endfor %}{% else %}| — | 无 | — | — | — |
{% endif %}

## 五、下次会议

{{ next_meeting | default("待定") }}

---

> 本纪要由文档流水线自动生成 · {{ generated_at }} · 模板: meeting_minutes
