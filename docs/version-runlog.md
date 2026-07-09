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

## v1.6 MainAgent 任务详情卡第一步

状态：已落地 P1.4 小范围任务协作增强。目标是让任务和审批不再是两张割裂的表，而是在重启、中断或切换工作后，主人能从任意一张详情卡看懂当前接续点。

本次完成：

```text
任务详情从普通事件列表升级为任务详情卡。
/agent 任务详情 <任务ID> / 最新任务详情 会展示：
  任务状态、目标、结果、创建/更新时间
  当前建议下一步
  关联审批摘要
  任务事件列表
  /agent 下一步 协作入口
审批详情从普通审批记录升级为审批详情卡。
/agent 审批详情 <审批ID> / 最新审批详情 会展示：
  审批状态、工具、风险、原因、输入摘要
  关联任务摘要
  关联任务最近事件
  当前建议下一步
新增 list_agent_approvals(task_id=...)，用于只读查询某个任务的关联审批。
固定 /agent 入口和语义 agent_task_read 入口都接入详情卡。
```

边界：

```text
详情卡仍是只读协作查询，不创建任务、不取消任务、不确认/拒绝审批、不恢复工具。
详情卡只读取当前会话、当前用户范围内的 agent_tasks / agent_task_events / agent_approvals。
普通聊天仍不会触发 MainAgent 任务协作。
不开放多步自动执行任务、自动修复失败任务、shell、任意文件写入或未注册数据库写入。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 20 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 279 tests OK
```

## v1.6 MainAgent 任务工作台第一步

状态：已落地 P1.5 任务协作 read-model 增强。目标是让 `/agent 下一步` 和新工作台视图从“近期任务列表”升级成更接近 Owner Console 后端读模型的分区摘要。

本次完成：

```text
新增 AGENT_TASK_COMMAND_WORKBENCH / workbench 只读命令。
/agent 任务工作台、/agent 任务看板、/agent 协作台 会展示 Agent 任务工作台。
语义 MainAgent 任务读工具也能识别“看看任务工作台”“打开任务看板”等说法，路由到 agent_task_read/workbench。
/agent 下一步 继续保留最高优先级建议，同时新增工作台概览分区。
工作台分区包括：
  待主人确认
  失败任务
  待处理任务
  可复盘/已完成
每条任务行包含任务 ID、状态、标题、最近事件和 /agent 任务详情入口。
待审批任务会在任务行上标出待审批编号。
待审批行包含 /agent 审批详情、/agent 确认、/agent 拒绝入口。
工作台待处理分区现在优先显示有待审批的任务；没有待审批的普通 pending 任务会作为“普通待处理/积压”默认折叠为计数，避免旧测试任务刷屏。
可复盘/已完成分区默认只展示最近少量记录，其余折叠为计数，避免历史执行结果刷屏。
折叠只是只读降噪，不会批量取消或修改旧任务。
```

边界：

```text
任务工作台是只读查询，不创建任务、不取消任务、不确认/拒绝审批、不恢复工具。
只读取当前会话、当前用户范围内的 agent_tasks / agent_task_events / agent_approvals。
普通聊天仍不会触发 MainAgent 任务协作。
不开放多步自动执行任务、自动修复失败任务、shell、任意文件写入或未注册数据库写入。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 21 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 280 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 21 tests OK
```

## v1.6 MainAgent Owner Runtime service 解耦第一步

状态：已落地 P2.1 代码层 service 解耦。目标是先让主人侧任务/审批 runtime 脱离 QQ `MessageEvent`，为后续 Runtime service、Owner Console 后端读模型和更清晰的适配层边界铺路。

本次完成：

```text
新增 src/plugins/ai_chat/owner_agent_runtime.py。
新增 OwnerAgentContext(session_key, user_id)，作为主人侧任务/审批 runtime 的最小上下文。
将任务状态、任务详情、任务工作台、审批详情、确认/拒绝、审批演练和审批请求创建逻辑从 QQ adapter 抽到 owner_agent_runtime service。
src/plugins/ai_chat/__init__.py 现在只负责 NoneBot/QQ 事件接入、owner 鉴权、session/user 上下文转换、RootGraph 调度和回复发送。
run_main_agent_task_command、语义 agent_task_read、语义 agent_task_command、owner_write 审批请求创建均改为委托 service。
新增 service 层单测，验证 OwnerAgentContext 可在没有 QQ event 的情况下读取工作台、任务详情和审批详情。
更新 QQ 边界测试，约束 __init__.py 继续保持 adapter 形态，不回退到直接承载任务/审批 runtime。
docs/runbook.md 补充 P2.1 边界说明。
```

边界：

```text
这是代码层解耦，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent 命令行为。
不新增 shell、任意文件写入、未注册数据库写入或多步写执行能力。
owner_write_command 仍必须审批，确认后仅已注册且 approval_resume_enabled=true 的工具会受控恢复。
普通聊天仍不会触发 MainAgent 任务/审批 runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 22 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 281 tests OK
```

## v1.6 MainAgent owner_read runtime service 解耦第一步

状态：已落地 P2.2 代码层 service 解耦。目标是继续把 `src/plugins/ai_chat/__init__.py` 从“承载业务 runtime”收窄为 QQ/NoneBot adapter，让主人只读管理命令分发可以被后续 Runtime service / Owner Console 后端复用。

本次完成：

```text
新增 src/plugins/ai_chat/owner_read_runtime.py。
新增 OwnerReadRuntime 依赖注入对象，用于承载 DiagnosticsGraph、MemoryRAG、MemoryAdmin、角色卡、名单和观测等只读 provider。
新增 run_owner_read_command(runtime, command, context)，集中分发 owner_read_command。
src/plugins/ai_chat/__init__.py 新增 owner_read_runtime_from_event(event)，只负责把 QQ event 绑定到现有只读读取函数。
run_main_agent_qq_command 内部的 execute_owner_read_command 现在只委托 owner_read_runtime service。
owner_read_runtime 单测验证不依赖 QQ event，也能分发 bot_status、ops_health、config_status、memory_retrieval、summary_status 和 view_persona。
QQ 边界测试改为检查 owner_read_runtime.py 承载只读命令分发，__init__.py 继续保留底层 QQ/event 绑定和诊断证据读取。
```

边界：

```text
这是代码层解耦，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent owner_read_command 行为。
不新增 shell、任意文件写入、未注册数据库写入或多步写执行能力。
owner_read_runtime 只做只读命令路由，不直接写数据库、不发额外 QQ 消息。
普通聊天仍不会触发 MainAgent owner_read runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 48 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 282 tests OK
```

## v1.6 MainAgent owner_write runtime service 解耦第一步

状态：已落地 P2.3 代码层 service 解耦。目标是把已审批恢复会调用的主人管理写执行器也从 QQ adapter 中抽出，让 task/read/write 三块 MainAgent owner runtime 都具备 service 边界。

本次完成：

```text
新增 src/plugins/ai_chat/owner_write_runtime.py。
新增 OwnerWriteRuntime 依赖注入对象，用于绑定现有受控写函数。
新增 run_owner_write_command(runtime, command, context)，集中执行已审批 owner_write_command。
src/plugins/ai_chat/__init__.py 新增 owner_write_runtime()，只负责把现有 clear_image_cache、clear_error_log、select_role_card、add_manual_memory、clear_session_summaries、delete_session_summary、动态名单 add/remove 等函数绑定给 service。
execute_owner_write_command 现在只委托 owner_write_runtime service。
owner_write_runtime 单测验证不依赖 QQ event，也能执行 clear_image_cache、allow_group、select_persona、add_fact_memory、clear_session_summaries 和 delete_session_summary。
QQ 边界测试改为检查 owner_write_runtime.py 承载写命令分发，__init__.py 不再承载 access_operations 分发表。
```

边界：

```text
这是代码层解耦，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent owner_write_command 行为。
不新增写工具。
不绕过审批；owner_write_command 仍必须先生成审批，确认后仅通过已注册且 approval_resume_enabled=true 的工具恢复。
不开放 shell、任意文件写入、未注册数据库写入、删除长期记忆、清空全部摘要或清空全部上下文。
普通聊天仍不会触发 MainAgent owner_write runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 49 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 22 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 283 tests OK
```

## v1.6 MainAgent owner runtime factory 总装层

状态：已落地 P2.4 代码层 service 总装。目标是在 task/read/write 三块 runtime 都抽离后，再把 QQ adapter 中散落的 runtime 绑定点收敛为一个 factory，为后续 Runtime service / Web Owner Console 复用同一套 owner runtime 装配铺路。

本次完成：

```text
新增 src/plugins/ai_chat/owner_runtime_factory.py。
新增 OwnerRuntimeFactory，集中组装 OwnerAgentContext、OwnerReadRuntime 和 OwnerWriteRuntime。
OwnerRuntimeFactory 提供 run_task_command、format_task_read、execute_task_command、create_approval_request、run_read_command 和 run_write_command。
src/plugins/ai_chat/__init__.py 移除 owner_agent_context_from_event、owner_read_runtime_from_event 和 owner_write_runtime 三个分散 helper。
QQ adapter 现在只保留 owner_runtime_factory() 依赖绑定点，/agent 入口通过 factory 委托 task/read/write runtime。
新增 factory 单测，验证不依赖 QQ event 也能组装 owner context、owner_read 和 owner_write。
QQ 边界测试改为约束 __init__.py 只挂 OwnerRuntimeFactory，三块 runtime 细节由 owner_runtime_factory.py 引用。
```

边界：

```text
这是代码层总装整理，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent task/read/write 行为。
不新增工具，不扩大审批恢复范围。
不开放 shell、任意文件写入、未注册数据库写入或多步写执行能力。
普通聊天仍不会触发 MainAgent owner runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 22 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 284 tests OK
```

## v1.6 Runtime service 解耦审计

状态：已落地 P2.5 文档审计。目标是在 P2.1-P2.4 把 MainAgent owner task/read/write runtime 抽离并总装后，先暂停继续大拆，明确当前边界、QQ live 回归点和 `src/plugins/ai_chat/__init__.py` 剩余职责。

本次完成：

