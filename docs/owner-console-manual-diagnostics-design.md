# P2.49 Owner Console 手动诊断工作流设计

状态：P2.49a ProjectDocRAG 固定真实检索与 P2.49b MemoryRAG 索引一致性均已完成主人页面 live；P2.49b 发现 2 条活动事实文档缺少当前有效向量并正确归类为 attention，未自动修复。主人已确认 P2.49c 第一阶段只判断 Main LLM 能否正常运行并回答固定问题，不用一次诊断评价任意问题的工具选择；对应代码、fake 自动化、静态页面和主人页面 live 均已完成。真实调用一次完成并返回完整 token usage，主人确认基础运行成功；严格五字段 JSON 未通过并保留为 attention 证据，不影响第一阶段基础可用性收口。

设计日期：2026-07-21。

基线提交：`8f34819 Complete P2.47 reliability and pure-image workflows`。

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
P2.49d  TTS 探测专属进程、固定短文本真实合成和精确关闭。
P2.49e  视觉固定本地图片真实推理和模型资源收口。
```

页面只显示已经实现并启用的动作，不提前增加未来禁用按钮。

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
