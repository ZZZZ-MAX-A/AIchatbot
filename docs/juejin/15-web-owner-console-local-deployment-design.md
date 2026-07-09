# 给 AI Chatbot 做本地 Web 控制台时，我为什么先设计部署边界

标签建议：`AI Agent`、`FastAPI`、`React`、`前端工程化`、`架构设计`

## 开头

上一篇里，我给 AIchatbot 的 Web Owner Console 先设计了 read model。

当时我没有急着写页面，而是先确定：

```text
未来控制台要有哪些页面。
每个页面读哪些数据。
后端返回什么结构化 DTO。
哪些能力不能因为有了 Web 页面就被打开。
```

后来这条线继续往前走了一点：

```text
FastAPI 只读 HTTP adapter 已经有了。
Vite + React + TypeScript 前端工程已经有了。
Dashboard、Tasks、Approvals、Diagnostics、Memory、Access Control、Settings 都接了真实只读数据。
前端也补了 guard，检查它只能调用 GET allowlist。
```

到这里，一个新的问题出现了：

```text
这个控制台以后应该怎么在本地跑？
```

现在开发时是两个服务：

```text
FastAPI: 127.0.0.1:8090
Vite:   127.0.0.1:5173
```

这对开发很好，但对日常使用来说，总觉得还差一步。

所以这一篇记录的不是“怎么上线”，而是我为什么先设计 Web Owner Console 的本地部署边界。

## 现在的运行方式很好，但它只是开发模式

当前前端通过 Vite dev server 运行：

```text
http://127.0.0.1:5173/owner-console
```

Vite 负责把 API 请求代理到 FastAPI：

```text
/healthz -> http://127.0.0.1:8090/healthz
/api/v1/owner-console -> http://127.0.0.1:8090/api/v1/owner-console
```

这个模式适合开发：

```text
前端热更新方便。
React 报错好定位。
CSS 调整很快。
后端 API 可以独立 smoke。
```

但如果只是日常打开控制台看一下任务、审批、诊断和记忆状态，每次都开两个窗口就有点笨重。

更自然的本地使用方式是：

```text
npm run build 生成前端 dist。
FastAPI 可选挂载这个 dist。
浏览器直接访问 http://127.0.0.1:8090/owner-console。
```

看起来只是少开一个服务，但里面有几个边界必须提前想清楚。

## 我没有把 API 和页面混在同一个路径下

最重要的设计是路径分层。

我保留了三个清晰的路径区：

```text
/healthz
  后端健康检查。

/api/v1/owner-console/*
  Owner Console JSON API。

/owner-console/*
  Web Owner Console 前端页面。
```

也就是说，API 永远在：

```text
/api/v1/owner-console
```

页面永远在：

```text
/owner-console
```

我没有选择这些写法：

```text
/owner-console/api
/api/v1/owner-console/page
/api/v1/owner-console/assets
```

原因很简单：控制台以后一定会变复杂。

如果 API 和页面路径一开始就混在一起，后面加登录、加审批操作、加静态资源、加前端路由时，命名会越来越含糊。

分开以后，规则就很直观：

```text
/api/v1/owner-console/* 只返回 JSON。
/owner-console/* 只返回 HTML/JS/CSS 等前端资源。
```

这个边界比“靠大家记住不要乱写”可靠得多。

## SPA fallback 只能服务页面，不能吞 API

React Router 里有这种页面：

```text
/owner-console/tasks/1
/owner-console/approvals/1
```

这些不是后端真实 HTML 文件，而是前端客户端路由。

所以当浏览器刷新：

```text
http://127.0.0.1:8090/owner-console/tasks/1
```

后端应该返回同一份：

```text
dist/index.html
```

然后由 React Router 渲染任务详情。

这就是 SPA fallback。

但这个 fallback 必须非常窄。

允许的是：

```text
/owner-console/tasks/1 -> index.html
```

禁止的是：

```text
/api/v1/owner-console/tasks/1 -> index.html
/docs -> index.html
/redoc -> index.html
/openapi.json -> index.html
```

实现时最怕写出这种过宽路由：

```text
/{path:path} -> index.html
```

它看起来方便，但会把 API 404、docs 404、未知路径全部吞成前端页面。

这种问题很隐蔽。浏览器里看起来“页面有返回”，但 API 契约已经被污染了。

所以我的设计里明确要求：

```text
fallback 只命中 /owner-console。
fallback 不是 API fallback。
fallback 不是全站 catch-all。
```

这句话很啰嗦，但值得写进文档。

## 静态资源缺失要返回 404，不要返回 index.html

还有一个小坑：`assets`。

Vite build 后通常会生成：

```text
/owner-console/assets/index-xxxx.js
/owner-console/assets/index-xxxx.css
```

这些是真实静态文件，不是前端路由。

所以：

```text
/owner-console/assets/index-xxxx.js
```

文件存在就返回 JS。

但如果访问：

```text
/owner-console/assets/missing.js
```

应该返回：

```text
404
```

