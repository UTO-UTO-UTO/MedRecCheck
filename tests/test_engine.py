import unittest

from src.scorer.engine import evaluate_record
from src.scorer.rules import get_total_score


class EngineTest(unittest.IsolatedAsyncioTestCase):
    async def test_skipped_record_is_reported_as_no_record(self):
        result = await evaluate_record({
            "patient_name": "张三",
            "patient_id": "p1",
            "record": {},
            "skipped": True,
            "skip_reason": "未识别到病历日期",
        })

        self.assertEqual(result["grade"], "无病历")
        self.assertEqual(result["total_score"], 0)
        self.assertEqual(result["full_score"], get_total_score())
        self.assertEqual(result["skip_reason"], "未识别到病历日期")


if __name__ == "__main__":
    unittest.main()
