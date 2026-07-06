# AIchatbot 未来运行时与底层框架设计

状态：讨论沉淀稿

记录日期：2026-07-06

适用范围：`v1.5` 封版之后的长期架构方向讨论。本文不代表立即进入 `v1.6` 实施，也不要求马上迁移官方 LangChain / LangGraph；它用于保存当前对项目底层框架、未来多端扩展、官方框架复用边界和核心安全边界的判断。

## 结论先行

当前项目虽然以 QQ 聊天机器人起步，但已经逐渐形成了一个更通用的个人 AI Runtime：

```text
有入口适配。
有 RootGraph 统一运行时。
有普通聊天图。
有主人 MainAgent 图。
有 ToolRegistry。
有 PolicyEngine。
有审批流。
有 MemoryRAG / ProjectDocRAG。
有视觉、语音、诊断和运行时观测。
```

因此，未来可以扩展到网页、桌宠、本地 API 或管理后台。但扩展方式不应该是把 Web / 桌宠逻辑直接塞进 QQ 插件，而应该逐步把项目拆成：

```text
平台适配层：
  QQ / Web / Desktop / API

核心运行时：
  RootGraph / ChatGraph / MainAgentGraph / ToolPolicy / Memory / RAG / Diagnostics

平台渲染层：
  QQ 文本和语音
  Web markdown / card / stream / button
  桌宠气泡 / TTS / 表情 / 动作
```

对官方 LangChain / LangGraph 的态度是：

```text
可以复用官方框架的模型适配、结构化输出、tool schema、retriever、callback/tracing 和未来的 checkpoint / interrupt / resume。

但不能让官方框架替代项目已有的业务边界：
  MainAgent 和 ChatAgent 不合并。
  MemoryRAG 和 ProjectDocRAG 不做无边界统一。
  ToolRegistry 和 PolicyEngine 仍是权威安全边界。
  写操作仍然必须审批。
  普通聊天仍然不能触发主人管理工具。
```

一句话：

```text
统一底层能力，不统一权限边界。
```

## 当前架构基线

`v1.5` 封版后，项目已经具备以下核心结构：

```text
QQ / NapCat / OneBot / NoneBot
  -> RootGraph
       -> CHAT
       -> MAIN_AGENT
       -> IGNORE

CHAT
  -> 既有聊天链路 / ChatGraph runtime
  -> 角色卡
  -> 短期历史
  -> 摘要
  -> 长期记忆
  -> MemoryRAG
  -> 图片上下文
  -> TTS 候选

MAIN_AGENT
  -> MainAgentGraph
  -> ToolRegistry
  -> ToolPolicyCheck
  -> owner_read_command
  -> owner_write_command
  -> agent_task_read
  -> agent_task_command
  -> dev_context
  -> approval

DevContextGraph
  -> ProjectDocRAG
  -> MemoryRAG
  -> CombinedRAG output

Diagnostics
  -> 视觉真实推理自检
  -> bge-m3 embedding 自检
  -> 最近错误
  -> RootGraph 最近观测
  -> MainAgent 最近观测
```

最重要的边界已经成立：

```text
普通聊天不触发 ToolRegistry。
普通聊天不触发 owner_write_command。
普通聊天不读取 ProjectDocRAG。
/agent 默认 owner private only。
非 owner 不进入 MainAgentGraph。
群聊默认不允许 MainAgent。
LLM 只能生成 ActionRequest，不能直接执行工具。
工具必须经过 ToolRegistry 注册和参数校验。
工具必须经过 PolicyEngine 风险判断。
写操作必须审批。
审批恢复只能恢复注册过且 approval_resume_enabled=true 的工具。
```

这些边界是项目当前最有价值的资产。后续所有框架升级都应服务这些边界，而不是抹平它们。

## 当前类 LangGraph Runner 的定位

项目当前没有直接使用官方 `langgraph.StateGraph` 作为主运行时，而是实现了一套 LangGraph-style 自研 runner。

典型结构是：

