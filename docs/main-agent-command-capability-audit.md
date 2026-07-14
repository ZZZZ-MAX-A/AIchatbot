# MainAgent `/agent` 命令能力审计

本文记录 2026-07-11 当前源码中 `/agent` 的真实能力面。它不是面向 QQ 用户的命令帮助，也不是未来能力规划；它用于回答一条输入实际经过什么路由、命中什么工具和 provider、读取或写入什么、是否调用 LLM/RAG、会产生什么副作用，以及现有测试能证明到什么程度。

审计基线为提交 `a9e7c4b Handle on-demand TTS diagnostics`。使用本文前仍应先检查实时 Git 状态；后续注册表、分类器、provider 或测试变化后，本文必须同步复核。

## 1. 与 `/权限帮助`、`/agent 帮助` 和“工具状态”的区别

| 入口或文档 | 面向对象 | 回答的问题 | 是否足以用于安全审计 |
|---|---|---|---|
| `/权限帮助` | QQ 使用者 | 固定管理命令有哪些 | 否。它混合主人命令和有限开放命令，不解释 `/agent` Graph、provider、LLM/RAG 或间接副作用 |
| `/agent 帮助` | 主人 | 常见 `/agent` 表达怎么写 | 否。它是示例清单，不保证每个示例对应独立能力，也不展示真实读取范围 |
| `/agent 工具状态` | 主人/开发者 | ToolRegistry 注册了哪些工具及其声明风险 | 部分。它展示注册事实，但不覆盖 Graph 前置的严格命令、静态回复、固定任务 parser 和 provider 内部间接调用 |
| 本审计表 | 维护者 | 输入以后实际发生什么 | 是。它把入口、路由、工具、provider、读写、LLM/RAG、副作用、输出与测试连成一条证据链 |

因此三者不应合并。`/权限帮助` 保持短小、面向操作；本表保留在 `docs/`，允许写入内部实现细节和已知缺口。

## 2. 共同入口与路由顺序

### 2.1 共同权限边界

常规 `/agent` 和 `/agent-debug` 都先经过以下入口边界：

- `ENABLE_MAIN_AGENT` 必须开启。
- `MAIN_AGENT_OWNER_ONLY=true` 时只允许主人。
- 群聊在 `MAIN_AGENT_ALLOW_GROUP=false` 时拒绝。
- 普通聊天文本不会触发 MainAgent。
- 入口只构造 `RuntimeIntent.MAIN_AGENT`；不存在 shell、任意文件或任意 SQL 工具。

当前生产配置通常是主人私聊使用，但能力表仍区分“代码允许条件”和“实际建议入口”。正式工作命令在自身 handler 中再次强制主人私聊。

### 2.2 `/agent` 的实际优先级

```text
/agent 输入
  -> 入口开关、主人和群聊检查
  -> 严格正式工作命令
       development_context_report
       system_diagnostics_report/{overview,vision,voice,memory_rag}
  -> 静态命令：帮助 / 状态 / 工具状态 / 边界
  -> 固定任务与审批命令 parser
  -> RootGraph / MainAgentGraph
       1. agent_task_command 确定性语义分类
       2. agent_task_read 确定性语义分类
       3. owner_read_command 确定性语义分类
       4. owner_write_command 参数检查与确定性语义分类
       5. 显式“查/查询/search” -> dev_context
       6. Main LLM（仅在启用时）在受限动作/可见工具中选择
       7. 无 Main LLM 的未知表达 -> ask_owner
  -> ActionRequest 校验
  -> ToolPolicyCheck
  -> 工具执行或审批中断
  -> 本地管理结果直接输出；其他只读结果可由 Main LLM 中性总结
```

这意味着“ToolRegistry 中列出的工具”不是全部入口：正式工作、静态回复和固定任务 parser 都发生在工具选择之前。

### 2.3 LLM 和 RAG 标记

下表使用这些缩写：

- `A-LLM`：Main LLM Action Planner。
- `S-LLM`：Main LLM Tool Summary。
- `R-LLM`：正式研发上下文报告的固定 JSON 总结。
- `MRAG`：MemoryRAG 召回。
- `PRAG`：ProjectDocRAG 召回。
- “可选”表示配置开启且该路径未被确定性路由提前截获时才可能发生。
- “无额外 QQ”表示只回复当前命令，不主动发送第二条消息；这不等于 QQ 出站链路已被独立端到端验证。

## 3. Graph 前置能力

