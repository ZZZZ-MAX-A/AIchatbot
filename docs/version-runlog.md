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

## v1.5 MemoryRAG embedding 自检

状态：已落地。`/记忆状态` 和 `/RAG状态` 现在会显示当前 MemoryRAG embedding 链路的真实自检结果。

本次完成：
```text
新增 check_embedding_provider，使用固定测试文本真实调用当前 embedding provider。
默认配置下该自检会验证 Ollama bge-m3 是否能返回可用向量。
自检请求沿用 MEMORY_RAG_EMBEDDING_DIMENSION 校验，并将诊断超时上限限制为 20 秒。
/记忆状态 新增 MemoryRAG 开关和 Embedding 自检摘要。
/RAG状态 新增 Embedding 自检详情。
自检成功时展示耗时和向量维度；失败时展示 provider 错误摘要。
```

边界：
```text
不读取用户聊天内容，不读取记忆正文。
不记录 embedding 向量，不写数据库，不重建索引。
不改变普通聊天 MemoryRAG 注入逻辑。
不改变 ProjectDocRAG 与 QQ 普通聊天的隔离边界。
bge-m3 失效时，普通聊天继续兜底运行，但 MemoryRAG / ProjectDocRAG 语义搜索不可用。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary tests.test_rag_units -v
Ran 24 tests OK
```

## v1.5 /视觉状态 推理自检

状态：已落地。`/视觉状态` 现在除了检查 Ollama `/api/tags` 和视觉模型是否存在，还会用一张内置的小型 PNG 测试图执行一次真实的 Ollama 视觉推理。

本次完成：
```text
新增 diagnostic_vision_image_base64，使用标准库生成 32x32 PNG 测试图，不依赖 Pillow/cv2。
新增 check_vision_inference，复用真实 Ollama /api/chat 视觉链路。
自检请求沿用 VISION_NUM_CTX，但将诊断超时上限限制为 45 秒，避免 /视觉状态 长时间卡死。
/视觉状态 新增“推理自检”行，成功时只展示耗时和返回字数。
如果 Ollama 服务异常、视觉模型不存在或视觉未开启，则跳过推理自检。
如果模型返回 @@@@@@ 这类低质量重复内容，自检会显示失败原因。
```

边界：
```text
不记录测试图的模型描述正文。
不读取用户图片，不记录图片 URL。
不改变普通聊天图片识别链路。
不改变 RootGraph 路由、聊天权限、图片缓存策略或视觉安全脱敏策略。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_diagnostics_units tests.test_vision_voice_units -v
Ran 24 tests OK
```

## 当前总览

```text
普通聊天：
  ChatAgent 路线保持稳定。
  MemoryRAG 已可用于普通聊天语义记忆召回。

/agent：
  QQ live 只读 MainAgent 已验证。
  真实 MainAgent LLM 可生成 ActionRequest。
  真实可见工具包括 dev_context、owner_read_command、agent_task_read、owner_write_command。
  隐藏的确定性控制面工具包括 agent_task_command，用于语义创建/取消任务、确认/拒绝审批、创建审批演练。
  ActionRequest tool_request 已改为 ToolRegistry-backed 校验。
  dev_context 返回后可进行 tool_result 二次总结；本地管理工具结果直接返回，避免角色卡语气污染。
  owner_read_command 可语义触发诊断、最近错误、多步只读图片识别/记忆检索排查、角色卡、角色卡列表、模型配置、访问控制、摘要、RAG、记忆检索、RAG索引详情、MainAgent观测、白名单等只读主人管理查询。
  agent_task_read 可语义触发任务列表、任务详情、审批列表、审批详情。
  agent_task_command 可语义触发任务/审批控制面操作，但不暴露给 LLM 工具契约。
  owner_write_command 已开放清空图片缓存、清空错误日志、选择角色卡、添加事实/偏好长期记忆、清空当前会话摘要、删除当前会话指定摘要、动态黑白名单修改；必须先生成审批，确认后才恢复执行。
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
  /agent 确认 <审批ID> 可确认当前会话 pending 审批；仅已注册且启用 approval_resume_enabled 的工具会受控恢复。
  /agent 拒绝 <审批ID> 可拒绝当前会话 pending 审批，不恢复执行。
  /agent 工具状态 / /agent 能力列表 可列出当前开放语义工具、风险等级、可见性、审批要求和示例命令。
  shell 越权请求已验证会拒绝。

项目文档 RAG：
ProjectDocRAG 不进入普通聊天。
ProjectDocRAG 只通过开发侧命令或 /agent owner 显式命令进入 dev_context。

RootGraph：
  v1.5 RootGraph 统一运行入口设计已新增：docs/v1.5-rootgraph-runtime.md。
  RootGraphRunner Phase 1 已补齐 normalize_event / load_actor_context / hard_policy_gate / route_intent / build_runtime_context / dispatch_capability / commit_side_effects / render_response 节点序列。
  RootGraph artifact 现在记录 policy、route、context、commit 和 root_graph 元数据。
  RootGraph 可稳定分发 MAIN_AGENT / CHAT / IGNORE；owner private MAIN_AGENT 放行，非 owner MAIN_AGENT 在 RootGraph 层提前拒绝，不进入 MainAgentGraph。
  handler 异常会被 RootGraph 捕获并写入 state.error 与 root_graph.error。
  本轮全量单测：$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  Ran 238 tests OK。
```

