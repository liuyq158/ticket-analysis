# 工单数据字段说明（数据源结构）

数据源为 JSON 数组，每条记录代表一个客服工单。文件路径通过 `analyze_tickets.py` 的 `--input` 参数传入（默认示例：`task5_tickets.json`）。

| 字段 | 类型 | 说明 | 分析用途 |
|------|------|------|----------|
| `ticket_id` | string | 工单唯一编号 | 计数 / 主键 |
| `created_at` | string | 创建时间（YYYY-MM-DD HH:MM） | 时间维度：按日趋势、工作日/周末/节假日、上午/下午/晚上 |
| `category` | string | 问题分类标签 | 问题分类维度：占比与趋势 |
| `description` | string | 问题描述（用户原文） | 可选，不参与量化分析 |
| `priority` | string | 优先级（高/中/低） | 优先级维度 |
| `resolution_time_hours` | number | 处理时长（小时） | 处理时长维度：均值、分布、按分类对比 |
| `satisfaction` | number | 满意度评分（1-5） | 满意度维度：均值、评分分布 |
| `channel` | string | 来源渠道（在线/电话/邮件） | 来源渠道维度（注意：实际数据可能不包含所有渠道值） |
| `is_resolved` | boolean | 是否已解决 | 是否已解决维度：解决率 |

## 注意事项

- `created_at` 解析使用 `datetime.strptime(value, "%Y-%m-%d %H:%M")`。
- 节假日判定优先使用 `chinese_calendar.is_holiday(date)`，若库不可用则回退到脚本内置的 `HOLIDAYS` 集合（含 2024 年主要法定节假日，可扩展）。
- 时段分桶：06:00–11:59 为「上午」，12:00–17:59 为「下午」，18:00–05:59 为「晚上」。
- `channel` 维度需动态识别数据中实际出现的渠道值，缺失项在报告中说明，不臆造。
- `satisfaction` 取值 1–5，低分为 1、2，用于识别体验风险点。
- `is_resolved` 为布尔，解决率 = 已解决数 / 总数。