```text
State dataclass
Node enum
NODE_SEQUENCE
GraphRunner.run()
node_trace
result
artifact
error break
```

例如：

```text
RootGraphRunner:
  normalize_event
  load_actor_context
  hard_policy_gate
  route_intent
  build_runtime_context
  dispatch_capability
  commit_side_effects
  render_response

MainAgentGraphRunner:
  validate_agent_request
  build_agent_context
  call_main_agent
  validate_action_request
  check_tool_policy
  execute_tool
  render_agent_response

ChatGraphRunner:
  validate_input
  resolve_image_context
  prepare_memory
  build_prompt_context
  call_chat_agent
  maybe_voice_response
  persist_turn
  update_trial_accounting
  update_tts_candidate
  schedule_compression
  render_response

DevContextGraphRunner:
  validate_context_request
  retrieve_combined_context
  render_context_artifact
```

这种模式不是官方 LangGraph，但保留了 LangGraph 的核心思想：

```text
状态流动。
节点边界。
节点顺序。
错误中断。
运行轨迹。
可注入 handler。
可测试的 execution result。
```

### 优点

#### 1. 控制力强

项目接入 QQ、图片、语音、RAG、审批、任务和本地模型，安全边界比“通用 Agent demo”复杂得多。自研 runner 让每一步都在代码里可见：

```text
先校验权限。
再构建上下文。
再请求模型。
再校验结构化输出。
再检查工具策略。
再执行工具。
最后渲染回复。
```

LLM 不能绕过中间节点。

#### 2. 权限和审批边界清楚

当前 MainAgent 不是模型自由调工具，而是：

```text
LLM / 本地语义分类器
  -> ActionRequest
  -> ToolRegistry.validate_arguments
  -> PolicyEngine.decide_tool_policy
  -> approval_required / execute_tool
```

工具执行权不在模型手里。

#### 3. 单元测试简单

每个 runner 都可以注入 fake handler：

```text
RootGraphRunner.run(state)
MainAgentGraphRunner.run(state)
ChatGraphRunner.run(state)
DevContextGraphRunner.run(state)
```

测试可以稳定覆盖：

```text
node_trace 是否正确。
handler 是否被调用。
policy 是否阻止。
error 是否写入。
tool_request 是否被校验。
审批是否中断。
commit artifact 是否汇总。
```

#### 4. 适合旧系统渐进迁移

当前项目不是从零开始。它已有旧聊天链路、旧 NoneBot matcher、旧诊断命令、旧记忆命令、旧图片缓存和旧语音入口。

自研 runner 支持“包裹式迁移”：

```text
RootGraph 先包住普通聊天。
CHAT handler 继续复用现有聊天链路。
聊天链路写 chat_commit。
RootGraph 汇总 commit artifact。
RootGraph 不重复发送 QQ 回复。
```

这样可以先得到统一入口和观测，再慢慢迁移副作用边界。

#### 5. artifact 可按项目真实问题定制

RootGraph 观测不是通用 trace，而是项目需要的运行快照：

```text
policy
route
context
commit
error
chat_access_policy
chat_commit
vision detail
shadow snapshot
```

它能回答：

```text
这条消息有没有图片？
有没有进入 CHAT？
有没有用 vision？
MemoryRAG 是否启用？
ProjectDocRAG 是否被隔离？
回复有没有发送？
聊天有没有持久化？
图片上下文是不是 deferred？
视觉模型是不是返回低质量符号？
```

#### 6. 对 NoneBot 控制流友好

NoneBot 的 `matcher.finish`、`matcher.pause`、`matcher.reject` 等控制流不能被当成普通异常。自研 `RootGraphRunner` 可以显式配置 passthrough exceptions，避免把 NoneBot 控制流误包装成运行时错误。

### 缺点

#### 1. 没有官方 checkpoint

当前 runner 是一次性内存执行：

```text
run 从头到尾。
中间状态主要靠 return result / artifact。
进程重启后没有 graph-level checkpoint。
暂停和恢复不是 runner 原生能力。
```