当前不开放：

```text
shell 工具
写文件工具
真实写文件工具（dry_run_write_file 只用于内部 dry-run 审批测试，不写文件，且不对 LLM 可见）
数据库写工具（除 /agent 任务固定命令、agent_task_command 控制面语义命令、内部审批记录链路，以及已审批的注册 owner_write_command 主人管理写命令）
额外 QQ 发送
Agent API
多步 agent loop
通用真实任务执行链路
通用真实审批恢复执行链路（目前仅 owner_write_command 已注册主人管理命令和 dry_run_write_file 可恢复）
长期记忆自动写入
角色卡自动修改
清空全部上下文或删除记忆
```

## v1.6 MainAgent 单步审批闭环第一步

状态：已落地第一步。目标是先修正 MainAgent “语义上答应了，但控制层没有真实执行或没有明确阻止”的体验问题。当前先以“删除当前会话指定摘要”为黄金路径收紧参数、审批和恢复执行边界。

本次完成：

```text
删除当前会话摘要必须携带数字 summary_id。
/agent 删除摘要 123 仍会进入 owner_write_command，并创建审批，不会立即执行。
/agent 删除摘要、/agent 删除摘要 最新、/agent 删除当前摘要 会进入 ask_owner，提示先查看摘要 ID；不会创建审批，也不会删除任何摘要。
真实 MainAgent LLM 如果生成缺少 summary_id 的 owner_write_command/delete_session_summary，也会在 ActionRequest 校验后以 need_argument 中断，不会进入审批。
owner_write_command executor 统一复用命令参数校验，缺 target/content/summary_id 的写命令不会被执行。
审批请求回复新增“尚未执行，等待主人确认”提示，避免把 approval_requested 误读为已执行。
非 dry-run 审批恢复回复新增“执行状态/执行结果”，让确认审批和真实工具结果分开可见。
/agent 同意、/agent 通过、/agent 执行吧、/agent 不同意 等裸确认/拒绝语义现在被解析为“隐式最新审批”引用；只有 QQ 入口解析到唯一 pending 审批时才会实际确认/拒绝，多个 pending 时要求指定审批 ID。
修复审批恢复执行中的 SQLite 锁问题：resume_agent_approval 现在先记录 tool_resume_started 并提交，再关闭 agent_tasks 写事务后执行真实工具，最后重新打开连接记录 tool_resume_finished 或 tool_resume_failed。
新增真实 session_summaries 删除恢复测试，覆盖 owner_write_command/delete_session_summary 在审批恢复阶段再次写数据库的场景，避免外层任务事务锁住摘要删除。
新增真实 long_term_memories 写入恢复测试，覆盖 owner_write_command/add_fact_memory 在审批恢复阶段再次写数据库的场景。
补齐 owner_write_command 语义预检：选择角色卡缺 target、添加事实/偏好记忆缺 content、动态名单修改缺数字 target 时直接 ask_owner，不进入 dev_context、LLM 猜测或审批创建。
已知禁止批量写意图会直接停止：清空全部摘要、清空全部上下文、删除长期记忆；不会创建审批，也不会执行清理或删除。
owner_read_command 在只读路由前先识别写意图，避免“使用角色卡”等写请求被误判成查看角色卡。
任务/审批边界文案更新为“不执行任意 shell、任意真实写文件或未注册数据库写入”，和已审批注册写工具的真实执行能力保持一致。
修复角色卡列表枚举：`README.md` 和 `*.example.md` 这类说明/模板文件不再作为可选角色卡展示，也不能被 `/选择角色卡` 选中。
本地验证当前 `prompts/persona-cards/` 只展示 `aike`、`moyan` 两张真实角色卡。
QQ live 已验证：/agent 删除摘要 <ID> -> /agent 确认 最新 -> 当前会话摘要实际删除成功。
```

边界：

```text
普通聊天里的“同意”不触发 MainAgent；仍必须走 /agent 入口。
缺少摘要 ID 时不猜“最新摘要”或“第二条摘要”。
delete_session_summary 仍只作用于当前会话，不跨会话删除。
owner_write_command 仍必须先审批，确认后才恢复执行。
不开放 shell、任意文件写入、未注册数据库写入、多步写操作自动执行、删除长期记忆、清空全部上下文或清空全部摘要。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge tests.test_persistence_units -v
Ran 64 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary tests.test_graph_runners -v
Ran 53 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 268 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 46 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 18 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_operation_units tests.test_memory_rag_qq_boundary -v
Ran 22 tests OK
```

