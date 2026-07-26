# P2.49 Owner Console 手动诊断工作流设计

状态：P2.49a ProjectDocRAG 固定真实检索与 P2.49b MemoryRAG 索引一致性均已完成主人页面 live；P2.49b 发现 2 条活动事实文档缺少当前有效向量并正确归类为 attention，未自动修复。P2.49c Main LLM 固定问答已证明基础运行可用，严格 JSON 不匹配保留 attention。P2.49d 固定 TTS、资源收尾和主人音质接受均已 live 通过。P2.49e 本地视觉接口与模型收口已 live 通过，但固定正式表情的严格结构化版与自然描述版均未被主人接受。百炼北京地域 `qwen3.7-flash` 隔离样本、Owner Console 页面和两张 QQ 生产图片均已由主人验收通过；启动脚本也已移除视觉对本地 qwen2.5/Ollama 的陈旧依赖。

设计日期：2026-07-21。

初始设计基线：`8f34819 Complete P2.47 reliability and pure-image workflows`。最近审计的已提交基线：`0055dcc Add Owner Console and Main LLM diagnostic articles`。

## 1. 边界演进结论

Owner Console 的初始只读边界不再作为诊断系统的永久能力上限。新合同是：

```text
默认快照继续只读。
配置与业务数据写入继续关闭。
非只读运行动作只能按主人批准的固定诊断工作流逐项开放。
页面刷新、自动刷新和后台任务不能触发诊断动作。
LLM 不得选择工作流、生成动作参数或扩展执行范围。
未注册或未启用的动作必须 fail closed。
```

在通用任务审批流成熟前，Owner Console 不开放通用 shell、任意查询、任意模型调用、任意进程控制、任意路径、任意配置修改或任意数据库写入。

## 2. 发展顺序

后续手动诊断按资源和隐私风险逐步开放：

```text
P2.49a  ProjectDocRAG 固定项目文档真实检索。
P2.49b  MemoryRAG 一致性；真实私人记忆检索另行审批。
P2.49c  Main LLM 固定合同测试，无工具执行。
P2.49d  loopback TTS 的一键受控生命周期：必要时临时启动、一次固定合成、精确清理、仅停止本次持有进程。
P2.49e  视觉固定本地图片真实推理、模型资源收口与主人描述质检（v1 基础 live 已通过；v2 已实现回归，待重载和主人 live）。
```

此顺序用于表达风险递增关系，不是自动路线图。只有当前状态快照标为 `owner_approved` 的阶段可以开始；页面只显示已经实现并启用的动作，不提前增加未来禁用按钮。

## 3. P2.49a 使用问题

第一刀回答一个明确问题：

```text
当前 ProjectDocRAG 是否具有完整的项目文档向量，且能通过一次真实固定查询把本设计文档召回到前五项？
```

它不回答：

```text
任意项目问题是否都能正确召回。
MemoryRAG 或 DevContext 是否正常。
Main LLM 是否正常。
索引是否需要自动重建。
召回片段内容是否适合交给模型。
```

## 4. 固定工作流

工作流稳定值：

```text
project_doc_rag_fixed_retrieval
```

固定测试问题由后端注册，不接受页面参数：

```text
P2.49 Owner Console 手动诊断工作流 ProjectDocRAG 固定检索
```

固定目标：

```text
docs/owner-console-manual-diagnostics-design.md
```

固定限制：

```text
top_k=5
embedding_attempt_count=1
automatic_retry=false
index_rebuild=false
database_write=false
query_text_exposed=false
result_content_exposed=false
llm_called=false
dev_context_called=false
```

执行步骤：

```text
1. 读取并记录 ProjectDocRAG 生产功能开关，但不以其关闭阻断已单独批准的手动工作流。
2. 使用 SQLite mode=ro 统计活动项目文档和当前 provider/model 的有效向量。
3. 文档数为零或文档数与向量数不一致时停止，不执行 embedding。
4. 通过 Ollama 当前 `/api/embed` 接口生成一次固定查询向量。
5. 不使用旧 `/api/embeddings` 自动回退，不重试。
6. 使用 SQLite mode=ro 只读取 source_id、chunk_index 和 embedding。
7. 不 SELECT 文档 content、title、用户、聊天、路径之外的本地信息或原始异常。
8. 计算 cosine similarity，取前五项安全元数据。
9. 检查固定目标文档是否进入前五项。
10. 返回固定状态、计数、最高相似度和安全 code。
```

## 5. 为什么不能复用现有通用检索

审计确认现有 `retrieve_project_docs` 会调用通用 `search_rag_documents`。后者当前执行：

```text
ensure_database()
connect()
```

`ensure_database()` 会设置 WAL 并执行 schema 创建；`connect()` 是可提交的写连接。即使当前 SQL 只有 SELECT，也不符合新手动诊断的 `database_write=false` 合同。

P2.49a 因此新增专用只读查询：

```text
不调用 ensure_database。
只使用 connect_read_only，SQLite URI mode=ro。
只选择检索验证需要的固定元数据和向量。
不选择或返回文档正文。
```

现有普通 ProjectDocRAG、CombinedRAG、DevContextGraph 和 QQ MainAgent 行为保持不变。

## 6. 手动动作 HTTP 合同

只读状态接口：

```text
GET /api/v1/owner-console/manual-diagnostics
```

唯一第一阶段动作：

```text
POST /api/v1/owner-console/manual-diagnostics/project-doc-rag
```

请求体固定为：

```json
{"confirmation":"run_registered_project_doc_rag_probe"}
```

固定请求头：

```text
X-Owner-Console-Action: manual-project-doc-rag-probe-v1
```

POST 不接受 query、path、model、prompt、top_k、min_score、URL、PID 或其他动作参数。

## 7. 同源动作鉴权

Owner Console 仍只允许 loopback 使用。手动 POST 同时要求：

```text
Host 必须是 127.0.0.1、localhost 或 ::1。
Origin 必须与当前 http Host 完全一致。
不开放 CORS。
Content-Type 必须是 application/json。
先通过同源 GET 获得 HttpOnly、SameSite=Strict 的进程内动作 Cookie。
POST Cookie 必须与服务启动时生成的随机动作 session 一致。
固定动作请求头和固定确认值必须同时匹配。
```

动作 session 不进入 URL、不渲染到页面、不写日志、不进入数据库，Owner Console 重启后自动失效。

## 8. 启用合同

普通启动继续关闭所有手动动作。只有显式运行：

```powershell
.\scripts\start-owner-console.ps1 -EnableProjectDocRagProbe
```

才在本次 Owner Console 进程中设置：

```text
OWNER_CONSOLE_MANUAL_DIAGNOSTICS_ENABLED=true
OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED=true
```

未使用该开关时：

```text
状态 GET 可读取。
页面不显示 ProjectDocRAG 动作面板。
POST 固定返回 403。
```

P2.49b 另有独立 `-EnableMemoryRagConsistencyProbe` 开关。两个开关可同时注册到页面，但运行时共享单动作锁，任何时刻只允许执行一个工作流。Main LLM、TTS 和视觉仍没有启用开关或 POST 路由。

## 9. 运行状态

第一刀只保留当前 Owner Console 进程内的最近一次运行，不新增数据库表：

```text
run_id
workflow
status
outcome
stage
code
code_label
started_at
finished_at
attempt_count
document_count
embedding_count
result_count
expected_document_matched
top_score
elapsed_ms
固定安全边界布尔值
```

页面刷新后结果仍可从当前进程内读取；Owner Console 重启后结果消失。等通用任务审批或诊断运行审计表设计完成后，再决定是否持久化。第一刀不借用 Agent 任务、可靠性事件或聊天数据库记录，避免污染真实任务和故障趋势。

同一进程最多运行一个手动诊断：

```text
不排队。
并发请求返回 409 conflict。
不自动重试。
不自动执行后续 MemoryRAG、Main LLM、TTS 或视觉检查。
```

## 10. 页面设计

诊断页只在工作流启用时增加一个紧凑面板：

```text
主人手动动作
项目文档 RAG 真实检索
[手动检查检索]
```

第一次点击只展开确认说明；第二次“确认并执行”才发送 POST。结果显示：

```text
中文结论。
项目文档数量。
有效向量数量。
前五项结果数量。
最高相似度。
英文 workflow、stage 和 code。
本次固定样本的证据限制。
```

不显示固定查询文本、结果文档标识、片段正文、原始异常、Key、URL、本地绝对路径、QQ 或用户标识。

## 11. 固定结果代码

```text
manual_probe_running
unsupported_embedding_provider
project_doc_index_unavailable
project_doc_index_empty
project_doc_index_incomplete
query_embedding_failed
retrieval_execution_failed
expected_document_not_retrieved
unexpected_probe_failure
project_doc_rag_probe_succeeded
```

中文解释不得替代英文 code；原始异常只用于内存中的异常链，不返回或持久化。

## 12. 自动化边界

自动化必须使用 fake embedder 和临时数据库，不调用真实 Ollama。至少覆盖：

```text
专用查询使用 mode=ro，查询前后数据库大小和 mtime 不变。
SELECT 结果没有 content 字段。
固定 executor 只调用 embed_once 一次。
embed_once 不使用 legacy fallback。
并发请求 fail closed，不排队、不重试。
动作关闭时 POST 为 403。
错误 Origin、Cookie、Header、Content-Type 或 confirmation 被拒绝。
成功动作 envelope 明确 read_only=false 和 manual_runtime_action=true。
配置与业务数据写入继续 false。
页面第一次点击不执行，第二次确认才执行一次。
```

真实检索只能由主人启动 Owner Console 后在页面手动点击完成。

## 13. 当前禁止项

P2.49a 继续禁止：

```text
DevContext 或 CombinedRAG 查询。
MemoryRAG 私人记忆查询。
Main LLM、Chat LLM、DeepSeek 或 Tavily 调用。
索引重建、向量写入、文档写入或 schema 创建。
自动诊断、自动重试、自动修复、自动告警或自动清理。
视觉、TTS 或其他媒体模型调用。
任意工具、命令、路径、URL、模型或 prompt 参数。
QQ 消息、图片、语音或文件发送。
通用 Owner Console 写 API。
```

## 14. live 验收

代码、fake 自动化、完整回归和 ProjectDocRAG 重建完成后，主人显式启动：

```powershell
.\scripts\start-owner-console.ps1 -EnableProjectDocRagProbe
```

然后人工验收：

```text
动作面板只在启用后出现。
第一次点击只显示确认内容。
确认后只发生一次 embedding 请求和一次只读检索。
结果显示中英安全证据，不显示查询或片段正文。
数据库大小和 mtime 在动作前后不变。
没有 reliability、Agent task、approval、MemoryRAG 或 DevContext 新记录。
没有自动执行下一阶段动作。
```

只有真实固定检索、数据库零写入和页面证据同时通过，P2.49a 才能 live 收口。

## 15. P2.49b MemoryRAG 索引一致性

第二刀只回答：

```text
活动 MemoryRAG 文档是否都有当前 provider/model 与 content_hash 对应的有效向量？
活动文档是否仍能映射到原 long_term_memories 或 session_summaries 来源？
已配置的记忆来源是否存在缺少活动 RAG 文档的结构缺口？
软删除历史 MemoryRAG 文档当前保留多少向量记录？
```

它不回答具体私人问题能否召回，不读取或输出记忆正文，也不执行真实检索。稳定工作流为：

```text
workflow=memory_rag_index_consistency
POST /api/v1/owner-console/manual-diagnostics/memory-rag-consistency
confirmation=run_registered_memory_rag_consistency
X-Owner-Console-Action=manual-memory-rag-consistency-v1
```

显式启动方式：

```powershell
.\scripts\start-owner-console.ps1 -EnableProjectDocRagProbe -EnableMemoryRagConsistencyProbe
```

MemoryRAG 动作单独设置：

```text
OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED=true
```

专用查询使用 `connect_read_only()`，不调用 `ensure_database()`，不选择 `rag_documents.content`、`session_summaries.summary` 或 `long_term_memories.content`。`build_embedding_provider` 只用于取得配置中的 provider/model 身份，不调用 `embed` 或 `embed_once`，也不访问 Ollama。返回仅包含按来源类型拆分的计数、阶段、固定 code 和以下恒定边界：

```text
memory_content_read=false
private_memory_query_executed=false
embedding_called=false
index_rebuild_executed=false
database_write_allowed=false
llm_called=false
dev_context_called=false
automatic_retry=false
```

结果优先级为：

```text
来源映射缺口 > 活动文档缺少有效向量 > 无活动文档 > 一致性通过

memory_rag_source_mismatch          outcome=attention
memory_rag_active_embedding_gap     outcome=attention
memory_rag_index_empty              outcome=attention
memory_rag_consistency_succeeded    outcome=succeeded
memory_rag_consistency_unavailable  outcome=failed
```

`attention` 表示只读检查成功并发现需要关注的真实状态，不得显示成探测执行失败。当前生产安全计数预期为活动文档 37、有效向量 35、缺失 2，缺失来源类型仅 `manual_fact`；来源缺失 0，软删除历史文档向量 5。因此首次 live 的预期 code 为 `memory_rag_active_embedding_gap`。软删除历史向量是次级存储证据，不等同于活动 orphan，也不自动清理。

页面只在独立开关启用时增加一个紧凑面板。第一次点击只展开确认，第二次才发送一次固定 POST；中文结论旁必须直接显示英文 `workflow/stage/code`，并显示 `memory_content_read=false`、`private_memory_query_executed=false`、`embedding_called=false`。不显示来源 ID、用户、会话、正文、查询、URL、路径、Key 或原始异常。

