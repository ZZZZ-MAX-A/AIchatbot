# Web Owner Console read-only auto-refresh design

本文记录 P2.40 Web Owner Console 只读自动刷新策略设计。

设计日期：2026-07-11。

本文最初只做设计和文档收口。P2.40a 已实现受控 hook、AppShell 内存态开关、页面可见性、失败暂停、health 低频检查和生命周期测试；P2.43c 已形成真实 running 任务生命周期，但 Dashboard、Tasks、Approvals 与两个 Detail 页面仍未接周期刷新，等待根据实际工作负载单独批准 P2.40b。

## 1. 设计结论

Web Owner Console 适合使用低频、可关闭、页面可见时才运行的 HTTP GET 轮询，不直接引入 WebSocket、SSE、TanStack Query 或全局状态库。

第一版策略：

```text
默认关闭自动刷新。
用户显式打开后，只在当前浏览器页面生命周期内生效。
刷新偏好只保存在 AppShell 内存中，不写 localStorage 或 sessionStorage。
浏览器完整刷新后恢复为关闭。
页面隐藏时暂停自动请求。
只刷新当前活动路由，不刷新未挂载页面。
同一资源不允许并发或重叠刷新。
失败后不立即重试，不做激进指数重试。
连续失败达到阈值后暂停自动刷新，等待手动恢复。
手动刷新始终保留。
所有自动请求继续经过 ownerConsoleApi GET allowlist。
```

推荐固定频率：

```text
AppShell health：60 秒，仅在自动刷新开启时检查。
Dashboard overview：60-120 秒（P2.40b 单独批准后才接入）。
Tasks：60-120 秒（P2.40b 单独批准后才接入）。
Task Detail：60-120 秒（P2.40b 单独批准后才接入）。
Approvals：60-120 秒（P2.40b 单独批准后才接入）。
Approval Detail：60-120 秒（P2.40b 单独批准后才接入）。
```

以下资源保持手动刷新：

```text
routes contract
Dashboard diagnostics section
Diagnostics
Memory
Access Control
Settings
```

## 2. 当前基线

当前前端已经具备：

```text
唯一 HTTP client：web/owner-console/src/api/ownerConsoleApi.ts。
所有 HTTP 请求都是 GET。
所有路径都经过只读 allowlist。
每个页面独立维护 loading / data / error。
页面挂载时读取一次数据。
每个页面保留显式刷新按钮。
AppShell 独立读取 health 和 routes。
AbortController 会在页面卸载时取消初始请求。
```

当前明确没有：

```text
setInterval。
setTimeout 轮询。
visibilitychange 监听。
后台刷新状态。
跨页面请求缓存。
WebSocket / SSE client。
Service Worker 或 Background Sync。
```

P2.40 不改变“页面首次进入时自动加载一次”的现有行为。本文所说的“默认关闭自动刷新”，只指首次加载之后的周期性刷新默认关闭。

## 3. 目标与非目标

目标：

```text
让任务、审批和概览在主人主动开启后低频更新。
页面不可见时停止产生请求。
避免慢请求重叠和路由切换后的旧请求回写。
失败时保留最近一次成功数据。
让自动刷新状态和最后成功时间可观察。
继续保持前端 GET-only 和后端只读边界。
把定时器限制在一个受控 hook 中，便于 guard 审计。
```

非目标：

```text
不追求秒级实时性。
不监听数据库变更。
不新增后端 push channel。
不新增 WebSocket 或 SSE endpoint。
不新增审批确认、拒绝或恢复执行。
不新增登录/鉴权。
不新增跨标签页同步。
不新增离线缓存或后台同步。
不改变 QQ / NoneBot / MainAgent 行为。
```

## 4. 为什么选择低频轮询

当前 Owner Console 是单机、只读、低并发的本地控制台。任务和审批状态会变化，但没有要求亚秒级展示。

低频 HTTP GET 轮询可以直接复用：

```text
现有 FastAPI GET route。
现有 JSON envelope。
现有 ownerConsoleApi allowlist。
现有 AbortSignal 参数。
现有页面 data/error 状态。
```

WebSocket / SSE 会额外引入：

```text
新的后端连接 endpoint。
连接重建和心跳。
浏览器隐藏后的连接策略。
事件顺序和丢失恢复。
服务关闭时的重连风暴控制。
新的鉴权和部署边界。
新的 guard 与 contract 测试面。
```