## v1.6 MainAgent 多步只读诊断第一步

状态：已落地第一条 P1 多步只读诊断命令。目标是让 MainAgent 不只是调用单个状态页，而是能为常见故障读取多个只读证据源并给出可验证的判断。

本次完成：

```text
新增 owner_read_command/vision_troubleshoot。
/agent 完整排查图片识别问题 和 /agent 排查识图为什么失败 会语义路由到 vision_troubleshoot。
广义 “诊断一下 Ollama / 看一下视觉和记忆状态” 仍保持 ops_health 聚合诊断；单独看视觉状态仍可走 vision_status。
QQ 执行 vision_troubleshoot 时会依次读取：
  1. DiagnosticsGraph 视觉/Ollama 状态
  2. DiagnosticsGraph 图片缓存状态
  3. 最近错误日志
  4. RootGraph 最近聊天观测
  5. MainAgent 最近观测
返回内容包含步骤、初步判断、视觉/Ollama 证据、图片缓存证据、最近错误证据、RootGraph 证据和 MainAgent 证据。
回复中明确只读保证：未清理缓存、未修改配置、未写入数据库、未发送额外 QQ 消息。
视觉排查判断逻辑移入 diagnostics 纯函数，避免 “Ollama 服务：正常” 被误判为异常。
RootGraph Vision detail 会按 errors / low_quality 的正数计数判断，不会因为同一批观测里同时存在 0 和非 0 而漏报。
```

边界：

```text
只读多步诊断不等于多步任务执行。
不开放清空图片缓存、修改视觉配置、拉取模型、重启 Ollama 或发送额外 QQ 消息。
不读取新的用户图片，不下载外部网络资源；视觉自检只复用 DiagnosticsGraph 的 Ollama 状态和内置测试图。
普通聊天仍不会触发 MainAgent 诊断，必须走 /agent 主人私聊入口。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_diagnostics_units -v
Ran 5 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 46 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 9 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 272 tests OK
```

## v1.6 MainAgent 多步只读诊断第二步

状态：已落地第二条 P1 多步只读诊断命令，复用图片识别排查的报告形态，补上 MemoryRAG/Embedding/索引链路的主人侧可观测性。

本次完成：

```text
新增 owner_read_command/memory_rag_troubleshoot。
/agent 完整排查记忆检索问题 和 /agent 排查 MemoryRAG 为什么没有召回 会语义路由到 memory_rag_troubleshoot。
显式 /agent 记忆检索 <查询内容> 仍保持 memory_retrieval，不会被排查命令抢走。
同时包含图片和 RAG 的广义问题，例如“最近图片和 RAG 有没有问题”，仍保持 ops_health 聚合诊断。
QQ 执行 memory_rag_troubleshoot 时会依次读取：
  1. MemoryRAG/Embedding 状态和 embedding 自检
  2. RAG 索引详情
  3. 最近错误日志
  4. RootGraph MemoryRAG 最近观测
  5. MainAgent 最近观测
返回内容包含步骤、初步判断、MemoryRAG/Embedding 证据、RAG 索引证据、最近错误证据、RootGraph 证据和 MainAgent 证据。
回复中明确只读保证：未重建索引、未写入记忆、未删除文档、未修改配置、未写入数据库、未发送额外 QQ 消息。
MemoryRAG 排查判断逻辑移入 diagnostics 纯函数，覆盖 RAG 关闭、聊天注入关闭、embedding 自检失败、索引为空、向量为空、待索引、RootGraph commit 错误、最近召回 0 命中和最近错误日志非空。
```

边界：

```text
只读多步诊断不等于自动修复。
不开放重建索引、写入长期记忆、删除 RAG 文档、修改 embedding 配置、重启 Ollama 或发送额外 QQ 消息。
该命令会执行现有 MemoryRAG 状态自检；embedding 自检只使用固定测试文本，不读取用户记忆正文。
普通聊天仍不会触发 MainAgent 诊断，必须走 /agent 主人私聊入口。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_diagnostics_units -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 46 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 276 tests OK
```

## v1.6 Ollama 启动前自愈

状态：已落地本地启动脚本层面的 Ollama ensure，解决频繁出现的 `WinError 10061` / 11434 未监听问题。

本次完成：

