# Web Owner Console read-model 设计

本文记录 P2.6 Web Owner Console read-model 设计。当前阶段只做设计，不写前端、不接 HTTP、不做登录鉴权、不改数据库 schema、不改变 `/agent`、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。

后续实现状态：P2.16-P2.24 已经基于本文的 read model 落地本地只读 FastAPI adapter。P2.6 的“不接 HTTP”描述指当时的设计阶段边界；当前 HTTP surface 审计见 `docs/owner-console-http-surface-audit.md`。P2.28 已补充未来只读前端壳的页面到 API 映射，见 `docs/web-owner-console-read-only-shell-design.md`。截至该设计，Owner Console 仍不做真实前端、不做登录鉴权、不开放 Web 写操作。

## 1. Web Owner Console v0 定位

Web Owner Console v0 是未来主人控制台的只读数据契约设计，不是前端页面实现，也不是 HTTP API 设计。

v0 目标：

```text
定义未来 Web Owner Console 需要哪些页面。
定义每个页面需要哪些结构化 read model。
说明这些 read model 如何复用现有 owner runtime service 和持久化查询能力。
明确只读边界，避免未来 Web 入口绕过现有 /agent 和审批恢复安全链路。
```

v0 不做：

```text
不做真实网页。
不接 HTTP API。
不做登录、鉴权、会话管理。
不新增数据库表。
不做 Web 写操作。
不做审批确认按钮。
不执行 shell。
不做任意文件写入。
不做未注册数据库写入。
不新增额外 QQ 发送副作用。
不开放多步写自动化。
```

Web Owner Console 的长期方向是成为 `/agent` 主人控制台的另一个只读入口。它不替代 QQ adapter，也不把 NoneBot handler 暴露给 Web。Web 入口应复用 handler 背后的稳定 service、Graph runner 和持久化查询函数。

## 2. 现有 QQ 文本输出后端形态

当前 `/agent` 的 QQ 输出最终都是 `str`，由 NoneBot matcher 发送：

```text
QQ /agent 命令
  -> run_main_agent_qq_command(...)
  -> OwnerRuntimeFactory
  -> owner_agent_runtime / owner_read_runtime / owner_write_runtime
  -> 返回 str
  -> matcher.finish(reply)
```

现有文本输出主要来自三类后端形式。

### 2.1 lines provider

部分只读状态函数返回 `list[str]`，再由 `owner_read_runtime` 拼成文本：

```text
role_card_list_lines()
model_config_status_lines()
access_overview_lines()
rag_index_detail_lines()
main_agent_observation_lines()
root_graph_observation_lines()
```

这些函数适合 QQ 展示，但它们仍是展示文本，不是 Web read model。Web 可以短期保留 `display_lines` 作为过渡字段，但不应把它作为长期接口。

### 2.2 Graph execution reply_text

诊断、MemoryRAG 和 MemoryAdmin 当前通过 Graph runner 返回 execution，再取 `execution.result.reply_text`：

```text
run_diagnostics(...)
run_memory_retrieval(...)
run_memory_admin(...)
```

这类输出已经由 Graph 聚合过状态，但对 `/agent` 来说仍是一段 QQ 文本。未来 Web read model 应优先复用 Graph result 中的结构化状态；如果 Graph result 暂时没有结构化字段，可以先以 `summary_text` 过渡。

### 2.3 task / approval formatter

任务和审批底层已有结构化 dataclass：

```text
AgentTask
AgentTaskEvent
AgentApproval
```

但当前 QQ 输出会立刻进入 formatter：

```text
format_agent_task_list(tasks) -> str
format_agent_task_detail(task, events, approvals) -> str
format_agent_approval_list(approvals) -> str
format_agent_approval_detail(approval, task, events) -> str
format_agent_task_workbench(...) -> str
```

Web Console 不应解析这些 formatter 的文本。任务、审批页面应直接复用 `AgentTask`、`AgentTaskEvent`、`AgentApproval` 以及对应查询函数，构建结构化 read model。

结论：

```text
当前 QQ 后端形式 = 结构化数据/服务结果 -> QQ 文本 formatter -> str。
Web read model 应复用 str 之前的结构化来源，而不是复用最终 QQ 文本。
```