这些复杂度对当前本地只读场景没有足够收益，因此不进入 P2.40。

## 5. 页面策略矩阵

| 页面或资源 | 自动刷新 | 周期 | 自动刷新内容 | 保持手动的内容 |
| --- | --- | --- | --- | --- |
| AppShell | 可选 | 60 秒 | `GET /healthz` | `GET /routes` |
| Dashboard | P2.40b 单独批准后 | 60-120 秒 | `GET /overview` | `GET /diagnostics` |
| Tasks | P2.40b 单独批准后 | 60-120 秒 | 当前筛选条件下的 `GET /tasks` | 无 |
| Task Detail | P2.40b 单独批准后 | 60-120 秒 | 当前 ID 的 `GET /tasks/{task_id}` | 无 |
| Approvals | P2.40b 单独批准后 | 60-120 秒 | 当前筛选条件下的 `GET /approvals` | 无 |
| Approval Detail | P2.40b 单独批准后 | 60-120 秒 | 当前 ID 的 `GET /approvals/{approval_id}` | 无 |
| Diagnostics | 否 | 手动 | 无 | `GET /diagnostics` |
| Memory | 否 | 手动 | 无 | `GET /memory` |
| Access Control | 否 | 手动 | 无 | `GET /access-control` |
| Settings | 否 | 手动 | 无 | `GET /settings` |

理由：

```text
Overview、Tasks、Approvals 和 Detail 展示的是工作流状态，低频变化值得更新。
Diagnostics 是聚合诊断快照，不应因为停留页面而持续读取。
Memory、Access Control、Settings 变化频率低，手动刷新足够。
routes contract 在同一次前端运行期间应稳定，不需要周期读取。
health 可以低频检查连接状态，但不应和每个页面请求绑定成同一批次。
```

Dashboard 当前手动刷新会同时读取 overview 和 diagnostics。后续实现自动刷新时应拆分：

```text
首次加载：overview + diagnostics。
手动刷新：overview + diagnostics。
自动刷新：只读取 overview。
```

## 6. 开关与生命周期

推荐由 AppShell 持有：

```text
autoRefreshEnabled: boolean
```

规则：

```text
初始值固定为 false。
用户打开后，在前端路由跳转期间保持。
浏览器完整刷新后回到 false。
不从 URL、环境变量或后端响应自动开启。
不写 localStorage、sessionStorage、cookie 或数据库。
```

AppShell 根据当前路由策略决定是否存在页面轮询：

```text
自动刷新关闭：所有周期请求停止。
自动刷新开启 + 可轮询页面：启动当前页面的受控调度。
自动刷新开启 + 手动页面：页面数据不轮询，只保留低频 health 检查。
离开页面：取消该页面的定时器和未完成自动请求。
进入新页面：按新页面策略重新计算下一次刷新时间。
```

不建议把开关放进每个页面各自保存。AppShell 内存态可以避免页面之间出现互相矛盾的多个轮询开关，同时不会形成长期持久偏好。

## 7. 页面可见性

自动刷新只能在下面条件同时满足时调度：

```text
autoRefreshEnabled=true。
当前路由允许自动刷新。
document.visibilityState === "visible"。
当前没有同资源请求在执行。
当前资源没有进入失败暂停状态。
```

页面变为 hidden 时：

```text
清除下一次自动刷新定时器。
取消正在执行的自动刷新请求。
不累计隐藏期间错过的刷新次数。
不在后台排队。
```

页面重新变为 visible 时：

```text
如果距离上次完成已超过一个周期，只补一次刷新。
补刷新延迟约 1 秒，避免切回标签页瞬间与浏览器恢复请求重叠。
如果尚未到周期，等待剩余时间。
绝不补发隐藏期间的多次请求。
```

手动刷新不依赖自动刷新开关。用户在可见页面点击刷新时，仍可以立即请求。

## 8. 调度与并发

推荐新增单一 hook：

```text
web/owner-console/src/hooks/useControlledAutoRefresh.ts
```

推荐使用“请求完成后再安排下一次”的 `setTimeout`，不使用固定节拍 `setInterval`。这样慢请求不会和下一次 tick 重叠。

核心行为：

