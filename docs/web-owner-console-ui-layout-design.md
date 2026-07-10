# Web Owner Console UI layout design

本文记录 P2.30 Web Owner Console UI 布局设计。当前阶段只做页面结构和中文化展示设计，不创建前端工程、不写 React 组件、不写 CSS、不修改 FastAPI 行为。

后续实现状态：P2.31 已创建 `web/owner-console` 最小只读 App Shell，采用本文定义的中文左侧导航和中文顶部状态条，第一刀只接 `/healthz` 和 `/api/v1/owner-console/routes`。P2.32 已在概览页接入 `/overview` 和 `/diagnostics` 真实只读数据。P2.33 已接入任务列表 `/tasks`，支持中文状态筛选和只读表格展示。P2.34 已接入任务详情 `/tasks/{task_id}`、审批列表 `/approvals` 和审批详情 `/approvals/{approval_id}`。P2.35 已接入诊断页 `/diagnostics`、记忆页 `/memory`、访问控制页 `/access-control` 和设置页 `/settings`，主导航页面已全部接入真实只读数据。P2.36 已完成前端只读收口审计，见 `docs/web-owner-console-frontend-readonly-audit.md`。P2.37 已新增 `npm run guard:readonly` 前端只读 contract guard，见 `docs/web-owner-console-frontend-contract-guard.md`，仍不开放 Web 写操作。

## 1. 设计定位

Web Owner Console 第一版走简约工具风格：

```text
结构优先。
状态优先。
信息密度适中。
中文展示。
只读边界明确。
少装饰。
少动画。
不做营销式 landing page。
```

它应该更像一个安静的运维控制台，而不是产品官网或聊天界面。

优先级：

```text
1. 页面结构清楚。
2. 系统状态清楚。
3. 任务和审批脉络清楚。
4. 错误态和空态清楚。
5. 视觉风格简约一致。
```

暂不追求：

```text
复杂图表。
复杂动画。
大面积渐变。
大 Hero。
卡片套卡片。
像素级完整设计系统。
```

## 2. 布局总览

第一版采用三段式布局：

```text
左侧固定导航。
顶部状态条。
右侧主内容区。
```

桌面端布局：

```text
+---------------------------------------------------------+
| 左侧导航 | 顶部状态条：主人控制台 / 只读 / 后端 / 刷新 |
|          |----------------------------------------------|
|          | 页面标题 / 页面操作区                        |
|          |----------------------------------------------|
|          | 主内容                                      |
+---------------------------------------------------------+
```

移动端后续再细化。第一版只需要保证布局不崩，不优先做移动端复杂交互。

## 3. 中文导航结构

左侧固定导航使用中文标签：

| 路由 | 中文标签 | 英文资源含义 | 是否主导航 |
| --- | --- | --- | --- |
| `/owner-console` | 概览 | Dashboard | yes |
| `/owner-console/tasks` | 任务 | Tasks | yes |
| `/owner-console/approvals` | 审批 | Approvals | yes |
| `/owner-console/diagnostics` | 诊断 | Diagnostics | yes |
| `/owner-console/memory` | 记忆 | Memory | yes |
| `/owner-console/access-control` | 访问控制 | Access Control | yes |
| `/owner-console/settings` | 设置 | Settings | yes |
| `/owner-console/tasks/:task_id` | 任务详情 | Task Detail | no |
| `/owner-console/approvals/:approval_id` | 审批详情 | Approval Detail | no |

规则：

```text
任务详情不放入主导航，从任务列表点击进入。
审批详情不放入主导航，从审批列表点击进入。
左侧导航不要出现英文页面名。
页面内部可以在调试区或 tooltip 中保留 resource 名称，但默认展示中文。
```

导航顺序固定为：

```text
概览
任务
审批
诊断
记忆
访问控制
设置
```

## 4. 顶部状态条

每个页面都显示顶部状态条。状态条使用中文，不直接把后端字段裸露成英文。

建议展示：

| 后端字段 | 中文展示 | 示例 |
| --- | --- | --- |
| `service=owner-console` | 主人控制台 | 主人控制台 |
| `read_only=true` | 只读模式 | 只读模式：已开启 |
| `web_write_enabled=false` | 网页写入 | 网页写入：已关闭 |
| backend reachable | 后端连接 | 后端连接：已连接 |
| backend unreachable | 后端连接 | 后端连接：已断开 |
| `schema_version` | 接口版本 | 接口版本：owner_console.http.v1 |
| `generated_at` / client time | 最后刷新 | 最后刷新：2026-07-09 18:30:12 |

顶部状态条中文文案建议：

```text
主人控制台
只读模式：已开启
网页写入：已关闭
后端连接：已连接
接口版本：owner_console.http.v1
最后刷新：YYYY-MM-DD HH:mm:ss
刷新
```

