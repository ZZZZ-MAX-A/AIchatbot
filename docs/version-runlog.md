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

## 2026-07-11 MainAgent external-read 安全设计

状态：设计和前三刀本地合同已建立，未新增阶段编号；未启用任何真实联网工具。

本次完成：

```text
确认 system_diagnostics_report 是第二个正式只读工作任务；其基本稳定后的原主线是 external-read security design，而不是第二个审批写操作。
确认 RiskLevel.READ_EXTERNAL、PolicyEngine enable_external_read 和 ENABLE_AGENT_WEB 已存在，但当前没有 external-read ToolSpec/provider/executor/sanitizer。
新增 docs/main-agent-external-read-security-design.md。
第一版建议固定 external_search provider，禁止 arbitrary URL fetch。
第一版建议 llm_visible=false，只允许主人私聊严格命令；外部读取不创建写审批，也不保存 pending intent。
定义三重门控：工具注册、ENABLE_AGENT_WEB、严格主人命令。
定义 query 数据最小化、HTTPS/provider allowlist、IPv4/IPv6/metadata 阻断、redirect/DNS rebinding、响应预算和 prompt injection 边界。
定义 external_read_report 候选 work type 和独立 sanitizer；不得复用 external_request_count=0 的 system diagnostics sanitizer。
定义从纯策略、fake provider、正式 work、严格 QQ 命令到真实固定 provider live 的分步路线。
第一刀纯安全策略随后已实现：新增 external_read_security.py 和无网络参数化测试。
query 规范化后限制 300 字，并拒绝 URL、本地路径、API key/token/Authorization/cookie/JWT 等常见秘密形态。
固定 endpoint 只允许 HTTPS/443、无 userinfo/query/fragment，且 host 必须精确命中 allowlist。
解析后地址必须为公网 IPv4/IPv6；除 is_global 外显式拒绝 private、loopback、link-local、multicast、reserved 和 unspecified。
ExternalReadBudget 固定单请求、0 redirect、0 retry，最多 3 结果、256 KiB 和 15 秒。
实现不执行 DNS、HTTP、provider 调用或 ToolRegistry 注册。
第二刀 fake provider 链随后已实现：新增 external_search.py、async ExternalSearchProvider 协议、结构化 response/result、确定性 sanitizer 和 execute_external_search。
executor 在 provider 前执行 query policy，provider 只调用一次，并按 budget 强制总超时和 response_bytes 上限。
外部结果移除 HTML/script/style/template/noscript、控制字符和双向控制符；title/snippet/time 限长。
提示注入结果替换为中性占位；输出只显示 source_host，不显示完整 URL/query/fragment。
结果按 title + host 去重并最多保留 3 条；非法结果按条丢弃，全无可用结果时返回证据不足而不扩大查询或重试。
确定性 formatter 不调用 LLM，不写 RAG/记忆，不打开来源页面，也不发送额外 QQ。
fake provider 只存在于测试；生产模块没有 DNS/HTTP client、ToolSpec 或 QQ 接线。
第三刀正式 work runtime 随后已实现：新增可选注入的 external_read_report，risk_level=read_external，requires_approval=false。
未注入 external executor 时，生产 OwnerRuntimeFactory 仍只注册既有两个本地只读 work；当前 QQ 不会看到 external-read。
独立 ExternalReadReportPayload/sanitizer 强制单次外部请求、最多 3 条结果、合法 provider 枚举、来源/丢弃计数和成功/无结果状态一致性。
外部 query 只传给本次 executor；任务 goal 和 work event 使用固定占位摘要，不保存 query 原文。
title、snippet 和 source host 明细只进入本次经过清理的临时回复；持久化结果只包含 provider 名称和安全计数。
无结果为 done；执行器原始异常只保存异常类型和固定错误类别，不保存异常正文。
第三刀仍只注入 fake executor 做 runtime 测试，没有严格 QQ parser、ToolSpec、DNS、HTTP 或真实 provider。
第四刀严格 QQ 命令随后已实现：只接受 /agent 执行外部只读查询：<问题>。
命令按主人私聊、ENABLE_AGENT_WEB、固定 executor 和 query policy 顺序门控；任何拒绝都发生在任务创建和 provider 调用之前。
生产 OwnerRuntimeFactory 仍不注入 external executor，ENABLE_AGENT_WEB 默认 false；因此当前命令只返回关闭或 provider 未配置提示。
fake executor 只用于测试可选注册和 work 合同；未给普通聊天或 Main LLM ToolRegistry 注册 external-read。
没有 pending intent、模糊“可以”确认、额外 QQ、DNS、HTTP、真实 provider 或自动重试。
```

当前边界：

```text
ENABLE_AGENT_WEB 继续 false。
不注册 web_search、web_fetch 或 arbitrary URL 工具。
不发起真实外部请求。
不让 Main LLM 自由选择 external read。
不把外部内容写入 MemoryRAG、ProjectDocRAG 或长期记忆。
不新增额外 QQ、自动 retry、浏览器自动化、下载、Web 写操作或诊断自动修复。
P2.40b、P2.41 和 P2.42 继续未批准。
```

第一刀验证：

```text
external-read 纯策略：11 tests OK
现有 PolicyEngine：10 tests OK
external-search fake executor：9 tests OK
MainAgent bridge：54 tests OK
external-read 正式 work runtime：22 tests OK
全量回归：438 tests OK
Python AST：108 files OK
git diff --check：通过
第四刀严格入口聚焦：OwnerAgentWorkRuntime 25 tests、MainAgent bridge 54 tests、QQ 边界 12 tests OK
第四刀完成后全量回归：442 tests OK
```

## 2026-07-11 MainAgent 局部诊断按 view 采集收口

状态：本地实现和回归已完成，未新增阶段编号；尚未单独进行主人 QQ live。

本次完成：

```text
新增内部 docs/main-agent-command-capability-audit.md，逐项记录 /agent 路由、工具、provider、读写、LLM/RAG、副作用、输出和测试。
DiagnosticsGraph 从所有 view 共用全量节点序列，改为完整的 DiagnosticsView -> node sequence 映射。
FULL 保持原有 config/runtime/TTS/errors/memory/image cache 全量采集。
CONFIG 只经过 config 和 render。
VISION 只经过 config、image cache 和 render；既有视觉 formatter 继续负责视觉检查。
RECENT_ERRORS 只经过 errors 和 render。
IMAGE_CACHE 只经过 config、image cache 和 render。
MEMORY 只经过 memory stats 和 render，并把已采集 stats 传给 formatter，避免基础统计重复查询。
TTS 只经过 config、TTS health 和 render。
所有 DiagnosticsView 枚举成员都必须出现在显式映射中；新增参数化测试验证局部 view 不调用无关 handler。
```

边界：

```text
不改变 QQ 命令名称、确定性语义分类或现有输出格式。
不改变正式 system_diagnostics_report 的四个 scope。
不增加外部请求、深度探针、自动下钻、修复、写操作或额外 QQ。
formatter 自身已有的合法读取仍保留；node trace 不能被误读为 renderer 内部零读取。
```

测试：

```text
Graph 合同：21 tests OK
Graph runner：46 tests OK
诊断 formatter：10 tests OK
MainAgent bridge + QQ/RAG boundary + system diagnostics + formal work runtime：124 tests OK
全量回归：412 tests OK（补充 runner 建议后）
Python AST：104 files OK
git diff --check：通过
```

补充 live 现象与提示边界：

```text
主人确认 Ollama Model location 已指向 D:\OllamaModels，单实例、模型存在和显存余量均正常。
qwen2.5vl:3b 曾在真实图片后持续返回低质量重复内容；手动执行 ollama stop qwen2.5vl:3b 后，固定自检恢复为正常、返回 74 字，随后真实 QQ 图片和再次自检均成功。
/agent 查看视觉状态 和 /agent 完整排查图片识别问题 现在只在服务/模型可用且推理明确为低质量重复内容时提示“runner 可能处于异常状态”。
提示给出手动命令 ollama stop qwen2.5vl:3b，并明确只卸载模型、下次请求重新加载；诊断不自动执行、不自动重试。
超时、服务不可达、模型不存在等其他失败不会误用 runner 恢复建议。
相关聚焦回归 121 tests OK；全量回归 412 tests OK。
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
  /agent 执行研发上下文任务：<问题> 仅允许主人私聊显式执行 development_context_report，并形成 running -> done / failed 生命周期。
  研发上下文任务在有召回且 MainAgent LLM 开启时返回固定六字段受限报告；不可用时确定性回退，任务记录只保存命中计数和总结方式。
  /agent 执行系统诊断任务 与 /agent 执行系统诊断任务：视觉 仅允许主人私聊显式执行 system_diagnostics_report/overview 或 vision；分别使用确定性六区分诊和首故障视觉状态链，任务记录只保存安全状态/层级/计数。
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

## v1.6 MainAgent zoned system diagnostics overview

状态：已完成 P2.46a 设计、P2.46b 系统概览、P2.46c 视觉区详情和 P2.46d 主人 QQ live。随后在不另设阶段编号的前提下，增加了语音、记忆与RAG区域详情以及 MainAgent 路由/表达收口。设计见 `docs/main-agent-system-diagnostics-report-design.md`。

当前扩展（不另设阶段编号）：

```text
system_diagnostics_report 当前严格注册 overview、vision、voice 和 memory_rag。
/agent 执行系统诊断任务：语音 沿 configuration -> endpoint -> service -> model -> observation 首故障链检查，只读 loopback TTS health、loaded、language、最近候选和最近安全发送观测。
/agent 执行系统诊断任务：记忆与RAG 沿 configuration -> storage -> index -> runtime -> observation 首故障链检查，只读非正文存储/索引统计和最近安全观测。
voice 不生成音频、不创建音频文件、不发送 QQ、不重启或加载/下载模型；memory_rag 不执行 embedding、语义召回、ProjectDocRAG 正文读取或索引重建。
/agent 语音状态怎么样 已显示总体状态、开关、服务可达性、health、IndexTTS2 loaded、语言、最近候选和端到端未验证声明。
/agent 查看配置状态 已更新为基础入口、聊天模型、MainAgent、记忆与RAG、视觉、语音和高风险边界分区，并继续对 URL 与 Key 脱敏。
未知且无 Main LLM 的 /agent 表达现在进入 ask_owner，不再默认调用 dev_context/RAG；显式 /agent 查、/agent 查询、/agent search 和 /agent-debug 仍可进入研发上下文。
Main LLM 遇到对象、范围或运行/研发歧义时优先 ask_owner；运行状态禁止由 dev_context 兜底猜测。
MainAgent 工具总结新增中性身份边界：RAG/工具结果不是身份设定，不采用角色名、自称、动作旁白，也不虚构未执行检查。
OwnerAgentWorkRuntime sanitizer 已支持四种报告 payload；任务记录只保留区域状态、定位层级、推荐 scope 和安全计数，任何 external/deep/repair 非零结果都拒绝完成。
```

当前扩展验证：

```text
聚焦回归：148 tests OK。
全量 unittest discover：407 tests OK。
新增视觉 8 种、语音 7 种、记忆与RAG 8 种概览—详情状态一致性合同，以及三类详情共同实用性输出合同。
Python compile、AST 和 git diff --check 通过。
既有非失败提示：FastAPI/Starlette TestClient 与 httpx 弃用警告。
```

主人 QQ live：

```text
正式任务：#33 系统概览、#34 视觉详情、#35 语音详情、#36 记忆与RAG详情；四条命令均成功完成。
主人核对任务详情后确认 external_request_count=0、deep_probe_count=0、repair_action_count=0，其他功能输出正常。
#35 定位为语音服务层降级：TTS 开启、地址为本机 loopback，但本地服务不可达；第一故障链因此没有继续判断 health、IndexTTS2、语言或生成/发送状态。
live 发现服务失败时下游“未继续判断”原因不够直观，且任务回复尾部仍只写 overview/vision。代码已补充 health、模型、语言、生成、发送的逐项跳过原因，并把边界更新为 overview、vision、voice、memory_rag。
正式任务 #37 当时完成主人 QQ live 复验：输出仍按旧语义定位服务层降级；health、IndexTTS2、语言、最近生成和最近发送均明确写明因本地服务不可达而未继续判断；尾部正确列出视觉、语音、记忆与RAG区详情。该段是运行策略补充前的历史输出，不代表当前严重度结论。
主人随后明确 TTS 为节省显存采用真实语音请求时按需冷启动。当前实现新增 `auto_start_enabled` evidence 和启动策略层：自动冷启动开启且服务未运行时为正常/按需待机；服务在线但 `loaded=false` 时为模型等待首次生成按需加载；自动启动关闭且服务不可达或 health 明确异常时才降级。overview、正式语音详情和快速语音状态复用同一纯状态 evaluator。
快速语音状态 QQ live 已正确显示“按需待机”。正式语音任务 #40 随后失败：纯报告已生成 `fault_layer=startup`，但 OwnerAgentWorkRuntime 的 `expected_statuses` 遗漏该新层，访问映射时触发 `KeyError`。补上 `startup -> normal` 并新增真正经过任务创建、sanitizer、持久化和格式化的回归后，聚焦 59 项、全量 407 项通过；主人重启 Bot 重新验证正式语音详情和 overview，反馈均没有问题。新的成功任务 ID 未提供，因此不补写编号。该 live 没有触发真实 TTS 冷启动、模型加载、音频生成或 QQ 发送。
该 live 不代表执行了真实视觉推理、TTS 音频生成、QQ 语音端到端发送、embedding、语义召回或 MemoryRAG 重建。
系统概览曾显示 2 条活动文档缺少向量；仅保留为已发现现象，不自动重建索引或创建修复任务。
```

本次完成：

```text
将 system_diagnostics_report 定位为第二个候选正式只读工作类型。
默认任务只做系统大区概览分诊，不复制现有诊断系统的完整输出。
采用“系统概览 -> 区域详情 -> 针对性深度探针”三级模型。
正常和按设计关闭的大区合并输出，只单独突出异常、降级、需要关注和影响判断的未知区域。
概览最多推荐一个优先排查区域，并返回严格的主人确认命令；不自动创建详情任务。
首批核心大区定义为核心运行、聊天、MainAgent、记忆与RAG、视觉和语音；Owner Console 为可选区。
区域详情沿固定依赖链查找第一故障层，上游失败后不继续堆叠无关下游证据。
视觉区作为首个候选详情试点，明确区分服务在线、模型已安装、模型驻留和最近使用状态。
概览不调用 LLM、外部聊天 API、视觉推理、embedding、RAG 召回或 ProjectDocRAG 正文。
定义了自适应短输出、安全持久化摘要、部分失败、任务 done/failed 和显式下钻合同。
```

拟定拆分：

```text
P2.46b：只实现结构化大区快照、确定性 evaluator、overview 和第二个正式只读 work type。
P2.46c：实现 vision 区域详情试点，不执行真实推理。
P2.46d：重启 Bot 后完成主人 QQ live，验证短输出、显式下钻和安全持久化。
其他区域详情和深度探针根据实际使用结果另行批准。
```

P2.46b 实现：

```text
新增 src/plugins/ai_chat/system_diagnostics_report.py：
  六个固定大区的结构化 evidence 和 status。
  normal / attention / degraded / error / off_by_design / unknown 确定性判断。
  严重度和核心依赖优先级选择一个 primary scope。
  正常/按设计关闭区域合并，异常区域单行突出，概览最多 1200 字符。
  只允许 loopback 服务 URL 进入廉价本地探针判断。

OwnerAgentWorkRuntime：
  注册第二个 system_diagnostics_report/read_local work type。
  新增严格“执行系统诊断任务”解析；overview 可执行，已知区域和未知 scope 均在任务前停止。
  系统概览 sanitizer 强制 external_request_count、deep_probe_count、repair_action_count 全为 0。
  QQ 详细报告只在本次主人私聊返回；task.result 和 work_finished 只保存总体状态、六区计数、优先区域和安全计数。

