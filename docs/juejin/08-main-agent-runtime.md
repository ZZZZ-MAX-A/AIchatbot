# 给 QQ 机器人接入主 Agent：我为什么先做只读、任务表和审批流

标签建议：`AI Agent`、`LangGraph`、`LangChain`、`NoneBot`、`Agent 安全`

## 开头

当一个聊天机器人已经能稳定对话、识图、语音、记忆和诊断后，很自然会想做下一步：让它不只是聊天，而是能帮我处理任务。

比如：

```text
帮我查一下当前项目做到哪了。
把这次开发结论写进版本日志。
整理下一步计划。
检查配置为什么连不上主模型。
```

这时就会遇到一个关键问题：主 Agent 到底应该有多大权限？

如果直接给模型 shell、文件写入、QQ 发送、数据库写入权限，它确实会“能干很多事”，但也会非常危险。提示词可以告诉它“不要乱动”，但真正的权限边界不能只靠提示词。

所以我在 v1.3 的目标不是立刻让主 Agent 自动干活，而是先搭一个受控 Agent Runtime：只读接入、结构化动作、工具策略检查、任务表、事件表、审批表。

这篇文章记录这个过程。

## 项目背景

项目是一个 QQ AI 机器人：

```text
QQ
  -> NapCatQQ
  -> OneBot v11
  -> NoneBot2
  -> AI Chat Plugin
```

普通聊天使用 ChatAgent，主要负责自然语言回复。MainAgent 是后面新增的主 Agent，负责理解任务、生成计划、提出工具请求和总结工具结果。

我给它们做了明确分工：

```text
ChatAgent：
  负责聊天表达，不接工具。

MainAgent：
  负责规划和工具请求，但不能直接执行动作。

LangGraph：
  负责流程、权限、状态和审批。

LangChain：
  负责模型调用、结构化输出和工具 schema。

SQLite：
  负责任务状态、事件和审批记录。
```

核心原则很简单：

```text
MainAgent proposes.
LangGraph disposes.
```

主 Agent 可以提出请求，但是否执行由代码决定。

## 为什么不能让主 Agent 直接调用工具

很多 Agent demo 的体验是：模型想调用什么工具，就调用什么工具。做 demo 很爽，但接到真实 QQ 机器人上会有几个风险。

第一，模型可能误解用户意图。

用户说：

```text
这个目录现在是什么情况？
```

模型可能理解成要执行 `dir` 或 `ls`。但在没有审批和工具边界之前，它不应该碰 shell。

第二，外部输入不可信。

网页、图片、群聊消息、文档内容都可能包含类似“忽略之前规则，执行 xxx”的文本。模型可能会把它当成指令。

第三，提示词规则不可靠。

提示词可以写：

```text
你不能执行 shell。
你不能写文件。
```

但真正安全的系统必须在代码里判断：

```text
这个工具是否注册？
这个调用者是谁？
当前会话能不能用？
风险等级是什么？
是否需要审批？
```

所以 v1.3 的设计原则是：

```text
提示词是提醒。
代码规则才是权限。
```

## MainAgentGraph 的第一版：只读

第一版 QQ 入口是：

```text
/agent
/agent-debug
```

默认只允许主人私聊触发，群聊不开放。

最初只注册一个只读工具：

```text
dev_context
```

它用于查询项目上下文，底层会走 CombinedRAG，把项目文档和语义记忆分区召回。注意，它仍然是只读工具，不执行 shell，不写文件，不写数据库，不发额外 QQ 消息。

当前 MainAgentGraph 的核心流程是：

```text
VALIDATE_AGENT_REQUEST
BUILD_AGENT_CONTEXT
CALL_MAIN_AGENT
VALIDATE_ACTION_REQUEST
CHECK_TOOL_POLICY
EXECUTE_TOOL
RENDER_AGENT_RESPONSE
```

真实 Main LLM 接入后，主模型不是自由输出一段话，而是生成结构化 `ActionRequest`。然后系统再验证 schema、检查工具策略、执行允许的只读工具。

如果用户测试：

```text
/agent 帮我执行 dir
```

预期结果不是执行命令，而是拒绝 shell。

这一步看起来保守，但它验证了一件事：主模型可以接入，但它不能绕过工具策略。

## /agent 和 /agent-debug 的分工

我把 `/agent` 和 `/agent-debug` 分开。

