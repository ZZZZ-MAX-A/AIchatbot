# Web Owner Console v0 runbook

本文记录 P2.38 Web Owner Console v0 的本地使用手册和启动排障流程。它把当前 FastAPI 只读 HTTP adapter、Vite 前端、前端只读 guard 和后端 HTTP contract 测试串成一套日常开发验证步骤。

当前 runbook 只覆盖本地开发和只读查看，不是公网部署手册。

## 1. 定位

Web Owner Console v0 是 AIchatbot 的本地主人控制台：

```text
FastAPI 只提供本地只读 JSON read model。
Vite + React 前端只展示结构化状态和只读详情。
前端通过 Vite dev proxy 访问 127.0.0.1:8090。
主界面访问地址是 http://127.0.0.1:5173/owner-console。
```

它不是：

```text
QQ adapter。
普通聊天入口。
MainAgent 自动执行入口。
公网管理后台。
登录/鉴权系统。
审批写操作页面。
```

## 2. 当前页面

主导航页面：

```text
Dashboard：总览任务、审批和诊断摘要。
Tasks：任务列表，支持只读状态筛选。
Approvals：审批列表，支持只读状态筛选。
Diagnostics：诊断快照，只展示状态，不执行探测。
Memory：记忆快照，只展示计数和边界，不暴露正文。
Access Control：访问控制快照，只展示名单统计和策略。
Settings：设置快照，只展示脱敏配置和功能开关。
```

详情页不放在主导航里，只从列表进入：

```text
Task Detail：/owner-console/tasks/:task_id
Approval Detail：/owner-console/approvals/:approval_id
```

顶部状态条应始终能看到：

```text
主人控制台
只读模式=true
网页写入=false
后端已连接 / 后端未连接
schema_version
最后刷新时间
自动刷新开关，完整页面加载后默认关闭
```

## 3. 启动前检查

在项目根目录检查当前仓库状态：

```powershell
cd D:\AIchatbot
git status -sb
git log --oneline -5
```

确认后端端口未被占用：

```powershell
netstat -ano | Select-String ':8090'
```

确认前端端口未被占用：

```powershell
netstat -ano | Select-String ':5173'
```

如果端口被占用，可以先停止对应开发进程。后端也可以临时改成 8091，但此时需要同步调整 Vite proxy 或环境配置；日常开发推荐继续使用 8090。

Owner context 页面依赖 `BOT_OWNER_QQ`。如果未配置，以下页面可能显示后端 403，这是预期的权限边界，不代表服务挂了：

```text
Dashboard
Tasks
Task Detail
Approvals
Approval Detail
```

以下页面通常不依赖 owner 私聊上下文：

```text
Diagnostics
Memory
Access Control
Settings
```

## 4. 启动后端

打开第一个 PowerShell，在项目根目录启动 FastAPI：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

看到类似输出表示后端已启动：

```text
Uvicorn running on http://127.0.0.1:8090
```

这个窗口不要关闭。

必须使用 `src.owner_console_fastapi_launcher:app`，不要直接用：

```text
src.plugins.ai_chat.owner_console_fastapi_app:app
```

原因是 `src.plugins.ai_chat` 是 NoneBot / QQ 插件包。Web Owner Console 后端需要通过 launcher 安装 package stub 后再加载 FastAPI app，避免执行 QQ adapter 入口。

## 5. 启动前端

打开第二个 PowerShell：

```powershell
cd D:\AIchatbot\web\owner-console
npm install
npm run dev
```

看到 Vite 输出后访问：

```text
http://127.0.0.1:5173/owner-console
```

`npm install` 只需要首次或依赖变化后运行。日常启动只需要：

```powershell
cd D:\AIchatbot\web\owner-console
npm run dev
```

当前 Vite dev server 会代理：

```text
/healthz -> http://127.0.0.1:8090/healthz
/api/v1/owner-console -> http://127.0.0.1:8090/api/v1/owner-console
```

## 5.1 本地静态模式