```text
新增 docs/v1.6-runtime-service-audit.md。
记录当前 owner runtime 分层：
  __init__.py
  owner_runtime_factory.py
  owner_agent_runtime.py
  owner_read_runtime.py
  owner_write_runtime.py

记录本轮仍保持的行为边界：
  不拆独立进程
  不新增 HTTP API
  不新增 Web Owner Console
  不改 DB schema
  不新增工具
  不扩大审批恢复范围
  普通聊天仍不会触发 MainAgent owner runtime

记录已观察到的 QQ live 路径：
  /agent 访问控制
  /agent 删除摘要 41
  /agent 确认 19
  /agent 确认 最新

审计 __init__.py 剩余职责：
  QQ adapter 必须保留
  Chat runtime 仍然很重
  Diagnostics / MemoryRAG / MemoryAdmin 可继续 service 化
  Voice / Notification 可独立拆但不是当前瓶颈

给出下一步建议：
  优先 P2.6 Web Owner Console read-model 设计，不写前端、不接 HTTP
  备选 P2.6-alt Diagnostics runtime service 解耦
  暂不建议立刻拆 Chat runtime
```

边界：

```text
本步只做审计和文档，不改变运行时代码。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增测试依赖。
```

## v1.6 Web Owner Console read-model 设计

状态：已落地 P2.6 设计文档。目标是在 MainAgent owner runtime service 解耦后，先定义未来 Web Owner Console 的只读页面和结构化 read model，而不是直接写前端或接 HTTP。

本次完成：

```text
新增 docs/web-owner-console-read-model-design.md。

明确 Web Owner Console v0 定位：
  只做 read-model 设计
  不写前端
  不接 HTTP
  不做登录/鉴权
  不新增数据库表
  不做 Web 写操作

梳理现有 QQ 文本输出后端形态：
  lines provider -> str
  Graph execution reply_text -> str
  AgentTask / AgentApproval -> QQ formatter -> str

确定 Web read model 不应长期复用 QQ 文本输出：
  不解析 QQ 文案
  不把文案当接口契约
  任务/审批优先复用 AgentTask / AgentTaskEvent / AgentApproval 等结构化来源

页面范围分层：
  v0 必须清楚：Dashboard、Tasks、Task Detail、Approvals、Approval Detail、Diagnostics、Access Control
  v0 浅层快照：Memory、Settings

定义 read model 草案：
  OwnerConsoleOverview
  OwnerConsoleTaskList
  OwnerConsoleTaskDetail
  OwnerConsoleApprovalList
  OwnerConsoleApprovalDetail
  OwnerConsoleHealthSnapshot
  OwnerConsoleMemorySnapshot
  OwnerConsoleAccessControlSnapshot
  OwnerConsoleRuntimeBoundary

写清未来升级路线：
  v0 全只读
  v0.1 只读 actionability metadata
  v1 如支持审批决定，也必须复用现有 approval resume / owner_write_runtime 链路
```

稀土掘金文章：

```text
新增 docs/juejin/14-web-owner-console-read-model-design.md。
主题：为什么 Web Owner Console 不直接复用 QQ 文本输出，以及为什么要先设计结构化 DTO。
```

边界：

```text
本步只做设计和文档，不改变运行时代码。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增 HTTP API。
不新增 Web 前端。
不新增工具能力。
不新增数据库表。
不执行测试；本次为纯文档变更。
```

## v1.6 Owner Console Task / Approval read-model builder

状态：已落地 P2.7 第一刀。目标是把 P2.6 中“不要复用 QQ 文本、先做结构化 DTO”的设计落到任务/审批只读 builder 上，验证未来 Web Owner Console 可以不依赖 QQ formatter 读取结构化数据。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_read_models.py。

第一批结构化 DTO：
  OwnerConsoleContext
  OwnerConsoleRuntimeBoundary
  OwnerConsoleTaskRow
  OwnerConsoleTaskEventRow
  OwnerConsoleTaskList
  OwnerConsoleTaskDetail
  OwnerConsoleApprovalActionability
  OwnerConsoleApprovalRow
  OwnerConsoleApprovalList
  OwnerConsoleApprovalDetail
  OwnerConsoleToolInputPreview

新增 src/plugins/ai_chat/owner_console_read_runtime.py。

第一批只读 builder：
  build_owner_console_task_list
  build_owner_console_task_detail
  build_owner_console_approval_list
  build_owner_console_approval_detail
  build_tool_input_preview

实现边界：
  使用 OwnerConsoleContext(session_key, user_id)，不依赖 QQ MessageEvent。
  任务/审批直接复用 AgentTask、AgentTaskEvent、AgentApproval 和持久化查询函数。
  不解析 QQ formatter 文本。
  不改变现有 /agent 输出。
  不接 HTTP。
  不写前端。
  不调用 owner_write_runtime。
```

actionability 第一版保持保守：

```text
pending approval:
  can_approve=true
  can_reject=true
  resume_enabled=None
  blocked_reason=""
  future_operation_only=true

非 pending approval:
  can_approve=false
  can_reject=false
  resume_enabled=None
  blocked_reason="approval is not pending"
  future_operation_only=true
```

其中 `resume_enabled=None` 表示 P2.7 尚未接入 tool registry，不声称该审批确认后一定可恢复工具。后续如进入 Web 操作阶段，必须由后端基于 tool registry 和 `approval_resume_enabled=true` 计算真实值。

安全预览：

```text
tool_input_json 只生成 preview。
支持敏感 key 脱敏：api_key、token、cookie、password、secret 等。
支持长度截断，避免把长内容或潜在隐私正文完整塞进 read model。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 4 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units.AgentTaskPersistenceUnitTests -v
Ran 17 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 288 tests OK
```

边界：

```text
本步只新增只读 read-model builder。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增 HTTP API。
不新增 Web 前端。
不新增数据库表。
不新增工具能力。
不开放 Web 写操作。
```

## v1.6 Owner Console Overview read-model builder

状态：已落地 P2.8 第一刀。目标是在 P2.7 Task / Approval 结构化 read model 的基础上，新增 Dashboard / Overview 的轻量只读聚合模型，为未来 Web Owner Console 首页做准备。

本次完成：

```text
agent_tasks.py 新增只读计数 helper：
  count_agent_tasks
  count_agent_approvals

owner_console_read_models.py 新增：
  OwnerConsoleOverviewCounters
  OwnerConsoleOverview

owner_console_read_runtime.py 新增：
  build_owner_console_overview

Overview 当前聚合：
  pending_tasks
  failed_tasks
  pending_approvals
  recent_tasks
  pending_approvals rows
  runtime boundary
```

本步刻意不做深层 Dashboard：

```text
不接 Diagnostics 深层结构。
不接 Access Control 深层结构。
不接 Memory / Settings snapshot。
不接 HTTP。
不写前端。
```

原因是 P2.8 只验证 Dashboard 可以复用 P2.7 的结构化 rows 和精确计数，避免第一版 overview 同时牵扯诊断、访问控制、记忆和设置而膨胀。

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 5 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units.AgentTaskPersistenceUnitTests -v
Ran 17 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 289 tests OK
```

边界：

```text
本步只新增只读 overview builder。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增 HTTP API。
不新增 Web 前端。
不新增数据库表。
不新增工具能力。
不开放 Web 写操作。
```

## v1.6 Owner Console Access / Settings snapshot

状态：已落地 P2.9 第一刀。目标是在 Task / Approval / Overview 之后，继续补齐未来 Owner Console 的浅层配置类 read model，先做 Access Control 和 Settings，只读、结构化、脱敏，不接 HTTP 或前端。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleAccessList
  OwnerConsoleAccessControlSnapshot
  OwnerConsoleModelConfigSnapshot
  OwnerConsoleRoleCardRow
  OwnerConsoleSettingsSnapshot

owner_console_read_runtime.py 新增：
  build_owner_console_access_control_snapshot
  build_owner_console_settings_snapshot
```

Access Control snapshot 当前包含：

```text
owner_configured
private_chat_enabled
group_chat_enabled
unknown_private_policy
private_whitelist
group_whitelist
user_blacklist
runtime boundary
```

Settings snapshot 当前包含：

```text
chat_model
main_agent_model
embedding
role_cards
active_role_card_key
feature_flags
runtime boundary
```

安全处理：

```text
base_url 使用 redacted_base_url 脱敏，不保留 userinfo/query/token。
API Key 只展示 api_key_configured 布尔值，不暴露原文。
访问名单支持 item_limit 截断，避免一次性把大量名单项塞进 read model。
Settings builder 由调用方传入 role_cards 和 active_role_card_key，不读取角色卡正文。
```

边界：

```text
不 import access.py，避免引入 NoneBot MessageEvent。
不依赖 QQ adapter。
不读取角色卡正文。
不修改名单。
不切换角色卡。
不修改模型配置。
不写 .env。
不接 HTTP。
不写前端。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 7 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units.AgentTaskPersistenceUnitTests -v
Ran 17 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_legacy_business_rules.AccessRuleTests tests.test_legacy_business_rules.AccessStoreTests tests.test_config_loading -v
Ran 11 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 291 tests OK
```

附记：

```text
本轮短暂验证过独立 Web 入口不能直接 import src.plugins.ai_chat.* 包路径，
因为 Python 会先执行 QQ 插件包 __init__.py 并触发插件初始化副作用。
后续如做 FastAPI，只能作为薄 Web adapter 接 read-model 层，不能直接 import QQ adapter。
```

## v1.6 Owner Console Diagnostics snapshot

状态：已落地 P2.10 第一刀。目标是在不重构 DiagnosticsGraph、不接 HTTP、不写前端的前提下，给未来 Owner Console 的 Diagnostics 页面提供浅层结构化 read model。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleTextSnapshotSection
  OwnerConsoleObservationSnapshot
  OwnerConsoleHealthSnapshot

owner_console_read_runtime.py 新增：
  build_owner_console_health_snapshot
```

Health snapshot 当前包含：

```text
bot_status
diagnostics
config
vision
image_cache
memory
tts
recent_errors
observations.main_agent
observations.root_graph
runtime boundary
```

设计取舍：

```text
P2.10 不强行把 DiagnosticsGraph 内部全部结构化。
现阶段允许 summary_text / display_lines 过渡。
builder 可接收 str、list[str]、tuple[str, ...]，也可接收带 result.reply_text / result.error 的 Graph execution-like 对象。
错误状态会转成 section.ok=false 和 section.error，不让前端猜文本。
```

边界：

```text
不 import diagnostics.py，避免引入 nonebot.get_driver / OpenAI 等诊断实现依赖。
不依赖 QQ adapter。
不改变 DiagnosticsGraph node sequence。
不改变 /诊断、/配置状态、/视觉状态、/最近错误 等 QQ 命令输出。
不接 HTTP。
不写前端。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 292 tests OK
```

