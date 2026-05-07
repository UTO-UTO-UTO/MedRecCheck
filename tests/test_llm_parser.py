import unittest

from src.llm.parser import parse_scoring_response


class LlmParserTest(unittest.TestCase):
    def test_parse_json_inside_markdown_fence(self):
        result = parse_scoring_response(
            """```json
{"details":[{"rule_id":"1-2","score":6,"deduct":0,"passed":true,"evidence":"完整"}],"total_score":6,"total_deduct":0,"grade":"优秀"}
```"""
        )
        self.assertEqual(result["grade"], "优秀")
        self.assertEqual(result["details"][0]["rule_id"], "1-2")

    def test_missing_required_top_level_field_raises(self):
        with self.assertRaises(ValueError):
            parse_scoring_response('{"details":[],"total_score":0}')


if __name__ == "__main__":
    unittest.main()
