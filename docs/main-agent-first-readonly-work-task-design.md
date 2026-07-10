# MainAgent first read-only work task design

本文记录 P2.43 MainAgent 首个正式工作任务模型设计。

设计日期：2026-07-11。

P2.43 先完成设计。P2.43a 已实现任务状态与持久化边界：`running`、原子 claim、work 事件和受限结果保存；尚未实现执行器、work registry、factory 注入或新的 QQ 命令，不引入后台 worker，也不开放新的写能力。

## 1. 设计结论

第一个正式任务类型固定为：

```text
work_type=development_context_report
中文名称=研发上下文报告
风险等级=read_local
执行来源=已注册的 DevContextGraph / dev_context 依赖
触发入口=主人私聊显式 /agent 命令
执行方式=当前命令内单次、同步、受控执行
审批=不需要
```

推荐明确命令形态：

```text
/agent 执行研发上下文任务：<问题>
```

示例：

```text
/agent 执行研发上下文任务：恢复 Owner Console 当前开发状态和下一步计划
/agent 执行研发上下文任务：总结 MainAgent 审批恢复边界和现有测试覆盖
```

旧的 `/agent 任务 <目标>` 继续只创建待办记录，绝不因为自然语言目标相似就自动转为执行任务。

它不让 MainAgent 自由选工具，不运行 shell，不执行文件或数据库业务写入，不发送额外 QQ 消息，也不在 Web 页面中启动。

## 2. 为什么选研发上下文报告

它复用的能力已经存在，并且边界已被长期测试：

```text
DevContextGraph
CombinedRAG
ProjectDocRAG
MemoryRAG 的开发侧分区召回
ToolRegistry 中的 dev_context read_local 语义
```

它适合首个工作任务，因为：

```text
输入是一个受限查询。
输出是只读研发报告。
没有外部副作用。
不新增后端 HTTP API。
不新增 QQ 发送动作。
不需要审批或审批恢复。
能验证任务创建、开始、完成、失败、结果保存和事件时间线。
```

它不等于“让 MainAgent 自动开发”。第一刀只让系统对一个已注册、单步、只读的工作类型形成正式执行记录。

## 3. 当前基线和缺口

当前已有：

```text
agent_tasks：title、goal、status、result、创建和更新时间。
agent_task_events：步骤、事件类型、工具名、输入摘要、输出摘要、状态、错误。
agent_approvals：审批请求、决定、审批恢复审计。
OwnerAgentContext(session_key, user_id)：主人任务边界。
OwnerRuntimeFactory：task/read/write service 总装。
Owner Console：任务、事件、审批的只读 read model 和 Web 页面。
```

当前任务状态只有 `pending`、`done`、`failed`、`cancelled`。`pending` 同时表达刚创建的待办、等待审批和没有正式执行器，不能准确表示工作已经开始。

P2.43 要补的不是更多工具，而是：

```text
task work type 注册表。
pending -> running 的原子领取。
work_started / work_finished / work_failed 事件。
受限任务结果持久化规范。
一个通过 factory 注入依赖的 work runtime。
```

P2.43a 已落地其中的持久化边界：

```text
新增 AGENT_TASK_RUNNING，并纳入既有任务状态筛选和只读状态展示。
claim_agent_task_for_work 只允许 scoped pending task 原子变为 running；已有 pending approval 的任务不能被 claim。
同一事务内记录 work_claimed 和 work_started，重复 claim 不会再次执行或追加事件。
complete_agent_task_work / fail_agent_task_work 只接受 running task，并分别记录 work_finished / work_failed。
query_summary 限制 480 characters；task.result 限制 1600 characters；event output/error summary 限制 240 characters。
cancel_agent_task 同样使用 status=pending 的条件更新，避免与 claim 竞争时覆盖 running 状态。
```

P2.43b 才会提供 work registry、executor 和 factory 注入；P2.43a 的 helper 不自行注册或执行任何 work type。

## 4. 入口和总流程

首个工作任务的流程应是确定性的，不由 LLM 自由编排：

```text
主人私聊显式 /agent 执行研发上下文任务：<query>
  -> QQ adapter 完成 owner 和私聊入口校验
  -> OwnerRuntimeFactory 绑定 OwnerAgentContext
  -> OwnerAgentWorkRuntime 验证 work_type 和 query
  -> 创建 agent_task(status=pending)
  -> 原子领取任务：pending -> running
  -> 写入 work_claimed / work_started
  -> 调用注入的 development_context_report executor
  -> 成功：写入受限 result、work_finished、task done
  -> 失败：写入受限错误摘要、work_failed、task failed
  -> QQ 只回复本次任务的简短状态和结果入口
```

