# 运行维护手册

这份文档用于记录 AIchatbot 的日常启动、停止、重启、权限管理和常见故障处理。

## 运行组件

机器人运行时需要两个组件同时在线：

```text
NoneBot2 后端
NapCatQQ / QQ 接入端
```

链路：

```text
QQ
  -> NapCatQQ
  -> OneBot v11 WebSocket
  -> NoneBot2
  -> DeepSeek
  -> QQ 回复
```

## 日常启动

### 1. 启动 NoneBot2 后端

打开第一个 PowerShell：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

看到以下内容表示后端启动成功：

```text
Uvicorn running on http://127.0.0.1:8080
```

这个窗口不要关闭。

### 2. 启动 NapCatQQ

打开第二个 PowerShell：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1 2700318954
```

如果需要扫码，使用手机 QQ 扫码授权。

这个窗口也不要关闭。

## 日常停止

在两个 PowerShell 窗口中分别按：

```text
Ctrl + C
```

或者直接关闭窗口。

关闭窗口后机器人会停止运行，但项目文件不会丢失。

## 日常重启

如果只是修改了机器人代码、`.env` 配置或提示词，一般只需要重启 NoneBot2 后端：

```text
关闭 .\scripts\start.ps1 窗口
重新运行 .\scripts\start.ps1
```

NapCatQQ 不一定需要重启。

如果 QQ 掉线、WebSocket 连接异常或 NapCat 状态异常，再重启 NapCatQQ：

```text
关闭 NapCat 窗口
重新运行 .\scripts\start-napcat-shell.ps1 2700318954
```

## 注意事项

启动机器人前，不建议先手动打开普通 QQ 登录机器人账号。

原因：

```text
普通 QQ 可能占用账号，导致 NapCatQQ 无法接管登录。
```

推荐习惯：

```text
不要先打开普通 QQ
直接使用 .\scripts\start-napcat-shell.ps1 2700318954 启动
```

## WebUI

NapCat WebUI 地址通常是：

```text
http://127.0.0.1:6099
```

正常日常使用不需要打开 WebUI。

只有以下情况需要进入 WebUI：

- OneBot WebSocket 连接失败
- 需要查看 NapCat 日志
- 需要修改网络配置
- 更换 QQ 账号
- NapCat 更新后配置异常

当前 OneBot v11 WebSocket 客户端配置：

```text
URL: ws://127.0.0.1:8080/onebot/v11/ws
Token: 留空
消息格式: Array
```

## 权限配置

权限来源有两部分：

```text
.env 静态配置
data/access.json 动态配置
data/chatbot.db 聊天上下文和私聊试用次数
```

最终权限是两者合并：

```text
最终权限 = .env 名单 + data/access.json 名单
```

### .env

`.env` 用于保存敏感配置和默认配置。

不要提交 `.env` 到 GitHub。

关键配置：

```env
BOT_OWNER_QQ=3313097998
BOT_OWNER_PUBLIC_NAME=雨泽
BOT_ALIASES=

PRIVATE_WHITELIST=
ALLOW_UNKNOWN_PRIVATE_CHAT=false
PRIVATE_TRIAL_MESSAGES=3
PRIVATE_RATE_LIMIT_SECONDS=10
MAX_PRIVATE_MESSAGE_LENGTH=150

GROUP_WHITELIST=
GROUP_RATE_LIMIT_SECONDS=5
MAX_GROUP_MESSAGE_LENGTH=300
ENABLE_GROUP_AUTO_REPLY=false
GROUP_AUTO_REPLY_THRESHOLD=50
GROUP_AUTO_REPLY_COOLDOWN_SECONDS=60
GROUP_AUTO_REPLY_OWNER_COOLDOWN_SECONDS=30
GROUP_AUTO_REPLY_USER_COOLDOWN_SECONDS=120
ENABLE_OWNER_NOTIFICATIONS=true
OWNER_NOTIFICATION_MAX_LENGTH=50
OWNER_NOTIFICATION_GLOBAL_COOLDOWN_SECONDS=60
OWNER_NOTIFICATION_GROUP_COOLDOWN_SECONDS=120
OWNER_NOTIFICATION_USER_COOLDOWN_SECONDS=300

USER_BLACKLIST=