## 3. 页面地图

v0 页面分为“必须清楚”和“浅层快照”两层。

### 3.1 v0 必须清楚

```text
Dashboard
Tasks
Task Detail
Approvals
Approval Detail
Diagnostics
Access Control
```

这些页面最能验证 owner runtime service 解耦价值。它们主要复用任务/审批持久化查询、诊断只读能力、访问控制只读能力和现有 owner runtime 装配边界。

### 3.2 v0 浅层快照

```text
Memory
Settings
```

这两个页面先做只读摘要，不在 P2.6 深挖完整操作面。原因是 Memory 牵涉 MemoryRAG、MemoryAdmin、摘要、长期记忆和隐私边界；Settings 牵涉模型配置、角色卡、功能开关和潜在 secret 脱敏。v0 只定义摘要 read model，不设计修改能力。

## 4. 页面数据需求

### 4.1 Dashboard

用途：给主人一个系统当前状态总览。

需要数据：

```text
运行边界摘要。
MainAgent 是否开启。
MainAgent 是否 owner-only。
MainAgent LLM 是否开启。
普通聊天和 MainAgent 分离状态。
pending task 数量。
pending approval 数量。
failed task 数量。
最近任务摘要。
最近待审批摘要。
诊断健康摘要。
最近 MainAgent 观测摘要。
最近 RootGraph 观测摘要。
访问控制摘要。
MemoryRAG / ProjectDocRAG 边界摘要。
```

推荐 read model：

```text
OwnerConsoleOverview
OwnerConsoleRuntimeBoundary
OwnerConsoleHealthSnapshot
OwnerConsoleAccessControlSnapshot
```

### 4.2 Tasks

用途：查看任务列表、状态分布和下一步关注点。

需要数据：

```text
任务 ID。
标题。
目标摘要。
状态。
创建时间。
更新时间。
最近事件摘要。
是否存在 pending approval。
关联 pending approval IDs。
下一步提示。
```

支持的只读筛选：

```text
status
limit
sort=updated_at_desc
```

v0 不做：

```text
不创建任务。
不取消任务。
不重新执行任务。
不批量操作任务。
```

推荐 read model：

```text
OwnerConsoleTaskList
OwnerConsoleTaskRow
```

### 4.3 Task Detail

用途：查看单个任务完整脉络。

需要数据：

```text
任务基础字段。
任务目标。
任务结果。
状态。
创建时间。
更新时间。
事件列表。
关联审批列表。
下一步提示。
审批恢复边界提示。
```

推荐 read model：

```text
OwnerConsoleTaskDetail
OwnerConsoleTaskEventRow
OwnerConsoleApprovalRow
```

### 4.4 Approvals

用途：查看审批列表，尤其是待确认项。

需要数据：

```text
审批 ID。
任务 ID。
任务标题。
工具名。
风险等级。
原因摘要。
状态。
创建时间。
过期时间。
决定时间。
是否 pending。
只读 actionability metadata。
```

`actionability metadata` 是未来按钮状态的只读描述，不代表 v0 已支持操作：

```text
can_approve
can_reject
resume_enabled
blocked_reason
```

v0 可以先将这些字段定义为可选或 unknown。未来真正实现时，必须从 approval status、tool registry 和 `approval_resume_enabled` 计算，不能仅由前端判断。

v0 不做：

```text
不确认审批。
不拒绝审批。
不恢复工具。
不直接调用 owner_write_runtime。
```

推荐 read model：

```text
OwnerConsoleApprovalList
OwnerConsoleApprovalRow
```

### 4.5 Approval Detail

用途：查看单个审批的风险、输入摘要、关联任务和恢复边界。

需要数据：

```text
审批基础字段。
任务基础字段。
工具名。
风险等级。
策略原因。
工具输入摘要。
工具输入脱敏预览。
状态。
创建时间。
过期时间。
决定时间。
相关任务事件。
只读 actionability metadata。
审批恢复边界说明。
```

工具输入处理原则：