自动化使用临时 SQLite 与 provider identity fake，确认查询前后数据库大小和 mtime 不变、SELECT 不含正文列、没有 embedding 调用、生产功能关闭不阻断已单独批准的固定动作、两个手动工作流共享并发锁、同源 Cookie/Header/body 合同 fail closed、页面二次确认且只请求一次。P2.49b 不批准私人记忆检索、索引重建、补向量、自动修复、自动重试、Main LLM、DevContext、CombinedRAG、TTS、视觉或 QQ 副作用。

## 16. P2.49c Main LLM 固定合同测试设计草案

### 16.1 诊断问题与证据边界

第三刀只回答一个基础合同问题：

```text
当前配置的 Main LLM 是否能在一次无工具、无私人上下文、无自动重试的固定请求中，
于固定时间和输出预算内返回严格可验证的 JSON 对象？
```

它只验证：

```text
Main LLM 必要配置是否存在且满足固定探测前置条件。
当前配置的 endpoint、鉴权和模型是否能够完成一次请求。
固定 system/user messages 是否能得到非空文本响应。
响应是否精确满足后端注册的 JSON 键、类型和值。
响应对象是否没有 tool_calls 或 invalid_tool_calls。
provider 是否返回安全的 input/output/total token 计数。
固定短请求是否在硬超时和关注延迟阈值内完成。
```

它不验证：

```text
MainAgent 是否会为任意主人问题选择正确工具。
Action Planner、ToolPolicyCheck、审批恢复或工具执行是否正常。
长文、文档、PPT、复杂推理或自然语言质量是否达到生产要求。
MemoryRAG、ProjectDocRAG、DevContext、CombinedRAG 或 Tavily 是否正常。
ChatAgent 角色、聊天历史、时间上下文、表情分类、TTS 或视觉是否正常。
中转服务内部是否存在本客户端不可见的透明重试。
```

主人确认第一阶段的主要结论应是“Main LLM 能否回答固定问题、能否正常运行”。无工具只是隔离本次调用的安全边界；本工作流不向模型提供候选工具，也不根据本次结果评价 MainAgent 面对任意问题时应该选择何种工具。

### 16.2 稳定工作流与启用合同

稳定工作流值：

```text
workflow=main_llm_fixed_contract
```

普通 Owner Console 启动继续不注册该动作。只有显式运行：

```powershell
.\scripts\start-owner-console.ps1 `
  -EnableProjectDocRagProbe `
  -EnableMemoryRagConsistencyProbe `
  -EnableMainLlmContractProbe
```

才在本次 Owner Console 进程中额外设置：

```text
OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED=true
```

该开关只授权本次进程中的固定 Main LLM 合同测试，不修改 `.env`，也不改变 `ENABLE_MAIN_AGENT`、`MAIN_AGENT_USE_LLM`、`ENABLE_AGENT_WEB`、`ENABLE_AGENT_EXTERNAL_WRITE`、`ENABLE_AGENT_LOCAL_WRITE` 或 `ENABLE_AGENT_SHELL`。

生产 `ENABLE_MAIN_AGENT` 与 `MAIN_AGENT_USE_LLM` 只作为 `runtime_feature_enabled` 证据展示，不替代主人通过 `-EnableMainLlmContractProbe` 对本固定动作的单独授权。固定动作仍必须使用已有 `MAIN_LLM_API_KEY`、`MAIN_LLM_BASE_URL`、`MAIN_LLM_MODEL`；页面和 POST 均不能覆盖这些值。

未使用独立开关时：

```text
状态 GET 仍可读取。
页面不显示 Main LLM 合同测试面板。
对应 POST 固定返回 403。
不会预先构造模型客户端或发起网络请求。
```

### 16.3 固定输入与确定性输出合同

固定输入只能由后端代码注册。页面、URL、query string、请求体和 Header 均不能提供或覆盖 prompt、model、base URL、temperature、timeout、token budget、response format 或其他模型参数。

固定 system message 的语义为：

```text
You are a fixed Main LLM contract probe.
You have no tools.
Return exactly one JSON object.
Do not use markdown fences or surrounding prose.
Use exactly the registered keys, types, and values.
```

固定 user question 为：

```text
For probe marker "amber-17", compute 17 + 25 and return the registered contract object.
```

唯一合格响应对象为：

```json
{
  "contract_version": "main_llm.fixed.v1",
  "probe_id": "p2_49c",
  "marker": "amber-17",
  "sum": 42,
  "status": "ok"
}
```

结果验证必须同时满足：

```text
顶层是且只能是一个 JSON object。
字段集合精确等于 contract_version、probe_id、marker、sum、status。
不允许缺少字段或增加字段。
字段类型和值必须与固定对象精确一致。
不允许 Markdown fence、前后说明、多个 JSON 对象或尾随文本。
原始响应字符数不得超过固定本地上限。
响应对象的 tool_calls 和 invalid_tool_calls 必须为空。
```

模型即使返回工具名、ActionRequest 或 tool call，也只能得到 `attention` 结果；本工作流没有工具注册表、策略检查或执行器，因此任何工具都不会执行。

第一刀不依赖 provider 原生 JSON Schema、Responses API、`response_format=json_object` 或 tool calling。当前生产 MainAgent 依赖的是普通 chat messages 返回文本 JSON；固定合同测试应先验证同一基础能力，避免把中转扩展兼容性误当成 Main LLM 基础合同。

第一刀也不额外发送 temperature 参数。确定性来自固定问题、唯一期望对象和严格本地校验，避免因为某些模型或 OpenAI-compatible 中转拒绝 temperature 参数而制造与当前生产调用无关的失败。

### 16.4 专属无工具调用路径

P2.49c 不得调用现有完整 MainAgent Action Planner handler。禁止复用：

```text
create_main_agent_lc_call_handler
create_main_agent_call_handler
build_main_agent_action_messages
MainAgentGraphRunner
MainAgentState
ToolRegistry
ToolPolicyCheck
任何 result_observer 或 reliability recorder
```

专属 executor 只允许：

```text
1. 通过注入的 config provider 读取现有 Main LLM 配置。
2. 在本地完成固定配置前置校验。
3. 构造一个未 bind_tools 的裸 ChatOpenAI client。
4. 向该 client 传入后端注册的两条固定消息。
5. 保留完整响应对象到本地验证完成，以读取文本、tool-call 证据和 token usage。
6. 严格验证固定 JSON，并只返回安全计数、布尔证据、stage 和 code。
7. 丢弃原始响应和原始异常，不返回、不记录、不持久化。
```

专属 client 固定预算建议为：

```text
request_attempt_count=1
client_max_retries=0
streaming=false
probe_timeout_seconds=30
latency_attention_threshold_ms=15000
max_completion_tokens=256
raw_response_character_limit=1024
tools_bound=false
tool_choice_not_sent=true
response_format_not_required=true
```

`client_max_retries=0` 必须由自动化直接验证到最终模型客户端，不能只在结果 DTO 中写布尔值。`attempt_count=1` 只证明本 Owner Console executor 发起一次客户端调用；页面不得声称中转服务内部绝无透明重试。

### 16.5 Token、延迟与内容暴露边界

计时使用单调时钟包住唯一一次模型调用。页面只显示整数毫秒 `elapsed_ms`，不展示远端 request id、headers、system fingerprint 或其他 provider 元数据。

Token usage 提取顺序为：

```text
优先读取响应对象的 usage_metadata。
必要时读取 response_metadata.token_usage 的固定计数字段。
只接受非负整数 input_tokens、output_tokens、total_tokens。
provider 未返回 usage 时保持 unavailable/null，不伪造为 0。
```

固定请求的硬输出预算由 `max_completion_tokens=256` 控制，本地再以 `raw_response_character_limit=1024` fail closed。第一刀不根据 token 数量计费、不累计历史、不设置配额、不自动告警。

远端 Main LLM 只能接收到上述固定合成 system/user messages。不得向模型发送：

```text
主人自由输入或 QQ 消息。
聊天历史、会话摘要或长期记忆。
MemoryRAG、ProjectDocRAG、DevContext 或 CombinedRAG 内容。
数据库记录、任务、审批、可靠性事件或日志。
项目路径、文件正文、环境变量、Key、URL 或用户标识。
MainAgent 工具列表、运行时 metadata 或角色卡。
```

原始固定 prompt 和原始模型响应均不进入页面、Owner Console 状态 DTO、access log、业务日志或数据库。页面可以显示固定 `contract_version` 与 `probe_id`，但不显示 prompt 或响应正文。

### 16.6 HTTP 动作合同

固定路由：

```text
POST /api/v1/owner-console/manual-diagnostics/main-llm-contract
```

固定请求体：

```json
{"confirmation":"run_registered_main_llm_contract"}
```

固定请求头：

```text
X-Owner-Console-Action: manual-main-llm-contract-v1
```

该 POST 必须完整复用现有手动诊断的安全条件：

```text
loopback Host。
Origin 与当前 http Host 完全一致。
不开放 CORS。
Content-Type 精确为 application/json。
进程内 HttpOnly、SameSite=Strict 动作 Cookie。
Cookie、固定 Header 和固定 confirmation 同时匹配。
请求体不能含任何额外字段。
```

动作 envelope 继续明确：

```text
read_only=false
manual_runtime_action=true
configuration_write_enabled=false
business_data_write_enabled=false
```

`read_only=false` 只表示本次发生一次真实远程模型运行动作，不表示允许配置、文件、数据库、QQ 或业务数据写入。

### 16.7 全局运行锁与状态

Main LLM 合同测试必须加入 ProjectDocRAG 和 MemoryRAG 已使用的同一个进程内全局运行锁：

```text
同一时刻最多运行一个手动诊断。
不排队。
并发请求返回 409 conflict。
不自动重试。
不自动串行执行其他工作流。
```

第一刀只在 Owner Console 当前进程内保存：

```text
latest_run
main_llm_contract_latest_run
```

Owner Console 重启后结果消失。不新增数据库表，不借用 Agent task、approval、reliability event、聊天历史或诊断业务表。主人再次手动运行时必须重新完成二次确认；每次确认只产生一个 POST 和一次 client invoke。

### 16.8 结果 DTO 与固定安全证据

运行结果建议包含：

```text
run_id
workflow
status
outcome
stage
code
code_label
started_at
finished_at
attempt_count
elapsed_ms
configured_model
runtime_feature_enabled
contract_version
probe_id
contract_valid
usage_metadata_available
input_tokens
output_tokens
total_tokens
tool_definitions_sent
tool_calls_present
tool_execution_allowed
client_automatic_retry
chat_history_read
chat_history_written
agent_task_written
approval_written
reliability_event_written
database_write_allowed
memory_rag_called
project_doc_rag_called
dev_context_called
combined_rag_called
tavily_called
tts_called
vision_called
qq_write_executed
prompt_exposed
response_content_exposed
```

固定安全布尔值应为：

```text
tool_definitions_sent=false
tool_execution_allowed=false
client_automatic_retry=false
chat_history_read=false
chat_history_written=false
agent_task_written=false
approval_written=false
reliability_event_written=false
database_write_allowed=false
memory_rag_called=false
project_doc_rag_called=false
dev_context_called=false
combined_rag_called=false
tavily_called=false
tts_called=false
vision_called=false
qq_write_executed=false
prompt_exposed=false
response_content_exposed=false
```

`tool_calls_present`、`contract_valid` 和 `usage_metadata_available` 是本次响应的实际证据，不能写死。

不返回或持久化：

```text
API Key。
完整或原始 base URL。
固定 prompt 正文。
原始模型响应。
原始异常、HTTP body 或 headers。
request id、system fingerprint 或中转内部标识。
QQ、用户、会话、任务、审批、文档或记忆标识。
```

### 16.9 通过、需要关注与失败

结果优先级为：

```text
请求执行失败
> 合同或 tool-call 证据不合格
> token usage 不可验证
> 延迟超过关注阈值
> 完全通过
```

固定结果建议为：

```text
main_llm_contract_succeeded
  outcome=succeeded
  stage=result_validation

main_llm_contract_mismatch
  outcome=attention
  stage=result_validation

main_llm_usage_unavailable
  outcome=attention
  stage=result_validation

main_llm_latency_attention
  outcome=attention
  stage=result_validation

invalid_configuration
  outcome=failed
  stage=preflight

authorization_failed
  outcome=failed
  stage=request

model_not_found
  outcome=failed
  stage=request

model_rate_limited
  outcome=failed
  stage=request

request_timeout
  outcome=failed
  stage=request

connection_failed
  outcome=failed
  stage=request

main_llm_request_rejected
  outcome=failed
  stage=request

unexpected_probe_failure
  outcome=failed
  stage=unexpected
