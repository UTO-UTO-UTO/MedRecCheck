"""
确定性检查函数库。
每个检查函数接收病历文本（或整份病历字典）及相关参数，
返回 (bool: 是否通过, str: 证据/原因)。
"""

import re
from typing import Tuple


def _get_field_text(record: dict, field: str) -> str:
    """从病历字典中提取指定字段文本，若字段不存在则返回 raw_text 兜底。"""
    text = record.get("record", {}).get(field, "")
    if not text:
        text = record.get("record", {}).get("raw_text", "")
    return text or ""


def _get_field_text_direct(record: dict, field: str) -> str:
    """直接从病历字典中提取指定字段文本，不 fallback 到 raw_text。
    用于'可缺失'字段，避免把完整病历当成字段内容误评。"""
    return record.get("record", {}).get(field, "") or ""


def check_chief_complaint_elements(record: dict, field: str) -> Tuple[bool, str]:
    """
    检查主诉是否包含三要素：发病部位、症状、发病时间。
    使用关键词库进行近似判断。
    """
    text = _get_field_text(record, field)
    if not text:
        return False, "主诉内容为空"

    # 部位关键词
    parts = ["上颌", "下颌", "左侧", "右侧", "左", "右", "前牙", "后牙", "磨牙", "切牙", "尖牙",
             "第一磨牙", "第二磨牙", "智齿", "牙", "齿", "口腔", "舌", "唇", "颊", "腭", "龈"]
    # 症状关键词
    symptoms = ["痛", "疼", "肿胀", "肿", "出血", "出血", "松动", "缺失", "缺损", "龋", "蛀牙",
                "敏感", "不适", "咀嚼困难", "咬合痛", "自发痛", "冷热刺激", "夜间痛", "食物嵌塞"]
    # 时间关键词
    times = ["天", "日", "周", "月", "年", "小时", "分钟", "前", "以来", "至今", "昨天", "今天",
             "近日", "近期", "一周", "两周", "一个月", "三个月"]

    has_part = any(p in text for p in parts)
    has_symptom = any(s in text for s in symptoms)
    has_time = any(t in text for t in times)

    missing = []
    if not has_part:
        missing.append("发病部位")
    if not has_symptom:
        missing.append("症状")
    if not has_time:
        missing.append("发病时间")

    if not missing:
        return True, "包含部位、症状、时间三要素"
    return False, f"缺少要素: {', '.join(missing)} (当前文本: {text[:40]}...)"


# 常见诊断名词库（可扩展）
DIAGNOSIS_NOUNS = [
    "龋齿", "牙髓炎", "根尖周炎", "牙周炎", "牙龈炎", "智齿冠周炎",
    "牙列缺损", "牙列缺失", "错颌畸形", "口腔溃疡", "口腔扁平苔藓",
    "牙体缺损", "楔状缺损", "牙本质过敏", "颞下颌关节紊乱",
    "龋病", "牙髓病", "根尖周病", "牙周病", "黏膜病",
]


def check_no_diagnosis_nouns(record: dict, field: str) -> Tuple[bool, str]:
    """
    检查主诉中是否使用了诊断名词。
    命中则扣分（不通过）。
    """
    text = _get_field_text(record, field)
    if not text:
        return True, "主诉内容为空，无法判断（默认不扣分）"

    found = [d for d in DIAGNOSIS_NOUNS if d in text]
    if found:
        return False, f"疑似使用诊断名词: {', '.join(found)}"
    return True, "未检测到常见诊断名词"


def check_text_brevity(record: dict, field: str, max_chars: int = 20) -> Tuple[bool, str]:
    """
    检查文本是否在指定字数以内，近似判断简明扼要。
    """
    text = _get_field_text(record, field)
    if not text:
        return False, "内容为空"

    length = len(text)
    if length <= max_chars:
        return True, f"共 {length} 字，符合 {max_chars} 字以内要求"
    return False, f"共 {length} 字，超过 {max_chars} 字限制（当前: {text[:40]}...）"