| 命令或意图 | 路由与 provider | 风险/真实读写 | LLM / RAG | 输出与副作用 | 测试与结论 |
|---|---|---|---|---|---|
| `/agent`、`/agent 帮助` | `main_agent_static_reply -> main_agent_help_reply` | 纯静态读取；无持久化 | 无 / 无 | 命令示例和边界；无额外 QQ | 入口/空查询有测试；帮助正文主要靠源码审阅。实用，但不是能力事实来源 |
| `/agent 状态` | `main_agent_static_reply -> main_agent_status_reply` | 读取 MainAgent 配置开关、模型配置 | 无 / 无 | 配置和注册能力摘要；不验证服务在线 | 有入口边界测试，正文缺独立完整断言。可用，但“状态”主要是配置状态 |
| `/agent 工具状态`、`能力列表` | `main_agent_static_reply -> main_agent_tool_status_reply` | 静态描述注册表 | 无 / 无 | 工具、风险、审批示例 | ToolRegistry 合同有测试；展示文本仍是手写。可用，但可能随注册表演进过时 |
| `/agent 边界` | `main_agent_static_reply -> main_agent_boundary_reply` | 静态描述 | 无 / 无 | 当前允许/禁止范围 | 策略行为有测试，正文为手写。适合作为用户说明，不替代本审计 |
| `/agent 执行研发上下文任务：<问题>` | 严格 parser -> `OwnerAgentWorkRuntime/development_context_report` -> `run_development_context_report_for_event` -> DevContextGraph | `read_local`；读取 PRAG、MRAG 和当前状态锚点；创建/更新本地任务与事件，只持久化安全摘要 | R-LLM 可用；MRAG+PRAG | 返回完整临时报告和任务 ID；无外部请求、无额外 QQ | parser、sanitizer、失败路径、RAG 边界有专门测试。实用且职责明确 |
| `/agent 执行系统诊断任务` | 严格 parser -> `system_diagnostics_report/overview` | `read_local`；读取 DB、本地配置、注册能力、安全观测，并只对 loopback 视觉/TTS 做廉价检查；写任务/事件安全摘要 | 无 / 无 | 六区概览；不自动下钻、修复或发送 | 报告、任务链、计数 sanitizer 和 live 均验证。实用 |
| `/agent 执行系统诊断任务：视觉` | 严格 parser -> `system_diagnostics_report/vision` | `read_local`；配置 -> loopback Ollama -> 模型 -> 最近安全观测；写任务/事件安全摘要 | 无 / 无 | 首故障链；不做真实视觉推理 | 专门单测和 live。实用 |
| `/agent 执行系统诊断任务：语音` | 严格 parser -> `system_diagnostics_report/voice` | `read_local`；配置 -> 启动策略/loopback -> service/health -> loaded/language -> 最近安全观测；写任务/事件安全摘要 | 无 / 无 | 支持按需冷启动待机语义；不生成音频、不发送 QQ | 专门单测、完整任务 sanitizer 和 live。实用 |
| `/agent 执行系统诊断任务：记忆与RAG` | 严格 parser -> `system_diagnostics_report/memory_rag` | `read_local`；配置、SQLite 索引计数、最近安全观测；写任务/事件安全摘要 | 无 / 不召回正文 | 不执行 embedding、查询或重建 | 专门单测和 live。实用 |
| `/agent 执行外部只读查询：<问题>` | 严格 parser -> 私聊/主人/`ENABLE_AGENT_WEB`/固定 executor/query policy 门控 -> `external_read_report` | `read_external`；只有显式注入 provider executor 后才允许创建任务；query 原文不持久化 | 无 / 无 | 当前生产默认关闭且未配置 provider，因此只返回关闭或未配置提示；不进入 Main LLM/dev_context，不接受 URL，不创建 pending intent | parser、门控顺序、fake executor、持久化 sanitizer 和 QQ 源码边界有测试；真实联网尚未开放 |
| 未注册/未知系统诊断 scope | 严格 parser 在创建任务前拒绝 | 无读写 | 无 / 无 | 列出现有四个 scope；不创建任务 | parser 与无任务测试覆盖。安全且明确 |
| `/agent-debug <问题>` | 独立 debug 入口，`raw_output=true` -> 显式 `dev_context` | `read_local`；读取 MRAG+PRAG，不持久化原始结果 | 不做 S-LLM；MRAG+PRAG | 返回原始 dev_context 输出；无额外 QQ | RAG 边界与入口注册有测试。仅供主人调试，不应作为运行诊断入口 |

## 4. `owner_read_command` 能力表