当前项目已有 `agent_tasks`、`agent_approvals` 等业务持久化，但这不是官方 LangGraph 意义上的节点级 checkpoint。

#### 2. 条件分支表达朴素

当前主要是线性 `NODE_SEQUENCE`：

```text
for node in NODE_SEQUENCE:
  execute node
  if error:
    break
```

如果未来出现复杂动态分支，比如多步任务、重试、等待用户确认、等待外部服务、审批后继续后续计划，自研 runner 会逐渐堆出很多 `if/elif`。

官方 LangGraph 的条件边更适合复杂分支。

#### 3. 没有官方 tracing / 可视化生态

当前依赖：

```text
node_trace
artifact
QQ 诊断命令
本地日志
单元测试
```

官方 LangGraph / LangSmith 可以提供更完整的：

```text
节点图可视化
state diff
tool call trace
LLM call trace
stream events
debug timeline
```

但引入远端 tracing 时必须处理隐私脱敏。

#### 4. retry / timeout / parallel / streaming 要自建

当前自研 runner 没有统一的：

```text
节点级 retry
节点级 timeout
并行节点
streaming events
checkpoint store
中断恢复协议
```

这些以后如果需要，要么自建，要么局部引入官方 LangGraph。

#### 5. 容易形成“像 LangGraph 但不是官方 LangGraph”的认知误差

文档和讨论里要明确：

```text
当前是 LangGraph-style runner。
不是官方 StateGraph runtime。
```

否则容易误以为已经具备官方 checkpoint / interrupt / resume 等能力。

## checkpoint 的价值边界

checkpoint 保存的是图执行到某个节点时的运行时状态。它不是聊天记忆，也不是普通数据库记录。

它服务的是：

```text
长流程连续性。
多步任务恢复。
审批中断后继续。
失败续跑。
防重复执行。
任务进度查询。
跨消息协作。
```

### 和当前持久化的区别

当前项目已有：

```text
聊天原文
会话摘要
空窗摘要
长期记忆
agent_tasks
agent_task_events
agent_approvals
RAG 索引
RootGraph 最近观测
MainAgent 最近观测
```

这些是业务状态、记忆和审计日志。

checkpoint 保存的是：

```text
当前图执行到哪个节点。
state 里有什么。
已经执行过哪些工具。
工具结果是什么。
是否正在等待用户确认。
确认后应该从哪里继续。
哪些工具调用不能重复执行。
```

### checkpoint 有用的场景

#### 1. 审批中断和恢复

例如：

```text
/agent 帮我清空图片缓存，然后重新诊断视觉状态
```

理想图流程：

```text
plan
  -> diagnose vision
  -> decide clear image cache
  -> request approval
  -> interrupt
  -> owner confirms
  -> execute clear_image_cache
  -> run vision_status again
  -> summarize result
```

当前业务表可以恢复“单个工具执行”。
checkpoint 更适合恢复“审批后继续整个计划”。

#### 2. 多步只读排障

例如：

```text
/agent 帮我完整排查图片识别问题
```

可能需要：

```text
ops_health
vision_status
recent_errors
root_graph_observations
main_agent_observations
final_summary
```

checkpoint 可以避免中途失败后重复执行已经完成的诊断。

#### 3. 长耗时任务

例如：

```text
重建项目文档索引
扫描日志
生成版本报告
批量检查文档
```

checkpoint 可以支持服务重启后续跑。

#### 4. 外部等待

例如：

```text
等待主人确认
等待本地服务启动
等待模型下载
等待 GitHub push
等待 TTS 热启动
```

checkpoint 可以让图进入 `waiting_for_user` 或 `waiting_for_service` 状态。

#### 5. 人机协作任务

例如：

```text
/agent 帮我整理 v1.6 计划，先问我几个问题。
```

Agent 需要跨多条消息保存：

```text
已经问过什么。
用户回答了什么。
下一步该问什么。
最终方案生成到哪一步。
```

