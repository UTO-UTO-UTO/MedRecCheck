#!/bin/bash
# 用途：检查并安装项目所需的 Python 依赖与 Playwright 浏览器
# 参数：无
# 输出：stdout 输出安装进度与结果摘要
# 退出码：0=全部就绪，1=安装失败
# Known Issues：若系统中同时存在 python3 与 python 命令，优先使用 python3

set -e

echo "[setup_env] 开始检查环境..."

# 检查 Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[setup_env] 错误：未找到 python3 或 python 命令，请先安装 Python 3.9+"
    exit 1
fi

echo "[setup_env] Python 命令: $PYTHON_CMD"

# 检查 pip
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo "[setup_env] 错误：未找到 pip，请先安装 pip"
    exit 1
fi

# 安装 requirements
REQ_FILE="$(dirname "$0")/../requirements.txt"
echo "[setup_env] 安装依赖: $REQ_FILE"
$PYTHON_CMD -m pip install -r "$REQ_FILE"

# 安装 Playwright 浏览器
echo "[setup_env] 安装 Playwright Chromium..."
$PYTHON_CMD -m playwright install chromium

echo "[setup_env] 环境初始化完成"
exit 0