这些命令风险均声明为 `read_local`，正常情况下不写业务状态、不创建 approval、不发送额外 QQ。确定性分类先于 Main LLM；如果输入未被分类，启用 Main LLM 时它仍可以选择 LLM 可见的 `owner_read_command`，否则进入 `ask_owner`。

### 4.1 诊断与运行状态

| 内部 command / 常见表达 | 实际 provider 与读取范围 | LLM / RAG | 输出与实用性 | 测试 |
|---|---|---|---|---|
| `bot_status` / “机器人状态、整体状态” | `status_lines`；读取 Bot、会话、图运行、配置开关等本地状态 | A-LLM 可选；本地结果不经 S-LLM / 无 | 状态总览。与 `/agent 状态` 名称相近但对象不同：前者是 Bot，后者是 MainAgent | 分类器批次/dispatcher 族覆盖，缺单独输出合同 |
| `diagnostics` / “诊断、体检、自检” | `DiagnosticsGraph/FULL`；采集配置、runtime、TTS health、错误、memory、cache，并由 `format_diagnostics` 生成综合回复 | A-LLM 可选 / 无 | 能触发但范围宽、旧式输出较长，与正式 overview 重叠；建议主人优先用正式系统概览 | Graph runner 有测试，缺该自然语言入口的独立端到端合同 |
| `ops_health` / “系统诊断、视觉和记忆状态” | `agent_ops_health_reply`；执行视觉状态、MemoryRAG status，读取错误、RootGraph、MainAgent 观测 | A-LLM 可选 / MemoryRAG status 不召回正文 | 旧聚合诊断，证据丰富但不按首故障链，与正式 overview/区域详情重叠 | QQ 边界和 dispatcher 有测试；仍可用，长期应明确 legacy 定位 |
| `config_status` / “查看配置状态” | `DiagnosticsGraph/CONFIG -> format_config_status`；只经过 config snapshot 和 renderer，展示脱敏分区配置 | A-LLM 可选 / 无 | 输出已更新且实用；不验证各服务在线 | formatter 和 view 节点计划有专门测试 |
| `vision_status` / “查看视觉状态、识图、Ollama” | `DiagnosticsGraph/VISION -> format_vision_status`；配置、图片缓存、Ollama 服务/模型及当前实现的推理自检 | A-LLM 可选 / 无 | 快速状态；只有服务/模型正常且自检明确返回低质量重复内容时，中性提示 runner 可能异常，并给出手动 `ollama stop <model>`；本次不执行、不重试 | formatter 正常、服务失败、低质量专属建议和其他失败不误提示均有测试；live 已验证 |
| `vision_troubleshoot` / “完整排查图片识别问题” | `agent_vision_troubleshoot_reply`；视觉自检、图片缓存、最近错误、RootGraph、MainAgent | A-LLM 可选 / 无 | 多源只读排查；同一低质量条件下在初步判断中携带手动 runner 恢复建议，但不执行命令；输出长且与正式视觉详情重叠 | 分类、QQ 边界、findings 和 runner 建议有测试 |
| `tts_status` / “语音状态、TTS 是否在线、IndexTTS2 加载了吗” | `DiagnosticsGraph/TTS -> tts_health_snapshot -> tts_status_reply_lines`；仅主动访问 loopback，读取最近候选 | A-LLM 可选 / 无 | 快速状态；展示按需待机、health、loaded、language、未生成和未端到端验证。实用 | 对象+状态分类正反例、报告 evaluator 和 live 覆盖 |
| `recent_errors` / “查看最近错误” | `DiagnosticsGraph/RECENT_ERRORS -> recent_error_lines(5)`；只经过错误读取和 renderer | A-LLM 可选 / 无 | 能用；错误文本应继续避免泄密 | Graph view 计划和 dispatcher 族覆盖，缺脱敏内容专项合同 |
| `image_cache_status` / “图片缓存状态” | `DiagnosticsGraph/IMAGE_CACHE -> image_cache_stats`；经过 config、image cache 和 renderer | A-LLM 可选 / 无 | 能用；不再采集 TTS、错误或记忆状态 | Graph view 计划和 dispatcher 族覆盖 |
| `memory_status` / “记忆状态” | `DiagnosticsGraph/MEMORY -> memory_status_lines`；基础 `memory_stats` 只读取一次，formatter 继续读取长期记忆、空窗摘要、试用和 embedding 自检 | A-LLM 可选 / 无 | 能用；它是会话记忆状态，不等于 MemoryRAG 检索状态 | Graph view 计划和 dispatcher 族覆盖；名称边界应在帮助中保持清楚 |
| `rag_status` / “RAG 状态” | `MemoryRetrievalGraph/STATUS`；读取配置、向量服务自检和 SQLite 文档/向量计数 | A-LLM 可选 / 不执行语义召回 | 实用，但比正式 memory_rag 详情更偏底层且可能检查 embedding 服务 | QQ 边界和 embedding self-check 有测试 |
| `memory_rag_troubleshoot` / “完整排查记忆检索问题” | `agent_memory_rag_troubleshoot_reply`；RAG status、索引详情、错误、RootGraph、MainAgent | A-LLM 可选 / 不返回项目文档正文 | 多源只读排查；输出长，与正式 memory_rag 详情重叠，但适合跨源定位 | 分类、QQ 边界、findings 有测试 |
| `memory_retrieval` / “记忆检索 <查询>” | `MemoryRetrievalGraph/QUERY`；从当前 MemoryRAG 命名空间执行真实语义召回 | A-LLM 可选 / MRAG | 返回记忆命中；无 PRAG。查询为空或服务失败走 Graph 失败输出 | 查询提取、dispatcher 和 owner boundary 有测试。实用，必须与研发 `dev_context` 区分 |