## v1.6 Owner Console Memory snapshot

状态：已落地 P2.11 第一刀。目标是在不读取记忆正文、不触发检索、不重建索引的前提下，给未来 Owner Console 的 Memory 页面提供只读结构化快照。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleMemoryCounts
  OwnerConsoleMemoryContextPolicy
  OwnerConsoleMemoryRagSnapshot
  OwnerConsoleProjectDocRagSnapshot
  OwnerConsoleMemorySnapshot

owner_console_read_runtime.py 新增：
  build_owner_console_memory_snapshot
```

Memory snapshot 当前包含：

```text
counts:
  message_count
  session_count
  session_summary_count
  summarized_message_count
  manual_memory_count
  manual_memory_subject_count
  gap_scene_summary_count
  gap_scene_source_message_count
  rag_document_count
  rag_active_document_count
  rag_embedding_count

context_policy:
  memory_compression_enabled
  gap_scene_summaries_enabled
  long_term_memory_context_enabled
  max_context_messages
  max_stored_messages_per_session
  summary_keep_recent_messages
  summary_batch_messages
  summary_min_source_messages
  max_session_summaries_in_context
  max_gap_scene_summaries_in_context
  max_long_term_memories_in_context

memory_rag:
  enabled
  inject_in_chat
  owner_only_debug
  top_k
  min_score
  max_context_chars
  include_manual_facts
  include_manual_preferences
  include_session_summaries
  include_short_messages
  include_gap_scene_summaries

project_doc_rag:
  enabled
  explicit_agent_dev_context_only=true
  ordinary_chat_injection_allowed=false
  top_k
  min_score
  max_context_chars
```

设计取舍：

```text
builder 接收调用方传入的 stats dict，不直接 import memory.py、manual_memory.py、rag.documents 或 __init__.py。
这样未来 Web adapter 可以在 adapter 层选择调用现有 stats provider，
但 read-model 层仍保持纯粹、无 QQ adapter、无插件初始化副作用。

stats dict 中即使携带 content/summary 等额外字段，builder 也只取计数字段。
OwnerConsoleMemorySnapshot 明确标记：
  memory_content_exposed=false
  project_doc_content_exposed=false
  retrieval_executed=false
  index_rebuild_executed=false
```

边界：

```text
不暴露长期记忆正文。
不暴露会话摘要正文。
不暴露 gap scene 摘要正文。
不暴露 ProjectDocRAG 文档正文。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不写数据库。
不 import QQ 插件 __init__.py。
不接 HTTP。
不写前端。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 9 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 293 tests OK
```

## v1.6 Owner Console read-model facade

状态：已落地 P2.12 第一刀。目标是在 P2.7-P2.11 的分散 builder 之上收拢一个只读 facade，给未来 FastAPI / Web adapter 一个稳定调用边界，同时继续避免 HTTP、前端和 QQ adapter 依赖。

本次完成：

```text
owner_console_read_runtime.py 新增 OwnerConsoleReadRuntime。

OwnerConsoleReadRuntime 当前统一暴露：
  build_overview
  build_task_list
  build_task_detail
  build_approval_list
  build_approval_detail
  build_access_control_snapshot
  build_settings_snapshot
  build_memory_snapshot
  build_health_snapshot
```

依赖注入形式：

```text
config_provider
access_provider
role_cards_provider
active_role_card_key_provider
memory_stats_provider
manual_memory_stats_provider
gap_scene_stats_provider
rag_document_stats_provider
```

设计取舍：

```text
facade 不直接 import QQ 插件入口，不依赖 MessageEvent。
facade 不直接 import memory.py、manual_memory.py、rag.documents 或 diagnostics.py。
需要读取运行时状态时，由未来 adapter 在外层注入 provider。
这样 FastAPI 未来只需要作为薄 adapter：
  HTTP request / auth / serialization
  -> OwnerConsoleContext
  -> OwnerConsoleReadRuntime
  -> 结构化 DTO
而不是直接调用 QQ formatter 或拼接文本输出。
```

边界：

```text
本步只新增只读 facade。
不新增 HTTP API。
不写前端。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 294 tests OK
```

## v1.6 Owner Console serialization contract

状态：已落地 P2.13 第一刀。目标是在 read-model builder 和未来 FastAPI / Web adapter 之间定义一个稳定 JSON-safe 序列化契约，避免将来临时把 dataclass、QQ 文本或 Python 对象直接丢给 HTTP 层。

本次完成：

```text
owner_console_read_models.py 新增：
  OWNER_CONSOLE_SCHEMA_VERSION
  owner_console_to_jsonable
  owner_console_page_response

owner_console_read_runtime.py / OwnerConsoleReadRuntime 新增：
  serialize_model
  serialize_page
```

序列化契约：

```text
owner_console_to_jsonable:
  dataclass -> dict
  dict key -> str
  list / tuple -> list
  set / frozenset -> sorted list
  datetime / date -> isoformat string
  enum -> enum.value
  None 保留为 null
  bool / int / finite float / str 保留原类型
  non-finite float 拒绝
  其他未知 Python 对象拒绝

owner_console_page_response:
  schema_version
  page
  generated_at
  read_only=true
  http_api_enabled=false
  web_write_enabled=false
  data
```

设计取舍：

```text
序列化层不做 HTTP，不决定状态码，不做鉴权。
序列化层只保证 read model 可以安全进入 JSON response envelope。
敏感信息仍应在 builder 阶段脱敏；序列化层不负责猜测业务语义。
page response 明确 read_only=true / web_write_enabled=false，避免未来 Web adapter 把只读 DTO 误当可写接口。
```

边界：

```text
不新增 HTTP API。
不写前端。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 11 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 295 tests OK
```

## v1.6 Owner Console provider wiring audit

状态：已落地 P2.14 第一刀。目标是在不接 FastAPI、不写 Web adapter 的前提下，把未来 Web Owner Console 需要注入哪些 provider 固化成显式契约，并提供轻量 factory，避免以后在路由层散落临时 lambda 胶水。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleProviderWiringRow
  OwnerConsoleProviderWiringSnapshot

owner_console_read_runtime.py 新增：
  OwnerConsoleReadProviderSpec
  OWNER_CONSOLE_READ_PROVIDER_SPECS
  OwnerConsoleReadProviders
  build_owner_console_provider_wiring_snapshot
  create_owner_console_read_runtime
```

当前 provider 契约：

```text
required:
  config_provider
  access_provider

optional:
  role_cards_provider
  active_role_card_key_provider
  memory_stats_provider
  manual_memory_stats_provider
  gap_scene_stats_provider
  rag_document_stats_provider
```

optional provider fallback：

```text
role_cards_provider -> empty role card list
active_role_card_key_provider -> empty active role card key
memory_stats_provider -> zero memory counters
manual_memory_stats_provider -> zero manual memory counters
gap_scene_stats_provider -> zero gap scene counters
rag_document_stats_provider -> zero RAG document counters
```

Provider wiring snapshot 明确记录：

```text
runtime_ready
missing_required
provider_name
required
configured
read_model_area
owner_console_methods
fallback_behavior
direct_qq_dependency_allowed=false
write_side_effect_allowed=false
runtime boundary
```

设计取舍：

```text
audit 只检查 provider 是否注入，不调用 provider，不读取数据库。
factory 只把 provider bundle 转成 OwnerConsoleReadRuntime，不 import QQ 插件入口。
factory 不直接 import memory.py、manual_memory.py、rag.documents 或 diagnostics.py。
未来 FastAPI adapter 只需要组装 OwnerConsoleReadProviders，再调用 create_owner_console_read_runtime。
```

边界：

```text
不新增 HTTP API。
不写前端。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 12 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 296 tests OK
```

## v1.6 Owner Console read-only route contract

状态：已落地 P2.15 第一刀。目标是在 P2.12 facade、P2.13 serialization 和 P2.14 provider wiring 之后，把未来 Web Owner Console 的只读页面入口固化成显式 route contract，避免后续接 FastAPI 时临时把页面、DTO、runtime method 和参数散落在路由层。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleReadRouteRow
  OwnerConsoleReadRouteContractSnapshot

owner_console_read_runtime.py 新增：
  OwnerConsoleReadRouteSpec
  OWNER_CONSOLE_READ_ROUTE_SPECS
  build_owner_console_route_contract_snapshot

OwnerConsoleReadRuntime 新增：
  build_route_contract_snapshot
```

当前只读页面契约：

```text
dashboard:
  runtime_method=build_overview
  read_model=OwnerConsoleOverview
  requires_context=true
  optional_params=task_limit, approval_limit

tasks:
  runtime_method=build_task_list
  read_model=OwnerConsoleTaskList
  requires_context=true
  optional_params=status, limit

task_detail:
  runtime_method=build_task_detail
  read_model=OwnerConsoleTaskDetail
  requires_context=true
  required_params=task_id
  optional_params=event_limit, preview_limit

approvals:
  runtime_method=build_approval_list
  read_model=OwnerConsoleApprovalList
  requires_context=true
  optional_params=status, limit

approval_detail:
  runtime_method=build_approval_detail
  read_model=OwnerConsoleApprovalDetail
  requires_context=true
  required_params=approval_id
  optional_params=event_limit, preview_limit

diagnostics:
  runtime_method=build_health_snapshot
  read_model=OwnerConsoleHealthSnapshot
  requires_context=false

memory:
  runtime_method=build_memory_snapshot
  read_model=OwnerConsoleMemorySnapshot
  requires_context=false

access_control:
  runtime_method=build_access_control_snapshot
  read_model=OwnerConsoleAccessControlSnapshot
  requires_context=false

settings:
  runtime_method=build_settings_snapshot
  read_model=OwnerConsoleSettingsSnapshot
  requires_context=false
```

每一行 route contract 都显式标记：

```text
read_only=true
http_api_enabled=false
web_write_enabled=false
direct_qq_dependency_allowed=false
write_side_effect_allowed=false
```

设计取舍：

```text
P2.15 仍不是 HTTP API。
route contract 只是未来 Web adapter 的页面到 read-model facade 映射表。
它不决定 URL path、HTTP method、鉴权、状态码或前端布局。
真正接 FastAPI 时，路由层应只做薄适配：
  HTTP request / auth
  -> OwnerConsoleContext / 参数校验
  -> OwnerConsoleReadRuntime
  -> serialize_page