```text
新增 scripts/ensure-ollama.ps1。
scripts/start.ps1 默认先调用 ensure-ollama，再启动 bot.py。
ensure-ollama 会读取当前进程环境变量和 .env，判断是否需要本地 Ollama：
  ENABLE_VISION=true
  或 ENABLE_MEMORY_RAG / ENABLE_PROJECT_DOC_RAG=true 且 MEMORY_RAG_EMBEDDING_PROVIDER=ollama
如果不需要 Ollama，则直接跳过。
如果需要 Ollama，则检查 http://127.0.0.1:11434/api/tags。
检查必需模型：
  视觉：VISION_MODEL，默认 qwen2.5vl:3b
  MemoryRAG/ProjectDocRAG：MEMORY_RAG_EMBEDDING_MODEL，默认 bge-m3
如果 11434 未监听、/api/tags 不可用或必需模型不可见，且目标是本地 11434，则调用 scripts/start-ollama-vision.ps1。
start-ollama-vision 会用 OLLAMA_MODELS=D:\OllamaModels 重新拉起 ollama serve。
支持临时跳过：.\scripts\start.ps1 -SkipOllamaEnsure 或设置 SKIP_OLLAMA_ENSURE=1。
支持只检查不启动：.\scripts\ensure-ollama.ps1 -NoStart。
```

边界：

```text
不在 MainAgent/ChatAgent 运行时中自动启动外部进程。
不在 QQ 消息处理过程中拉起 Ollama。
只改本地启动脚本，保持运行时边界清晰。
如果配置为远程或非 11434 Ollama 地址，ensure 只检查，不尝试启动本地服务。
```

## v1.6 MainAgent 任务协作第一步

状态：已落地 P1.3 小范围任务协作增强。目标是让 `/agent 下一步` 从“查开发上下文”转为“只读任务协作台”，优先告诉主人当前卡点和最该处理的一步。

本次完成：

```text
新增 agent_task_read/next_step 只读命令。
/agent 下一步、/agent 现在卡在哪、/agent 接下来该做什么、/agent 有什么待我确认 会走任务协作摘要，不再默认进入 dev_context。
协作摘要读取当前会话 agent_tasks / agent_task_events / agent_approvals。
建议优先级：
  1. 有待审批：提示查看审批详情，并确认或拒绝具体审批。
  2. 有失败任务：提示查看失败任务详情。
  3. 有待处理任务但无审批：提示查看任务详情，并说明当前版本不会自动多步执行普通任务。
  4. 无待处理事项：提示可创建任务或显式 /agent 查 <问题>。
协作摘要会列出待主人确认项和近期任务，并显示最近事件摘要。
```

边界：

```text
这是只读协作查询，不创建任务、不取消任务、不确认/拒绝审批、不恢复工具。
普通聊天仍不会触发 MainAgent 任务协作。
/agent-debug 下一步 仍可走原始 dev_context 调试路径；普通 /agent 下一步 走任务协作摘要。
不开放多步自动执行任务、自动修复失败任务、shell、任意文件写入或未注册数据库写入。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 278 tests OK
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
/agent 审批详情 <审批ID> 展示审批记录；不会触发执行。
/agent 确认 <审批ID> 把当前会话 pending 审批标记为 approved；仅 dry_run_write_file 会进入受控 dry-run resume。
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
审批请求生成、查看、确认和拒绝能力；确认后仅 dry-run 工具会受控恢复。
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
真实任务执行链路。
真实审批恢复执行链路。
```

### 2026-07-04 Route B dry-run resume update

```text
MainAgent Route B now supports a narrow approval resume path for dry-run tools.
/agent approve/confirm still scopes approvals by current session and user.
Only approved dry_run_write_file approvals can resume.
The resume path uses ToolRegistry to require and validate the registered tool.
It records tool_resume_started and tool_resume_finished task events.
It marks the drill task done with the dry-run ToolResult.
It is idempotent: repeated resume attempts do not execute again.
Unapproved approvals, non-current-session approvals, repeated resume attempts, and non-dry-run tools do not resume.
No real file writes, shell commands, database business writes, extra QQ sends, or LLM-visible write tools were opened.
QQ live verified:
  /agent approval drill xxx
  /agent confirm latest
  /agent task detail latest
Result:
  task reached done
  events include approval_requested, approval_approved, tool_resume_started, tool_resume_finished
  dry_run_write_file returned side_effect: none
```

### 2026-07-04 Approval Resume Runner safety gate

```text
The approval resume path has been extracted behind resume_agent_approval(...).
resume_agent_approval_dry_run(...) remains as a compatibility wrapper.
ToolSpec now has approval_resume_enabled, default false.
dev_context keeps approval_resume_enabled=false.
dry_run_write_file has approval_resume_enabled=true, requires_approval=true, llm_visible=false.
/agent confirm now calls the generic registry-backed resume runner.
The runner requires:
  current session/user scoped approval
  approved approval status
  registered enabled tool
  approval_resume_enabled=true
  validated ToolRegistry arguments
Repeated resume attempts remain idempotent.
Tools registered without approval_resume_enabled do not resume even after approval.
No real write, shell, database business write, extra QQ send, or LLM-visible write tool was opened.
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

## MainAgent owner_read_command 语义只读管理工具

状态：第一批只读语义主人命令骨架已落地，保留原 QQ 斜杠命令。

本次完成：

```text
ToolRegistry 新增 owner_read_command 可见工具。
owner_read_command 仅开放只读诊断/状态类命令：
  diagnostics
  config_status
  vision_status
  recent_errors
  image_cache_status
  memory_status
  memory_retrieval
  bot_status
  rag_status
  summary_status
  view_summaries
  view_gap_scene_summaries
  view_long_term_memory
  view_persona
  tts_status
  group_whitelist
  private_whitelist
  blacklist
