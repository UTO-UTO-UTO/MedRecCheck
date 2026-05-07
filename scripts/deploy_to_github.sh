#!/bin/bash
# 用途：将生成的报告推送到 GitHub Pages，生成固定访问链接
# 参数：
#   --report     报告文件路径（默认 .tmp/report.html）
#   --branch     部署分支（默认 gh-pages）
#   --message    提交信息（默认包含日期）
#   --dry-run    仅预览，不实际推送
# 输出：GitHub Pages 访问链接
# 退出码：0=成功，1=失败
# Known Issues：
#   - 首次运行需要在 GitHub 仓库设置中开启 Pages（从 gh-pages 分支部署）
#   - 若使用 HTTPS 方式，可能需要输入 GitHub 用户名和 Token

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

REPORT_FILE=".tmp/report.html"
BRANCH="gh-pages"
COMMIT_MSG=""
DRY_RUN=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --report)
            REPORT_FILE="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --message)
            COMMIT_MSG="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--report .tmp/report.html] [--branch gh-pages] [--message \"更新报告\"] [--dry-run]"
            exit 1
            ;;
    esac
done

# 检查报告文件
if [ ! -f "$REPORT_FILE" ]; then
    echo "[deploy] 错误：报告文件不存在: $REPORT_FILE"
    echo "[deploy] 请先运行评分流程生成报告"
    exit 1
fi

# 获取 GitHub 仓库信息
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE_URL" ]; then
    echo "[deploy] 错误：当前目录没有配置 git remote origin"
    echo "[deploy] 请确保项目在 Git 仓库中，且已添加远程仓库:"
    echo "    git remote add origin https://github.com/用户名/仓库名.git"
    exit 1
fi

# 解析仓库信息
# 支持格式：git@github.com:用户名/仓库名.git 或 https://github.com/用户名/仓库名.git
if echo "$REMOTE_URL" | grep -qE '^git@github\.com:'; then
    REPO_PATH=$(echo "$REMOTE_URL" | sed -E 's/^git@github\.com:(.+)(\.git)?$/\1/')
    GITHUB_HOST="git@github.com"
elif echo "$REMOTE_URL" | grep -qE '^https?://github\.com/'; then
    REPO_PATH=$(echo "$REMOTE_URL" | sed -E 's|^https?://github\.com/(.+)(\.git)?$|\1|')
    GITHUB_HOST="https://github.com"
else
    echo "[deploy] 错误：无法识别远程仓库格式: $REMOTE_URL"
    echo "[deploy] 请确保 remote origin 指向 GitHub 仓库"
    exit 1
fi

OWNER=$(echo "$REPO_PATH" | cut -d'/' -f1)
REPO=$(echo "$REPO_PATH" | cut -d'/' -f2 | sed 's/\.git$//')
PAGES_URL="https://${OWNER}.github.io/${REPO}"

# 检查是否已安装 gh CLI（可选，用于检查 Pages 状态）
if command -v gh &> /dev/null; then
    # 尝试检查仓库是否已启用 Pages（仅信息提示，不影响执行）
    if gh api "repos/${OWNER}/${REPO}/pages" &> /dev/null; then
        PAGES_STATUS=$(gh api "repos/${OWNER}/${REPO}/pages" --jq '.html_url' 2>/dev/null || echo "")
        if [ -n "$PAGES_STATUS" ]; then
            PAGES_URL="$PAGES_STATUS"
        fi
    fi
fi

echo "[deploy] 报告文件: $REPORT_FILE"
echo "[deploy] 目标仓库: ${OWNER}/${REPO}"
echo "[deploy] 部署分支: $BRANCH"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "[deploy] 【预览模式】以下操作不会实际执行："
    echo "  1. 创建临时目录"
    echo "  2. 复制报告为 index.html"
    echo "  3. 推送到 ${GITHUB_HOST}:${REPO_PATH}.git ${BRANCH}"
    echo ""
    echo "[deploy] 部署后将可通过以下链接访问："
    echo "  $PAGES_URL"
    exit 0
fi

# 创建临时目录
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# 复制报告为 index.html
cp "$REPORT_FILE" "$TMP_DIR/index.html"

# 在临时目录中初始化 git 并推送
cd "$TMP_DIR"
git init -q
git checkout -b "$BRANCH" 2>/dev/null || true

git config user.email "medrec-bot@local"
git config user.name "MedRec Bot"

git add index.html

if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="更新报告 $(date '+%Y-%m-%d %H:%M')"
fi

git commit -m "$COMMIT_MSG" --allow-empty -q

echo "[deploy] 正在推送到 GitHub..."

# 根据 remote 格式选择推送方式
if [ "$GITHUB_HOST" = "git@github.com" ]; then
    git push -f "$REMOTE_URL" "$BRANCH"
else
    git push -f "$REMOTE_URL" "$BRANCH"
fi

echo ""
echo "=========================================="
echo "部署成功！"
echo ""
echo "访问链接: $PAGES_URL"
echo ""
echo "注意："
echo "  - 首次部署后，GitHub Pages 可能需要 1-2 分钟生效"
echo "  - 若链接无法访问，请检查仓库设置中的 Pages 配置"
echo "    （Settings → Pages → Source → Deploy from a branch → gh-pages）"
echo "=========================================="
