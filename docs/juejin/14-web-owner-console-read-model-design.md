# Web Owner Console 还没写前端，我先给它设计 read model

标签建议：`AI Agent`、`Agent 架构`、`DTO`、`NoneBot`、`工程化`

## 开头

上一篇里，我把 MainAgent owner 侧 runtime 从 QQ adapter 里拆了出来：

```text
owner_agent_runtime.py
  任务、审批、工作台、详情卡、审批恢复入口

owner_read_runtime.py
  主人只读管理命令分发

owner_write_runtime.py
  已审批主人写命令执行

owner_runtime_factory.py
  task/read/write runtime 总装层
```

这一步做完后，一个方向自然浮出来了：

```text
既然 /agent 已经越来越像主人控制台，
那是不是可以开始做 Web Owner Console？
```

但我这次没有直接写前端，也没有接 HTTP API。

我先做了一份更枯燥、但更关键的设计：

```text
Web Owner Console read-model 设计。
```

简单说，就是先决定未来 Web 控制台要读哪些数据、这些数据应该长什么样、从哪里来，以及哪些东西绝对不能因为有了 Web 入口就绕过安全边界。

这篇文章记录我为什么没有直接复用现在的 QQ 文本输出，也为什么要提前设计结构化 DTO。

## 当前系统已经有一个 QQ 版主人控制台

现在 `/agent` 已经不只是一个“问项目上下文”的命令了。

它可以做很多主人侧只读查询：

```text
/agent 看看最近错误
/agent 角色卡列表
/agent 模型配置
/agent 访问控制
/agent RAG 索引详情
/agent MainAgent 最近观测
/agent RootGraph 最近观测
```

也可以看任务和审批：

```text
/agent 任务工作台
/agent 下一步
/agent 任务详情 最新
/agent 审批状态
/agent 审批详情 最新
```

写操作也已经有审批门控：

```text
/agent 删除摘要 41
/agent 清空图片缓存
/agent 把群 123456 加入群白名单
/agent 确认 最新
```

这些能力组合起来，已经很像一个“QQ 里的 Owner Console”。

但它的输出形态是 QQ 消息。

也就是说，现在后端大体是这样：

```text
结构化数据 / 服务结果
  -> QQ 文本 formatter
  -> str
  -> matcher.finish(reply)
```

这对 QQ 很合适。

一条消息就应该是一段人能直接读的文本。

但如果未来要做 Web Owner Console，直接拿这段文本塞进网页，就会埋下很多坑。

## 现有 QQ 输出的三种后端形态

我这次先把现有 QQ 输出形态梳理了一遍。

它其实不是完全乱拼字符串，背后有三类来源。

第一类是 `list[str]`。

比如：

```text
role_card_list_lines()
model_config_status_lines()
access_overview_lines()
rag_index_detail_lines()
main_agent_observation_lines()
root_graph_observation_lines()
```

这些函数返回一组展示行，然后 `owner_read_runtime` 用换行拼成 QQ 文本。

第二类是 Graph execution 的 `reply_text`。

比如：

```text
run_diagnostics(...)
run_memory_retrieval(...)
run_memory_admin(...)
```

Graph 里已经聚合了状态，但最后给 `/agent` 的仍然是一段可发送的文本。

第三类是任务和审批 formatter。

任务和审批底层其实已经有结构化对象：

```text
AgentTask
AgentTaskEvent
AgentApproval
```

但 QQ 入口会立刻把它们送进 formatter：

```text
format_agent_task_list(tasks) -> str
format_agent_task_detail(task, events, approvals) -> str
format_agent_approval_list(approvals) -> str
format_agent_approval_detail(approval, task, events) -> str
format_agent_task_workbench(...) -> str
```

这些 formatter 产出的内容适合 QQ：

```text
Agent 审批详情卡 #19
审批ID：#19
状态：待确认
任务ID：#18
工具：owner_write_command
风险：medium
原因：owner write command requires approval
输入摘要：...
```

但它不是 Web 后端接口。

Web 如果想做表格、筛选、排序、状态标签、详情页、按钮禁用态，就不应该去解析这段文本。

## 为什么不能直接复用 QQ 文本

最省事的做法当然是：

```text
Web 页面请求一个接口。
后端调用现有 /agent 逻辑。
拿到 str。
前端原样展示。
```

这个方案第一天看起来很快，第三天就会开始难受。

### 1. 文案变化会变成接口破坏

比如 QQ 文本里有一行：

```text
审批ID：#19 [待确认] 任务ID：#18 owner_write_command / medium
```

如果 Web 前端靠解析这行拿 `approval_id`、`status`、`task_id`，那么以后我只要把文案改成：

```text
审批 #19：待主人确认，关联任务 #18
```

前端解析就坏了。

文案应该是展示层，不应该成为数据契约。

### 2. Web 页面天然需要结构

任务列表不是一段文本，它至少需要：

