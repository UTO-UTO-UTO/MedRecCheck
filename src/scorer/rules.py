"""
评分规则配置：基于《口腔门诊病历质量督查表（复诊）》定义所有检查项。
"""

from dataclasses import dataclass


@dataclass
class Rule:
    id: str          # 细项编号，如 "1-1"
    category_id: str # 大项编号，如 "1"
    category_name: str   # 大项名称，如 "主诉"
    description: str # 细项描述
    score: int       # 分值
    check_fn: str    # 检查函数名（对应 checks.py 中的函数）
    auto_level: str  # "auto" | "semi" | "manual"
    kwargs: dict = None  # 传给检查函数的额外参数

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


# 评分规则列表
RULES = [
    # ===== 1. 主诉 =====
    Rule(
        id="1-2", category_id="1", category_name="主诉",
        description="符合主诉记录三要素——发病部位、症状、发病时间",
        score=6,
        check_fn="check_chief_complaint_elements",
        auto_level="semi",
        kwargs={"field": "chief_complaint"}
    ),
    Rule(
        id="1-3", category_id="1", category_name="主诉",
        description="20字以内，重点突出、简明扼要",
        score=2,
        check_fn="check_text_brevity",
        auto_level="semi",
        kwargs={"field": "chief_complaint", "max_chars": 20}
    ),
    Rule(
        id="1-4", category_id="1", category_name="主诉",
        description="原则上不使用诊断名词",
        score=2,
        check_fn="check_no_diagnosis_nouns",
        auto_level="semi",
        kwargs={"field": "chief_complaint"}
    ),

    # ===== 2. 检查 =====
    Rule(
        id="2-2", category_id="2", category_name="检查",
        description="口腔检查：记录实际的口腔检查内容（视诊/探诊/叩诊/扪诊/松动度/冷热测试等具体体征）",
        score=10,
        check_fn="check_clinical_exam",
        auto_level="semi",
        kwargs={"field": "clinical_exam"}
    ),
    Rule(
        id="2-3", category_id="2", category_name="检查",
        description="辅助检查：须与相关影像同步出现或同步缺失（同步缺失不扣分）；同时存在时须含日期+影像名+描述三要素",
        score=10,
        check_fn="check_auxiliary_exam",
        auto_level="semi",
        kwargs={"field": "auxiliary_exam"}
    ),

    # ===== 3. 现病史 =====
    Rule(
        id="3-1", category_id="3", category_name="现病史",
        description="应体现起病时间、症状发展过程（缺失不扣分）",
        score=10,
        check_fn="check_history_of_present_illness",
        auto_level="semi",
        kwargs={"field": "history_of_present_illness"}
    ),

    # ===== 4. 既往史 =====
    Rule(
        id="4-1", category_id="4", category_name="既往史",
        description="应记录系统性疾病、慢性病、特殊家族史、过敏史（缺失不扣分）",
        score=10,
        check_fn="check_past_history",
        auto_level="semi",
        kwargs={"field": "past_history"}
    ),

    # ===== 2-4. 相关影像（隶属于检查大项）=====
    Rule(
        id="2-4", category_id="2", category_name="检查",
        description="须与辅助检查同步出现或同步缺失（同步缺失不扣分）；同时存在时应为实际影像图片",
        score=10,
        check_fn="check_related_imaging",
        auto_level="semi",
        kwargs={"field": "related_imaging"}
    ),

    # ===== 6. 诊断 =====
    Rule(
        id="6-1", category_id="6", category_name="诊断",
        description="诊断应为诊断性名词，可包含？以表示疑似；可缺失，缺失不扣分",
        score=10,
        check_fn="check_diagnosis",
        auto_level="semi",
        kwargs={"field": "diagnosis"}
    ),

    # ===== 7. 处理/治疗 =====
    Rule(
        id="7-2", category_id="7", category_name="处理/治疗",
        description="记录实际的治疗操作流程",
        score=10,
        check_fn="check_treatment_plan",
        auto_level="semi",
        kwargs={"field": "treatment"}
    ),
    Rule(
        id="7-3", category_id="7", category_name="处理/治疗",
        description="用药应记录药名、剂量、用法",
        score=5,
        check_fn="check_medication",
        auto_level="semi",
        kwargs={"field": "treatment"}
    ),
    Rule(
        id="7-5", category_id="7", category_name="处理/治疗",
        description="记录向患者交代的重要注意事项（医嘱、告知书，从医嘱中判断）",
        score=5,
        check_fn="check_doctor_advice",
        auto_level="semi",
        kwargs={"field": "notes"}
    ),
]


def get_total_score() -> int:
    return sum(r.score for r in RULES)
