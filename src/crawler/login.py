"""
登录模块：封装 Playwright 登录流程，保存登录态以便复用。
"""

from playwright.async_api import async_playwright
from src.config import LOGIN_URL, USERNAME, PASSWORD, STORAGE_STATE, require_login_config


async def perform_login(headless: bool = False, timeout_ms: int = 60000) -> None:
    """
    打开浏览器，访问登录页，填写账号密码并登录，保存 storage state 到文件。

    Args:
        headless: 是否无头模式。首次运行建议 False 以便观察登录过程。
        timeout_ms: 页面导航超时（毫秒），默认 60000。
    """
    require_login_config()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"[login] 正在访问登录页: {LOGIN_URL} (超时: {timeout_ms}ms)")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        # 等待 Angular SPA 渲染出登录表单（避免 JS 异步加载导致选择器找不到元素）
        username_loc = page.locator("input[placeholder*='用户名'], input[placeholder*='账号'], #username, input[name='username']").first
        password_loc = page.locator("input[placeholder*='密码'], input[type='password'], #password, input[name='password']").first
        try:
            await username_loc.wait_for(state="visible", timeout=15000)
            await password_loc.wait_for(state="visible", timeout=15000)
        except Exception as e:
            print(f"[login] 警告：等待登录表单超时: {e}")

        # 填写账号密码（使用占位符文本匹配，兼容多种选择器）
        await username_loc.fill(USERNAME)
        await password_loc.fill(PASSWORD)

        # 勾选用户协议（若页面存在且未勾选）
        agreement_locator = page.locator(
            "label:has-text('我已阅读并同意'), "
            "span:has-text('我已阅读并同意'), "
            ".el-checkbox__label:has-text('我已阅读并同意'), "
            ".agreement:has-text('我已阅读并同意')"
        ).first
        if await agreement_locator.count() > 0:
            checkbox = agreement_locator.locator("input[type='checkbox']").first
            if await checkbox.count() > 0:
                try:
                    is_checked = await checkbox.is_checked()
                except Exception:
                    is_checked = False
                if not is_checked:
                    await checkbox.click()
                    print("[login] 已勾选用户协议")
            else:
                await agreement_locator.click()
                print("[login] 已勾选用户协议")

        # 点击登录按钮（优先精确 ID，再按文本匹配；显式排除移动端隐藏按钮）
        login_btn = page.locator(
            "#login-button, "
            "button:has-text('登 录'):not(#mobile-login-button), "
            "button:has-text('登录'):not(#mobile-login-button), "
            "button[type='submit']:not(#mobile-login-button), "
            ".login-btn:not(#mobile-login-button), "
            ".btn-login:not(#mobile-login-button)"
        ).first
        print("[login] 点击登录...")
        await login_btn.click()

        # 等待登录成功：URL 变化或工作台元素出现（最多 15 秒）
        try:
            await page.wait_for_url("**/dashboard**", timeout=15000)
        except Exception:
            # 有些系统登录后不一定跳转到 /dashboard，尝试等待工作台特征元素
            await page.locator("text='工作台', text='患者', .dashboard, .workbench").first.wait_for(timeout=15000)

        print("[login] 登录成功，保存登录态...")
        await context.storage_state(path=STORAGE_STATE)
        await browser.close()
        print(f"[login] 登录态已保存至: {STORAGE_STATE}")


async def new_context_with_auth(browser):
    """
    基于已保存的 storage state 创建新浏览器上下文，复用登录态。

    Args:
        browser: Playwright Browser 实例

    Returns:
        Playwright 浏览器上下文
    """
    import os
    if not os.path.exists(STORAGE_STATE):
        raise FileNotFoundError(f"登录态文件不存在: {STORAGE_STATE}，请先执行登录")
    return await browser.new_context(storage_state=STORAGE_STATE)


async def verify_and_refresh_auth(p, browser, headless: bool = False, timeout_ms: int = 60000):
    """
    验证已保存的登录态是否仍然有效。若被重定向到登录页则删除旧状态并重新登录。

    Args:
        p: Playwright 实例
        browser: 当前 Browser 实例
        headless: 重新登录时是否使用无头模式
        timeout_ms: 页面导航超时（毫秒），默认 60000

    Returns:
        (browser, context) 元组，browser 可能是重新启动后的新实例
    """
    import os
    from src.config import BASE_URL

    temp_context = await browser.new_context(storage_state=STORAGE_STATE)
    temp_page = await temp_context.new_page()

    print(f"[auth] 验证登录态有效性... (超时: {timeout_ms}ms)")
    await temp_page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    await temp_page.wait_for_timeout(2500)

    pwd_loc = temp_page.locator("input[type='password'], #password, input[name='password']")
    login_btn_loc = temp_page.locator("#login-button, button:has-text('登录'), button[type='submit']")
    is_expired = await pwd_loc.count() > 0 and await login_btn_loc.count() > 0

    await temp_context.close()

    if is_expired:
        print("[auth] 登录态已过期，需要重新登录")
        await browser.close()
        if os.path.exists(STORAGE_STATE):
            os.remove(STORAGE_STATE)
            print(f"[auth] 已删除旧登录态: {STORAGE_STATE}")
        await perform_login(headless=headless, timeout_ms=timeout_ms)
        browser = await p.chromium.launch(headless=headless)
    else:
        print("[auth] 登录态有效")

    context = await new_context_with_auth(browser)
    return browser, context
