#!/bin/bash
# 用途：一键执行完整的病历质量督查流程（环境检查 → 抓取 → 评分 → 生成报告）
# 参数：无
# 输出：各步骤的进度与结果摘要
# 退出码：0=全部成功，1=任一环节失败
# Known Issues：
#   - 若环境未初始化，首次运行会自动安装依赖（可能需要较长时间）
#   - 抓取环节会弹出浏览器窗口，请勿在运行中关闭
#   - 设置环境变量 DEPLOY_TO_GITHUB=1 可在生成报告后自动部署到 GitHub Pages

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 统一检测 Python 命令（与 setup_env.sh 保持一致）
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[run_full_pipeline] 错误：未找到 python3 或 python 命令，请先安装 Python 3.9+"
    exit 1
fi

echo "========================================"
echo "  口腔门诊病历质量督查 - 一键执行"
echo "========================================"

# 1. 环境初始化
echo ""
echo "[1/4] 环境初始化..."
bash "$SCRIPT_DIR/setup_env.sh"

# 2. 抓取病历
echo ""
echo "[2/4] 抓取病历数据..."
$PYTHON_CMD "$SCRIPT_DIR/crawl_records.py" || CRAWL_EXIT=$?
CRAWL_EXIT=${CRAWL_EXIT:-0}
if [ "$CRAWL_EXIT" -eq 2 ]; then
    echo "[run_full_pipeline] 工作台无患者，流程正常终止"
    exit 0
elif [ "$CRAWL_EXIT" -ne 0 ]; then
    exit 1
fi

# 3. 评分
echo ""
echo "[3/4] 评分..."
$PYTHON_CMD "$SCRIPT_DIR/score_records.py" || SCORE_EXIT=$?
SCORE_EXIT=${SCORE_EXIT:-0}
if [ "$SCORE_EXIT" -eq 2 ]; then
    echo "[run_full_pipeline] 病历列表为空，流程正常终止"
    exit 0
elif [ "$SCORE_EXIT" -ne 0 ]; then
    exit 1
fi

# 4. 生成报告
echo ""
echo "[4/4] 生成报告..."
$PYTHON_CMD "$SCRIPT_DIR/generate_report.py" || REPORT_EXIT=$?
REPORT_EXIT=${REPORT_EXIT:-0}
if [ "$REPORT_EXIT" -eq 2 ]; then
    echo "[run_full_pipeline] 评分结果为空，未生成报告"
    exit 0
elif [ "$REPORT_EXIT" -ne 0 ]; then
    exit 1
fi

echo ""
echo "========================================"
echo "  全部完成！报告已生成并尝试打开浏览器。"
echo "========================================"

# 5. 可选：自动部署到 GitHub Pages
if [ "${DEPLOY_TO_GITHUB:-0}" = "1" ]; then
    echo ""
    echo "[5/5] 部署到 GitHub Pages..."
    bash "$SCRIPT_DIR/deploy_to_github.sh" || {
        echo "[run_full_pipeline] GitHub Pages 部署失败，但报告已生成本地文件"
    }
fi
