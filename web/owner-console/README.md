# Owner Console frontend

Owner Console 前端是 AIchatbot 的本地只读主人控制台。当前第一版只接入：

```text
GET /healthz
GET /api/v1/owner-console/routes
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

访问：

```text
http://127.0.0.1:5173/owner-console
```