```

`attention` 表示固定测试已经得到模型响应，但基础合同、token 证据或延迟目标需要关注；不得显示成“调用完全失败”。`failed` 表示没有取得可验证的模型响应，或在固定请求阶段被配置、鉴权、网络或 provider 拒绝。

错误映射优先使用明确异常类型与 HTTP status：超时、连接、401/403、404、429 和其他受控 400；只有无法取得类型/status 时才使用脱敏后的有限字符串匹配。原始异常不能进入 DTO、页面、日志或数据库。

### 16.10 页面设计

诊断页只在独立开关启用时增加第三个紧凑面板：

```text
Main LLM 固定合同
[手动检查合同]
```

第一次点击只展开确认说明。确认说明必须直接写明：

```text
将向当前配置的远程 Main LLM 发送一次固定合成文本。
本次可能产生少量 token 成本。
不发送主人输入、聊天历史、项目文档或私人记忆。
不开放或执行工具，不写数据库，不自动重试。
```

第二次“确认并执行”才发送一次固定 POST。三个工作流共享页面 running 状态；任一工作流运行时，其他两个按钮不发请求。

结果只显示：

```text
中文结论。
配置模型名。
延迟和安全 token 计数。
英文 workflow、stage、code。
contract_valid、usage_metadata_available、tool_calls_present。
关键零副作用边界。
```

页面不显示自由输入框、模型选择、URL、temperature、timeout、token 调整、原始 prompt、原始响应、原始异常、工具列表或“未来启用”按钮。

### 16.11 自动化边界

代码实现阶段的自动化必须全部使用 fake LLM，不调用真实 Main LLM 或任何外部模型。至少覆盖：

```text
固定 system/user messages 精确不变。
HTTP 和页面不能传入 prompt、model、URL 或模型参数。
专属 client 最终 max_retries=0、streaming=false、固定 timeout 和 max tokens。
一次 executor 只发生一次 fake invoke。
没有 bind_tools、tool definitions、ToolRegistry、MainAgentState 或 MainAgentGraphRunner。
精确 JSON 成功。
非 JSON、Markdown fence、额外字段、缺失字段、错误类型和值均为 attention。
tool_calls 或 invalid_tool_calls 非空时为 attention，且零工具执行。
空响应、content parts 和响应字符上限 fail closed。
usage_metadata 与 response_metadata.token_usage 的有限计数提取。
usage 缺失保持 unavailable/null，不写成 0。
延迟关注阈值和硬超时分开。
配置、401/403、404、429、timeout、connection、400 和未知异常稳定映射。
DTO、序列化结果和日志不含 Key、URL、prompt、response 或异常原文。
不调用 reliability recorder、数据库、Agent task、approval、RAG、QQ、TTS 或视觉。
三个手动工作流共享并发锁，不排队、不自动串行。
动作关闭时 403，并发时 409。
错误 Origin、Cookie、Header、Content-Type、confirmation 或额外 body 字段被拒绝。
页面第一次点击零 POST，第二次确认恰好一个 POST。
前端 POST allowlist 只新增这一条精确固定路由。
```

### 16.12 分阶段实施与 live 验收

主人批准实现后，第一阶段只完成代码、fake 自动化、文档、静态页面和完整回归，不调用真实 Main LLM，不自动重启 Owner Console。

代码与 fake 回归通过后再次向主人汇报。只有主人第二次明确批准，才只重启 Owner Console 并显式增加 `-EnableMainLlmContractProbe`，不停止或重启 Bot、Ollama、TTS，不修改 `.env`。

真实页面 live 必须验证：

```text
动作面板只在独立开关启用后出现。
启动后 main_llm_contract_latest_run 为空，没有自动预跑。
第一次点击只展开确认，第二次确认才执行。
access log 中固定 POST 恰好一次。
run_id=1、attempt_count=1、client_automatic_retry=false。
结果明确显示 succeeded、attention 或 failed，而不是模糊“正常/异常”。
页面显示英文 workflow、stage、code 和关键安全布尔值。
不显示 prompt、响应正文、异常、Key 或 URL。
没有聊天历史、Agent task、approval、reliability event 或业务数据库新记录。
没有调用 MemoryRAG、ProjectDocRAG、DevContext、CombinedRAG、Tavily、TTS 或视觉。
没有自动执行下一阶段工作流。
```

只有一次真实模型调用、严格合同判断、token/延迟证据、零工具执行、零业务数据库写入和页面中英证据同时通过，P2.49c 才能 live 收口。

本节第一阶段设计、fake-only 实现和主人页面 live 均已完成。live 证明 Main LLM 能正常运行并回答固定问题；严格五字段 JSON 未通过，按真实结果保留 `attention/main_llm_contract_mismatch`，不据此扩展为任意问题工具选择诊断。

## 17. P2.49d TTS 一键受控生命周期手动诊断

状态：2026-07-24 主人批准把旧版“服务必须预先在线、产物保留”修订为一键受控生命周期。2026-07-25 第二次 live 暴露旧 bootstrap 阻断，随后完成 lazy-bootstrap；第三次 live 已真实生成有效 WAV并完成服务/磁盘收尾。主人指出“技术 WAV 合同通过不等于语音质量通过”，因此增加进程内临时试听和主人接受/拒绝门控；新的质量 live 已由主人试听并接受。当前技术与音质均 `live_passed/owner_accepted`，没有 QQ 发送。

### 17.1 实际要回答的问题

第四个固定工作流只回答：

```text
当前配置的 loopback TTS 服务无论原本在线还是明确离线，
能否在一次主人确认、无合成重试的受控生命周期中，
安全复用已有服务，或临时启动一个由诊断持有句柄的服务，
使用后端固定短文本和当前配置的音色/情绪，
生成一个非空、时长有效、边界内的 WAV 文件，
清理本次最终/分段产物，并只停止本次诊断启动的进程？
```

它可以证明：

```text
固定 loopback /health 可访问且返回有效健康合同。
明确离线时受管理子进程能否在固定时间内启动并通过所有权指纹校验。
当前配置的 voice_id 能被服务接受。
IndexTTS2 能在本次请求中完成一次固定中文合成。
服务返回的产物位于允许目录，文件存在且非空。
WAV 头、声道、采样率、帧数和计算时长满足固定合同。
本次调用次数、启动/健康/合成/清理延迟、合成前模型 loaded 状态和文件副作用可观测。
最终 WAV 与分段目录能否按本次后端 artifact ID 精确清理。
若服务由诊断启动，是否只通过本次持有的进程句柄完成停止。
```

它不能证明：

```text
音色是否好听、情绪是否自然、发音是否完全正确。
任意长度、任意语言、任意音色或任意文本都能成功。
QQ record 上传、发送和客户端播放链路正常。
ChatAgent/MainAgent 会在合适时机选择语音。
Main LLM、视觉、RAG、外部读取或其他工具正常。
生产聊天链的 ensure_tts_service 自动启动策略正常。
长期稳定性、并发吞吐、显存峰值或内存泄漏不存在。
按端口、进程名或系统进程扫描定位未知 TTS 服务的能力；本诊断明确不做这些动作。
```

因此页面结论只能是“本次固定合成成功/需要关注/失败”，不能写成“TTS 所有能力正常”或“QQ 语音可用”。

### 17.2 现状审计

当前生产调用链是：

```text
send_tts_record()
  -> adapt_speech_text()
  -> request_tts()
       -> ensure_tts_service()
            -> GET /health
            -> TTS_AUTO_START=true 且 loopback 时可能启动本地服务
       -> POST /tts
       -> 校验文件存在、非空、服务声明时长有效且未超上限
       -> observe_tts_synthesis_safely()
  -> OneBot send_private_msg(record)
```

现有 Owner Console 诊断快照只显示 `enable_tts`、音色是否配置、`tts_auto_start` 和 `tts_probe_executed=false`。`/agent 语音状态怎么样` 与 `system_diagnostics_report/voice` 最多访问 loopback `/health`，不生成音频。这些入口能证明配置和服务健康，不能证明真实合成。

不能直接复用 `request_tts()` 作为 P2.49d executor，原因是：

```text
它可能通过 ensure_tts_service() 启动本地进程。
它会通过 reliability observer 写结构化可靠性事件。
它属于聊天/QQ 生产链，边界中包含后续发送能力。
错误会以异常原文在内部传播，不适合直接进入页面 DTO。
```

当前 `tts_service.py /tts` 的真实行为是：

```text
启动时确保 temp_audio/ 存在。
服务在线但模型未加载时，第一次 /tts 会加载 IndexTTS2 到显存。
普通生产请求仍生成随机 run_id；诊断请求可传后端生成的 32 位小写十六进制 artifact_id。
创建 temp_audio/tts_<run_id>_segments/ 和逐段 WAV。
创建 temp_audio/tts_<run_id>.wav 最终产物。
use_random=false、num_beams=1，但音频内容仍不作为字节级确定性合同。
成功返回 audio_path、duration_seconds、分段元数据和 cache_hit=false。
失败通常仍返回 HTTP 200、ok=false 和内部 error 字符串。
TTS 服务自身没有删除接口；Owner Console 专属 executor 已按 artifact_id 建立本次产物清理合同。
由诊断启动的服务通过环境变量接收一次性 owner token，/health 只返回 token 的 SHA-256 fingerprint，不返回 token 本身。
```

这意味着 P2.49d 是“受控本地写文件的手动运行时动作”，不是 read-only。页面和 DTO 必须同时显示 `database_write_allowed=false` 与 `local_file_write_expected=true`，不能用前者掩盖后者。

### 17.3 固定输入与调用路径

稳定 workflow：

```text
workflow=tts_managed_lifecycle
```

后端固定测试文本：

```text
这是一次固定语音合成检查。
```

固定请求合同：

```json
{
  "artifact_id": "<backend generated 32 lowercase hex>",
  "segments": ["这是一次固定语音合成检查。"],
  "pauses_ms": [],
  "voice_id": "<backend configured tts_voice>",
  "language": "zh",
  "emotion": "<backend configured tts_emotion>",
  "max_total_seconds": 20,
  "bypass_cache": true
}
```

页面、URL、query string、Header 和 POST body 都不能提供或覆盖文本、voice、emotion、language、service URL、timeout、max duration、cache 或输出路径。`ENABLE_TTS` 只作为 `runtime_feature_enabled` 证据；主人对独立启动开关的批准才授权本次固定合成。

专属 executor 不调用 `request_tts()`、`ensure_tts_service()`、`send_tts_record()`、VoiceGraph、ChatGraph、MainAgent、reliability observer 或 OneBot。允许的唯一真实调用顺序是：

```text
1. 读取后端现有 TTS 配置并做本地前置校验。
2. 拒绝非 127.0.0.1 / localhost / ::1 的 service URL。
3. 用固定 2 秒超时执行 GET /health；有效在线服务标记 service_preexisting=true，后续绝不停止。
4. 只有 TCP 连接尚未建立的 connection refused/`ConnectError`/`ConnectTimeout` 才允许启动；连接已经建立后的 `ReadTimeout`、畸形 JSON 或健康合同异常不得盲目启动第二个服务。
5. 离线时生成 64 位 owner token，通过环境变量启动一个受管理子进程并保留 Popen 句柄；不调用 start_local_tts_service()。
6. 最多等待 45 秒，轮询 /health；必须得到 owner token 的 SHA-256 fingerprint 才认定 service_owned_by_diagnostic=true。进程提前退出、超时或指纹不匹配均失败。
7. 记录 loaded_before，但 loaded=false 不阻断主人已确认的固定合成。
8. 后端生成 32 位 artifact_id，用固定 180 秒硬超时执行一次 POST /tts；合成不重试。
9. 严格验证安全响应字段、最终 WAV 与唯一 segment_01.wav，然后只清理该 artifact_id 的最终文件和分段目录。
10. 若服务由诊断启动，只对本次持有句柄调用 terminate，固定等待后才可对同一句柄 kill；已有服务绝不停止。不扫描端口、Python 进程或未知 PID。
11. 丢弃 owner token、artifact_id、原始响应、内部 error、文本和完整路径，只保留安全计数与布尔证据。
```

若 `loaded_before=false`，本次显式 POST 可能加载 IndexTTS2 并占用显存。若服务原本离线，本次二次确认还授权 Owner Console 启动和停止一个受管理 TTS 子进程；这不同于生产聊天链的隐式自动启动。页面必须在确认前说明两种副作用。

### 17.4 文件与内容暴露合同

允许的文件副作用仅限现有 TTS 服务为本次请求创建的：

```text
temp_audio/tts_<backend artifact id>.wav
temp_audio/tts_<backend artifact id>_segments/segment_01.wav
```

验证器必须：

```text
使用 resolve 后路径确认最终文件位于项目 temp_audio/ 内。
要求文件名满足固定 tts_<hex>.wav 形式。
拒绝目录穿越、边界外路径、符号链接逃逸或非 WAV 后缀。
确认文件存在、普通文件、大小大于 44 字节且不超过固定安全上限。
用 Python wave 只读取头和帧计数，不把音频内容读入 DTO。
确认 nchannels、sampwidth、framerate、nframes 均为正数。
用 nframes/framerate 计算时长，并与服务声明时长在固定容差内一致。
确认计算时长大于 0 且不超过 20 秒。
```

修订版由 Owner Console 在请求前生成 artifact_id，因此成功和 POST 后失败都能把本次产物精确归属到两个固定路径。收尾只允许删除最终 WAV，以及分段目录中匹配 `segment_XX.wav` 的文件；遇到未知文件时不得递归删除目录，必须保留未知内容并报告 attention。不得清空整个 `temp_audio/`，不得删除其他 artifact ID 或 QQ 产物。输出根目录、最终文件或分段目录的符号链接不得被跟随；本次精确符号链接只解除链接本身。结果必须显示：

```text
local_file_write_expected=true
output_file_created=true|false
output_retained=true|false
segment_directory_retained=true|false
artifact_cleanup_attempted=true|false
artifact_cleanup_succeeded=true|false
partial_artifact_state=none_before_post|failed_artifacts_removed|artifacts_removed|cleanup_incomplete
cleanup_executed=artifact_cleanup_attempted
```

页面只显示最终 WAV 字节数、计算时长、最终文件/分段目录是否仍保留和清理结果，不显示完整路径、artifact_id、分段文本、文件下载/播放链接或音频内容。设计不批准 Owner Console 静态服务暴露 `temp_audio/`。

固定文本会发送给本机 loopback TTS 服务，但不得进入 Owner Console DTO、access log、业务日志、数据库或页面。TTS 服务自身当前响应包含分段文本；专属 executor 必须在内存校验后丢弃，不向上透传。

### 17.5 启用、HTTP 与全局锁

已实现独立启动参数：

```powershell
.\scripts\start-owner-console.ps1 -EnableTtsSynthesisProbe
```

它只在本次 Owner Console 进程中设置：

```text
OWNER_CONSOLE_TTS_SYNTHESIS_ENABLED=true
```

普通启动不显示面板、不创建 `httpx.Client`、不访问 `/health`。已实现固定动作合同：

```text
POST /api/v1/owner-console/manual-diagnostics/tts-synthesis
Content-Type: application/json
X-Owner-Console-Action: manual-tts-synthesis-v1
{"confirmation":"run_registered_tts_synthesis"}
```

继续复用 loopback Host、同源 Origin、进程内 HttpOnly/SameSite Strict Cookie、精确 Header、精确 body 和拒绝额外字段的 fail-closed 条件。

TTS 必须加入 ProjectDocRAG、MemoryRAG、Main LLM 已使用的同一个全局手动诊断锁：不并发、不排队、不自动重试、不自动串行执行其他工作流。最近结果只存在 Owner Console 当前进程内；不创建 Agent task、approval、聊天历史、可靠性事件或业务数据库记录。

动作 envelope 应明确：

```text
read_only=false
manual_runtime_action=true
configuration_write_enabled=false
business_data_write_enabled=false
local_file_write_expected=true
```

### 17.6 结果字段与安全证据

建议结果至少包含：

```text
run_id
workflow
status
outcome
stage
code
started_at
finished_at
attempt_count
elapsed_ms
health_elapsed_ms
synthesis_elapsed_ms
startup_elapsed_ms
cleanup_elapsed_ms
runtime_feature_enabled
service_health_checked
service_healthy
model_loaded_before
model_load_may_have_occurred
configured_voice_present
tts_called
output_contract_valid
output_file_created
output_bytes
output_duration_ms
output_retained
segment_directory_retained
artifact_cleanup_attempted
artifact_cleanup_succeeded
partial_artifact_state
service_preexisting
service_start_attempted
service_started
service_owned_by_diagnostic
service_stop_attempted
service_stopped
automatic_retry
qq_write_executed
reliability_event_written
database_write_allowed
local_file_write_expected
cleanup_executed
chat_history_read
memory_rag_called
project_doc_rag_called
dev_context_called
combined_rag_called
main_llm_called
vision_called
prompt_exposed
response_content_exposed
output_path_exposed
```

正常固定边界应为：

```text
attempt_count=1
tts_called=true
service_preexisting=true|false
service_start_attempted=false|true
service_started=false|true
service_owned_by_diagnostic=false|true
service_stop_attempted=false|true
service_stopped=false|true
artifact_cleanup_attempted=true
artifact_cleanup_succeeded=true
output_retained=false
segment_directory_retained=false
automatic_retry=false
qq_write_executed=false
reliability_event_written=false
database_write_allowed=false
local_file_write_expected=true
partial_artifact_state=artifacts_removed
cleanup_executed=true
chat_history_read=false
memory_rag_called=false
project_doc_rag_called=false
dev_context_called=false
combined_rag_called=false
main_llm_called=false
vision_called=false
prompt_exposed=false
response_content_exposed=false
output_path_exposed=false
```

不返回或持久化 service URL、完整文件路径、固定文本、音频字节、voice 样本路径、原始 TTS 响应、内部 error、异常、日志、GPU 设备标识或 server run_id。

### 17.7 成功、需要关注与失败

结果优先级建议为：

```text
配置/loopback/初始 health 失败
> 受管理服务启动、所有权或健康等待失败
> 请求失败
> 文件安全边界或 WAV 合同失败
> 产物清理不完整
> 本次拥有的服务停止不完整
> 启动或合成延迟超过关注阈值
> 完全通过
```

固定 code：

```text
tts_managed_lifecycle_succeeded
  outcome=succeeded, stage=result_validation

