# 版本运行日志

本文作为 AIchatbot 的版本运行日志，用于汇总每个版本的实际落地状态、live 验证、补丁和后续边界。

文档分工：

```text
版本设计文档：
  记录该版本主要要实现的目标、边界和设计方案。

版本运行日志：
  记录该版本实际做到了哪里、哪些 live 验证已通过、哪些补丁已完成、哪些内容仍不开放。

每日 runlog：
  仅作为开发过程和上下文恢复材料；后续与版本具体内容相关的稳定结论，应整理回本文。

项目 RAG 使用手册：
  docs/project-rag-usage.md 保留为本地 RAG / DevContextGraph / Codex 恢复上下文手册。
```

## 当前总览

```text
普通聊天：
  ChatAgent 路线保持稳定。
  MemoryRAG 已可用于普通聊天语义记忆召回。

/agent：
  QQ live 只读 MainAgent 已验证。
  真实 MainAgent LLM 可生成 ActionRequest。
  真实可见工具只允许调用 dev_context。
  ActionRequest tool_request 已改为 ToolRegistry-backed 校验。
  dev_context 返回后可进行 tool_result 二次总结。
  /agent 任务 <目标> 可创建 pending 任务记录。
  /agent 新增任务：<目标> 等明确本地别名可创建 pending 任务记录。
  /agent 把“目标”加入任务 等明确本地别名可创建 pending 任务记录。
  /agent 任务状态 可查看当前会话任务。
  /agent 任务详情 <任务ID> 可查看任务和事件。
  /agent 取消任务 <任务ID> 可取消当前会话 pending 任务。
  /agent 审批演练 <目标> 可创建 dry-run 任务和审批请求，用于 QQ 侧实测 Route B。
  内部审批请求链路可生成 agent_approvals，并写入 approval_requested 任务事件。
  ToolPolicyCheck 适配层可将 require_approval 转为 approval_required 中断。
  /agent 审批状态 可查看当前会话审批记录。
  /agent 审批详情 <审批ID> 可查看审批详情。
  /agent 确认 <审批ID> 可确认当前会话 pending 审批，但不恢复执行。
  /agent 拒绝 <审批ID> 可拒绝当前会话 pending 审批，但不恢复执行。
  shell 越权请求已验证会拒绝。

项目文档 RAG：
  ProjectDocRAG 不进入普通聊天。
  ProjectDocRAG 只通过开发侧命令或 /agent owner 显式命令进入 dev_context。
```

当前不开放：

```text
shell 工具
写文件工具
真实写文件工具（dry_run_write_file 只用于内部 dry-run 审批测试，不写文件，且不对 LLM 可见）
数据库写工具（除 /agent 任务固定命令和内部审批记录链路写 agent_tasks / agent_task_events / agent_approvals）
额外 QQ 发送
Agent API
多步 agent loop
任务执行链路
审批恢复执行链路
长期记忆自动写入
角色卡自动修改
```

## v0.1 基础聊天

状态：已落地。

已完成：

```text
QQ -> NapCatQQ -> OneBot v11 -> NoneBot2 -> DeepSeek/OpenAI-compatible chat -> QQ 回复。
私聊和授权群聊基础回复可用。
```

## v0.2 权限与安全

状态：已落地。

已完成：

```text
主人识别。
私聊白名单。
群白名单。
黑名单。
冷却。
消息长度限制。
主人管理命令。
```

## v0.3 SQLite 记忆

状态：已落地。

已完成：

```text
data/chatbot.db 保存聊天上下文。
重启后短期上下文保留。
陌生人私聊试用次数持久化。
/记忆状态。
/清空全部上下文。
```

## v0.4 会话摘要压缩

状态：已落地。

已完成：

```text
session_summaries 表。
自动压缩旧聊天原文。
手动压缩当前会话。
查看、删除、清空摘要。
摘要参与普通聊天上下文。
```

## v0.5 主人手动长期记忆

状态：已落地，并完成旧长期回忆摘要退出。

当前结论：

```text
主人手动长期事实/偏好记忆保留。
旧长期回忆摘要退出正式运行链路。
AI 不自动写长期记忆。
```

## v0.6 人格表达提示词

状态：已落地。

已完成：

