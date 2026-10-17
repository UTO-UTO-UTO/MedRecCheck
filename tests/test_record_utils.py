import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.crawler.dashboard import apply_filters
from src.crawler.record import (
    _extract_section,
    crawl_all_records,
    find_date_in_text,
    is_today,
    restore_dashboard,
)


class RecordUtilsTest(unittest.TestCase):
    def test_find_date_in_text_requires_strict_minute_format(self):
        text = "患者今日就诊，病历时间 2026-04-29 09:30，主诉牙痛。"
        self.assertEqual(find_date_in_text(text), "2026-04-29 09:30")
        self.assertEqual(find_date_in_text("2026/04/29 09:30"), "")

    def test_is_today_uses_current_date(self):
        class FixedDatetime(datetime):
            @classmethod
            def now(cls):
                return cls(2026, 4, 29, 12, 0)

        with patch("src.crawler.record.datetime", FixedDatetime):
            self.assertTrue(is_today("2026-04-29 09:30"))
            self.assertFalse(is_today("2026-04-28 09:30"))
            self.assertFalse(is_today(""))

    def test_extract_section_stops_at_next_heading(self):
        raw = "主诉 左下后牙疼痛3天\n口腔检查 36叩痛\n诊断 牙髓炎\n处置 开髓处理"
        self.assertEqual(
            _extract_section(raw, ["主诉"], ["口腔检查", "诊断", "处置"]),
            "主诉 左下后牙疼痛3天",
        )


class RecordNavigationTest(unittest.IsolatedAsyncioTestCase):
    async def test_apply_filters_skips_missing_selectors_without_waiting(self):
        page = MagicMock()
        missing = MagicMock()
        missing.count = AsyncMock(return_value=0)
        missing.check = AsyncMock()
        page.locator.return_value = missing
        page.wait_for_timeout = AsyncMock()

        await apply_filters(page)

        self.assertEqual(missing.count.await_count, 2)
        missing.check.assert_not_awaited()
        page.wait_for_timeout.assert_awaited_once_with(1500)

    async def test_restore_dashboard_reapplies_filters_before_page_size(self):
        page = MagicMock()
        page.url = "https://shhy.linkedcare.cn/ares3/#/record/123"
        page.go_back = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        with (
            patch("src.crawler.dashboard.navigate_to_dashboard", new=AsyncMock()) as navigate,
            patch("src.crawler.dashboard.apply_filters", new=AsyncMock()) as filters,
            patch("src.crawler.dashboard.set_page_size", new=AsyncMock()) as page_size,
        ):
            await restore_dashboard(page)

        page.go_back.assert_awaited_once_with(wait_until="domcontentloaded", timeout=15000)
        navigate.assert_not_awaited()
        filters.assert_awaited_once_with(page)
        page_size.assert_awaited_once_with(page, size=100)

    async def test_restore_dashboard_uses_direct_navigation_outside_record_page(self):
        page = MagicMock()
        page.url = "https://shhy.linkedcare.cn/ares3/#/dashboard"
        with (
            patch("src.crawler.dashboard.navigate_to_dashboard", new=AsyncMock()) as navigate,
            patch("src.crawler.dashboard.apply_filters", new=AsyncMock()),
            patch("src.crawler.dashboard.set_page_size", new=AsyncMock()),
        ):
            await restore_dashboard(page)

        navigate.assert_awaited_once_with(page)
        page.go_back.assert_not_called()

    async def test_crawl_recovers_dashboard_after_patient_error(self):
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        failure = RuntimeError("患者链接已不在当前分页")

        with (
            patch("src.crawler.record.fetch_patient_record", new=AsyncMock(side_effect=failure)),
            patch("src.crawler.record.restore_dashboard", new=AsyncMock()) as restore,
        ):
            records = await crawl_all_records(page, [{"name": "张三", "id": "1", "index": 8}])

        restore.assert_awaited_once_with(page)
        self.assertEqual(records[0]["patient_name"], "张三")
        self.assertIn("当前分页", records[0]["error"])


if __name__ == "__main__":
    unittest.main()
