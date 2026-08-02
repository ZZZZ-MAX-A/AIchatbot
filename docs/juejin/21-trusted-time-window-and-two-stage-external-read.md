# “最近一个月”为什么搜到半年前：我如何给 MainAgent 加可信时间窗口和两阶段外部检索

标签建议：`AI Agent`、`RAG`、`Python`、`搜索`、`Agent 安全`

## 开头

我给 QQ AI Chatbot 的 MainAgent 接入外部只读查询后，第一版链路看起来已经很完整：

```text
主人显式输入 /agent
MainAgent 判断是否需要 external_read
Tavily Advanced 搜索
清洗公开证据
隔离 Main LLM 综合
附加编号引用
主人接受或拒绝结果
```

它还有很严格的边界：

```text
固定 provider
固定 max_results
不打开任意网页
不调用工具进行二次调查
不自动重试
不切换 fallback provider
不写入 RAG、记忆或聊天历史
```

但一次真实问题很快暴露了关键缺陷：

```text
帮我查询当前日期往前一个月有哪些重要的大模型或多模态模型发布，
优先使用模型发布方官方网站、官方博客或官方公告，并注明发布日期。
```

运行环境日期是 2026-07-28，所以目标范围应该是：

```text
2026-06-28 至 2026-07-28
```

旧回答却使用了 2026 年 1 月和 2 月的证据。

这不是一句“请注意当前日期”能够修好的 Prompt 小问题，而是一整条时间约束没有成为执行合同。

后来我又遇到第二个问题：时间过滤修好以后，搜索返回 5 个候选，却全部因为日期证据不足被拒绝；继续改进日期解析后，系统能够召回 Reuters、AP、Business Insider 等媒体报道，但发布方官方页面仍然是 0。

最终这条链路被拆成三个独立问题：

```text
相对时间怎样变成可信绝对窗口？
哪些日期证据真的有资格进入回答？
官方来源和媒体来源怎样分阶段召回？
```

这一篇记录完整的修复过程。

## 时间注入为什么会被忽略

最初很容易把问题理解成：

```text
MainAgent 不知道今天是哪一天。
```

这确实是原因之一，但不是全部。

即使在 Prompt 里加入：

```text
当前日期：2026-07-28
```

仍然不能保证后续链路遵守它。因为旧执行过程实际是：

```text
主人原问题
  -> MainAgent 自己重述工具 query
  -> 搜索器从重述后的 query 猜时间
  -> Tavily 没有收到 start_date / end_date
  -> 本地只做排序和时效提示
  -> 范围外结果仍可进入综合模型
```

这里至少有四个断点：

```text
模型可能把“最近一个月”改写丢失。
搜索请求可能没有结构化时间参数。
provider 返回的候选不一定真的位于时间范围内。
综合模型可能根据旧证据给出一篇看起来合理的答案。
```

因此真正的目标不能只是“让模型知道今天”，而应该是：

> 时间窗口必须由本地可信代码计算，并作为结构化对象贯穿规划、搜索、过滤和综合。

## 用本地时区计算可信窗口

我增加了一个本地时间对象：

```python
@dataclass(frozen=True)
class ExternalReadTimeWindow:
    start_date: date
    end_date: date
    kind: str
```

相对时间使用 Bot 配置时区对应的本地日期计算，不让 LLM 自己推算。

例如：

```text
reference_date = 2026-07-28
当前日期往前一个月
  -> 2026-06-28 至 2026-07-28
```

月末需要额外处理：

```text
2026-03-31 往前一个月
  -> 2026-02-28 至 2026-03-31
```

不能简单减 30 天，也不能直接把月份减一后保留不存在的 31 日。

第一版支持的明确表达包括：

```text
最近一个月
最近一周
本月
本周
今天
YYYY-MM-DD 至 YYYY-MM-DD
```

而只有：

```text
最近有什么模型发布
近期有什么政策变化
recently released models
```

这类没有明确周期的表达会要求主人澄清，不猜“一周、一个月还是一年”。

## 同时保留规划文本和搜索问题

时间正规化以后，我没有只保存一个字符串，而是拆成：

```python
@dataclass(frozen=True)
class ExternalReadTemporalQuery:
    query: str
    time_window: ExternalReadTimeWindow | None
    search_question: str
```

它们的职责不同。

`query` 给 MainAgent 和综合模型看，包含完整约束：

```text
查询 2026-06-28 至 2026-07-28 的重要模型发布；
限定发布日期：2026-06-28 至 2026-07-28；
优先官方网站、官方博客和官方公告。
```

`search_question` 则保留来源中立的核心问题：

```text
查询 2026-06-28 至 2026-07-28 的重要模型发布
```

后面官方阶段和媒体阶段都基于同一个 `search_question`，只追加本地固定的来源条款。