如果后端断开：

```text
后端连接：已断开
```

如果 contract mismatch：

```text
接口契约异常
```

如果 `web_write_enabled` 不是 `false`：

```text
网页写入状态异常
```

并进入保护态，不渲染任何可能被误解为操作入口的控件。

## 5. 字段中文化规则

后端 JSON 字段继续保持英文 snake_case，这是 HTTP contract。前端 UI 展示必须中文化，这是阅读体验。

规则：

```text
接口字段不改名。
TypeScript DTO 保留后端字段名。
页面标题、表头、状态、错误态、空态全部中文。
技术字段可以在详情或 tooltip 中显示原始值。
```

常用字段中文映射：

| 原始字段 | 中文标签 |
| --- | --- |
| `read_only` | 只读模式 |
| `http_api_enabled` | HTTP 接口 |
| `web_write_enabled` | 网页写入 |
| `schema_version` | 接口版本 |
| `read_model_schema_version` | 读模型版本 |
| `api_prefix` | 接口前缀 |
| `resource` | 资源 |
| `generated_at` | 生成时间 |
| `task_id` | 任务 ID |
| `approval_id` | 审批 ID |
| `tool_name` | 工具 |
| `risk_level` | 风险等级 |
| `status` | 状态 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `expires_at` | 过期时间 |
| `decided_at` | 决定时间 |
| `reason` | 原因 |
| `goal` | 目标 |
| `result` | 结果 |
| `events` | 事件 |
| `boundary` | 运行边界 |

## 6. 状态中文化规则

页面通用状态：

| 内部状态 | 中文展示 |
| --- | --- |
| `idle` | 等待加载 |
| `loading` | 正在加载 |
| `success` | 已加载 |
| `empty` | 暂无数据 |
| `bad_request` | 请求参数错误 |
| `forbidden` | 无法读取主人上下文 |
| `not_found` | 未找到 |
| `server_error` | 后端错误 |
| `network_error` | 后端连接失败 |
| `contract_mismatch` | 接口契约异常 |

HTTP error 中文展示：

```text
400 bad_request:
  请求参数错误，请检查筛选条件或 ID。

403 forbidden:
  无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。

404 not_found:
  未找到该资源，或该资源不属于主人私聊上下文。

500 internal_error:
  后端生成快照失败，请查看后端日志。

network_error:
  无法连接 Owner Console 后端，请确认 FastAPI 服务是否已启动。
```

这些错误态都应该是系统状态展示，不做夸张视觉。

## 7. 只读边界 UI 规则

第一版必须持续传达：

```text
这是只读控制台。
网页写入已关闭。
审批操作仍通过 /agent。
Web v0 不执行任何写操作。
```

页面中不出现：

```text
确认
拒绝
执行
删除
保存
提交
添加
移除
重建索引
运行诊断
清空
切换角色卡
```

如果需要说明未来能力，只能使用说明文本：

```text
当前网页版本只读，审批确认/拒绝请继续通过 /agent 执行。
```

不要用可点击按钮表达未来能力。即使是 disabled 按钮，也容易误导第一版范围。

## 8. 页面信息层级

### 8.1 概览

页面目标：

```text
给主人快速判断系统是否正常、是否有待处理任务或审批。
```

信息层级：

```text
1. 只读运行边界。
2. 任务计数。
3. 审批计数。
4. 最近任务。
5. 待审批摘要。
6. 轻量诊断摘要。
```

不放：

```text
完整设置。
完整记忆状态。
完整访问控制列表。
复杂图表。
```

### 8.2 任务

页面目标：

```text
查看任务列表、状态分布和下一步关注点。
```

主展示：

```text
表格。
```

表头中文：

```text
任务 ID
标题
目标摘要
状态
最近事件
待审批
创建时间
更新时间
下一步
```

筛选中文：

```text
全部
待处理
运行中
已完成
失败
已取消
```

### 8.3 任务详情

页面目标：

```text
查看单个任务的目标、结果、事件时间线和关联审批。
```

信息层级：

```text
1. 返回任务列表。
2. 任务基础信息。
3. 目标与结果。
4. 关联审批。
5. 事件时间线。
6. 运行边界提示。
```

### 8.4 审批

页面目标：

```text
查看审批列表，尤其是待处理审批。
```

主展示：

```text
表格。
```

表头中文：

```text
审批 ID
任务 ID
任务标题
工具
风险等级
原因摘要
状态
创建时间
过期时间
决定时间
操作状态
```

筛选中文：

```text
全部
待审批
已通过
已拒绝
已过期
```

操作状态只展示：

```text
只读展示
未来操作元数据
当前网页不执行审批
```

### 8.5 审批详情

页面目标：

```text
查看审批风险、工具输入脱敏预览、关联任务和近期事件。
```

信息层级：

