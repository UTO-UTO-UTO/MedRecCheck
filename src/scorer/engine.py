"""
评分引擎主逻辑：优先调用 LLM 进行语义评分，
LLM 不可用或失败时自动回退到确定性规则评分（checks.py）。
"""

from typing import List

from src.scorer.rules import RULES, get_total_score
from src.scorer import checks
from src.llm import client


def _calc_grade(total_deduct: int) -> str:
    """根据扣分计算评级。"""
    if total_deduct <= 5:
        return "优秀"
    elif total_deduct <= 10:
        return "一般"
    elif total_deduct <= 20:
        return "需注意"
    else:
        return "不合格"


def _evaluate_with_rules(record: dict) -> List[dict]:
    """使用确定性规则（checks.py）评分。"""
    details = []
    for rule in RULES:
        check_fn = getattr(checks, rule.check_fn, None)
        if check_fn is None:
            passed = False
            evidence = f"检查函数 {rule.check_fn} 未实现"
        else:
            try:
                passed, evidence = check_fn(record, **rule.kwargs)
            except Exception as e:
                passed = False
                evidence = f"检查执行异常: {e}"

        score = rule.score if passed else 0
        deduct = rule.score - score

        details.append({
            "rule_id": rule.id,
            "category_id": rule.category_id,
            "category_name": rule.category_name,
            "description": rule.description,
            "full_score": rule.score,
            "score": score,
            "deduct": deduct,
            "passed": passed,
            "evidence": evidence,
            "auto_level": rule.auto_level,
        })
    return details


def _merge_llm_details(llm_details: List[dict]) -> List[dict]:
    """将 LLM 返回的评分明细与 RULES 对齐，补全缺失项。"""
    rule_map = {r.id: r for r in RULES}
    result = []
    seen = set()

    for item in llm_details:
        rid = item.get("rule_id", "")
        rule = rule_map.get(rid)
        if rule:
            seen.add(rid)
            score = int(item.get("score", 0))
            deduct = int(item.get("deduct", rule.score - score))
            result.append({
                "rule_id": rule.id,
                "category_id": rule.category_id,
                "category_name": rule.category_name,
                "description": rule.description,
                "full_score": rule.score,
                "score": score,
                "deduct": deduct,
                "passed": bool(item.get("passed", False)),
                "evidence": str(item.get("evidence", "")),
                "auto_level": rule.auto_level,
            })

    # 补充 LLM 未返回的规则，默认 0 分
    for rule in RULES:
        if rule.id not in seen:
            result.append({
                "rule_id": rule.id,
                "category_id": rule.category_id,
                "category_name": rule.category_name,
                "description": rule.description,
                "full_score": rule.score,
                "score": 0,
                "deduct": rule.score,
                "passed": False,
                "evidence": "LLM 未返回该项评分，默认 0 分",
                "auto_level": rule.auto_level,
            })

    # 按 RULES 原始顺序排序
    order = {r.id: i for i, r in enumerate(RULES)}
    result.sort(key=lambda x: order.get(x["rule_id"], 999))
    return result


async def evaluate_record(record: dict) -> dict:
    """
    对单份病历执行评分。

    优先使用 LLM 语义评分；LLM 未配置或调用失败时回退到确定性规则评分。
    若患者无当日病历（skipped 或 record 为空），直接返回 0 分并标记为"无病历"。
    """
    # 无病历患者直接返回 0 分
    if record.get("skipped") or not record.get("record"):
        return {
            "patient_name": record.get("patient_name", "未知"),
            "patient_id": record.get("patient_id"),
            "details": [],
            "total_score": 0,
            "total_deduct": 0,
            "full_score": get_total_score(),
            "grade": "无病历",
            "manual_review_items": [],
            "error": record.get("error"),
            "skip_reason": record.get("skip_reason", ""),
            "llm_summary": "",
            "used_llm": False,
        }

    llm_result = None
    llm_summary = ""
    used_llm = False

    # 临时关闭 LLM 评分，仅使用规则评分
    # if client.is_configured():
    #     try:
    #         llm_result = await client.score_record(record)
    #         used_llm = True
    #     except Exception as e:
    #         print(f"[engine] 大模型调用失败（患者: {record.get('patient_name', '未知')}），回退到规则评分: {e}")

    if llm_result:
        details = _merge_llm_details(llm_result.get("details", []))
        total_score = llm_result.get("total_score", sum(d["score"] for d in details))
        total_deduct = llm_result.get("total_deduct", sum(d["deduct"] for d in details))
        grade = llm_result.get("grade", _calc_grade(total_deduct))
        llm_summary = llm_result.get("summary", "")
    else:
        details = _evaluate_with_rules(record)
        total_score = sum(d["score"] for d in details)
        total_deduct = sum(d["deduct"] for d in details)
        grade = _calc_grade(total_deduct)

    manual_review_items = [d for d in details if d.get("auto_level") == "manual"]

    return {
        "patient_name": record.get("patient_name", "未知"),
        "patient_id": record.get("patient_id"),
        "details": details,
        "total_score": total_score,
        "total_deduct": total_deduct,
        "full_score": get_total_score(),
        "grade": grade,
        "manual_review_items": manual_review_items,
        "error": record.get("error"),
        "llm_summary": llm_summary,
        "used_llm": used_llm,
    }


async def evaluate_all(records: List[dict]) -> List[dict]:
    """
    批量评分。顺序执行以避免触发 LLM API 速率限制。
    """
    results = []
    for rec in records:
        result = await evaluate_record(rec)
        results.append(result)
    return results
