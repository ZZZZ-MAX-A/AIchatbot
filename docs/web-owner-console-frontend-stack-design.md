# Web Owner Console frontend stack and directory boundary

本文记录 P2.29 Web Owner Console 前端技术栈与目录边界设计。当前阶段只做设计，不创建前端工程、不安装 npm 依赖、不修改 FastAPI 行为。

后续实现状态：P2.30 已补充 UI 布局和中文化展示规则，见 `docs/web-owner-console-ui-layout-design.md`。P2.31 已按本文边界创建 `web/owner-console` 最小 Vite + React + TypeScript 工程，只接 `/healthz` 和 `/api/v1/owner-console/routes`。P2.32 已接入概览页 `/overview` 和 `/diagnostics` 只读数据。P2.33 已接入任务列表 `/tasks` 只读数据。P2.34 第一刀已接入任务详情 `/tasks/{task_id}` 只读数据，仍不修改 FastAPI 行为、不开放 Web 写操作。

## 1. 目标

P2.29 要解决的问题不是“马上做网页”，而是先把未来网页工程放在哪里、用什么技术栈、如何和 Python/FastAPI 分层说清楚。

目标：

```text
确定未来前端工程目录。
确定推荐技术栈。
确定开发启动方式。
确定 API base / proxy 规则。
确定前端内部模块命名。
确定哪些目录和 import 是禁止的。
确定第一版只读 App Shell 的最小依赖范围。
```

非目标：

```text
不创建 package.json。
不安装 Node 依赖。
不写 React 组件。
不写 CSS。
不接真实浏览器页面。
不修改 FastAPI route。
不开放登录/鉴权。
不开放 Web 写操作。
不新增审批确认/拒绝 endpoint。
```

## 2. 推荐结论

推荐前端栈：

```text
Vite
React
TypeScript
React Router
lucide-react
plain CSS 或 CSS Modules
native fetch
```

暂不引入：

```text
Next.js
SSR
TanStack Query
Redux / Zustand
UI component mega framework
Tailwind
chart library
WebSocket / SSE client
```

推荐目录：

```text
web/owner-console
```

推荐第一版运行方式：

```text
FastAPI read-only backend:
  .\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090

Vite frontend dev server:
  npm run dev -- --host 127.0.0.1 --port 5173
```

推荐第一版 API base：

```text
VITE_OWNER_CONSOLE_API_BASE=/api/v1/owner-console
VITE_OWNER_CONSOLE_HEALTH_PATH=/healthz
```

Vite dev proxy 可把下面路径转发到 `http://127.0.0.1:8090`：

```text
/healthz
/api/v1/owner-console
```

## 3. 为什么不放在 Python src 里

当前 Python 目录：

```text
src/
  owner_console_fastapi_launcher.py
  plugins/
    ai_chat/
```

`src/plugins/ai_chat` 是 NoneBot/QQ 插件包。Owner Console HTTP 已经专门通过 `src.owner_console_fastapi_launcher` 绕开直接执行 `src/plugins/ai_chat/__init__.py` 的副作用。

因此前端不能放在：

```text
src/owner_console_web
src/plugins/ai_chat/web
src/plugins/ai_chat/static
```

原因：

```text
避免把 Node/Vite 工程混进 Python import path。
避免让 Web 目录看起来属于 QQ plugin package。
避免后续误以为前端可以 import Python runtime。
避免构建产物污染 src/plugins/ai_chat。
```

推荐放在：

```text
web/owner-console
```

语义：

```text
web/ 表示所有 Web 前端工程边界。
owner-console/ 表示只服务 Owner Console。
Python 后端仍在 src/。
FastAPI adapter 仍在 src.plugins.ai_chat.owner_console_fastapi_app。
side-effect-free launcher 仍在 src.owner_console_fastapi_launcher。
```

## 4. 未来目录草案

未来如果开始创建前端工程，建议结构：

```text
web/
  owner-console/
    package.json
    vite.config.ts
    tsconfig.json
    index.html
    src/
      main.tsx
      app/
        App.tsx
        AppShell.tsx
        routes.tsx
      api/
        ownerConsoleApi.ts
        ownerConsoleEnvelope.ts
        ownerConsoleTypes.ts
      pages/
        DashboardPage.tsx
        TasksPage.tsx
        TaskDetailPage.tsx
        ApprovalsPage.tsx
        ApprovalDetailPage.tsx
        DiagnosticsPage.tsx
        MemoryPage.tsx
        AccessControlPage.tsx
        SettingsPage.tsx
      components/
        BoundaryBadge.tsx
        EmptyState.tsx
        ErrorState.tsx
        LoadingState.tsx
        ResourceHeader.tsx
        StatusPill.tsx
      styles/
        app.css
```