### 当前不急需 checkpoint 的场景

这些短流程暂时不需要：

```text
普通聊天单轮回复
/视觉状态
/记忆状态
/RAG状态
/agent RootGraph 最近观测
/agent MainAgent 最近观测
/agent 聚合诊断
单个 owner_read_command
单个 owner_write_command 创建审批
单个审批确认后恢复单工具执行
```

当前业务持久化已经足够支撑这些功能。

## LangChain 官方能力的复用边界

当前 LangChain 主要服务 MainAgent：

```text
build_main_llm
create_main_llm_call
invoke_main_llm
build_main_agent_action_messages
call_main_llm_for_action
call_main_llm_for_tool_summary
```

普通聊天目前仍主要走旧 `AsyncOpenAI` 路径，`build_chat_llm` 已存在但不是聊天主链路核心。

未来可以逐步复用 LangChain 的能力，但应遵守：

```text
LangChain 负责模型和工具表达。
项目代码负责权限和执行。
```

### 适合 LangChain 接管或增强的部分

#### 1. 模型适配

可以统一：

```text
Main LLM
Chat LLM
summary LLM
tool summary LLM
embedding wrapper
```

但模型配置仍应区分：

```text
MAIN_LLM_*
CHAT_LLM_*
SUMMARY_LLM_*（未来可选）
EMBEDDING_*
```

#### 2. PromptTemplate / ChatPromptTemplate

可用于：

```text
MainAgent action planner prompt
tool summary prompt
普通聊天 prompt 的部分模板化
摘要压缩 prompt
空窗摘要 prompt
```

但角色卡、身份、隐私边界和 RAG 注入规则仍应由项目代码明确组装。

#### 3. 结构化输出

可以考虑：

```text
with_structured_output
JsonOutputParser
PydanticOutputParser
```

用于替代或增强 MainAgent `ActionRequest` JSON 解析。

但不能替代：

```text
ToolRegistry 参数校验
PolicyEngine 风险判断
审批逻辑
```

#### 4. Tool schema

可以从 `ToolRegistry` 生成 LangChain tool schema：

```text
ToolRegistry 是权威工具注册表。
LangChain tools 是给模型看的 schema。
工具执行仍回到 ToolRegistry。
```

不建议让 LangChain tool 直接绑定真实副作用函数绕过项目策略。

#### 5. Retriever / RAG 接口

可以借用：

```text
Embeddings
Document
Retriever
TextSplitter
Runnable chain
```

但 RAG 可见性和 scope 仍由项目控制。

#### 6. callback / tracing

可以接：

```text
LLM latency
tool call trace
prompt / parser error
token usage
```

但默认不应上传用户正文、图片 URL、记忆正文、项目敏感内容。若接 LangSmith 或远端 tracing，必须先做脱敏策略。

### 不应交给 LangChain 的部分

```text
owner 身份判断
黑名单 / 白名单
QQ群聊是否 @
普通聊天是否允许进入
ProjectDocRAG 是否允许进入普通聊天
写操作是否需要审批
审批恢复是否可执行
任意 shell / 文件 / 数据库写入权限
QQ 外发权限
记忆写入边界
角色卡修改权限
```

这些必须继续由项目代码和 PolicyEngine 决定。

## 是否要合并 MainAgent 和 ChatAgent

不应该合并。

当前两个 Agent 的职责不同：

```text
ChatAgent:
  普通聊天。
  角色卡表达。
  聊天记忆。
  图片上下文。
  不接主人管理工具。
  不读 ProjectDocRAG。

MainAgent:
  /agent 显式入口。
  主人管理。
  诊断。
  任务和审批。
  ProjectDocRAG dev_context。
  不走角色卡聊天语气。
```

合并会带来风险：

```text
普通聊天误触工具。
ProjectDocRAG 泄露到普通聊天。
管理回复被角色卡语气污染。
审批提示不够清晰。
安全审计变复杂。
```

未来即使引入官方 LangChain Agent，也应该是：

