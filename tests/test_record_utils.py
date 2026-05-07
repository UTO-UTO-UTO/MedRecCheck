import unittest
from datetime import datetime
from unittest.mock import patch

from src.crawler.record import _extract_section, find_date_in_text, is_today


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


if __name__ == "__main__":
    unittest.main()