如果只想本地打开控制台，而不单独启动 Vite dev server，可以先构建前端：

```powershell
cd D:\AIchatbot\web\owner-console
npm run build
```

然后打开新的 PowerShell，从项目根目录启动带静态页面的 FastAPI：

```powershell
cd D:\AIchatbot
$env:OWNER_CONSOLE_STATIC_ENABLED='true'
$env:OWNER_CONSOLE_STATIC_DIR='web/owner-console/dist'
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

访问：

```text
http://127.0.0.1:8090/owner-console
```

更方便的后台启动方式：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1
```

如果还没有构建前端，可以让脚本先构建：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1 -Build
```

脚本会：

```text
检查 .venv\Scripts\python.exe 是否存在。
检查 8090 是否已被占用。
检查 web/owner-console/dist/index.html 是否存在。
设置 OWNER_CONSOLE_STATIC_ENABLED=true。
设置 OWNER_CONSOLE_STATIC_DIR=web/owner-console/dist。
后台隐藏启动 uvicorn。
写日志到 logs/owner-console.out.log 和 logs/owner-console.err.log。
```

停止后台控制台：

```powershell
cd D:\AIchatbot
.\scripts\stop-owner-console.ps1
```

需要前台调试时：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1 -Foreground
```

边界：

```text
/api/v1/owner-console/* 仍然只返回 JSON API。
/owner-console/* 只服务前端页面或静态资源。
/owner-console/tasks/1 刷新时会 fallback 到 index.html。
/owner-console/assets/missing.js 返回 404，不 fallback。
/docs、/redoc、/openapi.json 仍然关闭。
静态页面仍只能调用 GET allowlist。
```

## 6. 手动验收顺序

### P2.40a 自动刷新基础设施

当前顶部状态区已经提供“自动刷新”开关：

```text
默认关闭。
只保存在当前 AppShell 内存中，浏览器完整刷新后恢复关闭。
开启后当前只每 60 秒检查一次 /healthz。
页面隐藏时暂停 timer 并取消自动 health 请求。
连续 3 次网络/5xx 失败后暂停；400/403/404 或 contract mismatch 立即暂停。
手动刷新成功后恢复调度。
Dashboard、Tasks、Approvals 和 Detail 业务数据当前仍然只支持首次加载和手动刷新。
```

P2.40b 才会把 30 秒低频刷新接入允许的业务页面。Diagnostics、Memory、Access Control 和 Settings 继续保持手动刷新。

建议按这个顺序看页面：

```text
1. Dashboard：确认顶部状态条显示后端已连接、只读模式=true、网页写入=false。
2. Diagnostics：确认诊断快照只展示状态，不执行外部探测。
3. Memory：确认 memory_content_exposed=false，retrieval_executed=false，index_rebuild_executed=false。
4. Access Control：确认只展示名单和策略摘要，没有添加/移除按钮。
5. Settings：确认 API Key 不展示原文，模型和 base_url 为脱敏状态。
6. Tasks：确认只有刷新和状态筛选，没有创建/取消/重试按钮。
7. Task Detail：从任务列表进入，确认只展示目标、结果、事件和关联审批。
8. Approvals：确认只有刷新和状态筛选，没有确认/拒绝/恢复按钮。
9. Approval Detail：从审批列表进入，确认只展示审批请求、风险和关联任务。
```

如果 `BOT_OWNER_QQ` 未配置，Dashboard、Tasks、Approvals 返回 403 是正常表现。此时重点检查顶部连接状态和非 context 页面即可。

## 7. 自动化验证

前端验证：

```powershell
cd D:\AIchatbot\web\owner-console
npm run guard:readonly
npm test
npm run typecheck
npm run build
npm audit
```

关键期望：

```text
guard:readonly 通过。
test 显示 1 个测试文件、12 项测试通过。
typecheck 通过。
build 通过。
npm audit 显示 found 0 vulnerabilities。
```

后端 HTTP contract 验证：

