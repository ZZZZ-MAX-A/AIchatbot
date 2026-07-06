# RootGraph v1.5 收工：我给 QQ 机器人补上了聊天运行时的“黑匣子”

标签建议：`AI Agent`、`NoneBot`、`Agent 架构`、`可观测性`、`RAG`

## 开头

前一篇里，我给 QQ 机器人加了一层 `RootGraph`。

它的目标不是替代聊天模型，也不是把所有逻辑都塞进一个万能 Agent，而是把 QQ 消息进入系统后的几个关键问题讲清楚：

```text
这条消息是谁发的？
它属于哪个会话？
它应该被处理吗？
它应该进入普通聊天，还是进入 /agent？
处理过程中用了哪些上下文？
最后有没有回复、落库、压缩、语音候选或图片上下文？
```

做到这里以后，普通聊天已经开始经由 `RootGraph CHAT` 分发。

但真正上线以后我发现，架构接入只是第一步。更重要的是：出问题时要能看见问题在哪里。

这篇文章记录 `RootGraph v1.5` 的收尾：我把普通聊天、图片识别、MemoryRAG、MainAgent 和诊断入口合到一套可观测链路里，让机器人在 QQ 侧也能回答：

```text
刚才那条图片消息到底有没有进入视觉链路？
Ollama 是没启动，还是 qwen 模型没推理成功？
bge-m3 挂了以后是不是 RAG 停摆？
普通聊天有没有真的走 RootGraph？
/agent 有没有被错误地混进聊天语气？
```

这不是一个炫技功能，但它是系统变复杂以后最救命的部分。

## 为什么聊天系统也需要运行时观测

普通聊天看起来很简单：

```text
用户发消息
模型生成回复
机器人发回 QQ
```

但一个长期运行的 QQ 机器人很快会变成这样：

```text
权限判断
黑名单和白名单
私聊试用次数
群聊是否 @
图片等待合并文字
图片下载和视觉模型
短期历史
会话摘要
长期记忆
MemoryRAG
角色卡
TTS 候选
数据库持久化
摘要压缩
/agent 管理入口
审批流
```

只要其中一个环节出问题，用户看到的可能只是：

```text
机器人没回。
机器人回得不对。
图片识别成了一串 @@@@@@。
RAG 好像没有记忆。
/agent 看起来像被普通聊天吃掉了。
```

如果没有运行时观测，就只能翻日志、猜路径、重启服务、再试一次。

所以 `v1.5` 的后半段，我没有继续加新能力，而是给已有能力补“黑匣子”。

## RootGraph v1.5 的核心定位

我最终给 RootGraph 定下来的边界是：

```text
RootGraph routes.
Subgraphs execute.
Policy gates decide.
Artifacts explain.
```

也就是说：

```text
RootGraph：
  负责统一入口、权限前置、路由、上下文层级、提交状态汇总和观测。

ChatGraph / legacy chat：
  负责普通聊天生成、记忆注入、图片上下文、发送回复和持久化。

MainAgentGraph：
  负责 /agent 的语义工具、只读查询、审批门控写操作和任务控制面。

VisionGraph：
  负责图片解析和视觉模型调用。

MemoryRAG：
  负责语义记忆检索和向量索引。
```

这让 RootGraph 不会变成另一个“巨型上帝对象”。

它只回答运行时问题：

```text
这轮为什么走这里？
它有没有被允许？
它有没有分发？
它用了什么类型的上下文？
它最后提交了哪些副作用？
如果失败，失败发生在哪个边界？
```

## 普通聊天接入 RootGraph CHAT

`v1.5` 里，普通聊天的主路径变成：

```text
QQ message
  -> NoneBot adapter
  -> RuntimeState
  -> RootGraph
       -> hard_policy_gate
       -> route_intent
       -> build_runtime_context
       -> dispatch CHAT handler
       -> summarize commit artifacts
       -> observe runtime
  -> existing chat chain sends reply
```

这里有一个很重要的实现选择：

```text
RootGraph 不重复发送聊天回复。
```

因为旧聊天链路已经负责 QQ 发送、落库、压缩、TTS 候选等副作用。如果 RootGraph 外层再发送一次，就会产生重复回复。

