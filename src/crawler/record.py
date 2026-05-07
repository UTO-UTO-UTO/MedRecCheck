"""
病历抓取模块：逐个点击患者，进入病历详情页，提取关键字段内容。
"""

import re
from datetime import datetime
from playwright.async_api import Page


# 病历关键字段及其在页面中可能出现的标题关键词
RECORD_SECTIONS = {
    "chief_complaint": ["主诉"],
    "history_of_present_illness": ["现病史"],
    "past_history": ["既往史"],
    "examination": [ "口腔检查","辅助检查" ],
    "related_imaging": ["相关影像"],
    "diagnosis": ["诊断"],
    "treatment": ["处置"],
    "doctor_name": ["医生"],
    "notes": ["医嘱"],
}


# 病历日期固定为 yyyy-mm-dd hh:mm 格式,例如 2024-06-22 18:30
_DATETIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}")


def find_date_in_text(text: str) -> str:
    """从文本中提取病历日期 (yyyy-mm-dd hh:mm), 命中返回完整匹配, 否则返回 ""."""
    if not text:
        return ""
    m = _DATETIME_PATTERN.search(text)
    return m.group(0) if m else ""


def is_today(date_str: str) -> bool:
    """判断 yyyy-mm-dd hh:mm 格式日期是否为今天."""
    if not date_str:
        return False
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M").date() == datetime.now().date()
    except ValueError:
        return False


def _extract_section(raw_text: str, start_keywords: list[str], end_keywords: list[str]) -> str:
    """
    从 raw_text 中提取从 start_keywords 任一关键词开始，
    到 end_keywords 任一关键词结束（不包含）之间的文本。
    """
    if not raw_text:
        return ""

    # 找到起始位置（取最先出现的）
    start_idx = -1
    matched_len = 0
    for kw in start_keywords:
        idx = raw_text.find(kw)
        if idx != -1:
            if start_idx == -1 or idx < start_idx:
                start_idx = idx
                matched_len = len(kw)

    if start_idx == -1:
        return ""

    # 找到结束位置（下一个区块的开始，取最先出现的）
    end_idx = len(raw_text)
    for kw in end_keywords:
        idx = raw_text.find(kw, start_idx + matched_len)
        if idx != -1 and idx < end_idx:
            end_idx = idx

    return raw_text[start_idx:end_idx].strip()