```text
同一 hook 同时最多一个请求。
下次计时从本次请求完成后开始。
手动刷新开始时，取消待执行的自动 timer。
手动刷新成功后，重新从完整周期计时。
自动请求执行中不再启动手动请求，刷新按钮显示 busy，避免同资源重复读取。
手动请求执行中遇到自动 tick 时跳过该 tick，等待手动请求完成后重新计时。
自动刷新执行中再次收到 tick 时直接跳过，不排队。
路由参数或筛选条件变化时取消旧请求并重新加载。
组件卸载时 abort 请求并清除 timer。
关闭自动刷新时 abort 自动请求并清除 timer。
```

hook 应区分请求原因：

```text
initial
manual
auto
visibility_resume
```

页面可以据此决定 loading UI，而不是把所有请求都当成首次加载。

## 9. 页面状态模型

当前页面通常只有一个 `loading` 布尔值。实现自动刷新前，应避免后台刷新把已有内容替换成整页 loading。

推荐页面状态：

```text
data
error
initialLoading
manualRefreshing
autoRefreshing
lastSuccessfulAt
consecutiveAutoFailures
autoRefreshPausedReason
```

展示规则：

```text
首次加载：可以显示现有 loading panel。
手动刷新：刷新按钮进入 busy 状态，已有数据可以继续显示。
自动刷新：保留已有数据，只显示轻量后台刷新状态。
自动刷新失败：保留最近成功数据，同时显示数据可能已过期。
首次加载失败且没有旧数据：继续使用现有 ErrorState。
```

AppShell 当前“最后刷新”只代表 health/routes。后续实现时应避免让它看起来像所有页面数据的统一时间：

```text
顶部时间改成“连接检查”。
页面资源头显示自己的“数据更新”时间。
```

## 10. 失败与恢复

自动刷新失败时不立即重试。

建议分类：

```text
网络错误或 HTTP 5xx：等待正常周期后再试。
连续 3 次网络错误或 5xx：暂停该资源自动刷新。
HTTP 400 / 403 / 404：立即暂停该资源自动刷新。
envelope contract mismatch：立即暂停该资源自动刷新。
AbortError：不计为失败。
```

暂停后：

```text
保留最近一次成功数据。
停止该资源 timer。
保留手动刷新按钮。
手动刷新成功后清零失败计数并恢复调度。
用户关闭再打开自动刷新时清零失败计数。
```

不做：

```text
立即 retry。
一秒级 retry。
无限指数退避。
多个失败请求并行探测。
失败后自动切换 endpoint。
失败后触发 QQ 通知或 MainAgent。
```

health 和当前页面资源应各自维护失败状态。health 失败不应自动取消页面已有的成功数据；页面资源失败也不应改写只读 contract 状态。

## 11. 请求预算

任意时刻只会挂载一个业务页面。P2.40b 如经实际工作负载确认接入，按推荐周期，自动刷新开启时的稳定请求上限是：

```text
可轮询业务页面：每分钟 0.5-1 次 GET。
AppShell health：每分钟 1 次 GET。
合计：每分钟最多约 2 次周期 GET，不含用户手动刷新。
```

Dashboard 自动刷新只读取 overview，不周期读取 diagnostics，因此同样保持每分钟最多约 2 次周期 GET。

手动页面只保留 health 低频检查，页面资源本身不产生周期请求。

## 12. UI 与可访问性

后续实现建议在顶部状态区增加二元 toggle：

```text
自动刷新：关闭 / 开启
```

同时显示当前路由状态：

```text
等待刷新
正在刷新
页面隐藏，已暂停
连续失败，已暂停
当前页面仅手动刷新
```

要求：

```text
手动刷新按钮始终保留。
自动刷新不能导致页面内容闪空或布局跳动。
后台成功不反复触发 aria-live 播报。
暂停和错误可以通过现有状态 badge 或非阻塞 banner 呈现。
开关必须使用原生 button/toggle 语义和清晰的 aria 状态。
```

## 13. 前端目录建议

后续实现可以增加：

```text
src/hooks/useControlledAutoRefresh.ts
  唯一定时器、visibility 和自动请求生命周期入口。

src/app/AutoRefreshContext.tsx
  AppShell 内存态开关和当前策略上下文。

src/app/ownerConsoleRefreshPolicy.ts
  页面资格、固定周期、失败阈值等纯配置。

src/components/AutoRefreshControl.tsx
  开关和当前状态展示。
```

不建议新增：

```text
Redux / Zustand store。
TanStack Query。
自定义 EventEmitter。
跨标签 BroadcastChannel。
Service Worker。
```