不能 fallback 到 `index.html`。

否则浏览器会拿 HTML 当 JS 解析，最后报一堆 MIME type 或模块加载错误。问题很小，但很恶心。

所以我把规则写死：

```text
/owner-console/assets/{file}
  文件存在：返回静态文件。
  文件不存在：返回 404。
  不 fallback 到 index.html。
```

## Vite build base 要和部署路径一致

如果页面挂在：

```text
/owner-console
```

那么前端构建资源也应该从这里加载：

```text
/owner-console/assets/...
```

这意味着未来实现时，Vite build 要配置：

```text
base = /owner-console/
```

这里还有一个容易混淆的点：

```text
页面 base 和 API base 不是一回事。
```

页面 base 是：

```text
/owner-console/
```

API base 仍然是：

```text
/api/v1/owner-console
```

健康检查仍然是：

```text
/healthz
```

它们不能因为静态部署就合并。

## /docs、/redoc、/openapi.json 继续关闭

FastAPI 默认很容易开放：

```text
/docs
/redoc
/openapi.json
```

但当前 Owner Console 仍是本地只读 v0，我选择继续关闭它们。

不是因为 OpenAPI 本身有问题，而是因为它会新增一个“可探索接口页面”。

当前系统的边界是靠这些东西维护的：

```text
read model 文档
HTTP contract 测试
前端 GET allowlist
readonly guard
runbook
```

在还没有设计鉴权、写操作和公开 schema 边界之前，不需要多开放一个浏览器 API 面板。

未来如果要打开，也应该单独讨论：

```text
只读 schema 是否可见？
是否需要 token？
是否允许 docs 页面直接发请求？
未来写接口是否隐藏？
是否只允许本机访问？
```

所以当前结论是：

```text
/docs -> 404
/redoc -> 404
/openapi.json -> 404
```

即使挂载前端页面，也不改变这个决定。

## 静态模式应该是显式开关，不是默认行为

我还设计了一个显式开关：

```text
OWNER_CONSOLE_STATIC_ENABLED=false
OWNER_CONSOLE_STATIC_DIR=web/owner-console/dist
```

默认关闭。

原因是现在的 FastAPI app 还有一个职责：后端 smoke 和 HTTP contract 测试。

如果默认突然开始服务静态页面，测试面会变大，边界也会变得不够明显。

所以更稳的语义是：

```text
false：
  FastAPI 只提供 JSON API。
  /owner-console 返回 404。

true：
  FastAPI 同时提供 JSON API 和前端静态页面。
  /api/v1/owner-console 仍然只返回 JSON。
  /owner-console 返回页面。
```

如果打开静态模式但 dist 不存在，我倾向于直接启动失败。

因为这类问题越早暴露越好。

## 静态页面仍然只能调用 GET allowlist

这一步只是本地部署设计，不是写操作设计。

当前前端仍然只能调用这些：

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

以后即使这个控制台只在本机使用，也不能因为“本机”两个字就顺手加写按钮。

Web 写操作应该走单独阶段：

```text
先设计本地访问保护或鉴权。
再设计 Web 审批 decision 资源。
再设计前端写操作状态和二次确认。
最后修改 guard 和后端 contract。
```

否则写能力会从一个“明确设计过的能力”变成“顺手加上的按钮”。

这对 Agent 系统很危险。

## 这次设计真正想解决什么

表面上看，这次只是在讨论：

```text
FastAPI 要不要挂载 dist？
页面刷新时怎么返回 index.html？
Vite base 怎么写？
```

但真正要解决的是：

```text
不要让前端部署方式反过来污染后端 API 边界。
不要让页面 fallback 变成全站 fallback。
不要让本地静态页面成为写操作的偷渡入口。
```

所以最后的结构是：

```text
开发模式继续保留：
  FastAPI 8090 + Vite 5173。

本地静态模式可选开启：
  FastAPI 8090 同时服务 API 和 /owner-console 页面。

API 和页面严格分离：
  /api/v1/owner-console/*
  /owner-console/*

OpenAPI 页面继续关闭：
  /docs
  /redoc
  /openapi.json

前端请求继续受 GET allowlist 约束。
```

这一步没有让系统看起来更炫。

但它让后续实现更不容易长歪。

## 下一步

我给后续拆了几步：

```text
P2.39a：按设计实现可选本地静态模式。
P2.40：设计只读自动刷新策略。
P2.41：设计本地访问保护 / 鉴权。
P2.42：设计 Web 审批操作。
```

如果进入实现，我会先做：

```text
配置 Vite build base=/owner-console/。
FastAPI 增加显式静态模式开关。
只给 /owner-console 做 index.html fallback。
补测试确认 /api/v1/owner-console 不受影响。
确认 /docs、/redoc、/openapi.json 仍然是 404。
确认缺失 assets 返回 404。
```

这就是我现在对 AIchatbot Web Owner Console 的判断：

```text
页面可以慢慢变强，
但路径、fallback、allowlist 和写操作边界必须先变清楚。
```
