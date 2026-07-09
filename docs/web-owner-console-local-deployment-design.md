# Web Owner Console local deployment design

本文记录 P2.39 Web Owner Console 本地部署方式设计。当前阶段只做设计，不修改 FastAPI app、不修改 Vite 配置、不生成前端构建产物、不接登录/鉴权、不开放 Web 写操作。

## 1. 设计结论

推荐保留两种本地运行形态：

```text
开发模式：
  FastAPI 只读 HTTP adapter 运行在 127.0.0.1:8090。
  Vite dev server 运行在 127.0.0.1:5173。
  Vite proxy 转发 /healthz 和 /api/v1/owner-console。
  访问 http://127.0.0.1:5173/owner-console。

本地静态模式：
  npm run build 生成 web/owner-console/dist。
  FastAPI 可选挂载 dist。
  API 继续走 /api/v1/owner-console。
  页面走 /owner-console。
  访问 http://127.0.0.1:8090/owner-console。
```

当前更推荐先实现“可选本地静态模式”，而不是替换开发模式。开发调试继续用 Vite；日常本地查看可以由 FastAPI 统一服务 API 和前端页面。

## 2. 当前保持不变

以下行为继续保持：

```text
FastAPI 只监听 127.0.0.1。
Owner Console HTTP API 只开放 GET。
/docs、/redoc、/openapi.json 继续关闭。
前端 API client 继续只允许 GET allowlist。
Web Owner Console v0 继续只读。
不新增登录/鉴权。
不新增审批确认/拒绝页面。
不新增后端写 API。
不提交 dist 构建产物。
```

`/docs`、`/redoc`、`/openapi.json` 可以在未来单独设立边界后再讨论是否开放部分内容。当前本地静态部署不改变这条策略。

## 3. 路径命名

推荐路径分层：

```text
/healthz
  后端健康检查。

/api/v1/owner-console/*
  Owner Console JSON API。
  只返回 application/json。
  不允许被前端 SPA fallback 接管。

/owner-console
/owner-console/*
  Web Owner Console 静态页面。
  只返回前端构建产物或 index.html fallback。
  不承载 JSON API。
```

不推荐：

```text
把 API 放到 /owner-console/api。
把静态页面放到 /api/v1/owner-console。
让 /api/v1/owner-console/* fallback 到 index.html。
让 /owner-console/* 直接读 Python 文件、数据库、日志或 .env。
```

这样可以避免 FastAPI 挂载静态文件后影响 `/api/v1/owner-console`。API namespace 和页面 namespace 是两条独立路径，不互相兜底。

## 4. 前端构建 base

如果未来由 FastAPI 挂载 `dist` 到 `/owner-console`，Vite 构建需要保证静态资源路径也在 `/owner-console` 下。

推荐未来实现：

```text
Vite build base = /owner-console/
```

原因：

```text
构建后的 JS/CSS 资源应从 /owner-console/assets/... 加载。
刷新 /owner-console/tasks/1 时，资源路径仍应稳定。
避免在站点根路径暴露 /assets。
避免和未来其他本地页面资源冲突。
```

当前 `.env.example` 中的 API base 仍保持：

```text
VITE_OWNER_CONSOLE_API_BASE=/api/v1/owner-console
VITE_OWNER_CONSOLE_HEALTH_PATH=/healthz
```

也就是说，页面 base 和 API base 不合并：

```text
页面 base：/owner-console/
API base：/api/v1/owner-console
健康检查：/healthz
```

## 5. SPA fallback 规则

前端使用 React Router，任务详情和审批详情是客户端路由：

```text
/owner-console/tasks/:task_id
/owner-console/approvals/:approval_id
```

因此本地静态模式需要支持刷新详情页。推荐 fallback 规则：

```text
GET /owner-console
  返回 dist/index.html。

GET /owner-console/
  返回 dist/index.html。

GET /owner-console/assets/{file}
  如果文件存在，返回 dist/assets/{file}。
  如果文件不存在，返回 404，不 fallback 到 index.html。

GET /owner-console/{client_route}
  如果不是 assets 路径，返回 dist/index.html。
```

这表示浏览器刷新 `/owner-console/tasks/1` 时，后端可以发送同一份 `index.html`，由前端路由渲染任务详情。这里的 fallback 只服务 HTML，不改变后端 API 行为。

明确禁止：

```text
GET /api/v1/owner-console/tasks/1 fallback 到 index.html。
POST /owner-console/... fallback 到 index.html。
/docs、/redoc、/openapi.json fallback 到 index.html。
缺失的 /owner-console/assets/... fallback 到 index.html。
```

如果未来需要对 `index.html` 做服务端模板注入，只允许注入非敏感构建元数据，例如版本号或构建时间；不能注入 token、API key、主人 QQ、数据库路径、日志路径或本地文件路径。

## 6. 静态模式开关

推荐未来实现时加显式开关，避免当前 smoke app 默认行为突然变化：

```text
OWNER_CONSOLE_STATIC_ENABLED=false
OWNER_CONSOLE_STATIC_DIR=web/owner-console/dist
```

建议语义：

```text
false：
  FastAPI 只提供 JSON API。
  /owner-console 返回 404。
  适合后端 contract 测试和纯 API smoke。

true：
  FastAPI 在 /owner-console 挂载前端 dist。
  /api/v1/owner-console 保持 JSON API。
  /docs、/redoc、/openapi.json 仍然关闭。
```

如果 `OWNER_CONSOLE_STATIC_ENABLED=true` 但 dist 不存在，推荐返回清晰错误，而不是静默 fallback 到其他目录：

```text
GET /owner-console -> 503 static build not found
```

或者启动时直接拒绝启动。两者都可以，后续实现前再选；我更偏向启动时拒绝，因为本地部署问题会更早暴露。

