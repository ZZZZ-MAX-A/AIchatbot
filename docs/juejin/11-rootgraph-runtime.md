# 我给 QQ 机器人加了一层 RootGraph：让聊天、Agent 和审批都有统一入口

标签建议：`AI Agent`、`NoneBot`、`Agent 架构`、`LangGraph`、`可观测性`

## 开头

前两篇里，我把 QQ 机器人的主人管理命令分成了两类：

```text
只读命令：
  可以通过 /agent 语义触发，直接返回结果。

写命令：
  可以通过 /agent 语义命中，但必须先创建审批，主人确认后才执行。
```

这解决了一个很具体的问题：固定命令逐渐变成了语义控制台。

但做完这一步后，我发现系统里还有一个更底层的问题：入口越来越多。

现在机器人至少有这些路径：

```text
普通聊天
图片识别后的聊天
语义语音
/agent 主人管理
旧 QQ 固定管理命令
任务表和审批恢复
记忆检索、摘要压缩、长期记忆
诊断、状态、错误日志
```

每条路径都能工作，但它们的权限判断、路由判断、上下文构建和副作用提交散在不同位置。继续往上堆功能的话，迟早会遇到一个问题：

```text
这条 QQ 消息到底为什么被处理？
它进了聊天，还是进了 Agent？
它有没有触发工具？
它有没有落库？
它有没有发语音？
它被拦截时是权限问题、黑名单问题，还是限流问题？
```

所以这一阶段我没有继续增加更多主人命令，而是开始搭一层 `RootGraph`。

它不是一个更大的 Agent，而是 QQ Runtime 的统一调度层。

## RootGraph 不应该是万能 Agent

一开始很容易把 RootGraph 想成“顶层 Agent”：

```text
让它看懂所有消息。
让它决定调用哪个工具。
让它规划后续步骤。
让它负责所有能力。
```

但我没有这么做。

原因很简单：这里最需要的不是自由规划，而是确定性。

我的 QQ 机器人已经有几个边界非常明确的子系统：

```text
ChatGraph：
  负责普通聊天、角色卡表达、聊天记忆、图片上下文、TTS 候选。

MainAgentGraph：
  负责 /agent 显式入口、主人只读工具、审批门控写工具、项目上下文查询。

MemoryGraph：
  负责聊天历史、会话摘要、长期记忆、MemoryRAG。

DevContextGraph：
  负责开发侧项目文档 RAG，只能从 /agent 进入。
```

如果 RootGraph 再去做“大脑”，反而会把这些边界搅乱。

所以我给 RootGraph 定的职责更像交通枢纽：

```text
识别事件。
加载 actor 和 session。
做硬权限判断。
决定 intent。
构建运行上下文。
分发到子图。
记录副作用提交结果。
渲染最终响应或保持沉默。
```

换句话说：

```text
RootGraph routes.
Subgraphs work.
```

RootGraph 只回答“这一轮应该去哪”，不替 ChatGraph 聊天，不替 MainAgentGraph 做工具选择。

## 我想先解决的不是功能，而是解释能力

这次改造的核心目标之一，是让每一轮运行都能解释自己。

普通聊天里一个很烦的问题是：出问题时你只能看日志猜。

比如用户说机器人没回，你需要挨个检查：

```text
群聊开关开了吗？
群在白名单里吗？
用户在黑名单里吗？
消息长度超了吗？
限流了吗？
图片还在等上下文吗？
LLM 失败了吗？
回复已经发了但落库失败了吗？
语音生成失败了吗？
```

如果这些状态散在不同函数里，就很难快速判断。

于是 RootGraph 里我开始统一写 artifact。

当前一轮运行里，会逐步形成类似这样的运行记录：

```text
normalized_event
actor_context
policy
route
context
commit
root_graph
chat_access_policy
chat_commit
chat_runtime
```

这些 artifact 不追求一开始就做成完美的强类型协议，而是先用最小稳定字段把运行生命周期串起来。

比如 route artifact 可以回答：

```text
这条消息被识别成什么 intent？
最后选择了哪个 handler？
有没有真正 dispatch？
```

policy artifact 可以回答：