边界约定：

```text
web/owner-console/src/api 只负责 HTTP GET client 和 TypeScript DTO。
web/owner-console/src/pages 只负责页面级数据读取与组合。
web/owner-console/src/components 只负责无副作用展示组件。
web/owner-console/src/app 只负责路由、shell 和全局状态。
```

不建议第一版拆得过细：

```text
不要引入 domain/service/store 三层。
不要先做 monorepo packages。
不要先做 shared UI library。
不要先做复杂权限系统目录。
```

## 5. API client 边界

第一版只允许一个 API client：

```text
ownerConsoleApi
```

建议方法：

```text
getHealth()
getRoutes()
getOverview({ task_limit, approval_limit })
getTasks({ status, limit })
getTaskDetail(task_id, { event_limit, preview_limit })
getApprovals({ status, limit })
getApprovalDetail(approval_id, { event_limit, preview_limit })
getDiagnostics()
getMemory()
getAccessControl({ item_limit })
getSettings()
```

禁止：

```text
approveApproval()
rejectApproval()
resumeApproval()
createTask()
cancelTask()
updateAccessControl()
updateSettings()
rebuildMemoryIndex()
runDiagnosticsProbe()
```

第一版 API client 必须保证：

```text
所有请求都是 GET。
所有路径都在 allowlist 内。
不会接受 user_id / session_key 参数。
不会把 owner context 放入 query。
不会请求 /docs /redoc /openapi.json。
不会请求 src/plugins/ai_chat 相关路径。
```

## 6. TypeScript DTO 策略

第一版不需要自动生成 OpenAPI types，因为当前 FastAPI app 故意关闭：

```text
/openapi.json
/docs
/redoc
```

建议做法：

```text
在 ownerConsoleEnvelope.ts 手写通用 envelope 类型。
在 ownerConsoleTypes.ts 手写当前页面需要的 DTO 子集。
字段名保持 snake_case，和后端 JSON 保持一致。
组件内部如需要展示标签，再做局部 formatter。
```

原因：

```text
减少构建工具复杂度。
避免为了前端类型生成而提前打开 OpenAPI。
保持后端 envelope 契约是唯一来源。
```

通用 envelope 类型应表达：

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

前端必须检查：

```text
schema_version === "owner_console.http.v1"
transport === "http"
api_prefix === "/api/v1/owner-console"
read_only === true
http_api_enabled === true
web_write_enabled === false
```

否则进入：

```text
contract_mismatch
```

## 7. 路由设计

前端页面路径建议：

```text
/owner-console
/owner-console/dashboard
/owner-console/tasks
/owner-console/tasks/:task_id
/owner-console/approvals
/owner-console/approvals/:approval_id
/owner-console/diagnostics
/owner-console/memory
/owner-console/access-control
/owner-console/settings
```

注意：

```text
前端页面路径不等于 API 路径。
前端页面路径使用 kebab-case。
API 路径仍固定为 /api/v1/owner-console。
前端 route params 可以叫 task_id / approval_id，保持和 API 一致。
```

第一版可以使用 React Router。原因：

```text
页面数量已经超过单页 tab 的舒适范围。
任务详情和审批详情天然需要 URL。
React Router 足够轻，不需要 Next.js。
```

## 8. 状态管理策略

第一版不引入全局状态库。

建议：

```text
每个 page 自己维护 loading / data / error。
AppShell 维护 health/routes 的只读状态。
刷新按钮触发当前页面重新 fetch。
详情页只从 URL param 读取 ID。
```

暂不做：

```text
自动轮询。
缓存失效策略。
跨页面复杂 store。
optimistic update。
后台刷新。
```

原因：

```text
当前 Web v0 是只读壳。
没有写操作，不需要 optimistic update。
显式刷新更容易审计请求行为。
```

## 9. 样式和组件策略

第一版视觉方向：

```text
安静、工具型、密度适中。
偏 dashboard / operations console。
避免营销 landing page。
避免大 hero。
避免装饰性渐变和大面积单色主题。
避免卡片套卡片。
```

建议组件：