这个拆分避免了一个常见问题：第一阶段搜索结果不理想后，再把网页正文交给 LLM 生成第二条 query。那样会让不可信网页内容参与搜索控制面，还会让两次请求之间的差异无法审计。

## MainAgent 只能决定“是否搜索”

时间对象在进入 MainAgent 之前就已经生成。

```text
主人原始 /agent 问题
  -> 本地计算 ExternalReadTemporalQuery
  -> MainAgent 看绝对日期文本
  -> MainAgent 决定是否调用 external_read
  -> executor 通过闭包拿到原始可信 time_window
```

即使 MainAgent 生成的工具参数变成：

```text
查询近期模型发布
```

executor 仍然使用最开始冻结的：

```text
start_date=2026-06-28
end_date=2026-07-28
```

模型不能通过重述、遗漏或改写取消时间窗口。

这里还保留了一条非常重要的入口边界：

```text
普通聊天只走原 ChatGraph。
普通聊天不调用 MainAgent。
普通聊天不判断是否联网。
普通聊天不触发 external_read 或 Tavily。

只有显式 /agent 才进入 MainAgent。
```

“MainAgent 可以自主选择 external_read”只表示它在显式 `/agent` 内拥有选择权，不等于可以把 MainAgent 注入所有日常聊天。

## 搜索参数不是最终时间证据

有了可信窗口以后，Tavily 请求可以带上：

```json
{
  "search_depth": "advanced",
  "max_results": 5,
  "start_date": "2026-06-28",
  "end_date": "2026-07-28"
}
```

但 provider 的时间参数只能提高召回相关性，不能代替本地验证。

搜索结果仍可能出现：

```text
发布日期缺失
发布日期在窗口外
标题出现一个日期，正文又出现多个日期
正文只有孤立日期，无法证明是发布时间
provider metadata 与正文日期冲突
聚合页或转载页把历史内容重新发布
```

所以结果返回后必须再次执行本地硬过滤。

## 把日期证据分成强、弱和不合格

当前实现区分三类日期证据。

第一类是 provider metadata：

```text
published_date=2026-07-12
```

它是强日期，但仍必须位于可信窗口内。

第二类是受限官方正文强日期：

```text
来源属于固定、已审查的官方域名
标题或摘要包含 release / launch / 发布 / 上线等明确语义
标题、摘要和受限正文合计只有一个完整日期
日期位于可信窗口内
```

这类结果允许在 provider 没有 `published_date` 时建立强锚点。

第三类是正文弱日期：

```text
第三方正文中出现唯一完整日期，
但无法仅凭这一点证明它就是目标事件的正式发布日期。
```

弱日期不能独立建立完整答案，只能在已经存在强日期证据时作为补充。

本地日期解析支持完整、无歧义的格式：

```text
2026-07-12
2026/7/12
2026年7月12日
July 12, 2026
12 July 2026
RFC 或 ISO 日期时间中的完整日期
```

继续拒绝：

```text
只有月份
只有月和日但没有年份
“上周”“近日”等相对正文日期
非法日期
多个互相冲突的完整日期
```

## 没有证据时，停止也是正确答案

第一次严格过滤 live 返回了：

```text
provider_candidate_count=5
result_count=0
dropped_result_count=5
synthesis_request_count=0
synthesis_status=not_run_no_evidence
```

它看起来像“什么也没找到”，但从安全合同看，这次结果是正确的：

```text
没有把旧内容混进答案。
没有用无可靠日期的内容凑数量。
没有调用综合模型猜测。
没有扩大时间窗口。
没有自动重新搜索。
```

系统明确回复：

```text
无法确认指定时间范围内的完整答案。
```

在时效问题里，一篇内容丰富但时间错误的回答，比一篇诚实的“证据不足”更糟。

## 只记录安全计数，不保存搜索正文

为了知道 5 条结果为什么全被拒绝，我没有把 query、标题、摘要、URL 或 raw content 写进任务数据库，而是增加互斥整数：

```text
provider_candidate_count
dropped_missing_date_count
dropped_outside_window_count
dropped_weak_only_count
dropped_conflicting_date_count
dropped_injection_count
dropped_sanitization_count
```

正式 sanitizer 强制：

```text
provider_candidate_count
  = result_count + dropped_result_count

所有丢弃原因之和
  = dropped_result_count
```

后续一次任务显示：

```text
候选 5
日期缺失丢弃 4
仅弱日期丢弃 1
窗口外丢弃 0
冲突、注入、清洗丢弃都是 0
```

这组安全整数直接证明问题不在时间窗口过窄，而在日期格式识别和弱证据规则。它使下一次修复有了明确方向，又没有扩大搜索内容的持久化范围。

## 为什么“优先官方”仍然搜到媒体