```text
统一底层模型适配和 tool schema。
不统一入口、权限、RAG 范围和输出风格。
```

可以共享：

```text
LLM provider factory
错误格式化
tracing callback
prompt utilities
RAG result formatter
embedding provider
health diagnostics
```

不应共享：

```text
系统 prompt
角色卡 prompt
工具权限
ProjectDocRAG 访问权
审批能力
输出渲染器
```

## 是否要统一 MemoryRAG 和 ProjectDocRAG

不应该做无边界统一。

当前两条 RAG 线语义不同：

```text
MemoryRAG:
  来源是聊天记忆、摘要、长期记忆。
  服务普通聊天。
  与用户、会话、主人身份相关。
  可进入 chat_context。

ProjectDocRAG:
  来源是项目文档和代码文档。
  服务开发侧 /agent。
  只进入 dev_context。
  不进入普通聊天。
```

可以统一底层能力：

```text
embedding provider
vector storage helper
document schema
chunker
score filter
context formatter
diagnostic self-check
```

但必须保留上层 scope：

```text
search(scope="memory")
search(scope="project_docs")
search(scope="combined_dev_context")
```

以及策略：

```text
MemoryRAGPolicy:
  允许普通聊天按权限读取。

ProjectDocRAGPolicy:
  只允许 owner /agent dev_context 读取。
```

不要出现：

```text
一个 global RAG，所有 Agent 和所有入口都能搜。
```

## 多端扩展方向

项目未来可以从 QQ 扩展到：

```text
Web Chat
Web Owner Console
Desktop Pet
Local API
CLI / Dev Console
```

扩展原则：

```text
扩展入口，不扩散边界。
```

也就是说，可以有多个入口：

```text
QQ
Web
Desktop
API
```

但仍保持：

```text
普通聊天不触发主人管理工具。
MainAgent 只在授权管理入口使用。
ProjectDocRAG 不进入普通聊天。
写操作必须审批。
视觉、RAG、错误、RootGraph、MainAgent 都可观测。
```

### 目标结构

```text
QQ Adapter
Web Adapter
Desktop Pet Adapter
API Adapter
  -> Runtime Core
       -> RootGraph
       -> ChatGraph
       -> MainAgentGraph
       -> Memory / RAG / Vision / Voice / Diagnostics
  -> Channel Renderer
```

更具体：

```text
                +----------------+
QQ / NoneBot -> | QQ Adapter     |
                +----------------+
                         |
                +----------------+
Web / API  ---> | Web Adapter    |
                +----------------+
                         |
                +----------------+
Desktop Pet ->  | Pet Adapter    |
                +----------------+
                         |
                         v
                +----------------+
                | Runtime Core   |
                +----------------+
                         |
                         v
                +----------------+
                | RootGraph      |
                +----------------+
                  |      |      |
                  v      v      v
              Chat   MainAgent  SystemEvent
              Graph  Graph      Graph
```

### 需要抽象的核心对象

#### InboundEvent

未来不应让核心运行时直接依赖 `MessageEvent`。可以设计：

```text
InboundEvent:
  channel
  surface
  event_id
  event_type
  user_id
  display_name
  session_id
  session_type
  text
  attachments
  metadata
```

#### RuntimePrincipal

QQ 里 owner 是 QQ 号；Web 里 owner 是登录账号；桌宠里 owner 可能是本机用户。

需要统一身份模型：

```text
Principal:
  id
  display_name
  role
  auth_provider
  channel
  permissions
```

再映射到：

```text
ActorRole:
  owner
  whitelisted
  user
  blocked
```

#### AttachmentRef / ImageRef

QQ 图片来自 OneBot segment / file_id / url；Web 图片来自上传文件；桌宠图片可能来自截图或本地文件。

需要统一：

```text
AttachmentRef:
  kind
  source
  content_type
  size
  local_path
  remote_url
  file_id
  metadata
```

#### ResponseEnvelope

未来不能只返回字符串：