```text
base chat-core 底层协议。
角色卡加载。
主人 / 非主人身份注入。
/查看角色卡。
/选择角色卡。
人格表达只控制说话方式，不写入记忆。
```

## v0.7 群聊主动回复

状态：已落地，默认关闭。

已完成：

```text
ENABLE_GROUP_AUTO_REPLY 开关。
规则评分器。
群全局冷却、主人冷却、用户冷却。
角色卡配套 auto-reply 配置。
白名单群内非 @ 消息可按规则评分决定是否回复。
```

仍不做：

```text
随机插话。
大模型判断是否主动回复。
跨群主动关联。
AI 自动写记忆。
```

## v0.8 主人通知与转告

状态：已落地。

已完成：

```text
/转告主人 内容。
/留言给主人 内容。
固定模板私聊主人。
长度限制。
敏感内容拒绝。
不调用 LLM。
不走角色卡。
不写长期记忆。
```

## v0.9 视觉识图与图片上下文

状态：已落地。

已完成：

```text
本地 Ollama 视觉模型。
私聊图片等待合并文字。
群聊图片缓存后按 @ 查询。
图片观察结果不可信，不能改写系统规则、主人身份或隐私边界。
VisionGraphRunner 已接入。
图片段支持 file / path / file_id / url。
支持 http(s)、data:image、本地绝对路径和 file://。
```

稳定运行经验：

```text
视觉模型建议使用 scripts/start-ollama-vision.ps1 启动。
该脚本会设置 OLLAMA_MODELS=D:\OllamaModels 并用 ollama serve 启动 11434。
如果托盘版 ollama app.exe 接管中文用户目录，可能出现 CLIP/mmproj 路径乱码和 HTTP 500。
出现 C:\Users\ÓêÔó 或 Failed to load CLIP model 时，先关闭托盘版 Ollama，再运行 start-ollama-vision.ps1。
```

## v1.0 稳定性与双通道诊断

状态：已落地第一批。

已完成：

```text
QQ 内诊断命令。
本地 diagnose.ps1。
配置状态。
最近错误。
视觉状态。
图片缓存状态。
错误日志清空。
DiagnosticsGraphRunner 已接入。
NotificationGraphRunner 已接入 /转告主人 链路。
```

已验证：

```text
/诊断、/配置状态、/视觉状态、/最近错误、/图片缓存状态、/记忆状态、/语音状态可用。
/转告主人 保持固定模板、长度限制、敏感内容拒绝和冷却，不调用 LLM。
```

## v1.1 语音输出

状态：已落地第一批。

已完成：

```text
本地 IndexTTS2。
主人私聊语音输出。
直接文本朗读。
上一条回复朗读。
语义语音回复。
TTS 服务自动拉起。
VoiceGraphRunner 已接入。
DIRECT_TEXT / LAST_REPLY / SEMANTIC_REPLY 三类语音请求已统一。
```

稳定运行经验：

```text
IndexTTS2 推理可能较慢，更多是显存、GPU 状态或冷启动问题，不是 VoiceGraph 链路问题。
如经常超时，优先检查 TTS 服务状态和 TTS_TIMEOUT_SECONDS。
```

## v1.2 记忆系统运行结构

状态：已落地。

当前结构：

```text
短期原文。
会话摘要。
空窗场景摘要。
主人手动长期记忆。
语义 MemoryRAG。
MemoryContextGraphRunner。
MemoryPersistGraphRunner。
MemoryAdminGraphRunner。
```

当前边界：

```text
AI 不自动写长期记忆。
长期事实和偏好由主人命令手动维护。
正式摘要和长期记忆可参与 MemoryRAG。
```

已完成 Graph 化：

```text
MemoryContextGraph：
  ENSURE_GAP_SCENE
  BUILD_MANUAL_MEMORY_CONTEXT
  RETRIEVE_SEMANTIC_MEMORY
  BUILD_HISTORY

MemoryPersistGraph：
  SAVE_USER_MESSAGE
  SAVE_ASSISTANT_MESSAGE
  SCHEDULE_COMPRESSION

MemoryAdminGraph：
  VALIDATE_ADMIN_REQUEST
  EXECUTE_ADMIN_OPERATION
  RENDER_ADMIN_REPLY
```