```text
是否允许分发？
为什么允许或拒绝？
拒绝后是否需要回复？
```

commit artifact 可以回答：

```text
文本回复有没有发送？
语音有没有发送？
聊天轮次有没有持久化？
试用次数有没有更新？
压缩有没有调度？
图片上下文是不是 deferred？
```

这一步看起来不如“新增一个炫酷功能”明显，但它会直接决定后面系统能不能继续变复杂。

## RootGraph 的第一版节点

我把 RootGraph 第一版拆成了几个节点：

```text
normalize_event
load_actor_context
hard_policy_gate
route_intent
build_runtime_context
dispatch_capability
commit_side_effects
render_response
```

它们不是每个都在第一天接管所有旧逻辑，但顺序是明确的。

### normalize_event

QQ 原始事件里有很多框架相关细节。

RootGraph 不应该让后面的子图直接关心这些东西，所以先把它归一成运行时上下文：

```text
message_id
raw_text
plain_text
has_image
```

以及会话上下文：

```text
session_type
session_key
group_id
```

这样后面判断的是 RuntimeState，而不是到处传 NoneBot event。

### load_actor_context

这里记录当前发送者是谁：

```text
user_id
actor_role
```

至少区分：

```text
OWNER
USER
BLOCKED
```

后面 MainAgent 和 Chat 的权限会依赖它。

### hard_policy_gate

这是 RootGraph 最关键的节点之一。

一些事情不应该交给 LLM 判断，也不应该等进了子图再说：

```text
黑名单用户不分发。
非主人不能进 MainAgent。
群聊默认不能进 MainAgent。
没有 intent 的消息直接忽略。
普通聊天如果 chat_access_policy 拒绝，就不进入 ChatGraph。
```

这个节点要做的是硬门控。

它不是“建议”，而是运行时的第一道防线。

### route_intent

当前第一版主要支持三个 intent：

```text
MAIN_AGENT
CHAT
IGNORE
```

也就是说：

```text
/agent 明确命令 -> MAIN_AGENT
普通聊天入口 -> CHAT
不该处理或无意图 -> IGNORE
```

旧固定命令没有被强行塞进 RootGraph。

它们继续由 NoneBot matcher 兜底，因为这批命令已经稳定，而且固定命令本身就是很好的 fallback。

### build_runtime_context

这一步不是把所有上下文都搬进 RootGraph。

比如普通聊天的 prompt、聊天历史、MemoryRAG，仍然主要由 ChatGraph 处理。

RootGraph 只记录这一轮上下文边界：

```text
chat context
main agent context
memory rag enabled
project doc rag enabled
vision used
```

这里有一个很重要的边界：

```text
MemoryRAG 可以进入普通聊天。
ProjectDocRAG 只能进入 /agent dev_context。
```

原因是 ProjectDocRAG 里有开发侧项目文档，它不应该被普通聊天角色卡随口说出去。

### dispatch_capability

RootGraph 不亲自处理业务。

它只把请求分发给对应 handler：

```text
MAIN_AGENT -> MainAgentGraph runtime handler
CHAT       -> 现有聊天运行链路
IGNORE     -> 不分发
```

第一版里，普通聊天已经开始从 RootGraph CHAT 进入现有聊天链路。

这很重要，因为它意味着普通聊天和 `/agent` 开始共享同一个运行入口骨架。

### commit_side_effects

严格来说，第一版还没有把所有副作用都迁到 RootGraph 统一提交。

比如聊天回复发送、聊天轮次保存、TTS 候选更新、摘要压缩调度，仍然发生在已有聊天链路里。

但我做了一个折中：

```text
副作用仍由原链路执行。
执行结果写入 chat_commit。
RootGraph 在 commit artifact 汇总。
```

这让 RootGraph 先拥有解释能力，再逐步拥有提交边界。

## 普通聊天怎么接入 RootGraph

这一阶段我没有动语义语音路径，因为语音涉及更多控制流和回复形态。

先接入的是普通文本/图片聊天：

