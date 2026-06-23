# AIchatbot

QQ 智能 AI 聊天机器人。

本项目使用 NoneBot2、OneBot v11、NapCatQQ 和 DeepSeek/OpenAI 兼容接口构建。

GitHub 仓库：

- `https://github.com/ZZZZ-MAX-A/AIchatbot.git`

## 目录结构

- `src/`: 机器人源码和插件
- `config/`: 配置文件和环境变量示例
- `data/`: 本地数据、动态白名单/黑名单、后续数据库
- `logs/`: 运行日志
- `prompts/`: AI 系统提示词和角色设定
- `docs/`: 项目说明、架构设计和部署记录
- `scripts/`: 安装、启动和诊断脚本

## 当前能力

- QQ 私聊和群聊 AI 回复
- DeepSeek 模型调用
- NapCatQQ + OneBot v11 接入
- 主人识别
- 私聊白名单
- 群聊白名单
- 用户黑名单
- QQ 内中文管理命令
- 私聊 150 字长度限制
- 群聊 300 字长度限制
- 用户冷却限制
- 主人免冷却
- 同一会话串行处理
- SQLite 聊天上下文持久化
- 私聊试用次数持久化
- 分层记忆数据库结构
- 会话摘要压缩
- `/状态` 查看机器人状态
- `/记忆状态` 查看记忆数据库状态
- `/权限帮助` 查看管理命令

## 启动

首次安装依赖：

```powershell
cd D:\AIchatbot
.\scripts\setup.ps1
```

启动 NoneBot2 后端：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

另开一个 PowerShell，启动 NapCatQQ：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1 2700318954
```

## 常用命令

普通命令：

```text
/重置
/状态
/记忆状态
/权限帮助
```

主人管理命令：

```text
/启用本群
/禁用本群
/加入群白名单 群号
/移出群白名单 群号
/加入私聊白名单 QQ号
/移出私聊白名单 QQ号
/加入黑名单 QQ号
/移出黑名单 QQ号
/群白名单
/私聊白名单
/黑名单
/清空全部上下文
/摘要状态
/查看摘要
/压缩当前会话
/清空当前摘要
/清空全部摘要
```

## 当前规划

- `v0.1`: QQ + NapCatQQ + NoneBot2 + DeepSeek 基础聊天，已跑通。
- `v0.2`: 权限、安全、白名单、黑名单、冷却和长度限制，已实现第一批和中文管理命令。
- `v0.3`: SQLite 聊天记录、试用次数持久化和基础记忆管理，已实现第一批。
- `v0.4`: 会话摘要压缩，已实现第一批。

## 文档

- [方案 C：NoneBot2 自研 QQ AI 机器人](docs/plan-c-nonebot.md)
- [NapCatQQ 接入 NoneBot2](docs/napcatqq-setup.md)
- [v0.2 权限与安全设计](docs/v0.2-access-control.md)
- [v0.3 SQLite 记忆方案](docs/v0.3-sqlite-memory.md)
- [v0.4 记忆压缩方案](docs/v0.4-memory-compression.md)
- [运行维护手册](docs/runbook.md)
- [推送到 GitHub](docs/push-to-github.md)

## 安全提醒

不要提交以下内容到公开仓库：

- `.env`
- API Key
- QQ Token
- WebUI Token
- 真实聊天记录
- 私密日志
- `tools/`
- `.venv/`
- `data/access.json`
- `data/chatbot.db`