所以当前版本里，`RootGraph CHAT` 的 handler 会复用既有聊天链路，真正的 QQ 回复仍由聊天链路发送；RootGraph 只把结果同步进 artifact。

这是一种过渡式接入：

```text
先统一入口和观测。
再逐步收束副作用位置。
```

我认为这是迁移复杂运行时最稳的方式。

## chat_access_policy：把聊天权限放到 RootGraph 前面

普通聊天最容易出事故的地方是权限。

例如：

```text
黑名单用户不能聊。
未知私聊用户可能只允许试用。
群聊必须在白名单里。
群聊非 @ 消息通常应该静默。
消息太长或限流时不能继续。
```

以前这些判断更多散在聊天入口和旧 handler 里。`v1.5` 开始，普通聊天会先构建一个 `chat_access_policy` artifact：

```text
chat_access_policy:
  allow_dispatch
  reason
  should_reply
  response_text
  actor_role
  session_type
  message_length
  rate_limited
```

RootGraph 的 `hard_policy_gate` 会读取它。

如果 `allow_dispatch=false`，RootGraph 会直接阻止 `CHAT` 分发：

```text
不进聊天 handler。
不调模型。
不解析图片。
不进入 MemoryRAG。
```

这个顺序很关键。

图片解析、RAG 检索和 LLM 调用都应该发生在权限放行之后，而不是先做昂贵操作，再发现其实不该回复。

## chat_commit：看清楚一轮聊天到底提交了什么

聊天回复不是只有“发出去”这一件事。

一次普通聊天可能还会做这些动作：

```text
保存用户消息
保存助手回复
消耗陌生私聊试用次数
更新 TTS 候选文本
触发摘要压缩
发送语音
延迟图片上下文，等待用户补文字
```

所以我加了 `chat_commit` artifact，用来记录聊天链路已经完成的提交状态：

```text
chat_commit:
  qq_reply_sent
  voice_response_sent
  persisted_turn_saved
  trial_updated
  compression_scheduled
  tts_candidate_updated
  image_context_deferred
  reply_chars
  stored_user_chars
  stored_assistant_chars
```

RootGraph 再把这些信息汇总到自己的 `commit` artifact。

这样 `/agent RootGraph 最近观测` 里就可以看到：

```text
Commit：
  reply_sent=是
  voice_sent=否
  persisted=是
  trial=否
  compression=是
  tts_candidate=是
  image_deferred=否
```

这比“机器人刚才好像回了”可靠得多。

## 图片链路：从 @@@@@@ 到可诊断

这次 `v1.5` 收尾里，最现实的问题来自图片。

有一段时间，QQ 表情包可以识别，但手机截图或电脑截图会被视觉模型输出成类似：

```text
@@@@@@
@@@@@@
@@@@@@
```

从用户角度看，这就像图片功能坏了。

但真正的问题可能有好几类：

```text
QQ 图片没有被正确提取。
图片 URL 或 file_id 没拿到。
Ollama 服务没启动。
qwen2.5vl:3b 模型没被当前 OLLAMA_MODELS 目录识别。
视觉模型上下文太小，截图内容触发低质量输出。
模型返回了重复符号，但系统误以为这是有效描述。
```

所以我做了三件事。

第一，提高视觉模型上下文：

```text
VISION_NUM_CTX=16384
```

并在 Ollama `/api/chat` 视觉请求里写入：

```text
options.num_ctx
```

第二，增加低质量输出检测。

如果视觉模型返回大量重复符号，比如 `@@@@@@`，系统会把它判定为视觉失败，而不是把它当作图片描述写进聊天上下文。

第三，把图片链路的非正文统计写入 RootGraph 观测：

```text
Vision detail：
  context
  urls
  continue
  descriptions
  errors
  low_quality
  num_ctx
```

注意这里不记录图片 URL，也不记录图片描述正文，只记录计数和状态。

这是一个隐私边界。

诊断要足够有用，但不能把用户发的图和模型描述泄露进观测文本里。

## /视觉状态：不只看模型存在，还要真实推理

以前很多“视觉状态”诊断只检查：