```text
左侧导航。
顶部状态条。
资源标题。
表格。
详情区块。
状态 badge。
只读边界 badge。
错误态。
空态。
刷新按钮。
```

图标：

```text
使用 lucide-react。
按钮优先 icon 或 icon + text。
不手写 SVG 图标，除非没有对应图标。
```

样式方式：

```text
plain CSS 或 CSS Modules。
先不引入 Tailwind。
先不引入大型 UI 组件库。
```

原因：

```text
第一版需要验证数据和边界，不需要复杂设计系统。
少依赖更容易接入现有 Python 项目。
```

## 10. 开发代理与 CORS

第一版建议使用 Vite dev proxy，而不是在 FastAPI v0 中打开 CORS。

开发时：

```text
浏览器访问 Vite:
  http://127.0.0.1:5173/owner-console

Vite proxy:
  /healthz -> http://127.0.0.1:8090/healthz
  /api/v1/owner-console -> http://127.0.0.1:8090/api/v1/owner-console
```

原因：

```text
Owner Console HTTP v0 仍是本地只读后端。
暂不做登录/鉴权，也不做公网暴露。
不为了开发前端提前扩大 CORS 面。
```

未来如果要部署静态页面，有两个方向：

```text
方案 A：FastAPI 挂载静态 dist。
方案 B：独立静态服务器 + 反向代理。
```

但这属于后续部署设计，不纳入 P2.29。

## 11. 启动命名

未来前端 package scripts 建议：

```text
npm run dev
npm run build
npm run preview
npm run typecheck
```

不要命名为：

```text
npm run start
npm run server
npm run backend
```

原因：

```text
start/server/backend 容易和 NoneBot / FastAPI 后端混淆。
dev/build/preview/typecheck 是前端语义。
```

文档中始终区分：

```text
Owner Console FastAPI backend
Owner Console frontend dev server
NoneBot QQ runtime
NapCatQQ runtime
```

## 12. Python / Node 边界

前端禁止 import 或读取：

```text
src/plugins/ai_chat
src/owner_console_fastapi_launcher.py
data/chatbot.db
data/access.json
.env
logs
prompts
```

前端只能通过 HTTP GET 读取：

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

这样可以保持：

```text
Web frontend -> HTTP adapter -> OwnerConsoleReadRuntime -> read model
```

而不是：

```text
Web frontend -> Python files / database / QQ plugin
```

## 13. 测试策略

第一版创建前端工程后，建议测试分层：

```text
Python tests:
  继续覆盖 FastAPI routes、HTTP contract、read runtime。

Frontend typecheck:
  npm run typecheck。

Frontend unit tests:
  可后置，先不强制引入 Vitest。

Smoke:
  启动 FastAPI backend。
  启动 Vite dev server。
  检查 /owner-console 页面能读取 /healthz 和 /routes。
```

不建议第一步就引入：

```text
Playwright E2E。
visual regression。
mock service worker。
复杂组件测试。
```

原因：

```text
先把只读 App Shell 跑通。
等页面和数据状态稳定后再补浏览器级测试。
```

## 14. 第一版前端工程创建标准

未来真正开始 P2.30 最小 App Shell 时，创建工程必须满足：

```text
1. 只在 web/owner-console 下新增 Node/Vite 文件。
2. 不修改 src/plugins/ai_chat。
3. 不修改 FastAPI route 行为。
4. 不打开 /docs /openapi.json。
5. 不新增 CORS。
6. 不新增 Web 写 endpoint。
7. 不新增登录/鉴权假实现。
8. 只接 /healthz 和 /api/v1/owner-console/routes。
9. 页面显示 read_only=true / web_write_enabled=false。
10. npm scripts 命名不和 Python 后端混淆。
```

## 15. 后续路线

建议路线：

```text
P2.30：创建 web/owner-console 最小 Vite + React + TypeScript 工程，只接 /healthz 和 /routes。
P2.31：实现 App Shell 导航和统一 envelope / error state。
P2.32：接 Dashboard / Tasks / Approvals 列表。
P2.33：接 Task Detail / Approval Detail。
P2.34：接 Diagnostics / Memory / Access Control / Settings。
P2.35：再讨论登录/鉴权设计。
P2.36：再讨论审批操作设计。
```

下一步不建议直接做：

```text
审批按钮。
写操作 API。
主动 diagnostics probe。
自动轮询。
公网部署。
大型 UI framework。
```

这些都需要单独设计和审计。
