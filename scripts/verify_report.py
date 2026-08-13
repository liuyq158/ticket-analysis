#!/usr/bin/env python3
"""
校验生成的 report.html 是否每个维度都已填写分析结论。

用法：
    python verify_report.py <report.html>

规则：
    1. 必须存在 7 个维度 section（created_at / category / priority /
       resolution_time / satisfaction / channel / is_resolved）。
    2. 每个 section 的 .analysis-body 内不能仍有 <!--ANALYSIS:...--> 占位符。
    3. 每个 .analysis-body 必须有非空文本内容（长度 > 10）。

缺少任一条件即退出码 1 并打印缺失项，供 Skill 工作流在交付前强制检查。
"""

import re
import sys
from pathlib import Path

REQUIRED_DIMS = [
    "created_at", "category", "priority", "resolution_time",
    "satisfaction", "channel", "is_resolved",
]


def verify(report_path):
    html = Path(report_path).read_text(encoding="utf-8")
    errors = []

    for dim in REQUIRED_DIMS:
        sec_match = re.search(rf'<section[^>]*id="{dim}"[^>]*>(.*?)</section>',
                              html, re.S)
        if not sec_match:
            errors.append(f"缺少维度 section: {dim}")
            continue

        sec = sec_match.group(1)
        body_match = re.search(
            r'<div class="analysis-body">(.*?)</div>', sec, re.S)
        if not body_match:
            errors.append(f"{dim}: 找不到分析结论容器")
            continue

        body = body_match.group(1).strip()
        placeholder = f"<!--ANALYSIS:{dim}-->"
        if placeholder in body:
            errors.append(f"{dim}: 分析结论占位符未替换")
        elif len(body) < 10:
            errors.append(f"{dim}: 分析结论内容过短或为空")

    if errors:
        print("[FAIL] 报告分析结论校验未通过：")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("[PASS] 全部 7 个维度的分析结论均已填写。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {Path(sys.argv[0]).name} <report.html>")
        sys.exit(2)
    sys.exit(verify(sys.argv[1]))