/agent 语义入口可把“帮我看一下最近错误”等请求映射到 owner_read_command。
/agent 语义入口可把“记忆检索 Route B 审批流”“查一下记忆里有没有审批流”等请求映射到 memory_retrieval，并复用原 MemoryRAG 检索图。
ToolRegistry 新增 agent_task_read 可见工具。
agent_task_read 仅开放任务/审批只读查询：
  list_tasks
  task_detail
  list_approvals
  approval_detail
可语义触发：
  /agent 看看任务表
  /agent 最新任务详情
  /agent 有没有待审批的东西
  /agent 最新审批详情
语义只读工具现在在 LLM/dev_context 前置拦截。
当 MAIN_AGENT_USE_LLM=true 时，明确命中的只读管理/任务查询不会先交给主模型去做项目 RAG 检索。
owner_read_command / agent_task_read 的工具结果现在直接返回，不再交给 LLM 二次总结。
原因：角色卡查看等管理输出如果被 LLM 总结，模型可能模仿角色卡语气；管理命令必须保持操作台式原文输出。
任务语义增加“任务卡/任务表/任务列表”说法，默认映射到 list_tasks。
原有 /诊断、/配置状态、/视觉状态、/最近错误、/图片缓存状态、/记忆状态 继续保留。
QQ RuntimeState 已把 message_id、session_key、session_type、user_id、actor_role、group_id、raw_text 注入 ToolContext.metadata。
```

边界：

```text
owner_read_command risk_level=read_local。
agent_task_read risk_level=read_local。
仍然只允许主人私聊默认执行。
owner_read_command 本身不清空日志，不清空图片缓存，不写数据库，不改白名单/黑名单，不切换角色卡。
agent_task_read 不创建任务、不取消任务、不确认审批、不拒绝审批、不恢复执行。
有副作用的主人管理命令必须走 owner_write_command 审批任务链路。
ProjectDocRAG 仍只通过 dev_context 进入 /agent，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_llm -v
```

## MainAgent owner_read_command 第二批只读工具

状态：第二批只读主人控制台查询已接入 owner_read_command，仍保留原 QQ 固定命令。

本次完成：

```text
新增只读命令：
  role_card_list
  model_config_status
  access_overview
  rag_index_detail
  main_agent_observations

可语义触发：
  /agent 看看有哪些角色卡
  /agent 角色卡列表
  /agent 看看模型配置
  /agent 当前主模型是什么
  /agent 看看访问控制
  /agent 权限状态
  /agent 看看项目文档索引
  /agent 看看记忆索引
  /agent RAG 索引详情
  /agent MainAgent 最近失败
  /agent 最近 agent 观测

role_card_list 只展示角色卡 key/title 和当前启用项，不输出角色卡正文。
model_config_status 只展示模型、base_url、超时和 Key 是否配置，不泄露 Key。
access_overview 汇总主人配置状态、私聊/群聊开关、白名单/黑名单数量和列表。
rag_index_detail 汇总 MemoryRAG / ProjectDocRAG 开关、embedding 配置和 rag_documents/rag_embeddings 分 namespace 统计。
main_agent_observations 从错误日志里筛选 MainAgent/LLM/tool summary 相关观测，方便定位语义命令是否误路由。
```

边界：

```text
全部 risk_level=read_local。
不切换角色卡，不修改模型配置，不修改白名单/黑名单，不重建索引，不清理日志。
普通聊天不触发这些工具。
本地管理工具结果继续直接返回，不交给 LLM 二次总结。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
```

## RootGraph / CHAT 只读观测入口

状态：RootGraph 普通聊天路径新增最近一次观测快照，并接入 `/agent` 只读语义工具。

本次完成：

```text
新增只读命令：
  root_graph_observations

可语义触发：
  /agent RootGraph 最近观测
  /agent RootGraph 状态
  /agent 看看普通聊天路由
  /agent chat commit 状态

普通聊天经 RootGraph CHAT 路径执行后，会记录最近一次非正文观测快照。
快照包含会话类型、消息 ID、是否有文本、是否有图片、Actor role、policy、route、context、commit、chat_runtime、chat_access_policy、chat_commit、shadow snapshot/validation 摘要。
快照不记录用户原文、不记录 LLM 回复正文，只记录布尔值、长度、计数和阶段信息。
```

边界：

```text
risk_level=read_local。
仅主人私聊默认执行。
不触发普通聊天，不调用 ChatGraph，不修改白名单/黑名单，不清理日志，不切换角色卡。
该入口用于回答“上一条普通聊天为什么处理/未处理、路由到哪里、副作用提交到哪一步”。
旧固定命令继续保留。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
```

## MainAgent owner_write_command 审批门控主人管理工具

状态：有副作用语义主人命令已接入 ToolRegistry 和审批恢复链路，保留原 QQ 固定命令作为 fallback。

本次完成：

```text
ToolRegistry 新增 owner_write_command 可见工具。
owner_write_command risk_level=write_local，requires_approval=true，approval_resume_enabled=true。
当前开放审批门控本地命令：
  clear_image_cache
  clear_error_log
  select_persona
  add_fact_memory
  add_preference_memory
  clear_session_summaries
  delete_session_summary
  allow_group
  deny_group
  allow_private
  deny_private
  block_user
  unblock_user

