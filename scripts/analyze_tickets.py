#!/usr/bin/env python3
"""
工单数据分析脚本（ticket-analysis skill）

读取工单 JSON 数据，按以下 7 个维度分类、统计，并生成 plotly 交互式图表：
  1. created_at   创建时间（按日趋势、工作日/周末/节假日、上午/下午/晚上）
  2. category      问题分类标签
  3. priority      优先级（高/中/低）
  4. resolution_time_hours 处理时长（小时）
  5. satisfaction  满意度评分（1-5）
  6. channel       来源渠道（在线/电话/邮件）
  7. is_resolved   是否已解决

输出：
  - <outdir>/report.html  图表 + 统计表 + 待填充的分析结论占位区
  - <outdir>/stats.json   结构化统计数据，供 Agent 撰写分析结论

用法：
  python analyze_tickets.py --input tickets.json --outdir examples \
      [--template assets/report_template.html]

依赖：plotly（pip install plotly）。标准库用于数据分类，无需 pandas。
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# 节假日回退集合（当 chinese_calendar 不可用时使用）。可按需扩展年份。
# ----------------------------------------------------------------------------
HOLIDAYS = {
    "2024-01-01", "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13",
    "2024-02-14", "2024-02-15", "2024-02-16", "2024-02-17", "2024-04-04",
    "2024-04-05", "2024-04-06", "2024-05-01", "2024-05-02", "2024-05-03",
    "2024-05-04", "2024-05-05", "2024-06-08", "2024-06-09", "2024-06-10",
    "2024-09-15", "2024-09-16", "2024-09-17", "2024-10-01", "2024-10-02",
    "2024-10-03", "2024-10-04", "2024-10-05", "2024-10-06", "2024-10-07",
}


def get_day_type(d):
    """返回 '工作日' / '周末' / '节假日'。优先 chinese_calendar，否则回退内置集合。"""
    ds = d.strftime("%Y-%m-%d")
    try:
        import chinese_calendar
        if chinese_calendar.is_holiday(d):
            return "节假日"
    except Exception:
        if ds in HOLIDAYS:
            return "节假日"
    if d.weekday() >= 5:
        return "周末"
    return "工作日"


def get_time_slot(hour):
    if 6 <= hour < 12:
        return "上午"
    if 12 <= hour < 18:
        return "下午"
    return "晚上"


def load_tickets(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------------
# 维度分析
# ----------------------------------------------------------------------------
def analyze(tickets):
    for t in tickets:
        dt = datetime.strptime(t["created_at"], "%Y-%m-%d %H:%M")
        t["_dt"] = dt
        t["_date"] = dt.strftime("%Y-%m-%d")
        t["_day_type"] = get_day_type(dt)
        t["_slot"] = get_time_slot(dt.hour)

    dates = sorted({t["_date"] for t in tickets})

    stats = {}
    stats["total"] = len(tickets)
    stats["date_range"] = {"start": dates[0], "end": dates[-1]} if dates else {}

    # 1. 创建时间
    daily_counts = Counter(t["_date"] for t in tickets)
    day_type_counts = Counter(t["_day_type"] for t in tickets)
    slot_counts = Counter(t["_slot"] for t in tickets)
    peak_date = max(daily_counts, key=daily_counts.get)
    stats["created_at"] = {
        "daily": {d: daily_counts.get(d, 0) for d in dates},
        "day_type": dict(day_type_counts),
        "time_slot": dict(slot_counts),
        "peak_date": peak_date,
        "peak_count": daily_counts[peak_date],
        "holiday_dates": sorted(
            {t["_date"] for t in tickets if t["_day_type"] == "节假日"}
        ),
    }

    # 2. 问题分类
    cat_counts = Counter(t["category"] for t in tickets)
    cat_daily = defaultdict(Counter)
    for t in tickets:
        cat_daily[t["_date"]][t["category"]] += 1
    cats = [c for c, _ in cat_counts.most_common()]
    stats["category"] = {
        "overall": dict(cat_counts),
        "categories": cats,
        "daily": {d: {c: cat_daily[d].get(c, 0) for c in cats} for d in dates},
        "top": cats[0] if cats else None,
        "top_count": cat_counts.most_common(1)[0][1] if cats else 0,
    }

    # 3. 优先级
    prio_counts = Counter(t["priority"] for t in tickets)
    prio_daily = defaultdict(Counter)
    for t in tickets:
        prio_daily[t["_date"]][t["priority"]] += 1
    prios = ["高", "中", "低"]
    present_prios = [p for p in prios if p in prio_counts]
    stats["priority"] = {
        "overall": dict(prio_counts),
        "order": present_prios,
        "daily": {d: {p: prio_daily[d].get(p, 0) for p in present_prios} for d in dates},
        "high_count": prio_counts.get("高", 0),
        "high_ratio": round(prio_counts.get("高", 0) / len(tickets), 4),
    }

    # 4. 处理时长
    rt_all = [t["resolution_time_hours"] for t in tickets]
    rt_daily = {}
    for d in dates:
        vals = [t["resolution_time_hours"] for t in tickets if t["_date"] == d]
        rt_daily[d] = round(sum(vals) / len(vals), 2) if vals else 0
    rt_by_cat = defaultdict(list)
    for t in tickets:
        rt_by_cat[t["category"]].append(t["resolution_time_hours"])
    stats["resolution_time"] = {
        "overall_avg": round(sum(rt_all) / len(rt_all), 2),
        "max": max(rt_all),
        "min": min(rt_all),
        "daily_avg": rt_daily,
        "by_category": {c: round(sum(v) / len(v), 2) for c, v in rt_by_cat.items()},
    }

    # 5. 满意度
    sat_all = [t["satisfaction"] for t in tickets]
    sat_daily = {}
    for d in dates:
        vals = [t["satisfaction"] for t in tickets if t["_date"] == d]
        sat_daily[d] = round(sum(vals) / len(vals), 2) if vals else 0
    sat_dist = Counter(t["satisfaction"] for t in tickets)
    low = sum(v for k, v in sat_dist.items() if k <= 2)
    stats["satisfaction"] = {
        "overall_avg": round(sum(sat_all) / len(sat_all), 2),
        "daily_avg": sat_daily,
        "distribution": {str(k): sat_dist.get(k, 0) for k in range(1, 6)},
        "low_score_ratio": round(low / len(tickets), 4),
    }

    # 6. 来源渠道
    ch_counts = Counter(t["channel"] for t in tickets)
    ch_daily = defaultdict(Counter)
    for t in tickets:
        ch_daily[t["_date"]][t["channel"]] += 1
    chs = [c for c, _ in ch_counts.most_common()]
    all_possible = ["在线", "电话", "邮件"]
    missing = [c for c in all_possible if c not in ch_counts]
    stats["channel"] = {
        "overall": dict(ch_counts),
        "channels": chs,
        "daily": {d: {c: ch_daily[d].get(c, 0) for c in chs} for d in dates},
        "missing_channels": missing,
    }

    # 7. 是否已解决
    resolved = sum(1 for t in tickets if t["is_resolved"])
    unresolved_by_cat = Counter(
        t["category"] for t in tickets if not t["is_resolved"]
    )
    res_daily = {}
    for d in dates:
        day_tickets = [t for t in tickets if t["_date"] == d]
        ok = sum(1 for t in day_tickets if t["is_resolved"])
        res_daily[d] = round(ok / len(day_tickets), 4) if day_tickets else 0
    stats["is_resolved"] = {
        "resolved": resolved,
        "unresolved": len(tickets) - resolved,
        "rate": round(resolved / len(tickets), 4),
        "daily_rate": res_daily,
        "unresolved_by_category": dict(unresolved_by_cat),
    }

    return stats, dates


# ----------------------------------------------------------------------------
# 图表生成（plotly）
# ----------------------------------------------------------------------------
_plotly_initialized = False


def fig_html(fig):
    global _plotly_initialized
    # responsive=True 让图表随容器宽度自适应，避免溢出/被放大且无法横向滚动
    # 关闭所有缩放/拖拽交互，避免图表被拖动放大；保留 hover 与 responsive
    cfg = {
        "displayModeBar": False,
        "responsive": True,
        "scrollZoom": False,
        "editable": False,
    }
    # layout 层面也禁用拖拽缩放
    fig.update_layout(dragmode=False)
    if not _plotly_initialized:
        html = fig.to_html(full_html=False, include_plotlyjs="inline", config=cfg)
        _plotly_initialized = True
    else:
        html = fig.to_html(full_html=False, include_plotlyjs=False, config=cfg)
    return html


def build_charts(stats, dates):
    import plotly.graph_objects as go
    # 对日期序列较长的折线/堆叠图，避免标签过密导致显示不全
    tick_strategy = "auto"

    charts = {}
    # width=None 配合 autosize + responsive，让 Plotly 在 grid/flex 容器里真正 100% 自适应
    layout = dict(
        autosize=True, width=None, height=380,
        margin=dict(l=40, r=20, t=40, b=40),
        font=dict(family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif", size=13),
    )

    # 1. created_at
    c = stats["created_at"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=[c["daily"][d] for d in dates],
                             mode="lines+markers", name="每日工单量",
                             line=dict(color="#2563eb", width=3)))
    fig.update_layout(
        title="每日工单创建量趋势", xaxis_title="日期", yaxis_title="工单数",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)), **layout)
    charts["created_at_trend"] = fig_html(fig)

    dt_order = ["工作日", "周末", "节假日"]
    dt_vals = [c["day_type"].get(k, 0) for k in dt_order]
    fig = go.Figure(go.Bar(x=dt_order, y=dt_vals,
                           marker_color=["#2563eb", "#f59e0b", "#ef4444"]))
    fig.update_layout(title="按工作日/周末/节假日分布", **layout)
    charts["created_at_daytype"] = fig_html(fig)

    slot_order = ["上午", "下午", "晚上"]
    slot_vals = [c["time_slot"].get(k, 0) for k in slot_order]
    fig = go.Figure(go.Pie(labels=slot_order, values=slot_vals, hole=0.4))
    fig.update_layout(title="按一天时段分布", **layout)
    charts["created_at_slot"] = fig_html(fig)

    # 2. category
    cat = stats["category"]
    fig = go.Figure()
    for cname in cat["categories"]:
        fig.add_trace(go.Bar(
            x=dates, y=[cat["daily"][d][cname] for d in dates],
            name=cname, hovertemplate=cname + ": %{y}<extra></extra>"))
    fig.update_layout(
        barmode="stack", title="每日问题分类堆叠",
        xaxis_title="日期", yaxis_title="工单数",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)), **layout)
    charts["category_daily"] = fig_html(fig)

    fig = go.Figure(go.Bar(
        x=list(cat["overall"].keys()), y=list(cat["overall"].values()),
        marker_color="#7c3aed"))
    fig.update_layout(title="问题分类总体占比", **layout)
    charts["category_overall"] = fig_html(fig)

    # 3. priority
    prio = stats["priority"]
    fig = go.Figure()
    colors = {"高": "#ef4444", "中": "#f59e0b", "低": "#10b981"}
    for p in prio["order"]:
        fig.add_trace(go.Bar(
            x=dates, y=[prio["daily"][d][p] for d in dates],
            name=p, marker_color=colors.get(p, "#64748b")))
    fig.update_layout(
        barmode="stack", title="每日优先级堆叠",
        xaxis_title="日期", yaxis_title="工单数",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)), **layout)
    charts["priority_daily"] = fig_html(fig)

    fig = go.Figure(go.Bar(
        x=list(prio["overall"].keys()), y=list(prio["overall"].values()),
        marker_color=[colors.get(p, "#64748b") for p in prio["overall"].keys()]))
    fig.update_layout(title="优先级总体分布", **layout)
    charts["priority_overall"] = fig_html(fig)

    # 4. resolution_time
    rt = stats["resolution_time"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=[rt["daily_avg"][d] for d in dates],
                             mode="lines+markers", name="平均处理时长",
                             line=dict(color="#0ea5e9", width=3)))
    fig.update_layout(
        title="每日平均处理时长趋势", xaxis_title="日期", yaxis_title="小时",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)), **layout)
    charts["resolution_daily"] = fig_html(fig)

    bc = rt["by_category"]
    fig = go.Figure(go.Bar(
        x=list(bc.keys()), y=list(bc.values()), marker_color="#0ea5e9"))
    fig.update_layout(title="各分类平均处理时长",
                     yaxis_title="平均小时", **layout)
    charts["resolution_by_cat"] = fig_html(fig)

    # 5. satisfaction
    sat = stats["satisfaction"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=[sat["daily_avg"][d] for d in dates],
                             mode="lines+markers", name="平均满意度",
                             line=dict(color="#10b981", width=3)))
    fig.update_layout(
        title="每日平均满意度趋势", xaxis_title="日期", yaxis_title="评分(1-5)",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)),
        yaxis=dict(range=[1, 5]), **layout)
    charts["satisfaction_daily"] = fig_html(fig)

    dist = sat["distribution"]
    fig = go.Figure(go.Bar(
        x=list(dist.keys()), y=list(dist.values()),
        marker_color=["#ef4444", "#f59e0b", "#fbbf24", "#84cc16", "#10b981"]))
    fig.update_layout(title="满意度评分分布(1-5)", xaxis_title="评分",
                     yaxis_title="工单数", **layout)
    charts["satisfaction_dist"] = fig_html(fig)

    # 6. channel
    ch = stats["channel"]
    fig = go.Figure()
    ch_colors = {"在线": "#2563eb", "电话": "#8b5cf6", "邮件": "#14b8a6"}
    for cn in ch["channels"]:
        fig.add_trace(go.Bar(
            x=dates, y=[ch["daily"][d][cn] for d in dates],
            name=cn, marker_color=ch_colors.get(cn, "#64748b")))
    fig.update_layout(
        barmode="stack", title="每日来源渠道堆叠",
        xaxis_title="日期", yaxis_title="工单数",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)), **layout)
    charts["channel_daily"] = fig_html(fig)

    fig = go.Figure(go.Pie(labels=list(ch["overall"].keys()),
                           values=list(ch["overall"].values()), hole=0.4))
    fig.update_layout(title="来源渠道总体占比", **layout)
    charts["channel_overall"] = fig_html(fig)

    # 7. is_resolved
    ir = stats["is_resolved"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=[ir["daily_rate"][d] * 100 for d in dates],
                             mode="lines+markers", name="解决率",
                             line=dict(color="#22c55e", width=3)))
    fig.update_layout(
        title="每日解决率趋势", xaxis_title="日期", yaxis_title="解决率(%)",
        xaxis=dict(tickmode=tick_strategy, nticks=len(dates)),
        yaxis=dict(range=[0, 100]), **layout)
    charts["resolved_daily"] = fig_html(fig)

    fig = go.Figure(go.Pie(
        labels=["已解决", "未解决"],
        values=[ir["resolved"], ir["unresolved"]],
        hole=0.4,
        marker_colors=["#22c55e", "#ef4444"]))
    fig.update_layout(title="整体解决情况", **layout)
    charts["resolved_overall"] = fig_html(fig)

    return charts


# ----------------------------------------------------------------------------
# HTML 渲染
# ----------------------------------------------------------------------------
def stats_table(rows):
    """rows: list of (label, value) tuples -> HTML table."""
    body = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows
    )
    return f'<table class="stat"><tbody>{body}</tbody></table>'


def build_section(dim, title, charts_html, table_html):
    analysis_ph = f"<!--ANALYSIS:{dim}-->"
    return f"""
    <section class="dim" id="{dim}">
      <div class="dim-head" onclick="toggleDim(this)">
        <span class="arrow">&#9662;</span><h2>{title}</h2>
      </div>
      <div class="dim-body">
        <div class="charts">{charts_html}</div>
        <div class="statwrap"><h3>关键统计</h3>{table_html}</div>
        <div class="analysis" data-dim="{dim}">
          <h3>分析结论</h3>
          <div class="analysis-body">{analysis_ph}</div>
        </div>
      </div>
    </section>
    """


def render_report(template_path, stats, charts, outdir):
    tpl = Path(template_path).read_text(encoding="utf-8")

    # 总览卡片
    total = stats["total"]
    rate = stats["is_resolved"]["rate"] * 100
    avg_sat = stats["satisfaction"]["overall_avg"]
    avg_rt = stats["resolution_time"]["overall_avg"]
    overview = f"""
      <div class="card"><div class="num">{total}</div><div class="lab">工单总数</div></div>
      <div class="card"><div class="num">{rate:.1f}%</div><div class="lab">整体解决率</div></div>
      <div class="card"><div class="num">{avg_sat}</div><div class="lab">平均满意度</div></div>
      <div class="card"><div class="num">{avg_rt}h</div><div class="lab">平均处理时长</div></div>
    """
    tpl = tpl.replace("{{OVERVIEW}}", overview)
    tpl = tpl.replace("{{DATE_RANGE}}",
                      f'{stats["date_range"].get("start","")} ~ {stats["date_range"].get("end","")}')

    sections = []

    # created_at
    c = stats["created_at"]
    ch = (charts["created_at_trend"] + charts["created_at_daytype"]
          + charts["created_at_slot"])
    tbl = stats_table([
        ("峰值日", f'{c["peak_date"]}（{c["peak_count"]} 单）'),
        ("工作日 / 周末 / 节假日",
         f'{c["day_type"].get("工作日",0)} / {c["day_type"].get("周末",0)} / {c["day_type"].get("节假日",0)}'),
        ("上午 / 下午 / 晚上",
         f'{c["time_slot"].get("上午",0)} / {c["time_slot"].get("下午",0)} / {c["time_slot"].get("晚上",0)}'),
        ("假期日期", "、".join(c["holiday_dates"]) or "无"),
    ])
    sections.append(build_section("created_at", "① 创建时间维度", ch, tbl))

    # category
    cat = stats["category"]
    ch = charts["category_daily"] + charts["category_overall"]
    tbl = stats_table([
        ("问题分类数", str(len(cat["categories"]))),
        ("最多分类", f'{cat["top"]}（{cat["top_count"]} 单）'),
    ])
    sections.append(build_section("category", "② 问题分类维度", ch, tbl))

    # priority
    p = stats["priority"]
    ch = charts["priority_daily"] + charts["priority_overall"]
    tbl = stats_table([
        ("高优先级工单", f'{p["high_count"]} 单（占比 {p["high_ratio"]*100:.1f}%）'),
        ("优先级分布", "、".join(f"{k}:{v}" for k, v in p["overall"].items())),
    ])
    sections.append(build_section("priority", "③ 优先级维度", ch, tbl))

    # resolution_time
    rt = stats["resolution_time"]
    ch = charts["resolution_daily"] + charts["resolution_by_cat"]
    tbl = stats_table([
        ("平均处理时长", f'{rt["overall_avg"]} h'),
        ("最长 / 最短", f'{rt["max"]} h / {rt["min"]} h'),
    ])
    sections.append(build_section("resolution_time", "④ 处理时长维度", ch, tbl))

    # satisfaction
    sat = stats["satisfaction"]
    ch = charts["satisfaction_daily"] + charts["satisfaction_dist"]
    tbl = stats_table([
        ("平均满意度", f'{sat["overall_avg"]} / 5'),
        ("低分(1-2)占比", f'{sat["low_score_ratio"]*100:.1f}%'),
    ])
    sections.append(build_section("satisfaction", "⑤ 满意度评分维度", ch, tbl))

    # channel
    chn = stats["channel"]
    ch = charts["channel_daily"] + charts["channel_overall"]
    miss = "、".join(chn["missing_channels"]) or "无"
    tbl = stats_table([
        ("渠道分布", "、".join(f"{k}:{v}" for k, v in chn["overall"].items())),
        ("数据中缺失渠道", miss),
    ])
    sections.append(build_section("channel", "⑥ 来源渠道维度", ch, tbl))

    # is_resolved
    ir = stats["is_resolved"]
    ch = charts["resolved_daily"] + charts["resolved_overall"]
    tbl = stats_table([
        ("已解决 / 未解决", f'{ir["resolved"]} / {ir["unresolved"]}'),
        ("整体解决率", f'{ir["rate"]*100:.1f}%'),
    ])
    sections.append(build_section("is_resolved", "⑦ 是否已解决维度", ch, tbl))

    tpl = tpl.replace("{{SECTIONS}}", "\n".join(sections))
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.html").write_text(tpl, encoding="utf-8")


def main():
    here = Path(__file__).parent
    ap = argparse.ArgumentParser(description="工单数据分析脚本")
    ap.add_argument("--input", required=True, help="工单 JSON 数据文件路径")
    ap.add_argument("--outdir", default="examples", help="输出目录（默认 examples，覆盖其下 report.html 与 stats.json）")
    ap.add_argument("--template", default=str(here.parent / "assets" / "report_template.html"),
                    help="HTML 模板路径")
    args = ap.parse_args()

    tickets = load_tickets(args.input)
    if not tickets:
        sys.exit("错误：数据源为空，无法生成报告。")
    stats, dates = analyze(tickets)
    # charts 需要 stats 已计算
    charts = build_charts(stats, dates)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    render_report(args.template, stats, charts, args.outdir)
    print(f"已生成：{out / 'report.html'}")
    print(f"已生成：{out / 'stats.json'}")
    print(f"工单总数：{stats['total']}，日期范围：{stats['date_range']}")


if __name__ == "__main__":
    main()