```text
task_id
title
goal_preview
status
status_label
created_at
updated_at
latest_event_summary
pending_approval_ids
```

审批列表也不是一段文本，它需要：

```text
approval_id
task_id
task_title
tool_name
risk_level
reason_preview
status
created_at
expires_at
decided_at
```

这些字段到了前端以后，才能自然变成：

```text
表格列
筛选条件
状态 badge
详情链接
风险颜色
空状态
禁用按钮原因
```

如果后端只给一段文本，前端要么只能做一个大文本框，要么就开始写脆弱的正则解析。

### 3. 安全脱敏需要字段级控制

审批详情里有 `tool_input_json`。

它可能包含：

```text
工具参数
记忆内容
摘要 ID
名单目标
模型配置相关信息
```

在 QQ 里，我可以用短文本摘要展示：

```text
输入摘要：{"command": "delete_session_summary", "summary_id": 41}
```

但 Web 以后可能会有折叠详情、复制按钮、JSON 预览。

这时如果后端只给一段 formatter 文本，脱敏边界就很难说清楚。

更稳的形式是 read model 里明确写：

```text
tool_input:
  preview_json: str
  redacted: bool
  truncated: bool
```

这样前端知道自己看到的是预览，不是完整原文。

### 4. 未来按钮状态不能靠前端猜

Web Console 以后可能会展示审批确认按钮。

但按钮能不能点，不能靠前端根据文案猜：

```text
如果文本里有“待确认”，按钮就可点。
```

这是危险的。

正确做法应该是后端 read model 给出只读的 actionability metadata：

```text
can_approve
can_reject
resume_enabled
blocked_reason
future_operation_only
```

v0 阶段这些字段只用于描述未来 UI 状态，不执行操作。

真正实现时，它们也必须由后端根据审批状态、tool registry 和 `approval_resume_enabled` 计算。

前端不应该自己判断某个工具能不能恢复。

## DTO 在这里到底是什么意思

我这里说的 DTO，不是说马上要写一堆复杂的类。

它更像是一个明确的数据契约：

```text
这个页面需要什么字段。
这些字段来自哪里。
哪些字段是展示摘要。
哪些字段是脱敏预览。
哪些字段只是未来操作提示。
哪些能力当前明确不可用。
```

比如任务列表可以设计成：

```text
OwnerConsoleTaskList
  generated_at
  filters
  total_visible
  rows
  boundary

OwnerConsoleTaskRow
  task_id
  title
  goal_preview
  status
  status_label
  result_preview
  created_at
  updated_at
  latest_event_kind
  latest_event_summary
  pending_approval_ids
  next_action
```

审批详情可以设计成：

```text
OwnerConsoleApprovalDetail
  generated_at
  approval
  tool_input
  task
  recent_events
  actionability
  boundary
```

这类结构化 DTO 有几个好处。

第一，前端不关心 QQ 文案。

第二，后端可以继续复用已有查询函数。

第三，安全边界可以被字段显式表达。

第四，后续 HTTP API、CLI、甚至新的 Owner Console 入口都可以共享同一个 read model。

## read model 不是数据库表

这里还有一个容易混淆的点：

```text
read model 不等于新表。
```

这次 P2.6 明确不改数据库 schema。

任务和审批已经有持久化数据：

```text
AgentTask
AgentTaskEvent
AgentApproval
```

read model 做的是组装：

```text
从 agent_tasks 查询任务和审批。
从 DiagnosticsGraph 拿诊断摘要。
从访问控制对象拿黑白名单。
从配置和角色卡读取设置摘要。
从 owner runtime service 复用现有只读依赖。
```

也就是说，read model 是给界面看的“读模型”，不是新的存储模型。

这能避免为了做一个页面就急着加表。

对于一个还在演进中的 Agent 项目，这很重要。

## 页面范围为什么要分层

这次设计里，我把 Web Owner Console v0 页面分成两层。

第一层是 v0 必须清楚：

```text
Dashboard
Tasks
Task Detail
Approvals
Approval Detail
Diagnostics
Access Control
```

这些页面最能验证前面 Runtime service 解耦的价值。

因为它们主要依赖：

```text
任务/审批持久化查询
owner_agent_runtime
owner_read_runtime
diagnostics 只读能力
access control 只读能力
```

第二层是 v0 浅层快照：

```text
Memory
Settings
```

Memory 很重要，但它牵涉：

```text
MemoryRAG
MemoryAdmin
摘要
长期记忆
隐私正文
ProjectDocRAG 隔离
```

Settings 也很重要，但它牵涉：

```text
模型配置
base_url 脱敏
API Key 是否配置
角色卡列表
功能开关
Vision / TTS / MemoryRAG 配置
```

如果一上来把这两个页面做深，P2.6 会失控。

所以 v0 只设计浅层快照，不做修改能力。

## 为什么现在不写前端

直接写前端当然更有成就感。

但对这个项目来说，现在先写前端反而可能把错误的后端形态固定下来。

