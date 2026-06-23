# QQ AI Chatbot Workspace

这个目录用于存放 QQ 智能 AI 聊天机器人项目文件。

GitHub 仓库：

- `https://github.com/ZZZZ-MAX-A/AIchatbot.git`

## 目录结构

- `src/`: 机器人源码
- `config/`: 配置文件和环境变量示例
- `data/`: 本地数据、缓存、会话记录或向量索引
- `logs/`: 运行日志
- `prompts/`: AI 系统提示词和角色设定
- `docs/`: 项目说明、架构设计和部署记录

## 下一步建议

1. 安装 Python 3.12 或更新版本。
2. 在 `.env.example` 的基础上创建 `.env`，填写 DeepSeek API Key。
3. 运行 `.\scripts\setup.ps1` 安装依赖，再运行 `.\scripts\start.ps1` 启动机器人。
4. 参考 `docs/napcatqq-setup.md` 配置 NapCatQQ 的 OneBot v11 反向 WebSocket。
5. 参考 `docs/plan-c-nonebot.md` 继续完善方案 C。
6. 参考 `docs/push-to-github.md` 把本地文件推送到 GitHub。

## 当前规划

- `v0.1`: QQ + NapCatQQ + NoneBot2 + DeepSeek 基础聊天，已跑通。
- `v0.2`: 权限、安全、白名单、黑名单、冷却和长度限制，设计见 `docs/v0.2-access-control.md`。

## 注意

不要把 `.env`、真实 Token、聊天记录数据库或私密日志上传到公开仓库。