### 4.2 记忆管理、配置清单与观测

| 内部 command / 常见表达 | 实际 provider 与读取范围 | LLM / RAG | 输出与实用性 | 测试 |
|---|---|---|---|---|
| `summary_status` | `MemoryAdminGraph/SUMMARY_STATUS`；当前会话摘要统计 | A-LLM 可选 / 无 | 实用 | dispatcher 族覆盖，缺单命令端到端合同 |
| `view_summaries` | `MemoryAdminGraph/VIEW_SUMMARIES`；当前会话摘要正文 | A-LLM 可选 / 无 | 实用；输出含用户数据，只应在主人会话内 | dispatcher 族覆盖 |
| `view_gap_scene_summaries` | `MemoryAdminGraph/VIEW_GAP_SCENE_SUMMARIES` | A-LLM 可选 / 无 | 专用排查入口，普通使用频率低 | dispatcher 族覆盖 |
| `view_long_term_memory` | `MemoryAdminGraph/VIEW_LONG_TERM_MEMORY` | A-LLM 可选 / 无 | 实用；读取主人长期记忆正文 | dispatcher 族覆盖 |
| `view_persona` | `load_persona_prompt`，为空时回退 `persona_status_lines` | A-LLM 可选 / 无 | 能读取 ChatAgent 角色卡；不会把角色卡注入 MainAgent 身份 | classifier/dispatcher 族覆盖；身份隔离由 LLM prompt 测试补充 |
| `role_card_list` | `role_card_list_lines`；列出可选卡 | A-LLM 可选 / 无 | 实用，常与审批写 `select_persona` 配合 | 第二批 classifier/dispatcher 覆盖 |
| `model_config_status` | `model_config_status_lines`；聊天/MainAgent/Embedding 配置，URL 脱敏 | A-LLM 可选 / 无 | 仅证明配置，不证明在线或 loaded。实用 | 第二批 classifier/dispatcher 覆盖，缺脱敏专项测试 |
| `access_overview` | `access_overview_lines`；配置和动态黑白名单 | A-LLM 可选 / 无 | 输出计数及完整名单，仅主人使用 | 第二批 classifier/dispatcher 覆盖 |
| `rag_index_detail` | `rag_index_detail_lines`；直接读 SQLite 的 `rag_documents/rag_embeddings` 聚合 | A-LLM 可选 / 不召回正文 | 实用；证明存储计数，不证明一次查询成功 | 第二批 classifier/dispatcher 覆盖 |
| `main_agent_observations` | `recent_main_agent_observation_lines`；从错误日志筛选 MainAgent/main_llm/tool_summary 行 | A-LLM 可选 / 无 | 只有失败类日志观测，不是完整 tracing；“暂无”不证明系统健康 | 第二批 classifier/dispatcher 覆盖 |
| `root_graph_observations` | `recent_root_graph_chat_observation_lines`；读取内存中的最近聊天观测 | A-LLM 可选 / 无 | 实用但仅代表进程内最近样本，重启后可能为空 | 第二批 classifier、结构化观测测试覆盖 |
| `group_whitelist` | `current_access().group_whitelist` | A-LLM 可选 / 无 | 返回当前动态群名单 | classifier/dispatcher 族覆盖 |
| `private_whitelist` | `current_access().private_whitelist` | A-LLM 可选 / 无 | 返回当前动态私聊名单 | classifier/dispatcher 族覆盖 |
| `blacklist` | `current_access().user_blacklist` | A-LLM 可选 / 无 | 返回当前动态用户黑名单 | classifier/dispatcher 族覆盖 |

