# Owner Console HTTP surface audit

本文记录 P2.25 Owner Console HTTP surface 审计。目标是把 P2.16-P2.24 已经落地的只读 FastAPI 后端面统一盘点清楚，避免后续接前端、鉴权或审批操作时把边界弄乱。

当前结论：

```text
Owner Console HTTP v0 已经具备完整只读资源面。
它仍然不是 Web 前端。
它仍然不做登录/鉴权。
它仍然不开放写操作。
它仍然不替代 QQ / NoneBot adapter。
它仍然不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

本地启动和 smoke 验证流程见：

```text
docs/owner-console-fastapi-smoke-runbook.md
```

未来只读前端壳的页面到 API 映射见：

```text
docs/web-owner-console-read-only-shell-design.md
```

未来前端技术栈和目录边界见：

```text
docs/web-owner-console-frontend-stack-design.md
```

未来 UI 布局和中文化展示规则见：

```text
docs/web-owner-console-ui-layout-design.md
```

## 1. 实现定位

Owner Console HTTP v0 是 Web Owner Console read model 的本地 HTTP adapter。它只负责：

```text
接收 HTTP GET 请求。
解析 path/query 参数。
从本地配置构造 owner console context 或 provider。
调用 OwnerConsoleReadRuntime。
把 read model 包成稳定 HTTP envelope。
返回 JSON。
```

它不负责：

```text
不渲染 HTML / 前端页面。
不做登录、鉴权、cookie、session。
不接 POST/PUT/PATCH/DELETE。
不调用 OwnerWriteRuntime。
不确认/拒绝审批。
不恢复工具执行。
不发送 QQ 消息。
不 import src/plugins/ai_chat/__init__.py。
不把 QQ 文本 formatter 当作 Web 数据源。
```

## 2. 启动入口

推荐启动入口：

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

不要直接使用：

```text
uvicorn src.plugins.ai_chat.owner_console_fastapi_app:app
```

原因：

```text
src.plugins.ai_chat 是 NoneBot/QQ 插件包。
直接按普通包导入可能执行 src/plugins/ai_chat/__init__.py。
Owner Console HTTP adapter 必须保持 side-effect-free import boundary。
src.owner_console_fastapi_launcher 会先安装 package stub，再导入 owner_console_fastapi_app。
launcher 测试会验证 nonebot 未加载、QQ 插件入口未执行。
```

## 3. RESTful 规范

API prefix 固定为：

```text
/api/v1/owner-console
```

路径规范：

```text
只使用 GET。
静态路径 segment 使用 lowercase kebab-case。
路径参数使用 {task_id} / {approval_id}。
JSON 字段和 query 参数使用 snake_case。
集合资源使用复数：tasks、approvals。
详情资源挂在集合资源下：tasks/{task_id}、approvals/{approval_id}。
```

当前故意关闭：

```text
/docs
/redoc
/openapi.json
```

原因是 v0 仍处在本地只读后端面阶段，暂不暴露自动文档页面，避免给人“这是对外开放 API”的错觉。

## 4. HTTP envelope

成功响应统一使用：

```text
owner_console_http_success_response(resource, data, http_api_enabled=true)
```

错误响应统一使用：

```text
owner_console_http_error_response(resource, code, message, details, http_api_enabled=true)
```

稳定 envelope 字段：

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

全局约束：

```text
read_only=true
web_write_enabled=false
transport=http
api_prefix=/api/v1/owner-console
```

允许的 error code：

```text
bad_request
forbidden
not_found
provider_unavailable
internal_error
```

## 5. Route surface

`/healthz` 是服务健康检查，不属于 `/routes` 的 route contract 计数。

当前 HTTP app 已开放：

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

Route contract 内的 10 个资源路由：

| name | resource | path | runtime method | read model | context |
| --- | --- | --- | --- | --- | --- |
| routes | routes | `/api/v1/owner-console/routes` | `build_route_contract_snapshot` | `OwnerConsoleReadRouteContractSnapshot` | no |
| overview | overview | `/api/v1/owner-console/overview` | `build_overview` | `OwnerConsoleOverview` | yes |
| tasks | tasks | `/api/v1/owner-console/tasks` | `build_task_list` | `OwnerConsoleTaskList` | yes |
| tasks.detail | tasks | `/api/v1/owner-console/tasks/{task_id}` | `build_task_detail` | `OwnerConsoleTaskDetail` | yes |
| approvals | approvals | `/api/v1/owner-console/approvals` | `build_approval_list` | `OwnerConsoleApprovalList` | yes |
| approvals.detail | approvals | `/api/v1/owner-console/approvals/{approval_id}` | `build_approval_detail` | `OwnerConsoleApprovalDetail` | yes |
| diagnostics | diagnostics | `/api/v1/owner-console/diagnostics` | `build_health_snapshot` | `OwnerConsoleHealthSnapshot` | no |
| memory | memory | `/api/v1/owner-console/memory` | `build_memory_snapshot` | `OwnerConsoleMemorySnapshot` | no |
| access-control | access-control | `/api/v1/owner-console/access-control` | `build_access_control_snapshot` | `OwnerConsoleAccessControlSnapshot` | no |
| settings | settings | `/api/v1/owner-console/settings` | `build_settings_snapshot` | `OwnerConsoleSettingsSnapshot` | no |

## 6. Context strategy

需要 owner context 的端点：

```text
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
```

context 构造规则：

```text
user_id = BOT_OWNER_QQ
session_key = private:{BOT_OWNER_QQ}
```

边界：

```text
不允许 query 参数覆盖 user_id。
不允许 query 参数覆盖 session_key。
BOT_OWNER_QQ 未配置时返回 HTTP 403。
任务和审批查询只读取 owner 私聊上下文范围内的数据。
其他用户或其他 session 的 task/approval detail 返回 HTTP 404。
```

不需要 owner context 的端点：

```text
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/diagnostics
```

这些端点只返回系统级只读快照，不暴露用户消息正文、长期记忆正文或 ProjectDoc 内容。

## 7. Endpoint audit

### 7.1 routes

用途：

```text
返回当前 Owner Console HTTP route contract。
```

安全点：

```text
不需要 owner context。
不读数据库内容。
不触发任何业务操作。
所有 rows 都标记 read_only=true / web_write_enabled=false。
```

### 7.2 overview

用途：

```text
返回 owner 私聊上下文的 Dashboard 聚合摘要。
```

输入：

```text
task_limit，默认 5，必须 >= 1。
approval_limit，默认 5，必须 >= 1。
```

安全点：

```text
只读取 private:{BOT_OWNER_QQ} / BOT_OWNER_QQ 范围内的任务和审批。
不读取普通聊天上下文。
不触发 MainAgent。
```

### 7.3 tasks

用途：

```text
返回 owner 私聊上下文中的 task list。
```

输入：

```text
status，可选，必须属于 agent task status 集合。
limit，默认 20，必须 >= 1。
```

安全点：

```text
只读 agent_tasks / agent_approvals。
只显示 owner 私聊上下文内的数据。
不创建任务、不取消任务、不推进任务。
```

### 7.4 tasks/{task_id}

用途：

```text
返回某个 owner task 的详情、事件和关联审批摘要。
```

输入：

```text
task_id，必须 >= 1。
event_limit，默认 20，必须 >= 1。
preview_limit，默认 DEFAULT_PREVIEW_LIMIT，必须 >= 1。
```

安全点：

```text
task 不存在或不属于 owner 私聊上下文时返回 404。
tool input 使用 preview/redaction，不直接暴露敏感字段。
不恢复工具执行。
```

### 7.5 approvals

用途：

```text
返回 owner 私聊上下文中的 approval list。
```

输入：

```text
status，可选，必须属于 agent approval status 集合。
limit，默认 20，必须 >= 1。
```

安全点：

```text
只读审批状态。
actionability 是未来 UI 的只读按钮状态描述，不代表当前 Web 支持 approve/reject。
```

### 7.6 approvals/{approval_id}

用途：

```text
返回某个 owner approval 的详情、工具输入 preview 和近期 task events。
```

输入：

```text
approval_id，必须 >= 1。
event_limit，默认 5，必须 >= 1。
preview_limit，默认 DEFAULT_PREVIEW_LIMIT，必须 >= 1。
```

安全点：

```text
approval 不存在或不属于 owner 私聊上下文时返回 404。
tool_input 使用 OwnerConsoleToolInputPreview。
不确认审批、不拒绝审批、不恢复工具。
```

### 7.7 access-control

用途：

```text
返回访问控制只读快照。
```

输入：

```text
item_limit，默认 50，必须 >= 1。
```

数据来源：

```text
load_config()
merged_access(config.private_whitelist, config.group_whitelist, config.user_blacklist)
data/access.json
```

安全点：

```text
只读 whitelist / blacklist 状态。
不修改名单。
不调用 owner_write_runtime。
```

### 7.8 settings

用途：

```text
返回模型配置、角色卡和 feature flags 的只读快照。
```

数据来源：

```text
load_config()
list_role_cards()
active_role_card()
```

脱敏：

```text
API key 只返回 api_key_configured=true/false。
base_url 通过 redacted_base_url 脱敏。
embedding API key 固定不暴露。
```

安全点：

```text
不修改配置。
不切换角色卡。
不写 data/active-role-card.json。
```

### 7.9 memory

用途：

```text
返回 Memory / MemoryRAG / ProjectDocRAG 的只读快照。
```

数据来源：

```text
memory_stats()
manual_memory_stats()
gap_scene_summary_stats()
rag_document_stats()
load_config()
```

强边界：

```text
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
ordinary_chat_injection_allowed=false
```

安全点：

```text
不返回 messages.content。
不返回 long_term_memories.content。
不返回 rag_documents.content。
不执行 MemoryRAG 检索。
不执行 ProjectDocRAG 检索。
不重建索引。
```

### 7.10 diagnostics

用途：

```text
返回 Web Owner Console HTTP 层的轻量诊断快照。
```

当前设计：

```text
不直接 import diagnostics.py。
不触发 OpenAI chat self-test。
不触发 Ollama /api/tags。
不触发 vision inference。
不读取 QQ adapter 的图片缓存。
不读取最近错误日志。
```

响应中显式标记：

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
```