tts_artifact_cleanup_incomplete
tts_managed_service_stop_incomplete
tts_startup_latency_attention
tts_synthesis_latency_attention
  outcome=attention, stage=result_validation
  条件依次为：清理不完整；本次拥有服务停止不完整；启动超过 30000 ms；合成超过 120000 ms

tts_invalid_configuration
tts_non_loopback_service_rejected
  outcome=failed, stage=preflight

tts_health_contract_invalid
  outcome=failed, stage=health_check

tts_service_start_failed
tts_managed_process_exited_early
tts_service_start_timeout
tts_service_ownership_mismatch
  outcome=failed, stage=service_start

tts_request_timeout
tts_connection_failed
tts_request_rejected
tts_synthesis_failed
  outcome=failed, stage=model_synthesis

tts_response_contract_mismatch
tts_output_outside_boundary
tts_output_missing
tts_output_empty
tts_output_invalid_wav
tts_output_duration_invalid
  outcome=failed, stage=result_validation

tts_unexpected_probe_failure
  outcome=failed, stage=unexpected
```

服务在线但 `loaded_before=false` 不是 attention；它表示本次固定动作可能承担了一次正常冷加载。清理、停止、启动延迟和合成延迟按上述顺序进入 attention。错误映射优先使用明确异常类型、HTTP status 和 `ok=false`；原始 `error` 只在内存中用于分类，不能进入 DTO、日志或页面。

### 17.8 页面与二次确认

独立开关启用后，诊断页只增加一个紧凑面板：

```text
TTS 一键生命周期
[检查启动、合成与清理]
```

第一次点击只展开：

```text
先检查本机 TTS；明确离线时会启动一个受管理子进程，已有服务只复用且绝不停止。
服务或模型未加载时，本次请求可能加载 IndexTTS2 并占用显存。
执行一次后端固定中文合成，验证后只清理本次 artifact ID 的最终 WAV 与分段目录。
若服务由本次诊断启动，只停止本次持有句柄的进程；不扫描或结束其他 Python/TTS 进程。
不会发送 QQ、写业务数据库、记录可靠性事件、调用 LLM/RAG 或自动重试。
```

第二次“确认并执行”才发送一个固定 POST。结果只显示中文结论、启动/健康/合成/清理延迟、文件字节数、WAV 时长、模型是否在调用前已加载、服务来源/停止状态、文件清理状态、英文 `workflow/stage/code` 和关键布尔证据。不增加音频播放器、下载按钮、自由文本、音色选择、情绪选择、URL、超时、输出路径或未来禁用按钮。

### 17.9 实现与验收顺序

主人批准的第一步只做代码、fake HTTP、临时 WAV、前端和完整回归；自动化不得访问真实 7861、加载 IndexTTS2、写真实 `temp_audio/`、发送 QQ 或启动服务。本步骤现已完成。

自动化至少覆盖：

```text
固定文本和 payload 不可由 HTTP/页面覆盖。
非 loopback URL 拒绝。
已有服务在线时 process starter 零调用且绝不停止已有服务。
明确离线时只调用一次受管理 process starter；不调用 start_local_tts_service。
初始 health 的 `ReadTimeout`、畸形响应或合同异常不盲目启动；无 listener 但 Windows/httpx 表现为连接建立 `ConnectTimeout` 时进入受管理启动。启动后 owner fingerprint 不匹配时不合成并停止持有进程。
受管理进程提前退出和 45 秒启动超时稳定映射且不进入真实等待。
一次执行只有一次 synthesis，零合成 retry；启动阶段只做固定间隔、有界 health polling。
loaded=false 仍允许已确认的单次合成，并正确显示可能冷加载。
ok=false、超时、连接、HTTP、畸形 JSON 和未知异常稳定映射。
后端 artifact_id 不可由 HTTP/页面覆盖；最终与分段 WAV 路径、文件名、symlink、大小、WAV 头、帧数和时长校验。
成功和 POST 后失败均精确清理本次 artifact；其他 run/QQ 文件保持不变。
分段目录遇到未知文件不递归删除并报告不完整；本次 symlink 只解除链接、不跟随目标。
清理器异常仍必须停止本次持有进程；停止超时只对同一句柄 terminate/kill，不扫描其他进程。
测试只写独立临时目录并由测试框架收尾，不触碰生产 temp_audio。
DTO/日志不含 URL、路径、文本、响应、error 或异常。
不调用 request_tts、ensure_tts_service、reliability observer、数据库、QQ、LLM/RAG 或视觉。
四个手动工作流共享全局锁，关闭时 403、并发时 409。
页面第一次点击零 POST，第二次确认恰好一个 POST。
```

代码与 fake 回归通过后必须再次汇报，不能自动重启 Owner Console 或 TTS。真实 live 需要主人分别确认：

```text
1. 无需主人预先启动 TTS；只重启 Owner Console，并显式增加 -EnableTtsSynthesisProbe。
2. 启动后 tts_synthesis_latest_run 为空，未自动访问 /health 或 /tts，也未启动 TTS。
3. 主人在页面完成二次确认。
4. 若 7861 原本在线：process starter/stop 均为 false，已有服务动作后仍在线。
5. 若 7861 原本离线：service_start_attempted/started/owned 为 true；只能停止本次句柄，service_stop_attempted/stopped 为 true。
6. access log 只有一个 Owner Console 固定 POST；TTS 端只有一次 /tts，合成无 retry。
7. 页面显示英文 workflow/stage/code、attempt_count=1、服务所有权和 artifact 清理证据。
8. 最终 WAV 与分段目录已清理；不得清空 temp_audio，不得影响其他 run 或 QQ 文件。
9. 核对没有 QQ、业务数据库、reliability event、LLM/RAG、视觉或其他工作流副作用。
```

只有固定合成得到有效 WAV、文件边界明确、零重试、零 QQ、零业务数据库写入和页面证据同时满足，P2.49d 才能以“基础合成可用”收口。

### 17.10 fake-only 实现结果与 live 门控

2026-07-24 已实现并验证：

```text
workflow=tts_managed_lifecycle
confirmation=run_registered_tts_synthesis
action header=manual-tts-synthesis-v1
POST /api/v1/owner-console/manual-diagnostics/tts-synthesis

GET /health timeout=2s
POST /tts timeout=180s
follow_redirects=false
trust_env=false
automatic_retry=false
service_preexisting=true|false
service_start_attempted=false|true
service_owned_by_diagnostic=false|true
artifact_cleanup_attempted=true
artifact_cleanup_succeeded=true
output_retained=false
segment_directory_retained=false

