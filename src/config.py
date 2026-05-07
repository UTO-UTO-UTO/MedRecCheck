"""项目配置。

敏感信息只从环境变量读取，避免提交账号、密码或 API Key。
自动加载项目根目录的 .env 文件（若存在）。
"""

import os
from pathlib import Path

# 自动加载 .env 文件（若 python-dotenv 已安装）
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent
    _env_file = _project_root / ".env"
    if _env_file.exists():
        load_dotenv(dotenv_path=_env_file)
except Exception:
    pass

BASE_URL = "https://shhy.linkedcare.cn/ares3/#"
LOGIN_URL = BASE_URL

USERNAME = os.environ.get("MEDREC_USERNAME", "")
PASSWORD = os.environ.get("MEDREC_PASSWORD", "")

# 输出路径
TMP_DIR = ".tmp"
RECORDS_FILE = f"{TMP_DIR}/records.json"
SCORED_FILE = f"{TMP_DIR}/scored_records.json"
REPORT_FILE = f"{TMP_DIR}/report.html"
STORAGE_STATE = f"{TMP_DIR}/state.json"

# LLM 配置
# 支持 moonshot (Kimi), anthropic (Claude), openai (OpenAI) 及任意 OpenAI-compatible 端点
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "moonshot")
LLM_API_KEY = (
    os.environ.get("MOONSHOT_API_KEY")
    or os.environ.get("ANTHROPIC_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("LLM_API_KEY")
    or ""
)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.moonshot.cn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "moonshot-v1-8k")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "300"))


def require_login_config() -> None:
    """确认登录必需配置已提供。"""
    missing = []
    if not USERNAME:
        missing.append("MEDREC_USERNAME")
    if not PASSWORD:
        missing.append("MEDREC_PASSWORD")
    if missing:
        raise RuntimeError(f"缺少登录配置环境变量: {', '.join(missing)}")