这样可以继续保持：
  Web 页面不解析 QQ 文本输出
  Web adapter 不 import QQ 插件 __init__.py
  Web adapter 不直接拼业务 DTO
  页面可用性由 read model / facade / route contract 三层共同约束
```

边界：

```text
不新增 HTTP API。
不写前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 13 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 297 tests OK
```

## v1.6 Owner Console RESTful HTTP adapter contract

状态：已落地 P2.16 第一刀。目标是在不接 FastAPI、不启动 HTTP 服务、不写前端的前提下，先把未来 Web Owner Console 的 HTTP 命名规范、RESTful 路径契约和统一响应 envelope 固化下来，避免后续接口路径和项目命名发散。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_http_models.py。

HTTP adapter DTO / 常量：
  OWNER_CONSOLE_HTTP_SCHEMA_VERSION = owner_console.http.v1
  OWNER_CONSOLE_HTTP_API_PREFIX = /api/v1/owner-console
  OWNER_CONSOLE_HTTP_ALLOWED_METHODS = GET
  OWNER_CONSOLE_HTTP_ERROR_CODES
  OwnerConsoleHttpError
  OwnerConsoleHttpRouteRow
  OwnerConsoleHttpRouteContractSnapshot

HTTP envelope helper：
  owner_console_http_success_response
  owner_console_http_error_response

新增 src/plugins/ai_chat/owner_console_http_contract.py。

RESTful route contract：
  OwnerConsoleHttpRouteSpec
  OWNER_CONSOLE_HTTP_ROUTE_SPECS
  build_owner_console_http_route_contract_snapshot
```

当前 HTTP namespace 固定为：

```text
/api/v1/owner-console
```

当前只读 RESTful 路径契约：

```text
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/diagnostics
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
```

命名规范：

```text
API prefix 统一为 /api/v1/owner-console。
HTTP path 静态段统一小写 kebab-case。
集合资源使用复数：tasks、approvals。
详情资源使用 /{id}：tasks/{task_id}、approvals/{approval_id}。
查询参数沿用 Python / DTO 的 snake_case。
第一版只允许 GET。
Dashboard 页面在 HTTP 资源层命名为 overview，避免把前端页面名和 API 资源名混在一起。
```

HTTP route contract 复用 P2.15 read route contract：

```text
overview -> read_page=dashboard -> build_overview -> OwnerConsoleOverview
tasks -> read_page=tasks -> build_task_list -> OwnerConsoleTaskList
tasks.detail -> read_page=task_detail -> build_task_detail -> OwnerConsoleTaskDetail
approvals -> read_page=approvals -> build_approval_list -> OwnerConsoleApprovalList
approvals.detail -> read_page=approval_detail -> build_approval_detail -> OwnerConsoleApprovalDetail
diagnostics -> read_page=diagnostics -> build_health_snapshot -> OwnerConsoleHealthSnapshot
memory -> read_page=memory -> build_memory_snapshot -> OwnerConsoleMemorySnapshot
access-control -> read_page=access_control -> build_access_control_snapshot -> OwnerConsoleAccessControlSnapshot
settings -> read_page=settings -> build_settings_snapshot -> OwnerConsoleSettingsSnapshot
routes -> build_route_contract_snapshot -> OwnerConsoleReadRouteContractSnapshot
```

HTTP success envelope：

```text
schema_version=owner_console.http.v1
read_model_schema_version=owner_console.read_model.v0
transport=http
api_prefix=/api/v1/owner-console
resource
generated_at
read_only=true
http_api_enabled=false
web_write_enabled=false
data
error=null
```

HTTP error envelope：

```text
schema_version=owner_console.http.v1
read_model_schema_version=owner_console.read_model.v0
transport=http
api_prefix=/api/v1/owner-console
resource
generated_at
read_only=true
http_api_enabled=false
web_write_enabled=false
data=null
error:
  code
  message
  details
```

第一版错误码固定为：

```text
bad_request
forbidden
not_found
provider_unavailable
internal_error
```

上下文策略先只进入契约，不开放实现：

```text
context_strategy=owner_private_session_from_config
context_override_allowed=false
write_routes_enabled=false
```

设计取舍：

```text
P2.16 仍不是 HTTP API。
本步不接 FastAPI，不启动服务，不注册 route。
http_api_enabled=false 表示当前只是 adapter contract，不声称真实 HTTP 已开放。
HTTP contract 只规定未来路径、方法、资源名、read model 映射和 envelope。
未来 FastAPI 层必须作为薄 adapter 服从该 contract：
  HTTP request / auth
  -> OwnerConsoleContext / 参数校验
  -> OwnerConsoleReadRuntime
  -> owner_console_http_success_response / owner_console_http_error_response
```

边界：

```text
不新增真实 HTTP API。
不写前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不 import QQ adapter。
不依赖 FastAPI。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_http_contract -v
Ran 3 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 300 tests OK
```

## v1.6 Owner Console FastAPI local smoke adapter

状态：已落地 P2.17 第一刀。目标是在 P2.16 RESTful HTTP contract 之后，验证 FastAPI 可以作为极薄的本地 HTTP adapter 承载 Owner Console 只读 contract，但仍不接全量页面、不写前端、不做登录鉴权、不开放 Web 写操作。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_fastapi_app.py。

新增：
  OWNER_CONSOLE_FASTAPI_APP_TITLE
  OWNER_CONSOLE_FASTAPI_SMOKE_ROUTES
  create_owner_console_fastapi_app
  app

当前 FastAPI smoke app 只注册：
  GET /healthz
  GET /api/v1/owner-console/routes
```

`GET /healthz` 返回本地 smoke 状态：

```text
ok=true
service=owner-console
schema_version=owner_console.http.v1
api_prefix=/api/v1/owner-console
read_only=true
http_api_enabled=true
web_write_enabled=false
enabled_routes:
  /healthz
  /api/v1/owner-console/routes
```

`GET /api/v1/owner-console/routes` 返回 P2.16 定义的 RESTful route contract，并通过 HTTP envelope 包装：

```text
schema_version=owner_console.http.v1
read_model_schema_version=owner_console.read_model.v0
transport=http
api_prefix=/api/v1/owner-console
resource=routes
read_only=true
http_api_enabled=true
web_write_enabled=false
data=OwnerConsoleHttpRouteContractSnapshot
error=null
```

设计取舍：

```text
FastAPI app factory 默认关闭 docs/redoc/openapi。
当前不注册 /api/v1/owner-console/tasks 等页面接口。
当前不接 OwnerConsoleContext。
当前不装配 OwnerConsoleReadProviders。
当前只证明 FastAPI 能按 P2.16 envelope 和路径规范返回 routes contract。

本步中 response envelope 的 http_api_enabled=true 只表示当前 smoke endpoint 已通过 HTTP 暴露。
route contract data 内仍由 P2.16 contract 记录未来完整页面接口的只读映射和边界。
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不接任务/审批/记忆/诊断等完整页面接口。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不 import QQ adapter。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 4 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 16 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 304 tests OK
```

## v1.6 Owner Console side-effect-free FastAPI launcher

状态：已落地 P2.18 第一刀。目标是在 P2.17 已有 FastAPI smoke app 后，补上独立启动边界：未来本地 Uvicorn 应从 side-effect-free launcher 进入，而不是直接 import `src.plugins.ai_chat.owner_console_fastapi_app`，避免 Python 先执行 QQ/NoneBot 插件入口 `src/plugins/ai_chat/__init__.py`。

本次完成：

```text
新增 src/owner_console_fastapi_launcher.py。

新增：
  OWNER_CONSOLE_FASTAPI_MODULE
  ensure_owner_console_import_boundary
  load_owner_console_fastapi_module
  create_app
  app
```

推荐未来本地启动入口：

```text
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

设计取舍：

```text
launcher 位于 src/owner_console_fastapi_launcher.py，而不是 src/plugins/ai_chat 包内。
导入 launcher 只会执行 src/__init__.py 这个空包入口，不会正常 import src.plugins.ai_chat 包。
launcher 会先在 sys.modules 中建立轻量 package stub：
  src
  src.plugins
  src.plugins.ai_chat

然后再 import：
  src.plugins.ai_chat.owner_console_fastapi_app

这样 owner_console_fastapi_app 内部的相对导入仍然可用，
但不会执行 src/plugins/ai_chat/__init__.py。
```

安全保护：

```text
如果 src.plugins.ai_chat 已经以真实 __file__ 初始化，
launcher 会拒绝继续建立 side-effect-free import boundary。

这避免在同一进程已经加载 QQ 插件入口后，
又误以为当前 FastAPI app 仍处于无 QQ side effect 的独立边界。
```

当前 launcher 仍只承载 P2.17 smoke app：

```text
GET /healthz
GET /api/v1/owner-console/routes
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不接完整 tasks / approvals / memory / diagnostics 页面接口。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher -v
Ran 3 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 7 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 307 tests OK
```

## v1.6 Owner Console FastAPI overview endpoint

状态：已落地 P2.19 第一刀。目标是在 P2.18 已解决 side-effect-free launcher 后，接入第一个真正需要 `OwnerConsoleContext` 的只读 HTTP endpoint：`GET /api/v1/owner-console/overview`。本步仍不接完整页面、不做登录鉴权、不开放 Web 写操作。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_http_adapter.py。

新增：
  OwnerConsoleHttpAdapterError
  build_owner_console_context_from_config
  build_owner_console_access_from_config
  create_owner_console_http_read_runtime
  parse_owner_console_positive_int

更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/overview

更新 src/plugins/ai_chat/owner_console_http_contract.py：
  build_owner_console_http_route_contract_snapshot 支持 enabled_route_names。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
```

`GET /api/v1/owner-console/overview` 策略：

```text
从 load_config() 读取 BOT_OWNER_QQ。
构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

创建 OwnerConsoleReadRuntime：
  config_provider = 当前请求读取到的 config
  access_provider = merged_access(config.private_whitelist, config.group_whitelist, config.user_blacklist)

调用：
  runtime.build_overview(context, task_limit, approval_limit)

返回：
  owner_console_http_success_response(resource=overview, data=OwnerConsoleOverview)
```

查询参数：

```text
task_limit:
  默认 5
  必须为 >= 1 的整数

approval_limit:
  默认 5
  必须为 >= 1 的整数
```

错误处理：

```text
BOT_OWNER_QQ 未配置：
  HTTP 403
  error.code = forbidden
  error.details.config_key = BOT_OWNER_QQ

task_limit / approval_limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = 对应字段名

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
直接调用 build_owner_console_http_route_contract_snapshot() 时仍保持设计态：
  http_api_enabled=false