```text
默认展示摘要，不展示完整原始 JSON。
不得泄露 API Key、token、cookie、私有配置值。
对可能包含长文本或隐私内容的参数做截断。
必要时提供 has_more / redacted 字段，而不是把原文全部塞给前端。
```

推荐 read model：

```text
OwnerConsoleApprovalDetail
OwnerConsoleApprovalActionability
```

### 4.6 Diagnostics

用途：只读查看系统运行状态和最近错误。

需要数据：

```text
bot 状态。
配置状态。
视觉状态。
图片缓存状态。
记忆状态。
TTS 状态。
最近错误摘要。
MainAgent 最近观测。
RootGraph 最近观测。
ops health 摘要。
```

复用来源：

```text
OwnerReadRuntime.run_diagnostics
bot_status_lines
main_agent_observation_lines
root_graph_observation_lines
ops_health_reply
```

v0 可以保留 `summary_text` 和 `display_lines` 作为过渡，但长期应逐步从 DiagnosticsGraph result 暴露结构化字段。

推荐 read model：

```text
OwnerConsoleHealthSnapshot
OwnerConsoleObservationSnapshot
```

### 4.7 Memory

用途：浅层查看记忆和索引状态。

需要数据：

```text
MemoryRAG 是否开启。
MemoryRAG 索引状态摘要。
摘要状态。
长期记忆数量摘要。
最近检索健康状态。
ProjectDocRAG 与 QQ 普通聊天隔离说明。
```

边界：

```text
Memory 页面 v0 只做状态快照。
不做记忆新增。
不做记忆删除。
不做摘要清空。
不做索引重建。
不把 ProjectDocRAG 注入普通聊天。
不展示不必要的隐私正文。
```

推荐 read model：

```text
OwnerConsoleMemorySnapshot
```

### 4.8 Access Control

用途：只读查看访问控制状态。

需要数据：

```text
owner 是否配置。
owner-only 策略。
私聊是否开启。
群聊是否开启。
未知私聊策略。
私聊白名单摘要。
群白名单摘要。
黑名单摘要。
动态名单来源说明。
```

复用来源：

```text
current_access()
access_overview_lines()
list_lines(...)
```

Web read model 应直接基于访问控制对象生成结构化字段，`access_overview_lines()` 可作为过渡展示。

v0 不做：

```text
不添加白名单。
不移除白名单。
不加入黑名单。
不解除拉黑。
```

推荐 read model：

```text
OwnerConsoleAccessControlSnapshot
OwnerConsoleAccessList
```

### 4.9 Settings

用途：浅层查看运行配置，不修改配置。

需要数据：

```text
模型配置摘要。
base_url 脱敏展示。
API Key 是否配置，不展示 Key 原文。
超时配置。
角色卡列表。
当前角色卡 key 和标题。
MainAgent feature flags。
Vision / TTS / MemoryRAG 关键配置摘要。
```

边界：

```text
不切换角色卡。
不修改模型。
不展示 secret。
不写 .env。
不修改运行时配置。
```

推荐 read model：

```text
OwnerConsoleSettingsSnapshot
OwnerConsoleRuntimeBoundary
```

## 5. read model 结构草案

以下是结构草案，不是本阶段要落地的 Python 类型。字段可以在后续实现时按实际 Graph result 和持久化查询函数微调。

### 5.1 通用约定

```text
generated_at: str
scope:
  session_key: str
  user_id: str
source:
  service: str
  command: str | None
display_text: str | None
display_lines: list[str]
warnings: list[str]
```

约定：

```text
display_text / display_lines 只作为过渡展示字段。
结构化字段优先于 QQ 文本。
所有 secret 必须脱敏。
所有长文本必须有截断策略。
所有写操作能力只能以 disabled / future metadata 表示，不能在 v0 暗中执行。
```

### 5.2 OwnerConsoleRuntimeBoundary

```text
OwnerConsoleRuntimeBoundary
  main_agent_entry: "/agent explicit owner entry only"
  ordinary_chat_can_trigger_main_agent: false
  project_doc_rag_in_ordinary_chat: false
  shell_tools_exposed: false
  arbitrary_file_write_allowed: false
  unregistered_db_write_allowed: false
  owner_write_requires_approval: true
  approval_resume_requires_registered_tool: true
  approval_resume_requires_enabled_tool: true
  multi_step_write_automation_allowed: false
  extra_qq_send_side_effect_allowed: false
```