def check_clinical_exam(record: dict, field: str) -> Tuple[bool, str]:
    """
    口腔检查：记录实际的口腔检查内容（视诊/探诊/叩诊/扪诊/松动度/冷热测试等具体体征），
    仅出现"复查""阳性体征"等模板用语视为不达标。
    """
    text = _get_field_text(record, field)
    if not text:
        return False, "检查内容为空"

    # 模板用语单独出现不算"实际检查内容"
    template_only = re.fullmatch(r"\s*(复查|阳性体征|阴性体征|体征阴性|体征阳性|无明显异常|未见异常)\s*", text)
    if template_only:
        return False, f"仅含模板用语「{text.strip()}」,缺少实际检查内容"

    # 具体口腔检查内容关键词（视诊/探诊/叩诊/扪诊/松动度/冷热测试等具体体征）
    specific_terms = [
        "视诊", "探", "叩", "扪", "松动", "冷", "热",
        "红肿", "残根", "残冠", "缺失", "在位", "脱落",
        "龋坏", "充填", "瘘管",
        "Ⅰ", "Ⅱ", "Ⅲ", "I", "II", "III",
        "见",
        "矫治器", "愈合基台",
    ]
    matched = [k for k in specific_terms if k in text]
    has_tooth = bool(re.search(r"[1-4][1-8]\b|第[一二三四五六七八]?[磨切尖前]牙|上颌|下颌", text))

    if matched or (has_tooth and len(text) >= 12):
        evidence_bits = []
        if matched:
            evidence_bits.append(f"具体体征/检查: {', '.join(matched[:5])}")
        if has_tooth:
            evidence_bits.append("含牙位描述")
        return True, "; ".join(evidence_bits) or "含临床检查描述"

    return False, "未检测到具体口腔检查内容（视诊/探诊/叩诊/扪诊/松动度/冷热测试等具体体征）"


def check_auxiliary_exam(record: dict, field: str) -> Tuple[bool, str]:
    """
    辅助检查和相关影像必须同时出现或同时缺失。
    若同时缺失，不扣分；若同时存在，辅助检查须含日期+影像名+描述三要素。
    若不同步，辅助检查扣分。
    """
    text = _get_field_text_direct(record, field)
    stripped = text.replace("辅助检查", "").replace(":", "").replace("：", "").strip()
    has_aux = bool(text and len(stripped) >= 2)

    # 判断相关影像是否存在（有图片或文本）
    has_images = record.get("record", {}).get("has_imaging_images", False)
    imaging_text = _get_field_text_direct(record, "related_imaging")
    has_imaging = has_images or bool(imaging_text)

    # 同步性检查
    if not has_aux and not has_imaging:
        return True, "辅助检查与相关影像同时缺失（符合要求）"
    if not has_aux and has_imaging:
        return False, "辅助检查为空，但相关影像不为空（应同步）"
    if has_aux and not has_imaging:
        return False, "辅助检查有内容，但相关影像缺失（应同步）"

    imaging_types = ["全景片", "CBCT", "根尖片", "X线", "X光", "曲面断层", "牙片", "CT", "MRI"]
    has_imaging = any(t in text for t in imaging_types)
    has_date = bool(re.search(
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}[-/月]\d{1,2}\s*日?", text
    ))
    read_keywords = ["读片", "阅片", "影像", "示", "显示", "可见", "未见", "根尖", "骨质", "牙周膜", "牙槽骨", "龋损"]
    has_info = any(k in text for k in read_keywords) or len(stripped) >= 30

    missing = []
    if not has_imaging:
        missing.append("影像名")
    if not has_date:
        missing.append("日期")
    if not has_info:
        missing.append("描述/读片信息")

    if not missing:
        return True, "辅助检查含日期、影像名与描述"
    return False, f"辅助检查缺少: {', '.join(missing)}"


