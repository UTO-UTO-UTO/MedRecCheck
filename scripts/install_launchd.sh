#!/bin/bash
# 用途：安装本地定时任务（macOS launchd），每天定时执行评分+部署
# 参数：
#   --hour    执行小时（默认 22，即晚上10点）
#   --minute  执行分钟（默认 0）
# 输出：安装和检查状态
# 退出码：0=成功，1=失败
# Known Issues：需要 macOS，其他系统请使用 crontab 方案

set -e

HOUR="${1:-9}"
MINUTE="${2:-0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.medrec.report.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

# 生成 plist 文件
cat > "$PLIST_PATH" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.medrec.report</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$PROJECT_ROOT"
bash scripts/run_full_pipeline.sh
if [ \$? -eq 0 ]; then
    bash scripts/deploy_to_github.sh
fi</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$PROJECT_ROOT/.tmp/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_ROOT/.tmp/launchd.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>DEPLOY_TO_GITHUB</key>
        <string>1</string>
    </dict>
</dict>
</plist>
PLIST_EOF

echo "[install_launchd] plist 已写入: $PLIST_PATH"

# 卸载旧版本（如果存在）
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# 加载新版本
launchctl load "$PLIST_PATH"

echo "[install_launchd] 定时任务已安装"
echo ""
echo "  执行时间: 每天 ${HOUR}:$(printf '%02d' "$MINUTE")"
echo "  执行内容: 抓取病历 → 评分 → 生成报告 → 推送到 GitHub Pages"
echo "  日志文件: $PROJECT_ROOT/.tmp/launchd.log"
echo ""
echo "常用命令:"
echo "  查看状态:  launchctl list | grep medrec"
echo "  手动执行:  launchctl start com.medrec.report"
echo "  停止任务:  launchctl unload $PLIST_PATH"
echo "  卸载任务:  rm $PLIST_PATH && launchctl unload $PLIST_PATH"