独立显式开关与默认关闭
四个手动工作流共享同一个进程内锁
loopback 固定 7861、配置、响应大小、owner fingerprint、路径、文件名、普通文件、大小、最终/分段 WAV 和时长 fail closed
明确离线时受管理子进程启动、45 秒健康等待、持有句柄停止
已有服务不停止；不按端口、进程名或未知 PID 扫描/结束进程
后端固定 artifact_id；成功/失败后只清理本次最终 WAV 和分段目录
页面第一次点击不发 POST，第二次确认只发一个固定 POST
DTO 不暴露固定文本、服务 URL、完整路径、音频、原始响应、内部 error 或异常
```

回归结果：Python 693 tests OK（skipped=4）；其中本模块 15 tests、Owner Console 相关 57 tests、RAG/QQ 边界 13 tests；前端 24 tests、TypeScript、Vite production build和四固定 POST guard 通过。所有 TTS 自动化只使用 fake request、fake process 和测试临时目录中的 WAV。Windows 上需要额外符号链接权限的单项测试按平台跳过，其余路径逃逸、所有权、清理和停止边界已覆盖。最终 AST、pip check 与 diff 证据记录在同日 runlog。

当前完成度严格为：

```text
audited=true
designed=true
implemented=true
regression_passed=true
loaded=false
live_passed=false
real_tts_called=false
tts_service_started=false
index_tts_loaded=false
production_temp_audio_written=false
awaiting_owner_live_approval=true
```

因此这轮只能证明“一键受控生命周期合同在 fake HTTP、fake process 与临时 WAV 下成立”，不能宣称真实 TTS 冷启动、合成、清理或停止已经 live 通过。未经主人新批准，不启动 TTS、不重启 Owner Console、不显式启用开关、不访问 7861，也不生成生产产物。

### 17.11 2026-07-25 首次主人动作与 ConnectTimeout 最小修复

Owner Console 在 `127.0.0.1:8090` 加载五个手动工作流后，主人第一次执行 TTS 动作，得到：

```text
workflow=tts_managed_lifecycle
outcome=failed
stage=health_check
code=tts_health_contract_invalid
health_elapsed_ms=2014
service_preexisting=false
service_start_attempted=false
service_started=false
tts_called=false
output_file_created=false
partial_artifact_state=none_before_post
```

同一时点 `netstat` 没有 `127.0.0.1:7861` listener；用同样的 `httpx.Client(timeout=2, follow_redirects=false, trust_env=false)` 只读复现得到 `httpx.ConnectTimeout`，约 2110 ms。没有证据可进一步归因 Windows 网络层为何把无 listener 表现为超时，因此不得臆测其根因。

旧实现只把 `ConnectError`/connection refused 视为“明确离线”，所以 `ConnectTimeout` 被保守映射为 health contract invalid，没有进入 process starter。这不是“TTS 子进程启动后失败”：本次没有启动子进程、没有加载模型、没有调用 `/tts`、没有创建 WAV，也没有停止任何进程。

主人批准的最小修复只调整连接阶段分类：

```text
ConnectError       -> offline，可以进入受管理启动
ConnectionRefused  -> offline，可以进入受管理启动
ConnectTimeout     -> offline，可以进入受管理启动
ReadTimeout        -> 连接已建立但响应超时，继续 fail closed，不盲目启动
HTTP/JSON/health contract invalid -> 继续 fail closed，不盲目启动
```

`ConnectTimeout` 进入启动后仍必须满足原 owner fingerprint：只有本次 owner token 的 SHA-256 fingerprint 精确匹配，才能继续固定合成；否则不合成，并且只收尾本次持有的 `Popen`。因此修复没有扩大到任意 timeout、端口扫描、进程扫描、未知服务停止、自动重试或自动重跑。

新增端到端 fake 测试验证 `ConnectTimeout -> start once -> fingerprint match -> synthesize once -> exact cleanup -> stop held process`；原 `ReadTimeout -> starter zero calls` 测试继续通过。修复后结果为 TTS 16 tests OK（skipped=1）、Owner Console 手动诊断 17 tests OK、Python 全量 712 tests OK（skipped=4）。Owner Console 已重启加载修复，五 workflow 启用、`latest_run=null`、7861 仍未监听；仍由主人在页面二次确认重试，不由后端自动执行。

### 17.12 2026-07-25 第二次主人 live：服务启动超时

主人重试后的权威结果是：

```text
workflow=tts_managed_lifecycle
run_id=1
attempt_count=1
outcome=failed
stage=service_start
code=tts_service_start_timeout
elapsed_ms=49634
startup_elapsed_ms=47304
health_elapsed_ms=40542
synthesis_elapsed_ms=0
cleanup_elapsed_ms=0
service_preexisting=false
service_start_attempted=true
service_started=false
service_owned_by_diagnostic=false
service_stop_attempted=true
service_stopped=true
tts_called=false
output_file_created=false
artifact_cleanup_attempted=false
artifact_cleanup_succeeded=true
partial_artifact_state=none_before_post
```

本次证明：

```text
ConnectTimeout 最小分类修复已经生效，动作进入了受管理 process starter。
受管理子进程在整个等待窗口内没有提前退出，否则应映射 tts_managed_process_exited_early。
45 秒内始终没有得到带本次 owner fingerprint 的有效 /health。
超时后只停止了本次持有句柄，当前 7861 无 listener。
没有进入 /tts，没有模型合成，没有创建或清理 WAV，没有其他工作流副作用。
```

只读源码审计进一步限定了阻断范围：`tts_service.py` 在执行 `uvicorn.run()` 前顶层导入 `torch` 和 `indextts.infer_v2.IndexTTS2`；真正的 `IndexTTS2(...)` 实例构造则在 `/tts` 调用 `ModelState.ensure_loaded()` 时发生。因此本次不是已确认的“模型加载超过 45 秒”，而是端口监听前 bootstrap/import 阶段没有完成。受管理进程 stdout/stderr 当前为 `DEVNULL`，没有可用子进程错误或阶段日志，无法确认是某个 import 过慢、依赖初始化等待还是其他未退出异常。

不得从该结果直接推导“把 45 秒改成更长即可”。主人随后批准以下最小修订：

```text
让 FastAPI /health 在不导入 torch/IndexTTS2 重依赖的前提下先启动并返回 loaded=false；
把 torch/indextts runtime import 与 IndexTTS2 实例构造统一放入 /tts 的有界模型加载阶段；
为 bootstrap 增加有限枚举 stage/code 或有界脱敏证据，不向 DTO/页面暴露路径、命令、token、traceback 或原始 stderr；
保持 owner fingerprint、一次固定合成、180 秒 synthesis timeout、精确 artifact 清理和只停止本次句柄不变。
```

第二次 live 状态必须永久保持 `failed/tts_service_start_timeout`，不能被后续实现改写成 TTS 可用或 live 通过。

### 17.13 2026-07-25 lazy bootstrap 实现、证据与重载

主人批准按“轻量 health 先启动，torch/IndexTTS 延迟到 `/tts`”继续。实现结果：

```text
tts_service.py 顶层不再 import torch 或 indextts.infer_v2。
GET /health 不触发重依赖导入，返回 loaded=false、runtime_imported=false、language=zh 和 owner fingerprint。
首次 POST /tts 才调用 load_tts_runtime()，导入 torch/IndexTTS2 并构造模型。
runtime 导入成功后在进程内复用；模型 idle unload 后不重复导入 runtime。
runtime 导入失败时模型保持 unloaded，由固定 /tts 失败合同处理，不把 health 伪装成失败。
loaded=true、runtime_imported=false 属于不可能的 health 状态，executor fail closed。
旧服务没有 runtime_imported 字段时按 loaded 兼容，避免把已加载旧服务误判为无 runtime。
```

Owner Console 脱敏 DTO 与页面新增：

```text
runtime_imported_before=true|false
调用前 runtime 已导入 / 未导入
```

该证据只表示本次 `/tts` 前重依赖是否已进入服务进程，不返回 import 名称、路径、耗时分段、异常、traceback、stdout/stderr、owner token 或命令。45 秒 service bootstrap timeout、180 秒 `/tts` hard timeout、一次执行、零自动重试、owner fingerprint、固定 artifact ID、精确清理和只停止本次句柄保持不变。

回归结果：

```text
TTS bootstrap 5 tests OK
TTS lifecycle executor 17 tests OK, skipped=1
Owner Console manual diagnostics 17 tests OK
Owner Console adjacent 101 tests OK, skipped=1
Python full 718 tests OK, skipped=4
frontend 26 tests OK
RAG/QQ boundary 13 tests OK
TypeScript OK
Vite build OK
five fixed POST guard OK
Python AST 153 files OK
PowerShell parse OK
pip check OK
git diff --check OK
```

随后只重启 Owner Console。只读确认当时 `127.0.0.1:8090` 为 PID 19156，五个 workflow 启用，`latest_run=null`、`tts_synthesis_latest_run=null`、`vision_inference_latest_run=null`；`7861` 仍未监听；既有 `11434` 仍为 PID 13412。重启没有执行 TTS、视觉、Main LLM 或 RAG。该状态随后由第三次主人 live 更新，见下一节。

### 17.14 第三次技术 live 与主人音质门控

主人第三次页面动作返回：

```text
workflow=tts_managed_lifecycle
outcome=succeeded
stage=result_validation
code=tts_managed_lifecycle_succeeded
elapsed_ms=70802
startup_elapsed_ms=1054
health_elapsed_ms=3201
synthesis_elapsed_ms=67565
cleanup_elapsed_ms=1
output_bytes=132140
output_duration_ms=2995
model_loaded_before=false
runtime_imported_before=false
service_preexisting=false
service_start_attempted=true
service_started=true
service_owned_by_diagnostic=true
service_stop_attempted=true
service_stopped=true
tts_called=true
artifact_cleanup_succeeded=true
output_retained=false
segment_directory_retained=false
automatic_retry=false
```

该 live 证明：轻量 health 在约 1 秒启动窗口内就绪；重依赖在首次 `/tts` 才进入；IndexTTS2 完成一次真实固定合成；最终 WAV 为有效 132140-byte/2995-ms 产物；磁盘 WAV/分段目录与本次受管理服务均成功收尾。它没有证明固定文本读对或听感合格，因为旧合同在页面可听前已删除 WAV。主人明确要求“回复语音不合格不能算通过”，因此旧结果只收口为 `technical_live_passed=true`、`audio_quality_reviewed=false`，不写成最终主人接受。

固定输入继续是：

```text
这是一次固定语音合成检查。
```

新门控流程：

```text
一次固定合成
-> 验证 WAV 路径、大小、参数、时长与分段合同
-> 在磁盘删除前读取受限最终 WAV 字节
-> 立即精确删除磁盘最终 WAV 和分段目录
-> 只停止本次持有服务
-> 将 WAV 暂存在 Owner Console 单一进程内存槽并绑定 run_id
-> 返回 attention/owner_audio_review/tts_audio_quality_review_required
-> 主人用受保护 GET 加载 Blob 临时试听
-> 主人接受：清除内存，恢复 underlying technical outcome/code
-> 主人拒绝：清除内存，failed/owner_audio_review/tts_audio_quality_rejected
```

临时试听 GET：

```text
GET /api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-preview/{run_id}
X-Owner-Console-Action: manual-tts-audio-preview-v1
```

它要求 loopback Host、当前动作 Cookie、固定 Header、正整数且等于当前待审 run_id；返回 `audio/wav`、`Cache-Control: no-store`、`Content-Disposition: inline`、`nosniff`。没有 query、路径、文件名或下载参数。错误 run、缺 Cookie/Header、诊断并发或预览消失均 fail closed。磁盘 artifact 已经清理，GET 只读取有界内存字节。

主人接受与拒绝分别使用两个固定 POST：

```text
POST .../tts-synthesis/audio-quality/accept
X-Owner-Console-Action: manual-tts-audio-quality-accept-v1
{"confirmation":"accept_latest_tts_audio_quality","run_id":<current>}

POST .../tts-synthesis/audio-quality/reject
X-Owner-Console-Action: manual-tts-audio-quality-reject-v1
{"confirmation":"reject_latest_tts_audio_quality","run_id":<current>}
```

两个审核动作都不调用 TTS、不重试、不创建文件；只更新当前 Owner Console 进程内最近结果并清除内存预览。接受不能覆盖原技术 attention：如果底层是启动/合成延迟、清理或停止 attention，接受后仍恢复该 attention。拒绝总是 failed。页面要求音频播放结束后才解锁“语音合格”；“语音不合格”可在加载后立即选择。后端最终依据主人明确动作，不把浏览器事件伪称为自动音质识别。

新增证据：

```text
fixed_text
technical_outcome
technical_code
audio_preview_available
audio_quality_review_required
audio_quality_reviewed
audio_quality_accepted
audio_reviewed_at
fixed_text_exposed=true
audio_preview_persisted=false
audio_preview_path_exposed=false
audio_review_action_executed
```

回归结果：Python 719 tests OK（skipped=4）；TTS lifecycle 18 tests OK（skipped=1）；Owner Console adjacent 102 tests OK（skipped=1）；前端 29 tests OK；RAG/QQ boundary 13 tests OK；TypeScript、Vite build、一个受保护试听 GET、七固定 POST guard、Python AST 153 files、PowerShell parse、pip check 和 `git diff --check` 通过。

完成后只重载 Owner Console。只读确认 `127.0.0.1:8090` 为 PID 14892，五个 workflow 启用，试听/接受/拒绝路由启用，`latest_run=null`、`tts_synthesis_latest_run=null`；`7861` 未监听，既有 `11434` 仍为 PID 13412。重载没有执行任何诊断。重载当时的阶段状态为 `technical_live_passed=true`、`audio_quality_gate_implemented=true`、`regression_passed=true`、`loaded=true`、`audio_quality_live=false`；该阶段状态已由下述主人听检结果取代。

主人随后在新门控页面重新执行并完成试听。只读结果为：

```text
run_id=1
workflow=tts_managed_lifecycle
status=completed
outcome=succeeded
stage=result_validation
code=tts_managed_lifecycle_succeeded
attempt_count=1
elapsed_ms=59780
startup_elapsed_ms=1031
health_elapsed_ms=3157
synthesis_elapsed_ms=56579
cleanup_elapsed_ms=1
output_bytes=140844
output_duration_ms=3193
model_loaded_before=false
runtime_imported_before=false
service_preexisting=false
service_start_attempted=true
service_started=true
service_owned_by_diagnostic=true
service_stop_attempted=true
service_stopped=true
tts_called=true
output_contract_valid=true
artifact_cleanup_succeeded=true
output_retained=false
segment_directory_retained=false
technical_outcome=succeeded
technical_code=tts_managed_lifecycle_succeeded
audio_preview_available=false
audio_quality_review_required=false
audio_quality_reviewed=true
audio_quality_accepted=true
audio_preview_persisted=false
audio_preview_path_exposed=false
audio_review_action_executed=true
automatic_retry=false
qq_write_executed=false
reliability_event_written=false
database_write_allowed=false
```

`audio_reviewed_at=2026-07-25T10:08:34+00:00`（即 2026-07-25 18:08:34 Asia/Shanghai）。主人明确报告测试通过；后续只读 GET 当前 preview 返回 409，证明接受动作已使内存预览失效。`7861` 无 listener，8090 PID 14892 与既有 11434 PID 13412 保持在线。P2.49d 因此收口为 `technical_live_passed=true`、`audio_quality_live_passed=true`、`owner_accepted=true`。

## 18. P2.49e 视觉固定推理与模型资源收口

状态：2026-07-24 主人先批准视觉模型诊断规划，随后明确“只有清晰识别图片内容才算正常”，并批准 fake-only 实现。独立 executor、固定内存 PNG、严格颜色 JSON、服务/模型所有权、显式开关、固定 POST、页面二次确认、五工作流全局锁和自动化回归均已实现。当前 `implemented=true`、`regression_passed=true`、`loaded=true`、`live=false`；Owner Console 已加载页面和开关，但没有执行真实 `/api/chat`，没有启动/停止既有 11434、加载/卸载视觉模型或读取真实图片。

### 18.1 实际要回答的问题

第五个固定工作流只回答：

```text
当前配置的本机 Ollama 视觉模型，
无论 Ollama 原本在线还是明确离线，
能否在一次主人确认、无重试的受控生命周期中，
接收后端内存生成的固定无隐私 PNG，
正常返回非空、非低质量重复的回答，
并正确识别固定四色位置合同；
诊断结束后，能否保持已有服务/已有模型不被破坏，
同时释放只由本次诊断加载的视觉模型和服务资源？
```

它可以证明：

```text
固定 loopback Ollama /api/tags 可访问且模型清单合同有效。
当前配置的 vision_model 在本地模型清单中存在，无需 pull。
/api/ps 能提供推理前后的视觉模型驻留证据。
服务明确离线时，受管理 ollama serve 能在固定时间内就绪。
当前视觉模型能完成一次固定内存 PNG 的 /api/chat 推理。
返回不是空文本、超长文本或明显低质量重复字符。
严格 JSON 回答是否正确识别四色方位。
本次启动、加载、推理、释放和停止耗时可观测。
已有 Ollama 服务、其他模型和原本已驻留的视觉模型不被诊断停止或卸载。
只由本次诊断加载的视觉模型能否通过 keep_alive=0 和 /api/ps 证据释放。
```

它不能证明：

```text
任意照片、截图、OCR、人物、动漫、游戏 UI 或复杂场景都能正确理解。
图片隐私脱敏、提示注入防护和生产 120 字描述在所有输入上都正确。
QQ 图片下载、等待合并、缓存、群聊 @、RootGraph、ChatAgent 回复链正常。
Main LLM 能为任意问题正确选择视觉工具。
视觉模型质量、幻觉率、长图、多图、并发吞吐或长期显存稳定性完全合格。
RAG embedding、Main LLM、TTS 或其他 Ollama 模型正常。
原本已经在线并由其他业务持有的 Ollama 服务可以安全关闭；本诊断明确不关闭。
```

因此页面结论只能是“本次固定视觉运行与资源合同通过/需要关注/失败”，不能写成“视觉所有能力正常”“QQ 看图可用”或“Main LLM 会正确选择视觉”。

### 18.2 现状审计

当前生产图片链是：

```text
QQ 图片引用
  -> 图片等待/缓存/URL 或本地引用解析
  -> describe_images()
       -> 下载或读取用户图片
       -> base64 编码
       -> _describe_image_base64()
       -> Ollama POST /api/chat
       -> sanitize_vision_description()
       -> observe_vision_infer_safely()
  -> VisionGraph / RootGraph / ChatAgent
  -> QQ 文本回复