OwnerRuntimeFactory / QQ 入口：
  注入 event-bound system_diagnostics_report executor。
  /agent 执行系统诊断任务 只允许主人私聊且先于普通语义/LLM 路径执行。
  /agent-debug、普通聊天、群聊、非主人私聊和 Web 不能触发。
  区域详情未注册时不创建任务，不执行探针，不 fallback 到 dev_context。

overview 证据：
  核心运行：当前入口和数据库 SELECT 1。
  聊天：开关、模型配置完整性和最近 RootGraph 安全错误布尔值；不发 completion。
  MainAgent：两个正式 work type、主人私聊策略和 owner_write_command 审批/受控恢复标记。
  记忆与RAG：MemoryRAG 非正文索引/向量/待索引计数和最近安全观测；不做 embedding/召回。
  视觉：只对 loopback Ollama 查询服务和模型列表，结合最近视觉计数；不做推理。
  语音：关闭时跳过；开启且 loopback 时只读 health；不生成音频。
```

P2.46c 实现：

```text
system_diagnostics_report.py：
  新增 VisionDiagnosticsReportPayload、vision scope、1800 字符上限和固定定位层级。
  按 configuration -> service -> model -> invocation/quality/observation 首故障短路。
  视觉关闭为 off_by_design；非 loopback/未验证服务为 unknown；服务或模型不可用为 degraded。
  最近调用错误只建议 vision_invocation，低质量只建议 vision_inference；两个深度 scope 均未注册且不会自动执行。
  无近期使用保持 normal/neutral，并明确不等于端到端验证。

OwnerAgentWorkRuntime：
  system_diagnostics_report sanitizer 同时接受 overview 与 vision 两种结构化 payload。
  vision task.result/work_finished 只保存区域状态、定位层级、推荐 scope 和本地/深度/外部/修复计数。
  external_request_count、deep_probe_count、repair_action_count 任一非 0 都拒绝完成任务。
  不持久化详细状态链、日志、图片、路径、配置值或完整观测。

OwnerRuntimeFactory / QQ 入口：
  /agent 执行系统诊断任务：视觉 仅允许主人私聊显式执行并创建 scope=vision 正式任务。
  overview 与 vision 共用视觉 evidence collector，避免两个输出漂移。
  vision-only 在数据库、MemoryRAG、MainAgent 注册表、TTS 和聊天概览探针之前返回。
  只允许 loopback Ollama /api/tags；非 loopback 地址不主动访问。
  不执行 describe_images、真实视觉推理、测试图片、模型拉取、服务重启、自动子任务、重试或修复。
  其他已知区域和未知 scope 仍在任务创建前停止，不 fallback 到语义 MainAgent、LLM 或 dev_context。
```

P2.46c 验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_system_diagnostics_report tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract tests.test_diagnostics_units tests.test_config_loading -q
Ran 166 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -q
Ran 375 tests OK

既有非失败提示：FastAPI TestClient 依赖产生 StarletteDeprecationWarning。
```

P2.46c 文档与检索验证：

```text
.\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=62
  chunks_seen=1320
  created_documents=1
  updated_documents=221
  embeddings_created=1
  embeddings_updated=75
  errors=0

P2.46c 当时的固定查询“P2.46c system_diagnostics_report vision 视觉区详情 当前实现 P2.46d QQ live 待验收”：
  project_results=5
  第 1 条为 current-development-status P2.46c 当前状态锚点
  第 2 条为 main-agent-system-diagnostics-report-design 的 P2.46c 实现清单
  第 4、5 条为设计总状态和 version-runlog 当前阶段
  当时召回结论一致：P2.46c 本地完成，P2.46d Bot 重启和主人 QQ live 待完成
  历史 P2.46a/b 片段只作为后排阶段记录，没有覆盖当前状态锚点
```

边界：

```text
本段是 P2.46c 完成时的历史边界；当时尚未重启 Bot 或进行 P2.46d live 验收，后续 live 已完成。
普通聊天仍不能触发 MainAgent；ProjectDocRAG 正文仍只进入显式 /agent dev_context。
不新增 shell、Git、任意文件读写、未注册数据库写入、外部请求、自动诊断、自动下钻、自动修复或额外 QQ 发送。
Owner Console 继续只读 GET；P2.40b、登录鉴权和 Web 审批操作继续未批准。
```

P2.46b 验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_system_diagnostics_report tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract tests.test_diagnostics_units tests.test_config_loading -v
Ran 155 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 364 tests OK

既有非失败提示：FastAPI TestClient 依赖产生 StarletteDeprecationWarning。
```

P2.46b 文档与检索验证：

```text
.\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=62
  chunks_seen=1318
  new_documents=1
  new_embeddings=1
  errors=0

固定查询“P2.46b system_diagnostics_report overview 当前实现 视觉区域待完成 QQ live”：
  project_results=4
  memory_results=0
  第 1 条为 current-development-status P2.46b 快照
  其余命中来自 main-agent-system-diagnostics-report-design 和 version-runlog
  全部一致声明 P2.46b 本地完成、P2.46c 视觉详情和 P2.46d QQ live 未完成
```

文档与检索验证：

```text
Markdown 相对链接检查：没有缺失目标。
git diff --check：通过。
第一次 ProjectDocRAG 重建因执行工具 64 秒上限被中断，未将其记为成功。
使用更长命令超时重新执行 .\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=62
  chunks_seen=1317
  errors=0

P2.46a 设计阶段固定查询“P2.46a system_diagnostics_report 分区分层诊断 默认短概览 视觉区域 尚未实现”：
  project_results=5
  memory_results=0
  5 条均来自 main-agent-system-diagnostics-report-design 或 version-runlog 的 P2.46a 记录
  当时结果明确区分 P2.46a 设计完成与 P2.46b-d 尚未实现
  该记录是 P2.46a 历史检索验证，不覆盖本节前面的 P2.46b 当前实现状态
```

## v1.6 Development context current-state production connection

状态：已完成 P2.45c 实现、回归及 P2.45d 本地索引和主人 QQ live 验收。目标是只为主人私聊正式 `development_context_report` 接入固定当前状态锚点和多来源语义证据，不改变普通 `/agent`、`/agent-debug`、本地通用 DevContext 或普通聊天。

本次完成：

```text
src/plugins/ai_chat/rag/development_report.py：
  固定先从 ProjectDocRAG 读取 current-development-status 锚点，再生成一次 query embedding。
  项目语义候选固定至少 12 条，排除锚点 source，每 source 最多 1 条，最终最多 3 条。
  记忆继续只读检索，并与 anchor 1200 / project 1800 / memory 800 / format 400 分区预算合并。
  只返回 current_status_anchor_missing、current_status_anchor_failed、query_embedding_failed、project_retrieval_failed、memory_retrieval_failed 等固定类别，不把异常原文写进结果。

DevContextGraph：
  新增默认关闭的内部 development-report evidence 模式。
  只有 run_development_context_report_for_event 固定传 true；普通 MainAgent dev_context 继续使用原 retrieve_combined_rag。
  正式模式的图 metadata 只保留锚点布尔值/块数、项目来源数/结果数、记忆结果数、来源多样性标志和固定 warning/error 类别。
  原始 RagDocument/RagSearchResult 只存在于单次图执行闭包，报告 source 经过脱敏后进入 context_text，不写入 metadata 或任务持久化。

报告与持久化：
  当前状态锚点固定排在项目语义证据和开发侧记忆之前。
  主模型提示明确：锚点决定当前阶段、未完成项和明确延后项；语义文档只补设计/历史；记忆不能覆盖锚点。
  锚点与历史材料冲突时，历史材料必须按历史说明。
  确定性回退和受限主模型结果都追加固定的锚点/检索限制说明。
  agent_tasks.result 与 work_finished.output_summary 只新增“当前状态锚点：已加载/缺失”和“检索警告：N”，不保存详细报告、路径、分数、source id、片段或异常原文。
```

部分失败策略：

```text
锚点成功、embedding 或语义检索失败：使用锚点完成部分报告，任务可保持 done，并显示固定证据限制。
锚点缺失、语义证据成功：使用语义证据完成报告，并明确不能保证最新阶段。
没有任何证据且存在技术检索错误：DevContextGraph execution_failed，任务 failed。
干净地没有命中且没有技术错误：返回证据不足回退，不伪造系统故障。
不自动重试，不直接读文件兜底，不发送额外 QQ。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_development_context_report tests.test_main_agent_llm tests.test_owner_agent_work_runtime tests.test_memory_rag_qq_boundary -v
Ran 48 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 222 tests OK

既有非失败提示：FastAPI 测试依赖产生 StarletteDeprecationWarning。

更新快照和文档后执行 .\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=59
  chunks_seen=1271
  errors=0

使用重建后的真实本地索引和固定问题“恢复 Owner Console 当前开发状态和下一步计划”执行正式证据检索干跑：
  anchor_included=true
  anchor_chunks=1
  anchor 包含 P2.45c、P2.40b 和 Owner Console 只读边界
  project_results=3
  project_sources=web-owner-console-read-model-design、owner-console-http-surface-audit、version-runlog
  memory_results=0
  warnings=0
  errors=0
  execution_failed=false
  evidence_chars=2720
```

主人 QQ live 验收：

```text
任务 #27 仍返回 P2.34 任务详情和 P2.39b 本地启动脚本等旧阶段材料，没有加载当前状态锚点策略。
重启 Bot 后再次执行固定命令，任务 #28 正确返回：
  当前处于 P2.45c，P2.45a-c 已完成。
  P2.45d 本地索引和固定问题检索已完成，live 是当时剩余验收项。
  P2.40b 未批准，业务页面继续初次加载加手动刷新。
  Owner Console 保持只读 GET，不开放 shell、Git、任意文件读写、Web 写操作或登录鉴权。
  证据与限制明确“当前状态锚点已加载”，并把旧 P2.34 材料降为历史参考。

任务 #28 详情持久化摘要：
  状态=已完成
  项目文档命中=2
  开发侧记忆命中=0
  当前状态锚点=已加载
  检索警告=0
  summary_mode=受限主模型结构化总结

任务详情和 work_finished 事件均未保存详细六字段报告、原始 RAG 片段、路径、source id、分数或异常原文。
项目文档最终命中 2 少于选择上限 3 属正常结果：来源多样性选择之后仍受 1800 字符项目证据预算约束。
```

边界：

```text
P2.45c 没有新增 work type、QQ 命令、Web endpoint、Web 写操作、登录鉴权、shell、Git、任意文件读写、未注册数据库写入或多步写自动化。
Owner Console 继续只读 GET；P2.40b 继续未启用；/docs、/redoc、/openapi.json 继续关闭。
本地干跑没有发送 QQ；live 命令由主人手动发送。P2.45 已完成，不新增任何自动 QQ 发送。
```

## v1.6 Development context diverse evidence policy

状态：已完成 P2.45b。目标是在不查询数据库、不调用 embedding、不接 QQ 生产路径的前提下，把研发报告所需的候选扩展、固定锚点排除、单来源去重和分区预算实现为独立纯策略。

本次完成：

```text
新增 src/plugins/ai_chat/rag/development_report.py：
  development_report_candidate_top_k：requested<=0 返回 0；正常至少 12；requested*4；最大 32。
  select_development_report_project_results：固定排除 current-development-status source；空 source 跳过；每 source 最多 1 条；最多 3 条；保持候选原 score 顺序。
  build_development_report_evidence：分别裁剪 current_status_docs、project candidates 和 memories，返回 CombinedRagResults。
  固定预算：anchor 1200、project 1800、memory 800、format reserve 400；与 P2.44 4200 source limit 启动时严格校验一致。
  输入使用不可变 RagDocument 替换裁剪，不修改原候选对象。

tests/test_development_report_retrieval.py：
  覆盖候选池边界、单来源霸榜、锚点语义重复、空 source、缺失锚点、三个分区精确限长、总证据 3800 和输入不变。
```

边界：

```text
纯策略模块没有数据库、embedding、QQ、Web、MainAgent 或 work runtime 依赖。
retrieve_combined_rag、DevContextGraph 和 development_context_report 尚未调用该策略。
当前 Agent 仍使用旧纯语义召回；不需要主人 QQ 测试。
不新增 shell、任意文件读写、数据库 schema、外部 reranker 或 Web 写操作。
P2.40b 继续未启用。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_rag_units -v
Ran 23 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -q
Ran 214 tests OK

源码调用审计：除策略定义、RAG export 和测试外，没有生产模块调用 build_development_report_evidence 或 development_report_candidate_top_k。

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 59，扫描片段 1269，错误：无。

使用原问题“恢复 Owner Console 当前开发状态和下一步计划”执行真实本地 embedding + 前 12 候选纯策略演练：
  candidate_count=12
  前 12 候选实际只有 3 个不同 source，多条历史片段重复占位。
  selected_sources=web-owner-console-read-model-design、owner-console-http-surface-audit、version-runlog
  anchor_count=1
  evidence_anchor_count=1
  evidence_project_count=3
  evidence_content_chars=2721

该演练仅手动调用纯策略，没有修改 DevContextGraph/Agent 生产链，也没有发送 QQ。
```

## v1.6 Development context current-state anchor foundation

状态：已完成 P2.45a。目标是在不接入 QQ 正式任务、不修改语义排序的前提下，先建立固定当前状态快照、ProjectDocRAG 精确锚点读取和 anchor/semantic 结果模型分离。

本次完成：

```text
新增 docs/current-development-status.md：
  目标保持单 chunk，记录当前阶段、完成项、未完成项、明确延后、安全边界、下一步和证据限制。
  当前准确声明 P2.45a 已完成基础、P2.45b-c 尚未实现、P2.40b 未批准。

src/plugins/ai_chat/rag/project_docs.py：
  固定注册 CURRENT_DEVELOPMENT_STATUS_SOURCE_ID=docs/current-development-status.md。

src/plugins/ai_chat/rag/documents.py：
  list_rag_documents 增加内部 source_id 精确过滤，不暴露为 QQ/Web 参数。

src/plugins/ai_chat/rag/project_index.py：
  新增 retrieve_current_development_status(is_owner, max_context_chars)。
  函数不接受 source_id/path；只读取固定锚点，校验 owner 可见性、软删除、chunk 顺序和 1200 字符预算。

src/plugins/ai_chat/rag/combined.py：
  CombinedRagResults 新增默认空 current_status_docs。
  anchor 使用 RagDocument，不伪造 similarity score；只有非空时才由 debug formatter 显示。
  现有 retrieve_combined_rag 未调用锚点函数，普通格式化输出不变。
```

边界：

```text
尚未修改 DevContextGraph、MainAgent、owner work runtime 或 QQ adapter。
development_context_report 当前仍使用旧纯语义 project_docs + memories。
新增快照可能被普通语义检索机会性命中，但尚无固定锚点保证，也没有来源去重或分区预算。
普通聊天、普通 /agent dev_context、/agent-debug 和 Web 行为不变。
不新增任意路径读取、shell、Git 工具、文件写入、数据库 schema 或 Web endpoint。
P2.40b 继续未启用。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_rag_units -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary -q
Ran 134 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -q
Ran 210 tests OK

覆盖固定 source id、无路径参数、owner scope、chunk 顺序、字符预算、软删除、单 chunk 快照、默认空 anchor 和现有格式输出不变。

docs/current-development-status.md 本地检查：
  773 characters
  1 个 Markdown heading
  重建后 1 个 ProjectDocRAG chunk

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 59，扫描片段 1266，错误：无。

真实索引固定读取验证：
  owner_anchor_count=1
  source_id=docs/current-development-status.md
  chunk_index=0
  content_chars=772
  non_owner_anchor_count=0

