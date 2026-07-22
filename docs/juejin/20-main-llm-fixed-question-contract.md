# 一次无工具、无重试的固定问答：我如何验证 Main LLM 基础可用性

标签建议：`AI Agent`、`LLM`、`Python`、`系统设计`、`可观测性`

## 开头

给 Owner Console 加完 ProjectDocRAG 固定检索和 MemoryRAG 一致性检查后，我准备验证下一条基础依赖：

```text
Main LLM 当前能不能正常运行并回答问题？
```

这句话听起来很简单，但在 Agent 系统里，“调用 Main LLM”通常已经和很多东西绑在一起：

```text
对话历史
工具定义
Action Planner
状态图
审批
可靠性事件
自动重试
RAG
```

如果直接从现有 MainAgent 入口发一个问题，我得到的将不是单纯的模型可用性证据，而是一整条 Agent 链路的混合结果。

所以我为 Owner Console 做了一个非常窄的固定问答合同：

```text
后端固定输入。
只调用一次 Main LLM。
不发送工具定义。
不进入 MainAgent。
不读聊天和 RAG。
不写任何业务数据。
```

更重要的是，这个诊断只回答“能否正常运行和回答固定问题”，不试图通过一次调用评价模型面对任意问题时应该选择什么工具。

## 为什么不能直接复用 MainAgent 调用入口

现有 MainAgent 的 Main LLM 入口是为 Action Planner 服务的。

它的职责不是普通问答，而是根据状态和工具合同决定下一步：

```text
ask_owner
tool_request
final_answer
```

审计后，我发现直接复用会引入几个不属于基础合同测试的变量。

第一，生产入口会注入可见工具定义。

即使最终没有执行工具，只要模型看到了 tools，本次响应就已经不能证明“无工具固定问答”是否正常。

第二，生产入口会创建 MainAgentState，并进入 Graph、Policy 和后续状态处理。

第三，生产链挂有 reliability observer，调用结果可能写入结构化事件。

第四，现有客户端构造没有为这个用途显式关闭 SDK 自动重试；在当时依赖版本下，默认值并不是零。

第五，如果复用 Agent 入口，测试结果会混合模型响应、路由判断、工具选择、状态转换和结果格式化，失败时很难知道是哪一层出问题。

因此我没有给 MainAgent 增加一个 `diagnostic=true` 分支，而是写了专属执行器。

## 第一阶段目标必须足够窄

最初讨论 Main LLM 诊断时，很容易想到一个更大的目标：

```text
给它很多问题，看看会不会选择正确工具。
```

但这不适合一次固定诊断。

任意问题的工具选择至少取决于：

```text
工具目录
工具描述
系统提示
上下文状态
风险政策
参数完整性
是否应该 ask_owner
```

几个样本即使通过，也不能证明开放域路由可靠；一个样本失败，也不能直接归因于模型基础不可用。

所以第一阶段只判断：

```text
配置能否创建客户端。
一次固定调用能否在超时内完成。
模型是否返回非空回答。
token usage 是否可获得。
响应是否满足一个简单、可机器验证的 JSON 子合同。
```

工具选择能力留给单独的 planner eval、用例集和风险路由测试，不让它污染基础连通性结论。

## 固定问题为什么同时包含 marker 和算术

后端固定问题要求模型处理一个合成 marker，并计算：

```text
marker: amber-17
17 + 25
```

期望的唯一结果是五字段 JSON：

```json
{
  "contract_version": "main_llm.fixed.v1",
  "probe_id": "p2_49c",
  "marker": "amber-17",
  "sum": 42,
  "status": "ok"
}
```

这个问题故意很简单。

它不测试知识，也不依赖当前日期、互联网、项目文档或私人记忆。marker 能验证模型处理了本次固定输入，算术能验证它不是只返回一个完全静态的状态字符串，五字段对象则提供最小结构合同。

服务端允许字段重排，但不允许：

