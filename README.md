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
- `prompts/`: AI 系统提示词、角色卡和表达设定
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
- 主人发言优先的客观会话摘要
- 短会话保留原文，达到最低门槛后再摘要
- 主人手动长期记忆
- 长上下文短版底层规则定期提醒
- 人格表达提示词
- 群聊主动回复规则评分，默认关闭
- 角色卡专属主动回复别名和触发词
- 主人转告通知，固定模板私聊给主人
- 本地 Ollama 视觉识图，图片只作为受限事实参考
- 私聊图片短等待合并追问，群聊图片短期缓存后由同一用户 @ 触发识别
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

## 测试

运行纯本地单元测试：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前测试优先覆盖 config loading / LangGraph adapter / shadow state / snapshot validation / graph contracts / policy / runtime skeleton / LangChain model factories / access rules / owner notification / rate limit / group auto-reply / vision and voice pure units / memory pure units / operation pure units，不启动 NoneBot、不连接 QQ、不调用模型 API。

## 常用命令

普通命令：

```text
/重置
/状态
/诊断
/配置状态
/视觉状态
/最近错误
/图片缓存状态
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
/清空错误日志
/清空图片缓存
/清空全部上下文
/摘要状态
/查看摘要
/查看空窗摘要
/压缩当前会话
/清空当前摘要
/删除摘要 摘要ID
/清空全部摘要
/添加事实记忆 内容
/添加偏好记忆 内容
/查看长期记忆
/删除长期记忆 记忆ID
/查看角色卡
/选择角色卡
/转告主人 内容
/留言给主人 内容
```

## 当前规划

- `v0.1`: QQ + NapCatQQ + NoneBot2 + DeepSeek 基础聊天，已跑通。
- `v0.2`: 权限、安全、白名单、黑名单、冷却和长度限制，已实现第一批和中文管理命令。
- `v0.3`: SQLite 聊天记录、试用次数持久化和基础记忆管理，已实现第一批。
- `v0.4`: 会话摘要压缩，已实现第一批。
- `v0.5`: 旧长期回忆摘要已退出正式运行链路，当前保留主人手动长期记忆。
- `v0.6`: 人格表达提示词和发言者身份识别，已实现第一批。
- `v0.7`: 群聊主动回复规则评分，已实现第一批，默认关闭。
- `v0.8`: 主人通知与转告，已实现第一批。
- `v0.9`: 视觉识图与图片上下文，已实现第一批。
- `v1.0`: 稳定性与双通道诊断，已实现第一批。
- `v1.2`: 记忆系统运行结构，短时 40 条、正式压缩 80/40、空窗场景摘要和手动长期记忆。
- `v1.3`: LangGraph Agent Runtime 设计，规划主 Agent / 聊天 Agent 分离、权限图、工具风险分级和主人审批。

## 文档

- [方案 C：NoneBot2 自研 QQ AI 机器人](docs/plan-c-nonebot.md)
- [NapCatQQ 接入 NoneBot2](docs/napcatqq-setup.md)
- [v0.2 权限与安全设计](docs/v0.2-access-control.md)
- [v0.3 SQLite 记忆方案](docs/v0.3-sqlite-memory.md)
- [v0.4 记忆压缩方案](docs/v0.4-memory-compression.md)
- [v0.5 长期回忆摘要](docs/v0.5-long-term-memory.md)
- [v0.6 人格表达提示词方案](docs/v0.6-persona-expression.md)
- [v0.7 群聊主动回复方案](docs/v0.7-group-auto-reply.md)
- [v0.8 主人通知与转告方案](docs/v0.8-owner-notifications.md)
- [v1.2 记忆系统运行设计](docs/v1.2-memory-runtime.md)
- [v1.3 LangGraph Agent Runtime 设计](docs/v1.3-langgraph-agent-runtime.md)
- [v0.9 视觉识图与图片上下文方案](docs/v0.9-vision-image-context.md)
- [v1.0 稳定性与双通道诊断方案](docs/v1.0-diagnostics-and-operations.md)
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