### 5.3 OwnerConsoleOverview

```text
OwnerConsoleOverview
  generated_at: str
  boundary: OwnerConsoleRuntimeBoundary
  main_agent:
    enabled: bool
    owner_only: bool
    use_llm: bool
  counters:
    pending_tasks: int
    failed_tasks: int
    pending_approvals: int
  recent_tasks: list[OwnerConsoleTaskRow]
  recent_approvals: list[OwnerConsoleApprovalRow]
  health: OwnerConsoleHealthSnapshot
  access: OwnerConsoleAccessControlSnapshot
  memory: OwnerConsoleMemorySnapshot
  observations:
    main_agent: list[str]
    root_graph: list[str]
```

### 5.4 OwnerConsoleTaskList

```text
OwnerConsoleTaskList
  generated_at: str
  filters:
    status: str | None
    limit: int
  total_visible: int
  rows: list[OwnerConsoleTaskRow]
  boundary: OwnerConsoleRuntimeBoundary

OwnerConsoleTaskRow
  task_id: int
  title: str
  goal_preview: str
  status: str
  status_label: str
  result_preview: str
  created_at: str
  updated_at: str
  latest_event_kind: str
  latest_event_summary: str
  pending_approval_ids: list[int]
  next_action: str
```

### 5.5 OwnerConsoleTaskDetail

```text
OwnerConsoleTaskDetail
  generated_at: str
  task:
    task_id: int
    title: str
    goal: str
    status: str
    status_label: str
    result: str
    created_at: str
    updated_at: str
  events: list[OwnerConsoleTaskEventRow]
  approvals: list[OwnerConsoleApprovalRow]
  next_action: str
  boundary: OwnerConsoleRuntimeBoundary

OwnerConsoleTaskEventRow
  event_id: int
  task_id: int
  step_index: int
  kind: str
  tool_name: str
  input_preview: str
  output_summary: str
  status: str
  status_label: str
  error: str
  created_at: str
```

### 5.6 OwnerConsoleApprovalList

```text
OwnerConsoleApprovalList
  generated_at: str
  filters:
    status: str | None
    limit: int
  total_visible: int
  rows: list[OwnerConsoleApprovalRow]
  boundary: OwnerConsoleRuntimeBoundary

OwnerConsoleApprovalRow
  approval_id: int
  task_id: int
  task_title: str
  tool_name: str
  risk_level: str
  reason_preview: str
  status: str
  status_label: str
  created_at: str
  expires_at: str
  decided_at: str
  actionability: OwnerConsoleApprovalActionability
```

### 5.7 OwnerConsoleApprovalDetail

```text
OwnerConsoleApprovalDetail
  generated_at: str
  approval:
    approval_id: int
    task_id: int
    task_title: str
    tool_name: str
    risk_level: str
    reason: str
    status: str
    status_label: str
    created_at: str
    expires_at: str
    decided_at: str
  tool_input:
    preview_json: str
    redacted: bool
    truncated: bool
  task: OwnerConsoleTaskRow | None
  recent_events: list[OwnerConsoleTaskEventRow]
  actionability: OwnerConsoleApprovalActionability
  boundary: OwnerConsoleRuntimeBoundary

OwnerConsoleApprovalActionability
  can_approve: bool
  can_reject: bool
  resume_enabled: bool | None
  blocked_reason: str
  future_operation_only: bool
```

v0 中 `future_operation_only` 固定为 `true`。这表示 read model 可以描述未来操作状态，但当前 Web v0 不执行任何操作。

### 5.8 OwnerConsoleHealthSnapshot

```text
OwnerConsoleHealthSnapshot
  generated_at: str
  bot_status:
    display_lines: list[str]
  diagnostics:
    status: str
    summary_text: str
  config:
    summary_text: str
  vision:
    summary_text: str
  memory:
    summary_text: str
  tts:
    summary_text: str
  recent_errors:
    summary_text: str
  observations:
    main_agent: list[str]
    root_graph: list[str]
```