```text
ResponseEnvelope:
  text
  markdown
  voice_text
  media
  cards
  actions
  emotion
  animation
  should_reply
  metadata
```

QQ renderer 可以取：

```text
text / voice
```

Web renderer 可以取：

```text
markdown / cards / buttons / stream
```

Desktop renderer 可以取：

```text
bubble / TTS / emotion / animation
```

## Web 方向

Web 可以分两条线：

```text
Web Chat:
  浏览器聊天界面。
  支持文字、图片上传、历史、语音播放、流式输出。

Web Owner Console:
  管理后台。
  查看诊断、任务、审批、RootGraph 观测、MainAgent 观测。
```

第一阶段建议优先做 Web Owner Console，而不是完整 Web Chat。

原因：

```text
Owner Console 能复用 /agent 的只读和审批能力。
对普通聊天主链路影响小。
安全边界清楚。
收益明显。
```

第一版 Web Owner Console 可以做：

```text
登录
查看 /视觉状态
查看 /RAG状态
查看 /最近错误
查看 RootGraph 最近观测
查看 MainAgent 最近观测
查看任务列表
查看审批列表
确认 / 拒绝审批
查看聚合诊断
```

暂时不做：

```text
公开聊天入口
多人账户
复杂角色卡编辑器
任意文件管理
自动任务执行
```

## Desktop Pet 方向

桌宠不是“多一个聊天窗口”，而是“持续存在的角色表现层”。

它需要新增：

```text
桌面窗口
角色立绘 / Live2D / Spine / PNG 动画
表情状态
动作状态
气泡文本
TTS 播放
主动提醒
待机行为
鼠标点击互动
拖拽
本地通知
```

当前可复用：

```text
ChatGraph
角色卡
MemoryRAG
TTS
Vision
MainAgent 诊断能力
RootGraph 运行时
```

需要新增：

```text
PetPresentationLayer
PetState
Emotion / Animation mapper
DesktopEventAdapter
DesktopRenderer
ProactiveGraph / SchedulerGraph
```

桌宠输出不只是文本，可能是：

```json
{
  "text": "我看了一下，Ollama 好像没起来。",
  "voice_text": "我看了一下，Ollama 好像没起来。",
  "emotion": "concerned",
  "animation": "think",
  "actions": [
    {"type": "show_status_panel", "target": "ollama"}
  ]
}
```

第一版桌宠建议只做：

```text
本地窗口
固定立绘或简单动画
文字输入
气泡回复
TTS 播放
idle / thinking / speaking / error 四类状态
```

暂时不做：

```text
屏幕感知
自动看屏幕
主动打扰
复杂日程
多角色
长期自主任务
```

## 多端后的 ToolPolicy 升级

当前 ToolPolicy 主要看：

```text
risk_level
is_owner
is_group
enable_external_read
enable_local_write
enable_external_write
```

多端后还需要看：

```text
channel:
  qq / web / desktop / api

surface:
  chat / admin_console / pet / dev_console

interaction_mode:
  passive_chat / management / background / proactive

supports_approval:
  true / false

supports_rich_ui:
  true / false
```

例如：

```text
QQ 私聊：
  可以发起审批。

Web Owner Console：
  可以发起审批，也可以展示更详细 diff。

桌宠普通聊天：
  不应该触发危险写工具。

桌宠管理模式：
  可以发起审批，但必须有明显 UI 提示。
```

未来 ToolPolicyInput 可以扩展为：

```text
ToolPolicyInput:
  risk_level
  principal_role
  channel
  surface
  session_type
  enable_external_read
  enable_local_write
  enable_external_write
  approval_capable
```

## 推荐演进路线

本文不决定 `v1.6` 具体做什么，但给出长期路线。

### v1.6 候选

优先讨论以下方向之一：

```text
MainAgent 多步只读诊断：
  让 /agent 能只读地组合多个诊断工具。
  不做自动写操作。
  可先不用官方 checkpoint。

MainAgent 任务协作：
  让 /agent 更擅长记录任务、追踪状态、询问澄清问题。
  开始为跨消息状态做准备。

Runtime service 解耦：
  把 QQ handler 里的核心运行逻辑拆成 service。
  为 Web / Desktop adapter 铺路。
```