```

项目已经存在历史真实推理自检：

```text
/视觉状态
  -> DiagnosticsGraph view=VISION
  -> check_ollama() GET /api/tags
  -> check_vision_inference()
  -> diagnostic_vision_image_base64() 生成 32x32 四色 PNG
  -> _ollama_chat_vision() POST /api/chat
```

该入口能证明一次基础推理，但不能直接作为 P2.49e executor：

```text
它属于 QQ/NoneBot 入口，不具备 Owner Console 独立启动开关与二次确认。
它不与四个 Owner Console 手动工作流共享全局锁。
它只检查服务和模型存在，不负责服务离线时的受管理启动。
它不读取 /api/ps，无法区分模型原本驻留还是由本次加载。
它不设置 keep_alive=0，也不验证推理后的模型资源是否释放。
它把异常整理为中文详情字符串，不适合直接进入脱敏结构化 DTO。
它只要求非空、非重复回答，没有可验证的确定性图像语义合同。
虽然诊断自身不调用 reliability observer，但所在 diagnostics 模块同时依赖数据库、错误日志、角色卡等生产诊断能力，不适合成为独立 Owner Console 最小依赖。
```

现有启动脚本也不能直接复用：

```text
scripts/start-ollama-vision.ps1 默认在未传 -KeepExisting 时，
按进程名结束所有 ollama / ollama app 进程后再启动服务。

scripts/ensure-ollama.ps1 在服务不可达或模型缺失时会调用上述默认脚本；
模型缺失也可能触发重启，而不是只报告缺失。
```

Ollama 可能同时承载 `qwen2.5vl:3b` 与 RAG embedding 模型。固定视觉诊断不得按进程名、端口或未知 PID 结束服务，不得 pull 模型，也不得因为视觉模型缺失而重启一个本来正常服务。

### 18.3 稳定 workflow、固定图片与回答合同

建议稳定 workflow：

```text
workflow=vision_managed_lifecycle
```

固定图片由专属 executor 使用 Python 标准库在内存中生成，不创建项目文件：

```text
contract_version=vision.fixed.v1
format=PNG
width=128
height=128
top_left=纯红
top_right=纯蓝
bottom_left=纯绿
bottom_right=纯白
四个象限之间使用固定黑色分隔线
无文字、无人物、无二维码、无隐私、无网络来源
```

实现时必须固定 PNG 字节长度与 SHA-256，测试用字节级快照确认图片没有漂移；页面只显示 `fixed_image_contract=vision.fixed.v1`、尺寸、字节数和 hash 是否匹配，不返回 base64 或图片内容。

后端固定 prompt 要求模型只返回一个 JSON object：

```json
{
  "contract_version": "vision.fixed.v1",
  "grid": ["red", "blue", "green", "white"],
  "status": "ok"
}
```

确定性校验要求：

```text
必须是单个 UTF-8 JSON object，不接受 Markdown fence、前后说明或重复 key。
字段必须恰好为 contract_version、grid、status，不允许缺失或额外字段。
grid 必须恰好四个字符串，并按左上、右上、左下、右下顺序精确匹配。
原始回答必须非空、低于固定 2048 字符上限且不属于现有低质量重复判定。
```

主人于 2026-07-24 明确收紧通过标准：只有服务成功启动或复用、模型完成一次真实推理，并且回答精确满足上述 JSON/颜色语义合同，才允许返回 `succeeded` 并显示“诊断正常”。仅仅收到非空 HTTP 回答不构成通过证据。

严格 JSON/颜色合同不匹配时，即使回答非空、没有重复字符，也无法确定模型清晰识别了固定图片内容，必须返回 `failed/vision_response_contract_mismatch`，不得降为 `attention`，更不得显示“正常”。空回答、明显重复或无效符号、畸形 Ollama envelope、`done=false`、超长回答，以及任何导致服务未能启动、模型未能加载或推理未完成的原因，同样属于 `failed`。

页面、URL、query、Header 和 POST body 均不能提供或覆盖图片、prompt、model、service URL、num_ctx、keep_alive、timeout、输出格式或资源收尾策略。

### 18.4 专属服务生命周期

专属 executor 不调用 `check_vision_inference()`、`describe_images()`、`scripts/start-ollama-vision.ps1`、`scripts/ensure-ollama.ps1`、DiagnosticsGraph、VisionGraph、RootGraph、ChatAgent、MainAgent、reliability observer 或 QQ adapter。

允许的唯一真实顺序建议为：

```text
1. 读取后端现有 enable_vision、vision_ollama_base_url、vision_model 配置。
2. 只允许无凭据、无 query/fragment/自定义 path 的 http://127.0.0.1|localhost|::1:11434。
3. 校验 model 名称为有限安全字符串；不接受页面覆盖，不执行 ollama pull。
4. 用固定 3 秒超时 GET /api/tags；响应流式读取并限制为 256 KiB。
5. 有效在线服务标记 service_preexisting=true，后续绝不停止。
6. 只有明确 ConnectError/connection refused 才允许启动；超时、HTTP 错误或畸形 JSON 不盲目启动第二个服务。
7. 离线时使用 shutil.which 固定解析 ollama 可执行文件，校验 OLLAMA_MODELS 或项目注册的 D:\OllamaModels 中 blobs/manifests 存在；直接 Popen([ollama, serve])，不经过 PowerShell，不结束任何现有进程。
8. 启动时固定 OLLAMA_HOST 为配置的 loopback 11434，保留 Popen 句柄，最多等待 30 秒；进程提前退出或未就绪则失败。
9. Ollama 不支持 owner token。所有权证据只能是“初始明确离线 + 本次 Popen 仍存活 + 端口随后就绪”；DTO 必须显示 service_ownership_basis=offline_precheck_popen_handle，不得伪称密码学所有权。
10. 校验 /api/tags 中当前 vision_model 存在；缺失直接失败，不下载、不重启。
11. 用固定 3 秒超时 GET /api/ps，记录视觉模型推理前是否驻留；/api/ps 不可验证时不进入推理，避免无法安全收口。
12. 生成固定内存 PNG，执行一次 POST /api/chat；stream=false，不发送 tools，固定 num_ctx=4096，固定硬超时 180 秒，响应限制 64 KiB，零重试。
13. 严格验证 Ollama envelope、done、有限计数/时长、回答质量和固定 JSON 颜色合同；丢弃原始回答与图片。
14. 最多 5 秒、每 250 ms 对 GET /api/ps 做一次有界只读轮询，目标模型消失即结束；记录轮询次数与总耗时，不重复 `/api/chat`。
15. 若服务由本次启动，先确认本次视觉模型已不驻留，再只对本次 Popen 句柄 terminate；超时后只允许对同一句柄 kill。
16. 丢弃 URL、模型目录、可执行路径、原始 tags/ps/chat、异常、prompt、PNG base64 和回答，只保留安全结构化证据。
```

与 TTS 的差异必须保留：Ollama 无法像本项目 TTS `/health` 一样加入 owner fingerprint，因此不得把“持有 Popen”夸大为对端加密证明。若子进程已经退出但端口突然出现其他服务，诊断不得停止该服务，并应返回 ownership ambiguous/failed。

### 18.5 模型驻留与显存收口

推理前必须通过 `/api/ps` 区分三种情况：

```text
A. model_loaded_before=true
   视觉模型在诊断前已经驻留。
   固定请求不得设置 keep_alive=0，不得执行 ollama stop。
   推理后保留模型，不把既有资源当成本次所有。
   页面提示本次请求可能刷新 Ollama 的默认 keep-alive 计时，但未主动卸载。

B. model_loaded_before=false，service_preexisting=true
   服务原本在线，但视觉模型未驻留。
   固定 /api/chat 请求设置 keep_alive=0，使本次加载的模型在响应后立即释放。
   推理后 /api/ps 必须确认该视觉模型不存在；否则 outcome=attention。
   不停止已有 Ollama 服务，不影响其他模型。

C. service_owned_by_diagnostic=true
   Ollama 服务由本次诊断在明确离线后启动。
   固定 /api/chat 同样设置 keep_alive=0，并用 /api/ps 确认视觉模型释放。
   然后只停止本次持有句柄的 ollama serve。
```

固定诊断不使用 `ollama stop <model>` CLI，因为 CLI 会依赖外部 PATH/服务选择且缺少本次请求关联；优先使用本次 `/api/chat` 的 `keep_alive=0` 与 `/api/ps` 前后证据。如果当前 Ollama 版本的 `keep_alive=0` 或 `/api/ps` 合同不成立，应返回 attention/failed，不得自动改用进程扫描或重启。

四个现有手动诊断与 P2.49e 共享 Owner Console 全局锁，只能防止 Owner Console 动作并发，不能阻止 Bot 同时收到真实 QQ 图片。真实 live 前必须由主人安排无视觉业务请求的时间窗口；实现不得为此自动停止 Bot 或修改 QQ 配置。

### 18.6 调用参数、时延与内容暴露

建议固定 `/api/chat` 关键参数：

```json
{
  "model": "<backend configured vision_model>",
  "messages": [
    {
      "role": "user",
      "content": "<backend fixed contract prompt>",
      "images": ["<backend fixed PNG base64>"]
    }
  ],
  "stream": false,
  "options": {"num_ctx": 4096},
  "keep_alive": "<0 only when model was not loaded before; omitted otherwise>"
}
```

固定 `num_ctx=4096` 是基础运行诊断的资源边界，不等于生产配置 `VISION_NUM_CTX` 已被完整验证。页面必须显示：

```text
diagnostic_num_ctx=4096
configured_num_ctx=<有限整数证据>
configured_num_ctx_exercised=false
```

建议时延边界：

```text
GET /api/tags timeout=3s
GET /api/ps timeout=3s
managed service startup timeout=30s
POST /api/chat hard timeout=180s
startup attention threshold=15000ms
inference attention threshold=60000ms
```

Ollama 正常响应可提供 `total_duration`、`load_duration`、`prompt_eval_count`、`eval_count` 等有限元数据。只保留非负有限计数和转换后的毫秒数；字段缺失不应泄露原响应。客户端实测 elapsed_ms 是主要时延证据，服务声明时长只作交叉检查。

不得返回或持久化：

```text
固定 prompt 原文
PNG base64 或图片字节
模型原始回答
Ollama 原始 JSON
模型 digest、blob 路径、模型目录或 ollama 可执行路径
完整 service URL
异常原文、HTTP body 或服务日志
GPU 设备标识和其他已加载模型的名称清单
主人、QQ、缓存或项目图片
```

### 18.7 写入和副作用合同

P2.49e 不是严格 read-only，因为真实推理会加载 GPU 模型，必要时还会创建本地 Ollama 进程。动作 envelope 应明确：

```text
read_only=false
manual_runtime_action=true
configuration_write_enabled=false
business_data_write_enabled=false
project_file_write_allowed=false
ollama_service_start_may_occur=true
gpu_model_load_may_occur=true
ollama_runtime_side_effect_possible=true
model_pull_allowed=false
```

专属 executor 不创建或修改项目文件，不写聊天历史、图片缓存、Agent task、approval、可靠性事件或业务数据库。Ollama 自身在运行时可能维护进程日志、缓存或内部状态，不能宣称整个外部进程零本地写入；但不得 pull 模型、修改环境持久配置或写项目目录。

### 18.8 结果字段与安全证据

建议结果至少包含：

```text
run_id
workflow
status
outcome
stage
code
started_at
finished_at
attempt_count
elapsed_ms
startup_elapsed_ms
tags_elapsed_ms
ps_before_elapsed_ms
inference_elapsed_ms
ps_after_elapsed_ms
cleanup_elapsed_ms
configured_model
runtime_feature_enabled
fixed_image_contract
fixed_image_dimensions
fixed_image_hash_valid
service_preexisting
service_start_attempted
service_started
service_owned_by_diagnostic
service_ownership_basis
service_stop_attempted
service_stopped
model_present
model_loaded_before
model_load_may_have_occurred
model_unload_requested
model_loaded_after
model_cleanup_succeeded
vision_called
response_received
response_nonempty
low_quality_repetition_detected
answer_contract_valid
usage_metadata_available
prompt_eval_count
eval_count
ollama_total_duration_ms
ollama_load_duration_ms
diagnostic_num_ctx
configured_num_ctx
configured_num_ctx_exercised
automatic_retry
tool_definitions_sent
qq_image_read
qq_write_executed
image_cache_read
reliability_event_written
database_write_allowed
project_file_write_allowed
model_pull_allowed
memory_rag_called
project_doc_rag_called
dev_context_called
combined_rag_called
main_llm_called
tts_called
prompt_exposed
image_content_exposed
response_content_exposed
service_url_exposed
```

正常边界应为：

```text
attempt_count=1
vision_called=true
response_received=true
response_nonempty=true
low_quality_repetition_detected=false
answer_contract_valid=true
automatic_retry=false
tool_definitions_sent=false
qq_image_read=false
qq_write_executed=false
image_cache_read=false
reliability_event_written=false
database_write_allowed=false
project_file_write_allowed=false
model_pull_allowed=false
memory_rag_called=false
project_doc_rag_called=false
dev_context_called=false
combined_rag_called=false
main_llm_called=false
tts_called=false
prompt_exposed=false
image_content_exposed=false
response_content_exposed=false
service_url_exposed=false
```

### 18.9 succeeded、attention 与 failed

结果优先级建议为：

```text
配置/loopback/固定图片本地合同失败
> 服务发现或受管理启动失败
> 模型清单或 /api/ps 驻留证据失败
> 推理连接、超时、HTTP、envelope、空回答、低质量重复或超长失败
> 本次加载模型未释放
> 本次拥有服务未完全停止
> usage 元数据缺失
> 启动或推理延迟需要关注
> 完全通过
```

建议固定 code：

```text
vision_managed_lifecycle_succeeded
  outcome=succeeded, stage=result_validation