为什么这样做：

```text
GET /diagnostics 在 v0 中仍应是 side-effect-free read model。
主动探测可能产生网络调用、耗时、外部服务依赖和更复杂的失败面。
未来如果需要主动诊断，应设计单独 explicit probe endpoint，而不是把 GET diagnostics 变成探测执行器。
```

## 8. Import boundary

允许：

```text
owner_console_fastapi_app.py
owner_console_http_adapter.py
owner_console_http_contract.py
owner_console_http_models.py
owner_console_read_runtime.py
owner_console_read_models.py
config.py
access_store.py
role_cards.py
memory.py
manual_memory.py
gap_scene_summaries.py
rag.documents
agent_tasks.py
```

禁止：

```text
src/plugins/ai_chat/__init__.py
NoneBot matcher
MessageEvent
bot.send
owner_write_runtime
shell tools
```

审计点：

```text
tests.test_owner_console_fastapi_launcher 会验证 launcher import 不执行 QQ plugin entrypoint。
tests.test_owner_console_fastapi_app 会检查 app / adapter source 不包含 nonebot、MessageEvent、matcher.finish、bot.send、owner_write_runtime。
tests.test_owner_console_http_contract 会检查 contract 层没有 FastAPI / QQ / write runtime 依赖。
```

## 9. Current non-goals