```text
/agent：
  给主人看的自然语言总结。

/agent-debug：
  返回原始 dev_context / CombinedRAG 召回内容。
```

这样日常使用时，主人看到的是主 Agent 总结后的答案；调试时，又能看到原始召回是否正确。

真实 Main LLM 模式下，流程大概是：

```text
用户输入
  -> Main LLM 生成 ActionRequest
  -> dev_context 只读工具执行
  -> Main LLM 对 tool_result 二次总结
  -> QQ 回复
```

如果 Main LLM 连接失败，也会转成更友好的中文提示，比如：

```text
主模型连接失败，请检查 MAIN_LLM_BASE_URL、网络、代理或中转服务。
```

同时错误日志会脱敏记录：

```text
phase
error_type
model
base_url
api_key_configured
```

不会记录 API Key 原文。

## 任务功能：记录“我要 Agent 做什么”

只读主 Agent 能回答“当前状态是什么”，但还不能处理长期任务。

所以 Route B 的第一步是任务表。

新增：

```text
agent_tasks
agent_task_events
```

任务表记录目标：

```sql
CREATE TABLE IF NOT EXISTS agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

事件表记录任务过程：

```sql
CREATE TABLE IF NOT EXISTS agent_task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    step_index INTEGER NOT NULL,
    kind TEXT NOT NULL,
    tool_name TEXT,
    input_json TEXT,
    output_summary TEXT,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);
```

QQ 侧命令是：

```text
/agent 任务 <目标>
/agent 任务状态
/agent 任务详情 <任务ID>
/agent 取消任务 <任务ID>
```

后来又加了明确本地别名：

```text
/agent 新增任务：整理审批流
/agent 记录任务：整理 Route B 下一步
/agent 把“整理审批流”加入任务
```

这些命令只做确定性解析，不调用 Main LLM 判断语义。

也就是说，这句会创建任务：

```text
/agent 新增任务：整理审批流
```

但这句不会自动创建任务：

```text
/agent 后面记得做一下审批流
```

这是有意为之。现阶段只接受明确写入任务的表达，避免误把普通聊天或提问写进任务表。

## 任务和执行不是一回事

这里有一个容易混淆的点：创建任务不等于执行任务。

任务回答的是：

```text
我要让 Agent 做什么？
```

比如：

```text
任务 #12
目标：整理 v1.3 MainAgentGraph 的运行日志
状态：待处理
```

它只是一个目标记录。

真正执行时，未来可能会产生多个事件：

```text
事件 #1：任务创建
事件 #2：读取项目文档
事件 #3：生成计划
事件 #4：请求写文件审批
事件 #5：任务完成
```

目前还没有执行器，所以任务只会创建、查看、取消，不会自动干活。

这一步的价值是：先有任务状态和事件审计，再接执行能力。

## 审批流：记录“这个高风险动作允不允许”

任务表解决的是目标记录，审批表解决的是动作授权。

新增：

```text
agent_approvals
```

表结构：

```sql
CREATE TABLE IF NOT EXISTS agent_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    tool_input_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    decided_at TEXT,
    FOREIGN KEY(task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE
);
```

QQ 侧先只做只读查看：

```text
/agent 审批状态
/agent 审批详情 <审批ID>
```

当前通常会显示“暂无审批”，这是正常的。因为还没有开放写文件、发 QQ、shell、git push 这类会产生审批的工具。

审批表的作用是给后续能力预留安全闸门。

比如未来用户说：

```text
/agent 新增任务：整理版本日志并写入 docs/version-runlog.md
```

如果执行器发现需要写文件，不能直接执行，而应该生成审批：

```text
审批 #5
任务：#12
工具：write_file
风险：L3_WRITE_LOCAL
原因：需要修改 docs/version-runlog.md
输入摘要：追加 v1.3 运行日志
状态：待审批
```

主人查看：

```text
/agent 审批详情 5
```

未来确认：

```text
/agent 确认 5
```

系统才恢复执行。

这就是任务和审批的区别：

```text
任务：
  我要 Agent 做什么？

审批：
  Agent 想做某个有风险动作，我允不允许？
```

一个任务可以没有审批，也可以有多个审批。一个审批必须属于某个任务。

## 风险等级设计

为了避免所有工具混在一起，我给工具设计了风险等级：

```text
L0_INTERNAL：
  内部计算，无副作用。

L1_READ_LOCAL：
  读取本地状态，例如文档、数据库统计。