原始查询“恢复 Owner Console 当前开发状态和下一步计划”仍只召回 P2.34 与 P2.39b 历史片段。
这证明 P2.45a 尚未改变生产检索；P2.45b-c 的来源多样性和固定接入仍然必要。
```

## v1.6 Development context current-state retrieval design

状态：已完成 P2.45 设计，尚未修改运行时。主人私聊 live 结果证明 P2.44 能安全生成结构化报告，但同一问题只召回 P2.34 任务详情和 P2.39b 本地启动脚本；索引包含最新文档，缺口位于纯语义排序、单来源历史片段霸榜和上下文顺序截断。

本次设计：

```text
新增 docs/development-context-current-state-retrieval-design.md。
规划固定 docs/current-development-status.md 作为权威当前状态快照。
锚点 source id 由代码固定注册，用户、LLM、Web 和环境变量不能传任意路径。
锚点仍从 ProjectDocRAG 数据库读取，不在 QQ adapter/work runtime 直接打开文件。
正式 development_context_report 计划固定启用锚点；普通 /agent dev_context 第一刀保持现状。
语义检索计划先扩大内部候选池，再限制每个 source_id 最多 1 个片段。
报告 4200 字符输入计划拆为：锚点 1200、项目语义证据 1800、开发侧记忆 800、格式余量 400。
锚点、semantic project results 和 memories 在结果模型中分开，不伪造锚点相似度。
```

不采用：

```text
不只增大 top_k、降低 min_score 或扩大上下文。
不按整个 version-runlog 文件 mtime 判断章节新旧。
不让主模型从缺失的上下文猜最新状态。
不新增 shell、Git 工具、任意文件读取、目录扫描或自动状态生成。
```

实现拆分：

```text
P2.45a：当前状态快照和固定锚点读取基础，不接 QQ。
P2.45b：候选扩展、单来源去重和分区预算。
P2.45c：只接 development_context_report，并补持久化/入口/Owner Console 回归。
P2.45d：重建索引和主人手动 live 验收。
```

边界：

```text
本次仅文档设计，没有运行时代码、数据库 schema、QQ 命令、Web endpoint 或前端改动。
普通聊天继续不能进入 ProjectDocRAG。
Owner Console 继续只读。
P2.40b 继续未批准，业务页面保持手动刷新。
```

验证：

```text
git diff --check
Markdown fence check
OK

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 58，扫描片段 1264，错误：无。

.\scripts\rebuild-rag-index.ps1 -QueryDevContext "P2.45 当前状态锚点 来源多样性 分区预算 尚未实现" -TopK 4 -MaxContextChars 2200
项目文档命中 4，均能明确召回 P2.45 已完成设计、尚未实现，以及 P2.45a-d 的实现拆分；记忆命中 0。

原始“恢复 Owner Console 当前开发状态和下一步计划”查询仍会召回旧片段，符合本步仅设计、未修改运行时的预期。
```

## v1.6 MainAgent useful development context report

状态：已落地 P2.44。目标是让主人私聊显式研发上下文任务返回真正有用的“当前阶段、完成项、未完成项、安全边界和下一步”，同时继续禁止原始 RAG、路径、详细回复和异常文本进入任务记录。设计与边界见 `docs/main-agent-useful-development-context-report-design.md`。

本次完成：

```text
新增 src/plugins/ai_chat/development_context_report.py：
  定义固定六字段报告结构、JSON 严格解析、确定性回退、报告格式化和限长。
  总结输入最多 4200 字符；移除来源路径、检索元数据，并预脱敏密钥、Token、URL、本地路径和 .env。

src/plugins/ai_chat/graph/main_agent_llm.py：
  新增专用 development-context report system prompt 和直接 LLM 调用。
  不进入 ActionRequest planner，不附带工具，只接受固定 JSON；禁止编造提交/日期或输出原始 RAG、路径、标识符和异常文本。

src/plugins/ai_chat/__init__.py：
  DevContextGraph 成功后构造受限总结输入。
  MAIN_AGENT_USE_LLM=true 且有召回时执行一次固定 JSON 总结；模型关闭、无召回、调用或 JSON 失败时使用确定性回退。
  总结失败不把任务标成 failed，不重试，不新增消息发送。

src/plugins/ai_chat/owner_agent_work_runtime.py：
  详细 QQ 回复与持久化摘要分层。
  task.result 和 work_finished 继续只保存命中计数、总结方式和固定安全说明。
  详细回复再次脱敏并限制为 2400 字符，不持久化。
```

边界：

```text
唯一执行入口仍是主人私聊 /agent 执行研发上下文任务：<问题>。
普通聊天、群聊、非主人私聊、/agent-debug、Web Owner Console 和 MainAgent LLM 工具选择不能触发该 work runtime。
专用总结调用没有 ToolRegistry、ActionRequest、shell、文件写入、数据库写入、Web 写操作或 QQ 发送能力。
DevContextGraph 失败仍进入 failed；只有总结失败才安全回退为 done。
P2.40b 继续保持未启用，业务页面仍手动刷新。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -q
Ran 146 tests OK

cd web/owner-console
npm run guard:readonly
npm run typecheck
OK

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 57，扫描片段 1230，错误：无。

.\scripts\rebuild-rag-index.ps1 -QueryDevContext "P2.44 研发上下文报告 当前状态 下一步 安全边界" -TopK 3 -MaxContextChars 1400
项目文档命中 3，包含 P2.44 已完成、详细回复/持久化分层和 P2.40b 仍需单独批准；记忆命中 0。

未向真实 QQ 会话发送测试消息，避免额外外部副作用。
```

## v1.6 MainAgent explicit development context task command

状态：已落地 P2.43c + P2.43d。目标是把 P2.43b 中唯一注册的只读 work runtime 接到严格的主人私聊 `/agent` 命令，并确认 Owner Console 只读展示 `running` 任务，不扩展任何写能力。

本次完成：

```text
src/plugins/ai_chat/owner_agent_work_runtime.py：
  新增严格命令解析：执行研发上下文任务：<query>（支持中英文冒号）。
  裸命令返回空 query；旧 /agent 任务 <目标> 和普通 /agent 查询不会匹配。
  新增安全结果渲染：只展示 task id、状态、受限报告摘要和任务详情入口。

src/plugins/ai_chat/owner_runtime_factory.py：
  新增 execute_development_context_report(event, query)，固定调用唯一注册的 development_context_report。

src/plugins/ai_chat/__init__.py：
  既有 /agent handler 在静态回复、旧任务命令和 MainAgent/LLM 路径之前检查显式研发上下文任务命令。
  强制 PrivateMessageEvent 与 is_owner(config, event)，不受 main_agent_allow_group 放宽影响。
  /agent-debug 不执行这个任务；一次命令只由既有 matcher 返回一次结果，不发送额外 QQ 消息。
  更新 /agent 帮助、状态和边界文字。

src/plugins/ai_chat/owner_console_read_runtime.py：
  running 任务的只读 next_action 为 monitor_running_task。
  既有 GET task list/detail 和 status=running 筛选可展示 created / work_claimed / work_started。
  不新增 Web 写 endpoint、执行、取消或重试按钮。
```

边界：

```text
只允许主人私聊显式 /agent 执行研发上下文任务：<问题>。
普通聊天、群聊、非主人私聊、/agent-debug、旧 /agent 任务 <目标> 和 MainAgent LLM 都不能触发该 runtime。
不新增审批、approval resume、后台 worker、队列、timer、自动 retry、shell、任意文件写入、未注册数据库写入、Web 写操作或额外 QQ 发送。
P2.40b 不因命令可用而自动开启；业务页面继续手动刷新，等待实际工作负载单独决定。
```

验证：

```text
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units -v
Ran 89 tests OK

.\.venv\Scripts\python.exe -m unittest tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 125 tests OK

未向真实 QQ 会话发送测试消息，避免额外外部副作用。
```

## v1.6 MainAgent read-only work runtime registration

状态：已落地 P2.43b。目标是在 P2.43a 的状态机和持久化边界之上，提供唯一已注册的只读 work type 及 factory 注入，但不开放 QQ 或 Web 执行入口。

本次完成：

```text
新增 src/plugins/ai_chat/owner_agent_work_runtime.py：
  OwnerAgentWorkContext、AgentWorkSpec、OwnerAgentWorkRuntime 和 OwnerAgentWorkExecution。
  registry 固定只包含 development_context_report：read_local、query 参数、无需审批、结果上限 1600。
  execute 先验证 work type 与 query，再创建 pending task、claim 为 running、调用注入执行器、写入 done / failed。
  无效 query 或未注册 work type 不创建任务。
  DevContextGraph 原始输出只解析项目文档/开发侧记忆命中计数；task.result 和事件不持久化 RAG 片段、路径或异常原文。

src/plugins/ai_chat/owner_runtime_factory.py：
  新增 work_runtime(event)，只将 OwnerAgentContext 和 event-bound development_context_report executor 注入 runtime。

src/plugins/ai_chat/__init__.py：
  新增受 factory 注入的 run_development_context_report_for_event callback。
  callback 只调用现有 DevContextGraph 并返回命中计数，不返回原始 RAG 内容。
  未新增 /agent 命令、普通聊天入口或 Web endpoint。

tests/test_owner_agent_work_runtime.py：
  覆盖唯一 registry、成功持久化安全摘要、无效/未注册输入不建任务、失败不泄漏异常文本。
```

边界：

```text
不新增 QQ 命令，不从普通聊天调用 runtime，不让 MainAgent LLM 选择或指定 work type。
不新增后台 worker、队列、timer、自动 retry、shell、任意文件写入、未注册数据库写入、额外 QQ 发送或 Web 写操作。
不改变审批创建、确认、拒绝、approval_resume_enabled 或 owner_write_runtime。
Web Owner Console 仍只有 GET read model；P2.40b 仍等待 P2.43c 的真实 running 任务生命周期。
```

验证：

```text
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_persistence_units -v
Ran 78 tests OK
```

## v1.6 MainAgent read-only work task persistence foundation

状态：已落地 P2.43a。目标是把 P2.43 的第一个正式只读工作任务状态机落实到持久化边界，但不接执行器、factory、QQ 命令或 Web 写操作。

本次完成：

```text
src/plugins/ai_chat/agent_tasks.py：
  新增 AGENT_TASK_RUNNING 并纳入任务状态筛选与状态标签。
  新增 claim_agent_task_for_work：scoped pending -> running 条件更新；已有 pending approval 的任务不能被 claim。
  claim 成功后在同一持久化事务写入 work_claimed 和 work_started；重复 claim 不再追加事件。
  新增 complete_agent_task_work / fail_agent_task_work：只允许 running -> done / failed，写入 work_finished / work_failed。
  task.result 限制 1600 characters；query_summary 限制 480 characters；event output/error summary 限制 240 characters。
  cancel_agent_task 改为 scoped status=pending 条件更新，避免取消与 claim 竞争时覆盖 running。

tests/test_persistence_units.py：
  覆盖 scoped claim、重复 claim、已有审批任务兼容、running 不可取消、成功/失败终态和摘要长度限制。
```

边界：

```text
尚未新增 OwnerAgentWorkRuntime、work registry、DevContextGraph executor、factory 注入或 /agent 执行研发上下文任务命令。
没有新 QQ 发送副作用、后台 worker、队列、定时器、自动 retry、shell、任意文件写入、未注册数据库写入或 Web 写操作。
现有审批创建、确认、拒绝和 approval_resume_enabled 恢复链路保持不变。
Web Owner Console 仍然只读；其现有 GET status filter 现在可以安全识别 running，但不新增任何 Web 操作。
P2.40b 仍等待 P2.43c 出现真实 running 任务生命周期后再评估。
```

验证：

```text
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 24 tests OK

.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 35 tests OK

.\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary -v
Ran 60 tests OK
```

## v1.6 MainAgent first read-only work task design

状态：已落地 P2.43 设计。目标是不再把 `agent_tasks` 只当待办记录，而是先定义一个已注册、单步、只读、可审计的正式工作任务闭环；本步只做设计，不实现任务执行。

本次完成：

```text
新增 docs/main-agent-first-readonly-work-task-design.md：
  首个 work_type 固定为 development_context_report（研发上下文报告）。
  只允许主人私聊显式 /agent 执行研发上下文任务：<query> 入口。
  复用 DevContextGraph / dev_context 的只读依赖，不让 MainAgent LLM 自由选择工具。
  旧 /agent 任务 <目标> 继续只创建待办，不自动执行。

定义首个执行链路：
  validate -> create pending -> atomic claim running -> work_started
  -> registered read-only executor -> work_finished / work_failed
  -> bounded task.result 和 event summary。

定义状态和兼容策略：
  P2.43 实现时新增 running。
  首个只读任务使用 pending -> running -> done / failed，或 pending -> cancelled。
  既有审批任务继续使用现有 pending / approval status，不在本步引入 waiting_approval。
  running 任务不支持现有取消命令中断；失败后不自动 retry。

定义边界：
  不引入后台 worker、队列、定时器或独立进程。
  不新增 shell、文件写入、未注册数据库写入、额外 QQ 发送或 Web 写操作。
  不从 work runtime 调用 owner_write_runtime。
  不扩展 approval_resume_enabled。
  任务结果、事件输入和错误均需受限保存，不能持久化完整 RAG 原文、traceback 或敏感配置。

更新 Owner Console 路线：
  P2.40b 业务页面低频刷新延后到 P2.43c 有真实 running 任务生命周期之后再评估。
```

边界：

```text
本次只新增设计文档和路线记录，不修改 Python 或前端运行时代码。
当前没有正式 work runtime，没有新的 /agent 执行命令。
任务列表、审批和 Diagnostics 继续保持首次加载与手动刷新。
Web Owner Console v0 继续只读。
普通聊天继续不触发 MainAgent。
ProjectDocRAG 继续只在显式 /agent dev_context 中使用。
```

验证：

```text
文档设计变更，无运行时代码改动。
通过 DevContextGraph 查询现有 agent_tasks / approvals / owner runtime 基线后完成设计。
```

## v1.6 Web Owner Console controlled auto-refresh foundation

状态：已落地 P2.40a。目标是先实现自动刷新的受控基础设施和 AppShell health 低频检查，验证 timer、页面可见性、失败暂停和 AbortController 生命周期；本步不接业务页面轮询。

本次完成：

```text
新增 web/owner-console/src/hooks/useControlledAutoRefresh.ts：
  使用请求完成后再 setTimeout 的 completion-based 调度。
  不使用 setInterval。
  页面 hidden 时清 timer 并 abort 自动请求。
  页面恢复 visible 时，过期请求最多延迟 1 秒补一次。
  同一资源不并发、不积压 tick。
  手动刷新开始前暂停 timer，结束后再恢复调度。
  自动请求执行期间拒绝并发手动刷新。
  transient 失败按正常周期重试，连续 3 次后暂停。
  terminal 失败立即暂停。
  手动成功可以清失败状态并恢复调度。

新增 AutoRefreshContext / AutoRefreshControl / ownerConsoleRefreshPolicy：
  AppShell 内存态开关默认 false。
  浏览器完整刷新后恢复关闭。
  不写 localStorage、sessionStorage、cookie 或数据库。
  AppShell 开启后每 60 秒检查 GET /healthz。
  routes contract 不周期读取。
  顶部“最后刷新”调整为语义更准确的“连接检查”。

新增前端生命周期测试：
  Vitest + jsdom + @testing-library/react renderHook。
  覆盖默认关闭、周期调度、慢请求不重叠、hidden 暂停、visible 补一次、连续失败暂停、terminal 失败、手动恢复、隐藏/关闭 abort 和错误分类。

扩展 readonly guard：
  timer 和 visibility API 只能出现在受控 hook，测试文件除外。
  第一版禁止 setInterval。
  业务组件不能自行创建 timer 或监听 visibilitychange。