当前仍不做：

```text
不做 Web 前端。
不做登录/鉴权。
不做公网暴露。
不做 CORS。
不开放 POST/PUT/PATCH/DELETE。
不做审批确认/拒绝。
不恢复工具。
不新增数据库表。
不新增工具能力。
不改变 QQ 命令行为。
不改变 /agent 行为。
不改变普通聊天行为。
不改变 MemoryRAG / ProjectDocRAG 行为。
不改变 DiagnosticsGraph 行为。
```

## 10. Upgrade route

建议后续路线：

```text
P2.26：HTTP surface contract cleanup，把重复的 endpoint try/except 和 runtime/context 装配收敛成更小的 helper，但不改变行为。
P2.27：本地 FastAPI smoke runbook，记录如何启动、如何 curl 每个只读端点、如何确认没有写副作用。
P2.28：Web Owner Console 前端只读壳，先消费现有 GET endpoints。
P2.29：登录/鉴权设计，不做写操作。
P2.30：审批操作设计，只设计显式 approve/reject endpoint，不复用 GET，不开放多步写自动化。
```

写操作升级必须继续遵守：

```text
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可以恢复执行。
不开放 shell。
不做任意文件写入。
不做未注册数据库写入。
不新增额外 QQ 发送副作用。
不开放多步写自动化。
```

## 11. Verification

P2.21-P2.24 已验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 14 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 317 tests OK
```