def check_treatment_plan(record: dict, field: str) -> Tuple[bool, str]:
    """
    记录处理方案、治疗意见，应包含实际的治疗操作流程。
    """
    text = _get_field_text(record, field)
    if not text:
        return False, "处理/治疗内容为空"

    if len(text) < 15:
        return False, f"处理/治疗记录过短（{len(text)} 字），可能未记录具体方案"

    # 具体操作流程关键词
    procedure_terms = [
        "开髓", "拔髓", "根管预备", "根管充填", "根充", "封药",
        "去腐", "备洞", "充填", "补牙", "垫底", "粘接",
        "拔除", "切开", "引流", "缝合", "麻醉", "局部麻醉",
        "洁治", "刮治", "翻瓣", "植骨", "种植",
        "调合", "抛光", "上药", "复查", "复诊",
        "拍片", "取模", "试戴", "粘固", "戴牙",
        "涂氟", "窝沟",
        "矫治器", "托槽", "ss", "NiTi", "颊面管", "摇椅", "牵引", "支抗钉",
        "卡环", "基托", "调磨", "重衬", "压痛", "支托",
    ]
    # 治疗阶段/次数描述
    stage_terms = ["一期", "二期", "初诊", "复诊", "首次", "再次", "术后", "术前"]
    # 器械/材料
    material_terms = ["树脂", "玻璃离子", "银汞", "氢氧化钙", "MTA", "牙胶", "糊剂", "橡皮障", "三德钳"]

    matched_proc = [k for k in procedure_terms if k in text]
    matched_stage = [k for k in stage_terms if k in text]
    matched_mat = [k for k in material_terms if k in text]
    has_tooth = bool(re.search(r"[1-4][1-8]\b|第[一二三四五六七八]?[磨切尖前]牙|上颌|下颌", text))

    if matched_proc or (has_tooth and len(text) >= 20):
        evidence = []
        if matched_proc:
            evidence.append(f"操作步骤: {', '.join(matched_proc[:5])}")
        if matched_stage:
            evidence.append("含治疗阶段/次数")
        if matched_mat:
            evidence.append("含材料/器械")
        if has_tooth:
            evidence.append("含牙位")
        return True, "; ".join(evidence) or "包含治疗操作流程"

    return False, "未检测到具体治疗操作流程或操作步骤"


# 常见剂量单位，用于匹配药名+剂量+用法
MEDICATION_PATTERN = re.compile(
    r"([^，,。；;\s]{2,20}?(?:片|胶囊|颗粒|口服液|注射液|混悬液|滴眼液|软膏|含片|漱口水|甲硝唑|阿莫西林|头孢|布洛芬|对乙酰氨基酚|替硝唑|奥硝唑|克林霉素|罗红霉素|阿奇霉素))"
    r".*?"
    r"(\d+(?:\.\d+)?\s*(?:mg|g|ml|片|粒|支|瓶|袋|单位|U))"
    r".*?"
    r"(口服|含服|含漱|外用|注射|静滴|肌注|皮下注射|每日|一日|bid|tid|qd|qid|prn|必要时)"
)


def check_medication(record: dict, field: str) -> Tuple[bool, str]:
    """
    用药应记录药名、剂量、用法。
    """
    text = _get_field_text(record, field)
    if not text:
        return True, "处理/治疗内容为空，无用药记录（默认不扣分）"

    # 先检查是否提到药物
    if not any(k in text for k in ["药", "片", "胶囊", "颗粒", "口服", "含服", "甲硝唑", "阿莫西林", "头孢"]):
        return True, "未提及用药，可能本次无需用药（默认不扣分）"

    matches = MEDICATION_PATTERN.findall(text)
    if matches:
        examples = [f"{m[0]} {m[1]} {m[2]}" for m in matches[:2]]
        return True, f"检测到用药记录示例: {'; '.join(examples)}"

    # 若提到药但正则未完整匹配，给部分提示
    return False, "提及用药但未完整记录药名、剂量、用法（建议人工核对）"


def check_history_of_present_illness(record: dict, field: str) -> Tuple[bool, str]:
    """现病史应体现症状发展过程，原则上不含诊断名词；可缺失，缺失不扣分。"""
    text = _get_field_text_direct(record, field)
    if not text:
        return True, "现病史缺失（可缺失，不扣分）"

    # 检查是否体现症状发展过程（时间线关键词 + 症状变化描述）
    time_indicators = ["前", "以来", "至今", "开始", "逐渐", "加重", "缓解", "后",
                       "第", "天", "日", "周", "月", "年", "小时", "分钟",
                       "昨日", "今日", "近日", "当时", "随后", "继之"]
    symptom_changes = ["加重", "缓解", "减轻", "消失", "反复", "持续", "阵发",
                       "加剧", "好转", "恶化", "无改善", "未愈"]

    has_time = any(t in text for t in time_indicators)
    has_change = any(c in text for c in symptom_changes)

    # 检查是否含诊断名词
    found_diagnosis = [d for d in DIAGNOSIS_NOUNS if d in text]

    issues = []
    if not has_time:
        issues.append("未体现时间线/发病过程")
    if not has_change:
        issues.append("未体现症状变化/发展")
    if found_diagnosis:
        issues.append(f"含诊断名词: {', '.join(found_diagnosis[:3])}")

    if not issues:
        return True, "体现症状发展过程，未含诊断名词"
    return False, "; ".join(issues)