/agent 语义入口可把下列请求映射为 owner_write_command：
  /agent 帮我清空图片缓存
  /agent 帮我清空错误日志
  /agent 帮我选择角色卡 moyan
  /agent 帮我添加事实记忆 主人喜欢先看结论
  /agent 帮我添加偏好记忆 技术讨论先给结论
  /agent 帮我清空当前摘要
  /agent 删除摘要 123
  /agent 把群 123456 加入群白名单
  /agent 把群 123456 移出群白名单
  /agent 把用户 10001 加入私聊白名单
  /agent 把用户 10001 移出私聊白名单
  /agent 把用户 10002 加入黑名单
  /agent 解除拉黑 10002

命中后不会立刻执行工具，而是创建 agent_tasks + agent_approvals，并返回审批提示。
/agent 确认 <审批ID> 或 /agent 确认 最新 会在确认后通过注册表恢复执行对应工具。
恢复执行会写入 tool_resume_started / tool_resume_finished 事件。
重复确认同一个审批不会重复执行；已有 tool_resume_finished 时直接跳过。
拒绝审批后不会恢复执行。
```

边界：

```text
owner_write_command 仍只允许主人私聊走 /agent 入口。
普通聊天不触发 ProjectDocRAG，也不触发主人管理工具。
选择角色卡必须带明确 target 参数，确认审批后才调用 select_role_card。
添加事实/偏好长期记忆必须带明确 content 参数；/agent 私聊语义工具确认后只写 owner 用户自身长期记忆。
旧 /添加事实记忆、/添加偏好记忆 固定命令继续保留；需要群场景 fact 记忆时仍由旧命令兜底。
清空当前摘要只删除当前会话 session_summaries，不清空全部摘要。
删除摘要必须带数字 summary_id，且只删除当前会话中匹配的 session_summary。
动态黑白名单修改必须带数字 target；/agent 私聊语义工具确认后只修改 data/access.json 动态访问控制，不修改 .env 静态配置。
旧 /加入群白名单、/移出群白名单、/加入私聊白名单、/移出私聊白名单、/加入黑名单、/移出黑名单 固定命令继续保留。
旧 /启用本群、/禁用本群 仍由群聊固定命令兜底；/agent 当前仍是主人私聊入口，不支持无数字群号的“本群”语义写入。
不开放清空全部上下文、清空全部摘要、删除记忆、shell、任意文件写入或未注册数据库写入。
LLM 即使生成 tool_request，也必须通过 ToolRegistry 参数校验和 ToolPolicyCheck 审批中断。
只有注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge tests.test_persistence_units tests.test_main_agent_llm tests.test_memory_rag_qq_boundary -v
Ran 75 tests OK
```

## MainAgent agent_task_command 语义任务/审批控制面工具

状态：任务和审批控制面已接入确定性语义工具；原固定命令继续保留。

本次完成：

```text
ToolRegistry 新增 agent_task_command 工具。
agent_task_command risk_level=internal，llm_visible=false。
它不出现在主模型工具契约里，只由本地确定性语义分类器命中。

当前开放命令：
  create_task
  cancel_task
  approve_approval
  reject_approval
  create_approval_drill

可语义触发：
  /agent 帮我创建一个任务：整理审批流
  /agent 把整理 Route B 加入任务
  /agent 取消最新任务
  /agent 帮我确认最新审批
  /agent 拒绝审批 #7
  /agent 创建审批演练：写入版本日志

agent_task_command 在 agent_task_read 前面拦截，避免“确认最新审批”被误判成审批详情查询。
确认审批时沿用现有审批恢复链路；如果对应审批已执行过，不会重复执行。
```

边界：

```text
只允许主人私聊 /agent 入口。
不交给 LLM 自由选择，避免模型误确认或误取消。
只操作 agent_tasks / agent_task_events / agent_approvals 控制面记录。
确认审批可能恢复已经批准的注册工具，但仍受 approval_resume_enabled 和幂等事件保护。
普通聊天不触发 agent_task_command。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
```

## MainAgent 工具状态/能力列表

状态：QQ 侧已新增自描述能力面板，方便查看当前开放工具和边界。

本次完成：

```text
新增静态命令：
  /agent 工具状态
  /agent 能力列表
  /agent 工具列表