```text
Ollama 能不能连上。
/api/tags 里有没有 qwen 模型。
```

但这不够。

因为模型存在不代表能正常推理。尤其是视觉模型，还可能遇到 mmproj、上下文、模型文件路径等问题。

所以 `/视觉状态` 现在会做一次真实推理自检：

```text
生成一张内置 32x32 PNG 测试图。
调用当前配置的 Ollama vision 模型。
检查是否返回有效文本。
检查是否出现低质量重复符号。
只展示耗时和返回字符数。
不展示模型对测试图的描述正文。
```

诊断输出大概长这样：

```text
推理自检：正常，用时 8.3 秒，返回 74 字
```

如果 Ollama 没启动，或者模型不在当前模型目录里，它会直接显示失败原因。

这对本地模型系统非常重要。

因为用户经常会遇到：

```text
模型文件在磁盘里。
但当前 ollama serve 没用那个 OLLAMA_MODELS 目录。
```

这时候“文件存在”和“服务可用”不是一回事。

## /记忆状态：bge-m3 挂了，RAG 会怎样

MemoryRAG 的关键依赖是 embedding provider。

当前本地配置里，它对应的是：

```text
Ollama bge-m3
```

如果 bge-m3 不能连接，RAG 检索会受影响。常见错误类似：

```text
EmbeddingProviderError: Cannot connect to Ollama
```

但这不应该让普通聊天直接停摆。

所以我给 `/记忆状态` 和 `/RAG状态` 加了真实 embedding 自检：

```text
使用固定测试文本。
调用当前 embedding provider。
校验返回维度。
展示耗时和维度。
不读取用户聊天内容。
不读取记忆正文。
不写数据库。
不重建索引。
```

成功时可以看到：

```text
Embedding 自检：正常，用时 5.9 秒，维度 1024
```

这里的边界是：

```text
bge-m3 正常：
  MemoryRAG 和 ProjectDocRAG 的语义检索可用。

bge-m3 失败：
  RAG 检索不可用或降级。
  普通聊天仍应尽量继续。
```

也就是说，embedding 是 RAG 的发动机，但不是整个聊天系统的发动机。

## /agent 聚合诊断：把分散状态合在一起

单独的诊断命令很多：

```text
/视觉状态
/记忆状态
/RAG状态
/最近错误
/agent RootGraph 最近观测
/agent MainAgent 最近观测
```

但真实排障时，用户通常不会先知道该查哪一个。

他说的可能是：

```text
/agent 诊断一下 Ollama
/agent 看一下视觉和记忆状态
/agent 最近图片和 RAG 有没有问题
```

所以我给 MainAgent 的只读语义工具加了一个聚合诊断命令：`ops_health`。

它仍然是只读工具，不写数据库，不重建索引，不读取用户图片正文。

返回内容按区块合并：

```text
Agent 聚合诊断：
范围：视觉/Ollama、MemoryRAG/Embedding、最近错误、RootGraph、MainAgent。

视觉链路：
  ...

RAG/Embedding：
  ...

最近错误：
  ...

RootGraph：
  ...

MainAgent：
  ...
```

这让 `/agent` 从“能查很多状态”变成“能帮我判断现在系统哪块可能坏了”。

它仍然不是自主运维 Agent。

它只是一个安全的 owner-only 只读诊断入口。

## RootGraph 最近观测长什么样

现在 `/agent RootGraph 最近观测` 会输出类似这样的摘要：

```text
RootGraph/CHAT 最近观测：
时间：2026-07-06T14:32:07
会话：private private:3313097998 group=-
消息：id=1177041770 text=否 image=是
Actor：user=3313097998 role=owner
Policy：allow allow=是 reason=policy allows dispatch
Route：intent=chat handler=chat dispatched=是
Context：level=chat_context memory_rag=是 project_doc_rag=否 vision=是
Runtime：stage=dispatched handler=legacy_chat_session
Commit：reply_sent=是 voice_sent=否 persisted=是 trial=否 compression=是 tts_candidate=是 image_deferred=否
Commit detail：reply_chars=252 stored_user_chars=153 stored_assistant_chars=252
Shadow：route=root_graph_chat stage=finalizing valid=是 mode=text history=48 reply_chars=252
```