日期解析放宽以后，系统成功保留了 Business Insider、AP 和 Reuters 的窗口内报道，但官方来源仍为 0。

原因并不神秘：

```text
topic=news 天然偏向新闻媒体。
“优先官方网站”只是 query 文本，不是 provider 的强制来源过滤器。
官方博客和官方文档未必使用新闻页面常见的发布时间 metadata。
发布方页面标题也未必包含“发布”二字。
```

换句话说，一次搜索同时承担：

```text
召回官方原始资料
召回媒体补充报道
```

会让来源目标互相竞争。

## 两阶段搜索：问题不变，只改变来源通道

最终实现采用本地固定的两阶段搜索。

阶段 1：官方来源阶段。

```text
同一主人问题
同一 start_date / end_date
topic=general
固定追加第一方、官方网站、官方博客、官方公告、官方文档要求
本地只接受已识别的官方 host
```

如果阶段 1 找到合格官方证据，立即停止：

```text
Tavily 请求 = 1
媒体阶段 = 0
综合请求最多 = 1
```

只有阶段 1 请求成功、但官方合格结果为 0 时，才进入阶段 2：

```text
同一主人问题
同一 start_date / end_date
topic=news
固定追加可靠独立媒体或专业公开资料要求
明确不得把第三方报道表述为官方确认
```

两次 query 的核心问题完全相同：

```text
问题没有换。
时间窗口没有换。
provider 没有换。
max_results 没有换。
只有 topic 和来源条款改变。
```

所以这里不需要为“模型发布、政策、软件版本、公司公告”分别维护一套业务模板。

模板只描述来源角色：

```text
official
media_fallback
```

用户问什么，核心问题就是什么；时间窗口存在时继续使用本地计算出的绝对日期。

## 第二阶段为什么不由 MainAgent 来写

如果让 MainAgent 根据第一阶段结果生成第二条搜索词，会出现几个问题：

```text
第一阶段网页内容可能通过模型影响第二阶段控制面。
两次 query 无法证明只改变了来源策略。
模型可能扩大时间窗口或改变问题目标。
不同问题会产生不可预测的动态模板。
失败很难判断来自召回、改写还是策略漂移。
```

所以阶段 query 由本地纯函数生成：

```python
build_external_read_stage_query(
    search_question,
    time_window=trusted_window,
    stage="official",
)

build_external_read_stage_query(
    search_question,
    time_window=trusted_window,
    stage="media_fallback",
)
```

MainAgent 仍然有自主性，但自主性的范围是：

```text
这个显式 /agent 问题是否需要 external_read？
```

它没有被授权决定：

```text
是否重试
是否切换 provider
是否扩大时间窗口
第二阶段怎样改写 query
哪些来源可以绕过本地过滤
```

## 两阶段不是自动重试

这一点必须单独强调。

当前触发第二阶段的唯一条件是：

```text
阶段 1 请求成功
并且官方合格结果为 0
```

如果阶段 1 出现：

```text
超时
认证失败
连接失败
provider 不可用
非法响应
```

任务会直接失败：

```text
阶段 2 不执行
综合模型不调用
provider 不切换
请求不自动重发
```

这意味着两阶段设计解决的是“来源召回结构”，不是“网络可靠性”。

如果以后要允许官方阶段超时后继续媒体阶段，那是新的失败策略：它可能提高可用性，也可能掩盖 provider 故障和增加请求成本，必须单独审批、测试和记录，不能把它偷偷当成普通修复。

## 让最终回答说清楚证据来自哪个阶段

每条临时证据增加阶段标签：

```text
official
media_fallback
```

隔离综合 Prompt 明确要求：

```text
media_fallback 证据必须表述为独立报道或媒体补充，
不能自动表述为发布方官方确认。
```

如果执行了两阶段，最终回复会显示：

```text
检索路径：官方来源阶段无合格证据，已执行可靠媒体补充阶段。
媒体补充证据不能自动视为发布方官方确认。
```

边界计数也根据真实路径生成：

```text
边界：Tavily 1 次、隔离综合最多 1 次……
```

或者：

```text
边界：Tavily 2 次、隔离综合最多 1 次……
```

不能明明发送了两次请求，回复里还沿用旧文案说“Tavily 1 次”。可观测性本身也是执行合同的一部分。

## 任务摘要和 Owner Console 怎样展示两阶段

任务数据库仍然不保存搜索正文，只增加安全整数：

```text
search_stage_count
official_stage_candidate_count
official_stage_result_count
media_stage_candidate_count
media_stage_result_count
dropped_source_policy_count
```

一阶段成功时必须满足：

```text
search_stage_count = 1
official_result_count = final_result_count
media_candidate_count = 0
media_result_count = 0
```

两阶段时必须满足：