### 4.3 `DiagnosticsGraph` 的按 view 采集

本次审计后，`run_diagnostics_graph(event, view)` 已从统一全量采集改为显式的 view→节点计划：

```text
FULL          -> config + runtime + TTS + errors + memory + image cache + render
CONFIG        -> config + render
VISION        -> config + image cache + render（视觉 formatter 执行既有视觉检查）
RECENT_ERRORS -> errors + render
IMAGE_CACHE   -> config + image cache + render
MEMORY        -> memory stats + render（其余记忆状态由既有 formatter 读取）
TTS           -> config + TTS health + render
```

CONFIG、RECENT_ERRORS、IMAGE_CACHE 和 MEMORY 不再因为共享 FULL 序列而检查 TTS health。MEMORY renderer 复用已采集的基础 `memory_stats`，避免同一次 Graph 内重复读取该统计。每个 view 的明确节点序列和“不调用无关 provider”均由参数化测试约束；formatter 自身执行的读取仍属于该 view 的真实 provider 范围，不能只凭 Graph node trace 推断为零读取。

## 5. 任务与审批控制面

### 5.1 只读 `agent_task_read`

| command / 常见表达 | provider 与读写 | LLM / RAG | 输出 | 测试与结论 |
|---|---|---|---|---|
| `next_step` / “下一步、现在卡在哪、待我确认” | SQLite 任务/审批只读聚合 | A-LLM 可选 / 无 | 当前下一步或阻塞点 | 确定性优先于 dev_context 有专门测试。实用；不再等同“查研发下一步” |
| `workbench` / “任务工作台、任务看板、协作台” | SQLite 任务/审批只读聚合 | A-LLM 可选 / 无 | 工作台摘要 | classifier 有专门测试。实用 |
| `list_tasks` / “任务状态、任务表” | 读取当前 session/user 的任务 | A-LLM 可选 / 无 | 任务列表 | classifier/dispatcher 覆盖 |
| `task_detail` / “任务详情 #ID、最新任务详情” | 读取任务、事件和关联审批 | A-LLM 可选 / 无 | 详情；缺 ID 时提示严格命令 | latest reference 和隔离测试覆盖 |
| `list_approvals` / “审批状态、有没有待审批” | 读取当前 session/user 的审批 | A-LLM 可选 / 无 | 审批列表 | classifier/dispatcher 覆盖 |
| `approval_detail` / “审批详情 #ID、最新审批详情” | 读取审批、关联任务和最近事件 | A-LLM 可选 / 无 | 详情；缺 ID 时提示严格命令 | latest reference 和隔离测试覆盖 |

### 5.2 内部 `agent_task_command`

该工具 `llm_visible=false`，只能由固定 parser 或确定性语义分类触发。它的风险标记为 `internal`，控制命令本身不创建额外风险审批，但确认已有审批时可能恢复那个审批明确绑定的工具。

| command / 常见表达 | 实际写入或动作 | LLM / RAG | 门控与输出 | 测试与结论 |
|---|---|---|---|---|
| `create_task` / `/agent 任务 <目标>`、自然语言创建任务 | 写 `agent_tasks` 和事件；不执行目标 | 无 / 无 | 返回 task ID 和 pending 状态 | 固定 parser、语义分类和优先级测试。实用，必须继续强调“创建记录 != 执行” |
| `cancel_task` | 更新允许取消的任务和事件 | 无 / 无 | latest/ID 解析；running 等不可取消状态由 runtime 拒绝 | 语义控制测试覆盖 |
| `approve_approval` | 更新 approval；仅当关联工具仍注册且 `approval_resume_enabled=true` 时受控恢复 | 无 / 无 | 裸“可以”不匹配；需要审批语义和 ID/latest | 控制语义、registry、恢复参数和策略测试覆盖 |
| `reject_approval` | 更新 approval 为拒绝，不执行工具 | 无 / 无 | 返回拒绝结果 | 控制语义测试覆盖 |
| `create_approval_drill` | 创建 dry-run task 和 approval；目标工具为隐藏 `dry_run_write_file` | 无 / 无 | 确认后也不写文件 | registry 隐藏、策略中断和 dry-run 测试覆盖 |

## 6. 审批门控 `owner_write_command`