本地启动兼容修复：
  start-owner-console.ps1 在后台 Start-Process 前规范化当前进程 Path 环境项。
  避免部分启动环境同时携带 Path / PATH 时触发 duplicate-key 异常。
  后台启动由固定等待 2 秒改为最多等待 10 秒，并在进程提前退出时立即失败。
  避免冷启动超过 2 秒时被误报为启动失败。
  Path 值本身保持不变，不改变端口、launcher、日志或静态模式行为。
```

边界：

```text
Dashboard、Tasks、Approvals、Task Detail、Approval Detail 尚未接周期刷新。
Diagnostics、Memory、Access Control、Settings 继续手动刷新。
不新增后端 API，不修改 FastAPI app。
所有自动请求继续经过 ownerConsoleApi GET allowlist。
不新增 POST / PUT / PATCH / DELETE。
不新增登录/鉴权或 Web 写操作。
不触发 MainAgent、ProjectDocRAG、MemoryRAG 检索或 QQ 发送。
不开放 /docs、/redoc、/openapi.json。
```

验证：

```text
npm run guard:readonly
Owner Console frontend read-only guard passed.
Checked 24 TypeScript source files.

npm test
Test Files 1 passed
Tests 12 passed

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities
```

## v1.6 Web Owner Console read-only auto-refresh design

状态：已落地 P2.40 设计。目标是在 Web Owner Console 本地静态模式可用后，先定义低频、可控、页面可见时才运行的只读自动刷新策略，不直接实现轮询，也不引入 WebSocket / SSE。

本次完成：

```text
新增 docs/web-owner-console-readonly-auto-refresh-design.md：
  默认关闭自动刷新，用户显式开启后只在 AppShell 内存生命周期内生效。
  页面完整刷新后恢复关闭，不写 localStorage、sessionStorage、cookie 或数据库。
  页面隐藏时停止 timer 并取消自动请求，恢复可见时最多补一次。
  同一资源不允许并发或重叠请求。
  自动失败不立即重试；连续 3 次网络/5xx 失败后暂停。
  400 / 403 / 404 / contract mismatch 立即暂停自动刷新。
  手动刷新继续保留，手动成功后可以恢复调度。

定义页面策略：
  AppShell health 60 秒。
  Dashboard overview、Tasks / Task Detail、Approvals / Approval Detail 在 P2.43c 有真实 running 任务前均保持手动。
  届时如接入，业务页面候选周期为 60-120 秒；diagnostics 保持手动。
  Diagnostics / Memory / Access Control / Settings 保持手动。
  routes contract 只在首次加载和手动刷新时读取。

定义后续实现边界：
  使用单一 useControlledAutoRefresh hook。
  推荐请求完成后再 setTimeout，不使用固定节拍 setInterval。
  readonly guard 后续限制 timer 和 visibility API 只能出现在受控 hook。
  自动刷新仍只调用现有 ownerConsoleApi GET allowlist。
  不新增后端 endpoint、WebSocket、SSE、TanStack Query 或全局状态库。

同步文档：
  修正 local deployment design 中“不新增启动脚本”的过期描述。
  将 v0 runbook 的后端 contract 基线从 20 项更新为 22 项。
  更新 frontend stack、UI layout、readonly audit、contract guard、local deployment、runbook 和 frontend README。
```

边界：

```text
本次只做设计，不修改 web/owner-console/src 运行时代码。
当前自动刷新仍默认不存在，不产生周期请求。
不新增后端 API，不修改 FastAPI app。
不新增 POST / PUT / PATCH / DELETE。
不新增登录/鉴权。
不开放审批确认、拒绝或恢复执行。
不开放 /docs、/redoc、/openapi.json。
不改变 QQ / NoneBot / /agent 行为。
ProjectDocRAG 仍只允许在显式 /agent dev_context 中使用。
Web Owner Console v0 继续只读。
```

验证：

```text
设计前重新执行 Owner Console 后端 HTTP contract：
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 22 tests OK

本次无运行时代码改动，后续 P2.40a 实现时再增加 timer / visibility 生命周期测试并执行前端 guard、typecheck、build 和 audit。
```

## v1.6 Web Owner Console local start scripts

状态：已落地 P2.39b。目标是让 Web Owner Console 本地静态模式可以一键后台启动和停止，避免日常使用时每次手动输入 uvicorn 环境变量和启动命令。

本次完成：

```text
新增 scripts/start-owner-console.ps1：
  默认以本地静态模式后台隐藏启动 FastAPI。
  默认访问 http://127.0.0.1:8090/owner-console。
  检查 .venv\Scripts\python.exe 是否存在。
  检查 8090 是否已被占用。
  如果已存在 Owner Console 进程，直接提示已运行，不重复启动。
  如果端口被其他进程占用，拒绝启动并显示进程信息。
  检查 web/owner-console/dist/index.html 是否存在。
  支持 -Build 在缺少 dist 时先执行 npm run build。
  支持 -Foreground 前台调试。
  支持 -CheckOnly 做启动预检。
  输出日志到 logs/owner-console.out.log 和 logs/owner-console.err.log。

新增 scripts/stop-owner-console.ps1：
  只查找 python owner_console_fastapi_launcher:app 且匹配指定端口的进程。
  默认停止 8090 上的 Owner Console。
  支持 -Force 强制停止。
  不按端口杀无关进程。

更新文档：
  web/owner-console/README.md 增加一键启动/停止命令。
  docs/web-owner-console-v0-runbook.md 增加脚本用法、日志路径、前台调试方式和 -Build 说明。
  docs/web-owner-console-local-deployment-design.md 和 docs/web-owner-console-frontend-stack-design.md 标记 P2.39b 已完成。
```

边界：

```text
不新增后端 API。
不新增 Web 写操作。
不新增登录/鉴权。
不新增开机自启。
不注册 Windows Service。
不改变 QQ / NoneBot / /agent 行为。
脚本只服务本地 Owner Console 静态模式。
```

验证：

```text
PowerShell Parser ParseFile scripts/start-owner-console.ps1
OK

PowerShell Parser ParseFile scripts/stop-owner-console.ps1
OK

.\scripts\start-owner-console.ps1 -CheckOnly
Owner Console start preflight OK.

npm run guard:readonly
Owner Console frontend read-only guard passed.

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 22 tests OK
```

## v1.6 Web Owner Console optional local static mode

状态：已落地 P2.39a。目标是按 P2.39 设计实现可选本地静态模式，让 FastAPI 在显式开关打开时服务 `web/owner-console/dist`，同时继续保持 API 路径、页面路径和只读边界隔离。

本次完成：

```text
更新 web/owner-console/vite.config.ts：
  设置 Vite build base=/owner-console/。
  build 后资源路径变为 /owner-console/assets/...。

