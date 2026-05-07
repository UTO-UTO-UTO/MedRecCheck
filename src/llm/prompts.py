"""
LLM 评分 Prompt 模板。
将督查标准与病历文本组合为结构化 Prompt，要求模型返回固定 JSON 格式。
"""

from src.scorer.rules import RULES, get_total_score


_SYSTEM_INSTRUCTION = """你是一位口腔医院病历质量督查专家。请根据《口腔门诊病历质量督查表（复诊）》对给定病历进行逐项评分。

评分原则：
- 严格依据标准，存在疑问时倾向于"扣分"并说明原因。
- 若某项内容在病历中完全缺失，该项得 0 分。
- 若内容存在但不符合标准描述，根据不符合程度酌情扣分。
- 输出必须使用中文。

输出格式（严格 JSON，不要添加 markdown 代码块标记，evidence 中不要包含换行符或引号）：
{
  "details": [
    {
      "rule_id": "细项编号",
      "score": 得分整数,
      "deduct": 扣分整数,
      "passed": true/false,
      "evidence": "评分依据/扣分原因简述（单行文本，不要换行）"
    }
  ],
  "total_score": 总分整数,
  "total_deduct": 扣分总和整数,
  "grade": "优秀/一般/需注意/不合格",
  "manual_review_items": [],
  "summary": "对该病历质量的简短总体评价（1-2句话）"
}

评级规则（按扣分划分）：
- 扣分 0–5 分 → 优秀
- 扣分 6–10 分 → 一般
- 扣分 11–20 分 → 需注意
- 扣分 21 分以上 → 不合格
"""


def _build_rules_text() -> str:
    lines = ["评分标准明细："]
    for rule in RULES:
        lines.append(
            f"- {rule.id} ({rule.category_name})：{rule.description} — 满分 {rule.score} 分"
        )
    lines.append(f"\n满分总计：{get_total_score()} 分")
    return "\n".join(lines)


def build_scoring_prompt(record: dict) -> str:
    """
    为单份病历构造评分 Prompt。

    Args:
        record: {"patient_name": "...", "record": {"chief_complaint": "...", ...}}

    Returns:
        完整的 user prompt 字符串
    """
    patient_name = record.get("patient_name", "未知患者")
    rec = record.get("record", {})

    sections = []
    for key, label in [
        ("chief_complaint", "主诉"),
        ("history_of_present_illness", "现病史"),
        ("past_history", "既往史"),
        ("clinical_exam", "临床检查"),
        ("auxiliary_exam", "辅助检查"),
        ("related_imaging", "相关影像"),
        ("diagnosis", "诊断"),
        ("treatment", "处理/治疗"),
        ("doctor_name", "医生"),
        ("notes", "医嘱/注意事项"),
    ]:
        text = rec.get(key, "")
        if text:
            sections.append(f"【{label}】\n{text}")

    # 额外传递图片信息
    if rec.get("has_imaging_images"):
        sections.append("【相关影像图片】有")
    else:
        sections.append("【相关影像图片】无")

    raw_text = rec.get("raw_text", "")
    if not sections and raw_text:
        sections.append(f"【病历全文】\n{raw_text}")

    record_text = "\n\n".join(sections) if sections else "（病历内容为空）"

    prompt = f"""患者姓名：{patient_name}

病历内容：
{record_text}

{_build_rules_text()}

请对上述病历逐项评分，并返回要求的 JSON 格式。"""

    return prompt


def get_system_message() -> str:
    """返回 system message 内容。"""
    return _SYSTEM_INSTRUCTION