以下工具均为 `write_local`、`llm_visible=true`、`requires_approval=true`、`approval_resume_enabled=true`。首次请求只创建任务和 approval，不执行 provider；主人用明确审批命令确认后，系统重新构造受限 registry 并恢复原工具参数。缺关键参数时先 `ask_owner`，不会创建审批。

| command / 常见表达 | 确认后的 provider 与写入范围 | 失败/证据不足输出 | 测试与结论 |
|---|---|---|---|
| `clear_image_cache` | 清空当前进程图片缓存 | 返回清理数量；provider 失败走受控错误 | 审批前停止和 dispatcher 覆盖。实用 |
| `clear_error_log` | 清空已注册错误日志文件 | 返回清理结果 | 审批族覆盖；应继续防路径扩展 |
| `select_persona` | 按明确 key 更新当前角色卡选择 | 缺 key 先建议查看列表；不存在返回未找到 | 参数保留和审批测试 |
| `add_fact_memory` | 向主人 user subject 写一条事实型人工长期记忆 | 缺内容先澄清；返回 memory ID | 事实/偏好参数和审批测试 |
| `add_preference_memory` | 向主人 user subject 写一条偏好型人工长期记忆 | 同上 | 同上 |
| `clear_session_summaries` | 删除当前 session 的会话摘要 | 返回删除数量 | 专门审批测试 |
| `delete_session_summary` | 删除当前 session 中明确数字 ID 的单条摘要 | 缺 ID 先 `ask_owner`；跨 session 查不到 | 缺 ID、LLM 伪参数、审批和恢复测试充分 |
| `allow_group` | 动态群白名单添加明确数字群号 | 缺数字 target 先 `ask_owner` | 名单写审批和参数测试 |
| `deny_group` | 动态群白名单移除明确数字群号 | 同上 | 同族覆盖 |
| `allow_private` | 动态私聊白名单添加明确数字 QQ | 同上 | 同族覆盖 |
| `deny_private` | 动态私聊白名单移除明确数字 QQ | 同上 | 同族覆盖 |
| `block_user` | 动态用户黑名单添加明确数字 QQ | 同上 | 同族覆盖 |
| `unblock_user` | 动态用户黑名单移除明确数字 QQ | 同上 | 同族覆盖 |

明确禁止的批量/高风险意图包括清空全部上下文、清空全部摘要、删除长期记忆，以及重启 TTS、自动修复语音、下载模型、修改语音配置和清理语音缓存。这些表达直接停止，不创建 approval；“已有审批机制”不代表任意写操作可以自动获得审批能力。

### 6.1 固定工作区文档产物

2026-07-14 新增三个 `owner_write_command` 子命令：

| command | 确认后的动作 | 固定边界 |
|---|---|---|
| `create_txt_document` | 生成 UTF-8 TXT | 固定工作区、唯一新文件、精确重读 |
| `create_word_document` | 生成无宏 DOCX | `python-docx`、OOXML 校验、重新打开 |
| `create_presentation` | 生成无宏 PPTX | `python-pptx`、最多 20 页、重新打开 |

三者仅由 Main LLM 在主人明确请求时生成包含完整 `title/content` 的 ActionRequest；风险为 `write_local`，审批前不执行。工具合同没有 `path` 参数，输出只能进入 Git 忽略的 `output/main-agent-workspace/`，不修改项目文件、不覆盖已有产物、不调用 shell、网络、数据库或 QQ 文件发送。审批参数缺失或超预算时在创建审批前停止。详细合同见 `docs/main-agent-document-artifact-design.md`。

首次 QQ live 暴露 Main LLM LC handler 曾用默认 registry 构建 prompt，导致可见工具只有 `dev_context`，虽然执行侧 registry 已注册 `owner_write_command`。现已在生产接线路径构造一次完整 registry，同时注入 LC prompt handler、ActionRequest/Policy/执行 handler；回归测试验证 prompt 可见三个文档 command 且没有 `path` 参数。

### 6.2 固定主人私聊文档交付

2026-07-14 新增独立 `document_delivery_command`，不改变 6.1 中本地文档命令的授权语义。

| command | 确认后的动作 | 风险与门控 |
|---|---|---|
| `create_and_send_txt_document` | 生成一个 UTF-8 TXT，复核后发给当前主人私聊 | `write_external`；`ENABLE_AGENT_EXTERNAL_WRITE=true`；必须审批 |
| `create_and_send_word_document` | 生成一个 DOCX，复核后发给当前主人私聊 | 同上 |
| `create_and_send_presentation` | 生成一个 PPTX，复核后发给当前主人私聊 | 同上 |