这个流程不走普通聊天、ChatAgent、MainAgent LLM 的自由工具选择、任意 ToolRegistry 工具名、Web HTTP 写接口、后台队列、定时器或自动重试。

`DevContextGraph` 的执行依赖必须通过 factory 注入。新的 work runtime 不能反向 import QQ adapter 或 `src/plugins/ai_chat/__init__.py`。

## 5. 状态机、领取和重复保护

P2.43a 已新增任务状态 `running`。

首个只读工作任务只允许以下迁移：

```text
pending -> running -> done
pending -> running -> failed
pending -> cancelled
```

规则：

```text
只有 work runtime 的原子 claim 可以将 pending 改为 running。
running 不能被普通 /agent 取消任务直接取消。
第一个同步单步任务不提供中断执行能力。
done、failed、cancelled 都是终态，不允许再次执行同一 task_id。
失败后由主人显式创建新任务，不自动 retry。
```

执行前必须原子领取：

```text
UPDATE agent_tasks
SET status=running, updated_at=<now>
WHERE id=<task_id> AND status=pending
```

只有更新行数为 1 的调用者可以继续执行。领取成功后，在同一个持久化边界中写入 `work_claimed` 和 `work_started`。

这用于防护 QQ 重复投递、重复 handler 调用、未来多个入口同时请求同一任务，以及失败后错误地对同一 task_id 自动重试。

同一查询被主人再次显式发送时，会创建新的 task_id；这是新的工作请求，不是同一任务的自动重试。

已有审批任务保持兼容：

```text
已有 pending 审批任务不回填为 running。
已有 approval resume 行为不在 P2.43 改动。
approval pending 仍由 agent_approvals.status 表示。
P2.43 不新增 waiting_approval task status。
```

将来真正有多步写任务时，再单独设计 `waiting_approval`、恢复后的 `running` 和可取消边界，不能在本步顺手重构审批状态机。

## 6. Work type 注册边界

后续实现建议新增内部 work registry：

```text
AgentWorkSpec
  name
  display_name
  risk_level
  required_arguments
  executor
  enabled
  requires_approval
  result_limit
```

P2.43 只注册：

```text
name=development_context_report
display_name=研发上下文报告
risk_level=read_local
required_arguments=query
enabled=true
requires_approval=false
result_limit=1600 characters
```

注册表不接受任意 Python callable、任意 ToolRegistry 名称、任意 shell 命令、任意文件路径、任意 SQL、用户指定的 risk_level，或用户指定的 session_key / user_id。

Work runtime 必须从 `OwnerAgentContext` 取得 session_key 和 user_id，不能从 QQ 文本或 Web query 参数接受这些字段。

## 7. 输入、输出与隐私

输入规范：

```text
query 必须非空。
query 建议限制在 480 characters。
只允许主人私聊显式入口。
query 作为 task.goal 保存前应进行长度限制和控制字符清理。
不接受额外 parameters。
```

结果规范：

```text
task.result 只保存最多 1600 characters 的任务结果摘要。
event.output_summary 只保存最多 240 characters 的阶段摘要。
event.input_json 只保存 work_type 和经过限制的 query 摘要。
失败只保存错误类别和受限安全摘要。
不保存 Python traceback。
不保存完整 RAG 文档片段或完整 MemoryRAG 命中正文。
不保存 token、API key、.env、数据库路径或日志路径。
```

QQ 回复可以继续使用现有 `dev_context` 的简洁格式；任务记录不应复制无限长的 RAG 原始输出。Web Owner Console 继续只读，不新增执行、重试或取消 running 任务按钮。

## 8. 审批、失败与取消边界

`development_context_report` 是 `read_local`，不创建 `agent_approvals`。

P2.43 明确不做：

```text
把任意 pending task 自动交给审批恢复。
把 read-only work type 伪装为审批演练。
把任务结果写入长期记忆。
把任务结果发往额外 QQ 会话。
从任务执行器调用 owner_write_runtime。
把 approval_resume_enabled 扩展给新的 work type。
```

失败策略：

```text
输入无效：不创建 task，直接返回固定错误。
领取失败：不执行，读取现有 task 状态并返回受限说明。
DevContextGraph 执行失败：task 进入 failed，追加 work_failed。
失败后不自动 retry，不自动降级为普通聊天，不自动发送 QQ 通知。
```

取消策略：

```text
pending 可以继续使用现有取消命令取消。
running 在 P2.43a 中不可取消，因为执行是同步、单步、没有安全的中断协议。
终态任务不可取消。
```

