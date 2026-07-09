# Web Owner Console read-only shell design

本文记录 P2.28 Web Owner Console 只读前端壳设计。当前阶段仍不实现真实前端，只定义未来第一版页面壳如何消费现有 Owner Console HTTP GET endpoints，以及如何保持只读、安全和命名一致。

后续实现状态：P2.29 已补充前端技术栈和目录边界设计，见 `docs/web-owner-console-frontend-stack-design.md`。截至该设计，仍不创建真实前端工程、不安装 npm 依赖、不修改 FastAPI 行为。

## 1. 定位

Web Owner Console read-only shell 是未来网页控制台的第一层 UI 壳，不是新的后端能力。

它的职责：

```text
提供固定页面地图。
调用已有 GET /api/v1/owner-console endpoints。
展示统一 HTTP envelope 中的 data / error。
展示 loading / empty / error / forbidden 状态。
把 read_only、http_api_enabled、web_write_enabled 等边界显示为系统状态。
让主人能从网页查看 Dashboard、任务、审批、诊断、记忆、访问控制和设置摘要。
```

它不负责：

```text
不新增后端 endpoint。
不开放 POST/PUT/PATCH/DELETE。
不确认审批。
不拒绝审批。
不恢复工具执行。
不新增登录/鉴权。
不直接调用 owner_write_runtime。
不发送 QQ 消息。
不触发 MainAgent。
不触发 MemoryRAG / ProjectDocRAG 检索。
不触发 diagnostics 主动探测。
```

这一步的关键是先把“页面如何读数据”定清楚，而不是抢先做页面。

## 2. 前端壳范围

第一版页面壳建议只包含：

```text
App Shell
Dashboard
Tasks
Task Detail
Approvals
Approval Detail
Diagnostics
Memory
Access Control
Settings
```

### 2.1 App Shell

App Shell 是所有页面共享的外壳：

```text
左侧导航。
顶部状态条。
当前资源标题。
后端连接状态。
只读状态标记。
最后刷新时间。
刷新按钮。
```

顶部状态条建议来自：

```text
GET /healthz
GET /api/v1/owner-console/routes
```

关键显示：

```text
service=owner-console
schema_version=owner_console.http.v1
api_prefix=/api/v1/owner-console
read_only=true
http_api_enabled=true
web_write_enabled=false
route_count=10
```

如果 `web_write_enabled=false`，前端不得渲染任何真实写操作入口。

### 2.2 Dashboard

对应页面：

```text
/owner-console
/owner-console/dashboard
```

调用：

```text
GET /api/v1/owner-console/overview?task_limit=5&approval_limit=5
GET /api/v1/owner-console/diagnostics
```

展示：

```text
runtime boundary。
pending tasks。
pending approvals。
failed tasks。
recent tasks。
pending approvals preview。
轻量 diagnostics snapshot。
```

状态处理：

```text
overview 返回 403 时显示 BOT_OWNER_QQ 未配置提示。
diagnostics 仍可展示，因为它不依赖 owner context。
```

### 2.3 Tasks

对应页面：

```text
/owner-console/tasks
```

调用：

```text
GET /api/v1/owner-console/tasks?status={status}&limit={limit}
```

query 控件：

```text
status segmented control:
  all
  pending
  running
  completed
  failed
  canceled

limit select:
  20
  50
  100
```

展示：

```text
task_id
title
goal_preview
status_label
latest_event_kind
latest_event_summary
pending_approval_ids
created_at
updated_at
next_action
```

点击行进入：

```text
/owner-console/tasks/{task_id}
```

v0 不显示：

```text
创建任务按钮。
取消任务按钮。
重新执行按钮。
批量操作按钮。
```

### 2.4 Task Detail

对应页面：

```text
/owner-console/tasks/{task_id}
```

调用：

```text
GET /api/v1/owner-console/tasks/{task_id}?event_limit=20&preview_limit=800
```

展示：

```text
任务基础信息。
goal。
result。
status。
事件时间线。
关联审批。
runtime boundary。
```

状态处理：

```text
400 bad_request：task_id 或 limit 非法。
403 forbidden：BOT_OWNER_QQ 未配置。
404 not_found：任务不存在，或不属于 owner 私聊上下文。
```

v0 不显示：

```text
取消任务。
继续任务。
重试任务。
编辑目标。
```

### 2.5 Approvals

对应页面：

```text
/owner-console/approvals
```

调用：

```text
GET /api/v1/owner-console/approvals?status={status}&limit={limit}
```

query 控件：

```text
status segmented control:
  all
  pending
  approved
  rejected
  expired

limit select:
  20
  50
  100
```

展示：

```text
approval_id
task_id
task_title
tool_name
risk_level
reason_preview
status_label
created_at
expires_at
decided_at
actionability.future_operation_only
actionability.blocked_reason
```