MemoryAdminGraph 已接入：

```text
/摘要状态
/查看摘要
/查看空窗摘要
/压缩当前会话
/压缩当前对话
/清空当前摘要
/清空当前对话摘要
/删除摘要
/清空全部摘要
/添加事实记忆
/添加偏好记忆
/查看长期记忆
/删除长期记忆
/清空全部上下文
```

## v1.3 LangGraph Agent Runtime

状态：部分落地，QQ live 只读 MainAgent 已验证。

已完成：

```text
RootGraph 显式分发。
RuntimeIntent.MAIN_AGENT。
DevContextGraph。
MainAgentGraph。
ActionRequest schema。
ToolRegistry v0。
ToolPolicyCheck。
CALL_MAIN_AGENT stub。
MainAgent LLM adapter。
LangChain MainAgent wrapper。
QQ /agent 只读入口。
/agent-debug 原始召回入口。
MAIN_AGENT_USE_LLM 显式开关。
真实 MainAgent LLM QQ live 验证。
tool_result 二次总结。
main_llm_failed 失败观测日志。
shell 越权请求拒绝验证。
/agent 状态主模型摘要。
/agent 状态不显示主模型接口。
常见 Main LLM 错误 QQ 侧友好化。
agent_tasks 表。
agent_task_events 表。
agent_approvals 表。
approval_requested 任务事件。
/agent 任务 <目标> 固定命令。
/agent 新增任务：<目标>、/agent 记录任务：<目标>、/agent 把“目标”加入任务 等固定本地别名。
/agent 任务状态 固定命令。
/agent 任务详情 <任务ID> 固定命令。
/agent 取消任务 <任务ID> 固定命令。
/agent 审批状态 固定命令。
/agent 审批详情 <审批ID> 固定命令。
```

已验证 live 行为：

```text
/agent 状态 可用。
/agent 查 MainAgentGraph 当前状态 可由真实主模型回复。
/agent-debug MainAgentGraph 当前状态 可返回原始 dev_context / CombinedRAG。
/agent 帮我执行 dir 会拒绝 shell，不执行命令。
/agent 任务 整理 MainAgentGraph 下一步计划 只创建 pending 任务记录。
/agent 新增任务：整理审批流 只创建 pending 任务记录。
/agent 把“整理审批流”加入任务 只创建 pending 任务记录。
不明确的自然句，例如“后面记得做一下审批流”，不会创建任务。
/agent 任务状态 只列出当前会话任务，不触发 LLM 或 dev_context。
/agent 任务详情 <任务ID> 只展示任务记录和事件，不触发 LLM 或 dev_context。
/agent 取消任务 <任务ID> 只把当前会话 pending 任务标记为 cancelled，并记录 cancelled 事件。
/agent 审批演练 <目标> 创建 dry-run 任务和 dry_run_write_file 审批请求，只用于实测审批闭环，不执行工具。
审批演练回复会明确显示 任务ID：#X 和 审批ID：#Y，并支持 审批详情 最新、确认 最新、拒绝 最新、任务详情 最新。
内部审批请求创建会写入 agent_approvals，并追加 approval_requested 任务事件，不触发执行。
PolicyEngine 返回 require_approval 时，create_tool_policy_checker 会触发 approval_required 中断，不进入 execute_tool。
/agent 审批状态 只列出当前会话审批，不触发 LLM 或 dev_context。
/agent 审批详情 <审批ID> 只展示审批记录，不恢复执行。
/agent 确认 <审批ID> 只把当前会话 pending 审批标记为 approved，并记录审批决定事件，不恢复执行。
/agent 拒绝 <审批ID> 只把当前会话 pending 审批标记为 rejected，并记录审批决定事件，不恢复执行。
/agent 审批详情 最新、/agent 确认 最新、/agent 拒绝 最新、/agent 任务详情 最新 可直接操作当前会话最近记录，避免手动查 ID。
MainAgentGraph 的 tool_request 现在通过 ToolRegistry 校验注册工具、参数和风险等级；真实 registry 只向 LLM 暴露 dev_context。
dry_run_write_file 只在显式 dry-run/test registry 中注册，llm_visible=false，risk_level=write_local，进入 approval_required 中断但不执行真实写入。
```