工具只接受 `command/query/title/content`，不接受 `path`、QQ 号、群号、收件人或重试参数。审批恢复时使用原审批的当前 session/user 上下文；发送前再校验固定工作区、后缀、大小和完整 SHA-256。待发送内存状态在 OneBot 尝试前移除；发送失败不重试、不换文件、不换接收者，本地产物仍保留。

旧的 `owner_write_command` 审批不被追溯扩权。已完成的审批 `#20` 仅生成本地 TXT；如果需要生成后直接发送，必须在启用配置后发起新的“生成并发送”请求并确认新审批。

## 7. Main LLM、`dev_context` 与未知输入

| 场景 | 当前路由 | 工具/数据 | 输出和边界 | 测试 |
|---|---|---|---|---|
| `/agent 查 <问题>`、`查询`、`search` | 明确标记 `explicit_dev_context`，确定性选择 `dev_context` | DevContextGraph；MRAG+PRAG | 回答开发阶段、设计、历史和计划；不得声称当前运行健康 | 只读执行、RAG boundary、简洁总结、错误路径有测试 |
| 未命中确定性规则，Main LLM 开启 | A-LLM 只能输出 `tool_request/final_answer/ask_owner` 等 schema 动作 | 可见工具为 dev_context、owner_read、agent_task_read、owner_write；`ENABLE_AGENT_EXTERNAL_WRITE=true` 时额外可见 document_delivery；agent_task_command 隐藏 | 模糊、多个工具都可能或运行/研发含义不清时 prompt 要求 `ask_owner`；策略仍会校验工具与风险 | prompt、合法/非法 JSON、假 shell、final_answer、外部写配置门控和失败映射有测试 |
| 未命中确定性规则，Main LLM 关闭 | `call_safe_no_llm_fallback_agent -> ask_owner` | 不执行工具，不查询 RAG，不写状态 | 返回系统支持的严格命令；不保存 pending intent，不接受后续裸“可以” | 有专门测试 |
| 运行诊断没有注册工具 | 必须 `ask_owner` 或说明支持范围 | 禁止回退 `dev_context` | 不用项目文档生成“可能原因列表”冒充实时诊断 | Main LLM prompt 和 unknown fallback 测试覆盖 |
| Tool Summary | 仅对适合总结的只读工具结果调用 S-LLM；本地管理文本可直接输出 | 工具结果是证据，不是身份设定 | 中性、简洁、不自称角色名、不加括号动作、不补做未执行检查 | summary prompt 与 fallback 测试覆盖 |

`dev_context` 的硬边界是：

```text
允许：当前开发阶段、已完成/未完成工作、设计依据、项目文档、研发历史、下一步计划、架构讨论。

禁止兜底：当前服务是否在线、配置是否实际生效、模型是否加载、数据库是否正常、当前错误是什么、进程是否运行、当前 TTS/视觉是否可用。
```

## 8. 成功、证据不足与失败语义

能力不能只审计“是否触发”，还必须审计三类输出：

| 能力族 | 成功输出 | 证据不足输出 | 失败输出 |
|---|---|---|---|
| 快速状态 | 展示当前 provider 实际获得的字段 | 明确“未验证、未继续判断、未完成端到端验证” | Graph 的安全失败回复，不伪造正常 |
| 正式区域详情 | 状态、定位层、首故障链、安全计数和未执行项 | 上游失败后下游标记未继续；无最近观测时说明证据不足 | 任务标记 failed，只保存异常类别，不持久化原始异常文本 |
| MRAG 查询 | 命中列表/上下文 | 无命中明确返回空结果 | embedding/存储失败走 MemoryRetrievalGraph 错误合同 |
| 任务/审批读取 | 当前 session/user 范围内记录 | 无记录或缺 ID 给严格命令 | 不泄漏其他 session/user 的记录 |
| owner write 请求 | 创建 approval，不立即执行 | 缺 target/content/ID 时 `ask_owner` | 不支持的写意图直接拒绝，不创建 approval |
| approval resume | 明确显示已执行的注册工具结果 | 工具已下线或不可恢复时不执行 | provider 失败记录在受控任务/审批事件中 |
| ask_owner | 一个澄清问题加真实严格命令 | 本身就是不确定性输出 | 明确本次未运行工具、未查询 RAG、未修改状态 |

## 9. 重复入口与当前实用性结论

### 9.1 能触发但职责不够清楚