FastAPI /routes endpoint 返回时传入 enabled_route_names：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks / approvals / memory / diagnostics / settings 等仍为 false
```

设计取舍：

```text
第一版没有登录系统，因此不允许 query 参数覆盖 user_id 或 session_key。
context_override_allowed 仍为 false。
overview 只查询 owner 私聊上下文 private:{BOT_OWNER_QQ}。
本步只读取 agent_tasks / agent_approvals 的只读 read model。
access_provider 使用 merged_access，但 overview 当前不会读取访问名单；这是给后续 settings/access-control endpoint 复用的 adapter 边界。
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不接 tasks / approvals / memory / diagnostics / settings 等完整页面接口。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 6 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 309 tests OK
```

## v1.6 Owner Console FastAPI task / approval list endpoints

状态：已落地 P2.20 第一刀。目标是在 P2.19 接通 overview 后，继续接入两个只读列表资源：`GET /api/v1/owner-console/tasks` 和 `GET /api/v1/owner-console/approvals`。本步仍不接详情页、不做登录鉴权、不开放 Web 写操作。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/tasks
  GET /api/v1/owner-console/approvals

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  parse_owner_console_optional_status

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 tasks / approvals 列表读取、owner context 作用域、status 过滤、limit 校验和写方法拒绝。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 tasks / approvals。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/approvals
```

`GET /api/v1/owner-console/tasks` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

查询参数：
  status，可选，必须属于 agent task status 集合
  limit，可选，默认 20，必须为 >= 1 的整数

调用：
  runtime.build_task_list(context, status, limit)

返回：
  owner_console_http_success_response(resource=tasks, data=OwnerConsoleTaskList)
```

`GET /api/v1/owner-console/approvals` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

查询参数：
  status，可选，必须属于 agent approval status 集合
  limit，可选，默认 20，必须为 >= 1 的整数

调用：
  runtime.build_approval_list(context, status, limit)

返回：
  owner_console_http_success_response(resource=approvals, data=OwnerConsoleApprovalList)
```

错误处理：

```text
BOT_OWNER_QQ 未配置：
  HTTP 403
  error.code = forbidden

status 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = status
  error.details.allowed = 当前允许的 status 列表

limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = limit

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  approvals.http_api_enabled=true

仍未开放：
  task_detail.http_api_enabled=false
  approval_detail.http_api_enabled=false
  diagnostics.http_api_enabled=false
  memory.http_api_enabled=false
  access-control.http_api_enabled=false
  settings.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不接 task_detail / approval_detail 详情页。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 311 tests OK
```

## v1.6 Owner Console FastAPI task / approval detail endpoints

状态：已落地 P2.21 第一刀。目标是在 P2.20 列表端点之后，继续接入两个只读详情资源：`GET /api/v1/owner-console/tasks/{task_id}` 和 `GET /api/v1/owner-console/approvals/{approval_id}`。本步仍不做审批确认/拒绝，不接 Web 前端，不新增登录鉴权，也不改变 QQ / `/agent` 的任何运行时行为。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/tasks/{task_id}
  GET /api/v1/owner-console/approvals/{approval_id}

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  parse_owner_console_required_positive_int

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 task detail / approval detail 的 owner context 作用域、path id 校验、event_limit / preview_limit 校验、not_found envelope 和写方法拒绝。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 task detail / approval detail。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
```

`GET /api/v1/owner-console/tasks/{task_id}` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

路径参数：
  task_id，必填，必须为 >= 1 的整数

查询参数：
  event_limit，可选，默认 20，必须为 >= 1 的整数
  preview_limit，可选，默认 DEFAULT_PREVIEW_LIMIT，必须为 >= 1 的整数

调用：
  runtime.build_task_detail(context, task_id, event_limit, preview_limit)

返回：
  找到时 owner_console_http_success_response(resource=tasks, data=OwnerConsoleTaskDetail)
  不存在或不属于 owner 私聊上下文时 HTTP 404 / error.code=not_found
```

`GET /api/v1/owner-console/approvals/{approval_id}` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

路径参数：
  approval_id，必填，必须为 >= 1 的整数

查询参数：
  event_limit，可选，默认 5，必须为 >= 1 的整数
  preview_limit，可选，默认 DEFAULT_PREVIEW_LIMIT，必须为 >= 1 的整数

调用：
  runtime.build_approval_detail(context, approval_id, event_limit, preview_limit)

返回：
  找到时 owner_console_http_success_response(resource=approvals, data=OwnerConsoleApprovalDetail)
  不存在或不属于 owner 私聊上下文时 HTTP 404 / error.code=not_found
```

错误处理：

```text
BOT_OWNER_QQ 未配置：
  HTTP 403
  error.code = forbidden

task_id / approval_id 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = task_id 或 approval_id

event_limit / preview_limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = event_limit 或 preview_limit

详情不存在或不属于 owner 私聊上下文：
  HTTP 404
  error.code = not_found

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true

仍未开放：
  diagnostics.http_api_enabled=false
  memory.http_api_enabled=false
  access-control.http_api_enabled=false
  settings.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 313 tests OK
```

## v1.6 Owner Console FastAPI access / settings endpoints

状态：已落地 P2.22 第一刀。目标是在 P2.21 接通 task / approval 详情后，继续开放两个低风险只读页面资源：`GET /api/v1/owner-console/access-control` 和 `GET /api/v1/owner-console/settings`。本步仍不接 Web 前端、不新增登录鉴权、不开放写操作，也不执行 MemoryRAG / Diagnostics 运行态读取。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/access-control
  GET /api/v1/owner-console/settings

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  HTTP read runtime 注入只读 role card providers：
    list_role_cards
    active_role_card -> active key

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 access-control / settings 只读 envelope、配置脱敏、访问名单展示、item_limit 校验和无 owner context 读取。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 access-control / settings。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
```

`GET /api/v1/owner-console/access-control` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取访问控制配置：
  BOT_OWNER_QQ
  ENABLE_PRIVATE_CHAT
  ENABLE_GROUP_CHAT
  ALLOW_UNKNOWN_PRIVATE_CHAT
  PRIVATE_WHITELIST
  GROUP_WHITELIST
  USER_BLACKLIST

通过 build_owner_console_access_from_config(config) 合并 env 与 data/access.json 的只读访问名单。

查询参数：
  item_limit，可选，默认 50，必须为 >= 1 的整数

调用：
  runtime.build_access_control_snapshot(item_limit=item_limit)

返回：
  owner_console_http_success_response(resource=access-control, data=OwnerConsoleAccessControlSnapshot)
```

`GET /api/v1/owner-console/settings` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取模型、RAG、MainAgent、TTS、Web/shell/write capability flags。

HTTP read runtime 注入只读 role card provider：
  role_cards_provider = list_role_cards
  active_role_card_key_provider = active_role_card().key 或空字符串

调用：
  runtime.build_settings_snapshot()

返回：
  owner_console_http_success_response(resource=settings, data=OwnerConsoleSettingsSnapshot)
```

脱敏策略：

```text
settings endpoint 复用 OwnerConsoleSettingsSnapshot：
  base_url 通过 redacted_base_url 输出
  API key 只输出 api_key_configured=true/false
  不输出 OPENAI_API_KEY / MAIN_LLM_API_KEY 正文
  embedding API key 固定不暴露
```

错误处理：

```text
item_limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = item_limit

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true
  access-control.http_api_enabled=true
  settings.http_api_enabled=true

仍未开放：
  diagnostics.http_api_enabled=false
  memory.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 Diagnostics 外部探测。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 12 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 315 tests OK
```

## v1.6 Owner Console FastAPI memory endpoint

状态：已落地 P2.23 第一刀。目标是在 P2.22 接通 access-control / settings 后，继续开放 `GET /api/v1/owner-console/memory`。本步仍只返回结构化只读快照：计数、配置、RAG 边界与安全标志；不返回任何记忆正文，不执行检索，不重建索引。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/memory

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  HTTP read runtime 注入只读 memory stats providers：
    memory_stats
    manual_memory_stats
    gap_scene_summary_stats
    rag_document_stats

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 memory endpoint 的只读 envelope、消息计数、上下文策略、MemoryRAG / ProjectDocRAG flags、内容不暴露、检索不执行、索引不重建。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 memory。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
```

`GET /api/v1/owner-console/memory` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取：
  memory compression 配置
  gap scene summaries 配置
  long term memory context 配置
  MemoryRAG 配置
  ProjectDocRAG 配置

只读统计：
  memory_stats -> message_count / session_count / summary_count / summarized_message_count
  manual_memory_stats -> memory_count / subject_count
  gap_scene_summary_stats -> summary_count / source_message_count
  rag_document_stats -> document_count / active_document_count / embedding_count

调用：
  runtime.build_memory_snapshot()

返回：
  owner_console_http_success_response(resource=memory, data=OwnerConsoleMemorySnapshot)
```

强边界：

```text
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
ProjectDocRAG ordinary_chat_injection_allowed=false
ProjectDocRAG 仍只允许显式 /agent dev_context
```

错误处理：

```text
其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true
  access-control.http_api_enabled=true
  settings.http_api_enabled=true
  memory.http_api_enabled=true

仍未开放：
  diagnostics.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 Diagnostics 外部探测。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 13 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 316 tests OK
```

## v1.6 Owner Console FastAPI diagnostics endpoint

状态：已落地 P2.24 第一刀。目标是在 P2.23 接通 memory 后，开放最后一个 v0 只读页面资源：`GET /api/v1/owner-console/diagnostics`。本步采用轻量 read-only diagnostics snapshot：只组合安全文本和已有 read model 计数，不主动调用 `diagnostics.py`，不跑 OpenAI / Ollama / TTS / 图片缓存探测，不读取 QQ adapter。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/diagnostics

新增内部 helper：
  _owner_console_bool
  _build_owner_console_http_diagnostics

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 diagnostics endpoint 的只读 envelope、外部探测跳过标记、QQ adapter 未导入标记、memory 计数摘要、正文不暴露。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 diagnostics。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/diagnostics
```

`GET /api/v1/owner-console/diagnostics` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取安全配置摘要：
  owner 是否配置
  private/group chat 开关
  MainAgent flags
  ChatGraph flag
  Vision 配置摘要
  TTS 配置摘要

复用 runtime.build_memory_snapshot() 读取只读计数：
  message_count
  session_count
  session_summary_count
  manual_memory_count
  rag_document_count
  rag_embedding_count

调用：
  runtime.build_health_snapshot(...)

返回：
  owner_console_http_success_response(resource=diagnostics, data=OwnerConsoleHealthSnapshot)
```

