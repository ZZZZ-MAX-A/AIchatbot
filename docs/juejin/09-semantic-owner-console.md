# 把 QQ 主人命令改造成语义工具：我给机器人做了一个只读控制台

标签建议：`AI Agent`、`NoneBot`、`LangGraph`、`工具调用`、`Agent 安全`

## 开头

上一篇写到，我给 QQ 机器人接入了 MainAgentGraph：它可以通过 `/agent` 进入一个受控的主 Agent 运行时，先只读，再任务表，再审批流。

但第一版还有一个明显问题：很多主人管理能力仍然是固定命令。

比如：

```text
/最近错误
/配置状态
/视觉状态
/记忆状态
/角色卡
/群白名单
```

这些命令很稳定，但使用体验并不像“Agent”。我更希望能这样说：

```text
/agent 帮我看一下最近错误
/agent 看看角色卡
/agent 当前主模型是什么
/agent 看看访问控制
/agent RAG 索引详情
```

也就是说，不是让大模型去“猜应该执行什么函数”，而是把原来的主人管理命令逐步改造成受控语义工具：语义触发、工具注册、权限检查、原文返回。

这篇文章记录的是我怎么给 QQ 机器人做第一版语义主人控制台。

## 固定命令不是问题，但它不是控制台

固定命令有一个很大的优点：确定。

用户输入：

```text
/最近错误
```

程序就执行固定 handler，返回最近错误日志。没有模型参与，没有误判，没有幻觉。

但随着管理能力越来越多，固定命令会变得分散：

```text
/状态
/诊断
/配置状态
/视觉状态
/图片缓存状态
/记忆状态
/RAG状态
/摘要状态
/角色卡
/群白名单
/私聊白名单
/黑名单
```

对我自己来说，命令还能记住；但如果后面继续加任务、审批、RAG、模型配置、角色卡列表、访问控制总览，就会越来越像一个命令行手册，而不是一个 QQ 里的主人控制台。

所以我的目标不是删除固定命令，而是加一层语义入口：

```text
固定命令继续保留，作为 fallback。
/agent 语义命令成为更自然的控制入口。
```

这样即使 MainAgent 语义层出问题，我仍然可以用原来的固定命令操作系统。

## 最关键的边界：普通聊天不能进控制台

这个项目里有两类聊天入口：

```text
普通聊天：
  用于自然回复、角色卡表达、记忆召回。

/agent：
  用于主人管理、任务、审批、项目上下文查询。
```

我没有把主人管理语义接到普通聊天里。原因很简单：普通聊天太容易出现模糊表达。

用户在普通聊天里说：

```text
最近好像有点问题。
```

这不应该触发“查看最近错误”。再比如角色卡里可能出现“主人”“命令”“权限”等文本，也不应该被误当成管理指令。

所以语义主人控制台的入口被限定为：

```text
/agent <自然语言管理请求>
```

并且默认只允许主人私聊。

## ToolRegistry：语义命令也必须先注册

我没有让 LLM 直接调用 Python 函数，而是给 MainAgentGraph 做了一个 ToolRegistry。

每个工具都有一个 `ToolSpec`：

```text
name
description
risk_level
required_arguments
optional_arguments
executor
enabled
llm_visible
requires_approval
approval_resume_enabled
```

只读主人管理工具被注册成：

```text
owner_read_command
```

它的风险等级是：

```text
read_local
```

它只允许调用白名单里的只读命令：

```text
bot_status
diagnostics
config_status
vision_status
recent_errors
image_cache_status
memory_status
rag_status
summary_status
view_summaries
view_gap_scene_summaries
view_long_term_memory
view_persona
role_card_list
tts_status
group_whitelist
private_whitelist
blacklist
access_overview
model_config_status
rag_index_detail
main_agent_observations
```

注意，这里没有“清空”“删除”“切换”“加入白名单”之类的动作。它只是控制台查询，不改变系统状态。

## 语义分类先于 LLM

我一开始遇到过一个真实问题：`/agent 看看任务卡` 没有去查任务表，而是被 MainAgent 当成项目上下文查询，走了 RAG，最后根据旧文档回答“未找到实际任务表内容”。