1. `/agent 诊断`：确实执行 FULL DiagnosticsGraph，但“诊断什么”过宽，与正式系统概览重叠，也没有首故障链。当前可保留兼容，帮助文本应优先推荐 `/agent 执行系统诊断任务`。
2. `ops_health`：跨视觉、RAG、错误和两类观测的旧聚合输出，证据多但长。它适合历史兼容和多源排查，不应与正式 overview 同时被描述为唯一系统诊断入口。
3. `vision_troubleshoot`、`memory_rag_troubleshoot`：比正式区域详情读取更多旁证，仍有价值；应明确为“多源只读排查”，而正式区域详情是“稳定首故障链和任务审计”。
4. `bot_status`、`/agent 状态`、`config_status`、`model_config_status`：四者名字相近，但分别对应 Bot 运行摘要、MainAgent 自身摘要、全局脱敏配置、模型配置。当前帮助只列示例，容易造成误解。
5. `memory_status`、`rag_status`、`memory_rag` 正式详情：分别是会话记忆、RAG/embedding 快速状态、稳定的记忆与 RAG 首故障链，不能互相替代。
6. `/agent 下一步`：当前优先读取任务/审批协作状态，不再自动查询项目文档。若主人要研发计划，应明确使用 `/agent 查 当前开发下一步` 或正式研发上下文任务。

### 9.2 局部采集已收口

CONFIG、RECENT_ERRORS、IMAGE_CACHE、MEMORY、VISION 和 TTS 已使用各自的显式采集计划。后续新增 node 或 view 时，必须同时更新完整 view 映射；测试会检查所有 `DiagnosticsView` 枚举成员均已注册，并验证局部 view 不调用无关 handler。

### 9.3 手写展示可能漂移

`main_agent_help_reply`、`main_agent_tool_status_reply` 和 `main_agent_boundary_reply` 都是手写文本。ToolRegistry、正式 work registry 和 parser 才是运行事实。未来新增或删除能力时，测试未必能自动发现帮助文本过时。

## 10. 测试覆盖总览与缺口

当前测试已经较强地证明：

- `/agent` 与普通聊天、非主人、群聊边界。
- 确定性分类先于 Main LLM。
- 未知无 LLM 输入进入 `ask_owner`，不调用工具或 RAG。
- 语音诊断对象+状态正例和非诊断反例。
- owner write 缺参数、禁止批量意图、审批中断和受控恢复。
- ToolRegistry 参数、可见性、重复注册和假 shell 拒绝。
- 两种正式 work 的严格 parser、任务生命周期、sanitizer 和安全计数。
- overview、vision、voice、memory_rag 的 evaluator、首故障链和一致性。
- Main LLM Action、Tool Summary 与正式研发报告 prompt 边界。

仍应补充但本轮不修改代码的测试候选：

1. 从源码注册事实生成或校验 `/agent 工具状态`，避免手写清单漂移。
2. 为 27 个 `OWNER_READ_COMMANDS` 建立参数化的“表达 -> command -> provider”矩阵，而不是只覆盖代表性批次。
3. 为 bot/config/model/memory/RAG 等近义“状态”建立互斥分类测试。
4. 继续检查 formatter 内部的间接读取是否与 Graph 节点计划一致；Graph handler 已具备“不调用无关 provider”的测试合同。
5. 为最近错误、名单、角色卡、长期记忆输出增加长度和敏感信息边界测试。
6. 为帮助文本中的每条严格命令做 parser 可达性检查。
7. 建立正式区域详情与旧快速/多源入口的职责不混淆测试。

## 11. 维护规则

每次新增或修改 `/agent` 能力时，至少检查：

```text
入口是否是严格命令、确定性分类还是 LLM 选择
ToolRegistry/work registry 是否真实注册
provider 实际读取了什么，是否有间接本地请求
是否写任务、审批、记忆、名单、缓存或日志
是否调用 A-LLM、S-LLM、R-LLM、MRAG 或 PRAG
是否产生额外 QQ 或外部请求
成功、证据不足、失败三种输出是否成立
帮助文本、工具状态和边界文本是否需要同步
测试是单个例子、能力族覆盖还是完整端到端覆盖
是否出现“能触发但不实用”或与旧入口重复
```

推荐长期采用“可生成事实 + 人工审计语义”的方式维护：

- 可生成：ToolRegistry 规格、work registry、内部 command 枚举、风险、LLM 可见性和审批标记。
- 人工审计：自然语言歧义、真实 provider 间接读取、输出实用性、职责重复、证据不足语义和测试强度。

完全手写会很快过时；完全自动生成又看不到 provider 内部行为和语义问题。两者结合才适合作为后续重构、Owner Console 脱敏能力模型、安全回归和项目架构学习的基线。
