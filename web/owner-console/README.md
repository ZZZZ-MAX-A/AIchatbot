# Owner Console frontend

Owner Console 前端是 AIchatbot 的本地只读主人控制台。当前 v0 主导航页面已经接入：

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

边界：

```text
只读。
不开放写操作。
不做登录/鉴权。
不确认/拒绝审批。
不触发 MainAgent。
不读取 Python 文件、数据库、.env 或日志。
```

后端启动：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

前端启动：

```powershell
cd D:\AIchatbot\web\owner-console
npm install
npm run dev
```

本地静态模式：

```powershell
cd D:\AIchatbot\web\owner-console
npm run build

cd D:\AIchatbot
$env:OWNER_CONSOLE_STATIC_ENABLED='true'
$env:OWNER_CONSOLE_STATIC_DIR='web/owner-console/dist'
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

一键后台启动本地静态模式：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1
```

如果还没有构建前端：

```powershell
.\scripts\start-owner-console.ps1 -Build
```

停止后台控制台：

```powershell
.\scripts\stop-owner-console.ps1
```

只读边界检查：

```powershell
cd D:\AIchatbot\web\owner-console
npm run guard:readonly
```

访问：

```text
http://127.0.0.1:5173/owner-console

静态模式：
http://127.0.0.1:8090/owner-console
```

完整本地使用手册和排障流程见：

```text
docs/web-owner-console-v0-runbook.md
```