更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  新增 OWNER_CONSOLE_STATIC_ENABLED 开关，默认 false。
  新增 OWNER_CONSOLE_STATIC_DIR，默认 web/owner-console/dist。
  静态模式开启时，/owner-console 和 /owner-console/* 返回前端页面。
  /owner-console/assets/{file} 返回真实静态资源。
  缺失 assets 返回 404，不 fallback 到 index.html。
  /api/v1/owner-console/* 仍然只承载 JSON API。
  /docs、/redoc、/openapi.json 仍然关闭。
  静态模式开启但 index.html 不存在时拒绝创建 app。

更新测试：
  默认静态模式关闭时 /owner-console 仍是 404。
  静态模式开启时 /owner-console、/owner-console/tasks/1、/owner-console/approvals/1 返回 text/html。
  静态资源存在时返回资源，缺失时 404。
  POST /owner-console/tasks 返回 405。
  API route、POST API 405、docs/redoc/openapi 404 均不受静态 fallback 影响。
  launcher 测试显式关闭静态模式，避免本机环境变量干扰 smoke。

更新 .env.example 和 config/.env.example：
  增加 OWNER_CONSOLE_STATIC_ENABLED=false。
  增加 OWNER_CONSOLE_STATIC_DIR=web/owner-console/dist。

更新文档：
  docs/web-owner-console-local-deployment-design.md 标记 P2.39a 已实现。
  docs/web-owner-console-v0-runbook.md 增加本地静态模式启动方式。
  web/owner-console/README.md 增加静态模式命令。
  docs/web-owner-console-frontend-stack-design.md 追加 P2.39a 实现状态。
```

边界：

```text
不提交 dist 构建产物。
不新增 API endpoint。
不新增 POST/PUT/PATCH/DELETE。
不新增登录/鉴权。
不新增审批确认/拒绝页面。
不改变 QQ / NoneBot / /agent 行为。
不开放 /docs、/redoc、/openapi.json。
Web Owner Console v0 仍然只读。
```

验证：

```text
npm run guard:readonly
Owner Console frontend read-only guard passed.

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 22 tests OK
```

## v1.6 Web Owner Console local deployment design

状态：已落地 P2.39 设计。目标是先把 Web Owner Console 的本地部署形态、路径隔离、静态页面 fallback、docs/openapi 边界和只读 allowlist 说清楚，后续再决定是否实现 FastAPI 挂载 dist。

本次完成：

```text
新增 docs/web-owner-console-local-deployment-design.md：
  定义开发模式：FastAPI 8090 + Vite 5173 + Vite proxy。
  定义本地静态模式：FastAPI 可选挂载 web/owner-console/dist 到 /owner-console。
  明确 /api/v1/owner-console 只承载 JSON API。
  明确 /owner-console 只承载前端页面。
  明确 /owner-console/* 客户端路由刷新时 fallback 到 index.html。
  明确 /api/v1/owner-console/*、/docs、/redoc、/openapi.json 不 fallback 到 index.html。
  明确 /docs、/redoc、/openapi.json 继续关闭。
  明确静态页面当前仍只能调用 GET allowlist。
  补充实现优化和防偏建议：fallback 只服务 /owner-console，不做 API fallback，不做敏感配置注入。
  记录未来实现步骤和测试清单。

更新 docs/web-owner-console-v0-runbook.md：
  增加 P2.39 设计文档引用。
  调整后续路线为 P2.39a 静态模式实现、P2.40 只读自动刷新、P2.41 访问保护、P2.42 Web 审批操作。

更新 docs/web-owner-console-frontend-stack-design.md：
  追加 P2.39 本地部署方式设计状态。

新增 docs/juejin/15-web-owner-console-local-deployment-design.md：
  生成稀土掘金文章，说明为什么本地 Web 控制台要先设计部署边界、路径隔离、SPA fallback 和 GET allowlist。
```

边界：

```text
不修改 FastAPI app。
不修改 Vite 配置。
不生成或提交 dist。
不新增接口。
不新增前端写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot / /agent 行为。
```

验证：

```text
文档更新，无运行时代码改动。
```

## v1.6 Web Owner Console v0 runbook

状态：已落地 P2.38。目标是把 Web Owner Console v0 的后端启动、前端启动、页面验收、只读边界、自动化验证和常见问题整理成一份本地使用手册，方便后续继续做部署、鉴权或审批操作前有稳定基线。

本次完成：

```text
新增 docs/web-owner-console-v0-runbook.md：
  记录 Web Owner Console v0 定位。
  记录当前页面和详情页范围。
  记录后端 FastAPI launcher 启动方式。
  记录前端 Vite dev server 启动方式。
  记录页面手动验收顺序。
  记录 guard/typecheck/build/audit 和后端 HTTP contract 验证组合。
  记录只读边界和禁止加入的写入口。
  记录 backend disconnected、403、404、/docs 404、5173 端口占用等常见排障。

更新 web/owner-console/README.md：
  增加完整 runbook 引用。
```

边界：

```text
不修改 FastAPI 代码。
不修改 React 代码。
不新增接口。
不新增前端写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot / /agent 行为。
```

验证：

```text
文档更新，无运行时代码改动。
P2.37 提交前已通过：
  npm run guard:readonly
  npm run typecheck
  npm run build
  npm audit
  owner console 后端 HTTP contract 20 tests OK
```

## v1.6 Web Owner Console frontend contract guard

状态：已落地 P2.37。目标是把 P2.36 的人工前端只读审计固化成本地自动检查，避免后续新增页面或 API client 时无意间扩大 Web Owner Console v0 的能力边界。

本次完成：

```text
新增 web/owner-console/scripts/readonly-guard.mjs：
  检查 fetch() 只出现在 ownerConsoleApi.ts。
  检查 HTTP method 只允许 GET。
  检查源码不引用 /openapi、/docs、/redoc。
  检查源码不出现 approveApproval / rejectApproval / resumeApproval 等写操作风格 API 名称。
  检查 ownerConsoleApi.ts 保留当前只读 allowlist。
  检查任务详情 / 审批详情动态路径仍使用正整数 ID 校验。
  检查主导航页面路由仍全部存在。
  检查 PlaceholderPage 没有被重新引入。

更新 web/owner-console/package.json：
  新增 npm run guard:readonly。

更新 web/owner-console/README.md：
  更新当前已接入的只读端点列表。
  增加 guard:readonly 检查命令。

新增 docs/web-owner-console-frontend-contract-guard.md：
  记录 guard 定位、命令、检查项、禁止项、验证组合和后续路线。

更新 docs/web-owner-console-frontend-readonly-audit.md：
  将人工审计命令升级为包含 npm run guard:readonly。
  标记 P2.37 guard 已落地。

更新前端栈和 UI 布局设计文档的后续实现状态。
```

边界：

```text
不新增后端接口。
不新增前端写能力。
不新增登录/鉴权。
不修改 FastAPI 运行时代码。
不触发 MainAgent。
不改变 QQ / /agent 行为。
guard 只是前端静态边界检查，不替代后端 HTTP contract 测试。
```

测试：

```text
npm run guard:readonly
Owner Console frontend read-only guard passed.

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

## MainAgent external-read：Tavily 配置与 executor 装配

状态：生产条件接线已打开，认证 executor 和主人 QQ strict command live 均已完成。

本次完成：
```text
新增 TAVILY_API_KEY（配置 repr 脱敏）和 TAVILY_TIMEOUT_SECONDS=10。
现有 OpenAI/Main/Chat API Key 同步改为不进入配置 repr。
新增未注册的 create_tavily_external_read_executor 装配 factory。
固定把 ExternalSearchExecution 映射为 ExternalReadReportPayload。
成功和无结果均保持 external_request_count=1；无二次请求、retry 或 fallback。
fake transport 集成测试验证 Basic 固定参数、最多 3 条、关闭 answer/raw content/images。
测试验证 Key、raw_content、完整 URL 不进入临时 report。
为内部 AutoBackend 路径声明 httpx 0.28.x / httpcore 1.0.x 兼容窗口。
最新定向配置/Tavily/QQ 边界/MainAgent bridge 92 tests OK。
全量回归 465 tests OK；115 个 Python 文件 AST/尾随空白检查通过；git diff --check 通过。
生产 OwnerRuntimeFactory 已增加延迟、条件接线：默认关闭时不导入 Tavily HTTP 模块。
开关 true 但 Key/超时非法或 Tavily 依赖导入失败时失败关闭，不创建任务或网络请求。
TAVILY_TIMEOUT_SECONDS 非数字时配置加载为安全哨兵 0，Bot 可启动但 executor 保持未配置。
普通聊天和 Main LLM ToolRegistry 仍无 external-read 工具。
```

生产边界：
```text
ENABLE_AGENT_WEB 已由主人明确批准在本地 .env 打开。
真实 TAVILY_API_KEY 仅存在于被 Git 忽略的本地 .env；示例文件继续为空。
插件入口只在 ENABLE_AGENT_WEB=true 时延迟导入并条件注入 Tavily executor。
普通聊天和 Main LLM ToolRegistry 不可触发。
已按主人预算发起唯一一次 Tavily Basic 认证请求：3 条结果、3 个来源、0 丢弃、external_request_count=1。
认证 harness 与随后主人 QQ live 是两个独立 operation；每个 operation 均为一次请求，无自动 retry、fallback 或来源页抓取；未 commit 或 push。
tracked files 和 Bot 日志均未发现真实 Key 或 Authorization header。
主人随后反馈 QQ live 能够成功发送；正式 external-read 任务 #43 为 done。
任务 #43 事件链为 created、work_claimed、work_started、work_finished。
持久化 goal/event input 使用固定原文未持久化占位，只保存 provider、请求数和状态等安全元数据；未发现 URL、Bearer 或 Key 前缀。
```

## MainAgent external-read：QQ live 后结果质量优化

状态：已落地，未新增联网请求。

```text
新增保守来源类型：中国政府域名、已识别的官方文档域名、中央媒体域名、一般公开来源。
域名匹配使用 host/subdomain 边界，docs.python.org.evil.example 不会被标为官方文档。
时间敏感 query 增加临时核验提示；缺失 published_at 明确显示未提供。
QQ 结果改为标题、类型、来源、时间、摘要分层格式，继续不展示完整 URL。
Tavily content 额外清理反引号和 ¶，仍固定最多 360 字符。
request_timeout、provider_unavailable、response_too_large、invalid response 和 sanitizer 等错误改为中文安全回复。
新增 /agent 联网状态：仅主人私聊、纯本地、不请求 Tavily、不消耗 credit。
ChatAgent、普通聊天、角色卡、情感表达、Main LLM external-read 可见性均未改变。
定向 external-search/Tavily/work/QQ 边界 59 tests OK；MainAgent/config 80 tests OK。
全量回归 469 tests OK。
```

## MainAgent external-read：个人信息、日期与 provider 错误收口

状态：已落地，未新增 Tavily 请求。

```text
Query policy 新增邮箱、明确手机号/电话、QQ号和身份证号拒绝。
保留 RFC 9110、CVE-2026-12345 和无标签产品编号，避免宽泛长数字误伤。
published_at 只接受有效 ISO 类日期并规范为 YYYY-MM-DD；无效日期不展示。
发布日期字段加入提示注入检测，命中时整条外部结果中和。
Tavily 401/403 -> authentication_failed；429 -> rate_limited；503 等 -> provider_unavailable。
鉴权失败和限流分别使用中文安全回复，不记录 response body 或原始异常。
/agent 联网状态新增 httpx/httpcore 实际版本和已验证兼容范围判断；状态查询仍不联网。
ChatAgent、普通聊天、角色卡、情感表达和 Main LLM external-read 可见性未改变。
定向 security/search/Tavily/work/QQ 边界 74 tests OK。
全量回归 473 tests OK。
```

## MainAgent external-read：Unicode 注入与最近任务安全快照

状态：已落地，未新增 Tavily 请求。

```text
外部可见文本新增 Unicode NFKC 规范化。
提示注入检测新增 compact 检测副本，覆盖全角英文、拆分空白、零宽字符、有限标点、双向字符和 HTML 标签分段。
新增 external_read_status 纯只读模块，SQLite mode=ro、当前 session/user、固定任务标题、limit 1。
最近任务只展示 ID、白名单状态、provider、安全计数、类别和合法 ISO 更新时间。
数据库任意 status/updated_at 污染文本不会回显；缺失或损坏时安全显示无可用元数据。
/agent 联网状态不读取 query、goal、事件正文或结果详情，不访问 Tavily、不消耗 credit。
ChatAgent、普通聊天、角色卡、情感表达和 Main LLM external-read 可见性未改变。
定向 external-search/status/QQ/work 60 tests OK。
全量回归 479 tests OK。
主人随后在 QQ live 验证 /agent 联网状态成功；本地兼容性与最近正式任务安全快照已加载生效。
该状态命令未发起 Tavily 请求，不消耗 credit；主人未提供新的 external-read 任务 ID，因此不臆造编号。
```

## Owner Console：external-read 只读观测页

状态：已落地，未新增 Tavily 请求或 Web 写操作。

```text
新增 GET /api/v1/owner-console/external-read，并纳入统一 HTTP/read-model 路由契约。
新增独立“联网查询”页面、侧栏入口和 Dashboard 摘要卡片。
页面展示 Tavily Basic、本地开关、凭据存在性、executor 就绪状态、timeout、httpx/httpcore 兼容性和最近正式任务安全元数据。
接口不返回 Key、query、goal、标题、摘要、完整 URL、事件正文、原始响应或原始异常。
接口通过 SQLite mode=ro 按当前主人 session/user 和固定任务标题读取最近任务，不执行实时 Tavily probe，不消耗 credit。
安全边界明确显示 Main LLM/普通聊天/任意 URL/retry/fallback/AI answer/raw content/images 均未开放。
修复正式 work 持久化把换行压为空格后，最近任务安全元数据无法解析的问题；解析仍只接受 provider、计数、状态类别、错误类别和合法时间白名单。
Owner Console 继续只有 GET；/docs、/redoc、/openapi.json 继续关闭；web/owner-console/dist 继续不提交。
全量回归 481 tests OK；Python AST 116 files OK。
前端生产构建、GET-only guard、12 tests 和 git diff --check 通过。
受当前会话浏览器控制接口缺失影响，本轮未完成真实浏览器视觉点击验收；生产构建和路由/组件契约已验证。
```

## Owner Console：任务 work type 标签与筛选

状态：已落地，未新增外部请求或 Web 写操作。

```text
OwnerConsoleTaskRow 新增 work_type，OwnerConsoleTaskList 新增 work_type_filter。
只展示 development_context_report、system_diagnostics_report、external_read_report 三个正式只读 work type。
未知、污染或未注册的事件 tool_name 不作为类型标签回显。
GET /api/v1/owner-console/tasks 新增可选 work_type 参数，并严格拒绝白名单外值。
数据库查询通过 agent_task_events 的 work_claimed 精确 EXISTS 条件先筛选再 LIMIT，避免较旧联网任务被较新普通任务挤出。
前端任务页增加研发上下文、系统诊断、联网查询类型筛选和类型 badge；任务详情摘要同步展示安全 work type。
筛选只读取本地 SQLite，不访问 Tavily、不消耗 credit。
全量回归 482 tests OK；Python AST 116 files OK。
前端生产构建、GET-only guard、12 tests 和 git diff --check 通过。
```

## ChatAgent：本地日期、星期和时间

状态：已落地，已改为 ChatAgent 角色化表达，尚待主人 QQ live 验收。

```text
新增 BOT_TIMEZONE，第一版只允许 Asia/Shanghai，默认无需修改现有 .env。
当前 Windows Python 环境缺少 IANA tzdata，因此采用等价的固定中国标准时间 UTC+8，不新增依赖或网络下载。
新增纯本地 LocalTimeSnapshot、显式意图解析、可信 Prompt 上下文和确定性回退格式化。
支持今天星期几/周几/礼拜几、今天几号/几月几日、日期+星期、现在几点、当前年份。
明确时间问题在 generate_chat_text_response 内生成可信本地事实，并把 system context 追加到本轮 history 副本后正常调用 ChatAgent；当前角色卡负责自然表达。
原 ChatPromptContext history 不被修改，内部时间事实不作为用户文本、聊天历史或 RAG 内容持久化。
模型回复按 intent 校验正确日期、星期、年份或小时分钟；错误值、冲突值、空回复或超长回复统一回退到确定性答案。
Chat LLM 调用异常时记录既有安全错误并直接使用本地回退，不把简单日期问题变成 AI 调用失败提示。
日期能力调用现有 Chat LLM，但不调用 MainAgent、Tavily、MemoryRAG 或 ProjectDocRAG，不消耗 Tavily credit；远程 Chat LLM 不增加本地 GPU 显存。
每条命中消息只读取一次时钟，先转换为 Asia/Shanghai，再从同一不可变快照生成日期和星期。
命令消息、明天星期几、指定历史日期和更宽泛的自然问题不被第一版误拦截。
无效时区配置和 naive 测试时钟明确失败，不静默使用系统时区。
全量回归 490 tests OK；Python AST 118 files OK；git diff --check 通过。
```

## ChatAgent：爱可角色卡表达与外观补充

状态：已落地，尚待主人 QQ live 验收。

```text
当前 active role card 仍为 aike，没有修改 MainAgent、系统提示或其他角色卡。
外观新增：身高约 155 厘米、胸围约 B 罩杯，保留经典黑白女仆装和 18 岁既有设定。
主人和非主人普通回复默认写得稍长，通常使用 2 到 3 句；明确极简、详细格式或安全边界时可按请求调整。
普通回复至少包含一处中文圆括号动作或内心描述。
括号内凡指代角色自身，只能使用“爱可”或“爱可的”，禁止“我”“我的”“我们”等第一人称代词。
括号外对白继续按主人/非主人模式使用既有称谓、自称、结巴和距离感规则。
主人和非主人全部示例已同步改写，避免旧的一句式、无动作示例覆盖新规则。
新增角色卡合同测试，扫描外观、句数规则、括号自称和所有示例动作描述。
MainAgent 继续保持中性、无角色身份、无括号动作旁白；本次角色卡修改只影响普通 ChatAgent。
全量回归 493 tests OK；Python AST 119 files OK；git diff --check 通过。
```

## ChatAgent：本地时间自然问法与主人 QQ live 收口

状态：已补丁并通过主人 QQ live，未新增 Tavily 请求或 Agent 任务。

```text
主人首次询问“爱可记得今天几号吗”时，严格整句解析未接受自然前缀和句尾“吗”，因此未注入可信时间，ChatAgent 沿用旧历史回答 2025-05-24 星期六。
补充受限自然问法前缀和吗/嘛，同时继续拒绝假设句、更宽泛问题、明天、历史日期和 /agent 命令。
主人加入开头括号动作后仍未命中；解析器因此增加仅用于意图识别的开头括号动作剥离，最多三个中文或 ASCII 括号段。
完整原始消息仍通过 user_content.for_llm 原样交给 ChatAgent；只有解析副本用于追加可信本地时间 system context。
可信上下文要求忽略历史旧日期，不复述、纠正或比较旧值；只陈述一次本轮事实并继续遵守角色卡。
数据库与运行时证据确认“今天几月几号”此前确实调用 ChatAgent；最终裸日期是候选未通过事实校验后的确定性回退，不是跳过模型。
新增主人原话、ASCII 括号、未闭合括号、非直接问题和真实错误候选 2025-05-24 的回归合同。
定向本地时间 7 tests OK；全量回归 493 tests OK；git diff --check 通过。
修复后主人 QQ live 正确包含 2026-07-13、星期一，并保留“狗修金”称呼、括号动作和完整互动语境。
Bot/NapCat/OneBot 正常，错误日志为空；最新 Agent 任务仍为 #43，没有新增 external-read 或 Tavily 请求。
```

## 主人审核的本地静态表情包库设计

状态：第一版安全设计、A1/A2、动态候选预算、代表帧和 AI 标签建议合同已完成；A3 及以后尚未实现，尚未导入主人图片或发送 QQ 表情包。

```text
新增 docs/local-static-sticker-library-design.md。
真实候选、批准文件、隔离文件、报告和索引建议放在 Git 忽略的 data/stickers 下。
静态候选允许 PNG、JPEG、WebP；动态候选允许 GIF、APNG、动态 WebP；拒绝 SVG、视频、未知格式、路径逃逸和链接。
候选按魔数和真实逐帧解码校验尺寸、像素、帧数、时长与字节预算；A3 主人批准时才生成规范化副本和 SHA-256 固定索引。
运行时只读取 approved 索引；ChatAgent、MainAgent 和用户文本都不能提供文件路径或 URL。
第一阶段仅设计主人显式候选检查、候选预览、批准和已批准预览；普通 ChatAgent 不自动发图。
第二阶段若另行批准，ChatAgent 只提出有限 mood/usage_tag，本地策略映射到已批准 ID；默认关闭、主人私聊限定、每次最多一张、至少 120 秒冷却、失败不 retry。
表情包库不调用 Tavily、浏览器、图片生成、视觉入库、MemoryRAG 或 ProjectDocRAG，不开放 Owner Console 写接口。
QQ 动态、群发、非主人自动发图、主动私聊和自动下载继续延后。
主人已批准并完成动态分析骨架；推荐下一步用少量主人 GIF 做 /表情检查 与 /表情分析 live，校准不确定标签后再做批量审核与 A3，QQ 发送继续延后。
```

## 本地静态表情包库 A1：配置、manifest 与图片校验

状态：已实现并完成本地回归；未创建真实表情包目录、未导入图片、未注册 QQ 命令、未发送图片。

```text
新增默认关闭的 ENABLE_LOCAL_STICKERS，以及 2 MiB、32-2048 像素和 4,194,304 总像素安全预算；无效数字加载为 0，后续校验 fail closed。
固定本地根目录为 Git 忽略的 data/stickers，根目录字段不进入配置 repr；聊天文本不能覆盖路径。
显式声明并验证 Pillow 12.x 依赖窗口。
新增纯本地 sticker_library.py，不依赖 NoneBot、网络、数据库、Tavily、MainAgent 或 LLM。
新增不可变 StickerLimits、StickerImageInfo、StickerAsset、StickerIssue 和 StickerLibrary 数据模型。
manifest 顶层严格验证 schema_version、library_revision、条目数量和 1 MiB 预算；逐条非法 entry 以安全 code 隔离，不扩大读取范围。
批准文件只允许 approved 根目录的单层安全文件名；拒绝路径穿越、绝对路径、子目录和符号链接，并在 resolve 后再次确认文件仍位于固定根目录。
按文件魔数和 Pillow 真实解码验证 PNG、JPEG、静态 WebP；拒绝 GIF、动画 PNG、损坏文件、metadata、尺寸/像素/字节超限和未知格式。
重新计算 SHA-256，并复核 manifest 的 MIME、尺寸和字节数；重复 ID、文件和哈希均拒绝后出现条目。
persona、mood、usage tag、owner_private scope、enabled、带时区 ISO approved_at 和固定 approval_source 均使用白名单验证。
定向 sticker/config 22 tests OK，其中 Windows 当前权限不允许创建测试符号链接而安全跳过 1 项；代码路径仍显式拒绝链接。
全量回归 509 tests OK（skipped=1）；Python AST 575 files OK；pip check 无损坏依赖；git diff --check 通过。
真实 Bot 重启加载成功，8080 正常，NapCat/OneBot 自动重连，错误日志为空。
A1 不加载真实 library、不注册表情命令、不产生 Agent 任务或 Tavily 请求。
A2 候选检查与安全报告随后已完成；本节 A1 边界仍保持不批准、不写索引、不发送 QQ。
```

## 本地静态表情包库 A2：只读候选检查与安全报告

状态：代码与回归已完成，真实开关、inbox 候选和主人 QQ live 尚未执行；未批准、改写或发送图片。

```text
新增 StickerCandidate 和 StickerCandidateReport 不可变模型，以及 inspect_sticker_candidates / format_sticker_candidate_report。
只扫描固定 data/stickers/inbox 的直接子项；缺目录时报告“未自动创建”，不创建目录或文件。
根目录、inbox 和候选文件均拒绝符号链接或 Windows junction；真实 resolve 后必须仍是 inbox 的直接普通文件。
直接子项预算固定为 200；超过时整体拒绝扫描，不继续读取文件。
候选在 2 MiB 预算内先计算 SHA-256，再按 A1 真实图片规则解码；重复内容只允许第一项进入审核。
对外只显示 candidate_<12位短哈希>、短哈希、MIME、尺寸、字节数和安全分类；不显示文件名、绝对路径或完整哈希。
metadata 候选可以读取格式/尺寸但标记为待清理，不可直接进入审核；目录、动画、损坏、未知格式、超预算和链接均拒绝。
报告最多展开 30 项，仍保留总扫描、可审核和拒绝计数。
新增严格固定 QQ 命令 /表情检查，仅主人私聊；总开关关闭时直接提示未开启。
handler 延迟导入 Pillow 校验模块；依赖缺失或安全预算无效时给固定中文安全提示，不泄露原始异常。
该命令不进入普通聊天、ChatAgent 或 MainAgent，不调用 LLM、RAG、Tavily、数据库、Agent 任务或图片发送。
定向 sticker/config 30 tests OK（skipped=2，均为 Windows 当前权限无法创建符号链接测试）。
全量回归 517 tests OK（skipped=2）；Python AST 575 files OK；git diff --check 通过。
Bot 重启成功，8080 正常，NapCat/OneBot 自动重连，错误日志为空。
当前 ENABLE_LOCAL_STICKERS 仍保持默认关闭，data/stickers 未自动创建，因此尚未宣称真实候选或 QQ live 通过。
推荐下一步先由主人决定是否本地启用并准备少量自有候选；A2 live 通过后才进入 A3 批准/规范化写入。
```

## 本地表情包 A2.1-A2.3：动态预算、代表帧与 AI 标签建议

状态：代码与假视觉合同回归完成；尚未导入主人 GIF、调用真实候选视觉分析、写正式标签或发送图片。

```text
候选层新增 GIF、APNG 和动态 WebP 支持；静态批准 loader 继续拒绝 GIF/多帧，A3 尚未开放动态正式资产。
新增动态 5 MiB、120 帧、10 秒、最小 20ms 帧间隔和 60,000,000 总解码像素预算；逐帧真实解码并执行首故障短路。
Pillow 12 不暴露动态 WebP 帧时长，因此新增受限 RIFF/ANMF chunk 解析；块越界、帧数不一致或时长不可用时 fail closed。
候选报告新增静态/动态、帧数和总时长；仍不输出文件名、路径或完整哈希。
新增内存代表帧联系表：最多 6 张，包含首尾、四分位和变化较大帧；输出 PNG bytes，不写临时文件。
新增 sticker_labeling.py 固定 JSON 合同，只允许 moods、soft/medium/strong、动作、兼容场景、三类置信度和 ambiguous。
情绪置信度低于 0.85、强度低于 0.75、场景低于 0.70、mixed 或 ambiguous 自动标记 needs_owner_review。
高置信度只标记 suggested/待主人确认；AI 建议不写 library.json，不成为正式标签。
现有本地 Ollama transport 新增固定 prompt 入口；原聊天视觉事实描述仍经过原 sanitize/truncate 行为，回归保持不变。
新增 candidate_<12位短哈希> 精确解析器；只在固定 inbox 中重新匹配完整 SHA-256，碰撞、替换、路径逃逸或预算失败均拒绝。
新增主人私聊严格命令 /表情分析 <candidate_id>；总开关与视觉开关门控，抽帧和视觉调用放入线程，失败只返回固定中文类别。
/表情分析 不发送图片、不写标签、不批准候选，不调用 ChatAgent、MainAgent、Tavily、RAG、数据库或 Agent 任务。
聚焦 sticker/label/config/vision 65 tests OK（skipped=2，均为 Windows 符号链接权限）。
全量回归 530 tests OK（skipped=2）；Python AST 577 files OK；pip check 和 git diff --check 通过。
Bot 重启成功，8080 正常，NapCat/OneBot 自动重连，错误日志为空。
本轮未调用真实 Ollama 标签分析，避免用合成联系表冒充主人 GIF 分类质量；真实置信度阈值等待主人样本校准。
推荐下一步为少量主人 GIF 的 /表情检查 + /表情分析 live；主人反馈不确定项后再做批量审核页和 A3 正式标签。
```

## 本地表情首批真实分析与主人校准

状态：32 个候选已完成只读安全扫描；首批 6 个完成真实本地视觉分析、主人校准和一次改进后复跑；剩余 26 个完成 AI 人工辅助初判。未写正式标签、未批准候选、未发送 QQ 图片，剩余候选未交给当前模型静默批量分类。

```text
data/stickers/inbox 扫描到 32 个候选：31 个动态 GIF、1 个静态 PNG；全部通过字节、尺寸、帧数、时长和总解码像素预算，没有 rejected candidate。
首批 6 个生成 output/sticker-review/initial-batch.png，只包含 candidate_<短哈希> 和代表帧，不包含源文件名、路径或完整 SHA-256。
第一次本地 Ollama 标签结果置信度普遍偏低，并重复输出 neutral + embarrassed；全部正确路由到 needs_owner_review，没有写 library.json。
人工初步建议经主人校准：第 1 个是“卖萌 / 中等”，不是打哈欠；第 3、4 个属于同一探头/围观场景；第 6 个“撒娇”或“拜托”均符合；第 2、5 及其他建议无需修正。
固定标签白名单补充 curious、expectant、playful、pleading；动作补充 act_cute、exclamation_mark、hands_together、peek、show_heart；场景补充 acting_cute、attention_seeking、checking_reaction、joining_chat、request。
固定 prompt 明确：仅凭张嘴不得判断 yawn；从遮挡物后探头不得自动判断 shy/embarrassed/cover_face；爱心、感叹号、闪亮注视和双手合拢按各自可见证据映射；neutral 不得作为不确定时的默认答案。
改进后复跑第 1、4、6 个方向改善，但第 2、3、5 个仍出现明显误判，且 6 个均因低置信度或 ambiguous 保持 needs_owner_review。当前 3B 模型未通过无人复核批量分类质量门槛。
剩余 26 个不再调用该 Ollama 分类器，而是按最多 6 个一批生成 5 张本地审核图，由 AI 直接查看代表帧完成初步建议。结果保存为 Git 忽略的 output/sticker-review/preliminary-analysis.md。8、18、19、20、22、24、25、26、28 共 9 个物品、原梗或触发语义不清项随后由主人逐一确认：喝奶茶表示观望/“请继续说”，手机拍照表示记录，锤子敲头表示受到打击，灵魂出窍用于震惊，趴倒表示摆烂，伸舌舔用于讨好/撒娇，蛋糕用于生日快乐和分享点心，小本本用于“我记住了”或记仇，握方向盘表示出发。32 个候选现均完成初步语义确认。
固定标签合同继续增加 attentive、hurt、resigned、dizzy，以及 drink_milk_tea、take_photo、get_hit、soul_leave_body、lie_flat、lick、offer_cake、take_notes、drive、offer_gift、sway、type_angrily 和相应受控场景。图片动作和聊天用途分层保存；同一小本本 GIF 可兼容普通倾听/记录和有生气证据时的记仇场景，不把 angry 固化为唯一情绪。
本次真实分析只调用 loopback Ollama，不调用 Tavily、ChatAgent、MainAgent、RAG、数据库或 Agent 任务；未消耗 Tavily credit。
推荐下一步先设计 A3 待审草稿与显式批准流程，或先实现并验证两段式客观描述/受控标签映射。未经主人另行授权，不写正式 manifest、规范化副本，不实现 QQ 预览、自动触发或发送。
全量回归 531 tests OK（skipped=2）；仓库范围 Python AST 135 files OK；pip check 和 git diff --check 通过。
```

## 本地表情包 A3：主人显式批准、规范化与撤销核心

状态：A3 代码、纯本地回归和 32 条主人确认草稿已完成；尚未执行真实主人 QQ 命令、生成 `library.json` 或创建 approved 文件，没有发送表情包。

```text
正式 manifest 升级为 schema v2，新增 source_sha256、animated、frame_count、duration_ms、intensity 和 actions；新批准只写 v2，旧 schema v1 静态库继续只读兼容且不自动迁移。
正式情绪、动作和 usage tag 白名单与主人确认的 32 个候选语义对齐；manifest loader 重新验证最终/来源哈希、动态属性和所有枚举，并拒绝重复来源哈希。
新增纯本地 sticker_approval.py；不依赖 NoneBot、网络、Tavily、数据库、ChatAgent、MainAgent、RAG 或 OneBot sender。
批准草稿固定在 data/stickers/reports/approval-drafts.json；只允许严格 schema、完整源哈希、唯一 candidate/sticker/source、白名单标签、owner_private 和 owner_confirmed=true。
/表情草稿 仅主人私聊只读，只返回草稿 revision、数量、安全 candidate/sticker ID、情绪、强度和场景，不显示完整哈希、路径或源文件名。
/表情批准 candidate_<12位短哈希> <同一短哈希> 仅主人私聊；重新解析固定 inbox 当前文件并匹配草稿完整源 SHA-256，候选替换、错误确认、重复来源和无草稿均 fail closed。
静态候选修正方向、清除 metadata 并统一编码 PNG；GIF/APNG/动态 WebP 逐帧解码后按原动画类型重编码，保留帧时长和 loop 语义。规范化结果再次执行全部格式、metadata、帧数、时长、像素和字节预算。
approved 文件先写同目录唯一临时文件并验证，再原子替换最终文件；manifest 通过 fsync 临时文件和 os.replace 原子更新。manifest 失败时清理本轮新文件，不形成有效条目。
批准成功只返回安全 sticker ID、library revision、静态/动态摘要和最终 12 位撤销短哈希；不发送图片、不自动触发、不启用 ChatAgent 选择。
/表情撤销 sticker_id <最终短哈希> 仅主人私聊；重新验证整个 v2 manifest 后原子递增 revision 并设置 enabled=false。第一版保留规范化文件，不删除、不移动，disabled 条目不可选择。
根据 output/sticker-review/preliminary-analysis.md 和主人逐项确认生成 32 条真实本地草稿，draft schema=1、revision=1、32 个唯一 sticker ID；生成前要求实际 eligible candidate 集合与定义精确相等。一次人工报告短哈希笔误被集合检查拦截并修正，没有模糊匹配。
当前 data/stickers/library.json 和 data/stickers/approved 均不存在，证明本阶段没有把“进入 A3”解释为自动批准。
A3 专项覆盖静态 metadata 清理、GIF 帧数/总时长保留、错误确认零写入、候选替换、manifest 失败清孤立文件、重复批准、草稿校验、输出脱敏、撤销短哈希和 owner-private 命令隔离。
全量回归 542 tests OK（skipped=2，均为 Windows 符号链接权限）。
.env 原本没有 ENABLE_LOCAL_STICKERS；已只补充唯一 ENABLE_LOCAL_STICKERS=true，不显示或改动其他配置，也不进入 Git。Bot 于 2026-07-13 16:24 重启成功，ai_chat 插件加载、127.0.0.1:8080、NapCat/OneBot 重连均正常，stderr 为空。
推荐下一步 QQ 私聊先验收 /表情草稿，再由主人挑一张静态和一张短 GIF 逐项批准，最后选择一项验证撤销。A4 QQ 预览、自动触发和发送继续延后。
```

### A3 QQ live：草稿、两项批准与重复批准提示

```text
/表情草稿 live 返回 draft revision 1、32 条安全 candidate/sticker ID 与主人确认标签；未显示路径、文件名或完整哈希，未发送图片。
主人于 16:56:34 批准 candidate_350e629e52e1，生成 aike_angry_002 静态规范化 PNG；随后于 16:56:58 批准 candidate_1ee215ac7c6e，生成 aike_act_cute_001 动态规范化 GIF。
正式库安全复核：schema 2、revision 2、enabled 2、disabled 0、invalid 0。静态最终短哈希 bc295b1266b1；动态最终短哈希 c82a170dcdbb。
动态源容器报告 6 帧/360ms；规范化 GIF 为 2 帧/360ms。Pillow 合并了连续相同画面，总时长、动画属性和可见变化保持；设计与文档改为记录最终真实帧数，不承诺保留冗余相同帧。
主人于 17:04:57 再次批准同一静态候选，重复 sticker ID/来源规则正确拒绝。原统一失败文本无法区分“已批准”和真正安全失败，因此补充分层安全提示：重复批准明确返回“该候选已经批准，正式库未重复写入”；确认哈希、候选变化、manifest 检查和规范化失败分别返回不同固定类别，不输出原异常。
此前两条撤销尝试分别缺少最终短哈希或使用错误命令/候选哈希，均未改变正式库。正确静态撤销命令为 /表情撤销 aike_angry_002 bc295b1266b1；是否执行由主人决定。
A3 专项 12 tests OK；全量回归 543 tests OK（skipped=2）。
细分错误提示已随 17:19 Bot 重启加载；ai_chat 插件、8080 和 OneBot 重连正常，stderr 为空，正式库仍为 revision 2、enabled 2、invalid 0。
```

## 本地表情包 A4：主人显式 QQ 预览

状态：代码、回归、Bot 重启和主人 QQ 动态 GIF live 均完成；正式库 revision 3、enabled 1、disabled 1，普通聊天自动附带仍关闭。

```text
新增纯本地 sticker_preview.py；严格 sticker ID 解析后重新加载完整 manifest，任何 invalid issue 均使预览 fail closed。
只允许 enabled=true 的正式条目；disabled、未知 ID、非法 ID 均返回固定安全类别，不进入发送和冷却。
发送前再次检查正式文件 SHA-256、MIME、尺寸、字节、metadata、动画属性、帧数与总时长，避免批准后文件被替换。
新增 LOCAL_STICKER_PREVIEW_COOLDOWN_SECONDS，默认 3 秒；无效值加载为 0 并安全关闭预览。
新增主人私聊严格命令 /表情预览 <sticker_id>；只接受一个参数，每条命令只有一次 send_private_msg，使用 MessageSegment.image 发送已复核的正式本地文件。
成功只发送图片，不追加文字。OneBot 失败只记录 sticker_preview_send_failed 固定类别，不记录路径或原始异常；不重试、不改发其他图片、不随机选择。
预览入口不调用 ChatAgent、MainAgent、Tavily、视觉、RAG、数据库或 Agent 任务，不开放群聊、普通聊天或自动附带。
定向 config/preview 13 tests OK；全量回归 549 tests OK（skipped=2）。首次全量失败来自旧 A2/A3 源码审计测试截取范围延伸到新 A4 handler；收紧各自 handler 结束边界后通过，隔离要求未降低。
QQ live 顺序：先 /表情预览 aike_angry_002，确认 disabled 只返回拒绝；再 /表情预览 aike_act_cute_001，确认 QQ/NapCat 实际播放动态 GIF。普通聊天自动触发继续延后。
Bot 于 19:07 重启，ai_chat 插件、8080 和 OneBot 重连正常，stderr 为空；重启后正式库仍为 schema 2、revision 3、enabled 1、disabled 1、invalid 0。
主人于 20:53 执行 /表情预览 aike_act_cute_001；OneBot matcher 单次完成，主人确认 QQ 收到的是第 1 张“卖萌”表情且能够播放动态效果。stderr 为空，没有 retry 或替代发送证据。
预览前后正式库保持 schema 2、revision 3、enabled 1、disabled 1、invalid 0，证明 A4 只读预览没有改写 manifest。A4 enabled 动态主链 live 通过；disabled 拒绝 live 可选补验。
```

## 本地表情包 B1：ChatAgent 有限意图与本地 shadow 选择

状态：代码、回归、shadow 配置和 Bot 重启加载完成，自动附件关闭；尚待主人 QQ shadow 样本校准。

```text
新增 sticker_intent.py 固定合同。ChatAgent 正常可见回复结束后只能追加一次末尾标记，字段限定 attach、mood、intensity、scene、confidence；不能选择 sticker ID、文件名、路径或 URL。
控制标记在本地时间事实校验、QQ 发送、TTS 候选、stored_assistant、聊天历史和 RAG 之前解析并剥离。marker 缺失保持原回复；非法 JSON、未知枚举、额外字段、错误置信度、非末尾或残缺标记均丢弃意图并截断控制区域，绝不进入可见/持久化文本。
ask_llm 新增可选 extra_system_context，不增加第二次 LLM 调用；只有 ENABLE_CHAT_STICKER_INTENT_SHADOW=true 时注入固定意图合同。附件开关不赋予模型额外能力。
ChatRuntimeResult 新增可选 StickerIntent，并在 legacy/graph/semantic voice 包装中传递；现有构造保持默认兼容。
新增 sticker_selection.py 纯本地策略：owner-private、回复非空、confidence>=0.82、正式库无 invalid、persona/scope/enabled 和 mood/intensity/scene 精确匹配。
频率为确定性硬门控：120 秒冷却、至少 4 条消息间隔、每小时最多 6 张、每回复最多 1 张。无概率随机触发；同类多候选使用 shuffle-bag，袋内用完前不重复。
选择和发送分成 decide/commit_sent；只有未来 OneBot 图片发送成功后才提交冷却、小时计数和袋消费。B1 shadow 只 decide，不 commit，不发送。
新增 /表情意图状态 主人私聊只读命令，仅显示 marker 状态、有限意图、置信度、本地决策原因、匹配数量和安全 sticker ID；不保存或显示用户原文、回复正文、路径、哈希或文件名。
.env 已设置 ENABLE_CHAT_STICKER_INTENT_SHADOW=true 与 ENABLE_CHAT_STICKER_ATTACHMENTS=false，均唯一；普通聊天仍没有 MessageSegment.image 或 send_private_msg 接入。
意图/config/选择定向 20 tests OK；全量回归 562 tests OK（skipped=2）；Python AST 143 files OK；pip check 和 git diff --check 通过。
推荐 QQ shadow live：先普通事实问题后查 /表情意图状态，确认不建议/不匹配且无图片；再发“爱可卖个萌给我看看”后查状态，观察是否为 playful/medium/acting_cute 并 shadow 选中 aike_act_cute_001。两轮均不得发图。
Bot 于 21:33 重启，ai_chat 插件、8080 和 OneBot 重连正常，stderr 为空；shadow=true、attachments=false 均为唯一有效配置。

主人首轮 QQ shadow 依次发送“爱可记得今天几号吗”和“爱可给我卖萌”。两次文本均正常回复且没有图片，但 `/表情意图状态` 都显示 `marker_absent / intent_absent`。21:41 与 21:57 日志确认消息进入同一普通聊天 matcher 且正常完成，stderr 为空。
使用完整正式 ChatAgent prompt 的无隐私最小探针复现 marker 缺失；简短独立 prompt 可以输出 marker，说明不是解析器、开关、QQ handler 或 DeepSeek 完全不支持该字符格式，而是完整系统/基础/角色组合下的输出合同不稳定。将 system 消息简单合并仍有缺失或错误标签，不能作为修复。
当前 DeepSeek 接口 3/3 支持 `json_object`，但 `json_schema` 返回 HTTP 400，因此曾把 B1 改为同一次 LLM 调用的严格 JSON envelope。最小探针连续三次得到 requested，并不代表真实长会话稳定；22:34 左右主人连续发送“爱可给我卖萌”时，Bot 一直返回固定“没有组织好回答”兜底。该句来自结构解析后可见 reply 为空触发的本地兜底，不是角色卡正常回复。虽然之后用同一近期历史的独立 JSON 探针又能返回完整结构，但这进一步证明输出具有随机不稳定性，不能靠放宽校验修复。
为恢复“聊天优先”，22:37 先把 `.env` 的 shadow 改为 false 并重启；随后从 ChatAgent 主链完整撤销 JSON response_format、system 合并和结构 envelope 解析，恢复普通文本 + 可选末尾 marker 的安全形态。marker 缺失只会丢弃表情建议，正文原样保留。使用同一近期历史的普通模式探针得到 275 字非 JSON、非固定兜底回复；回退后全量 `562 tests OK（skipped=2）`，git diff --check 通过。Bot 于 22:47 再次重启，shadow=false、attachments=false；普通聊天恢复尚待主人 QQ 复验。正式库、Agent #43 和 Tavily 状态未因该回退改变。
主人随后确认 QQ 中“爱可给我卖萌”已恢复正常角色回复，并选择新增第二个 DeepSeek API Key 做解耦分类。新 Key 只保存在 `.env` 的 `STICKER_CLASSIFIER_API_KEY`，检查时仅确认非空，没有输出内容；Base URL 固定 `https://api.deepseek.com`，模型为 `deepseek-v4-flash`。新增 `sticker_classifier.py`、独立配置和正文发送后的 owner-private 异步调度；分类器不回退使用 ChatAgent Key，不读取历史/记忆/RAG/图片/文件，不写数据库，不重试，也不发送图片。假 transport 覆盖禁用、错误配置、输入预算、严格字段、额外 ID、超时和调用次数；源码审计确认 legacy 与 graph 两条文字路径都先 `matcher.send(result.reply)`，再调度分类。
独立 Key 手动探针只返回安全有限结果：卖萌为 requested + `playful/medium/acting_cute` + 0.95，日期事实为 not_requested；没有经过 QQ、Tavily、MainAgent、RAG 或聊天存储。补充 401/403/429/500 安全类别与单次调用回归后，全量 `571 tests OK（skipped=2）`，Git 口径 Python AST 145 files OK，pip check 与 git diff --check 通过。Bot 于 23:42 在 remote classifier=false、旧 marker shadow=false、attachments=false 下重启；ai_chat 加载、8080 监听、OneBot 重连均正常，stderr 为空，Agent 最新任务仍为 #43。尚未授权 QQ shadow 或 B2 发送。
主人随后明确要求打开新的远程 shadow。只把 `ENABLE_REMOTE_STICKER_CLASSIFIER` 改为 true；旧 `ENABLE_CHAT_STICKER_INTENT_SHADOW=false`、`ENABLE_CHAT_STICKER_ATTACHMENTS=false` 保持不变。Bot 于 23:57 重启，ai_chat、8080 与 OneBot 重连正常，stderr 为空。当前只允许主人私聊在正文成功发送后产生一次后台分类，不发送 GIF；等待日期事实和卖萌样本 QQ live。
2026-07-14 00:02–00:03 主人完成两组 QQ live。样本 #1“今天是几月几号”先得到正常日期正文，远程分类为 not_requested，本地 intent_absent、0 匹配、无选中；样本 #2“爱可给我卖萌”先得到正常角色回复，远程分类为 requested + `playful/medium/acting_cute` + 0.95，本地精确匹配 1 项并影子选中 `aike_act_cute_001`。两次状态均明确自动附带关闭，没有 GIF。NoneBot 日志显示四个 matcher 正常完成，stderr 为空；正式库保持 schema 2、revision 3、enabled 1、disabled 1，Agent 最新任务和 Tavily/external-read 最新任务均仍为 #43，`sticker_classifier.py` 不含 MessageSegment.image、send_private_msg 或 commit_sent。C1 日期负样本与卖萌正样本主链通过；B2 真实自动发送仍需主人另行明确授权。
主人明确授权进入 B2。新增 `sticker_attachment.py`，通过注入单次 sender 复用 A4 发送前安全复核；`__init__.py` 只在正文成功发送、远程分类 requested、本地 selected、attachments=true、未熔断时调用一次 OneBot private image。失败不 retry、不替代，成功后才 commit 冷却/消息间隔/小时计数/shuffle-bag；发送成功但 commit 异常时熔断。全量 `576 tests OK（skipped=2）`，Git 口径 Python AST 147 files OK，pip check 和 git diff --check 通过。先在 attachments=false 下于 00:35 重启安全加载，再按授权设为 true 并于 00:36 重启，ai_chat、8080、OneBot 正常。
主人 00:39 发送“爱可给我卖萌”，确认先收到正常文字、随后收到动态表情；00:40 状态显示 requested、`playful/medium/acting_cute`、0.95、selected、匹配 1、`aike_act_cute_001`、自动附带已发送。stderr 为空，Agent/Tavily 最新任务仍为 #43。主人随即表示不喜欢该表情并要求删除。核对 enabled 与最终短哈希后，调用现有原子撤销函数把 `aike_act_cute_001` 设为 disabled，library revision 从 3 升至 4；完整 loader 复核为 enabled 0、disabled 2、invalid 0。当前不会再自动发送该 GIF；文件按现有安全撤销合同保留作审计，未做不可逆磁盘删除。
```

## 后续整理规则

## 2026-07-14 本地表情批量逐项批准

```text
主人明确指定批准草稿序号 4、5、6、9、12、15、18、21、23、24、29、30、31、32，未授权批准其他候选。
按草稿 revision 1 精确映射到 14 个 candidate_<12位短哈希>，每项确认值与 candidate ID 完全相同。写入前一次性复核 14 项当前候选、完整源 SHA-256、sticker ID、来源去重和目标文件冲突，全部通过。
在受限工作区内首次执行时，安全批准函数无法在 approved 目录创建以点开头的原子临时文件，因此在第一项 normalization 阶段 fail closed 并清理临时文件，manifest 仍为 revision 4。同一张 38 帧 GIF 在隔离临时目录使用相同参数成功规范化，进一步定位为受限环境的目录写入权限，不是素材损坏。获得主人对本地批准写入的明确允许后，使用原有原子写入函数完成，未绕过任何哈希、图片预算、metadata、动画或 manifest 复核。
成功新增：aike_peek_002、aike_surprised_001、aike_pleading_001、aike_pleading_002、aike_pleading_003、aike_affection_003、aike_recording_001、aike_affection_004、aike_surprised_003、aike_pleasing_001、aike_affection_005、aike_peek_003、aike_tired_002、aike_pleading_004。其中 13 张动态 GIF、1 张静态图；每项批准独立递增 revision。
批准后完整 loader 复核：schema 2、revision 18、enabled 14、disabled 2、invalid 0；14 个指定 ID 全部 enabled，missing=none。已撤销的 aike_act_cute_001 和 aike_angry_002 继续 disabled，未物理删除审计副本。其他 16 个候选仍在 inbox/草稿中保留，未批准、未移动、未删除。
表情专项回归运行 81 tests，全部通过，skipped=2 仍为 Windows 当前权限无法创建测试符号链接。运行选择路径在每次分类后重新加载完整 manifest，因此新资产不需要 Bot 重启即可参与主人私聊 B2；本轮没有发送 QQ 图片，仍需主人做新资产 live 验收。
本轮没有修改 .env、API Key、数据库、RAG 索引或网络权限；没有调用 Tavily、MainAgent、ProjectDocRAG 或 QQ 动态；没有 commit 或 push。
```

## 2026-07-14 本地表情设计文档状态收口

```text
按恢复清单重新核对 Git、当前开发状态、版本运行记录和本地表情设计；main 与 origin/main 仍共同指向 cfbda5c，既有大量未提交开发修改全部保留，没有 commit、push 或 reset。
执行指定 rebuild-rag-index 开发上下文查询并成功返回 5 条项目文档、4 条记忆；召回结果命中当前状态文档，但表情主题的前几项仍偏向旧基础文档，因此本轮继续以仓库与最新交接文档为准，没有把召回结果当作运行时事实。
核对独立远程分类、正文发送后调度、B2 单次私聊图片发送和发送成功后 commit_sent 的代码顺序；表情专项重新运行 81 tests OK，skipped=2 仍为 Windows 当前权限无法创建测试符号链接。
修正 local-static-sticker-library-design.md 的过期当前态：不再写 revision 3、shadow 开启、attachments 关闭或 B2 未执行；同步为远程分类开启、旧 marker shadow 关闭、attachments 开启，以及 schema 2、revision 18、enabled 14、disabled 2、invalid 0。
文档明确运行分类后会重新加载 manifest、14 个新资产无需单独重启 Bot；保留 B1 marker/JSON envelope 的历史失败经验、主人私聊限定、正文优先、无重试、频率门控、撤销不物理删除和剩余 16 个候选不自动批准等边界。
除按恢复清单执行开发侧 ProjectDocRAG 索引重建外，本轮只修改设计与运行记录文档；没有修改 .env、API Key、聊天数据库、MemoryRAG、真实表情、正式 manifest 或批准草稿，没有调用 DeepSeek、Tavily、MainAgent 或 QQ 图片发送。
```

## 2026-07-14 B2 冷却期跳过远程表情分类

```text
主人完成一晚 QQ live，反馈基本场景均符合预期，未发现功能问题；提出在表情发送冷却期间跳过表情分类 LLM，以减少 token 使用。
StickerSelectionRuntime 新增纯本地 preflight，不需要 StickerIntent 或正式库即可检查 policy、owner-private scope、正文可用性、120 秒冷却、4 条消息间隔和每小时发送上限。preflight 只读取既有内存发送状态，不消费 shuffle-bag、不提交冷却或小时计数。
B2 自动附件开启时，schedule_remote_sticker_classifier_shadow 在创建异步分类任务前执行 preflight；命中 cooldown、message_gap、hourly_cap 或附件熔断时直接返回 classifier_status=skipped，不调用 classify_sticker_intent。C1 shadow 在 attachments=false 时仍继续分类观察，不受发送频率状态影响。
正文发送顺序保持不变；预检发生在正文成功发送之后。会话消息仍正常持久化，因此跳过分类不会冻结 message_index，达到 4 条间隔后可以自然恢复。预检读取本地消息进度异常时 fail closed 为 preflight_unavailable，跳过分类且不影响已发送正文。
/表情意图状态 新增“频率门控中，未调用分类模型”展示；本地决策保留 cooldown、message_gap、hourly_cap 等安全类别，不显示正文、路径、哈希或异常原文。
新增 preflight 冷却、消息间隔恢复、小时窗口到期、不消费状态和分类前源码顺序测试。表情专项 83 tests OK（skipped=2）；完整回归 578 tests OK（skipped=2）。本轮未调用 DeepSeek、Tavily、MainAgent 或 QQ 图片发送，未修改 .env、API Key、真实表情、正式 manifest 或批准草稿，未重启 Bot，未 commit 或 push。
```

## 2026-07-14 MainAgent TXT/Word/PPT 受控文档产物

```text
主人明确选择下一步同时增加 TXT、Word 和 PPT 三种 MainAgent 文档能力，并保持“不让 Agent 修改项目”的边界。
新增纯本地 document_artifacts.py，生产根固定为 Git 忽略的 output/main-agent-workspace/；工具不接受 path 或文件名参数，只创建 artifact_<UTC>_<安全随机后缀>.txt/.docx/.pptx 唯一新文件，不覆盖已有文件。
TXT 使用 UTF-8/LF 并精确重读；DOCX 使用 python-docx，支持标题、三级标题、项目符号和编号列表；PPTX 使用 python-pptx，生成 16:9 标题页和正文页，以 ## 标题或 --- 分页，每页最多 8 项、总计最多 20 页。
DOCX/PPTX 保存后执行 ZIP test、必需 OOXML member 校验和库级重新打开；三种格式都限制 title<=120、content<=20,000、最终文件<=10 MiB，刷新临时文件后原子替换，并再次核对最终字节和 SHA-256。符号链接、控制字符、空内容、未知格式、超预算和异常依赖均 fail closed。
MainAgent owner_write_command 新增 create_txt_document、create_word_document、create_presentation。Main LLM 工具合同只允许 command/query/title/content/既有管理参数，不暴露 path；模型必须先生成完整 title/content，ToolPolicyCheck 只创建 write_local 审批，主人确认后才通过既有 approval_resume_enabled 注册表执行一次。
帮助、工具状态、边界和 Main LLM prompt 已同步。普通 ChatAgent、群聊、非主人、Owner Console、Tavily、RAG、数据库、shell 和 QQ sender 均未接入；产物完成后只返回 artifact ID、相对路径、大小、计数和短哈希，不自动发送文件。
项目依赖新增 python-docx 1.x 与 python-pptx 1.x，当前虚拟环境已安装 python-docx 1.2.0、python-pptx 1.0.2、lxml 6.1.1 和 XlsxWriter 3.2.9。开发中修正 python-pptx 1.0 的 Pt/Inches 导入位置，以及 Windows 只读句柄 fsync 不兼容；修正后真实 DOCX/PPTX 重开通过。
专项 MainAgent/格式合同 79 tests OK（skipped=1，为 Windows 符号链接权限）；完整回归 587 tests OK（skipped=3，均为符号链接权限）。本轮测试仅写系统临时目录，没有创建真实文档产物，没有调用 Main LLM、Tavily、RAG 或 QQ 发送；Bot 未重启，QQ live 尚未执行，没有 commit 或 push。
```

## 2026-07-14 修复 Main LLM 文档工具可见性接线

```text
主人首次 live 请求 TXT artifact 时收到“当前可用的 visible tool 只有 dev_context，未注册可调用的 owner_write_command”安全拒绝；没有创建审批、没有写文件。
定位结果：run_main_agent_qq_command 的执行侧 create_read_only_main_agent_runtime_handler 会注册 owner_write_command，但 LC handler 使用 create_main_agent_lc_call_handler(config) 时没有传入该运行时 registry；main_agent_llm 因而按默认 registry 只渲染 dev_context。问题不在文档渲染器、审批策略或依赖。
修复为生产路径只构造一份完整 main_agent_tool_registry，同时传给 LC Main LLM prompt、create_read_only_main_agent_runtime_handler；runner 也支持显式 tool_registry，并从 active registry 推导 local-write policy。这样 prompt、ActionRequest 校验、ToolPolicyCheck 和实际执行共享同一注册事实。
新增 LC 接线回归：注入完整 registry 后 prompt 必须包含 owner_write_command、create_txt_document/create_word_document/create_presentation、title/content，并且不能包含 path。同步保留文档产物审批前零执行测试。
完整回归 588 tests OK（skipped=3，均为 Windows 符号链接权限）；定向 MainAgent/LC/文档合同 107 tests OK；Python AST 149 files OK，pip check 与 git diff --check 通过。
本轮没有重新调用 Main LLM、Tavily、RAG 或 QQ 文件发送，没有创建真实文档产物，没有 commit 或 push。Bot 尚未重启；修复需重启后再做主人 QQ live。

## 2026-07-14 MainAgent 文档生成后受控 QQ 直接交付

状态：已实现并通过本地定向回归；配置默认仍关闭，Bot 未重启，真实 QQ 文件 live 尚未执行。

保留 `create_txt_document`、`create_word_document`、`create_presentation` 的本地 `write_local` 语义，不会将旧审批追溯扩权。已完成的审批 `#20` 只授权当时的本地 TXT 生成，不会被自动发送。

新增独立 `document_delivery_command`，包含 `create_and_send_txt_document`、`create_and_send_word_document`、`create_and_send_presentation`。工具为 `write_external`、`llm_visible=true`、`requires_approval=true`、`approval_resume_enabled=true`；仅在 `ENABLE_AGENT_EXTERNAL_WRITE=true` 时注册并通过策略门控。参数仅包含 command/query/title/content，不开放 path、文件名、QQ 号、群号、任意接收者或重试选项。

审批恢复后复用纯本地渲染器生成一个新文件，然后创建与 approval/session/user 绑定的有界内存待发送状态。当前 `/agent 确认` 处理器只消费该次确认新生成的状态，发送前再次核对固定工作区、后缀、字节数和完整 SHA-256。待发送状态在 OneBot `send_private_msg` 尝试前移除；每个审批最多发送一个 file segment，失败不重试、不换文件、不换接收者，且不影响本地产物保留。

文档完整性、MainAgent bridge、Main LLM 工具合同、LC registry 接线和 QQ 边界定向回归为 117 tests OK（skipped=1，仅 Windows 符号链接权限）；最新完整回归 592 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。本轮没有修改 `.env`、没有重启 Bot、没有调用 Main LLM/Tavily/RAG，也没有通过 QQ 发送测试文件；没有 commit 或 push。

## 2026-07-14 MainAgent Word 直接交付 live 的 prompt 污染修复

主人已自行开启 `.env` 外部写开关，真实 QQ 链路成功生成并发送 Word，因而 `document_delivery_command` 审批恢复、DOCX 渲染和 OneBot file segment 达到主人私聊已有 live 证据。但产物正文误包含 `Read-only project context`、`MainAgentGraph read-only local test mode`、可见工具列表、禁止项和 `User query`，不能将该次生成视为内容质量验收通过。

根因是 `create_read_only_agent_context_builder` 的历史文本仍声称“只读本地测试”和“禁止外部写”，即使完整 registry 已注册 `document_delivery_command`；`build_main_agent_action_messages` 又把它标记为 `Read-only project context` 并与 owner query 同置于 user message。Main LLM 因而把控制元数据误当可用正文。

修复后，runtime context 明确标记为非用户文档内容，根据实际 registry 说明文档交付是否可用，不再绝对声称“禁止 QQ/外部写”。Action Planner 明确：主题型文档请求需自行生成完整 title/content；“生成并发送”在工具已注册时必须选择 `document_delivery_command`，不得用 `final_answer` 或本地产物降级；内部 metadata 不得复制进 title/content。

本地校验层新增已知 internal scaffold marker 拒绝，即使模型再次输出包装文本，也会在审批创建前停止。MainAgent 未开放上一条 QQ 消息作为文档正文的读取能力；对“使用我刚才/上一条/上面提供的完整内容”且未同条内联正文的文档请求，确定性规则在 Main LLM 和审批之前返回 `ask_owner`，要求同一条 `/agent` 请求粘贴完整正文或明确仅给主题由 MainAgent 撰写。

新增 prompt 分区、主题型请求、缺失历史引用、scaffold 拒绝和动态 registry context 回归；定向 110 tests OK（skipped=1），最新完整回归 597 tests OK（skipped=3）。修复需重启 Bot 后再用主题型 Word 请求复验；本轮没有修改 `.env`、没有自动重启、没有删除已生成的错误产物，没有 commit 或 push。

主人随后用完整提纲复验，“推荐下一步”被确定性 `agent_task_read` 分类器提前消费，所以 Bot 转而询问 Agent 下一步，没有创建文档交付审批。该问题与外部写开关无关，属于“确定性管理分类优先于 Main LLM”的路由冲突。

新增 `is_document_artifact_request`：当整句同时具有 TXT/Word/PPT/文档对象和生成/撰写/制作意图，且 registry 中存在本地文档或文档交付工具时，跳过任务、审批、主人管理等确定性文本分类，把完整要求交给文档能力 Main LLM。该收口只对明确文档创建请求生效；独立 `/agent 下一步`、任务查询和审批查询仍使用原确定性路由。新增真实提纲复现测试，确认不调 `agent_task_read`、不调 `dev_context`，Main LLM 请求 `document_delivery_command`，策略结果为 `write_external` 审批中断。定向 111 tests OK（skipped=1），完整回归 598 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。修复需重启 Bot 后再做主人 QQ live；本轮未修改 `.env`、未重启、未 commit 或 push。

主人随后重启并用同类主题型 Word 请求完成复验，反馈文档成功生成且内容质量不错。该 live 表明新文档意图优先级已加载，提纲中的“推荐下一步”未再误命中 `agent_task_read`；Main LLM 生成了可用 title/content，内部 runtime metadata、工具列表和 query 包装未再出现在产物正文，审批恢复、DOCX 渲染和主人 QQ 文件交付也均成功。Word 主题型“生成并发送”链路因此完成真实内容质量验收。本次任务 ID 和审批 ID 未由主人提供，不臆造编号；TXT/PPTX 仍只有自动化格式/边界覆盖，尚未记录主人真实内容质量反馈。本次只同步文档状态，未重启 Bot、未修改 `.env`、未 commit 或 push。

## 2026-07-14 MainAgent 文档生成进度回执与会话并发保护

主人在 Word/PPT 测试中观察到 Action Planner 需等待约二十多秒才生成完整文档 `title/content`，期间 QQ 没有首条回执。主人追加 `/agent 在吗` 后，第二个 MainAgent 请求并发返回“在”，第一个文档请求随后才返回审批，导致可见顺序与请求顺序不一致。

新增 `_main_agent_session_locks`，按 QQ session 隔离 `/agent` 和 `/agent-debug`，不复用普通聊天 `_session_locks`。文档请求成功取得锁后，先通过 matcher 发送“MainAgent 正在生成文档标题、正文和审批请求，请稍候”，再调用 Main LLM。同一 session 在锁持有期间收到的后续 `/agent` 不排队、不调 LLM、不调工具，立即返回“上一条正在处理，当前消息未执行”。只引用上一条内容而缺失同条正文的文档请求仍会立即 `ask_owner`，不先发慢任务回执。

互斥锁在 `matcher.finish(reply)` 将最终结果或审批消息交给 adapter 之后才由 `finally` 释放，避免“先释放锁、再发结果”造成新的小竞态窗口。补丁只改善可见响应和顺序，不会缩短 Main LLM 生成完整文档内容的实际耗时，也不增加重试、后台队列或并发生成。

主人本次 PPT 命令已正确生成审批 `#23`、任务 `#47`；工具为 `document_delivery_command`，命令为 `create_and_send_presentation`，标题和 PPT 结构化内容已出现在截断审批摘要中，风险为 `write_external`，状态为待主人确认。因未收到确认后的 PPTX 发送反馈，不宣称 PPT 内容质量或 QQ 交付 live 已通过。定向 124 tests OK（skipped=1），完整回归 599 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。需重启 Bot 后验收进度回执、忙碌拒绝和最终审批顺序；本轮未修改 `.env`、未重启、未 commit 或 push。

## 2026-07-14 MainAgent PPT 审批恢复超页失败与前置结构预检

主人已确认审批 `#23`，但恢复执行返回 `Approval resume failed: document_delivery_too_many_slides`。该错误发生在 PPTX 渲染前置结构阶段：没有成功生成最终 PPTX，没有创建待发送交付状态，也没有调用 OneBot 文件发送。审批已经进入确认/失败语义，不自动重试或改写原审批内容。

根因是审批前 `owner_write_argument_error` 只检查 title/content 类型、空值、控制字符和字符长度，未执行 PPT 的最终分页算法。实际渲染将每个 `## ` 或 `---` 分成一个内容节，每 8 条非空正文拆分续页，并额外生成标题页；结构展开后超过 `DOCUMENT_ARTIFACT_MAX_SLIDES=20`，因而只在主人确认后才 fail closed。

新增纯本地 `presentation_slide_count`，复用 `_ppt_sections` 实际章节和续页语义，返回包含自动标题页的确切渲染页数。MainAgent ActionRequest 校验在 ToolPolicyCheck 和审批创建之前调用该计算，超限时返回明确的“减少 `##` 章节/每节正文，不要另建封面”提示，不创建一个注定失败的审批。渲染器仍保留原硬上限作为第二层保护。

Main LLM 系统 prompt、本地 `owner_write_command` 和外部 `document_delivery_command` 工具合同均补充 PPT 预算：标题页自动生成，不输出独立“封面”内容节；建议最多 12 个 `##` 内容节、每节最多 6 条非空正文；硬上限为标题页、内容页和自动续页合计 20 张。新增确切续页计数和审批前超页拒绝测试；定向 90 tests OK（skipped=1），完整回归 601 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。修复需重启 Bot；主人需重新发起 PPT 请求并确认新审批，不应再确认 `#23`。本轮未修改 `.env`、未重启、未 commit 或 push。

## 2026-07-14 MainAgent PPT 主题、版式与内容叙事升级

主人重新发起 PPT 请求并确认新审批后，PPTX 已成功生成和发送，证明超页结构预检后的真实交付链可达。主人同时反馈产物存在瑕疵且生成质量不高。用本机 PowerPoint 将实际收到的 9 页 PPTX 全部导出为 PNG 后检查，客观问题为：纯白背景、九页均使用同一标题/列表版式、封面 28pt、页标题 24pt、正文 18pt、内容集中于左上而留白过多，并且无主题色、分隔、页码、章节节奏或视觉支撑。内容覆盖完整，但多为并列概括，缺少演示文稿的连续叙事。

本地 `_render_pptx` 升级为受控视觉主题：16:9 深色标题页，52pt 标题、20pt 副标题；浅色内容页，36pt 标题和 22pt 正文；蓝/青/紫循环强调色，顶部强调线、章节/页面双位数编号、分隔线、`AIchatbot · MainAgent` 页脚与页码；“下一步/总结/结论/展望/行动”节使用浅青背景收束。标题和正文都使用微软雅黑；顶层 `# ` 标题被视为与 title 重复而忽略，H1–H6/列表/编号前缀在正文中被归一化，避免 Markdown 符号进入页面。

Main LLM 文档工具合同同步升级：PPT 内容直接从 `## ` 开始，不重复 deck title；按总览、分组能力、当前亮点/边界、下一步组织叙事；每页一个主旨、3–5 条简短具体要点，不使用空泛市场化填充和重复句式。该改动改善文字密度、页间逻辑和自动续页数量，不开放联网图片、任意本地素材或模板下载。

升级后生成一份临时 9 页代表性 PPTX，使用本机 PowerPoint 以 1600×900 导出全部页面，组合联系表并检查代表页原图。所有页均正常打开，未发现文字裁切、标题换行、元素意外重叠、页码不一致或页脚越界。临时 PPTX、单页 PNG 和联系表仅保留在系统临时目录作 QA，未进入 `output/main-agent-workspace/`、Git 或 QQ。演示文稿专项技能对字号、信息密度、留白和逐页视觉检查的要求直接影响了本轮升级。定向 103 tests OK（skipped=1），完整回归 601 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。

主人明确选择保留当前审批顺序：Main LLM 先生成可审查的 title/content 提案，主人确认后才写入 PPTX 并通过 QQ 发送。不改为“审批时看不到最终内容，确认后才调 Main LLM”的意图审批模式。本轮未修改 `.env`、未重启 Bot、未 commit 或 push。

## 2026-07-14 可靠性错误分类与只读周期巡检

主人确认 TXT 未发送是指令未包含“发给我”，不是工具故障；随后明确把下一步转向近期高频错误、超时、失败调用、异常退出、统一分类、可读提示和定期巡检。

新增 `failure_diagnostics.py`，把关键失败统一为配置、模型、权限、网络和数据五类，并产生稳定 code、简要原因和不带副作用的下一步建议。新增密钥、token、password、secret 和 URL 脱敏；未来 `log_ai_event_error` 直接写安全 `category/code/type/message`，MainAgent 观测限制长度。Main LLM、工具执行、正式只读工作和审批恢复失败均接入分类提示；审批失败任务与事件不再持久化任意工具异常原文。PPT 超页、产物完整性、QQ 文件发送、审批上下文和恢复参数缺失均有专用 code。

`/agent 做一次可靠性巡检` 确定性映射到现有 `owner_read_command/ops_health`，近 24 小时错误区改为分类统计，不调用 Main LLM 猜测状态。新增 `scripts/reliability_inspection.py` 与 `scripts/inspect-reliability.ps1`：只读取 `.env` 配置存在性、本机 8080/11434 端口、SQLite immutable read-only schema 和四个固定日志；无时间戳行使用日志文件 mtime 参与窗口过滤，避免旧 TTS/Owner Console 日志污染当前趋势。`-WriteReport` 只原子刷新 Git 忽略的 `output/reliability-inspections/latest.txt`，不接受任意输出路径。

本机实际巡检：当前状态正常，NoneBot 8080 可达，SQLite 只读检查通过，聊天与 MainAgent 模型必填项已配置；最近 24 小时 0 个失败信号，最近 7 天 11 个失败信号（数据类 8、网络类 3、超时 1、失败调用 3、疑似异常退出 0）。这些是历史日志信号，不等于仍有 11 个当前故障或 11 次独立事故。

最终完整回归 607 tests OK（skipped=3，均为 Windows 符号链接权限）；Python AST 594 files OK，pip check 和 `git diff --check` 通过。固定报告 UTF-8 中文重读通过，无替换字符且无残留临时文件。没有调用外部模型/Tavily/QQ，没有自动重试、重启、修改配置、修复数据、创建系统计划任务、commit 或 push。
```

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