```text
字段缺失
额外字段
重复 key
错误类型
错误值
Markdown code fence
JSON 后追加解释正文
tool_calls
invalid_tool_calls
```

这是一条刻意严格的结构兼容性检查。

但它只是整个诊断中的一个子结论，不应该吞掉“模型已经正常响应”这个更基础的事实。

## 专属客户端必须把预算写死

执行器不接受前端参数，也不复用自由配置表单。客户端构造固定为：

```text
max_retries=0
streaming=false
timeout=30 秒
max completion tokens=256
```

本地还增加两条限制：

```text
15 秒延迟关注阈值
1024 字符原始响应上限
```

执行器只调用一次同步 `invoke`。

这里有一个措辞边界很重要：

```text
attempt_count=1
```

证明的是 Owner Console 执行器只发起了一次客户端调用；`client_automatic_retry=false` 证明当前客户端禁用了自动重试。它不能凭空证明更上游的网关或服务商内部绝对没有透明重试。

诊断证据应该描述自己真正能够观察到的边界，不要把一个布尔值写成全链路保证。

## 不发送 tools，比“模型没有调用工具”更重要

如果请求里发送了工具定义，而模型恰好没有选择工具，只能得到：

```text
tool_calls_present=false
```

但我还想证明更强的一条事实：

```text
tool_definitions_sent=false
```

因此专属执行器根本不调用 `bind_tools`，也不构造 ToolRegistry。

整条路径不创建 `MainAgentState`，不进入：

```text
MainAgentGraph
Action Planner
Policy
approval
tool execution
```

同时固定关闭或绕开：

```text
MemoryRAG
ProjectDocRAG
DevContext
CombinedRAG
Tavily
TTS
vision
QQ write
```

这意味着它不能回答“模型会不会为某类问题选对工具”，但能更干净地回答“这次基础问答调用是否工作”。

## 原始回答不应该出现在页面和日志里

为了校验 JSON，后端必须短暂拿到完整响应。

但“校验时需要”不等于“应该展示或持久化”。

原始 prompt、回答正文和异常细节只在执行器局部内存中存在。运行结束后，页面只能看到有限结果：

```text
配置模型名
延迟
输入 token
输出 token
总 token
usage metadata 是否可用
回答合同是否通过
workflow / stage / code
安全边界布尔值
```

它不会返回或记录：

```text
固定 prompt 全文
原始回答正文
异常原文
API Key
Base URL
聊天历史
```

如果回答超过 1024 字符，执行器也不会截一段出来继续猜合同，而是 fail closed。

## 基础响应和严格合同必须给出两个结论

我为结果设计了三种 outcome：

```text
succeeded
  模型完成回答，延迟正常，严格 JSON 合同通过。

attention
  模型完成回答，但结构合同、token metadata 或延迟需要关注。

failed
  客户端无法创建，鉴权、连接、限流、超时或调用本身失败。
```

错误还会映射到固定 `stage/code`，例如：

```text
configuration
client_initialization
llm_invocation
result_validation
```

异常原文不会穿透到 DTO。这样页面可以解释发生在哪一层，同时避免把服务 URL、请求细节或上游返回全文带到浏览器。

其中最关键的一个 code 是：

```text
workflow=main_llm_fixed_contract
stage=result_validation
code=main_llm_contract_mismatch
```

它表示调用已经完成，但严格五字段结构没有精确匹配。

这和“Main LLM 完全不可用”不是一回事。

## 真实 live：基础运行成功，JSON 子合同需要关注

自动化阶段全部使用 fake LLM，没有提前调用真实模型。

代码、HTTP 合同、二次确认页面和安全边界完成后，由主人在真实 Owner Console 页面手动执行了一次固定问答。

页面结果是：

```text
run_id=1
attempt_count=1
configured_model=gpt-5.5
elapsed_ms=8146
input_tokens=74
output_tokens=126
total_tokens=200
llm_called=true
contract_valid=false
tool_calls_present=false
client_automatic_retry=false
tool_definitions_sent=false
database_write_allowed=false
```