## 7. 只读 API allowlist

本地静态模式不改变前端请求面。当前仍只允许：

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

未来如果本机操作要加入修改功能，不能通过“本地静态部署”顺手打开。它应进入单独阶段：

```text
先设计本地访问保护或鉴权。
再设计 Web 审批 decision 资源。
再设计前端写操作状态和二次确认。
最后修改 guard 和后端 contract。
```

在那之前，静态页面仍然只能调用 GET allowlist。

## 8. 与 docs/openapi 的关系

当前继续关闭：

```text
/docs
/redoc
/openapi.json
```

理由：

```text
当前 Owner Console 的边界由文档和测试维护，不依赖浏览器 OpenAPI 页面。
v0 不做公网部署，也不需要给第三方开发者探索 API。
开放 OpenAPI 页面会额外引入可见 surface，需要单独审计。
```

未来如果开放，应单独设计：

```text
只读 schema 是否可见。
是否需要 token。
是否隐藏未来写 endpoint。
是否允许在 docs 页面直接发请求。
是否继续屏蔽非 Owner Console 路由。
```

## 9. 推荐实现步骤

后续如果要从设计进入实现，建议分四刀：

```text
第一刀：前端构建 base
  配置 Vite build base=/owner-console/。
  验证 npm run build 后资源路径正确。

第二刀：FastAPI 静态挂载
  增加显式静态模式开关。
  /owner-console 和 /owner-console/* 返回 index.html fallback。
  /owner-console/assets/* 返回真实静态资源。

第三刀：路由冲突测试
  验证 /api/v1/owner-console/* 不受静态 fallback 影响。
  验证 /docs、/redoc、/openapi.json 仍是 404。
  验证 POST /api/v1/owner-console/* 仍是 405。
  验证缺失资产返回 404。

第四刀：runbook 更新
  增加本地静态模式启动命令。
  说明 dev mode 和 static mode 的选择。
```

这四刀都不需要引入登录、写操作、WebSocket、SSE 或自动刷新。

## 10. 推荐测试清单

后续实现本地静态模式时，建议新增或扩展测试：

```text
GET /owner-console -> text/html。
GET /owner-console/ -> text/html。
GET /owner-console/tasks -> text/html。
GET /owner-console/tasks/1 -> text/html。
GET /owner-console/approvals/1 -> text/html。
GET /owner-console/assets/{existing_file} -> 静态资源。
GET /owner-console/assets/missing.js -> 404。
GET /api/v1/owner-console/routes -> JSON envelope。
GET /api/v1/owner-console/tasks/1 -> JSON envelope 或 JSON error。
POST /api/v1/owner-console/tasks -> 405。
GET /docs -> 404。
GET /redoc -> 404。
GET /openapi.json -> 404。
```

前端仍需跑：

```powershell
cd D:\AIchatbot\web\owner-console
npm run guard:readonly
npm run typecheck
npm run build
npm audit
```

后端仍需跑：

```powershell
cd D:\AIchatbot
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

## 11. 当前暂不做

本阶段不做：

```text
不实现 FastAPI 静态挂载。
不修改 Vite base。
不新增启动脚本。
不新增登录/鉴权。
不新增写 endpoint。
不开放 /docs、/redoc、/openapi.json。
不做公网部署。
不做反向代理。
不做 TLS。
不做自动轮询。
不做 WebSocket / SSE。
不提交 dist。
```

## 12. 实现优化和防偏建议

后续实现时，重点不是“能不能返回页面”，而是不要让静态页面 fallback 污染 API 边界。

建议实现时遵守：

```text
fallback 是路由级 fallback。
fallback 只服务 /owner-console 前端页面。
fallback 不是 API fallback。
fallback 不是敏感配置注入。
```

应避免过宽 catch-all：

```text
不应写成 /{path:path} -> index.html。
不应让未知路径都返回前端页面。
不应让 /api/v1/owner-console/*、/docs、/redoc、/openapi.json 被页面 fallback 吞掉。
```

推荐只处理明确页面前缀：

```text
/owner-console
/owner-console/
/owner-console/{client_path:path}
```

实现静态资源时，建议把 assets 当作真实文件资源，而不是客户端路由：

```text
/owner-console/assets/{file}
  文件存在：返回静态文件。
  文件不存在：返回 404。
  不返回 index.html。
```

`index.html` 默认应作为静态构建产物原样返回。即使未来需要服务端注入，也只允许注入低风险元数据：

```text
允许：
  build_version
  build_time
  public_api_base

不允许：
  token
  API key
  BOT_OWNER_QQ
  .env 内容
  数据库路径
  日志路径
  本地文件路径
```

静态模式建议默认关闭：

```text
OWNER_CONSOLE_STATIC_ENABLED=false
```

这样后端 smoke app 的默认行为仍是纯 JSON API，测试和边界不会因为前端静态部署突然扩大。只有明确打开静态模式时，`/owner-console` 才应该返回页面。

路由注册和测试需要特别覆盖：

```text
API route 优先保持 JSON 行为。
页面 fallback 只命中 /owner-console。
/docs、/redoc、/openapi.json 继续是 404。
缺失 assets 继续是 404。
POST /owner-console/... 不应被当作页面请求处理。
```

一句话概括：

```text
/owner-console/tasks/1 -> index.html 是允许的。
/api/v1/owner-console/tasks/1 -> index.html 是禁止的。
/docs -> index.html 是禁止的。
```

## 13. 后续路线

建议后续路线：

```text
P2.39a：按本文实现可选本地静态模式。
P2.40：设计只读自动刷新策略。
P2.41：设计本地访问保护 / 鉴权。
P2.42：设计 Web 审批操作。
```