不建议 `v1.6` 一次性做：

```text
完整 Web。
完整桌宠。
全量迁官方 LangGraph。
合并 MainAgent 和 ChatAgent。
统一所有 RAG。
多步写操作自动执行。
```

### v1.7 候选

```text
Multi-surface Runtime 基础。
抽象 InboundEvent / ResponseEnvelope / ChannelAdapter。
QQ adapter 先迁到新接口，但行为不变。
```

### v1.8 候选

```text
Web Owner Console。
先做诊断、任务、审批、观测。
不做公开聊天。
```

### v1.9 候选

```text
Web Chat 或 Desktop Pet prototype 二选一。
```

### v2.0 候选

```text
多端正式化。
QQ / Web / Desktop 共用核心 Runtime。
官方 LangGraph 局部用于多步任务、checkpoint、interrupt/resume。
```

## 何时引入官方 LangGraph

当出现以下需求时，可以认真考虑局部引入官方 LangGraph：

```text
/agent 可以执行 3 步以上的只读排障流程。
/agent 会在中间向主人提问，等待回复后继续。
审批确认后不只是执行一个工具，而是继续后续计划。
任务可能跨越多条 QQ / Web / Desktop 消息。
任务可能跨越 bot 重启。
同一任务有多个 tool_call，需要防重复执行。
用户需要查询“任务执行到第几步”。
```

引入方式应是局部的：

```text
先在 MainAgent 多步只读诊断试点。
再在任务协作图试点。
最后才考虑审批后连续执行。
```

不建议一开始就把 RootGraph / ChatGraph / MainAgentGraph 全量迁官方 LangGraph。

## 何时深化 LangChain

可逐步推进：

```text
1. MainAgent action planner 使用 structured output。
2. tool summary 使用 Runnable chain。
3. ToolRegistry 生成 LangChain tool schema。
4. LLM 调用接本地 callback/tracing。
5. RAG retriever 层逐步兼容 LangChain 接口。
```

仍要坚持：

```text
LangChain 可以负责表达工具。
ToolRegistry 才负责承认工具。
PolicyEngine 才负责允许工具。
Approval 才负责恢复写工具。
```

## 核心设计原则

后续开发应遵守以下原则：

```text
1. 扩展入口，不扩散权限。
2. 统一底层，不统一业务边界。
3. MainAgent 和 ChatAgent 保持分离。
4. MemoryRAG 和 ProjectDocRAG 保持 scope 分离。
5. LLM 只提出请求，代码决定是否执行。
6. 写操作必须审批。
7. 普通聊天不触发主人管理工具。
8. ProjectDocRAG 不进入普通聊天。
9. 观测信息不输出用户正文、图片 URL、图片描述正文或记忆正文。
10. 官方框架是增强工具，不是安全边界替代品。
```

## 下一步建议

在决定 `v1.6` 前，建议先围绕三个问题继续讨论：

```text
1. v1.6 更想增强 MainAgent 任务能力，还是先做 Runtime service 解耦？

2. 是否先做一个只读多步诊断 Agent，作为未来 checkpoint / official LangGraph 的试点？

3. 多端方向优先级是 Web Owner Console，还是 Desktop Pet prototype？
```

当前最稳的选择是：

```text
短期：
  不迁官方 LangGraph。
  不合并 Agent。
  不统一 RAG scope。
  保持 v1.5 稳定。

中期：
  把 QQ adapter 和核心 Runtime service 拆清楚。
  增强 MainAgent 的只读多步诊断或任务协作能力。

长期：
  在确实需要 checkpoint / interrupt / resume 的子图上局部引入官方 LangGraph。
  在模型、结构化输出、tool schema 和 tracing 上逐步深化 LangChain。
  将 QQ 扩展为个人 AI Runtime 的第一个入口，而不是唯一入口。
```