根因是：

```text
MAIN_AGENT_USE_LLM=true 时，配置的 LLM handler 先运行。
确定性语义分类器没有优先拦截。
```

修复方式是加一个 semantic-first planner：

```text
先跑本地确定性语义分类。
如果命中 owner_read_command / agent_task_read / owner_write_command，就直接生成 ActionRequest。
没有命中，再交给 LLM 或 dev_context fallback。
```

这样：

```text
/agent 帮我看一下最近错误
```

会被本地分类器稳定映射为：

```json
{
  "action": "tool_request",
  "tool_name": "owner_read_command",
  "arguments": {
    "command": "recent_errors"
  }
}
```

而不是让模型自由发挥。

这里我得到一个很重要的经验：

```text
确定性管理意图应该先于 LLM。
LLM 适合处理开放问题，不适合抢确定性控制命令。
```

## 角色卡问题：工具结果不能再交给模型总结

另一个很有意思的问题出现在角色卡查看上。

当我输入：

```text
/agent 看看角色卡
```

工具确实查到了当前角色卡内容。但如果把工具结果再交给 LLM 做“自然总结”，模型有概率模仿角色卡里的语气。

比如角色卡内容里写了：

```text
主人模式下称呼用户为……
语气害羞、结巴、忠诚……
```

模型总结时可能会直接进入这个语气。这在普通聊天里也许可以接受，但在管理控制台里是错误的。控制台应该像控制台，不应该被被查看对象污染表达。

所以我做了一个边界：

```text
dev_context：
  可以交给 LLM 做自然总结。

owner_read_command / agent_task_read / owner_write_command：
  工具结果直接返回，不交给 LLM 二次总结。
```

这样查看角色卡时，返回的是操作台式原文：

```text
当前角色卡内容：
...
```

而不是让模型“扮演”角色卡。

这也是我后来反复坚持的一个原则：

```text
管理输出不走角色表达。
控制台输出不被被查看内容影响。
```

## 第一批只读语义命令

第一批主要覆盖原有诊断和状态命令：

```text
/agent 帮我看一下最近错误
/agent 看看诊断
/agent 看看配置状态
/agent 视觉状态怎么样
/agent 图片缓存状态
/agent 记忆状态
/agent RAG状态
/agent 摘要状态
/agent 看看角色卡
/agent 看看群白名单
/agent 看看私聊白名单
/agent 看看黑名单
```

这些命令本质上都只是读本地状态。它们不会写数据库，不会清空缓存，不会修改配置，也不会发额外 QQ 消息。

实现上，`owner_read_command` 的 executor 并不重新实现业务逻辑，而是复用已有服务函数或 Graph：

```text
diagnostics
config_status
vision_status
recent_errors
image_cache_status
memory_status
tts_status
```

走诊断图。

```text
summary_status
view_summaries
view_gap_scene_summaries
view_long_term_memory
```

走记忆管理图的只读分支。

```text
group_whitelist
private_whitelist
blacklist
```

走访问控制读取函数。

这点很重要：我不是把 NoneBot handler 暴露给 Agent，而是把 handler 背后的稳定服务函数注册成工具。

## 第二批只读语义命令

第一批验证通过后，我又补了一批更像“主人控制台”的查询：

```text
role_card_list
model_config_status
access_overview
rag_index_detail
main_agent_observations
```

对应语义输入：

```text
/agent 看看有哪些角色卡
/agent 角色卡列表
/agent 看看模型配置
/agent 当前主模型是什么
/agent 看看访问控制
/agent 权限状态
/agent 看看项目文档索引
/agent 看看记忆索引
/agent RAG 索引详情
/agent MainAgent 最近失败
/agent 最近 agent 观测
```

这里每个查询都有明确边界。

角色卡列表只返回：

```text
角色卡 key
角色卡标题
当前启用项
```

不输出角色卡正文，也不切换角色卡。

模型配置摘要只返回：

```text
模型名
base_url
超时
Key 是否配置
```

不会泄露 API Key。

访问控制总览会汇总：

