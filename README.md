# 口腔医院电子病历质量督查工具

本地单机使用的病历质量督查工具，自动登录领健医疗云，批量抓取电子病历并依据《口腔门诊病历质量督查表（复诊）》评分，生成可视化HTML报告。

## 快速开始

```bash
# 1. 初始化环境
bash scripts/setup_env.sh

# 2. 配置登录账号（也可写入本机 shell 配置或 .env 管理工具）
export MEDREC_USERNAME="你的账号"
export MEDREC_PASSWORD="你的密码"

# 3. 一键执行完整督查流程
bash scripts/run_full_pipeline.sh
```

执行完成后会自动在浏览器中打开评分报告。

## 项目结构

本项目遵循 Playbooks（协调层）→ Scripts（执行层）两层框架。

- `playbooks/` — 协调层流程定义
- `scripts/` — 执行层确定性脚本
- `src/` — 项目源代码模块
- `.tmp/` — 临时文件与中间产物

## 配置

敏感信息通过环境变量配置，不写入代码。可参考 `.env.example`：

- `MEDREC_USERNAME`：领健医疗云登录账号
- `MEDREC_PASSWORD`：领健医疗云登录密码
- `MOONSHOT_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `LLM_API_KEY`：可选，配置后使用 LLM 评分；留空时自动使用确定性规则评分
