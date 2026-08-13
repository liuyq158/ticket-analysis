---
name: ticket-analysis
description: 分析客服/工单类 JSON 数据并生成可视化 HTML 报告。当用户提供工单、客服工单、ticket 等 JSON 数据，并希望按「创建时间、问题分类、优先级、处理时长、满意度、来源渠道、是否已解决」等维度进行分类统计、绘制趋势图并进行数据分析时，使用此 skill。输出为单文件、可交互的 HTML 报告。
---

# 工单数据分析（ticket-analysis）

## Overview

本 skill 读取工单类 JSON 数据，按 7 个核心维度（创建时间、问题分类标签、优先级、处理时长、满意度评分、来源渠道、是否已解决）自动分类、统计并生成 Plotly 交互式趋势图，随后由 Agent 基于结构化统计结果撰写每个维度的数据分析结论，最终汇总为一个自包含的 HTML 报告。

## 触发场景

- 用户提供 `task5_tickets.json` 等工单数据并要求「分析」「出图」「可视化」「报告」。
- 用户提到按时间、分类、优先级、处理时长、满意度、渠道、解决情况等维度审视工单。
- 用户希望得到一份可在浏览器打开的交互式工单分析报告。

## 字段结构

数据源字段定义见 `references/fields.md`。脚本默认按该字段结构解析；若用户提供的数据字段名不同，先与 `references/fields.md` 对照并相应调整脚本中的键名。

## Workflow

### 第 1 步：确定输入与输出

- 输入：工单 JSON 文件路径（数组，每条一个工单）。若用户未指定，询问或查找工作区附近的 `*.json` 工单文件（如 `task5_tickets.json`）。
- 输出目录：建议 `output/`（脚本 `--outdir`）。
- 确认已安装 `plotly`：若运行脚本报错缺少 `plotly`，先执行 `pip install plotly`（使用可运行 Python 解释器）。

### 第 2 步：运行分析脚本

执行 `scripts/analyze_tickets.py`，示例：

```bash
python <skill>/scripts/analyze_tickets.py --input <工单.json> --outdir output
```

脚本将完成：
1. 按 7 个维度分类（创建时间含工作日/周末/节假日与上午/下午/晚上判定，节假日优先用 `chinese_calendar`，否则回退内置集合）。
2. 生成 Plotly 交互图（每日趋势、堆叠分布、占比饼图、评分分布、按分类对比等）。
3. 输出 `output/report.html`（含图表 + 统计表 + 待填充的分析占位区）与 `output/stats.json`（结构化统计，供下一步使用）。

### 第 3 步：Agent 撰写数据分析结论

读取 `output/stats.json`，针对 **每个维度** 在 `output/report.html` 中对应的 `<!--ANALYSIS:<dim>-->` 占位符处，用 `replace_in_file` 填入中文分析结论。各维度分析要点：

- **created_at（创建时间）**：必须包含——工作日/周末/节假日对比（引用 `day_type` 计数）、上午/下午/晚上分布（引用 `time_slot`）、峰值日（`peak_date`/`peak_count`）、假期是否出现量增（对比 `holiday_dates` 与平日均值）；可结合优先级看高危时段。
- **category（问题分类）**：哪类工单最多（`top`/`top_count`），是否存在某类集中爆发。
- **priority（优先级）**：高优先级占比（`high_ratio`），是否某日高危集中。
- **resolution_time（处理时长）**：整体平均、最长工单，超长处理集中在哪些分类（`by_category`），是否存在体验风险。
- **satisfaction（满意度）**：平均得分、低分（1-2）占比（`low_score_ratio`），低分与哪些分类/渠道相关。
- **channel（来源渠道）**：各渠道占比；注意 `missing_channels` 中缺失的渠道需在报告中说明（如数据中无「邮件」）。
- **is_resolved（是否已解决）**：整体解决率、未解决数量及其集中分类（`unresolved_by_category`）。

结论应基于 `stats.json` 的真实数值，避免臆造；缺失维度如实说明。

### 第 4 步：强制检查分析结论完整性

在交付前必须运行校验脚本，确保没有遗漏：

```bash
python <skill>/scripts/verify_report.py output/report.html
```

该脚本会检查：
1. 7 个维度 section 齐全；
2. 每个维度的 `<!--ANALYSIS:<dim>-->` 占位符已被替换；
3. 每个分析结论段落非空且长度合理。

若校验失败（退出码非 0），必须回到第 3 步补全缺失结论，禁止直接交付。

### 第 5 步：交付

校验通过后，将最终 `output/report.html` 通过 `open_result_view` / 浏览器预览交付给用户。该文件为单文件、内联 Plotly 库，可直接双击打开。

## Resources

- `scripts/analyze_tickets.py`：数据分类、统计、绘图与 HTML 渲染主脚本（依赖 `plotly`）。
- `references/fields.md`：数据源字段结构与解析注意事项。
- `assets/report_template.html`：HTML 报告模板（含 `{{OVERVIEW}}`、`{{SECTIONS}}`、各维度 `<!--ANALYSIS:<dim>-->` 占位符）。
