"""
工作台模块：复用登录态进入工作台，勾选筛选条件，获取患者列表。
"""

from playwright.async_api import Page
from src.config import BASE_URL

DASHBOARD_PATH = ""


async def navigate_to_dashboard(page: Page) -> None:
    """进入工作台页面并等待加载完成。"""
    url = f"{BASE_URL}{DASHBOARD_PATH}"
    print(f"[dashboard] 进入工作台: {url}")
    await page.goto(url, wait_until="domcontentloaded")
    # Angular SPA 渲染较慢，额外等待确保动态内容加载
    await page.wait_for_timeout(3000)


async def apply_filters(page: Page) -> None:
    """
    勾选「包含已离开」和「包含已结账」复选框。
    直接通过 input 元素的 ng-model 属性定位。
    """
    checkboxes = [
        ("input[ng-model='criteria.includeLeft']", "包含已离开"),
        ("input[ng-model='criteria.includeCharged']", "包含已结账"),
    ]

    for selector, text in checkboxes:
        try:
            await page.locator(selector).check()
            print(f"[dashboard] 已勾选「{text}」")
        except Exception:
            print(f"[dashboard] 警告：未找到筛选项「{text}」，跳过")

    # 等待列表刷新
    print("[dashboard] 等待列表刷新...")
    await page.wait_for_timeout(1500)


