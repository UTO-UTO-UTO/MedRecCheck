"""
LLM 评分响应解析器。
将 LLM 返回的文本（期望为 JSON）解析为结构化评分结果。
"""

import json
import re
from typing import Optional


def _sanitize_json_string(text: str) -> str:
    """修复 LLM 返回的 JSON 中常见的字符串格式错误。"""
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == '\\':
            result.append(ch)
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch in '\n\r':
            result.append('\\n')
            continue
        result.append(ch)
    return ''.join(result)


def _extract_json(text: str) -> Optional[str]:
    """从可能包含 markdown 代码块或多余文本的字符串中提取 JSON。"""
    text = text.strip()

    # 1) 尝试直接解析
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 2) 提取 markdown 代码块（提取块内全部内容，再验证 JSON）
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 3) 智能查找 JSON：从每个 { 开始，优先匹配最长的（最外层）有效 JSON
    for start in range(len(text)):
        if text[start] != '{':
            continue
        for end in range(len(text), start + 1, -1):
            if text[end - 1] != '}':
                continue
            candidate = text[start:end]
            try:
                data = json.loads(candidate)
                # 优先返回包含必要顶层字段的 JSON
                if {"details", "total_score", "total_deduct", "grade"} <= set(data.keys()):
                    return candidate
            except json.JSONDecodeError:
                continue

    return None


def parse_scoring_response(text: str) -> dict:
    """
    解析 LLM 评分响应。

    Args:
        text: LLM 返回的原始文本

    Returns:
        标准化评分字典，包含 details、total_score、total_deduct、grade 等字段

    Raises:
        ValueError: 解析失败或校验不通过
    """
    json_str = _extract_json(text)
    if not json_str:
        preview = text[:200].replace("\n", " ")
        raise ValueError(f"响应中未找到 JSON 内容。原始响应: {preview}...")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        # 尝试修复字符串中的未转义换行符等常见错误
        sanitized = _sanitize_json_string(json_str)
        try:
            data = json.loads(sanitized)
            json_str = sanitized
        except json.JSONDecodeError:
            preview = json_str[exc.pos - 30:exc.pos + 30].replace("\n", " ")
            raise ValueError(f"JSON 解析失败: {exc}。问题位置附近: ...{preview}...") from exc

    # 校验顶层字段
    required_top = {"details", "total_score", "total_deduct", "grade"}
    missing_top = required_top - set(data.keys())
    if missing_top:
        raise ValueError(f"JSON 缺少必要字段: {missing_top}")

    # 校验并规范 details
    details = data.get("details", [])
    if not isinstance(details, list):
        raise ValueError("details 必须是列表")

    standardized_details = []
    for item in details:
        if not isinstance(item, dict):
            continue
        rid = item.get("rule_id", "")
        score = int(item.get("score", 0))
        deduct = int(item.get("deduct", 0))
        passed = bool(item.get("passed", False))
        evidence = str(item.get("evidence", ""))
        standardized_details.append({
            "rule_id": rid,
            "score": score,
            "deduct": deduct,
            "passed": passed,
            "evidence": evidence,
        })

    return {
        "details": standardized_details,
        "total_score": int(data.get("total_score", 0)),
        "total_deduct": int(data.get("total_deduct", 0)),
        "grade": str(data.get("grade", "")),
        "manual_review_items": data.get("manual_review_items", []),
        "summary": str(data.get("summary", "")),
    }