```powershell
cd D:\AIchatbot
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

关键期望：

```text
Ran 22 tests OK
```

目前测试中可能出现 Starlette / httpx deprecation warning。只要最终结果是 OK，不影响当前判断。

## 8. 只读边界

当前必须保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent。
MainAgent 和 ChatAgent 保持分离。
ProjectDocRAG 只允许在显式 /agent dev_context 中使用。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复执行。
不开放多步写自动化。
不新增额外 QQ 发送副作用。
Web Owner Console v0 只读。
```

前端当前只允许调用：

```text
GET /healthz
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

不要在 v0 中加入：

```text
POST / PUT / PATCH / DELETE。
审批确认/拒绝按钮。
恢复执行按钮。
创建、取消、重试任务按钮。
保存设置按钮。
切换角色卡按钮。
修改名单按钮。
新增/删除记忆按钮。
主动运行诊断探测按钮。
未经 P2.40b 页面接入和 guard 验证的业务自动轮询、WebSocket 或 SSE。
登录页假实现。
```

## 9. 常见问题

### 后端未连接

现象：

```text
顶部状态条显示后端未连接。
页面出现 fetch failed 或加载失败。
```

检查：

```powershell
netstat -ano | Select-String ':8090'
```

确认后端是否用正确方式启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

### 页面返回 403

通常是 `BOT_OWNER_QQ` 未配置，或当前本地数据没有 owner 私聊上下文。检查：

```powershell
$env:BOT_OWNER_QQ
```

如果使用项目根目录 `.env`，修改后需要重启 Uvicorn。

### 详情页返回 404

详情页 ID 必须来自列表。返回 404 通常表示：

```text
ID 不存在。
ID 存在但不属于 owner 私聊上下文。
```

这是 owner 过滤边界，不应绕过。

### /docs、/redoc、/openapi.json 返回 404

这是预期行为。当前 v0 故意不暴露 OpenAPI 页面。

### npm run dev 启动失败

先确认依赖是否安装：

```powershell
cd D:\AIchatbot\web\owner-console
npm install
```

再确认 5173 是否被占用：

```powershell
netstat -ano | Select-String ':5173'
```

### build 后直接打开 dist 没有数据

不要直接双击打开 `web/owner-console/dist/index.html`。当前本地静态模式需要由 FastAPI 服务：

```powershell
cd D:\AIchatbot
$env:OWNER_CONSOLE_STATIC_ENABLED='true'
$env:OWNER_CONSOLE_STATIC_DIR='web/owner-console/dist'
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

然后访问：

```text
http://127.0.0.1:8090/owner-console
```

或者直接使用脚本：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1 -Build
```

## 10. 相关文档

```text
docs/web-owner-console-read-model-design.md
docs/web-owner-console-read-only-shell-design.md
docs/web-owner-console-local-deployment-design.md
docs/owner-console-fastapi-smoke-runbook.md
docs/web-owner-console-frontend-stack-design.md
docs/web-owner-console-ui-layout-design.md
docs/web-owner-console-frontend-readonly-audit.md
docs/web-owner-console-frontend-contract-guard.md
docs/web-owner-console-readonly-auto-refresh-design.md
web/owner-console/README.md
```

## 11. 后续路线

建议继续顺序：

```text
P2.39：本地部署方式设计，见 docs/web-owner-console-local-deployment-design.md。
P2.39a：按设计实现可选本地静态模式。已完成。
P2.39b：Owner Console 本地一键启动/停止脚本。已完成。
P2.40：只读自动刷新策略设计。已完成，见 docs/web-owner-console-readonly-auto-refresh-design.md。
P2.40a：受控自动刷新基础设施、AppShell health 检查和生命周期测试。已完成。
P2.40b：接入 Dashboard、Tasks、Approvals 和两个 Detail 页面。
P2.40c：guard、runbook 和浏览器 smoke 收口。
P2.41：设计本地访问保护 / 鉴权。
P2.42：单独设计 Web 审批操作，不能直接在 v0 只读页面上加按钮。
```
