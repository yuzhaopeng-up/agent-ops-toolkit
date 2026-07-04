# 👤 客户简报 — {{ customer_name | default("(待补充)") }}

| 字段 | 值 |
|------|----|
| 客户编号 | {{ customer_id | default("N/A") }} |
| 客户类型 | {{ customer_type | default("未分类") }} |
| 行业 | {{ industry | default("未知") }} |
| 注册地 | {{ region | default("未知") }} |
| 客户经理 | {{ rm | default("未分配") }} |
| 风险等级 | **{{ risk_grade | default("未评估") | upper }}** |
| 数据快照时间 | {{ snapshot_at | default(generated_at) }} |

## 一、基本概况

{{ overview | default("（暂无客户概况）") }}

## 二、关键财务/经营指标

| 指标 | 当期 | 同比 |
|------|------|------|
{% if financials %}{% for f in financials %}| {{ f.name }} | {{ f.current | default("—") }} | {{ f.yoy | default("—") }} |
{% endfor %}{% else %}| 营业收入 | — | — |
| 净利润 | — | — |
| 资产负债率 | — | — |
{% endif %}

## 三、合作历史

{% if cooperation %}{% for c in cooperation %}- **{{ c.year | default("—") }}** {{ c.product | default("产品") }} — {{ c.amount | default("—") }} ({{ c.status | default("—") }})
{% endfor %}{% else %}*暂无合作记录*
{% endif %}

## 四、风险信号

{% if risk_signals %}{% for s in risk_signals %}- ⚠️ {{ s }}
{% endfor %}{% else %}- 暂无显著风险信号
{% endif %}

## 五、营销机会

{% if opportunities %}{% for o in opportunities %}{{ loop.index }}. **{{ o.title | default(o) }}**{% if o.note %} — {{ o.note }}{% endif %}
{% endfor %}{% else %}*待挖掘*
{% endif %}

## 六、建议下一步

{{ next_steps | default("- 安排上门拜访\n- 更新客户画像\n- 制定 90 天营销计划") }}

---

> 本简报由文档流水线自动生成 · {{ generated_at }} · 模板: customer_brief
> ⚠️ 客户敏感信息，仅限授权人员查阅
