# 让 Agent 能做事但不能乱做：QQ 机器人的审批流、任务表和门控写工具

标签建议：`AI Agent`、`Agent 安全`、`LangGraph`、`NoneBot`、`SQLite`

## 开头

只读控制台做完后，下一步很自然：能不能让 `/agent` 做一点真正有副作用的事情？

比如：

```text
/agent 帮我清空图片缓存
/agent 帮我清空错误日志
```

这两个动作都不算特别危险，但它们仍然会改变系统状态。如果直接让模型理解后立刻执行，就会回到 Agent 系统最常见的问题：

```text
模型觉得要执行。
程序就执行了。
出了问题再说。
```

我不想要这种模式。

所以这一阶段的目标不是“让 Agent 自动干活”，而是让它具备一条受控执行链路：

```text
语义命中
创建任务
创建审批
等待主人确认
确认后只恢复注册过的工具
写入事件表
重复确认不重复执行
```

这篇文章记录我怎么给 QQ MainAgent 做审批门控写工具，以及为什么任务/审批控制面也要语义化。

## 为什么写工具一定要审批

如果一个 Agent 能执行写操作，就至少会遇到三个问题。

第一，误触。

用户说：

```text
图片缓存现在是不是该清一下？
```

这可能只是询问，不一定是命令。

第二，误判。

模型可能把：

```text
帮我看一下错误日志。
```

理解成：

```text
清空错误日志。
```

第三，重复执行。

如果网络卡顿、QQ 重发、用户重复确认，写工具可能执行两次。

所以我把写操作的基本规则定成：

```text
语义命中不等于执行。
命中后只创建审批。
主人确认后才恢复。
恢复必须幂等。
```

这个规则比提示词重要。提示词可以提醒模型，但真正的执行权在代码里。

## 任务表、事件表、审批表

为了让审批可追踪，我做了三张表。

第一张是任务表：

```text
agent_tasks
```

记录任务的目标、状态、结果、创建时间和更新时间。

第二张是事件表：

```text
agent_task_events
```

记录任务过程中发生过什么：

```text
created
approval_requested
approval_approved
approval_rejected
tool_resume_started
tool_resume_finished
tool_resume_failed
```

第三张是审批表：

```text
agent_approvals
```

记录工具名、工具输入、风险等级、审批原因、审批状态和决定时间。

这样每一次有副作用动作都能留下审计链路：

```text
谁请求了什么
为什么需要审批
主人是否确认
确认后执行了哪个工具
工具结果是什么
有没有重复执行
```

## ToolSpec 增加 approval_resume_enabled

写工具不是“审批通过就都能执行”。我又加了一层开关：

```text
approval_resume_enabled
```

也就是说，一个工具要想在审批确认后恢复执行，必须同时满足：

```text
工具已注册
工具 enabled=true
工具 requires_approval=true
工具 approval_resume_enabled=true
审批状态是 approved
当前会话和用户匹配
没有执行过 tool_resume_finished
```

如果工具没有注册，不能恢复。

如果工具注册了但没有开启 `approval_resume_enabled`，也不能恢复。

这一步非常重要。因为未来 ToolRegistry 里可能出现很多工具，但不是所有工具都应该支持“确认后恢复”。

## 第一条恢复链路：dry_run_write_file

在接真实写工具之前，我先做了一个 dry-run 工具：

```text
dry_run_write_file
```

它的行为是：

```text
模拟写文件审批。
返回 path 和 content_summary。
不写文件。
不产生真实副作用。
```

它被注册为：

```text
risk_level=write_local
requires_approval=true
llm_visible=false
approval_resume_enabled=true
```

`llm_visible=false` 的意思是：它不暴露给主模型自由选择，只用于内部审批演练和测试。

对应 QQ 命令：

```text
/agent 审批演练 写入版本日志
/agent 确认 最新
/agent 任务详情 最新
```

确认后会写入：

```text
tool_resume_started
tool_resume_finished
```

并把任务标记为 done。

重复确认时会检查是否已有 `tool_resume_finished`，如果已经完成，就直接跳过，不再执行。

这条 dry-run 链路先验证了审批恢复的骨架。

## 第一批真实 owner_write_command

dry-run 跑通后，我才接第一批真实有副作用主人管理工具：

```text
owner_write_command
```

当前只开放两个命令：

```text
clear_image_cache
clear_error_log
```

语义触发：

```text
/agent 帮我清空图片缓存
/agent 帮我清空错误日志
```

它们的注册信息大致是：

```text
risk_level=write_local
requires_approval=true
approval_resume_enabled=true
llm_visible=true
```

但即使 `llm_visible=true`，也不是模型想执行就执行。它必须经过 ToolPolicyCheck。

对于 `write_local`，策略结果不是 allow，而是：

```text
require_approval
```

于是 MainAgentGraph 会停在审批中断，不执行工具。

QQ 返回类似：

```text
Agent 请求审批 #12
审批ID：#12
任务ID：#8
工具：owner_write_command
风险：write_local
输入摘要：{"command":"clear_image_cache"}

回复：
/agent 确认 12
/agent 拒绝 12
```

只有当主人确认后，才会恢复执行。

## 审批恢复不是重新跑 Agent

这里有一个关键设计：审批确认后，不是把原始自然语言再丢给 Agent 重新理解。

如果这么做，会有风险：

```text
第一次理解成 clear_image_cache。
第二次重新理解时可能变成别的动作。
```

所以审批表里保存的是结构化工具输入：

```json
{
  "command": "clear_image_cache"
}
```

确认后恢复时，系统直接读取审批记录里的 `tool_name` 和 `tool_input_json`，然后走注册表执行对应工具。

也就是说：

```text
审批恢复执行的是当时被冻结的工具请求。
不是重新问模型应该做什么。
```