点击行进入：

```text
/owner-console/approvals/{approval_id}
```

v0 不显示真实：

```text
确认按钮。
拒绝按钮。
恢复执行按钮。
```

如果为了说明未来能力需要展示按钮，只能使用 disabled visual state，并显示 `future_operation_only=true`。

### 2.6 Approval Detail

对应页面：

```text
/owner-console/approvals/{approval_id}
```

调用：

```text
GET /api/v1/owner-console/approvals/{approval_id}?event_limit=5&preview_limit=800
```

展示：

```text
审批基础信息。
关联任务。
tool_name。
risk_level。
reason。
tool_input.preview_json。
tool_input.redacted。
tool_input.truncated。
recent_events。
actionability。
runtime boundary。
```

状态处理：

```text
400 bad_request：approval_id 或 limit 非法。
403 forbidden：BOT_OWNER_QQ 未配置。
404 not_found：审批不存在，或不属于 owner 私聊上下文。
```

强边界：

```text
前端不能根据 can_approve=true 自行发起写操作。
v0 actionability 只是只读元数据。
真实 approve/reject 需要后续单独设计 POST endpoint、鉴权和审计。
```

### 2.7 Diagnostics

对应页面：

```text
/owner-console/diagnostics
```

调用：

```text
GET /api/v1/owner-console/diagnostics
```

展示：

```text
bot_status.display_lines
diagnostics.display_lines
config.display_lines
vision.display_lines
image_cache.display_lines
memory.display_lines
tts.display_lines
recent_errors.display_lines
observations.main_agent
observations.root_graph
```

强边界：

```text
不显示“运行诊断”按钮。
不触发 OpenAI / Ollama / TTS / Vision 探测。
不读取最近错误日志。
不读取 QQ 图片缓存。
```

页面应明确展示这些 flags：

```text
external_probes_executed=false
diagnostics_module_imported=false
ollama_probe_executed=false
vision_inference_executed=false
tts_probe_executed=false
recent_error_log_read=false
```

### 2.8 Memory

对应页面：

```text
/owner-console/memory
```

调用：

```text
GET /api/v1/owner-console/memory
```

展示：

```text
counts。
context_policy。
memory_rag。
project_doc_rag。
runtime boundary。
```

强边界：

```text
不展示 message content。
不展示 long-term memory content。
不展示 ProjectDoc 内容。
不执行检索。
不重建索引。
不新增/删除记忆。
```

必须检查并可展示：

```text
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
```

### 2.9 Access Control

对应页面：

```text
/owner-console/access-control
```

调用：

```text
GET /api/v1/owner-console/access-control?item_limit=50
```

展示：

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

v0 不显示：

```text
添加白名单。
移除白名单。
加入黑名单。
解除拉黑。
```

### 2.10 Settings

对应页面：

```text
/owner-console/settings
```

调用：

```text
GET /api/v1/owner-console/settings
```

展示：

```text
chat_model。
main_agent_model。
embedding。
feature_flags。
role_cards。
runtime boundary。
```

强边界：

```text
只展示 api_key_configured。
只展示 base_url_redacted。
不展示 API key 原文。
不写 .env。
不切换角色卡。
不修改模型配置。
```

## 3. API 到页面映射

| Frontend page | HTTP endpoint | Owner context | Empty state | Error state |
| --- | --- | --- | --- | --- |
| App Shell | `GET /healthz` | no | service unavailable | backend offline |
| App Shell | `GET /api/v1/owner-console/routes` | no | no routes enabled | contract error |
| Dashboard | `GET /api/v1/owner-console/overview` | yes | no visible tasks | 403 owner missing |
| Dashboard | `GET /api/v1/owner-console/diagnostics` | no | no observations | diagnostics snapshot error |
| Tasks | `GET /api/v1/owner-console/tasks` | yes | no tasks | 403 owner missing |
| Task Detail | `GET /api/v1/owner-console/tasks/{task_id}` | yes | not applicable | 400 / 403 / 404 |
| Approvals | `GET /api/v1/owner-console/approvals` | yes | no approvals | 403 owner missing |
| Approval Detail | `GET /api/v1/owner-console/approvals/{approval_id}` | yes | not applicable | 400 / 403 / 404 |
| Diagnostics | `GET /api/v1/owner-console/diagnostics` | no | no observations | snapshot error |
| Memory | `GET /api/v1/owner-console/memory` | no | zero counts | snapshot error |
| Access Control | `GET /api/v1/owner-console/access-control` | no | empty lists | snapshot error |
| Settings | `GET /api/v1/owner-console/settings` | no | no role cards | snapshot error |

## 4. HTTP envelope handling