该模型允许短期保留文本摘要。后续如果 DiagnosticsGraph result 暴露结构化字段，再逐步替换 `summary_text`。

### 5.9 OwnerConsoleMemorySnapshot

```text
OwnerConsoleMemorySnapshot
  generated_at: str
  memory_rag:
    enabled: bool | None
    status_text: str
  summaries:
    status_text: str
  long_term_memory:
    status_text: str
    item_count: int | None
  project_doc_rag_boundary:
    only_explicit_agent_dev_context: true
    ordinary_chat_injection_allowed: false
```

### 5.10 OwnerConsoleAccessControlSnapshot

```text
OwnerConsoleAccessControlSnapshot
  generated_at: str
  owner_configured: bool
  private_chat_enabled: bool
  group_chat_enabled: bool
  unknown_private_policy: str
  group_whitelist: OwnerConsoleAccessList
  private_whitelist: OwnerConsoleAccessList
  user_blacklist: OwnerConsoleAccessList
  display_lines: list[str]

OwnerConsoleAccessList
  label: str
  count: int
  items: list[str]
  truncated: bool
```

### 5.11 OwnerConsoleSettingsSnapshot

```text
OwnerConsoleSettingsSnapshot
  generated_at: str
  model_config:
    model_name: str
    base_url_redacted: str
    api_key_configured: bool
    timeout_seconds: float | None
  role_cards:
    current_key: str
    rows:
      - key: str
        title: str
        active: bool
  feature_flags:
    main_agent_enabled: bool
    main_agent_use_llm: bool
    memory_rag_enabled: bool | None
    vision_enabled: bool | None
    tts_enabled: bool | None
  boundary: OwnerConsoleRuntimeBoundary
```

## 6. 复用现有 Runtime service 的方式

### 6.1 任务和审批

优先复用：

```text
list_agent_tasks
get_agent_task
list_agent_task_events
latest_agent_task_event
list_agent_approvals
get_agent_approval
agent_task_status_label
agent_approval_status_label
```

不建议 Web read model 复用：

```text
format_agent_task_list
format_agent_task_detail
format_agent_approval_list
format_agent_approval_detail
```

原因是这些 formatter 是 QQ 展示层。Web 需要结构化字段，而不是解析文本。

### 6.2 owner_agent_runtime

`owner_agent_runtime.py` 已经把任务和审批 runtime 从 QQ adapter 中拆出，并使用 `OwnerAgentContext(session_key, user_id)`。这适合作为未来 Web read model 的上下文参考。

但当前 `format_owner_agent_task_read(...)` 返回 `str`。未来如要落地 Web read model，建议在相邻层新增结构化 builder，而不是改破现有 QQ formatter：

```text
build_owner_console_task_list(context) -> OwnerConsoleTaskList
build_owner_console_task_detail(context, task_id) -> OwnerConsoleTaskDetail
build_owner_console_approval_list(context) -> OwnerConsoleApprovalList
build_owner_console_approval_detail(context, approval_id) -> OwnerConsoleApprovalDetail
```

### 6.3 owner_read_runtime

`owner_read_runtime.py` 当前负责只读命令分发，依赖通过 `OwnerReadRuntime` 注入。未来 Web Console 可以复用同一组依赖，但不应长期复用最终 `str`。

短期过渡：

```text
复用 bot_status_lines / access_overview_lines / rag_index_detail_lines 等 lines provider。
复用 run_diagnostics / run_memory_retrieval / run_memory_admin 的 reply_text。
将文本放入 display_lines / summary_text。
```

长期方向：

```text
DiagnosticsGraph、MemoryRAG、AccessControl 等模块逐步提供结构化 snapshot。
OwnerConsole read model builder 聚合 snapshot。
QQ formatter 和 Web read model 共享底层 snapshot，而不是互相解析展示文本。
```

### 6.4 owner_runtime_factory

`owner_runtime_factory.py` 已经证明 task/read/write runtime 可以通过依赖注入组装。未来 Web Owner Console 可以延续这个模式。

建议未来模块名：

