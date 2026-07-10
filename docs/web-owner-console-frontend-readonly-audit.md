# Web Owner Console frontend read-only audit

本文记录 Web Owner Console v0 主导航页面全部接入真实只读数据后的前端收口审计。当前阶段只审计前端只读请求面、页面操作入口和文档边界，不新增后端接口、不开放写操作、不做登录/鉴权。

审计日期：2026-07-09

## 1. 审计结论

结论：当前 `web/owner-console` 前端仍保持只读 v0 边界。

已确认：

```text
所有 API client 请求都通过 ownerConsoleApi。
ownerConsoleApi 只使用 fetch GET。
前端 allowlist 只包含 Owner Console 只读 HTTP 资源。
动态详情路径只允许正整数 ID。
没有请求 /docs、/redoc 或 /openapi.json。
没有 approve / reject / resume / create / cancel 类型 API client。
主导航页面已经全部接入真实只读数据。
任务详情和审批详情仍只从列表跳转进入，不放入主导航。
页面按钮仅用于刷新或筛选。
页面链接仅用于查看详情或返回列表。
没有 Web 审批确认、拒绝、恢复执行、配置保存、角色卡切换、名单修改、记忆写入或索引重建入口。
```

本次顺手移除：

```text
删除未使用的 PlaceholderPage。
主导航已无占位业务页，避免后续审计误把占位文案当作真实页面状态。
```

## 2. 当前页面覆盖

| 前端页面 | 后端资源 | 状态 | 写操作入口 |
| --- | --- | --- | --- |
| `/owner-console` | `GET /overview`, `GET /diagnostics` | 已接真实数据 | no |
| `/owner-console/tasks` | `GET /tasks` | 已接真实数据 | no |
| `/owner-console/tasks/:task_id` | `GET /tasks/{task_id}` | 已接真实数据 | no |
| `/owner-console/approvals` | `GET /approvals` | 已接真实数据 | no |
| `/owner-console/approvals/:approval_id` | `GET /approvals/{approval_id}` | 已接真实数据 | no |
| `/owner-console/diagnostics` | `GET /diagnostics` | 已接真实数据 | no |
| `/owner-console/memory` | `GET /memory` | 已接真实数据 | no |
| `/owner-console/access-control` | `GET /access-control` | 已接真实数据 | no |
| `/owner-console/settings` | `GET /settings` | 已接真实数据 | no |

AppShell 额外读取：

```text
GET /healthz
GET /api/v1/owner-console/routes
```

用途是顶部状态条和只读 route contract，不承载业务写操作。

## 3. 请求面审计

当前唯一 HTTP client：

```text
web/owner-console/src/api/ownerConsoleApi.ts
```

固定 allowlist：

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

请求方式：

```text
fetch(path, { method: "GET", headers: { Accept: "application/json" } })
```

当前 API client 方法：

```text
getHealth()
getRoutes()
getOverview()
getDiagnostics()
getMemory()
getAccessControl()
getSettings()
getTasks()
getTaskDetail()
getApprovals()
getApprovalDetail()
```

未出现：

```text
POST
PUT
PATCH
DELETE
approveApproval
rejectApproval
resumeApproval
createTask
cancelTask
saveSettings
switchRoleCard
updateAccessControl
rebuildMemoryIndex
runDiagnosticsProbe
```

## 4. 操作入口审计

当前页面 `<button>` 用途：

```text
AppShell：刷新顶部 health/routes 状态。
Dashboard：刷新概览。
Tasks：刷新任务、任务状态筛选。
Task Detail：刷新详情。
Approvals：刷新审批、审批状态筛选。
Approval Detail：刷新详情。
Diagnostics：刷新诊断快照。
Memory：刷新记忆快照。
Access Control：刷新访问控制快照。
Settings：刷新设置快照。
```

当前页面 `<Link>` 用途：

```text
任务列表 -> 任务详情
任务详情 -> 审批详情
审批列表 -> 审批详情
审批详情 -> 任务详情
详情页 -> 返回列表
```

未出现可点击写入口：

```text
确认审批
拒绝审批
恢复执行
创建任务
取消任务
重试任务
推进任务
保存设置
切换角色卡
添加白名单
移除白名单
拉黑用户
解除拉黑
新增记忆
删除记忆
运行诊断探测
清空缓存
清空错误日志
重建索引
```

## 5. 搜索命中说明

审计搜索中仍会命中一些写相关词，但它们不是操作入口：

```text
已确认 / 已拒绝：
  审批状态筛选和状态展示。

approved / rejected：
  审批状态枚举和 Promise.allSettled rejected 分支。

拒绝：
  陌生私聊策略 deny 的中文展示。

索引重建：
  Memory 页展示 index_rebuild_executed=false 的只读边界。

approval_resume / can_approve / can_reject：
  后端 DTO 元数据字段，只展示只读 actionability，不生成操作按钮。
```

这些命中不构成 Web 写能力。

## 6. 关键边界

当前仍保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent。
MainAgent 和 ChatAgent 继续分离。
ProjectDocRAG 只允许在显式 /agent dev_context 中使用，不能进入普通聊天。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复执行。
不开放多步写自动化。
不新增额外 QQ 发送副作用。
Web Owner Console v0 只读。
Web 前端不导入 Python runtime。
Web 前端不读取本地数据库、日志、prompt、.env 或 access.json。
Web 前端不打开 OpenAPI / docs / redoc。
```

## 7. 验证命令

前端审计搜索：

```text
rg -n "fetch\(|method:|post\(|put\(|patch\(|delete\(|/openapi|/docs|/redoc|approve|reject|resume|createTask|cancelTask|确认|拒绝|删除|保存|提交|添加|移除|重建|运行诊断|清空|切换" web\owner-console\src

rg -n "<button|<Link|to=|href=|ownerConsoleApi\." web\owner-console\src

rg -n "PlaceholderPage|占位|暂无业务快照" web\owner-console\src
```

构建与后端契约验证：

```text
npm run guard:readonly
npm run typecheck
npm run build
npm audit

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

## 8. 后续建议

下一阶段建议先不要直接开放写操作。

更稳的路线：

```text
P2.37：补一层前端 smoke / contract guard，自动校验 ownerConsoleApi 只允许 GET 和 allowlist。已落地，见 docs/web-owner-console-frontend-contract-guard.md。
P2.38：Web Owner Console v0 使用手册和启动 runbook。已完成。
P2.39-P2.39b：本地部署设计、静态模式和启停脚本。已完成。
P2.40：只读自动刷新策略设计。已完成，见 docs/web-owner-console-readonly-auto-refresh-design.md。
P2.40a：受控自动刷新基础设施与 AppShell health 检查。已完成。
P2.43：首个正式 MainAgent 只读工作任务模型，见 docs/main-agent-first-readonly-work-task-design.md。
P2.40b-P2.40c：在 P2.43c 后再评估允许轮询的页面，并完成 guard / smoke 收口。
P2.41：设计本地访问保护 / 鉴权。
P2.42：单独设计 Web 审批操作，不复用当前只读 v0。
```

当前不建议直接做：

```text
审批按钮。
写操作 API。
公网部署。
未经 P2.40a 实现和 guard 验证的自动轮询。
WebSocket / SSE。
登录页假实现。
```
