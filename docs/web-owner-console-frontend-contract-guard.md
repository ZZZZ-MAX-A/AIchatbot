# Web Owner Console frontend contract guard

本文记录 P2.37 Web Owner Console 前端只读 contract guard。目标是把 P2.36 的人工只读审计固化为本地自动检查，避免后续加页面时无意间扩大 Web Owner Console v0 的能力边界。

## 1. 定位

`guard:readonly` 是前端静态检查，不是浏览器 E2E，也不是后端 HTTP 测试。

它检查：

```text
前端是否仍只有一个 HTTP client。
HTTP client 是否仍只使用 GET。
请求路径是否仍在只读 allowlist 内。
任务详情 / 审批详情动态路径是否仍只允许正整数 ID。
源码是否引用 /openapi、/docs 或 /redoc。
源码是否出现写操作风格 API 名称。
主导航页面路由是否仍全部存在。
占位业务页是否已经清理。
timer 和 visibility API 是否只出现在受控自动刷新 hook。
第一版自动刷新是否避免使用 setInterval。
```

它不检查：

```text
真实浏览器渲染。
真实后端连接。
FastAPI route 行为。
QQ / NoneBot 行为。
登录/鉴权。
未来审批写操作。
```

## 2. 命令

```powershell
cd D:\AIchatbot\web\owner-console
npm run guard:readonly
```

当前输出：

```text
Owner Console frontend read-only guard passed.
Checked 24 TypeScript source files.
Verified GET-only fetch usage, read-only allowlist, controlled timers, page routes, and absence of write-style API names.
```

## 3. 文件

```text
web/owner-console/scripts/readonly-guard.mjs
```

package script：

```json
"guard:readonly": "node scripts/readonly-guard.mjs"
```

## 4. 当前固定 allowlist

静态 allowlist：

```text
/healthz
/api/v1/owner-console/routes
/api/v1/owner-console/overview
/api/v1/owner-console/diagnostics
/api/v1/owner-console/memory
/api/v1/owner-console/access-control
/api/v1/owner-console/settings
/api/v1/owner-console/tasks
/api/v1/owner-console/approvals
```

动态 allowlist：

```text
/api/v1/owner-console/tasks/{positive_int}
/api/v1/owner-console/approvals/{positive_int}
```

如果后续新增只读资源，必须同时更新：

```text
后端 route contract。
ownerConsoleApi allowlist。
readonly-guard.mjs expectedStaticPaths 或动态路径规则。
对应文档。
```

如果后续新增写资源，不应直接修改这个 guard 放行，而是先单独做 Web 写操作设计和审批操作审计。

## 5. 禁止项

guard 会拦截以下方向：

```text
fetch 出现在 ownerConsoleApi 之外。
HTTP method 不是 GET。
源码引用 /openapi、/docs、/redoc。
出现 approveApproval / rejectApproval / resumeApproval。
出现 createTask / cancelTask / retryTask。
出现 saveSettings / switchRoleCard / updateAccessControl。
出现 rebuildMemoryIndex / runDiagnosticsProbe。
出现 clearImageCache / clearErrorLog。
出现 addMemory / deleteMemory。
重新引入 PlaceholderPage。
在业务页面或组件中直接使用 setTimeout / clearTimeout / setInterval。
在业务页面或组件中直接监听 visibilitychange。
```

这些名字不是完整安全模型，只是 v0 只读边界的前端防线。后端 FastAPI / route contract / runtime service 测试仍然必须保留。

## 6. 建议验证组合

前端：

```powershell
npm run guard:readonly
npm run typecheck
npm run build
npm audit
```

后端 HTTP contract：

```powershell
cd D:\AIchatbot
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

## 7. 后续路线

建议下一步：

```text
P2.38：Web Owner Console v0 使用手册和启动 runbook。已完成。
P2.39-P2.39b：本地部署设计、静态模式和启停脚本。已完成。
P2.40：只读自动刷新策略设计。已完成，见 docs/web-owner-console-readonly-auto-refresh-design.md。
P2.40a：已扩展 guard，限制 timer 和 visibility API 只能出现在受控 hook。
P2.40b-P2.40c：页面接入后继续约束手动页面不能注册业务 timer，并补浏览器 smoke。
P2.41：设计本地访问保护 / 鉴权。
P2.42：单独设计 Web 审批操作。
```

仍不建议直接做：

```text
审批按钮。
写操作 API。
公网部署。
未经 P2.40a 实现和 guard 验证的自动轮询。
WebSocket / SSE。
登录页假实现。
```