P2.43 read-only task 没有 approval resume。重启期间未完成 running task 的恢复策略也不在 P2.43a 自动处理；将来如引入后台 worker，必须单独设计 lease、heartbeat、超时和崩溃恢复。

## 9. QQ、Web 与普通聊天隔离

| 入口或表面 | P2.43 行为 |
| --- | --- |
| 主人私聊 `/agent 执行研发上下文任务` | 允许创建并同步执行已注册只读工作 |
| 主人私聊普通聊天 | 不触发任务创建或执行 |
| 非主人私聊 | 拒绝，不创建任务 |
| 群聊 | 拒绝，不创建任务 |
| `/agent 任务 <目标>` | 继续只创建待办，不执行 |
| Web Owner Console | 只读展示，不创建、不执行、不重试 |
| approval confirm / reject | 继续只服务已存在的审批恢复链路 |

ProjectDocRAG 继续只允许通过显式 `/agent` 的开发上下文语义使用，绝不进入普通聊天上下文。

## 10. 预期事件时间线

正常成功：

```text
0 created
1 work_claimed
2 work_started
3 work_finished
```

执行失败：

```text
0 created
1 work_claimed
2 work_started
3 work_failed
```

领取前取消：

```text
0 created
1 cancelled
```

事件字段继续沿用现有 `agent_task_events`：

```text
kind
tool_name
input_json
output_summary
status
error
created_at
```

首个 work type 在 `tool_name` 中记录固定值 `development_context_report`，让 Owner Console 不新增 DTO 也能显示来源。

## 11. 推荐模块边界

后续实现建议新增：

```text
src/plugins/ai_chat/owner_agent_work_runtime.py
  OwnerAgentWorkContext / AgentWorkSpec / task claim / task execute / result persist。

src/plugins/ai_chat/owner_runtime_factory.py
  注入 development_context_report executor。

src/plugins/ai_chat/agent_tasks.py
  新增 running 常量、原子 claim、work event helper、受限 result 更新。
```

QQ adapter 只增加显式命令绑定和现有 factory 调用，不能把执行细节放回 `__init__.py`。

不建议新建独立进程、Redis、Celery、RabbitMQ、通用后台队列、Web runtime 直连或 ChatGraph work executor。

## 12. 测试与验收

P2.43 实现时至少新增：

```text
work type 只允许 development_context_report。
无效 query 不创建 task。
显式 owner context 能创建 pending 并原子 claim 为 running。
重复 claim 不重复执行。
成功路径写入 created / claimed / started / finished 和受限 result。
失败路径写入 failed 及安全错误摘要。
running task 不允许现有 cancel 命令取消。
pending task 仍可取消。
现有审批创建、确认、拒绝、恢复回归不变。
普通聊天、群聊、非主人私聊不触发 work runtime。
QQ adapter 仍只做绑定，不承载执行逻辑。
Owner Console API 继续只暴露 GET，Web 没有执行或重试按钮。
```

建议验证：

```powershell
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_persistence_units tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary -v

cd D:\AIchatbot\web\owner-console
npm run guard:readonly
npm test
npm run typecheck
npm run build
```

P2.43a 已新增持久化单测，覆盖 scoped claim、重复 claim、approval pending 兼容、running 不可取消、成功/失败终态和结果摘要上限。P2.43b/c 仍需要补 registry、executor 和 QQ 入口回归。

## 13. 实现拆分和后续路线

```text
P2.43：首个正式只读工作任务模型设计。已完成。

P2.43a：任务状态和持久化边界。已完成。
  已增加 running、原子 claim、work 事件、受限结果保存和取消竞态保护。

P2.43b：OwnerAgentWorkRuntime 和 factory 注入。
  只注册 development_context_report，不接 QQ 命令。

P2.43c：主人私聊显式 /agent 命令。
  同步执行、结果渲染、QQ live 回归。

P2.43d：Owner Console 只读展示回归和文档收口。
  不新增 Web 写操作。
```

P2.40b 应在 P2.43c 有真实 active task 生命周期后再重新评估。届时业务页面如需低频刷新，建议只在存在 running 任务时以 60-120 秒刷新；没有活动任务时停止轮询。

## 14. 保持的底线

P2.43 必须继续保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent 或 work runtime。
MainAgent 和 ChatAgent 继续分离。
ProjectDocRAG 只允许在显式 /agent dev_context 中使用。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复执行。
不开放多步写自动化。
不新增额外 QQ 发送副作用。
Web Owner Console 继续只读。
不新增 Web 写操作。
不新增登录/鉴权。
不开放 /docs、/redoc、/openapi.json。
不提交 web/owner-console/dist。
```