```text
1. 返回审批列表。
2. 审批基础信息。
3. 工具与风险。
4. 工具输入脱敏预览。
5. 关联任务。
6. 近期任务事件。
7. 只读边界说明。
```

### 8.6 诊断

页面目标：

```text
查看轻量诊断快照，不主动探测。
```

分区：

```text
机器人状态
诊断状态
配置状态
视觉状态
图片缓存
记忆状态
语音状态
最近错误
MainAgent 观测
RootGraph 观测
```

不出现：

```text
运行诊断
重新探测
读取错误日志
测试模型
```

### 8.7 记忆

页面目标：

```text
查看记忆、MemoryRAG、ProjectDocRAG 的计数、配置和边界。
```

分区：

```text
计数
上下文策略
MemoryRAG
ProjectDocRAG
隐私边界
```

必须突出：

```text
不展示记忆正文。
不展示项目文档正文。
未执行检索。
未重建索引。
```

### 8.8 访问控制

页面目标：

```text
查看主人、私聊、群聊、白名单和黑名单状态。
```

分区：

```text
主人状态
聊天入口
未知私聊策略
私聊白名单
群聊白名单
黑名单
```

不出现：

```text
添加白名单
移除白名单
拉黑
解除拉黑
```

### 8.9 设置

页面目标：

```text
只读查看模型配置、功能开关和角色卡摘要。
```

分区：

```text
聊天模型
MainAgent 模型
Embedding
功能开关
角色卡
运行边界
```

必须突出：

```text
API Key 只显示是否已配置。
Base URL 使用脱敏显示。
不提供保存或切换按钮。
```

## 9. 通用组件清单

第一版需要的组件：

```text
AppShell
SideNav
TopStatusBar
PageHeader
StatusBadge
BoundaryBadge
DataTable
DetailSection
Timeline
LoadingState
EmptyState
ErrorState
ReadOnlyNotice
RefreshButton
```

组件中文命名可以保留英文文件名，UI 展示必须中文。

示例：

```text
文件名：TopStatusBar.tsx
展示：只读模式：已开启
```

## 10. 视觉风格

建议：

```text
浅色背景。
深色正文。
低饱和状态色。
表格线条轻。
圆角控制在 6px 到 8px。
主要内容宽度稳定。
按钮和 badge 尺寸统一。
```

避免：

```text
大面积紫蓝渐变。
大面积深蓝/灰蓝。
大面积米色/棕色。
装饰性光斑。
漂浮大卡片。
卡片套卡片。
过大的标题。
负 letter spacing。
```

页面应该像工作台，不像宣传页。

## 11. 第一版 UI 完成标准

未来开始实现前端 UI 时，第一版完成标准：

```text
1. 左侧导航使用中文。
2. 顶部状态条使用中文。
3. 所有页面标题使用中文。
4. 所有表头和状态使用中文。
5. 后端字段不直接作为主要 UI 文案裸露。
6. read_only 显示为“只读模式：已开启”。
7. web_write_enabled=false 显示为“网页写入：已关闭”。
8. backend connected/disconnected 显示为“后端连接：已连接/已断开”。
9. schema_version 显示为“接口版本”。
10. last refreshed 显示为“最后刷新”。
11. 不出现任何写操作按钮。
12. 错误态能解释 400 / 403 / 404 / 500 / network error。
13. 空态不被当作错误。
14. 页面布局不依赖营销式 Hero 或装饰图。
```

## 12. 后续路线

建议后续：

```text
P2.31：创建 web/owner-console 最小 Vite + React + TypeScript 工程，只接 /healthz 和 /routes。
P2.32：实现中文 App Shell、左侧导航和顶部状态条。
P2.33：接概览 / 任务 / 审批列表。
P2.34：接任务详情 / 审批详情。
P2.35：接 Diagnostics / Memory / Access Control / Settings。
P2.36：完成前端只读收口审计。
P2.37：补前端 smoke / contract guard。
P2.38：整理使用手册和启动 runbook。
P2.39-P2.39b：本地部署设计、静态模式和启停脚本。已完成。
P2.40：只读自动刷新策略设计。已完成，见 docs/web-owner-console-readonly-auto-refresh-design.md。
P2.40a：受控自动刷新基础设施和顶部开关。已完成。
P2.43：首个正式 MainAgent 只读工作任务模型，见 docs/main-agent-first-readonly-work-task-design.md。
P2.40b-P2.40c：在 P2.43c 后接入允许轮询的页面，并完成 guard / smoke 收口。
P2.41：设计本地访问保护 / 鉴权。
P2.42：设计 Web 审批操作。
```

不建议下一步直接做：

```text
审批按钮。
写操作 API。
登录页。
公网部署。
复杂图表。
未经 P2.40a 实现和 guard 验证的自动轮询。
```
