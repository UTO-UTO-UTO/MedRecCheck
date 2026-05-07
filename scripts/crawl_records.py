#!/usr/bin/env python3
# 用途：自动登录 shhy.linkedcare.cn，批量抓取所有可见患者的电子病历，输出 JSON
# 参数：无（配置读取自 src/config.py）
# 输出：stdout 输出抓取到的患者数量与保存路径；.tmp/records.json 为结果文件
# 退出码：0=成功，1=出错
# Known Issues：
#   - 若目标网站页面结构大幅调整，选择器可能失效，需同步更新 src/crawler/ 下的页面定位逻辑
#   - 首次运行若未保存登录态，会自动调用登录流程并弹出浏览器窗口

import asyncio
import json
import os
import sys

# 将项目根目录加入路径，以便导入 src 模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright
from src.config import RECORDS_FILE, STORAGE_STATE
from src.crawler.login import perform_login, verify_and_refresh_auth
from src.crawler.dashboard import navigate_to_dashboard, apply_filters, set_page_size, get_patient_list
from src.crawler.record import crawl_all_records


async def main() -> int:
    # 确保 .tmp 目录存在
    os.makedirs(os.path.dirname(RECORDS_FILE) or ".tmp", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        # 检查登录态
        if not os.path.exists(STORAGE_STATE):
            print("[crawl] 未找到登录态，先执行登录...")
            await browser.close()
            await perform_login(headless=False)
            browser = await p.chromium.launch(headless=False)

        browser, context = await verify_and_refresh_auth(p, browser, headless=False)
        page = await context.new_page()

        try:
            # 进入工作台
            await navigate_to_dashboard(page)

            # 应用筛选
            await apply_filters(page)

            # 设置每页显示数量为 100
            await set_page_size(page, size=100)

            # 获取患者列表
            patients = await get_patient_list(page)
            if not patients:
                print("[crawl] 未在工作台找到任何患者，流程结束")
                with open(RECORDS_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                await browser.close()
                return 2

            # 批量抓取病历
            records = await crawl_all_records(page, patients)

            # 保存结果
            with open(RECORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

            success_count = sum(1 for r in records if not r.get("error"))
            print(f"[crawl] 完成：共 {len(records)} 位患者，成功 {success_count} 位")
            print(f"[crawl] 结果已保存至: {RECORDS_FILE}")
            await browser.close()
            return 0

        except Exception as e:
            print(f"[crawl] 错误: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