```text
主人是否配置
私聊是否开启
群聊是否开启
未知私聊策略
私聊白名单
群白名单
黑名单
```

但不修改名单。

RAG 索引详情会读 `rag_documents` 和 `rag_embeddings`，按 namespace / source_type 统计文档和 embedding 数量，但不重建索引。

MainAgent 最近观测会从错误日志里筛选 MainAgent / LLM / tool summary 相关记录，用来定位语义命令有没有误路由。

这些能力让 `/agent` 更像一个“只读运维面板”。

## 任务和审批也要只读语义查询

除了主人管理命令，我还把任务和审批表做成只读语义工具：

```text
agent_task_read
```

它只允许：

```text
list_tasks
task_detail
list_approvals
approval_detail
```

对应自然语言：

```text
/agent 看看任务表
/agent 查看任务列表
/agent 最新任务详情
/agent 有没有待审批的东西
/agent 最新审批详情
```

它不会创建任务，不会确认审批，不会拒绝审批，也不会恢复执行。

这样就解决了一个很实际的问题：当我想看“真实任务表”时，系统不会再去 RAG 里检索旧设计文档，而是直接查询 `agent_tasks` / `agent_task_events` / `agent_approvals`。

## 为什么固定命令还要保留

语义入口更自然，但我没有删除旧命令。

原因有三个。

第一，语义分类器仍然可能漏掉说法。

比如：

```text
/agent 权限看一下
```

如果分类器没覆盖，可能会 fallback 到 dev_context。旧命令仍然是确定可用的。

第二，MainAgent 未来可能会改。

如果某次重构让 `/agent` 路由出问题，固定命令仍然能救急。

第三，固定命令是测试基准。

当语义工具返回异常时，我可以用旧命令确认底层业务函数本身是否正常。

所以当前策略是：

```text
固定命令是底座。
语义命令是更好的入口。
```

## 测试重点

这批改动我重点测了几类情况。

第一，语义命令必须先于 LLM：

```text
/agent 帮我看一下最近错误
/agent 看看任务表
```

即使 `MAIN_AGENT_USE_LLM=true`，也不能先交给主模型。

第二，管理工具结果不能被 LLM 总结：

```text
/agent 看看角色卡
```

返回必须保持操作台式输出，不能模仿角色卡。

第三，危险词不能误入只读工具：

```text
/agent 帮我清空图片缓存
/agent 帮我选择角色卡
/agent 帮我加入群白名单
```

这些不能被 `owner_read_command` 当成只读命令。

第四，任务卡必须查真实表：

```text
/agent 看看任务卡
```

应该走 `agent_task_read`，而不是 RAG 文档召回。

## 当前效果

现在 `/agent` 已经可以承担一个只读主人控制台的角色：

```text
/agent 看看最近错误
/agent 角色卡列表
/agent 模型配置
/agent 访问控制
/agent RAG 索引详情
/agent 最近 agent 观测
/agent 看看任务表
/agent 最新审批详情
```

而普通聊天仍然只是聊天，不会突然触发控制台工具。

这让我对后续开放写工具更有底气。因为读工具已经走通了：

```text
语义识别
ToolRegistry
权限检查
工具执行
直接返回
测试覆盖
旧命令 fallback
```

后续只需要在这个框架上继续加风险等级和审批，而不是从零开始把工具塞给模型。

## 总结

这一步看起来不像“炫酷 Agent”，但它非常关键。

我的体会是：

```text
Agent 的第一批工具，不应该是 shell。
也不应该是写文件。
最好先是只读控制台。
```

只读控制台能帮你验证：

```text
语义路由是否稳定
工具注册是否清晰
权限边界是否有效
输出是否可控
旧命令是否能兜底
```

等这些都稳定后，再讨论写操作才比较安全。

这也是我现在给 QQ 主人控制台定下的原则：

```text
普通聊天不进控制台。
确定性管理意图先于 LLM。
管理结果不交给角色模型总结。
固定命令永远保留 fallback。
```

在这个基础上，MainAgent 才能从“会聊天的模型”慢慢变成“可审计、可控、能协作的运行时”。
