#!/usr/bin/env python3
# 用途：读取评分明细 JSON，生成带 ECharts 的 HTML 报告并自动打开浏览器
# 参数：无（输入输出路径读取自 src/config.py）
# 输出：stdout 输出报告生成路径；自动调用系统默认浏览器打开报告
# 退出码：0=成功，1=出错
# Known Issues：
#   - 若 .tmp/scored_records.json 不存在，需先运行 score_records.py
#   - 自动打开浏览器依赖操作系统 webbrowser 模块，无图形界面环境可能失效

import json
import os
import sys
import webbrowser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.config import SCORED_FILE, REPORT_FILE
from src.report.generator import generate_report


def main() -> int:
    if not os.path.exists(SCORED_FILE):
        print(f"[report] 错误：未找到评分文件 {SCORED_FILE}，请先运行 score_records.py")
        return 1

    print(f"[report] 读取评分数据: {SCORED_FILE}")
    with open(SCORED_FILE, "r", encoding="utf-8") as f:
        scored_records = json.load(f)

    if not scored_records:
        print("[report] 评分结果为空，无需生成报告")
        return 2

    try:
        generate_report(scored_records, REPORT_FILE)
    except Exception as e:
        print(f"[report] 生成报告失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 自动打开浏览器
    abs_path = os.path.abspath(REPORT_FILE)
    file_url = "file://" + abs_path
    print(f"[report] 正在打开浏览器: {file_url}")
    opened = webbrowser.open(file_url)
    if not opened:
        print(f"[report] 警告：未能自动打开浏览器，请手动打开: {file_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