```text
search_stage_count = 2
official_result_count = 0
media_result_count = final_result_count
official_candidate_count + media_candidate_count
  = provider_candidate_count
```

Owner Console 页面显示这些数字，但不显示：

```text
主人 query
标题和摘要
raw content
来源 URL
host 明细
provider endpoint
API Key
原始异常正文
```

旧任务没有新字段时显示“未知”，不会尝试从旧结果正文恢复隐私内容。

## 官方域名识别仍然是保守边界

官方阶段还有一个必须诚实说明的限制：

```text
本地只能确认已登记、已审查的官方域名。
```

一个新机构或冷门项目的官网即使被搜索到，如果不在保守识别范围内，也可能被官方阶段拒绝，然后进入媒体补充阶段。

不能只因为标题里写着“Official”就相信它，也不能让 LLM 根据网页自我声明动态扩充官方白名单。

后续如果要提高官方召回率，更合理的路线是：

```text
按明确主题审查并扩展官方域名映射。
为政府域名、标准组织和已验证发布方建立独立来源类别。
继续使用真实子域名判断，拒绝 openai.com.evil.example 之类后缀欺骗。
```

这属于来源身份治理，不应该通过放宽整个 official 判定来解决。

## fake-only 测试怎样证明分支没有串

这轮没有在开发过程中自动调用真实 Tavily 或 Main LLM，而是使用响应队列模拟 transport。

官方命中测试：

```text
第 1 个响应：openai.com 窗口内有效结果

断言：
transport calls = 1
topic = general 默认路径
官方合格结果 = 1
媒体候选 = 0
综合调用 = 1
```

官方为 0、媒体补充测试：

```text
第 1 个响应：非官方结果
第 2 个响应：Reuters 窗口内报道

断言：
transport calls = 2
两次 start_date / end_date 完全相同
两次 query 保留同一核心问题
第 1 次使用官方来源条款
第 2 次 topic=news 且使用媒体来源条款
第 2 次 query 不含第 1 次网页标题或正文
综合总计 = 1
最终回复显示媒体补充声明
```

第一阶段超时测试：

```text
第 1 个响应：TimeoutError

断言：
transport calls = 1
没有第 2 阶段
综合调用 = 0
任务按安全错误分类失败
```

最终完整回归结果为：

```text
Python 785 tests OK，skipped=4
Owner Console frontend 33 tests OK
TypeScript typecheck 通过
Vite production build 通过
Owner Console readonly guard 通过
Python AST 通过
git diff --check 通过
```

## 最后

这次修复最重要的变化，不是把 Prompt 里的“优先官方”写得更强，而是把自然语言偏好拆成了可验证的本地合同：

```text
相对时间由可信本地日期计算。
时间窗口作为结构化对象贯穿执行链。
MainAgent 重述不能取消窗口。
provider 时间参数之后仍做本地硬过滤。
日期证据分成 provider、官方正文强证据和正文弱证据。
没有合格证据时不调用综合模型。
官方召回和媒体补充分成两个固定阶段。
第二阶段只改变来源通道，不改变问题和时间。
来源阶段和网络重试是两种不同概念。
任务只保存安全计数，不持久化搜索正文。
普通聊天永远不因这项能力进入 MainAgent。
```

对有时间要求的外部查询来说，真正危险的通常不是模型明确说“我不知道”，而是它拿着过期证据生成一篇结构完整、语气自信的回答。

所以我最终保留的原则是：

> 搜索可以不完整，证据可以不足，系统也可以停止；但时间窗口、来源身份和请求次数不能靠模型临场猜测。

## 2026-07-30 后记：固定两阶段为什么又被动态规划取代

后续真实任务 #65/#66 证明，关闭 raw content 解决了响应超限，却没有解决搜索意图质量。固定“先官方、官方为零再查媒体”适合模型发布等第一方事实，但不适合“萍乡热门的小吃有哪些”这类本地生活问题；它也不能自动把“原神下一个版本的角色”拆成当前版本、下一版本、前瞻和角色事实。

因此当前主路径已经调整为：MainAgent 在显式 `/agent` 内先理解问题，再生成最多两条、每条不超过 50 字的搜索词，并为每条选择 `official|general|news`。第二条只有在确有互补价值时才存在，执行条件预先固定为 `if_no_results` 或 `always`；没有第二条计划时，第一条没有结果也不会机械补查。

这不是放弃安全合同。可信时间窗口仍由结构化对象强制执行；实际查询长度和数量在本地硬校验；provider 仍固定为 Tavily，最多两次读取、零自动重试、零 fallback、最多一次隔离综合；普通聊天仍不进入 MainAgent。变化只是把“该查什么、该查哪类来源、是否需要第二个子问题”从僵硬的全局规则交还给受约束的 MainAgent 理解能力。