## 14. guard 约束

P2.40a 已扩展 `npm run guard:readonly`：

```text
setInterval 只能出现在 useControlledAutoRefresh.ts；第一版实现应尽量完全不使用。
setTimeout / clearTimeout 只能由受控 auto-refresh hook 管理。
document.visibilityState 和 visibilitychange 只能出现在受控 hook。
业务页面不能各自创建 timer。
自动刷新仍只能调用现有 ownerConsoleApi 方法。
ownerConsoleApi 仍只允许 GET 和现有 allowlist。
Diagnostics、Memory、Access Control、Settings 不能注册周期刷新。
```

guard 仍然不能替代运行时测试。它只用于防止定时器散落和请求面扩大。

## 15. 测试策略

P2.40a 已首次引入需要精确控制 timer 和 DOM visibility 的前端生命周期测试：

```text
Vitest
jsdom
@testing-library/react renderHook
```

hook 接收可注入的异步 refresh callback，单测不启动 FastAPI，也不请求真实 API；当前不需要引入 MSW。

P2.40a 当前已覆盖：

```text
默认关闭时不会创建 timer。
开启后按固定周期调用一次 refresh。
页面 hidden 时不调用。
从 hidden 回到 visible 时最多补一次。
慢请求不会重叠。
关闭开关会清 timer 并 abort 自动请求。
组件卸载会清 timer 并 abort 请求。
AbortError 不增加失败次数。
网络错误不会立即重试。
连续 3 次失败后暂停。
400 / 403 / 404 / contract mismatch 立即暂停。
手动刷新成功后恢复自动调度。
手动刷新执行期间不会触发自动请求。
自动请求执行期间拒绝并发手动刷新。
```

P2.40b 页面接入时继续补：

```text
筛选条件或详情 ID 变化时旧请求不会回写。
Dashboard 自动刷新不调用 diagnostics。
Diagnostics、Memory、Access Control、Settings 没有业务 timer。
```

前端验证继续包含：

```powershell
npm run guard:readonly
npm run typecheck
npm run build
npm audit
```

后端未改动，但回归仍应保留：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

浏览器手工验证应同时覆盖 Vite 开发模式和 FastAPI 本地静态模式。

## 16. 安全与行为边界

P2.40 必须继续保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent。
MainAgent 和 ChatAgent 继续分离。
ProjectDocRAG 只允许在显式 /agent dev_context 中使用。
自动刷新不会调用 ProjectDocRAG、MemoryRAG 检索或索引重建。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有 approval_resume_enabled=true 的注册工具可以审批恢复。
不开放多步写自动化。
不新增 QQ 发送副作用。
Web Owner Console 继续只读。
不新增 POST / PUT / PATCH / DELETE。
不新增登录/鉴权。
不开放 /docs、/redoc、/openapi.json。
不提交 web/owner-console/dist。
```

自动刷新只是重复执行已经允许的 GET，不是新的工具能力，也不能成为触发 MainAgent 或 owner_write_runtime 的入口。

## 17. 推荐实现拆分

如果后续进入实现，建议分三刀：

```text
P2.40a：受控 hook、内存态开关、可见性和失败状态。已完成。
  AppShell 只接 health 60 秒低频检查，不扩大业务页面请求面。

P2.40b：在确认实际工作负载需要后，再接入 Dashboard、Tasks、Approvals 和两个 Detail 页面。
  Dashboard 自动刷新只读 overview。
  Diagnostics、Memory、Access Control、Settings 保持手动。

P2.40c：扩展 readonly guard、更新 runbook、做浏览器 smoke。
  验证开发模式和本地静态模式行为一致。
```

P2.40 设计阶段本身不执行以上实现。

## 18. 后续路线

建议后续顺序：

```text
P2.40：只读自动刷新策略设计。已完成。
P2.40a：受控自动刷新基础设施与测试。已完成。
P2.43：首个正式 MainAgent 只读工作任务模型及只读展示回归。已完成。
P2.40b：仍保持人工评估；只有实际工作负载需要时才接入允许轮询的页面。
P2.40c：guard、runbook 和浏览器 smoke 收口。
P2.41：设计本地访问保护 / 鉴权。
P2.42：单独设计 Web 审批操作。
```

在 P2.41 和 P2.42 前，自动刷新不能被用来顺手开放任何 Web 写操作。