这能避免确认阶段再次引入模型不确定性。

## 幂等：为什么确认两次不会执行两次

用户很可能重复发：

```text
/agent 确认 最新
```

或者第一次确认时网络没返回，以为没成功，又发一次。

所以恢复执行前会检查事件表：

```text
是否已经存在同一个 approval_id + tool_name 的 tool_resume_finished
```

如果存在，就返回：

```text
approval resume was already completed
```

不再调用 executor。

这是审批写工具必须有的保护。否则“清空缓存”也许还好，未来如果是更重要的写操作，重复执行就可能出问题。

## agent_task_command：任务和审批控制面也要语义化

在测试过程中，我发现任务和审批的固定命令虽然可用，但日常使用还是有点硬：

```text
/agent 审批详情 最新
/agent 确认 最新
/agent 任务详情 最新
```

我更想自然地说：

```text
/agent 帮我确认最新审批
/agent 拒绝最新审批
/agent 帮我创建一个任务：整理下一批工具
/agent 取消最新任务
```

于是我新增了一个工具：

```text
agent_task_command
```

它支持：

```text
create_task
cancel_task
approve_approval
reject_approval
create_approval_drill
```

但这个工具我故意设置为：

```text
risk_level=internal
llm_visible=false
```

也就是说，它不暴露给 LLM 工具契约，只能由本地确定性语义分类器命中。

原因很直接：确认审批、取消任务属于控制面动作，我不希望模型自由选择它。

它可以被这些语义触发：

```text
/agent 帮我创建一个任务：整理审批流
/agent 把整理 Route B 加入任务
/agent 取消最新任务
/agent 帮我确认最新审批
/agent 拒绝审批 #7
/agent 创建审批演练：写入版本日志
```

并且它的优先级在 `agent_task_read` 前面。

这解决了一个细节问题：如果用户说“确认最新审批”，里面同时包含“审批”和“最新”，如果只读分类先跑，可能会误判成“查看最新审批详情”。所以控制面命令必须先拦截。

## 为什么不开放 shell 和文件修改

做到这里，系统已经有了审批流。那能不能直接开放 shell？

我的答案是：暂时不。

原因不是做不到，而是不值得。

这个项目的开发侧已经有 Codex。我需要改文件、跑测试、提交代码时，直接让 Codex 做就行。QQ MainAgent 面向的是运行时管理，不应该过早承担开发机权限。

尤其是 shell：

```text
命令空间太大
副作用不可预测
输出容易诱导下一步动作
路径和环境复杂
```

如果未来真要开放，也应该是白名单工具：

```text
run_unit_tests
read_log_tail
restart_bot
```

而不是任意 shell。

同理，真实文件修改也暂时不放进 QQ MainAgent。写项目代码这件事，还是交给更适合的开发协作环境。

## 当前开放和不开放

当前开放：

```text
只读主人控制台：
  owner_read_command

任务/审批只读查询：
  agent_task_read

任务/审批控制面：
  agent_task_command

审批门控写工具：
  owner_write_command
```

当前不开放：

```text
shell
真实写文件
数据库任意写
白名单/黑名单修改
角色卡切换
删除记忆
清空全部上下文
索引重建自动执行
```

即使未来开放中风险写工具，也会继续走：

```text
ToolRegistry
ToolPolicyCheck
审批记录
确认恢复
事件审计
幂等保护
```

## 测试重点

这一阶段我重点测了几件事。

第一，语义写命令不会立刻执行：

```text
/agent 帮我清空图片缓存
```

预期是创建审批，而不是直接返回“已清空”。

第二，确认后才执行：

```text
/agent 确认 最新
```

预期是恢复 `owner_write_command`，返回：

```text
Approval resume completed
已清空图片缓存：N 条。
```

第三，重复确认不重复执行：

```text
/agent 确认 最新
/agent 确认 最新
```

第二次应该提示已经完成。

第四，拒绝后不执行：

```text
/agent 帮我清空错误日志
/agent 拒绝 最新
```

审批状态变成 rejected，不恢复工具。

第五，控制面语义不走 RAG：

```text
/agent 帮我确认最新审批
/agent 取消最新任务
```

必须命中 `agent_task_command`，不能去项目文档里检索旧设计。

## 这套结构的收益

做到这里，我开始觉得 QQ MainAgent 不再只是一个“能调用工具的模型”，而是一个小型受控运行时。

它有：

```text
工具注册表
风险等级
权限策略
审批中断
任务记录
事件审计
恢复执行
幂等保护
固定命令 fallback
```

这让后续扩展变得更清楚。

要加一个新工具，不是问：

```text
要不要让模型调用这个函数？
```

而是问：

```text
它是只读还是写？
风险等级是什么？
是否对 LLM 可见？
是否需要审批？
是否允许审批后恢复？
如何保证幂等？
旧命令是否保留？
测试怎么证明不会误触？
```

这些问题回答完，工具才应该进入系统。

## 总结

Agent 系统真正难的不是“能不能做事”，而是“能不能只在正确的时候做正确的事”。

我现在对 QQ MainAgent 的策略是：

```text
只读能力优先开放。
控制面命令确定性语义触发。
写操作必须审批。
确认后只恢复冻结的工具请求。
重复确认不重复执行。
shell 和真实文件修改暂时不开放。
```

这套设计牺牲了一点“全自动”的爽感，但换来的是长期可控。

对一个接在真实 QQ 号上的机器人来说，我觉得这是值得的。

因为我真正想要的不是一个“什么都敢做”的 Agent，而是一个：

```text
能理解我的意图，
能解释自己要做什么，
会在越权前停住，
等我确认后才行动，
并且每一步都有记录的协作系统。
```

这才是我愿意长期运行在 QQ 里的主 Agent。
