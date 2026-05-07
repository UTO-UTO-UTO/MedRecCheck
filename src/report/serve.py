#!/usr/bin/env python3
"""
用途：启动本地 HTTP 服务器，提供病历评分报告浏览服务
参数：
  --port    服务器端口（默认 8080）
  --report  报告文件路径（默认 .tmp/report.html）
  --open    自动打开浏览器（默认开启）
输出：本地访问地址，如 http://localhost:8080
退出码：0=正常启动，1=启动失败
Known Issues：无
"""

import argparse
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler


class ReportHandler(SimpleHTTPRequestHandler):
    """自定义请求处理器：将根路径 / 重定向到报告文件。"""

    def __init__(self, *args, report_file="report.html", **kwargs):
        self.report_file = report_file
        super().__init__(*args, **kwargs)

    def translate_path(self, path):
        # 根路径 serve 报告文件
        if path == "/" or path == "/index.html":
            return os.path.abspath(self.report_file)
        return super().translate_path(path)

    def log_message(self, format, *args):
        # 简化日志输出
        print(f"[{self.log_date_time_string()}] {args[0]}")


def _make_handler(report_file):
    """工厂函数：创建绑定 report_file 的 Handler 类。"""
    def _handler(*args, **kwargs):
        return ReportHandler(*args, report_file=report_file, **kwargs)
    return _handler


def serve_report(report_path: str, port: int = 8080, open_browser: bool = True) -> None:
    """
    启动 HTTP 服务器 serve 报告文件。

    Args:
        report_path: 报告 HTML 文件路径
        port: 服务器端口
        open_browser: 是否自动打开浏览器
    """
    if not os.path.exists(report_path):
        print(f"[serve] 错误：报告文件不存在: {report_path}")
        print("[serve] 请先生成报告：python scripts/generate_report.py")
        sys.exit(1)

    # 切换到报告所在目录作为根目录
    report_dir = os.path.dirname(os.path.abspath(report_path)) or "."
    report_name = os.path.basename(report_path)
    os.chdir(report_dir)

    handler = _make_handler(report_name)

    try:
        server = HTTPServer(("", port), handler)
    except OSError as e:
        print(f"[serve] 启动失败：{e}")
        sys.exit(1)

    local_url = f"http://localhost:{port}"
    print(f"[serve] 报告服务已启动: {local_url}")
    print(f"[serve] 报告文件: {report_path}")

    if open_browser:
        webbrowser.open(local_url)
        print("[serve] 已自动打开浏览器")

    print("[serve] 按 Ctrl+C 停止服务\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] 服务已停止")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="病历评分报告本地服务器")
    parser.add_argument("--port", type=int, default=8080, help="服务器端口（默认 8080）")
    parser.add_argument("--report", type=str, default=".tmp/report.html", help="报告文件路径")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    serve_report(args.report, args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