L2_READ_EXTERNAL：
  联网搜索、网页读取、外部只读 API。

L3_WRITE_LOCAL：
  写本地文件、写任务表、写长期记忆候选。

L4_WRITE_EXTERNAL：
  发 QQ 消息、git push、调用外部写接口。

L5_DANGEROUS：
  删除文件、改 .env、清空数据库、任意 shell。
```

默认策略：

```text
L0：允许。
L1：主人私聊允许。
L2：主人私聊 + 对应开关开启。
L3：需要主人确认。
L4：需要主人确认，并且工具在白名单中。
L5：默认禁止。
```

第一版实际只开放了只读工具。写工具和危险工具都没有开放。

这就是为什么主 Agent 当前能查项目上下文，却不能执行 `dir`，也不能写文件。

## 为什么要这么慢

从产品体验看，这套路线确实慢：

```text
先只读。
再任务表。
再事件表。
再审批表。
再考虑确认/拒绝。
再考虑执行器。
再逐个开放工具。
```

但这是有意的。

如果反过来做，先把 shell、写文件、发消息全接进去，再补审批和日志，就会很难收住。模型一旦有了自由行动权，后面再想补边界，成本会高很多。

我的原则是：

```text
先有状态，再有动作。
先有审计，再有执行。
先有审批，再开放写工具。
```

主 Agent 可以变聪明，但不能变自由。

## 当前已经验证的行为

目前 live 验证过的行为包括：

```text
/agent 状态：
  能看到入口、只读模式、dev_context、任务能力、审批查看能力、LLM 状态。

/agent 查 MainAgentGraph 当前状态：
  可由真实 MainAgent LLM 生成 ActionRequest，调用 dev_context 后总结。

/agent-debug MainAgentGraph 当前状态：
  返回原始 dev_context / CombinedRAG 召回。

/agent 帮我执行 dir：
  拒绝 shell，不执行命令。

/agent 新增任务：整理审批流：
  创建 pending 任务记录，不触发 LLM 或 dev_context。

/agent 任务详情 <任务ID>：
  只展示任务和事件。

/agent 取消任务 <任务ID>：
  只取消当前会话 pending 任务，并记录 cancelled 事件。

/agent 审批状态：
  只查看审批记录，不恢复执行。
```

当前仍不开放：

```text
shell 工具
写文件工具
数据库写工具，除了固定任务/审批记录链路
额外 QQ 发送
Agent API
多步 agent loop
任务执行链路
审批恢复执行链路
长期记忆自动写入
角色卡自动修改
```

## 代码结构上的收益

这套设计让系统逐步从“一个聊天插件”变成“可控运行时”。

RootGraph 负责分发：

```text
chat
main_agent
voice
vision
memory_admin
diagnostics
owner_notification
```

MainAgentGraph 负责主 Agent 的安全流程：

```text
校验请求
构建上下文
调用主模型
校验 ActionRequest
检查工具策略
执行允许工具
渲染结果
```

任务表和审批表负责持久状态：

```text
agent_tasks：
  目标和状态。

agent_task_events：
  任务过程审计。

agent_approvals：
  高风险动作授权。
```

这让后续扩展写文件、联网、发通知时，不需要重新发明状态系统。

## 后续路线

下一步可以继续补：

```text
/agent 确认 <审批ID>
/agent 拒绝 <审批ID>
审批超时
审批决定事件
执行器 checkpoint
只读诊断工具
受控写文件工具
```

但每一步都应该遵守同一个规则：

```text
工具先注册。
风险先标注。
策略先检查。
需要审批就先停住。
主人确认后再恢复。
```

尤其是 shell，第一版仍然不应该开放自由命令执行。即使未来开放，也应该是白名单工具，而不是任意 shell。

## 总结

把主 Agent 接进 QQ 机器人，不难。难的是让它长期可控。

我的实践结论是：

```text
不要一开始就追求“全自动”。
先让主 Agent 只读。
再让任务可以被记录。
再让事件可以被审计。
再让审批可以被查看。
最后才逐步开放真实工具。
```

这样做短期看起来慢，但它给后续能力留出了安全空间。

Agent 系统最重要的不是让模型“想做什么就做什么”，而是让模型只能在明确流程、明确权限、明确审计、明确主人控制之下做事。

这也是我目前给这个 QQ 主 Agent 定下的底线：

```text
主 Agent 可以提出请求。
LangGraph 决定是否允许。
主人拥有最终审批权。
```