所有页面都应先检查 envelope，而不是直接假设 `data` 存在。

通用 envelope：

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

客户端通用规则：

```text
schema_version 必须为 owner_console.http.v1。
transport 必须为 http。
api_prefix 必须为 /api/v1/owner-console。
read_only 必须为 true。
http_api_enabled 必须为 true。
web_write_enabled 必须为 false。
error 为 null 时渲染 data。
error 非 null 时渲染错误态，不渲染旧 data。
```

如果 `web_write_enabled` 不是 `false`，第一版前端应进入保护态：

```text
停止渲染任何 action 控件。
显示 contract mismatch。
提示需要重新审计前端壳。
```

## 5. 状态模型

每个页面使用同一组 UI 状态：

```text
idle
loading
success
empty
bad_request
forbidden
not_found
server_error
network_error
contract_mismatch
```

HTTP status 映射：

```text
200 -> success 或 empty
400 -> bad_request
403 -> forbidden
404 -> not_found
405 -> contract_mismatch 或 method_not_allowed diagnostic
500 -> server_error
network failure -> network_error
```

`empty` 不是错误：

```text
tasks.rows=[]
approvals.rows=[]
observations=[]
access list count=0
memory counts=0
```

## 6. 客户端 API 命名建议

前端内部可以使用清晰的 resource client 命名，避免项目名和 endpoint 名散乱：

```text
ownerConsoleApi.getHealth()
ownerConsoleApi.getRoutes()
ownerConsoleApi.getOverview({ task_limit, approval_limit })
ownerConsoleApi.getTasks({ status, limit })
ownerConsoleApi.getTaskDetail(task_id, { event_limit, preview_limit })
ownerConsoleApi.getApprovals({ status, limit })
ownerConsoleApi.getApprovalDetail(approval_id, { event_limit, preview_limit })
ownerConsoleApi.getDiagnostics()
ownerConsoleApi.getMemory()
ownerConsoleApi.getAccessControl({ item_limit })
ownerConsoleApi.getSettings()
```

路径仍固定遵守：

```text
/api/v1/owner-console
lowercase kebab-case path segment
snake_case query params
snake_case JSON fields
```

## 7. 刷新策略

第一版只做显式刷新，不做自动轮询：

```text
页面打开时请求一次。
用户点击刷新按钮时重新请求。
详情页从列表进入时请求详情。
```

暂不做：

```text
自动轮询。
WebSocket。
Server-Sent Events。
后台静默刷新。
```

原因：

```text
只读壳先验证 DTO 和页面映射。
避免频繁读取让日志和调试变复杂。
未来如要实时状态，应先设计刷新频率、错误退避和可见性策略。
```

## 8. 安全与隐私检查清单

第一版前端壳必须遵守：

```text
只调用 GET。
只调用 /healthz 和 /api/v1/owner-console/*。
不把 owner id / session_key 放入 query。
不从 URL 接收 user_id / session_key。
不展示 API key。
不展示 token / cookie。
不展示 message content。
不展示 long-term memory content。
不展示 ProjectDoc content。
不展示完整未脱敏 tool input。
不提供写按钮。
不提供 diagnostics 主动探测按钮。
```

页面 review 时必须检查：

```text
所有 actionability 都是只读展示。
所有 disabled future action 都不会绑定 click handler。
所有 request 都是 GET。
所有 request path 都在 allowlist 内。
所有错误态都不会误导用户“已经执行”。
```

## 9. 第一版完成标准

未来真正开始实现只读前端壳时，第一版完成标准建议为：

```text
1. App Shell 能显示 /healthz 和 /routes 状态。
2. Dashboard 能读取 overview 和 diagnostics。
3. Tasks / Task Detail 能读取列表和详情。
4. Approvals / Approval Detail 能读取列表和详情。
5. Diagnostics / Memory / Access Control / Settings 能读取对应 snapshot。
6. 所有页面都有 loading / empty / error 状态。
7. 所有页面确认 web_write_enabled=false。
8. 没有任何 POST/PUT/PATCH/DELETE。
9. 没有真实写按钮。
10. 没有登录/鉴权假实现。
11. 不修改 FastAPI 后端行为。
```

## 10. 后续路线

建议后续路线：

```text
P2.29：选择前端技术栈和目录边界，只做讨论/设计。
P2.30：实现最小 read-only App Shell，先只接 /healthz 和 /routes。
P2.31：接 Dashboard / Tasks / Approvals。
P2.32：接详情页和浅层快照页。
P2.33：再讨论登录/鉴权设计。
P2.34：再讨论审批操作设计。
```

不建议下一步直接做：

```text
登录系统。
审批按钮。
写操作 API。
前端自动轮询。
公网部署。
```

这些能力都需要单独设计和审计，不能混在只读壳里。
