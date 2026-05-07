#!/usr/bin/env python3
# 用途：读取抓取的病历 JSON，按督查表规则逐项评分，输出评分明细 JSON
# 参数：无（输入输出路径读取自 src/config.py）
# 输出：stdout 输出评分汇总；.tmp/scored_records.json 为结果文件
# 退出码：0=成功，1=出错
# Known Issues：
#   - 若 .tmp/records.json 不存在，需先运行 crawl_records.py
#   - 评分规则为近似自动化，部分项目标记为 manual 需人工复核
#   - LLM 评分需要配置 API Key；未配置时自动回退到确定性规则评分

import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.config import RECORDS_FILE, SCORED_FILE, LLM_PROVIDER, LLM_MODEL
from src.llm import client
from src.scorer.engine import evaluate_all


async def main() -> int:
    if not os.path.exists(RECORDS_FILE):
        print(f"[score] 错误：未找到病历文件 {RECORDS_FILE}，请先运行 crawl_records.py")
        return 1

    print(f"[score] 读取病历数据: {RECORDS_FILE}")
    with open(RECORDS_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        print("[score] 病历列表为空，无需评分")
        os.makedirs(os.path.dirname(SCORED_FILE) or ".tmp", exist_ok=True)
        with open(SCORED_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return 2

    if client.is_configured():
        print(f"[score] LLM 已配置（Provider: {LLM_PROVIDER}, Model: {LLM_MODEL}），将使用大模型评分")
    else:
        print("[score] 警告：LLM 未配置（缺少 API Key 或 Provider 不合法），将回退到确定性规则评分")

    print(f"[score] 开始对 {len(records)} 份病历进行评分...")
    results = await evaluate_all(records)

    # 保存评分结果
    os.makedirs(os.path.dirname(SCORED_FILE) or ".tmp", exist_ok=True)
    with open(SCORED_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 输出汇总
    grade_counts = {}
    for r in results:
        g = r["grade"]
        grade_counts[g] = grade_counts.get(g, 0) + 1

    print("[score] 评分完成，汇总如下:")
    for g, c in sorted(grade_counts.items()):
        print(f"         {g}: {c} 份")
    print(f"[score] 结果已保存至: {SCORED_FILE}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
