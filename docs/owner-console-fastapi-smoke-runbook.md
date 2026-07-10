# Owner Console FastAPI smoke runbook

本文记录 P2.27 本地 FastAPI smoke 验证流程。目标是让 Owner Console HTTP v0 可以被稳定启动、手动检查和排障，同时继续保持只读、本地、无 QQ adapter 副作用的边界。

## 1. 定位

Owner Console FastAPI app 当前仍是本地只读 HTTP adapter，并支持显式开启的可选静态页面模式：

```text
本地启动。
只监听 127.0.0.1。
只开放 GET。
`OWNER_CONSOLE_STATIC_ENABLED=false` 时只返回 JSON read model，不服务前端页面。
`OWNER_CONSOLE_STATIC_ENABLED=true` 时额外服务 `/owner-console` 静态页面和 SPA fallback；`/api/v1/owner-console/*` 仍只返回 JSON。
不做登录/鉴权。
不开放审批确认/拒绝。
不恢复工具执行。
不发送 QQ 消息。
不 import NoneBot / QQ plugin entrypoint。
```

这份 runbook 只用于本地开发和 smoke 验证，不代表公网部署手册。

## 2. 启动前检查

确认当前仓库状态：

```powershell
git status -sb
git log --oneline -5
```

确认 8090 端口未被占用：

```powershell
netstat -ano | Select-String ':8090'
```

如果 8090 已被占用，可以临时换成 8091：

```text
--port 8091
```

Owner context 类端点依赖 `BOT_OWNER_QQ`。通常项目根目录 `.env` 会被 `config.py` 自动读取。如果只想在当前 PowerShell 临时覆盖：

```powershell
$env:BOT_OWNER_QQ='你的主人 QQ'
```

`BOT_OWNER_QQ` 未配置时，以下端点返回 HTTP 403 是预期行为，不代表服务启动失败：

```text
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
```

## 3. 正确启动方式

在项目根目录打开 PowerShell：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

看到类似输出表示已启动：

```text
Uvicorn running on http://127.0.0.1:8090
```

这个窗口不要关闭。验证完成后按 `Ctrl + C` 停止服务。

禁止直接使用：

```text
uvicorn src.plugins.ai_chat.owner_console_fastapi_app:app
```

原因：

```text
src.plugins.ai_chat 是 NoneBot/QQ 插件包。
直接按普通包路径导入可能执行 src/plugins/ai_chat/__init__.py。
Owner Console HTTP adapter 必须通过 src.owner_console_fastapi_launcher 安装 package stub 后再加载。
```

## 4. 基础 smoke 检查

另开一个 PowerShell：

```powershell
$base = 'http://127.0.0.1:8090'
```

检查健康状态：

```powershell
Invoke-RestMethod "$base/healthz"
```

关键期望：

```text
ok=true
service=owner-console
schema_version=owner_console.http.v1
api_prefix=/api/v1/owner-console
read_only=true
http_api_enabled=true
web_write_enabled=false
```

检查 route contract：

```powershell
$routes = Invoke-RestMethod "$base/api/v1/owner-console/routes"
$routes.data.rows | Select-Object name, method, path, http_api_enabled, web_write_enabled
```

关键期望：

```text
allowed_methods 只有 GET。
route_count 为 10。
所有 rows 都是 read_only=true。
所有 rows 都是 http_api_enabled=true。
所有 rows 都是 web_write_enabled=false。
api_prefix 固定为 /api/v1/owner-console。
```

## 5. 非 context 快照检查

这些端点不需要 `BOT_OWNER_QQ`：

```powershell
Invoke-RestMethod "$base/api/v1/owner-console/access-control" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/v1/owner-console/settings" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/v1/owner-console/memory" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/v1/owner-console/diagnostics" | ConvertTo-Json -Depth 10
```

通用期望：

```text
schema_version=owner_console.http.v1
transport=http
read_only=true
http_api_enabled=true
web_write_enabled=false
error=null
```

`settings` 期望：

```text
API key 不出现在响应中。
base_url 使用脱敏字段。
只返回配置状态和角色卡摘要。
不写 active role card。
```

`memory` 期望：

```text
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
```

`diagnostics` 期望：

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

## 6. Owner context 端点检查

如果 `BOT_OWNER_QQ` 已配置，可以检查：

```powershell
Invoke-RestMethod "$base/api/v1/owner-console/overview?task_limit=5&approval_limit=5" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/v1/owner-console/tasks?limit=20" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/v1/owner-console/approvals?limit=20" | ConvertTo-Json -Depth 10
```

关键期望：

```text
只读取 user_id=BOT_OWNER_QQ。
只读取 session_key=private:{BOT_OWNER_QQ}。
不允许 query 覆盖 user_id。
不允许 query 覆盖 session_key。
```

如果列表里有可见任务或审批，可以继续检查详情：

```powershell
Invoke-RestMethod "$base/api/v1/owner-console/tasks/1?event_limit=20&preview_limit=800" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/v1/owner-console/approvals/1?event_limit=5&preview_limit=800" | ConvertTo-Json -Depth 10
```

如果 ID 不存在，或存在但不属于 owner 私聊上下文，返回 HTTP 404 是预期行为。

## 7. 只读边界检查

确认 docs / redoc / openapi 未暴露：

```powershell
try { Invoke-WebRequest "$base/docs" } catch { $_.Exception.Response.StatusCode.value__ }
try { Invoke-WebRequest "$base/redoc" } catch { $_.Exception.Response.StatusCode.value__ }
try { Invoke-WebRequest "$base/openapi.json" } catch { $_.Exception.Response.StatusCode.value__ }
```

期望：

```text
404
404
404
```

确认写方法未开放：

```powershell
try { Invoke-WebRequest -Method Post "$base/api/v1/owner-console/tasks" } catch { $_.Exception.Response.StatusCode.value__ }
try { Invoke-WebRequest -Method Post "$base/api/v1/owner-console/approvals" } catch { $_.Exception.Response.StatusCode.value__ }
try { Invoke-WebRequest -Method Post "$base/api/v1/owner-console/memory" } catch { $_.Exception.Response.StatusCode.value__ }
```

期望：

```text
405
405
405
```

这些 404 / 405 是安全边界，不是故障。

## 8. 自动化回归检查

本地 smoke 前后建议至少跑：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

更完整的 Owner Console 后端回归：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_app -v
```

全量回归：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

目前已知 FastAPI 测试可能出现 Starlette / httpx deprecation warning。只要测试为 OK，该 warning 不影响当前 smoke 判断。

## 9. Import boundary 自检

launcher 边界测试：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher -v
```

源码静态检查：

```powershell
Select-String -Path src\plugins\ai_chat\owner_console_fastapi_app.py,src\plugins\ai_chat\owner_console_http_adapter.py -Pattern 'nonebot|MessageEvent|matcher.finish|bot.send|owner_write_runtime'
```

期望：

```text
无匹配输出。
```

## 10. 常见问题

### 10.1 端口已占用

现象：

```text
Address already in use
```

处理：

```powershell
netstat -ano | Select-String ':8090'
```

可以停止占用进程，或者临时改用：

```text
--port 8091
```

### 10.2 owner 端点返回 403

这通常表示 `BOT_OWNER_QQ` 未配置。检查：

```powershell
$env:BOT_OWNER_QQ
```

或检查项目根目录 `.env`。配置后需要重启 Uvicorn，因为进程启动时会读取环境变量。

### 10.3 `/docs` 返回 404

这是预期行为。当前 v0 故意关闭：

```text
/docs
/redoc
/openapi.json
```

### 10.4 `Invoke-RestMethod` 看不到错误响应

PowerShell 对非 2xx 响应可能直接抛异常。需要用：

```powershell
try { Invoke-WebRequest "$base/api/v1/owner-console/overview" } catch { $_.Exception.Response.StatusCode.value__ }
```

### 10.5 怀疑误加载 QQ plugin

不要在同一个 Python 进程里先 import `src.plugins.ai_chat`，再启动 Owner Console launcher。

如果出现 launcher 拒绝启动，使用新的 PowerShell 重新启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

并运行：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher -v
```

## 11. 当前不做

本 runbook 不覆盖：

```text
公网部署。
反向代理。
TLS。
CORS。
登录/鉴权。
默认纯 API smoke 模式中的 Web 前端页面；静态页面模式的完整操作见 `docs/web-owner-console-v0-runbook.md`。
审批确认/拒绝 API。
写操作 API。
主动 diagnostics probe API。
多步写自动化。
```

这些能力需要后续单独设计和审计，不应混入 P2.27 smoke 验证流程。
