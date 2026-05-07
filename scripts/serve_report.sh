#!/bin/bash
# 用途：启动报告本地服务器，可一键暴露公网链接
# 参数：
#   --port       服务器端口（默认 8080）
#   --ngrok      同时使用 ngrok 暴露公网链接
#   --report     指定报告文件路径（默认 .tmp/report.html）
# 输出：本地访问地址，ngrok 公网链接（如启用）
# 退出码：0=正常启动，1=启动失败
# Known Issues：ngrok 免费版每次重启链接会变

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PORT=8080
USE_NGROK=false
REPORT_FILE=".tmp/report.html"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --ngrok)
            USE_NGROK=true
            shift
            ;;
        --report)
            REPORT_FILE="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--port 8080] [--ngrok] [--report .tmp/report.html]"
            exit 1
            ;;
    esac
done

# 检查报告文件是否存在
if [ ! -f "$REPORT_FILE" ]; then
    echo "[serve_report] 报告文件不存在: $REPORT_FILE"
    echo "[serve_report] 尝试重新生成报告..."
    python3 scripts/generate_report.py || {
        echo "[serve_report] 生成报告失败，请检查评分数据是否存在"
        exit 1
    }
fi

echo "[serve_report] 启动本地服务器 (端口 $PORT)..."

# 后台启动 Python HTTP 服务器
python3 src/report/serve.py --port "$PORT" --report "$REPORT_FILE" --no-open &
SERVER_PID=$!

# 等待服务器启动
sleep 1

LOCAL_URL="http://localhost:$PORT"
echo ""
echo "=========================================="
echo "本地访问地址: $LOCAL_URL"
echo "=========================================="

# 如果启用 ngrok，暴露公网链接
if [ "$USE_NGROK" = true ]; then
    if ! command -v ngrok &> /dev/null; then
        echo ""
        echo "[serve_report] 未检测到 ngrok，尝试安装..."
        if command -v brew &> /dev/null; then
            brew install ngrok/ngrok/ngrok
        else
            echo "[serve_report] 请手动安装 ngrok: https://ngrok.com/download"
            echo "[serve_report] 或使用 pip: pip install pyngrok"
            kill $SERVER_PID 2>/dev/null || true
            exit 1
        fi
    fi

    echo ""
    echo "[serve_report] 正在启动 ngrok 公网隧道..."

    # 启动 ngrok
    ngrok http "$PORT" --log=stdout > .tmp/ngrok.log 2>&1 &
    NGROK_PID=$!

    # 等待 ngrok 启动并获取公网链接
    sleep 3

    # 尝试获取公网链接
    for i in {1..10}; do
        PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*"' | grep "https://" | head -1 | cut -d'"' -f4)
        if [ -n "$PUBLIC_URL" ]; then
            break
        fi
        sleep 1
    done

    if [ -n "$PUBLIC_URL" ]; then
        echo ""
        echo "=========================================="
        echo "公网访问链接: $PUBLIC_URL"
        echo "=========================================="
        echo ""
        echo "可将此链接分享给他人，对方打开后即可："
        echo "  - 查看报告"
        echo "  - 点击 +分 / -分 进行人工复核"
        echo "  - 点击「下载 PNG」保存报告截图"
    else
        echo "[serve_report] 获取 ngrok 公网链接失败，请检查 .tmp/ngrok.log"
    fi

    # 保存 PID 以便后续清理
    echo $NGROK_PID > .tmp/ngrok.pid
fi

echo ""
echo "按 Ctrl+C 停止服务"

# 打开浏览器
open "$LOCAL_URL" 2>/dev/null || xdg-open "$LOCAL_URL" 2>/dev/null || true

# 等待用户中断
trap 'echo ""; echo "[serve_report] 正在停止服务..."; kill $SERVER_PID 2>/dev/null || true; [ -f .tmp/ngrok.pid ] && kill $(cat .tmp/ngrok.pid) 2>/dev/null || true; exit 0' INT
wait $SERVER_PID