这段信息刻意不包含：

```text
用户原文
助手回复正文
图片 URL
图片描述正文
RAG 命中的记忆正文
```

只看结构，不看隐私内容。

对排障来说，这已经足够回答大多数问题：

```text
消息有没有图片？
RootGraph 有没有分发？
走的是不是 CHAT？
有没有用 vision？
有没有启用 MemoryRAG？
回复有没有发送？
有没有持久化？
shadow 状态是否合法？
```

## MainAgent 的边界没有放松

在加聚合诊断时，我特别注意不破坏 MainAgent Route B 的边界。

当前 `/agent` 的工具仍然分层：

```text
owner_read_command：
  主人只读查询。
  可以语义触发。
  不需要审批。

owner_write_command：
  主人写操作。
  可以语义命中。
  必须先创建审批。
  确认后只恢复注册过的工具。

agent_task_command：
  本地确定性任务/审批控制面。
  不暴露给 LLM 工具契约。

dev_context：
  项目文档 RAG。
  只进入 /agent 开发侧上下文。
```

新增的聚合诊断属于 `owner_read_command`。

它能读：

```text
视觉诊断结果
RAG 状态结果
最近错误摘要
RootGraph 观测摘要
MainAgent 观测摘要
```

它不能做：

```text
清空错误日志
重建索引
修改白名单
修改角色卡
写长期记忆
执行 shell
写文件
写数据库
```

这条边界很重要。

诊断命令越方便，越不能顺手变成“帮我修一下”的自动执行命令。

## 这次封版的测试结果

封版前最后一轮完整测试：

```powershell
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

结果：

```text
Ran 260 tests in 3.848s
OK
```

同时做了本地运行态检查：

```text
NoneBot 启动成功。
ai_chat 插件加载成功。
Uvicorn 监听 http://127.0.0.1:8080。
启动日志无新的错误输出。
```

并打了封版 tag：

```text
v1.5
```

对我来说，这意味着 `v1.5` 可以作为一个稳定基线：

```text
普通聊天已经进入 RootGraph CHAT。
/agent 仍保持明确入口。
视觉、RAG、RootGraph、MainAgent 都有 QQ 侧诊断路径。
写操作仍然走审批。
项目文档 RAG 不进入普通聊天。
```

## 这版没有做什么

这次我刻意没有继续扩功能。

没有做：

```text
多步自主 Agent loop
自动修复 Ollama
自动重建 RAG 索引
自动写长期记忆
自动修改角色卡
把所有旧命令迁进 /agent
让普通聊天触发主人管理工具
让 ProjectDocRAG 进入普通聊天
```

原因很简单：`v1.5` 的主题是运行时收束和可观测性，不是自主执行。

如果在同一版里继续塞自动修复、自动任务和更多写工具，就会把刚刚建立起来的边界再次搅乱。

## 小结

`RootGraph v1.5` 做完后，这个 QQ 机器人从“功能很多，但排障靠猜”往前走了一步。

现在它至少能在 QQ 侧解释：

```text
为什么这条消息进了聊天。
为什么这条消息被拦截。
图片链路有没有启用。
视觉模型有没有真实推理成功。
bge-m3 embedding 是否可用。
RAG 是否可能失效。
最后有没有回复、落库、压缩或更新 TTS 候选。
/agent 有没有走 MainAgent 边界。
```

这类东西平时不显眼。

但当机器人开始长期运行、接入图片、RAG、语音、审批流和本地模型以后，可观测性本身就会变成核心功能。

下一版我还没有急着开。

候选方向大概有几个：

```text
MainAgent 任务运行时：
  让 /agent 更擅长管理任务和解释下一步，但写操作继续审批。

RootGraph 副作用边界：
  继续把语音、通知、图片延迟合并等链路纳入统一生命周期。

RAG 降级策略：
  bge-m3 失效时更明确地降级和提示。

自动巡检：
  周期性检查 Ollama、qwen、bge、8080 和最近错误。
```

但这些都应该是 `v1.6` 的事情。

`v1.5` 到这里，先收工。