如果我今天先做一个页面，为了快，很可能会这样接：

```text
Web -> 调用现有 QQ 文本输出 -> 前端展示文本
```

然后明天想加表格，就开始解析文本。

后天想加按钮，就开始根据文本判断状态。

再后天想加脱敏，就发现原始数据和展示文案已经混在一起了。

所以我宁愿先慢一步：

```text
先定义 read model。
先确认页面范围。
先写清只读边界。
先写清未来审批操作不能绕过现有链路。
```

这样后续真正写 Web 时，前端接的是稳定数据结构，而不是一段“刚好能看”的 QQ 文案。

## 最关键的安全边界：Web 不能绕过审批链路

Web Owner Console 最容易犯的错误，是把“有按钮”误解成“可以直接调用函数”。

比如未来审批详情页里有一个确认按钮。

危险做法是：

```text
Web button -> clear_image_cache()
Web button -> add_access_item()
Web button -> delete_session_summary()
```

这相当于 Web 入口绕过了现有审批恢复机制。

正确路线应该是：

```text
Web approval decision
  -> 与 /agent 确认/拒绝 相同的审批决策服务
  -> decide_agent_approval(...)
  -> resume_agent_approval(...)
  -> approval resume tool registry
  -> approval_resume_enabled=true 检查
  -> owner_write_runtime
  -> agent task event 幂等记录
```

也就是说，Web 未来可以成为审批入口，但不能成为绕过审批的写入口。

P2.6 v0 更保守：

```text
只读。
不确认审批。
不拒绝审批。
不恢复工具。
不调用 owner_write_runtime。
```

但我仍然在设计文档里写了未来升级路线。

因为安全边界最好在设计阶段就写清楚，而不是等前端按钮出现后再补。

## 未来模块为什么先只给建议名

设计文档里提了两个未来建议名：

```text
owner_console_read_runtime.py
owner_console_read_models.py
```

但这次没有创建代码文件。

原因是 P2.6 还只是设计阶段。

现在真正要确定的是边界：

```text
Web read model 层不依赖 MessageEvent。
Web read model 层不调用 matcher.finish / bot.send。
Web read model 层不执行写操作。
Web read model 层不解析 QQ 文本。
```

至于最后是一个文件还是两个文件，后续实现时可以再根据代码量决定。

我更在意的是这层不要消失。

如果没有这层，Web 很容易直接接到 QQ adapter 或 formatter 上。

那前面做 Runtime service 解耦的价值就被浪费了。

## 当前 P2.6 的结果

这次 P2.6 最终落地的是一份设计文档：

```text
docs/web-owner-console-read-model-design.md
```

它主要写了这些内容：

```text
Web Owner Console v0 定位
现有 QQ 文本输出后端形态
页面地图
每个页面需要的数据
read model 结构草案
现有 Runtime service 如何复用
暂不做的能力边界
从只读到审批操作的升级路线
```

这次仍然不做：

```text
不写前端。
不接 HTTP。
不做登录。
不新增数据库表。
不改变 /agent。
不改变普通聊天。
不改变审批恢复。
不改变 MemoryRAG。
不改变 Diagnostics。
不改变 QQ 命令行为。
```

从功能角度看，它“什么也没新增”。

从架构角度看，它把下一步怎么接 Web Owner Console 说清楚了。

## 一点工程感受

做 Agent 项目时，很容易被“下一步做个界面”吸引。

界面很直观，也很有反馈。

但如果后端还没有数据契约，界面会反过来逼你做很多脆弱连接：

```text
解析文本。
猜状态。
复制业务判断。
绕过安全链路。
展示未脱敏内容。
```

这次我想避免这个方向。

对这个项目来说，Web Owner Console 的第一步不是按钮，也不是页面，而是 read model。

我希望未来每个入口都很清楚：

```text
QQ adapter 负责 QQ。
Web adapter 负责 Web。
owner runtime 负责主人侧业务运行时。
read model 负责结构化只读数据。
write runtime 必须在审批恢复链路之后才执行。
```

这样系统能力可以继续长，但边界不会跟着糊掉。

## 下一步

如果 P2.6 设计确认稳定，后续可以小步实现：

```text
第一步：新增 owner_console_read_runtime.py，只做只读 builder。
第二步：优先实现 Tasks / Approvals / Dashboard。
第三步：Diagnostics、Memory、Settings 先保留 summary_text / display_lines 过渡。
第四步：等 read model 稳定后，再考虑 HTTP API。
第五步：最后才是 Web 前端。
```

这个顺序看起来慢，但它更适合一个长期运行的 Agent 系统。

因为我想要的不是“能打开一个网页”，而是：

```text
每个页面背后都有清楚的数据契约。
每个写操作背后都有审批链路。
每个入口都知道自己不能做什么。
```

这也是为什么我选择先做结构化 DTO，而不是直接把 QQ 文本搬到 Web 上。