vision_model_cleanup_incomplete
vision_managed_service_stop_incomplete
vision_usage_metadata_unavailable
vision_startup_latency_attention
vision_inference_latency_attention
  outcome=attention

vision_invalid_configuration
vision_non_loopback_service_rejected
vision_fixed_image_contract_invalid
vision_runtime_unavailable
  outcome=failed, stage=preflight

vision_service_contract_invalid
  outcome=failed, stage=service_discovery

vision_service_start_failed
vision_managed_process_exited_early
vision_service_start_timeout
vision_service_ownership_ambiguous
  outcome=failed, stage=service_start

vision_model_not_found
vision_model_residency_unavailable
  outcome=failed, stage=model_discovery

vision_request_timeout
vision_connection_failed
vision_request_rejected
vision_response_contract_mismatch
vision_empty_response
vision_low_quality_response
vision_response_too_large
  outcome=failed, stage=model_inference

vision_unexpected_probe_failure
  outcome=failed, stage=unexpected
```

### 18.10 启用、HTTP、页面与全局锁

已实现独立启动参数：

```powershell
.\scripts\start-owner-console.ps1 -EnableVisionInferenceProbe
```

只在本次 Owner Console 进程设置：

```text
OWNER_CONSOLE_VISION_INFERENCE_ENABLED=true
```

普通启动不显示面板、不访问 `/api/tags`、`/api/ps` 或 `/api/chat`，也不检查/启动 Ollama。已实现固定动作合同：

```text
POST /api/v1/owner-console/manual-diagnostics/vision-inference
Content-Type: application/json
X-Owner-Console-Action: manual-vision-inference-v1
{"confirmation":"run_registered_vision_inference"}
```

继续复用 loopback Host、同源 Origin、进程内 HttpOnly/SameSite Strict Cookie、精确 Header/body、拒绝额外字段和全局手动诊断锁。不排队、不自动重试、不自动串行执行 TTS 或其他工作流；最近结果只存在 Owner Console 当前进程内。

独立开关启用后页面只增加一个紧凑面板：

```text
视觉固定图片识别
[检查启动、识图与收口]
```

第一次点击只展开：

```text
将使用后端内存生成的固定四色 PNG，不读取主人、QQ、缓存或项目图片。
Ollama 明确离线时会启动一个受管理子进程；已有服务绝不停止。
视觉模型原本未驻留时，本次请求使用 keep_alive=0 并验证释放；原本已驻留时不卸载。
不会 pull 模型、停止其他 Ollama、执行进程扫描、写业务数据库/可靠性、调用 Main LLM/RAG/TTS 或发送 QQ。
本次只能证明固定图片基础推理与资源收尾，不代表任意图片质量或工具选择能力。
```

第二次确认才发送一个固定 POST。页面显示中文结论、模型名、有限时延/计数、服务/模型资源来源和收尾状态，以及英文 `workflow/stage/code` 与关键布尔证据；不提供图片预览、上传、URL、自由 prompt、模型选择、num_ctx、keep_alive、超时、下载或未来禁用按钮。

### 18.11 fake-only 自动化边界

fake-only 实现和回归已经覆盖：

```text
固定 PNG 字节长度、尺寸、SHA-256 和象限像素合同稳定。
页面/HTTP 不能覆盖图片、prompt、model、URL、num_ctx、keep_alive 或 timeout。
只允许固定 loopback 11434；凭据、query、fragment、自定义 path、其他端口拒绝。
已有服务在线时 starter 零调用，且绝不停止已有服务。
只有明确 ConnectError 才启动；health 超时/畸形响应不盲目启动。
默认 start-ollama-vision.ps1 与 ensure-ollama.ps1 不被调用。
受管理进程提前退出、启动超时、就绪竞态和 ownership ambiguous 稳定映射。
模型缺失只失败，不 pull、不重启。
/api/ps 推理前后模型驻留识别，且不暴露其他模型名称。
模型原本已驻留时不发送 keep_alive=0、不卸载。
模型原本未驻留时发送 keep_alive=0，并要求推理后 /api/ps 不含该模型。
严格固定 /api/chat payload、一次调用、stream=false、无 tools、零 retry。
空回答、重复内容、超长、畸形 JSON/UTF-8/envelope、HTTP、超时和连接错误稳定映射。
只有精确满足固定 JSON/颜色语义合同才进入 succeeded；非空回答但合同不匹配仍进入 failed，不把“服务有响应”伪装成“识图正常”。
空回答、重复无效符号、无法启动服务、无法加载模型或未完成推理均稳定进入 failed，任何 attention 结果也不得显示为“诊断正常”。
模型 cleanup 不完整和持有服务 stop 不完整进入 attention。
cleanup 异常不跳过本次 Popen 收尾；已有服务永不停止。
DTO/日志不含 prompt、PNG、base64、回答、URL、路径、digest、原始响应、异常或其他模型名。
不读取 QQ/图片缓存/项目文件，不写数据库/reliability/Agent task/approval，不调用 LLM/RAG/TTS/视觉生产链。
五个手动工作流共享全局锁；关闭 403，并发 409；页面第一次零 POST，第二次恰好一个 POST。
```

自动化不得访问真实 11434、运行 `ollama` 命令、加载 GPU 模型、读取 `D:\OllamaModels` 真实 blobs、停止 Bot/Ollama 或读取任何真实图片。

### 18.12 实际最小实现与 live 门控

实际新增：

```text
src/plugins/ai_chat/owner_console_vision_inference.py
tests/test_owner_console_vision_inference.py
```

并最小扩展：

```text
owner_console_manual_diagnostics.py
owner_console_fastapi_app.py
owner_console_http_contract.py
scripts/start-owner-console.ps1
web Owner Console API types/client/DiagnosticsPage/guard/tests
```

不修改生产 `describe_images()`、QQ 图片缓存、VisionGraph、RootGraph、MainAgent planner、可靠性 observer 或现有 `/视觉状态` 的行为；如果后续认为旧 `/视觉状态` 的真实推理过于隐蔽，应另立兼容/迁移任务，不能夹带在 P2.49e 第一版中。

初版已经完成实现、回归与 Owner Console 加载；首次主人 live 后又完成收口验证修订。后续顺序必须是：

```text
1. 固定四色识图已经 live 通过；原模型收口仍严格记录为 attention，不能用稍后状态倒写原运行。
2. 5 秒有界 `/api/ps` 轮询修订当前为 implemented/regression_passed/loaded/not_relive。
3. Owner Console 已按主人批准重启为 PID 20276；五 workflow 启用且最近结果为空，重启未执行任何诊断。
4. 视觉复验仍由主人页面二次确认；不得自动连续执行 TTS 或其他工作流。
```

只有一次真实固定图片调用、固定语义合同、服务/模型所有权证据、资源收尾、零重试、零 QQ、零业务数据库写入和页面中英证据同时满足，P2.49e 才能以“基础视觉推理可用”收口。

### 18.13 实现证据

固定内存 PNG 的自动化快照为：

```text
contract_version=vision.fixed.v1
width=128
height=128
png_bytes=311
sha256=3d1f6c2a1b1b220a474cb49dcec96841decedf4c0892bfbd66f082bbd098ffcd
top_left=red
top_right=blue
bottom_left=green
bottom_right=white
separator=black
```

实现只在显式启用 `-EnableVisionInferenceProbe` 后加载动作能力；启动 Owner Console 本身不运行诊断。固定 POST 不接受图片、prompt、模型、URL、工具、`num_ctx`、`keep_alive` 或 timeout。executor 不导入生产 `vision.py`、QQ、RAG、数据库、reliability、MainAgent 或历史 DiagnosticsGraph，也不调用 `start-ollama-vision.ps1`、`ensure-ollama.ps1`、`ollama pull` 或 `ollama stop`。

结果 DTO 不返回 prompt、PNG/base64、模型回答、URL、模型路径/digest、原始响应、异常或其他模型名称。它明确区分：

```text
project_artifact_write_expected=false
external_runtime_local_write_possible=true
```

前者表示诊断不创建项目图片或业务产物；后者如实说明真实 Ollama 进程仍可能写自己的日志或缓存，不能宣称整个外部运行时零本地写入。

2026-07-24 fake-only 回归：

```text
Python 711 tests OK, skipped=4
Owner Console adjacent 99 tests OK, skipped=1
frontend 26 tests OK
RAG/QQ boundary 13 tests OK
TypeScript OK
Vite build OK
five fixed POST guard OK
Python AST 156 files OK
PowerShell parse OK
pip check OK
git diff --check OK
```

上述回归没有访问真实 `11434`、运行 `ollama`、读取 `D:\OllamaModels` blobs、加载 GPU 模型、读取真实图片或执行真实视觉推理；P2.49d TTS live 也没有发生。

### 18.14 首次视觉 live 与收口验证修订

主人首次真实执行结果为：

```text
workflow=vision_managed_lifecycle
outcome=attention
stage=result_validation
code=vision_model_cleanup_incomplete
configured_model=qwen2.5vl:3b
elapsed_ms=34656
inference_elapsed_ms=34392
cleanup_elapsed_ms=8
input_tokens=1103
output_tokens=32
total_tokens=1135
fixed_image_bytes=311
fixed_image_contract_valid=true
response_contract_valid=true
model_loaded_before=false
keep_alive_zero_used=true
model_cleanup_required=true
model_cleanup_verified=false
service_preexisting=true
service_stop_attempted=false
client_automatic_retry=false
```

该结果明确证明固定图片与识图合同通过；`attention` 只来自资源收口。初版在 `/api/chat` 返回后仅执行一次 `/api/ps`，本次检查耗时 8 ms，当时仍能看到目标模型。稍后的独立只读 `/api/ps` 已显示 `qwen2.5vl:3b` 不再驻留，支持 Ollama 卸载完成与即时检查之间存在短暂竞态；但这不能把原运行改写为 `succeeded`，因为原固定检查点确实没有确认释放。

主人批准的最小修订仅改变收口观测：当模型调用前未驻留且本次使用 `keep_alive=0` 时，在推理后最多 5 秒、每 250 ms 只读查询 `/api/ps`，目标模型消失即结束；新增 `model_cleanup_poll_count`，`cleanup_elapsed_ms` 覆盖整个窗口。修订不重复图片推理、不调用 `ollama stop`、不停止已有 Ollama、不卸载其他模型、不自动执行其他工作流。超过窗口或持续无法验证时，仍返回 `attention/vision_model_cleanup_incomplete`。

修订回归：视觉 executor 15 tests、Owner Console 手动诊断 17 tests、Python full 720 tests（skipped=4）、前端 29 tests、TypeScript、Vite build、固定动作 guard 与 `git diff --check` 通过。自动化覆盖立即释放、延迟 500 ms 释放、5 秒仍未释放和原本驻留不卸载；所有 `/api/chat` 调用计数仍为一次。本轮没有重新访问真实视觉模型、没有停止或重启 Ollama。随后按主人批准只重启 Owner Console；PID 20276 监听 8090，五 workflow 启用、最近结果为空，页面 HTTP 200。修订已加载但尚未再次 live。

### 18.15 v1 收口通过与 v2 固定表情描述质检

主人在收口轮询版本重新执行 v1，结果为：

```text
run_id=1
workflow=vision_managed_lifecycle
outcome=succeeded
stage=result_validation
code=vision_managed_lifecycle_succeeded
configured_model=qwen2.5vl:3b
elapsed_ms=8821
inference_elapsed_ms=8373
cleanup_elapsed_ms=284
input_tokens=1103
output_tokens=32
fixed_image_contract_valid=true
response_contract_valid=true
model_loaded_before=false
keep_alive_zero_used=true
model_cleanup_required=true
model_cleanup_verified=true
model_cleanup_poll_count=2
```

这证明 5 秒有界 `/api/ps` 轮询能够覆盖真实 Ollama 的短暂异步卸载：第一次检查后模型仍可能驻留，约 250 ms 后第二次检查确认消失。v1 的接口、固定请求、结构输出和资源收口由此完成 live。但后续审计确认 v1 固定 prompt 直接写出了 `grid=[red,blue,green,white]`，且 128×128 四色块与日常人物表情图片差异过大；它只能保留为基础传输和生命周期证据，不能继续作为内容理解质量终态。

主人批准在同一 `workflow=vision_managed_lifecycle` 内原地升级 v2，不增加第六个诊断面板。v2 固定合同：

```text
contract_version=vision.sticker.v1
sticker_id=aike_affection_005
source=data/stickers/library.json + approved/aike_affection_005.png
scope=owner_private
media_type=image/png
width=500
height=500
bytes=162977
animated=false
frame_count=1
manifest/hash/dimensions pinned=true
```

每次动作只读取正式 manifest 与这一张固定资产；不遍历或读取其他表情文件。资产必须仍为启用、owner_private、普通文件、位于固定 approved 边界，且文件名、MIME、尺寸、字节数和 SHA-256 精确匹配。禁用、替换、hash 漂移、路径越界、symlink/reparse、manifest 异常均在推理前返回 `failed/preflight/vision_reference_asset_unavailable`，不会回退随机选择其他图片。

v2 prompt 只列出字段和“根据实际可见内容选择”的规则，不包含正确主体、发色、眼睛、爱心或主题答案。固定 JSON Schema 提供多个合理枚举，后端私有期望为：

```json
{
  "contract_version": "vision.sticker.v1",
  "subject_type": "anime_character",
  "subject_count": 1,
  "hair_colors": ["black", "white"],
  "eye_color_family": "pink_red",
  "held_object": "heart",
  "floating_symbols": "hearts",
  "visual_theme": "affection",
  "description_zh": "<20–180 字自然中文描述>",
  "status": "ok"
}
```

字段必须完整且没有额外项；黑白发色允许顺序不同。中文描述至少包含 8 个汉字、长度 20–180、非空、非重复无效内容。结构事实或描述不合格仍为 failed；失败回答若存在，会经控制字符/双向控制符清理并在 2048 字符上限内进入当前进程结果，供主人观察，不能写数据库、文件、日志、聊天历史或 reliability event。

技术合同通过后不直接显示最终成功，而是：

```text
outcome=attention
stage=owner_visual_review
code=vision_response_quality_review_required
```

页面显示实际 `description_zh`、可展开的模型原始 JSON、固定结构事实和受保护参考图。参考图 GET 固定为：

```text
GET /api/v1/owner-console/manual-diagnostics/vision-inference/reference-preview
X-Owner-Console-Action: manual-vision-reference-preview-v1
Content-Type: image/png
Cache-Control: no-store
```

该 GET 不接受路径、sticker ID、URL、query 或 run 参数，只能返回固定登记且重新校验通过的 PNG。主人接受/拒绝使用两个不同的固定同源 POST，并绑定当前正整数 run_id：

```text
POST .../vision-inference/response-quality/accept
confirmation=accept_latest_vision_response_quality

