import unittest

from src.scorer import checks


def make_record(**fields):
    return {"record": fields}


class ScorerChecksTest(unittest.TestCase):
    def test_optional_history_fields_do_not_deduct_when_missing(self):
        record = make_record()
        self.assertTrue(checks.check_history_of_present_illness(record, "history_of_present_illness")[0])
        self.assertTrue(checks.check_past_history(record, "past_history")[0])
        self.assertTrue(checks.check_diagnosis(record, "diagnosis")[0])

    def test_auxiliary_exam_requires_related_image_when_present(self):
        record = make_record(
            auxiliary_exam="辅助检查：2026-04-29 CBCT 显示36根尖低密度影",
            related_imaging="CBCT文本",
            has_imaging_images=False,
        )
        passed, evidence = checks.check_related_imaging(record, "related_imaging")
        self.assertFalse(passed)
        self.assertIn("无实际影像图片", evidence)

    def test_doctor_advice_rejects_vague_followup_without_time(self):
        record = make_record(notes="不适随诊，注意口腔卫生")
        passed, evidence = checks.check_doctor_advice(record, "notes")
        self.assertFalse(passed)
        self.assertIn("未记录复诊时间", evidence)

    def test_chief_complaint_requires_three_elements(self):
        record = make_record(chief_complaint="左下后牙疼痛3天")
        self.assertTrue(checks.check_chief_complaint_elements(record, "chief_complaint")[0])


if __name__ == "__main__":
    unittest.main()