```text
owner_console_read_runtime.py
  组装 Web Owner Console 只读 read model。
  不依赖 MessageEvent。
  不调用 matcher.finish / bot.send。
  不执行写操作。

owner_console_read_models.py
  如果 DTO 增多，可拆出 dataclass / TypedDict 定义。
```

这只是建议命名，P2.6 不创建这些文件。

### 6.5 owner_write_runtime

Web Owner Console v0 不调用 `owner_write_runtime.py`。

未来即使支持审批确认，也不能让 Web 直接调用具体写函数。Web 只能提交审批决定，审批通过后的恢复必须继续走现有 approval resume registry 和 `owner_write_runtime`。

## 7. 暂不做的能力边界

P2.6 和 Web Owner Console v0 明确不做：

```text
不写前端。
不接 HTTP。
不加登录。
不设计 token / cookie / session。
不新增数据库表。
不改变 agent_tasks schema。
不改变 /agent 命令输出。
不改变普通聊天行为。
不改变审批恢复行为。
不改变 MemoryRAG 注入边界。
不改变 Diagnostics 输出。
不改变 QQ 命令行为。
不新增工具能力。
不执行 Web 写操作。
不新增 QQ 发送副作用。
```

安全边界继续保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent。
MainAgent 和 ChatAgent 继续保持分离。
ProjectDocRAG 只允许在显式 /agent dev_context 中使用，不能进入普通聊天。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复执行。
不开放多步写自动化。
```

## 8. 从只读到审批操作的升级路线

Web Owner Console 的写操作必须分阶段进入，不能从 v0 直接变成任意控制台。

### 8.1 v0：全只读

```text
展示 Dashboard。
展示任务和审批。
展示诊断、记忆、访问控制、设置摘要。
不提供确认/拒绝按钮。
不调用 owner_write_runtime。
不改变任何数据库状态。
```

### 8.2 v0.1：只读 actionability metadata

```text
Approval read model 可以展示 can_approve / can_reject / resume_enabled / blocked_reason。
这些字段只用于未来 UI 状态，不执行操作。
resume_enabled 必须由 tool registry 和 approval_resume_enabled 计算。
前端不能自行推断工具是否可恢复。
```

### 8.3 v1：审批决定入口

如果未来 Web 支持确认/拒绝审批，只允许提交审批决定：

```text
approval_id
decision=approve | reject
```

正确链路：

```text
Web approval decision
  -> 与 /agent 确认/拒绝 相同的审批决策服务
  -> decide_agent_approval(...)
  -> resume_agent_approval(...)
  -> approval resume tool registry
  -> approval_resume_enabled=true 检查
  -> owner_write_runtime
  -> agent task event 幂等记录
```

禁止链路：

```text
Web button -> clear_image_cache()
Web button -> add_access_item()
Web button -> delete_session_summary()
Web button -> 任意工具函数
```

也就是说，Web 未来可以成为审批入口，但不能成为绕过审批的写入口。

### 8.4 v1 later：有限协作能力

可考虑：

```text
创建任务。
取消任务。
审批备注。
任务筛选和收藏。
更完整的 Diagnostics 结构化快照。
```

仍不开放：

```text
多步自动写执行。
任意 shell。
任意文件写入。
未注册数据库写入。
额外 QQ 发送副作用。
```

## 9. P2.6 完成标准

P2.6 完成标准：

```text
1. 定义 Web Owner Console v0 定位。
2. 明确页面地图，并区分 v0 必须清楚和 v0 浅层快照。
3. 说明现有 QQ 文本输出后端形态。
4. 给出结构化 read model 草案。
5. 说明如何复用 owner runtime service 和现有查询函数。
6. 明确暂不做的能力边界。
7. 写清从只读到审批操作的升级路线。
8. 不修改运行时代码行为。
```

当前建议下一步：

```text
先审阅本文档字段边界。
如果确认进入实现阶段，再新增 owner_console_read_runtime.py 的只读 builder。
第一批实现优先选择 Tasks / Approvals / Dashboard。
Diagnostics、Memory、Settings 保持文本摘要过渡，后续逐步结构化。
```