POST .../vision-inference/response-quality/reject
confirmation=reject_latest_vision_response_quality
```

接受恢复底层 technical outcome/code，底层 cleanup/stop/usage/latency attention 不会被覆盖；拒绝返回 `failed/owner_visual_review/vision_response_quality_rejected`。重复审核或错误 run 返回冲突。两种审核均不调用 `/api/chat`、不加载/卸载模型、不停止服务、不写数据库/文件/reliability、不发送 QQ。

页面和 DTO 新增：

```text
reference_sticker_id
registered_reference_asset_read
expected_answer_disclosed_in_prompt=false
response_preview
response_description
response_content_exposed_to_owner
technical_outcome
technical_code
reference_preview_available
visual_quality_review_required
visual_quality_reviewed
visual_quality_accepted
visual_review_action_executed
response_preview_persisted=false
response_preview_path_exposed=false
reference_image_exposed_to_owner
```

这里对主人展示的是固定 owner_private 参考资产和本次固定输入产生的有限模型回答，不是聊天、QQ 临时图或图片缓存；旧 `image_content_exposed=false` 的笼统边界不再适用于 v2 页面，必须改为明确区分 `reference_image_exposed_to_owner` 与 QQ/缓存读取仍为 false。

v2 回归结果：

```text
vision executor 15 tests OK
manual diagnostics 17 tests OK
HTTP contract 3 tests OK
FastAPI app 22 tests OK
launcher 4 tests OK
Python full 720 tests OK, skipped=4
frontend 31 tests OK
TypeScript OK
Vite build OK
protected TTS/vision preview + nine fixed POST guard OK
```

实现与回归阶段没有执行真实视觉、停止/重启 Ollama、修改/复制/移动正式表情资产、读取其他图片或发送 QQ。主人随后批准只重启 Owner Console；新 PID 12960 监听 8090，五个 workflow 与 reference-preview、response-quality accept/reject 均注册，route_count=24，页面 HTTP 200。`latest_run=null`、`vision_inference_latest_run=null`，证明重启未执行诊断；Ollama PID 13412 保持不变，7861 未监听。该严格结构化版本随后完成主人 live 并因错识别失败；后续自然描述修订见 18.16。

### 18.16 严格结构化 live 失败与最小自然描述实验

主人在严格结构化版本执行固定正式表情诊断。模型与资源生命周期完成，但结果严格判为：

```text
workflow=vision_managed_lifecycle
outcome=failed
stage=result_validation
code=vision_response_contract_mismatch
configured_model=qwen2.5vl:3b
vision_called=true
response_contract_valid=false
model_cleanup_verified=true
```

模型结构字段中 `contract_version`、`subject_type`、`eye_color_family` 与 `visual_theme` 等返回 `unknown`；自然描述为“一个戴着黑色帽子和白色披风的卡通角色，眼睛被红色心形遮住。”。对照参考图，主要可见的是黑白双色头发而不是黑帽子/白披风，粉红红色眼睛仍可见而不是被爱心遮住。后端没有把“服务有响应”伪装成识图成功，也没有进入主人接受/拒绝阶段。模型收口已经验证，因此本次失败不能归因于资源未释放。

该结果不能单独证明错误一定由 prompt 导致；严格英文指令、十字段 JSON Schema 和多组枚举可能使 3B 视觉模型更偏向字段填充，是可检验假设。主人批准做严格单变量实验：

```text
固定不变：aike_affection_005、qwen2.5vl:3b、stream=false、num_ctx=4096、temperature=0、一次 /api/chat、keep_alive/收口、服务所有权与全部安全边界。
唯一主要变量：删除 format JSON Schema、字段清单、枚举和后端视觉事实比对。
最小请求：请用自然中文客观描述这张图片中实际可见的内容。
```

不能真正发送空 prompt，因为视觉聊天接口仍需要一条用户指令来说明任务；这里的“关掉提示词”落实为关闭结构化约束与答案式字段，只保留一句不包含视觉答案的中性请求。新请求 payload 不含 `format`，不含 tools，也不含人物、发色、眼睛、爱心或主题答案。

自动基础回复合同只验证：HTTP 200、`done=true`、assistant role、无 tool_calls、非空、最多 2048 字符、清理控制/双向字符后仍可读、不是重复乱码，并至少包含 8 个汉字。它不再判断人物、颜色、眼睛、物体或主题是否正确。即使一段自然中文语义明显不准确，也只表示基础回复合同通过，必须进入主人对照参考图的质量门控，不能自动成功。

新增证据：

```text
response_mode=natural_text
structured_output_requested=false
semantic_contract_automatically_validated=false
owner_visual_judgment_required=true
expected_answer_disclosed_in_prompt=false
```

页面把“识图合同”改为“基础回复合同”，把“模型原始 JSON”改为“模型原始回复”，并明确写出无 JSON Schema、语义由主人判断。主人接受/拒绝仍不再次调用视觉；服务、模型、数据库、QQ、RAG、TTS、Main LLM 与项目写入边界全部不变。

回归结果：视觉 executor 15 tests、手动诊断 17 tests、Python full 720 tests OK（skipped=4）、前端 4 files/31 tests、TypeScript 与 Vite production build 通过。测试使用 fake HTTP/process，没有访问真实 11434、调用视觉、停止/重启 Ollama 或 Owner Console、修改固定资产、发送 QQ、执行 LLM/RAG/TTS、commit 或 push。

production 前端 build 完成后，主人批准只重启 Owner Console。新 PID 27072 监听 127.0.0.1:8090，页面 HTTP 200；五个手动 workflow 与 24 条路由启用，`latest_run` 及五个专属最近结果全部为 null，证明重启未执行诊断。既有 Ollama PID 13412 继续监听 11434，7861 未监听；没有停止/重启 Ollama、TTS 或 Bot。当前状态为 natural_prompt_revision_implemented=true、regression_passed=true、loaded=true、live=false。下一步由主人页面二次确认执行一次并对照参考图接受或拒绝自然回复。

### 18.17 自然描述主人拒绝与独立百炼线上诊断设计

主人随后执行最小自然描述版。固定图片、一次本地 Ollama 请求、usage 和模型资源收口均完成：

```text
run_id=1
workflow=vision_managed_lifecycle
technical_outcome=succeeded
technical_code=vision_managed_lifecycle_succeeded
configured_model=qwen2.5vl:3b
elapsed_ms=11035
inference_elapsed_ms=10474
cleanup_elapsed_ms=296
input_tokens=1058
output_tokens=66
total_tokens=1124
response_contract_valid=true
response_mode=natural_text
structured_output_requested=false
semantic_contract_automatically_validated=false
model_cleanup_verified=true
model_cleanup_poll_count=2
```

模型回复仍把黑白双色长发描述为黑帽子和披风，把清晰可见的粉红红色眼睛描述为被心形遮住，对被下方大爱心遮挡的嘴部作了无依据判断，并把透明 PNG 区域描述为实体纯黑背景。主人执行质量拒绝后，最终结果严格更新为：

```text
outcome=failed
stage=owner_visual_review
code=vision_response_quality_rejected
visual_quality_reviewed=true
visual_quality_accepted=false
visual_review_action_executed=true
```

因此本地阶段的结论是：请求和资源生命周期正常，但这张固定复杂表情的描述质量不满足主人要求。关闭 JSON Schema 没有消除主要错识别，不能把问题简单归因于严格提示词；也不能把一次固定样本外推为任意图片或所有本地视觉任务都失败。

主人随后批准先设计阿里云百炼固定线上视觉诊断。该方向不原地替换本地 `vision_managed_lifecycle`，而是规划独立：

```text
workflow=cloud_vision_fixed_description
provider=aliyun_bailian
region=cn-beijing
model=qwen3.7-flash
enable_thinking=false
```

它沿用同一固定 `owner_private` PNG 和最小自然中文问题，只允许一次请求、零客户端重试、无 tools、无 thinking、无 RAG/TTS/Main LLM/QQ/数据库写入，并与现有手动诊断共享全局锁。基础回复合同通过后仍必须由主人对照参考图接受或拒绝；云端通过不证明本地 Ollama/GPU 正常，本地失败也不得自动触发云端或更贵模型。

该设计阶段当时只完成设计与配置说明，状态为 `owner_approved_design/designed/not_implemented/not_configured/not_live`；当时没有读取或配置 API Key，没有把图片发送给阿里云，没有调用模型、重启服务或修改 QQ 生产视觉链。该历史状态已由 18.18 更新；详细固定 endpoint、独立凭据、费用估算、图片外发确认、HTTP/DTO、错误码和分阶段批准合同见 [owner-console-cloud-vision-diagnostic-design.md](owner-console-cloud-vision-diagnostic-design.md)。

### 18.18 百炼隔离通过、云诊断原位替换与生产主视觉实现

18.17 的末段只记录设计刚完成时的状态，现已被主人后续逐步批准和以下事实更新。主人在私密 `.env` 中配置北京地域 OpenAI-compatible URL/API Key，并逐次批准用同一 `aike_affection_005` owner_private PNG 做三次隔离请求。最终固定 prompt 允许根据明确可见的表情、动作和画面元素概括情绪或感情色彩，同时禁止猜测遮挡或无法确认的细节。第三次 `qwen3.7-flash` 请求为 1578 ms，input/output/total token 316/98/414；回复正确覆盖黑白头发、可见眼睛、大小爱心和爱意/兴奋/撒娇，主人接受。响应开头的孤立 `</think>` 只做有限前导清理，没有第四次请求。

主人随后明确批准两个实现变化：

1. 生产 `describe_images()` 以百炼北京地域 `qwen3.7-flash` 为主要视觉回复模型；失败时不自动 fallback 到本地 Ollama 或 Plus。
2. Owner Console 不增加第六个视觉面板，而是原位替换旧的本地视觉配置/诊断面板；旧 `vision_managed_lifecycle` executor 和历史测试保留，但默认 UI/production factory 不再启用它。

云诊断固定为：

```text
workflow=cloud_vision_fixed_description
provider=aliyun_bailian
region=cn-beijing
configured_model=qwen3.7-flash
request_count=1
client_automatic_retry=false
tool_definitions_sent=false
thinking_enabled=false
automatic_local_fallback=false
```

页面原位显示阿里云百炼、北京地域、模型、URL/Key 是否配置、owner_private 外发说明、固定参考图、清理后模型回复、`response_cleanup_applied`、input/output/total token、请求耗时与主人接受/拒绝。页面不显示 URL/Key 原值，也没有图片上传、自由 prompt、模型、参数、fallback 或连续测试控件。

固定执行、预览、接受和拒绝路由分别为：

```text
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description
GET  /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/reference-preview
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject
```

这些路由沿用 loopback/same-origin、动作 Cookie、精确 Header/body 和全局锁合同。预览与主人接受/拒绝只读取或更新当前进程内结果，不再次调用模型。生产启动脚本入口改为 `-EnableCloudVisionProbe`；旧本地视觉路由代码保留但在 production factory 中禁用。

完整离线回归为 Python 734 tests OK（skipped=4）、手动诊断 19 tests、前端 31 tests、TypeScript、Vite build、只读 guard、AST、PowerShell parse、pip check 和 `git diff --check` 通过。fake FastAPI 测试证明缺 Cookie、非同源、错误 Header、额外 image/prompt 在 executor 前拒绝，审核不重跑。自动化没有读取真实 Key、发送图片、调用本地/线上模型、重启服务、执行 QQ/RAG 或修复 MemoryRAG。

当前严格状态为 `implemented/regression_passed/configured_privately/isolated_live_passed/owner_console_loaded/ui_smoke_passed/bot_loaded/qq_live_passed/owner_accepted`。2026-07-27 Owner Console PID 15220 的页面由主人确认无问题；Bot PID 24552/15332 加载生产主链后，主人连续发送两张 QQ 图片，均快速得到准确描述，同一 runtime 记录两次结构化 vision success。该结果不读取或持久化图片/回复正文，也不自动扩大到更多 live。