强边界：

```text
external_probes_executed=false
qq_adapter_imported=false
diagnostics_module_imported=false
ollama_probe_executed=false
vision_inference_executed=false
image_cache_stats_collected=false
tts_probe_executed=false
recent_error_log_read=false
recent_errors_collected=false
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
```

为什么暂不直接复用 diagnostics.py：

```text
diagnostics.py 会导入 NoneBot / OpenAI / Vision 探测相关依赖。
Web Owner Console v0 的目标是先建立 side-effect-free HTTP read surface。
因此 diagnostics endpoint 第一版只暴露结构化、可预测、无外部探测的快照。
后续如果要做主动诊断，应单独设计 explicit probe endpoint，并继续保持 GET 只读与 probe 操作分离。
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true
  access-control.http_api_enabled=true
  settings.http_api_enabled=true
  memory.http_api_enabled=true
  diagnostics.http_api_enabled=true
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 Diagnostics 外部探测。
不 import diagnostics.py。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 14 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 317 tests OK
```

## v1.6 Owner Console HTTP surface audit

状态：已落地 P2.25。目标是在 P2.21-P2.24 完成 Owner Console v0 只读 HTTP surface 后，补一份集中审计文档，把 RESTful route、HTTP envelope、context 策略、只读边界、diagnostics 取舍和后续升级路线写清楚。

本次完成：

```text
新增 docs/owner-console-http-surface-audit.md。

更新 docs/web-owner-console-read-model-design.md：
  在开头补充后续实现状态说明。
  明确 P2.6 的“不接 HTTP”是当时设计阶段边界。
  指向 P2.25 HTTP surface audit。
```

审计结论：

```text
Owner Console HTTP v0 已经具备完整只读资源面。
它仍然不是 Web 前端。
它仍然不做登录/鉴权。
它仍然不开放写操作。
它仍然不替代 QQ / NoneBot adapter。
它仍然不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

当前 HTTP surface：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/diagnostics
```

文档重点：

```text
启动入口：
  .\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090

禁止直接使用：
  uvicorn src.plugins.ai_chat.owner_console_fastapi_app:app

原因：
  必须避免执行 src/plugins/ai_chat/__init__.py。
  Web adapter 不能加载 QQ/NoneBot 插件入口。
```

RESTful 规范：

```text
API prefix 固定为 /api/v1/owner-console。
只使用 GET。
静态路径 segment 使用 lowercase kebab-case。
JSON 字段和 query 参数使用 snake_case。
集合资源使用复数：tasks、approvals。
详情资源挂在集合资源下：tasks/{task_id}、approvals/{approval_id}。
```

HTTP envelope：

```text
schema_version
read_model_schema_version
transport
api_prefix
resource
generated_at
read_only
http_api_enabled
web_write_enabled
data
error
```

context 策略：

```text
需要 owner context：
  overview
  tasks
  tasks.detail
  approvals
  approvals.detail

构造方式：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

禁止：
  query 覆盖 user_id
  query 覆盖 session_key
```

非 context 快照：

```text
routes
access-control
settings
memory
diagnostics
```

diagnostics 取舍：

```text
GET /diagnostics 第一版只返回轻量 read-only snapshot。
不 import diagnostics.py。
不执行 OpenAI / Ollama / TTS / Vision 探测。
不读取 QQ adapter 图片缓存。
不读取最近错误日志。
未来如果需要主动诊断，应设计 explicit probe endpoint，不把 GET diagnostics 变成探测执行器。
```

后续建议路线：

```text
P2.26：HTTP surface contract cleanup，收敛重复 endpoint glue。
P2.27：本地 FastAPI smoke runbook。
P2.28：Web Owner Console 前端只读壳。
P2.29：登录/鉴权设计。
P2.30：审批操作设计。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract -v
Ran 6 tests OK
```

## v1.6 Owner Console FastAPI adapter glue cleanup

状态：已落地 P2.26。目标是在不新增接口、不改变 HTTP 行为的前提下，收敛 `owner_console_fastapi_app.py` 中重复的成功 envelope、错误 envelope 和 runtime 装配胶水，让 FastAPI 层继续保持薄 adapter。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  新增 _owner_console_runtime_from_config。
  新增 _owner_console_success。
  新增 _owner_console_error_response。
  新增 _owner_console_adapter_error。
  新增 _owner_console_internal_error。

各 endpoint 仍保留显式路由函数和显式参数解析。
重复的 owner_console_http_success_response / owner_console_http_error_response 调用收敛到本地 helper。
OwnerConsoleHttpAdapterError 的 status_code、code、message、details 透传语义保持不变。
task / approval detail 的 404 not_found envelope 保持不变。
```

边界：

```text
不新增 endpoint。
不改变 RESTful path。
不改变 query 参数。
不改变 HTTP status code。
不改变 response envelope。
不开放 Web 写操作。
不新增登录/鉴权。
不写前端。
不引入 QQ / NoneBot adapter 依赖。
不触碰 owner_write_runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 14 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 317 tests OK
```

## v1.6 Owner Console FastAPI smoke runbook

状态：已落地 P2.27。目标是在 Owner Console HTTP v0 完成只读 surface 和 adapter glue cleanup 后，补一份本地启动与 smoke 验证手册，避免后续调试时误用 QQ plugin 包路径启动，或把 404/405/403 边界误判为故障。

本次完成：

```text
新增 docs/owner-console-fastapi-smoke-runbook.md。

文档覆盖：
  启动前检查。
  推荐 Uvicorn 启动命令。
  禁止直接使用 src.plugins.ai_chat.owner_console_fastapi_app:app。
  /healthz smoke 检查。
  /routes contract 检查。
  access-control / settings / memory / diagnostics 非 context 快照检查。
  overview / tasks / approvals owner context 端点检查。
  /docs /redoc /openapi.json 关闭检查。
  POST 写方法 405 检查。
  Owner Console 相关 unittest 回归命令。
  import boundary 自检。
  常见问题排查。

更新 docs/owner-console-http-surface-audit.md：
  增加 P2.27 smoke runbook 链接。
```

边界：

```text
不新增 endpoint。
不修改 FastAPI 运行时代码。
不启动常驻服务。
不写前端。
不新增登录/鉴权。
不开放 Web 写操作。
不改变 QQ / NoneBot adapter。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console read-only shell design

状态：已落地 P2.28 设计文档。目标是在真正写前端之前，先把未来只读页面壳如何消费现有 Owner Console HTTP GET endpoints 定清楚，避免前端实现时把登录、写操作、审批恢复或 diagnostics 主动探测混进第一版。

本次完成：

```text
新增 docs/web-owner-console-read-only-shell-design.md。

文档覆盖：
  Web Owner Console read-only shell 定位。
  App Shell 范围。
  Dashboard / Tasks / Task Detail / Approvals / Approval Detail 页面映射。
  Diagnostics / Memory / Access Control / Settings 页面映射。
  API 到页面 mapping table。
  HTTP envelope handling 规则。
  loading / empty / error / forbidden / not_found / contract_mismatch 状态模型。
  前端 ownerConsoleApi 命名建议。
  显式刷新策略。
  安全与隐私检查清单。
  第一版完成标准。
  后续路线。

更新 docs/web-owner-console-read-model-design.md：
  补充 P2.28 只读前端壳设计链接。

更新 docs/owner-console-http-surface-audit.md：
  补充 P2.28 页面到 API 映射链接。
```

边界：

```text
不实现真实前端。
不新增 endpoint。
不修改 FastAPI 运行时代码。
不新增登录/鉴权。
不开放 Web 写操作。
不新增审批确认/拒绝入口。
不触发 MainAgent。
不触发 MemoryRAG / ProjectDocRAG 检索。
不触发 diagnostics 主动探测。
不改变 QQ / NoneBot adapter。
```

设计结论：

```text
第一版前端壳只允许调用 GET。
第一版只做显式刷新，不做自动轮询。
第一版必须检查 read_only=true、http_api_enabled=true、web_write_enabled=false。
actionability 只能作为只读展示；不能绑定真实 click handler。
如果未来需要 approve/reject，必须单独设计 POST endpoint、鉴权和审计。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console frontend stack design

状态：已落地 P2.29 设计文档。目标是在创建真实前端工程之前，先确定技术栈、目录边界、启动命名、API client 边界和 Python/Node 分层，避免把前端工程混入 `src/plugins/ai_chat` 或让 Web 入口绕过 HTTP read model。

本次完成：

```text
新增 docs/web-owner-console-frontend-stack-design.md。

设计推荐：
  未来前端目录使用 web/owner-console。
  技术栈使用 Vite + React + TypeScript。
  路由使用 React Router。
  图标使用 lucide-react。
  样式先用 plain CSS 或 CSS Modules。
  数据请求先用 native fetch。
  第一版不引入 Next.js、SSR、TanStack Query、Redux/Zustand、Tailwind 或大型 UI 框架。

文档覆盖：
  为什么不放在 Python src 里。
  未来目录草案。
  ownerConsoleApi 方法命名。
  TypeScript DTO 策略。
  前端页面路径设计。
  状态管理策略。
  样式和组件策略。
  Vite dev proxy 与 CORS 边界。
  npm scripts 命名建议。
  Python / Node 禁止 import 边界。
  未来测试策略。
  第一版前端工程创建标准。

更新 docs/web-owner-console-read-only-shell-design.md：
  补充 P2.29 前端栈设计链接。

更新 docs/owner-console-http-surface-audit.md：
  补充 P2.29 前端栈与目录边界链接。