async def set_page_size(page: Page, size: int = 100) -> None:
    """
    在工作台底部分页控件设置每页显示患者数量。
    优先通过 Kendo UI JavaScript API 直接设置，避免 DOM 点击模拟失效。
    """
    try:
        # 滚动到页面底部，确保分页控件进入视口
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(800)

        # 方案 A：直接通过 Kendo UI JS API 设置 pageSize（最可靠）
        js_result = await page.evaluate(f"""(targetSize) => {{
            const $ = window.jQuery || window.$;
            if (!$) return {{ ok: false, reason: "jQuery 未加载" }};

            // 1) 尝试 kendoGrid
            const grids = document.querySelectorAll('.k-grid, [data-role="grid"]');
            for (const g of grids) {{
                const w = $(g).data('kendoGrid');
                if (w && w.dataSource) {{
                    w.dataSource.pageSize(targetSize);
                    return {{ ok: true, method: "kendoGrid" }};
                }}
            }}

            // 2) 尝试 kendoPager
            const pagers = document.querySelectorAll('.k-pager-wrap, .k-pager, [data-role="pager"]');
            for (const p of pagers) {{
                const w = $(p).data('kendoPager');
                if (w && w.pageSize) {{
                    w.pageSize(targetSize);
                    return {{ ok: true, method: "kendoPager" }};
                }}
            }}

            // 3) 尝试分页相关的 kendoDropDownList
            const dropdowns = document.querySelectorAll('select[data-role="dropdownlist"]');
            for (const d of dropdowns) {{
                const w = $(d).data('kendoDropDownList');
                if (!w) continue;
                const inPager = d.closest('.k-pager-wrap, .k-pager') !== null;
                const items = w.dataSource ? w.dataSource.data() : [];
                for (let i = 0; i < items.length; i++) {{
                    const val = items[i] && items[i].value !== undefined ? String(items[i].value) : String(items[i]);
                    if (val === String(targetSize)) {{
                        w.select(i);
                        w.trigger('change');
                        return {{ ok: true, method: "kendoDropDownList" }};
                    }}
                }}
            }}

            return {{ ok: false, reason: "未找到 Kendo 分页组件" }};
        }}""", size)

        if js_result and js_result.get("ok"):
            print(f"[dashboard] 通过 Kendo JS API ({js_result['method']}) 设置每页显示 {size} 条")
            await page.wait_for_timeout(1500)
            return
        else:
            print(f"[dashboard] Kendo JS API 不可用: {js_result.get('reason') if js_result else '未知'}，回退到 DOM 模拟点击")

        # 方案 B：回退到 DOM 模拟点击（原有逻辑）
        await page.locator("span.k-icon.k-i-arrow-s").last.click(timeout=5000)
        await page.locator(".k-popup").first.wait_for(state="visible", timeout=5000)
        await page.wait_for_timeout(1200)

        clicked = False
        for sel in [
            f"li.k-item:has-text('{size}')",
            f".k-list .k-item:has-text('{size}')",
            f"li[role='option']:has-text('{size}')",
            f".k-popup li:has-text('{size}')",
        ]:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                try:
                    await loc.click(timeout=3000)
                    clicked = True
                    break
                except Exception:
                    try:
                        await loc.click(force=True, timeout=3000)
                        clicked = True
                        break
                    except Exception:
                        continue

        if not clicked:
            try:
                await page.get_by_text(str(size), exact=False).first.click(timeout=3000)
                clicked = True
            except Exception:
                pass

        if not clicked:
            try:
                js_clicked = await page.evaluate(f"""() => {{
                    const items = document.querySelectorAll('.k-popup li, .k-list .k-item, li[role="option"]');
                    for (const item of items) {{
                        if (item.textContent.trim() === '{size}') {{
                            item.click();
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                if js_clicked:
                    clicked = True
                    print(f"[dashboard] 通过 JS 模拟点击选择了 {size}")
            except Exception:
                pass

        if clicked:
            print(f"[dashboard] 已选择每页显示 {size} 条")
        else:
            print(f"[dashboard] 警告：未能在弹出层中找到选项 {size}")
        await page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[dashboard] 警告：设置每页显示数量失败: {e}")


async def get_patient_list(page: Page) -> list[dict]:
    """
    从工作台提取患者列表。

    Returns:
        患者字典列表，每个字典包含 name 和可选的 id/link。
        例如：[{"name": "张三", "id": "12345"}, ...]
    """
    patients = []

    # 优先使用已知的精确选择器 a.patient-name.auto-close-popup
    patient_anchors = await page.locator("a.patient-name.auto-close-popup").all()
    if patient_anchors:
        print(f"[dashboard] 找到 {len(patient_anchors)} 个患者")
        import re
        for i, anchor in enumerate(patient_anchors):
            name = await anchor.text_content()
            name = name.strip() if name else None

            # 从 ng-click 属性提取患者 ID，例如 goToPatient(1922371)
            id_val = None
            ng_click = await anchor.get_attribute("ng-click")
            if ng_click:
                m = re.search(r"goToPatient\((\d+)\)", ng_click)
                if m:
                    id_val = m.group(1)

            if name:
                patients.append({"name": name, "id": id_val, "index": i})

        print(f"[dashboard] 共提取 {len(patients)} 位患者")
        return patients

    # 回退：尝试多种常见列表项选择器
    selectors = [
        ".patient-list .patient-item",
        ".patient-list-item",
        ".el-table__row",
        "tr[data-patient-id]",
        ".patient-card",
        ".list-item:has(.patient-name)",
    ]

    items = None
    for sel in selectors:
        items = page.locator(sel)
        count = await items.count()
        if count > 0:
            print(f"[dashboard] 使用选择器 '{sel}' 找到 {count} 个患者")
            break

    if items is None or await items.count() == 0:
        # 最后尝试直接根据患者姓名字段反查
        name_locators = await page.locator(".patient-name, .name, td:nth-child(2) a, .user-name").all()
        names = [await n.text_content() for n in name_locators]
        names = [n.strip() for n in names if n and n.strip()]
        print(f"[dashboard] 通过姓名字段找到 {len(names)} 个患者")
        patients = [{"name": n, "id": None, "index": i} for i, n in enumerate(names)]
        return patients

    count = await items.count()
    for i in range(count):
        item = items.nth(i)
        # 尝试提取姓名
        name_el = item.locator(".patient-name, .name, .user-name, td").first
        name = await name_el.text_content() if await name_el.count() > 0 else None
        name = name.strip() if name else None

        # 尝试提取ID或链接
        id_val = None
        link_el = item.locator("a, [href]").first
        if await link_el.count() > 0:
            href = await link_el.get_attribute("href")
            id_val = href

        if name:
            patients.append({"name": name, "id": id_val, "index": i})

    print(f"[dashboard] 共提取 {len(patients)} 位患者")
    return patients