async def extract_record_text(page: Page) -> dict:
    """
    从当前病历详情页提取各关键字段的文本内容。

    页面从上往下依次为主诉、口腔检查、诊断（可缺失）、处置。
    每部分独立，按关键词位置切分，避免把后续区块内容混入。

    Returns:
        {"chief_complaint": "...", "examination": "...", "treatment": "...", ...}
    """
    result = {key: "" for key in RECORD_SECTIONS}
    result["raw_text"] = ""

    # 给 SPA 渲染留出余地：等 body 文本里出现"主诉"再开始抓取（失败也不抛，兜底走原逻辑）
    try:
        await page.wait_for_function(
            "document.body && (document.body.innerText || document.body.textContent || '').includes('主诉')",
            timeout=6000,
        )
    except Exception:
        pass

    # 1. 获取完整页面文本（用于日期识别和 raw_text 截取）
    try:
        full_text = await page.locator("body").inner_text()
    except Exception:
        try:
            full_text = await page.evaluate(
                "() => document.body ? (document.body.textContent || '') : ''"
            )
        except Exception:
            full_text = ""

    result["full_text"] = full_text

    # 2. raw_text 直接从 full_text 中"主诉"开始截取，到"打印"为止，避免历史病历干扰
    idx = full_text.find("主诉")
    raw = full_text[idx:].strip() if idx != -1 else ""
    print_idx = raw.find("打印")
    if print_idx != -1:
        raw = raw[:print_idx + len("打印")].strip()
    result["raw_text"] = raw

    # 3. 精确检测"相关影像"区域内的图片（单独 JS evaluate，不依赖文本截取）
    # 策略：找到页面上文本恰好是"相关影像"的元素（取最靠前的，即当前病历），
    # 只在该元素及其直接父容器、相邻兄弟元素内搜索图片，避免向上扩散到 body。
    try:
        eval_result = await page.evaluate("""() => {
            const allEls = Array.from(document.body.querySelectorAll('*'));
            let candidates = [];

            for (const el of allEls) {
                const text = (el.textContent || '').trim();
                if (text === '相关影像' || text.startsWith('相关影像')) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        candidates.push({el, rect});
                    }
                }
            }

            if (candidates.length === 0) {
                return {hasImages: false, imageUrls: []};
            }

            // 取最靠前的（当前病历在页面上方）
            candidates.sort((a, b) => a.rect.top - b.rect.top);
            const target = candidates[0].el;

            const imageUrls = [];
            const addImg = (src) => {
                if (src && !src.startsWith('data:')) imageUrls.push(src);
            };
            const collectFrom = (root) => {
                if (!root) return;
                for (const img of root.querySelectorAll('img')) {
                    addImg(img.src || img.dataset.src || '');
                }
                const bg = window.getComputedStyle(root).backgroundImage;
                if (bg && bg !== 'none') {
                    const m = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
                    if (m && m[1]) addImg(m[1]);
                }
            };

            // 搜索范围：目标元素自身、父元素、下一个兄弟、父元素的下一个兄弟
            collectFrom(target);
            if (target.parentElement) collectFrom(target.parentElement);
            if (target.nextElementSibling) collectFrom(target.nextElementSibling);
            if (target.parentElement && target.parentElement.nextElementSibling) {
                collectFrom(target.parentElement.nextElementSibling);
            }

            const uniqueUrls = [...new Set(imageUrls)];
            return {hasImages: uniqueUrls.length > 0, imageUrls: uniqueUrls};
        }""")
        result['has_imaging_images'] = eval_result.get('hasImages', False)
        result['image_urls'] = eval_result.get('imageUrls', [])
    except Exception:
        result['has_imaging_images'] = False
        result['image_urls'] = []

    raw = result["raw_text"]
    if not raw:
        return result

    # 按区块切分（优先匹配较长的关键词，避免"检查"误匹配"口腔检查"）
    result["chief_complaint"] = _extract_section(
        raw, ["主诉"], ["现病史", "口腔检查", "诊断", "处置"]
    )
    if result["chief_complaint"]:
        result["chief_complaint"] = re.sub(
            r"^主诉\s*[:：]?\s*", "", result["chief_complaint"]
        ).strip()

    result["examination"] = _extract_section(
        raw, ["口腔检查"], ["辅助检查", "相关影像", "诊断", "处置"]
    )
    result["clinical_exam"] = result["examination"]

    # 辅助检查单独提取，结束标志为"相关影像"/"诊断"/"处置"中最早出现者
    result["auxiliary_exam"] = _extract_section(
        raw, ["辅助检查"], ["相关影像", "诊断", "处置"]
    )

    result["history_of_present_illness"] = _extract_section(
        raw, ["现病史"], ["既往史", "口腔检查", "诊断", "处置"]
    )
    result["past_history"] = _extract_section(
        raw, ["既往史"], ["口腔检查", "诊断", "处置"]
    )
    result["related_imaging"] = _extract_section(
        raw, ["相关影像"], ["诊断", "处置", "医嘱", "打印"]
    )
    if result["related_imaging"]:
        result["related_imaging"] = re.sub(
            r"^相关影像\s*[:：]?\s*", "", result["related_imaging"]
        ).strip()

    result["diagnosis"] = _extract_section(
        raw, ["诊断"], ["处置"]
    )
    result["treatment"] = _extract_section(
        raw, ["处置"], ["医嘱", "打印"]
    )

    # 医嘱作为处置的子模块单独抓取：从"医嘱"开始，到"打印"之前
    result["notes"] = _extract_section(raw, ["医嘱"], ["打印"])
    if result["notes"]:
        result["notes"] = re.sub(
            r"^医嘱\s*[:：]?\s*", "", result["notes"]
        ).strip()

    # doctor_name 仍尝试从 DOM 中精确定位
    for key in ["doctor_name"]:
        for kw in RECORD_SECTIONS[key]:
            heading_selectors = [
                f"h1:has-text('{kw}'), h2:has-text('{kw}'), h3:has-text('{kw}')",
                f"th:has-text('{kw}'), label:has-text('{kw}'), .section-title:has-text('{kw}')",
                f".el-form-item__label:has-text('{kw}'), .title:has-text('{kw}')",
            ]
            heading = None
            for sel in heading_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    heading = loc
                    break
            if not heading:
                continue
            try:
                next_sibling = heading.locator("+ *")
                if await next_sibling.count() > 0:
                    content = await next_sibling.inner_text()
                    if content and content.strip():
                        result[key] = content.strip()
                        break
            except Exception:
                pass

    return result