def check_past_history(record: dict, field: str) -> Tuple[bool, str]:
    """既往史应记录系统性疾病、慢性病、特殊家族史、过敏史中至少一项；可缺失，缺失不扣分。"""
    text = _get_field_text_direct(record, field)
    if not text:
        return True, "既往史缺失（可缺失，不扣分）"

    systemic = ["高血压", "糖尿病", "心脏病", "冠心病", "肾病", "肝病", "血液病",
                "结核", "肝炎", "哮喘", "甲亢", "甲减", "系统性红斑狼疮"]
    chronic = ["高血压", "糖尿病", "冠心病", "慢性", "长期", "多年", "反复"]
    family = ["家族", "遗传", "父", "母", "兄", "弟", "姐", "妹", "亲属"]
    allergy = ["过敏", "青霉素", "磺胺", "碘", "麻药", "利多卡因", "阿替卡因",
               "药物过敏", "食物过敏"]

    has_systemic = any(s in text for s in systemic)
    has_chronic = any(c in text for c in chronic)
    has_family = any(f in text for f in family)
    has_allergy = any(a in text for a in allergy)

    found = []
    if has_systemic:
        found.append("系统性疾病")
    if has_chronic:
        found.append("慢性病")
    if has_family:
        found.append("家族史")
    if has_allergy:
        found.append("过敏史")

    if found:
        return True, f"记录到: {', '.join(found)}"
    return False, "未记录系统性疾病、慢性病、家族史或过敏史"


def check_related_imaging(record: dict, field: str) -> Tuple[bool, str]:
    """
    若辅助检查不为空，则相关影像亦不为空且应为实际影像图片；
    若辅助检查为空，则相关影像亦应为空。
    """
    aux_text = _get_field_text_direct(record, "auxiliary_exam")
    has_aux = bool(aux_text and len(aux_text.replace("辅助检查", "").replace(":", "").replace("：", "").strip()) >= 2)
    has_images = record.get("record", {}).get("has_imaging_images", False)
    imaging_text = _get_field_text_direct(record, field)

    if has_aux:
        if has_images:
            return True, "辅助检查有内容，且检测到相关影像图片"
        if imaging_text:
            return False, "辅助检查有内容，相关影像仅有文本描述但无实际影像图片"
        return False, "辅助检查有内容，但相关影像缺失"
    else:
        if has_images or imaging_text:
            return False, "辅助检查为空，但相关影像不为空（应同时为空）"
        return True, "辅助检查为空，相关影像亦为空（符合要求）"


def check_diagnosis(record: dict, field: str) -> Tuple[bool, str]:
    """诊断应为诊断性名词，可包含？以表示疑似；可缺失，缺失不扣分。"""
    text = _get_field_text_direct(record, field)
    if not text:
        return True, "诊断缺失（可缺失，不扣分）"

    # 检查是否包含诊断名词
    found = [d for d in DIAGNOSIS_NOUNS if d in text]
    # 检查是否有疑似标记
    has_question = "？" in text or "?" in text

    if found:
        evidence = f"包含诊断名词: {', '.join(found[:3])}"
        if has_question:
            evidence += "；含疑似标记(？)"
        return True, evidence

    # 如果无常见诊断名词，但至少包含"？"和一些医学词汇，也给过
    if has_question and len(text) >= 3:
        return True, "含疑似标记，可能为诊断描述"

    return False, "未检测到诊断性名词"


def check_doctor_advice(record: dict, field: str) -> Tuple[bool, str]:
    """
    记录向患者交代的重要注意事项（医嘱、告知书）。
    """
    text = _get_field_text(record, field)
    if not text:
        return False, "处理/治疗内容为空"

    # 新规则：若仅有模糊随访用语（如不适随诊），而无具体复诊时间约定，扣5分
    vague_followup = any(k in text for k in ["随诊", "随访", "不适随诊"])
    has_specific_time = bool(re.search(r"\d+\s*[天周月年]\s*后|一周后|两周后|一月后|三月后|明日|下次", text))

    if vague_followup and not has_specific_time:
        return False, "未记录复诊时间，需人工复核"

    keywords = ["医嘱", "告知", "注意", "禁忌", "禁食", "禁水", "避免", "保持", "随诊", "不适随诊", "签字"]
    matched = [k for k in keywords if k in text]
    if matched:
        return True, f"包含注意事项/医嘱描述: {', '.join(matched)}"
    return False, "未检测到医嘱、告知或注意事项关键词"