```text
QQ 普通消息
  -> build_chat_preflight_runtime_state
  -> RootGraphRunner
  -> CHAT handler
  -> resolve image context
  -> legacy chat session / ChatGraph
  -> render / persist / tts candidate / compression
  -> chat_commit
  -> RootGraph commit artifact
```

这样做有一个好处：不会一次性重写聊天链路。

聊天的核心行为保持不变：

```text
该回复还是回复。
该落库还是落库。
该触发摘要压缩还是触发。
该设置 TTS 候选还是设置。
```

RootGraph 只是先包住它，让它变得可路由、可观测。

## chat_access_policy：把聊天权限前置

普通聊天原来就有一堆访问规则：

```text
私聊是否启用
群聊是否启用
主人是否永远允许
私聊白名单
群白名单
黑名单
陌生私聊试用次数
消息长度限制
普通聊天限流
```

如果这些判断只发生在 ChatGraph 里面，RootGraph 就无法解释“为什么没有分发”。

所以我给普通聊天加了一个 preflight：

```text
chat_access_policy
```

它会在进入 RootGraph 前先计算好：

```text
allow_dispatch
decision
reason
should_reply
reply_text
```

然后 RootGraph 的 hard_policy_gate 读取这个 artifact。

如果 `allow_dispatch=false`，RootGraph 直接把 intent 转成 IGNORE，不进入 CHAT handler。

这样拒绝路径也能被记录：

```text
不是 ChatGraph 沉默。
是 RootGraph 根据 chat_access_policy 阻断了分发。
```

这就是入口收敛带来的好处。

## chat_commit：先记录副作用，再谈统一提交

RootGraph 最终应该管理副作用提交，但这一步不能硬拆。

因为聊天链路里已经有很多成熟行为：

```text
发送 QQ 文本回复
发送语音
保存用户/助手消息
更新陌生私聊试用次数
设置 TTS 候选
调度会话摘要压缩
图片上下文 deferred
```

直接把这些搬到 RootGraph 里，风险太高。

所以我先加了 `chat_commit` artifact。

聊天链路每完成一个动作，就写入提交状态：

```text
qq_reply_sent
voice_response_sent
persisted_turn_saved
trial_updated
tts_candidate_updated
compression_scheduled
image_context_deferred
reply_chars
stored_user_chars
stored_assistant_chars
```

RootGraph 再把这些汇总到 `commit`：

```text
chat_reply_sent
chat_voice_sent
chat_persisted
chat_trial_updated
chat_compression_scheduled
chat_tts_candidate_updated
chat_image_context_deferred
chat_runtime_stage
```

这样一来，排查问题时就不会只剩一句“聊天失败了”。

你可以看到它到底失败在：

```text
没进入 CHAT handler
图片上下文还在 deferred
LLM 没有产生回复
回复已经发送但持久化失败
持久化成功但压缩没调度
语音路径被抑制
```

这是 RootGraph 很重要的一步：把运行时从黑盒变成半透明。

## `/agent RootGraph 最近观测`

做完 artifact 后，还需要一个能从 QQ 里看的入口。

所以我加了一个只读语义工具：

```text
/agent RootGraph 最近观测
```

也可以用类似说法：

```text
/agent RootGraph 状态
/agent 看看普通聊天路由
/agent chat commit 状态
```

它返回最近一次 RootGraph/CHAT 观测快照。

大概会包含：

```text
RootGraph/CHAT 最近观测：
时间：...
会话：private private:10001 group=-
消息：id=... text=是 image=否
Actor：user=10001 role=owner
Policy：allow allow=是 reason=...
Route：intent=chat handler=... dispatched=是
Context：level=chat memory_rag=是 project_doc_rag=否 vision=否
Runtime：stage=dispatched handler=legacy_chat_session
Commit：reply_sent=是 voice_sent=否 persisted=是 trial=否 compression=是 ...
Shadow：route=root_graph_chat stage=... valid=是 ...
```

这里我特意做了一个限制：

```text
不记录用户原文。
不记录 LLM 回复正文。
只记录布尔值、长度、计数、阶段和路由结果。
```

因为这个入口是给运维和调试用的，不应该变成另一个聊天记录泄漏口。

它的定位很明确：