async def fetch_patient_record(
    page: Page,
    patient: dict,
) -> dict:
    """
    点击工作台中的患者姓名，在当前页跳转至电子病历，抓取数据后返回工作台。

    通过病历日期判定是否为当日病历——非当日 / 无病历 / 未识别到日期均置 skipped=True。
    日期严格匹配 yyyy-mm-dd hh:mm 格式,未命中即视为无病历(避免历史病历误评)。

    Args:
        page: 当前工作台页面
        patient: {"name": str, "index": int}

    Returns:
        包含 patient_name、record 等字段的字典：
        - 当日病历：record 含完整字段，附 visit_date
        - 非当日 / 无病历 / 未识别到日期：record={}，skipped=True，skip_reason=...
    """
    name = patient["name"]
    idx = patient.get("index", 0)
    print(f"[record] [{idx+1}] 正在抓取患者: {name}")

    # 定位患者并点击
    patient_locator = page.locator("a.patient-name.auto-close-popup").nth(idx)
    if await patient_locator.count() == 0:
        patient_locator = page.locator(f"a.patient-name.auto-close-popup:has-text('{name}')").first
        if await patient_locator.count() == 0:
            patient_locator = page.locator(f"text='{name}'").first

    await patient_locator.click()

    # 等待病历页面加载（SPA 跳转，当前页变化）
    await page.wait_for_timeout(1500)
    jumped = False
    try:
        await page.wait_for_url("**/*record**", timeout=8000)
        jumped = True
    except Exception:
        try:
            # body 文本中出现"主诉"即视为病历区域已渲染
            # 注意：原写法 page.locator("text='主诉', text='检查', ...") 在 Playwright 中
            # 逗号会被当作 text 字符串字面量而非 OR，必然超时——改用 wait_for_function 替代
            await page.wait_for_function(
                "document.body && (document.body.innerText || document.body.textContent || '').includes('主诉')",
                timeout=8000,
            )
            jumped = True
        except Exception:
            pass

    record_data = await extract_record_text(page)
    raw_text = (record_data.get("raw_text") or "").strip()

    async def _go_back():
        await page.go_back(wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

    # 病历内容为空 → 视为无病历
    if not raw_text:
        print(f"[record] [{idx+1}] {name} jumped={jumped} visit_date=- → skipped: 未提取到病历内容")
        await _go_back()
        return {
            "patient_name": name,
            "patient_id": patient.get("id"),
            "record": {},
            "skipped": True,
            "skip_reason": "未提取到病历内容",
        }

    # 在完整页面文本中提取病历日期 (yyyy-mm-dd hh:mm)
    date_str = find_date_in_text(record_data.get("full_text") or "")

    # 未识别到日期 → 跳过 (避免历史病历被误判为当日)
    if not date_str:
        print(f"[record] [{idx+1}] {name} jumped={jumped} visit_date=- → skipped: 未识别到病历日期")
        await _go_back()
        return {
            "patient_name": name,
            "patient_id": patient.get("id"),
            "record": {},
            "skipped": True,
            "skip_reason": "未识别到病历日期",
        }

    # 非今日 → 跳过
    if not is_today(date_str):
        reason = f"病历日期非今日: {date_str}"
        print(f"[record] [{idx+1}] {name} jumped={jumped} visit_date={date_str} → skipped: {reason}")
        await _go_back()
        return {
            "patient_name": name,
            "patient_id": patient.get("id"),
            "record": {},
            "skipped": True,
            "skip_reason": reason,
        }

    # 当日病历 → 正常评分
    print(f"[record] [{idx+1}] {name} jumped={jumped} visit_date={date_str} → evaluate")
    await _go_back()
    return {
        "patient_name": name,
        "patient_id": patient.get("id"),
        "record": record_data,
        "visit_date": date_str,
    }


async def crawl_all_records(page: Page, patients: list[dict]) -> list[dict]:
    """
    批量抓取所有患者的病历。非当日 / 无病历以 skipped=True 标记，
    由下游评分流程统一处理为"无病历"等级，不在抓取阶段过滤。

    Args:
        page: 已登录并已加载工作台列表的页面
        patients: get_patient_list 返回的患者列表

    Returns:
        全量患者数据列表（含 skipped 标记）
    """
    records = []

    for patient in patients:
        try:
            data = await fetch_patient_record(page, patient)
            records.append(data)
        except Exception as e:
            print(f"[record] 抓取患者 {patient.get('name')} 失败: {e}")
            records.append({
                "patient_name": patient.get("name"),
                "patient_id": patient.get("id"),
                "record": {},
                "error": str(e),
            })
        # 适当延迟，避免请求过快
        await page.wait_for_timeout(800)

    return records