返回内容包括：
  dev_context
  owner_read_command
  agent_task_read
  agent_task_command
  owner_write_command
  dry_run_write_file（隐藏演练工具）

每个条目展示：
  风险等级
  LLM 可见性
  是否需要审批
  用途
  示例命令

同时明确当前不开放：
  shell
  任意文件写入
  未注册数据库写入
  删除长期记忆
  清空全部摘要
  清空全部上下文
```

边界：

```text
工具状态只是静态只读说明，不触发 ToolRegistry 执行，不调用 LLM，不写数据库。
普通聊天不触发；仅 /agent 静态命令入口返回。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
```

## v1.5 RootGraph CHAT 接入第一步

状态：已落地第一步，普通聊天入口开始经过 RootGraph 的 CHAT intent 分发。

本次完成：
```text
handle_chat 在非语义语音路径下改为 run_chat_via_root_graph。
RootGraph CHAT handler 复用现有 run_legacy_chat_session，不重写聊天主体逻辑，不改变现有 ChatGraph/legacy 分支的回复、持久化和压缩行为。
shadow_chat production_route 新增 root_graph_chat，用于标识普通聊天已从 RootGraph 外层进入。
run_legacy_chat_session 可接收预构建 shadow_state，并返回最终 ChatState，便于 RootGraph 同步 response、error 和 chat_graph artifact。
RootGraphRunner 新增 passthrough_exceptions，QQ matcher.finish / matcher.pause / matcher.reject 等 NoneBot 控制流不会被误包装成 Agent Runtime error。
语义语音路径暂时保留旧入口，避免 matcher.finish 控制流和语音提交链路在本步被扩大改动。
RootGraph 对 CHAT 的 response 使用 should_reply=false，因为实际 QQ 回复仍由现有聊天运行链路发送，避免重复回复。
```

边界：
```text
ProjectDocRAG 仍不进入普通聊天。
普通聊天仍不触发 MainAgent ToolRegistry 或主人管理工具。
RootGraph 当前只是普通聊天的外层调度和观测入口，尚未接管 check_access / check_message_limits / commit_side_effects 的全部职责。
旧固定命令继续由现有 NoneBot matcher 兜底。
```

测试：
```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners tests.test_graph_adapters_and_shadow -v
Ran 54 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 241 tests OK
```

## v1.5 RootGraph CHAT 权限前置第一步

状态：已落地。普通聊天在解析图片和进入聊天主体前，会先构建 `chat_access_policy` artifact，并交给 RootGraph hard policy 判定。

本次完成：
```text
新增 chat_access_policy artifact，记录普通聊天 preflight 的 allow/deny、reason、should_reply、response_text、actor_role、session_type、消息长度、限速等信息。
RootGraph hard_policy_gate 现在能读取 chat_access_policy；当 allow_dispatch=false 时，直接把 CHAT 路由改为 IGNORE，不进入聊天 handler。
已前置的普通聊天策略包括：
  私聊/群聊是否开启
  黑名单
  owner / 私聊白名单 / 陌生私聊试用
  群白名单
  私聊试用次数是否耗尽
  消息长度限制
  普通聊天限速
普通聊天非语义语音路径现在先构建 RuntimeState，再经 RootGraph CHAT 分发；图片上下文解析被移动到 CHAT handler 内，在 policy 放行后才执行。
旧 prepare_chat_request / check_access / check_message_limits 仍保留，并继续服务语义语音等旧路径，作为防御性兜底。
```

边界：
```text
本步没有把 owner 管理工具暴露给普通聊天。
ProjectDocRAG 仍不进入普通聊天。
RootGraph 只做硬策略和分发，不接管 ChatGraph 内部 prompt、MemoryRAG、持久化和压缩。
语义语音路径仍暂时走旧 prepare_chat_request，后续单独收敛。
```

测试：
```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners tests.test_graph_adapters_and_shadow tests.test_memory_rag_qq_boundary -v
Ran 60 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 243 tests OK
```

## v1.5 RootGraph CHAT 提交观测第一步

状态：已落地。RootGraph 仍不搬迁聊天数据库写入和 QQ 发送动作，但现有聊天链路会把关键提交结果写入 `chat_commit` artifact，RootGraph `commit` artifact 会统一汇总。

本次完成：
```text
新增 chat_commit artifact，用于记录普通聊天已完成的提交类动作。
普通 legacy chat 路径在 finalize_chat_result 中记录：
  persisted_turn_saved
  trial_updated
  qq_reply_sent
  tts_candidate_updated
  compression_scheduled
  reply_chars / stored_user_chars / stored_assistant_chars
ChatGraph runtime 路径在各 side-effect callback 中记录：
  persisted_turn_saved
  trial_updated
  tts_candidate_updated
  compression_scheduled
  voice_response_sent / voice_send_suppressed