```text
回答上一条普通聊天为什么处理或未处理。
回答它路由到了哪里。
回答它的副作用提交到了哪一步。
```

## MainAgent 和普通聊天的边界

RootGraph 统一入口之后，最怕边界被误合并。

所以这次我反复确认了几条规则：

```text
普通聊天不能触发 MainAgent 工具。
/agent 不能落入 ChatGraph 角色卡语气。
ChatGraph 不能访问 ToolRegistry。
MainAgent 本地工具结果直接返回，不交给角色卡二次加工。
ProjectDocRAG 不进入普通聊天。
高风险旧命令不做语义化。
旧固定命令继续保留。
```

尤其是高风险命令，我没有因为“语义化看起来很酷”就继续扩。

比如这些仍然不进入 `/agent` 语义工具：

```text
清空全部摘要
清空全部上下文
删除长期记忆
重建记忆索引
压缩当前会话
任意 shell
任意文件写
任意数据库写
```

这不是技术上做不到，而是边界上不应该。

Agent 系统不是能做越多越好。

它应该是：

```text
能解释。
能拒绝。
能审批。
能恢复。
能回退到旧命令。
```

## 这一步做完后，架构变成什么样

现在可以把系统理解成这样：

```text
QQ Event
  -> NoneBot matcher / adapter
  -> RootGraph RuntimeState
       -> normalize_event
       -> load_actor_context
       -> hard_policy_gate
       -> route_intent
       -> build_runtime_context
       -> dispatch_capability
            -> CHAT: ChatGraph / legacy chat runtime
            -> MAIN_AGENT: MainAgentGraph
            -> IGNORE: no-op
       -> commit_side_effects
       -> render_response
```

旧固定命令仍然在旁边作为 fallback：

```text
/最近错误
/配置状态
/群白名单
/选择角色卡
...
```

而 `/agent` 继续作为主人管理入口：

```text
/agent 看看最近错误
/agent 当前主模型是什么
/agent 选择角色卡莫言
/agent 把用户 10002 加入黑名单
/agent RootGraph 最近观测
```

区别是：现在普通聊天和 MainAgent 不再像两个完全分散的入口，而是开始共享同一套 runtime lifecycle。

## 测试覆盖

这一阶段我补的测试主要覆盖几类：

```text
RootGraph node sequence 合同
MAIN_AGENT / CHAT / IGNORE 路由矩阵
非主人 MainAgent 阻断
群聊 MainAgent 阻断
chat_access_policy 阻断 CHAT 分发
handler 异常记录 artifact
NoneBot 控制流异常 passthrough
普通聊天 side-effectful response 不重复渲染
chat_commit 汇总到 RootGraph commit
图片上下文 deferred 记录
root_graph_observations 语义分类和工具执行
ProjectDocRAG 仍保持在 /agent dev_context 边界内
```

最后全量测试结果：

```text
Ran 244 tests
OK
```

这类改造我觉得测试尤其重要。

因为它不是单个功能点，而是在调整系统的入口层。如果入口层出了问题，影响范围会很大。

## 小结

这次 RootGraph 改造没有让机器人突然“更聪明”。

它做的是另一件更基础的事：让系统开始拥有统一运行骨架。

现在每条消息不再只是散落在不同 handler 里，而是逐步进入同一套生命周期：

```text
事件归一
身份识别
硬权限
路由
上下文边界
能力分发
副作用提交记录
响应渲染
运行观测
```

这会让后续很多事变得更稳：

```text
更细的运行观测
更清晰的权限策略
更安全的审批恢复
更可靠的聊天副作用提交
更明确的 RAG 边界
更多子图接入统一入口
```

我越来越觉得，做一个长期运行的个人 AI 机器人，最难的不是接一个模型，也不是多加几个工具。

真正难的是在能力越来越多的时候，还能让系统保持可解释、可回退、可约束。

RootGraph 就是为了这个目标加的一层地基。

下一步我会继续把更多运行期观测和提交边界往 RootGraph 收敛，但不会急着把所有旧命令都塞进去。

对 Agent 系统来说，慢一点、稳一点，通常比“看起来什么都会”更重要。
