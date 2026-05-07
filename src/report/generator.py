"""
报告生成器：读取评分明细 JSON，渲染 ECharts HTML 报告。
"""

import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

# 模板目录
TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))


def _grade_class(grade: str) -> str:
    mapping = {
        "优秀": "excellent",
        "一般": "normal",
        "需注意": "warning",
        "不合格": "fail",
        "无病历": "no-record",
    }
    return mapping.get(grade, "")


def generate_report(scored_records: list[dict], output_path: str) -> None:
    """
    根据评分结果生成 HTML 报告。

    Args:
        scored_records: evaluate_all 返回的评分结果列表
        output_path: HTML 文件输出路径
    """
    if not scored_records:
        raise ValueError("评分结果为空，无法生成报告")

    # 统计总览
    total_patients = len(scored_records)

    # 平均/最高/最低得分排除"无病历"患者，避免 0 分拉低均值
    valid_records = [r for r in scored_records if r.get("grade") != "无病历"]
    no_record_count = total_patients - len(valid_records)

    if valid_records:
        scores = [r["total_score"] for r in valid_records]
        avg_score = round(sum(scores) / len(scores), 1)
        max_score = max(scores)
        min_score = min(scores)
    else:
        avg_score = 0
        max_score = 0
        min_score = 0

    full_score = scored_records[0].get("full_score", 85)

    # 等级分布
    grade_counts = {"优秀": 0, "一般": 0, "需注意": 0, "不合格": 0, "无病历": 0}
    for r in scored_records:
        g = r["grade"]
        grade_counts[g] = grade_counts.get(g, 0) + 1

    grade_rows = []
    grade_config = [
        ("优秀", "excellent", "0–5 分"),
        ("一般", "normal", "6–10 分"),
        ("需注意", "warning", "11–20 分"),
        ("不合格", "fail", "21 分以上"),
        ("无病历", "no-record", "—"),
    ]
    for name, cls, deduct_range in grade_config:
        count = grade_counts.get(name, 0)
        percent = round(count / total_patients * 100, 1) if total_patients else 0
        grade_rows.append({
            "name": name,
            "class": cls,
            "count": count,
            "percent": percent,
            "deduct_range": deduct_range,
        })

    # 饼图数据
    grade_pie_data = [
        {"value": r["count"], "name": r["name"]}
        for r in grade_rows if r["count"] > 0
    ]
    # 给饼图加颜色
    pie_colors = {
        "优秀": "#52c41a",
        "一般": "#1890ff",
        "需注意": "#faad14",
        "不合格": "#ff4d4f",
        "无病历": "#999999",
    }
    for item in grade_pie_data:
        item["itemStyle"] = {"color": pie_colors.get(item["name"], "#999")}

    # 各维度平均得分（按大项汇总每个患者的得分）
    category_stats = {}
    for r in scored_records:
        patient_cat = {}
        for d in r["details"]:
            cid = d["category_id"]
            cname = d["category_name"]
            if cid not in patient_cat:
                patient_cat[cid] = {"name": cname, "score": 0, "full": 0}
            patient_cat[cid]["score"] += d["score"]
            patient_cat[cid]["full"] += d["full_score"]

        for cid, data in patient_cat.items():
            if cid not in category_stats:
                category_stats[cid] = {"name": data["name"], "scores": [], "full": data["full"]}
            category_stats[cid]["scores"].append(data["score"])

    category_names = []
    category_avg_scores = []
    for cid in sorted(category_stats.keys(), key=lambda x: int(x) if x.isdigit() else x):
        stats = category_stats[cid]
        category_names.append(stats["name"])
        category_avg_scores.append(round(sum(stats["scores"]) / len(stats["scores"]), 1))

    # 需人工复核项汇总
    manual_items = []
    total_manual = 0
    for r in scored_records:
        for d in r["details"]:
            if d["auto_level"] == "manual":
                total_manual += 1
                manual_items.append({
                    "patient_name": r["patient_name"],
                    "category_name": d["category_name"],
                    "description": d["description"],
                    "evidence": d["evidence"],
                })

    # 患者数据拆分为评分患者与无病历患者
    scored_patients = []
    skipped_patients = []
    for r in scored_records:
        p = dict(r)
        p["grade_class"] = _grade_class(r["grade"])
        if r.get("grade") == "无病历":
            skipped_patients.append(p)
        else:
            scored_patients.append(p)

    # 渲染模板
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template("template.html")

    html = template.render(
        total_patients=total_patients,
        avg_score=avg_score,
        max_score=max_score,
        min_score=min_score,
        full_score=full_score,
        total_manual=total_manual,
        no_record_count=no_record_count,
        grade_rows=grade_rows,
        grade_pie_data=grade_pie_data,
        category_names=category_names,
        category_avg_scores=category_avg_scores,
        manual_items=manual_items,
        scored_patients=scored_patients,
        skipped_patients=skipped_patients,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[report] 报告已生成: {output_path}")