render_chat_result 记录普通文本回复是否已经发送。
图片上下文等待合并时记录 image_context_deferred，不进入聊天主体。
RootGraph commit artifact 现在汇总：
  chat_reply_sent
  chat_voice_sent
  chat_persisted
  chat_trial_updated
  chat_compression_scheduled
  chat_tts_candidate_updated
  chat_image_context_deferred
  chat_runtime_stage
```

边界：
```text
本步只增加观测，不改变现有 QQ 回复、数据库持久化、试用次数、压缩调度和 TTS 候选更新的执行位置。
RootGraph 仍不直接执行聊天提交动作，只读取 handler 写入的 artifact。
ProjectDocRAG 仍不进入普通聊天。
```

测试：
```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners -v
Ran 44 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 244 tests OK
```

## v1.5 RootGraph error artifact 与审批恢复 metadata 清理

状态：已落地。RootGraph 在已有 `root_graph.error` 之外，新增结构化 `error` artifact；审批恢复上下文的 `resume_mode` 命名也从 dry-run 专用语义收敛为通用审批恢复语义。

本次完成：

```text
RootGraphRunner 在以下场景写入 artifacts["error"]：
  policy 拒绝，例如 chat_access_policy 阻断 CHAT 分发
  dispatch handler 抛出异常
  handler 自身设置 state.error 但没有抛异常

error artifact 字段：
  source
  message
  route
  policy_decision
  dispatched
  should_reply
  response_text_set

该 artifact 不记录用户原文，不记录 LLM 回复正文，只记录错误来源、路由和响应布尔状态。
root_graph.error 继续保留，兼容已有 RootGraph 最近观测和测试。

审批恢复 ToolContext.metadata：
  resume_mode=approval_resume
  resume_tool_name=<approval.tool_name>

这样 owner_write_command 恢复执行时不再被标成 dry_run；dry_run_write_file 仍保持无副作用演练工具语义。
```

边界：

```text
本步不改变 RootGraph 路由策略。
本步不迁移聊天副作用执行位置。
本步不新增任何 LLM 可见工具。
本步不开放 shell、任意文件写入、任意数据库写入或额外 QQ 发送。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners -v
Ran 45 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 15 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 42 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 245 tests OK
```

## v1.5 RootGraph 最近观测展示 error artifact

状态：已落地。`/agent RootGraph 最近观测` 现在会展示 RootGraph 结构化 `error` artifact 的摘要。

本次完成：

```text
RootGraph/CHAT 观测快照新增 error_artifact。
最近观测输出在存在 error_artifact 时展示：
  source
  route
  policy
  dispatched
  should_reply
  response_text
  message

该输出仍不记录用户原文，也不记录 LLM 回复正文。
旧 observation.error fallback 保留；没有结构化 error_artifact 时继续按旧 Error 行输出。
```

边界：

```text
本步只增强只读观测输出。
不改变 RootGraph 路由、权限、提交、副作用位置或审批策略。
普通聊天仍不触发 MainAgent 工具。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 5 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.RootGraphRunnerTests -v
Ran 12 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 246 tests OK
```

## v1.5 视觉电脑截图上下文与低质量输出兜底

状态：已落地。电脑截图经 `qwen2.5vl:3b` 识别时，默认 Ollama 上下文可能触发重复符号输出；本次将视觉请求默认 `num_ctx` 提升到 16384，并把 `@@@@@@@@...` 这类低信息量重复内容判为视觉失败。

本次完成：
```text
新增 VISION_NUM_CTX，默认 16384。
Ollama /api/chat 视觉请求写入 options.num_ctx。
新增低质量视觉描述检测，重复符号输出不再写入聊天上下文。
/配置状态 和 /视觉状态 展示视觉上下文配置。
.env.example、config/.env.example、docs/runbook.md 补充 VISION_NUM_CTX。
```

边界：
```text
不改变 RootGraph 路由、聊天权限、图片缓存策略和安全脱敏策略。
不引入图像处理依赖，不做截图切片；本次只修 Ollama 上下文和坏输出兜底。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_vision_voice_units -v
Ran 19 tests OK
```

## v1.5 RootGraph 最近观测展示 vision detail

状态：已落地。`/agent RootGraph 最近观测` 现在会展示普通聊天图片链路的非正文观测字段，便于定位图片未缓存、未解析、模型返回低质量内容或视觉上下文不足等问题。

本次完成：
```text
chat_commit 新增图片上下文观测字段：
  image_context_has_context
  image_context_url_count
  image_context_should_continue

chat_commit 新增视觉描述统计字段：
  vision_description_count
  vision_error_count
  vision_low_quality_count
  vision_num_ctx

/agent RootGraph 最近观测 新增 Vision detail 行：
  context
  urls
  continue
  descriptions
  errors
  low_quality
  num_ctx
```

边界：
```text
只记录计数、布尔值和上下文配置。
不记录图片 URL。
不记录图片描述正文。
不改变 RootGraph 路由、聊天权限、图片缓存策略或视觉模型调用策略。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 6 tests OK
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