最终状态为：

```text
outcome=attention
stage=result_validation
code=main_llm_contract_mismatch
```

如果只看严格合同，这是一次未通过。

但按第一阶段目标，它已经证明：

```text
Main LLM 客户端能够正常创建。
模型完成了一次真实回答。
8.146 秒低于 15 秒关注阈值。
token usage 完整返回。
客户端没有自动重试。
没有工具定义和工具调用。
```

所以主人确认“成功了”，项目结论也收敛为：

```text
Main LLM 基础运行 live 通过。
严格 JSON 子合同 attention。
```

这两个结论可以同时成立。

## 为什么不能继续猜 JSON 到底哪里错了

页面没有展示原始回答，后端也没有持久化它。执行结束后，原始内容已经丢弃。

因此我不能事后声称：

```text
一定是加了 Markdown fence。
一定是多了说明文字。
一定是字段类型不对。
```

这些都只是可能性，不是当前证据。

如果未来严格 JSON 兼容性本身变成重要目标，正确做法应该是单独设计一个更窄的可观测方案，例如只返回安全的 mismatch category，而不是为了方便排查就把完整模型回答长期保存。

这次没有自动补跑第二次，也没有修改校验器把真实结果“调成通过”。`attention` 被保留下来，作为当前模型与固定结构合同之间的真实兼容性证据。

## 页面仍然沿用手动诊断边界

Main LLM 固定问答不是一个孤立按钮，它复用了前两个工作流的动作框架：

```text
独立启动开关
同源 Origin
进程内 HttpOnly / SameSite=Strict 动作 Cookie
固定 Header
固定 confirmation
前端二次确认
精确 POST allowlist
进程内最近结果
共享全局运行锁
```

因此它不能和 ProjectDocRAG 或 MemoryRAG 手动工作流并发，也不会排队或在结束后触发下一项诊断。

自动化则验证了：

```text
专属客户端最终收到 max_retries=0。
没有 tools 参数。
执行器只 invoke 一次。
错误请求 fail closed。
页面一次确认只发送一个 POST。
原始 prompt 和响应不进入 HTTP DTO。
聊天、任务、审批、可靠性事件和业务数据库没有写入。
```

## 一次固定问答能证明什么，不能证明什么

它能够证明：

```text
当前配置下，Main LLM 基础调用链可达。
一次后端固定问题得到了回答。
客户端侧单次、无工具、无流式、无自动重试合同生效。
延迟和 token usage 可以被有限观测。
响应能否满足指定 JSON 子合同。
```

它不能证明：

```text
模型对任意问题都回答正确。
模型一定会为任意任务选择正确工具。
MainAgent Graph、Policy 和审批链完整可用。
RAG、Tavily、TTS、视觉或 QQ 链路可用。
上游服务内部绝无透明重试。
长期稳定性和并发容量已经验证。
```

一个诊断越清楚地写出“不能证明什么”，结果就越不容易被误用。

## 最后

这次实现最有价值的地方，不是成功调用了一次模型，而是把一个混合问题拆成了几个独立事实：

```text
模型有没有响应？
客户端有没有自动重试？
有没有发送工具定义？
有没有执行工具？
延迟是否需要关注？
token usage 是否存在？
严格 JSON 是否匹配？
有没有产生业务副作用？
```

真实结果并不完美：五字段 JSON 没有通过。

但系统没有因此把整次调用说成失败，也没有为了得到绿色状态自动再问一次、放宽合同或隐藏证据。

我最终保留的原则是：

```text
基础连通性和结构兼容性分开判断。
固定诊断只回答固定问题。
工具选择能力需要独立评测，不能靠一个样本下结论。
无工具要从请求入口保证，不只看最终 tool_calls。
没有证据时不猜原始响应。
attention 是有效结果，不是必须被自动修成 succeeded 的异常。
```

对于长期运行的 Agent 系统，这种诚实而有限的诊断，比一个什么都想证明的“万能测试按钮”更有用。