ENABLE_MEMORY_COMPRESSION=true
MAX_CONTEXT_MESSAGES=40
MAX_STORED_MESSAGES_PER_SESSION=120
SUMMARY_KEEP_RECENT_MESSAGES=40
SUMMARY_BATCH_MESSAGES=80
SUMMARY_MIN_SOURCE_MESSAGES=40
MAX_SESSION_SUMMARIES_IN_CONTEXT=3
ENABLE_GAP_SCENE_SUMMARIES=true
GAP_SCENE_SUMMARY_1_THRESHOLD=40
GAP_SCENE_SUMMARY_2_THRESHOLD=80
MAX_GAP_SCENE_SUMMARIES_IN_CONTEXT=2
ENABLE_LONG_TERM_MEMORY_CONTEXT=true
MAX_LONG_TERM_MEMORIES_IN_CONTEXT=8
RULE_REMINDER_INTERVAL_MESSAGES=40
```

`BOT_OWNER_PUBLIC_NAME` 是可选项，用于填写允许机器人对外说明的主人公开称呼或 QQ 名字；不填则只公开 `BOT_OWNER_QQ`。

`BOT_ALIASES` 是全局追加别名，可留空。角色卡专属主动回复别名优先写在 `prompts/persona-cards/private/*.auto-reply.json`；公开仓库只提交 `prompts/persona-cards/public/` 下的脱敏模板。

`ENABLE_GROUP_AUTO_REPLY` 控制非 @ 群消息主动回复，默认关闭。开启后仅对白名单群生效，并受评分阈值和冷却限制。

`ENABLE_OWNER_NOTIFICATIONS` 控制主人转告通知，默认开启。转告命令只接受 50 字以内纯文本，超过后回复“请主动联系主人，文本过长不予转告。”。

`SUMMARY_MIN_SOURCE_MESSAGES` 控制最低摘要门槛，默认 40 条消息，约等于 20 轮问答。未达到门槛时不会生成摘要。

`ENABLE_GAP_SCENE_SUMMARIES` 控制空窗场景状态摘要。开启后，当前会话未压缩原文超过 40 条时生成第 1 条空窗摘要，超过 80 条时生成第 2 条空窗摘要，超过 120 条后正式压缩旧 80 条并清理已覆盖的空窗摘要。

`ENABLE_LONG_TERM_MEMORY_CONTEXT` 控制手动长期记忆是否注入上下文。长期事实摘要和主人偏好摘要只由主人通过命令手动维护，系统不会让 AI 自动写入长期记忆。

`RULE_REMINDER_INTERVAL_MESSAGES` 控制长上下文短版底层规则提醒间隔，默认每累计 40 条会话消息提醒一次。设置为 `0` 可关闭。

### data/access.json

`data/access.json` 用于保存 QQ 内动态修改的白名单和黑名单。

不要提交 `data/access.json` 到 GitHub。

结构：

```json
{
  "private_whitelist": [],
  "group_whitelist": [],
  "user_blacklist": []
}
```

## QQ 管理命令

以下管理命令只有主人可以使用。

### 帮助

```text
/权限帮助
```

### 群白名单

把当前群加入白名单：

```text
/启用本群
```

把当前群移出白名单：

```text
/禁用本群
```

按群号加入：

```text
/加入群白名单 群号
```

按群号移出：

```text
/移出群白名单 群号
```

查看群白名单：

```text
/群白名单
```

### 私聊白名单

加入私聊白名单：

```text
/加入私聊白名单 QQ号
```

移出私聊白名单：

```text
/移出私聊白名单 QQ号
```

查看私聊白名单：

```text
/私聊白名单
```

### 黑名单

加入黑名单：

```text
/加入黑名单 QQ号
```

移出黑名单：

```text
/移出黑名单 QQ号
```

查看黑名单：

```text
/黑名单
```

## 普通命令

清空当前会话上下文：

```text
/重置
```

查看机器人状态：

```text
/状态
```

`/状态` 只有主人可以使用。

查看 SQLite 记忆状态：

```text
/记忆状态
```

`/记忆状态` 只有主人可以使用。

`/记忆状态` 会显示 MemoryRAG 开关和 Embedding 自检摘要。`/RAG状态` 会显示更完整的 MemoryRAG 索引状态，并用固定测试文本真实调用当前 embedding provider。默认配置下这条链路使用 Ollama `bge-m3`；如果 `bge-m3` 或 Ollama embedding 服务失败，普通聊天仍会继续，但 MemoryRAG / ProjectDocRAG 的语义搜索会不可用，最近错误中通常会出现 `EmbeddingProviderError`。

清空全部会话上下文：

```text
/清空全部上下文
```

`/清空全部上下文` 只有主人可以使用。它只清空聊天上下文，不清空白名单、黑名单和私聊试用次数。

查看当前摘要压缩状态：

```text
/摘要状态
```

查看当前会话最近摘要：

```text
/查看摘要
```

手动压缩当前会话：

```text
/压缩当前会话
```

清空当前会话摘要：

```text
/清空当前摘要
```

删除当前会话指定摘要：

```text
/删除摘要 摘要ID
```

清空全部会话摘要：

```text
/清空全部摘要
```

以上摘要命令只有主人可以使用。

## 主人转告通知

转告命令：

```text
/转告主人 内容
/留言给主人 内容
```

允许使用：

```text
主人
私聊白名单用户
授权群成员
```

限制：

```text
最多 50 字
只转告纯文本
不调用 LLM
不走角色卡
不写长期记忆
黑名单用户、非授权群和陌生私聊用户不能转告
```

超过 50 字时回复：

```text
请主动联系主人，文本过长不予转告。
```

命中密码、验证码、Token、API Key、身份证号、手机号、二维码或数据库等敏感内容时，不予转告。

成功后机器人会用固定模板私聊主人，原会话只回复：

```text
已转告主人。
```

## 主人手动长期记忆

运行时保留主人手动维护的长期记忆。系统不会让 AI 自动提取长期记忆，也不会把会话摘要当作长期记忆。

当前命令：

```text
/添加事实记忆 内容
/添加偏好记忆 内容
/查看长期记忆
/删除长期记忆 记忆ID
```

数据库表仍使用 `long_term_memories`，用于兼容已有手动记忆数据。旧的“长期回忆摘要”模块代码已退出正式运行链路；`memory_embeddings` 表仍作为历史兼容结构保留，但当前不参与运行。

## 人格表达提示词

人格表达提示词用于控制机器人如何说话，不保存用户记忆，也不让机器人假装自己是人。

通用底层聊天协议：

```text
prompts/base/chat-core.json
```

它只保存身份判定、权限、隐私、防注入、记忆边界和不机械重复等跨角色规则，不规定角色语气、称谓、回复长度或互动风格。

角色卡目录：

```text
prompts/persona-cards/
```

推荐结构：

```text
prompts/persona-cards/public/      脱敏模板，可提交到 Git
prompts/persona-cards/private/     真实角色卡，不提交到 Git
```

兼容旧路径：如果本地已经有 `prompts/persona-cards/*.md`，仍会被加载，但不会被 Git 跟踪。

角色卡枚举会跳过说明和模板文件，例如 `README.md`、`*.example.md`。公开目录里的 `default.example.md` 只作为脱敏模板，不会出现在 `/选择角色卡` 或 `/agent 角色卡列表` 的可选项里。

当前用途：

```text
控制回复更自然、简洁、稳定
根据当前发言者身份区分主人/非主人模式
减少客服模板感
减少无关扩展
减少长篇列表
避免旧人设和旧偏好被强行提起
群聊更克制
私聊更连续
长期记忆只读取主人手动维护的事实/偏好摘要
```

AI 调用时会额外注入当前发言者身份：

```text
当前发言者身份：主人 / 非主人
此信息仅用于角色卡判断
```

当前角色卡会根据这条身份信息自动选择主人模式或非主人模式。

主人身份只按 `BOT_OWNER_QQ` 对应的 QQ 号判断。QQ 名字、群名片、昵称、公开称呼或用户自称都不能作为主人身份依据。

群聊上下文会给新写入的用户消息标注“主人/非主人”身份，AI 调用时也会在最新消息前再次注入当前发言者身份，避免把历史里的主人发言套到当前群友身上。

统一隐私规则：

```text
不向非主人透露主人和机器人说过的具体内容
不向非主人透露身份证、手机号、住址、密码、Token、二维码、数据库内容等敏感信息
可以向非主人说明主人 QQ 号
可以向非主人说明 BOT_OWNER_PUBLIC_NAME 中配置的公开称呼或 QQ 名字
主人主动告诉机器人的公开称呼或名字，也可以说明
不确定是否公开的信息，默认不透露
```

查看当前角色卡内容：

```text
/查看角色卡
```

列出或选择角色卡：

```text
/选择角色卡
/选择角色卡 moyan
```

`/选择角色卡` 不带参数时会列出可选角色卡，带参数时会切换当前角色卡。

以上命令只有主人可以使用。

## SQLite 数据库

v0.3 开始，聊天上下文和陌生人私聊试用次数会保存到：

```text
data/chatbot.db
```

这个文件是本地运行数据，不要提交到 GitHub。当前 `.gitignore` 已经忽略 `data/*`。

数据库里主要保存：

```text
messages: 私聊和群聊上下文
private_trials: 陌生人私聊试用次数
session_summaries: 会话摘要
long_term_memories: 主人手动长期记忆
memory_embeddings: 历史兼容表，当前不参与运行
schema_meta: 数据库版本
```

重启 NoneBot2 后端后，近期上下文会继续保留。

当前版本已经预留分层记忆结构：

```text
第一层：短期对话缓存，已启用
第二层：会话摘要压缩，已启用
第三层：主人手动长期记忆，已启用
第四层：语义索引，当前不参与运行
```

摘要压缩规则：

```text
每次回复后检查当前会话原始消息数量
超过 MAX_STORED_MESSAGES_PER_SESSION 后自动压缩旧消息
自动压缩时保留最近 SUMMARY_KEEP_RECENT_MESSAGES 条原文
自动压缩每次最多压缩 SUMMARY_BATCH_MESSAGES 条旧消息
手动执行 /压缩当前会话 时，会把上次摘要后的未摘要消息压缩到最新一条
待摘要消息少于 SUMMARY_MIN_SOURCE_MESSAGES 时，不生成摘要
摘要生成优先保留主人明确说过的需求、决定、纠正、验收结果、待办和边界
事实分析只做客观归类，不分析主人的性格、动机或情绪价值
每次调用 AI 时最多带入 MAX_SESSION_SUMMARIES_IN_CONTEXT 条最近摘要
每累计 RULE_REMINDER_INTERVAL_MESSAGES 条会话消息，回复前追加一次短版底层规则提醒
```

## 限制规则

私聊：

```text
主人可以私聊
私聊白名单用户可以私聊
普通用户默认不能私聊
私聊消息限制 150 字
普通用户私聊冷却 10 秒
主人不受冷却限制
```

群聊：

```text
只有群白名单中的群可以使用
白名单群内所有非黑名单成员可以 @机器人
非 @ 群消息默认不主动回复
开启 ENABLE_GROUP_AUTO_REPLY 后，非 @ 群消息会先进入规则评分器
群聊消息限制 300 字
普通用户群聊冷却 5 秒
主人不受冷却限制
主动回复群冷却默认 60 秒
主动回复主人冷却默认 30 秒
主动回复普通用户冷却默认 120 秒
主人主动回复不受群全局主动回复冷却影响
非白名单群静默不回复
```

主动回复第一版只使用规则评分，不调用额外模型判断。主要加分项：

```text
提到机器人名字
主人在群里提问
主人在群里自我否定
有人诋毁主人
群友明确求助或提问
```

普通闲聊、短句、命令、超长消息、非白名单群消息不会触发主动回复。

主动回复触发规则会随当前角色卡变化。每张角色卡可以有一个配套配置：

```text
prompts/persona-cards/moyan.auto-reply.json
```

这个文件保存该角色卡专属的机器人别名、召唤词、自我否定词、护卫触发词等。莫言当前支持“小莫”“小言”“莫管家”等别名。

黑名单：

```text
私聊静默
群聊静默
管理命令不可用
```

## 常见问题

### 机器人不回复

按顺序检查：

1. `.\scripts\start.ps1` 窗口是否还在运行。
2. NapCatQQ 窗口是否还在运行。
3. QQ 是否掉线。
4. 当前群是否在群白名单中。
5. 是否真正 @ 到机器人账号。
6. 用户是否在黑名单中。
7. 消息是否超过长度限制。
8. 是否触发冷却。

### WebUI 显示无需重复登录

通常是普通 QQ 已经登录了同一个账号。

处理：

1. 关闭普通 QQ。
2. 关闭 NapCatQQ。
3. 重新运行：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1 2700318954
```

### AI 调用失败

先运行 DeepSeek 测试脚本：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe scripts\test_deepseek.py
```

如果脚本返回 `OK`，说明 DeepSeek 配置可用。

如果机器人仍然失败，查看：

```text
logs/ai_chat_error.log
```

## MainAgent /agent 只读主 Agent 运行

`/agent` 是主人私聊显式触发的主 Agent 管理入口。它不是普通聊天上下文的一部分；ProjectDocRAG 只通过 `dev_context` 进入 `/agent` 显式开发侧查询，不进入普通聊天。

当前 MainAgentGraph 已接入 ToolRegistry。真实 `/agent` runner 的 LLM 可见工具包括 `dev_context`、`owner_read_command`、`agent_task_read` 和 `owner_write_command`；隐藏的确定性控制面工具 `agent_task_command` 用于创建/取消任务、确认/拒绝审批和审批演练，不交给 LLM 自由调用。`ActionRequest` 的 `tool_request` 会先经过 registry 校验工具名、参数和工具风险等级，再进入 `ToolPolicyCheck`。`owner_write_command` 必须审批，确认后仅已注册且 `approval_resume_enabled=true` 的工具会受控恢复执行；`dry_run_write_file` 只在显式 dry-run/test registry 中存在，`llm_visible=false`，用于审批链路测试，不写文件。

当前边界：

```text
只允许主人私聊。
允许 dev_context、owner_read_command、agent_task_read 等只读工具。
允许 owner_write_command 创建审批；确认后可恢复已注册的主人管理写工具。
owner_write_command 缺少必要参数时不会创建审批：选择角色卡必须带 key，添加事实/偏好记忆必须带内容，删除摘要必须带数字 summary_id，动态名单修改必须带数字 QQ 号或群号。
清空全部上下文、清空全部摘要、删除长期记忆等批量/高风险写意图会在 /agent 内直接停止，不进入 dev_context、LLM 猜测或审批恢复。
允许 /agent 任务和审批固定/语义控制命令写入 agent_tasks / agent_task_events / agent_approvals。
ProjectDocRAG 只在 /agent 显式命令中使用，不进入普通聊天。
不执行 shell。
不执行任意文件写入。
MainAgent/LLM 不直接写数据库；任务、审批和已审批主人管理工具由受控代码写入。
不发送额外 QQ 消息。
不接 Agent API。
不跑多步 agent loop。
```

P1 起，MainAgent 允许“多步只读诊断”，但仍不是多步写执行。当前第一条聚合诊断命令是：

```text
/agent 完整排查图片识别问题
/agent 完整排查记忆检索问题
```

图片识别排查只读取视觉/Ollama 状态、图片缓存状态、最近错误、RootGraph 最近观测和 MainAgent 最近观测，然后返回步骤、初步判断和证据区。它不会清理缓存、修改配置、写数据库或发送额外 QQ 消息。

记忆检索排查只读取 MemoryRAG/Embedding 状态、RAG 索引统计、最近错误、RootGraph MemoryRAG 观测和 MainAgent 最近观测。它不会重建索引、写入记忆、删除文档、修改配置、写数据库或发送额外 QQ 消息。

### 启动只读 stub 模式

stub 模式不调用真实 Main LLM，适合先确认 `/agent` 命令和 `dev_context` 是否正常：

```powershell
cd D:\AIchatbot

$env:ENABLE_MAIN_AGENT="true"
$env:MAIN_AGENT_USE_LLM="false"

.\.venv\Scripts\python.exe .\bot.py
```

QQ 测试：

```text
/agent 状态
/agent 边界
/agent 任务 整理 MainAgentGraph 下一步计划
/agent 新增任务：整理审批流
/agent 把“整理审批流”加入任务
/agent 任务状态
/agent 任务详情 1
/agent 取消任务 1
/agent 审批演练 整理版本日志 dry-run
/agent 审批状态
/agent 审批详情 最新
/agent 确认 最新
/agent 任务详情 最新
/agent 完整排查图片识别问题
/agent 完整排查记忆检索问题
/agent 下一步
/agent 现在卡在哪
/agent 有什么待我确认
/agent-debug 下一步
```

### 启动真实 Main LLM 模式

真实 Main LLM 模式会让主模型生成 ActionRequest，并在 `dev_context` 返回后对 `tool_result` 做自然语言总结。推荐先用前台窗口启动，方便观察错误。

```powershell
cd D:\AIchatbot

$env:ENABLE_MAIN_AGENT="true"
$env:MAIN_AGENT_USE_LLM="true"
$env:MAIN_LLM_BASE_URL="https://你的-openai-compatible-api-base-url/v1"
$env:MAIN_LLM_MODEL="中转侧支持的模型名"
$env:MAIN_LLM_API_KEY="你的 key"

.\.venv\Scripts\python.exe .\bot.py
```

不要把 `MAIN_LLM_API_KEY` 写入文档、日志或 Git 提交。若要长期固化配置，只能写入本地 `.env`，且 `.env` 不得提交。

QQ 测试顺序：

```text
/agent 状态
/agent 任务 整理 MainAgentGraph 下一步计划
/agent 新增任务：整理审批流
/agent 把“整理审批流”加入任务
/agent 任务状态
/agent 任务详情 1
/agent 取消任务 1
/agent 审批演练 整理版本日志 dry-run
/agent 审批状态
/agent 审批详情 最新
/agent 确认 最新
/agent 任务详情 最新
/agent 完整排查图片识别问题
/agent 完整排查记忆检索问题
/agent-debug MainAgentGraph 当前状态
/agent 查 MainAgentGraph 当前状态
/agent 帮我执行 dir
```

任务协作查询：

```text
/agent 下一步
/agent 现在卡在哪
/agent 接下来该做什么
/agent 有什么待我确认
```

这些命令只读当前会话的 agent_tasks / agent_approvals，优先级是：待审批 > 失败任务 > 待处理任务 > 无事项。它们不会创建任务、确认审批、恢复工具或执行任何写操作。

任务详情卡和审批详情卡会互相挂钩：任务详情会列出关联审批、状态和建议操作；审批详情会列出关联任务、任务状态和最近事件。两者都只是读取 agent_tasks / agent_task_events / agent_approvals，不调用 Main LLM 或 dev_context。

预期结果：

```text
/agent 状态
  入口开启，LLM 已接入 /agent ActionRequest 生成。
  显示主模型名和主模型 Key 是否配置。
  不显示 MAIN_LLM_API_KEY 原文，也不显示 MAIN_LLM_BASE_URL。

/agent 任务 ...
  创建 pending 任务记录。
  当前版本只记录任务，不自动执行 shell、写文件或写数据库。
  该命令不触发 Main LLM 或 dev_context。

/agent 新增任务：...
/agent 记录任务：...
/agent 把“...”加入任务
  这些是明确创建任务的本地别名。
  只走固定解析规则，不调用 Main LLM 做语义判断。
  不明确的自然句不会自动创建任务。

/agent 任务状态
  列出当前会话和当前用户最近任务。
  该命令不触发 Main LLM 或 dev_context。

/agent 任务详情 <任务ID>
  展示当前会话任务详情卡、关联审批摘要和事件记录。
  如果任务有待审批项，会提示 /agent 确认 <审批ID> 或 /agent 拒绝 <审批ID>。
  该命令不触发 Main LLM 或 dev_context。

/agent 取消任务 <任务ID>
  只允许取消当前会话、当前用户的 pending 任务。
  会写入 cancelled 事件。
  不执行任何工具。

/agent 审批演练 <目标>
  创建一个 Route B dry-run 任务和一个 dry_run_write_file 审批请求。
  回复会明确显示 任务ID：#X 和 审批ID：#Y。
  会写入 created 和 approval_requested 事件。
  不调用 Main LLM 或 dev_context。
  不写文件、不执行 shell、不发送额外 QQ 消息、不恢复执行。
  这是当前推荐的 QQ 侧审批闭环实测入口。

/agent 审批状态
  列出当前会话和当前用户最近审批记录。
  未执行审批演练时通常为空，因为还没有开放真实写工具。
  如果内部链路创建了审批请求，会同时写入 approval_requested 任务事件。
  该命令不触发 Main LLM 或 dev_context。

/agent 审批详情 <审批ID>
  展示当前会话审批详情卡、关联任务摘要和最近任务事件。
  也可以用 /agent 审批详情 最新 查看当前会话最近审批。
  该命令不触发 Main LLM 或 dev_context。

/agent 确认 <审批ID>
/agent 拒绝 <审批ID>
  只允许决定当前会话、当前用户的 pending 审批。
  也可以用 /agent 确认 最新 或 /agent 拒绝 最新 操作当前会话最近审批。
  会更新 agent_approvals.status / decided_at，并写入 agent_task_events 审批决定事件。
  只有已注册且 approval_resume_enabled=true 的工具会在确认后受控恢复；其他工具只记录审批决定，不恢复执行。
  该命令不触发 Main LLM 或 dev_context。

内部审批请求链路：
  create_agent_approval 会写入 agent_approvals。
  同时追加 agent_task_events: approval_requested。
  可用 format_agent_approval_requested 生成给主人看的审批请求回复。
  create_tool_policy_checker 会把 PolicyEngine 的 require_approval 决策转换为 approval_required 中断。
  中断阶段只返回审批请求，不进入 execute_tool。
  当前仅开放已注册且启用审批恢复的工具在主人确认后受控恢复，不开放任意 shell、任意真实写文件或未注册数据库写入。

/agent-debug ...
  返回原始 dev_context / CombinedRAG 召回。

/agent 查 ...
  返回主 Agent 自然语言总结。

/agent 帮我执行 dir
  必须拒绝 shell，不能执行命令。
```

### Main LLM 连接失败

如果 QQ 返回：

```text
MainAgentGraph rejected: main llm failed: Connection error.
```

或返回新的中文短提示：

```text
MainAgentGraph rejected: 主模型连接失败，请检查 MAIN_LLM_BASE_URL、网络、代理或中转服务。
```

同时可以查看本地错误日志：

```powershell
Get-Content D:\AIchatbot\logs\ai_chat_error.log -Tail 20
```

MainAgent LLM 失败日志会记录：

```text
phase
error_type
error
model
base_url
api_key_configured
```

日志不会记录 `MAIN_LLM_API_KEY` 原文；`base_url` 只保留 scheme、host、port 和 path，不保留 query 或用户名密码。

优先检查机器是否能连到 `MAIN_LLM_BASE_URL` 对应域名的 443 端口：

```powershell
Test-NetConnection api.openai.com -Port 443
```

如果直连 OpenAI 不通，可以使用 OpenAI 兼容中转。`MAIN_LLM_BASE_URL` 要填中转站的 API Base URL，不是网页首页。比如中转文档里的请求地址是：

```text
https://api.example.com/v1/chat/completions
```

则配置：

```powershell
$env:MAIN_LLM_BASE_URL="https://api.example.com/v1"
```

如果使用本地代理，代理变量必须在启动 bot 的同一个 PowerShell 窗口设置：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"
```

### 关闭后台 bot 进程

如果曾用后台方式启动 bot，需要切回前台调试，可以先关闭后台 `bot.py`：

```powershell
$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "python*" -and $_.CommandLine -like "*bot.py*"
}
$procs | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
}
```

### 修改 .env 后不生效

`.env` 只在机器人启动时读取。

修改 `.env` 后需要重启 NoneBot2 后端：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

`scripts/start.ps1` 会先调用 `scripts/ensure-ollama.ps1`：如果视觉或 Ollama-backed RAG 需要本地 Ollama，它会检查 `http://127.0.0.1:11434/api/tags`，确认 `qwen2.5vl:3b` / `bge-m3` 等必需模型是否可见；如果 11434 未监听或模型目录被托盘版 Ollama 接管，会调用 `scripts/start-ollama-vision.ps1` 用 `OLLAMA_MODELS=D:\OllamaModels` 重新拉起本地 `ollama serve`。

临时跳过启动前 Ollama 自检：

```powershell
.\scripts\start.ps1 -SkipOllamaEnsure
```

### 动态白名单不生效

确认命令是否由主人发送。

查看：

```text
/群白名单
/私聊白名单
/黑名单
```

如果 `data/access.json` 损坏，可以关闭机器人后手动修复或删除该文件，再重启机器人。

## 视觉识图运行说明

视觉识图使用本地 Ollama，不走 DeepSeek 接口。

确认模型存在：

```powershell
ollama list
```

应能看到：

```text
qwen2.5vl:3b
```

如果 Windows 用户名包含中文，建议使用纯英文模型目录：

```powershell
$env:OLLAMA_MODELS
```

期望输出：

```text
D:\OllamaModels
```

如果识图报错中出现 `C:\Users\����\.ollama\models`，说明实际监听 `127.0.0.1:11434` 的 Ollama server 仍在使用默认中文用户目录。需要关闭 `ollama app.exe` 托盘程序和旧的 `ollama.exe`，再用正确环境变量启动 server。

推荐用项目脚本启动视觉 Ollama：

```powershell
.\scripts\start-ollama-vision.ps1
```

日常启动机器人时更推荐直接使用：

```powershell
.\scripts\start.ps1
```

它会先执行 `scripts/ensure-ollama.ps1`，只有在 11434 不可用或必需模型不可见时才重启 Ollama。单独检查 Ollama 而不启动：

```powershell
.\scripts\ensure-ollama.ps1 -NoStart
```

如果要把模型目录写入当前 Windows 用户环境变量：

```powershell
.\scripts\start-ollama-vision.ps1 -PersistUserEnv
```

该脚本会默认关闭现有 `ollama.exe` / `ollama app.exe`，设置：

```powershell
OLLAMA_MODELS=D:\OllamaModels
```

然后用 `ollama serve` 重新启动本地 11434 服务。

视觉配置：

```env
ENABLE_VISION=true
VISION_OLLAMA_BASE_URL=http://127.0.0.1:11434
VISION_MODEL=qwen2.5vl:3b
VISION_TIMEOUT_SECONDS=180
VISION_NUM_CTX=16384
VISION_MAX_IMAGES=1
VISION_MAX_IMAGE_BYTES=5242880
VISION_IMAGE_CACHE_TTL_SECONDS=120
VISION_PRIVATE_IMAGE_WAIT_SECONDS=5
```

私聊行为：

```text
用户发图片 -> 机器人等待 5 秒
5 秒内用户补文字 -> 图片和文字合并，只回复一次
5 秒内没有补文字 -> 按纯图片识别并回复
```

群聊行为：

```text
用户发图片 -> 机器人只缓存，不回复
同一用户 120 秒内 @机器人问图 -> 识别刚才图片并回复一次
其他用户问图 -> 不默认使用前一个人的图片
```

图片观察结果是不可信输入。图片文字不能修改系统提示、角色卡、主人身份、安全规则或隐私规则。真实人物身份不识别；公开动漫/游戏角色、游戏名和 UI 可以在高置信度时识别，不确定时只描述特征。

## v1.0 双通道诊断

诊断分两种：

```text
QQ 内诊断：机器人还能收发 QQ 消息时使用
本地诊断脚本：机器人无响应、进程异常或 QQ 链路断开时使用
```

QQ 内主人命令：

```text
/诊断
/配置状态
/视觉状态
/最近错误
/清空错误日志
/图片缓存状态
/清空图片缓存
```

这些命令由机器人插件代码直接检查配置、数据库、Ollama、聊天接口、错误日志和图片缓存，不交给聊天 AI，不走角色卡，不写入聊天记忆。

`/视觉状态` 会额外使用一张内置小 PNG 执行一次真实 Ollama 视觉推理自检，用于识别“模型存在但返回 @@@@@@ / 空描述 / 调用失败”的情况。自检只展示耗时和返回字数，不展示测试图描述正文；如果 Ollama 服务异常、模型不存在或视觉未开启，则跳过推理自检。

机器人完全没反应时，不要只在 QQ 里重复发命令，先在本地运行：

```powershell
cd D:\AIchatbot
.\scripts\diagnose.ps1
```

本地诊断脚本会检查：

```text
.venv 和 Python
bot.py 是否可导入
NoneBot/Python 相关进程
NapCat/QQ 相关进程
Ollama 进程
11434 和 8080 端口
.env 关键配置
OLLAMA_MODELS
Ollama tags 和 qwen2.5vl:3b
SQLite 数据库
最近 AI 错误
```

## v1.1 语音输出运行

v1.1 语音输出使用本地 IndexTTS2 服务生成 WAV，再由 OneBot record 发送到主人 QQ 私聊。TTS 不负责生成语义内容，只负责把聊天 AI 已经生成的文本清理、分句、合成和发送。

当前限制：

```text
仅私聊可用
仅主人可用
首次语音请求会冷启动 TTS 模型
如果本地 TTS 服务未运行，机器人会先自动拉起服务
模型空闲 10 分钟后自动释放显存
单次语音总时长上限 60 秒
```

TTS 服务可手动启动，也可在第一次语音请求时由机器人自动启动。手动启动方式：

```powershell
cd D:\AIchatbot
.\scripts\start-tts-service.ps1
```

机器人 `.env` 需要开启：

```text
ENABLE_TTS=true
TTS_SERVICE_URL=http://127.0.0.1:7861
TTS_VOICE=zh_kelin_raw_20260625_222137
TTS_EMOTION=affection
TTS_MAX_CHARS=180
TTS_MAX_TOTAL_SECONDS=60
TTS_AUTO_START=true
TTS_STARTUP_WAIT_SECONDS=45
```

QQ 私聊触发方式：

```text
用语音说：晚安，今天也辛苦了。
刚刚那句念给我听
请用语音给我说晚安
```

三类触发含义：

```text
直接文本语音：不调用聊天 AI，直接朗读冒号后的文本。
上一条回复语音：朗读最近一条主人私聊中机器人生成的可朗读回复。
语义语音回复：聊天 AI 按角色卡生成要说出口的内容，TTS 只负责朗读该回复。
```

日语语音已退出正式运行链路：

```text
当前正式 TTS 服务只加载中文 IndexTTS2。
历史日语验证材料已归档到本地 docs-archive/，该目录默认不提交到 Git。
```

如需检查旧日语测试是否污染 `data/chatbot.db`，先运行 dry-run：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe scripts\clean_japanese_history.py
```

确认数量后再执行删除：

```powershell
.\.venv\Scripts\python.exe scripts\clean_japanese_history.py --apply
```

语音文本会在合成前做轻量清理：

```text
删除括号和星号动作描写
狗修金 -> 主人
爱可 -> 我
保留轻度口吃和省略号停顿
按完整句子分段，段间约 550ms 停顿
```

状态命令：

```text
/语音状态
```

本地目录：

```text
D:\AIchatbot\tts-validation
D:\AIchatbot\voice-samples
D:\AIchatbot\temp_audio
```

这些目录包含本地模型、音色样本、临时音频和测试音频，不应提交到 GitHub。

详细设计和验证记录见：

```text
docs/v1.1-voice-output-draft.md
```

## Git 提交

查看状态：

```powershell
cd D:\AIchatbot
D:\AIchatbot\tools\PortableGit\cmd\git.exe status
```

提交：

```powershell
D:\AIchatbot\tools\PortableGit\cmd\git.exe add .
D:\AIchatbot\tools\PortableGit\cmd\git.exe commit -m "Update chatbot"
```

推送：

```powershell
D:\AIchatbot\tools\PortableGit\cmd\git.exe push
```

不要提交以下内容：

- `.env`
- `tools/`
- `tts-validation/`
- `.venv/`
- `data/access.json`
- `data/chatbot.db`
- `logs/`
- `__pycache__/`
- `*.egg-info/`

这些已在 `.gitignore` 中忽略。