```

边界：

```text
不创建 package.json。
不安装 Node 依赖。
不写 React 组件。
不写 CSS。
不启动前端 dev server。
不修改 FastAPI 运行时代码。
不新增 endpoint。
不新增 CORS。
不开放 Web 写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot adapter。
```

设计结论：

```text
前端工程未来放在 web/owner-console，而不是 src/ 或 src/plugins/ai_chat。
前端只能通过 GET /healthz 和 GET /api/v1/owner-console/* 读取数据。
第一版只接 /healthz 和 /routes，验证 App Shell 和 contract boundary。
Vite dev proxy 可以解决本地开发跨端口问题，不提前打开 FastAPI CORS。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console UI layout design

状态：已落地 P2.30 设计文档。目标是在创建真实前端工程前，先确定简约 UI 风格、中文导航、中文顶部状态条、页面信息层级和只读边界展示规则。

本次完成：

```text
新增 docs/web-owner-console-ui-layout-design.md。

设计结论：
  页面走简约工具风格。
  优先展示结构、内容和状态。
  左侧固定导航全部中文化。
  顶部状态条全部中文化。
  后端 JSON 字段继续保持英文 snake_case，前端展示统一转为中文标签。

中文主导航：
  概览
  任务
  审批
  诊断
  记忆
  访问控制
  设置

任务详情和审批详情不放入主导航，从列表点击进入。

顶部状态条中文标签：
  主人控制台
  只读模式：已开启
  网页写入：已关闭
  后端连接：已连接 / 已断开
  接口版本：owner_console.http.v1
  最后刷新：YYYY-MM-DD HH:mm:ss
  刷新
```

文档覆盖：

```text
三段式布局：左侧导航、顶部状态条、主内容区。
字段中文化规则。
页面状态中文化规则。
只读边界 UI 规则。
概览 / 任务 / 任务详情 / 审批 / 审批详情 页面信息层级。
诊断 / 记忆 / 访问控制 / 设置 页面信息层级。
通用组件清单。
视觉风格约束。
第一版 UI 完成标准。
```

更新：

```text
docs/web-owner-console-read-only-shell-design.md
docs/web-owner-console-frontend-stack-design.md
docs/owner-console-http-surface-audit.md
```

边界：

```text
不创建前端工程。
不安装 npm 依赖。
不写 React 组件。
不写 CSS。
不修改 FastAPI 运行时代码。
不新增 endpoint。
不开放 Web 写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot adapter。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console minimal App Shell

状态：已落地 P2.31 第一刀。目标是创建 `web/owner-console` 最小 Vite + React + TypeScript 前端工程，只接 `/healthz` 和 `/api/v1/owner-console/routes`，先跑通中文 App Shell、左侧导航、顶部状态条和只读 route contract 展示。

本次完成：

```text
新增 web/owner-console 前端工程。

新增：
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  index.html
  .env.example
  README.md
  src/main.tsx
  src/vite-env.d.ts
  src/api/ownerConsoleApi.ts
  src/api/ownerConsoleEnvelope.ts
  src/api/ownerConsoleTypes.ts
  src/app/App.tsx
  src/app/AppShell.tsx
  src/app/PlaceholderPage.tsx
  src/components/StatusBadge.tsx
  src/components/EmptyState.tsx
  src/styles/app.css

更新 .gitignore：
  忽略 web/owner-console/dist/
  忽略 web/owner-console/.vite/
```

前端第一刀能力：

```text
左侧中文固定导航：
  概览
  任务
  审批
  诊断
  记忆
  访问控制
  设置

顶部中文状态条：
  主人控制台
  只读模式：已开启 / 异常
  网页写入：已关闭 / 异常
  后端连接：连接中 / 已连接 / 已断开
  接口版本
  最后刷新
  刷新

概览页展示：
  只读接口状态
  route contract rows
  route_count
  allowed_methods
  write_routes_enabled=false
```

依赖与安全：

```text
npm install 后初始 Vite 5.x 链路触发 npm audit 漏洞提示。
根据 npm audit 修复建议，升级到 vite 8.1.4 和 @vitejs/plugin-react 6.0.3。
npm audit 后为 0 vulnerabilities。
```

边界：

```text
只调用 GET /healthz。
只调用 GET /api/v1/owner-console/routes。
不接 overview / tasks / approvals 业务数据。
不新增 FastAPI endpoint。
不修改 FastAPI 行为。
不打开 /docs /openapi.json。
不新增 CORS。
不新增登录/鉴权。
不开放 Web 写操作。
不新增审批确认/拒绝入口。
不触发 MainAgent。
不读取 Python 文件、数据库、.env 或日志。
```

本地 smoke：

```text
FastAPI backend:
  .\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090

Vite frontend:
  npm run dev

本地访问：
  http://127.0.0.1:5173/owner-console

进程状态：
  127.0.0.1:8090 LISTENING
  127.0.0.1:5173 LISTENING

HTTP smoke：
  GET http://127.0.0.1:5173/owner-console -> 200
  GET http://127.0.0.1:5173/healthz -> ok=true, read_only=true, web_write_enabled=false
  GET http://127.0.0.1:5173/api/v1/owner-console/routes -> resource=routes, route_count=10, methods=GET
```

浏览器验证：

```text
已尝试使用本地浏览器控制工具。
当前环境返回可用浏览器列表为空，因此本轮未完成截图级浏览器验证。
已用 Vite build、HTTP smoke 和 API proxy smoke 兜底验证。
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Dashboard data

状态：已落地 P2.32 第一刀。目标是在已有中文 App Shell 上接入概览页真实只读数据，先读取 `/overview` 和 `/diagnostics`，让页面能看到任务/审批计数、最近任务、待审批摘要、运行边界和轻量诊断状态。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleOverview / counters / task row / approval row 类型。
  增加 OwnerConsoleHealthSnapshot / text section / observation 类型。
  增加 overview 和 diagnostics envelope 类型。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /overview 和 /diagnostics。
  新增 getOverview({ task_limit, approval_limit })。
  新增 getDiagnostics()。
  增加 OwnerConsoleApiError，用于保留 HTTP status、error code 和 details。

新增 web/owner-console/src/pages/DashboardPage.tsx：
  并行读取 overview 和 diagnostics。
  overview 失败时用中文错误态展示，diagnostics 仍可独立展示。
  403 时提示检查 BOT_OWNER_QQ。
  展示待处理任务、失败任务、待审批、网页写入状态。
  展示最近任务表、待审批表、运行边界、轻量诊断分区。

新增 web/owner-console/src/components/ErrorState.tsx。
更新 App route：/owner-console 使用 DashboardPage。
更新 app.css：增加 dashboard、metric、compact table、diagnostic section、error/loading 状态样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/overview。
只调用 GET /api/v1/owner-console/diagnostics。
不接任务详情。
不接审批详情。
不显示审批确认/拒绝按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
不触发 diagnostics 主动探测。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console -> 200
GET http://127.0.0.1:5173/api/v1/owner-console/overview?task_limit=5&approval_limit=5
  resource=overview
  read_only=true
  web_write_enabled=false
  pending_tasks=9
  pending_approvals=2

GET http://127.0.0.1:5173/api/v1/owner-console/diagnostics
  resource=diagnostics
  read_only=true
  web_write_enabled=false
  bot_status_lines=4
  diagnostics_lines=4
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Tasks list data

状态：已落地 P2.33 第一刀。目标是在中文 App Shell 和 Dashboard 之后，接入任务列表页真实只读数据，让 `/owner-console/tasks` 可以读取 `/api/v1/owner-console/tasks` 并以表格展示主人私聊上下文内的任务。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleTaskList。
  增加 OwnerConsoleTaskListEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /tasks。
  新增 getTasks({ status, limit })。

新增 web/owner-console/src/pages/TasksPage.tsx：
  读取 GET /api/v1/owner-console/tasks?limit=20。
  支持中文状态筛选：全部、待处理、已完成、失败、已取消。
  展示任务 ID、目标摘要、状态、最近事件、待审批、下一步、详情入口。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查任务状态筛选或 limit。

更新 App route：
  /owner-console/tasks 使用 TasksPage。

更新 app.css：
  增加 data toolbar。
  增加 segmented filter tabs。
  增加 task table。
  增加只读详情链接样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/tasks。
不创建任务。
不取消任务。
不重试任务。
不推进任务。
不新增审批按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/tasks -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/tasks?limit=20
  resource=tasks
  read_only=true
  web_write_enabled=false
  total_visible=20
  rows=20

GET http://127.0.0.1:5173/api/v1/owner-console/tasks?status=pending&limit=20
  resource=tasks
  status_filter=pending
  total_visible=9
  rows=9
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Task detail data

状态：已落地 P2.34 第一刀。目标是在任务列表之后接入任务详情页真实只读数据，让 `/owner-console/tasks/:task_id` 可以读取 `/api/v1/owner-console/tasks/{task_id}` 并展示单个任务的目标、结果、关联审批和事件时间线。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleTaskEventRow。
  增加 OwnerConsoleTaskDetail。
  增加 OwnerConsoleTaskDetailEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /tasks/{positive_int} 动态路径校验。
  新增 getTaskDetail(task_id, { event_limit, preview_limit })。
  继续只使用 GET，不接受 owner context query 参数。

新增 web/owner-console/src/pages/TaskDetailPage.tsx：
  读取 GET /api/v1/owner-console/tasks/{task_id}?event_limit=20&preview_limit=800。
  展示任务信息、目标、结果、下一步、关联审批和事件时间线。
  支持从详情页返回任务列表。
  400 / 403 / 404 使用中文错误态说明。

更新 App route：
  /owner-console/tasks/:task_id 使用 TaskDetailPage。

更新 app.css：
  增加详情页 header action。
  增加返回链接、详情分区、关联审批小表格和事件时间线表格样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/tasks/{task_id}。
不创建任务。
不取消任务。
不重试任务。
不推进任务。
不确认或拒绝审批。
不新增审批操作按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/tasks/24 -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/tasks/24?event_limit=20&preview_limit=800
  resource=tasks
  read_only=true
  web_write_enabled=false
  task_id=24
  events=5
  approvals=1
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Approvals list data

状态：已落地 P2.34 第二刀。目标是在任务列表和任务详情之后补齐审批列表页真实只读数据，让 `/owner-console/approvals` 可以读取 `/api/v1/owner-console/approvals` 并以中文表格展示主人私聊上下文内的审批记录。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleApprovalList。
  增加 OwnerConsoleApprovalListEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /approvals。
  新增 getApprovals({ status, limit })。

新增 web/owner-console/src/pages/ApprovalsPage.tsx：
  读取 GET /api/v1/owner-console/approvals?limit=20。
  支持中文状态筛选：全部、待审批、已确认、已拒绝、已过期。
  展示审批 ID、任务 ID、工具、风险等级、状态、原因摘要、操作状态、创建时间和详情入口。
  操作状态只展示“网页只读”等元信息，不提供确认/拒绝入口。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查审批状态筛选或 limit。

更新 App route：
  /owner-console/approvals 使用 ApprovalsPage。

更新 app.css：
  增加 approval table 样式。
  移动端保持横向滚动，避免表格挤压布局。
```

边界：

```text
只调用 GET /api/v1/owner-console/approvals。
不确认审批。
不拒绝审批。
不恢复执行工具。
不新增审批操作按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/approvals -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/approvals?limit=20
  resource=approvals
  read_only=true
  web_write_enabled=false
  total_visible=19
  rows=19

GET http://127.0.0.1:5173/api/v1/owner-console/approvals?status=pending&limit=20
  resource=approvals
  pending_total=2
  pending_rows=2
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Approval detail data

状态：已落地 P2.34 第三刀。目标是在审批列表之后补齐审批详情页真实只读数据，让 `/owner-console/approvals/:approval_id` 可以读取 `/api/v1/owner-console/approvals/{approval_id}` 并展示审批风险、脱敏工具输入、关联任务和近期任务事件。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleToolInputPreview。
  增加 OwnerConsoleApprovalDetail。
  增加 OwnerConsoleApprovalDetailEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /approvals/{positive_int} 动态路径校验。
  新增 getApprovalDetail(approval_id, { event_limit, preview_limit })。
  继续只使用 GET，不接受 owner context query 参数。

新增 web/owner-console/src/pages/ApprovalDetailPage.tsx：
  读取 GET /api/v1/owner-console/approvals/{approval_id}?event_limit=5&preview_limit=800。
  展示审批信息、审批原因、工具输入预览、关联任务和近期任务事件。
  工具输入只展示后端已生成的 preview_json，并显示是否脱敏、是否截断。
  支持从详情页返回审批列表。
  支持跳转到关联任务详情。
  400 / 403 / 404 使用中文错误态说明。

更新 App route：
  /owner-console/approvals/:approval_id 使用 ApprovalDetailPage。

更新 app.css：
  增加详情页 section header / footer。
  增加工具输入预览块样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/approvals/{approval_id}。
不确认审批。
不拒绝审批。
不恢复执行工具。
不新增审批操作按钮。
不读取原始 tool_input_json。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/approvals/19 -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/approvals/19?event_limit=5&preview_limit=800
  resource=approvals
  read_only=true
  web_write_enabled=false
  approval_id=19
  has_task=true
  events=5
  redacted=false
  truncated=false
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Diagnostics data

状态：已落地 P2.35 第一刀。目标是在任务/审批主链路之后接入诊断页真实只读数据，让 `/owner-console/diagnostics` 可以读取 `/api/v1/owner-console/diagnostics` 并展示当前 Owner Console 可见的系统诊断快照。

本次完成：

```text
新增 web/owner-console/src/pages/DiagnosticsPage.tsx：
  读取 GET /api/v1/owner-console/diagnostics。
  展示快照时间、机器人状态、最近错误状态。
  展示机器人状态、诊断状态、配置状态、视觉状态、图片缓存、记忆状态、语音状态、最近错误。
  展示 MainAgent 观测和 RootGraph 观测。
  展示运行边界。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查诊断快照请求。

更新 App route：
  /owner-console/diagnostics 使用 DiagnosticsPage。

更新 app.css：
  增加 diagnostic card grid。
  增加 diagnostic card / diagnostic lines / empty line 样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/diagnostics。
不主动运行诊断探测。
不测试模型。
不读取新的图片。
不清理缓存。
不清理错误日志。
不重建索引。
不修改配置。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/diagnostics -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/diagnostics
  resource=diagnostics
  read_only=true
  web_write_enabled=false
  bot_status_lines=4
  diagnostics_lines=4
  memory_lines=11
  recent_errors_ok=true
  main_agent_observations=0
  root_graph_observations=0
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Memory data

状态：已落地 P2.35 第二刀。目标是在诊断页之后接入记忆页真实只读数据，让 `/owner-console/memory` 可以读取 `/api/v1/owner-console/memory` 并展示 Memory / MemoryRAG / ProjectDocRAG 的计数、配置和隐私边界。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleMemoryCounts。
  增加 OwnerConsoleMemoryContextPolicy。
  增加 OwnerConsoleMemoryRagSnapshot。
  增加 OwnerConsoleProjectDocRagSnapshot。
  增加 OwnerConsoleMemorySnapshot。
  增加 OwnerConsoleMemoryEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /memory。
  新增 getMemory()。

新增 web/owner-console/src/pages/MemoryPage.tsx：
  读取 GET /api/v1/owner-console/memory。
  展示消息、会话、会话摘要、长期记忆等计数。
  展示 RAG 文档、RAG 向量、场景摘要等详细计数。
  展示上下文策略。
  展示 MemoryRAG 配置。
  展示 ProjectDocRAG 配置。
  展示记忆正文、项目文档正文、检索、索引重建等隐私边界状态。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查记忆快照请求。

更新 App route：
  /owner-console/memory 使用 MemoryPage。

更新 app.css：
  增加 detail-list 样式，用于配置型只读字段展示。
```

边界：

```text
只调用 GET /api/v1/owner-console/memory。
不展示 messages.content。
不展示 long_term_memories.content。
不展示 rag_documents.content。
不执行 MemoryRAG 检索。
不执行 ProjectDocRAG 检索。
不重建索引。
不新增记忆。
不删除记忆。
不修改配置。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/memory -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/memory
  resource=memory
  read_only=true
  web_write_enabled=false
  message_count=384
  session_count=5
  manual_memory_count=13
  rag_document_count=977
  memory_content_exposed=false
  project_doc_content_exposed=false
  retrieval_executed=false
  index_rebuild_executed=false
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Access Control data

状态：已落地 P2.35 第三刀。目标是在记忆页之后接入访问控制页真实只读数据，让 `/owner-console/access-control` 可以读取 `/api/v1/owner-console/access-control` 并展示主人配置、聊天入口、陌生私聊策略、白名单、黑名单和运行边界。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleAccessList。
  增加 OwnerConsoleAccessControlSnapshot。
  增加 OwnerConsoleAccessControlEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /access-control。
  新增 getAccessControl({ item_limit })。

新增 web/owner-console/src/pages/AccessControlPage.tsx：
  读取 GET /api/v1/owner-console/access-control?item_limit=50。
  展示主人配置状态。
  展示私聊入口、群聊入口和陌生私聊策略。
  展示私聊白名单、群聊白名单、用户黑名单的数量、可见条目和截断状态。
  展示运行边界。
  400 时中文提示检查列表数量限制。

更新 App route：
  /owner-console/access-control 使用 AccessControlPage。

更新 app.css：
  增加 access-list-items 样式，用于只读名单条目展示。
```

边界：

```text
只调用 GET /api/v1/owner-console/access-control。
不添加白名单。
不移除白名单。
不拉黑用户。
不解除拉黑。
不修改私聊/群聊开关。
不修改陌生私聊策略。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/access-control -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/access-control?item_limit=50
  resource=access-control
  read_only=true
  web_write_enabled=false
  owner_configured=true
  private_chat_enabled=true
  group_chat_enabled=true
  unknown_private_policy=deny
  private_whitelist_count=2
  group_whitelist_count=2
  user_blacklist_count=0
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Settings data

状态：已落地 P2.35 第四刀。目标是在访问控制页之后接入设置页真实只读数据，让 `/owner-console/settings` 可以读取 `/api/v1/owner-console/settings` 并展示模型配置、Embedding、功能开关、角色卡摘要和运行边界。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleModelConfigSnapshot。
  增加 OwnerConsoleRoleCardRow。
  增加 OwnerConsoleSettingsSnapshot。
  增加 OwnerConsoleSettingsEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /settings。
  新增 getSettings()。

新增 web/owner-console/src/pages/SettingsPage.tsx：
  读取 GET /api/v1/owner-console/settings。
  展示聊天模型、MainAgent 模型和 Embedding 配置。
  API Key 只展示“已配置/未配置”。
  Base URL 只展示后端返回的脱敏值。
  展示功能开关。
  展示角色卡 key/title 和当前启用项。
  展示运行边界。
  400 时中文提示检查设置快照请求。

更新 App route：
  /owner-console/settings 使用 SettingsPage。

更新 app.css：
  增加 feature-flag-grid。
  增加 role-card-list / role-card-row 样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/settings。
不展示 API Key 原文。
不展示未脱敏 Base URL 密钥参数。
不保存配置。
不切换角色卡。
不写 data/active-role-card.json。
不修改功能开关。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/settings -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/settings
  resource=settings
  read_only=true
  web_write_enabled=false
  chat_model=deepseek-v4-flash
  chat_api_key_configured=true
  main_model=gpt-5.5
  main_api_key_configured=true
  embedding_model=bge-m3
  embedding_api_key_configured=false
  role_cards=2
  active_role_card_key=aike
  enable_main_agent=true
  enable_agent_shell=false
  enable_agent_web=false
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console frontend read-only audit

状态：已落地 P2.36 前端只读收口审计。目标是在主导航页面全部接入真实只读数据后，确认前端请求面、页面操作入口和文档边界仍符合 Web Owner Console v0 只读定位。

本次完成：

```text
新增 docs/web-owner-console-frontend-readonly-audit.md：
  记录主导航页面覆盖状态。
  记录 ownerConsoleApi 只读请求面。
  记录 allowlist 和动态详情路径校验。
  记录页面 button / Link 操作入口审计。
  记录写相关搜索命中的只读解释。
  记录当前仍保持的 MainAgent / ProjectDocRAG / Web v0 边界。
  给出后续建议：优先前端 smoke / contract guard、runbook、部署设计，再单独讨论登录/鉴权和审批操作。

移除 web/owner-console/src/app/PlaceholderPage.tsx：
  主导航页面已经全部接入真实只读数据。
  删除未使用占位组件，避免后续审计误把占位文案当作真实页面状态。
```

审计结论：

```text
所有 API client 请求都通过 ownerConsoleApi。
ownerConsoleApi 只使用 fetch GET。
前端 allowlist 只包含 Owner Console 只读 HTTP 资源。
动态详情路径只允许正整数 ID。
没有请求 /docs、/redoc 或 /openapi.json。
没有 approve / reject / resume / create / cancel 类型 API client。
页面按钮仅用于刷新或筛选。
页面链接仅用于查看详情或返回列表。
没有 Web 审批确认、拒绝、恢复执行、配置保存、角色卡切换、名单修改、记忆写入或索引重建入口。
```

边界：

```text
不新增后端接口。
不新增前端写能力。
不新增登录/鉴权。
不修改 FastAPI 运行时代码。
不触发 MainAgent。
不改变 QQ / /agent 行为。
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
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