当前 `/agent 状态` 会显示：

```text
入口是否开启。
只读模式。
可用工具 dev_context。
ToolRegistry v0，当前真实可见工具仍只有 dev_context。
任务状态和事件记录能力。
审批请求生成、查看、确认和拒绝能力；确认或拒绝不恢复执行。
Main LLM 是否接入 ActionRequest 生成。
主模型名。
主模型 Key 是否配置。
```

`MAIN_LLM_API_KEY` 原文不在 QQ 状态、文档或日志中显示；`MAIN_LLM_BASE_URL` 也不在 `/agent 状态` 中展示，只保留在本地配置和脱敏错误日志中。

Main LLM 常见错误会在 QQ 侧转换为中文短提示：

```text
Connection error -> 主模型连接失败，请检查 MAIN_LLM_BASE_URL、网络、代理或中转服务。
timeout -> 主模型请求超时。
401 / unauthorized -> 主模型鉴权失败。
404 / model_not_found -> 主模型或接口不存在。
429 / quota / rate limit -> 主模型额度或限流异常。
```

当前仍不开放：

```text
shell 工具。
写文件工具。
数据库写工具。例外：/agent 任务固定命令和内部审批记录链路只写 agent_tasks / agent_task_events / agent_approvals，不由 MainAgent/LLM 执行。
额外 QQ 发送。
Agent API。
多步 agent loop。
任务执行链路。
审批恢复执行链路。
```

## v1.4 语义记忆检索与项目文档 RAG

状态：核心能力已落地，并已被 MainAgentGraph 只读调用。

已完成：

```text
MemoryRAG。
ProjectDocRAG。
CombinedRAG。
DevContextGraph。
ProjectDocRAG 本地索引脚本。
QQ 侧 MemoryRAG 调试命令。
MainAgentGraph 通过 dev_context 只读查询项目上下文。
```

QQ 侧 MemoryRAG 已验证：

```text
/RAG状态
/记忆检索 查询内容
/重建记忆索引
普通聊天 MemoryRAG 自动注入
旧问题问答可通过 RAG 召回补充
```

当前推荐参数形态：

```text
ENABLE_MEMORY_RAG=true
MEMORY_RAG_INJECT_IN_CHAT=true
MEMORY_RAG_TOP_K=5
MEMORY_RAG_MIN_SCORE=0.55
MEMORY_RAG_MAX_CONTEXT_CHARS=1600
MEMORY_RAG_OWNER_ONLY_DEBUG=true
```

如果召回偏泛，可观察后再收紧为：

```text
MEMORY_RAG_TOP_K=3
MEMORY_RAG_MIN_SCORE=0.60
MEMORY_RAG_MAX_CONTEXT_CHARS=1000
```

ProjectDocRAG 扫描范围：

```text
README.md
docs/**/*.md
prompts/base/**/*.json
prompts/persona-cards/public/**/*.md
```

ProjectDocRAG 明确排除：

```text
.git
.venv
data
docs-archive
logs
prompts/persona-cards/private
temp_audio
tools
tts-validation
voice-samples
__pycache__
.env*
*.db
*.sqlite
*.sqlite3
*.log
```

CombinedRAG 稳定边界：

```text
只用于本地脚本、开发侧工具、Codex 上下文恢复和 MainAgentGraph dev_context。
不注册 QQ 普通命令。
不进入普通聊天上下文。
输出保持项目文档召回和记忆召回分区。
```

当前边界：

```text
MemoryRAG 可以进入普通聊天上下文。
ProjectDocRAG 不进入普通聊天上下文。
ProjectDocRAG 只在本地开发命令或 /agent owner 显式命令下通过 dev_context 查询。
```

保留手册：

```text
docs/project-rag-usage.md
```

## 后续整理规则

从当前阶段开始：

```text
关于版本目标、核心边界和设计原则：
  写入对应 vX.Y 版本设计文档。

关于该版本实际完成、live 验证、补丁、失败经验和下一步：
  写入本文。

关于每日开发过程和临时恢复上下文：
  可以继续写每日 runlog，但稳定结论应回填本文。

关于 ProjectDocRAG / DevContextGraph / Codex 恢复上下文用法：
  保留并更新 docs/project-rag-usage.md。
```
