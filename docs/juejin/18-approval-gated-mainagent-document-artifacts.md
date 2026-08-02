# 让 MainAgent 生成 Word、PPT 和 TXT：从只读 Agent 到审批门控文档交付

标签建议：`AI Agent`、`LangGraph`、`Python`、`PowerPoint`、`Agent 安全`

## 开头

之前我给 QQ AI Chatbot 的 MainAgent 做过很多只读能力：

```text
查询研发上下文
查看当前配置
系统分区诊断
查看任务和审批
查看 MemoryRAG、视觉和语音状态
```

这些能力很安全，但用久以后会遇到一个很现实的问题：

```text
Agent 能不能真正产出一份文件？
```

比如：

```text
/agent 帮我写一份 TXT：整理今晚测试结果
/agent 生成一份 Word 并发给我：总结当前开发进度
/agent 生成一份 PPT 并发给我：介绍当前能力和下一步规划
```

我不希望因为开放文档生成，就顺手给 MainAgent 开放整个项目目录、任意文件路径或者 shell。最终目标被收敛成：

```text
只允许创建新的 TXT、DOCX、PPTX artifact。
只写固定 Git 忽略工作区。
不接受 path 和自定义文件名。
不覆盖已有文件。
必须经过审批。
“本地生成”和“生成后通过 QQ 发送”是两种不同权限。
```

真正实现以后，又连续遇到了几个很典型的 Agent 工程问题：

```text
工具已经注册，但 Main LLM 看不见。
运行时 metadata 被模型写进 Word 正文。
文档提纲里的“下一步”误触发任务查询。
生成审批要二十多秒，后发消息反而先回复。
PPT 审批通过后才发现页数超限。
PPT 虽然能打开，但视觉质量像一份纯白提纲。
TXT 没写“发给我”时，为什么只生成本地文件？
审批恢复失败为什么只返回一串内部错误码？
```

这一篇记录我如何把这条链路从“能写文件”推进到“可审批、可交付、可诊断、可验证”。

## 先定边界：Agent 不是项目文件编辑器

MainAgent 的文档能力不是：

```text
给它一个路径，让它自由写文件。
```

它只能调用三个本地产物命令：

```text
create_txt_document
create_word_document
create_presentation
```

输入只有：

```text
command
query
title
content
```

没有：

```text
path
filename
working_directory
overwrite
shell_command
receiver_qq
group_id
```

产物目录固定为：

```text
output/main-agent-workspace/
```

文件名由本地代码生成：

```text
artifact_<UTC时间>_<随机后缀>.txt
artifact_<UTC时间>_<随机后缀>.docx
artifact_<UTC时间>_<随机后缀>.pptx
```

这个设计牺牲了一点自由度，但把路径穿越、覆盖项目源码、写入配置和文件名注入从能力层直接拿掉了。

## 本地生成和 QQ 发送为什么要分成两个工具

最开始只有本地写工具：

```text
owner_write_command
risk=write_local
```

后来增加“生成并发给我”，我没有修改原工具的语义，而是新增：

```text
document_delivery_command
risk=write_external
```

两组命令分别是：

```text
本地生成：
create_txt_document
create_word_document
create_presentation

生成并发送：
create_and_send_txt_document
create_and_send_word_document
create_and_send_presentation
```

于是自然语言也有明确区别：

```text
/agent 生成一份 TXT：整理测试结果
  -> 只生成本地文件

/agent 生成一份 TXT 并发给我：整理测试结果
  -> 审批后生成，并向当前主人私聊发送一次
```

如果用户没有说“发给我”，系统不会擅自把本地文件变成外部发送。这不是路由缺陷，而是权限合同。

更重要的是，增加外部发送以后，旧审批不会追溯扩权：

```text
以前批准的是 write_local。
以后即使系统增加了 write_external 工具，旧审批也只能执行当时冻结的本地命令。
```

## 审批顺序：模型先准备内容，确认后才创建文件

这条链路最终保留的审批语义是：

```text
Main LLM 生成可审查的 title/content
  -> ToolPolicyCheck
  -> 创建审批
  -> 主人确认
  -> 生成 TXT/DOCX/PPTX
  -> 完整性复核
  -> 如有外部发送授权，则通过 QQ 单次发送
```

需要特别区分两件事：

```text
审批前生成“内容提案”。
审批后生成“真实文件”。
```

如果审批发生在 Main LLM 之前，主人只能看到“准备生成一份 PPT”，却看不到模型实际准备的标题和正文，审批信息量太低。

如果文件在审批前就生成，写操作又提前发生了。

所以当前折中是：

```text
模型可以在审批前准备纯文本内容。
文件系统副作用必须等主人确认。
```

审批确认后也不会重新让模型理解一遍需求，而是执行审批中被冻结的结构化工具输入，避免两次理解产生漂移。

## 文件生成不是 save 一下就结束

三种格式共享一组预算：

```text
title 最多 120 字符
content 最多 20,000 字符
最终文件最多 10 MiB
PPT 最多 20 页
```

TXT 使用 UTF-8 和 LF，写入后重新读取并精确核对正文。

DOCX 和 PPTX 则需要更多检查：

```text
先写临时文件
flush + fsync
ZIP test
检查 OOXML 必需 member
用 python-docx/python-pptx 重新打开
核对标题和内容结构
计算最终字节和 SHA-256
原子替换到唯一新文件
再次读取并核对最终哈希
```

这条链路不接受宏，不允许符号链接逃逸，也不会覆盖已有 artifact。

返回给用户的结果只包含：

```text
artifact ID
相对路径
格式
字节数
正文字符或页数
SHA-256 短哈希
```

## 第一个问题：工具注册了，但 Main LLM 看不见

第一次真实测试 TXT 时，Bot 返回：

```text
当前可用的 visible tool 只有 dev_context，
未注册可调用的 owner_write_command。
```

这很奇怪，因为执行侧 ToolRegistry 里明明已经注册了文档工具。

最后定位到：系统里实际上存在两份 registry 视图。

```text
运行时 runner 使用完整 registry。
Main LLM prompt 却使用默认只读 registry。
```

于是产生了典型的不一致：

```text
执行器有工具。
策略层有工具。
模型看到的工具合同里却没有工具。
```

修复方式不是在 Prompt 里手写工具名，而是生产路径只构造一份完整 registry，同时传给：

```text
Main LLM tool contract
ActionRequest 校验
ToolPolicyCheck
实际工具执行
```

这次问题让我确认了一条很重要的原则：

> 工具可见性、策略判断和执行注册必须来自同一事实源。

否则系统会出现“模型说不能做、运行时其实能做”或者更危险的反向不一致。

## 第二个问题：运行时 metadata 被写进了 Word

工具可见性修好以后，Word 确实生成并通过 QQ 发出来了，但打开文档一看，正文包含：

```text
Read-only project context:
MainAgentGraph read-only local test mode.
Allowed tools: ...
Disallowed: ...
User query: ...
```

也就是说，模型把内部运行时包装当成了用户提供的原始内容。

根因有两个：

第一，旧 context 文案仍然声称系统处于“只读本地测试模式”，和已经注册的文档交付能力矛盾。

第二，runtime metadata 与 owner query 被放在同一条 user message 里，边界表达不够强。

修复分成两层。

Prompt 层明确分区：

```text
Runtime metadata：不属于用户文档内容。
Owner query：唯一用户指令。
禁止把工具列表、安全边界、内部标签和示例复制进 title/content。
```

本地校验层再做兜底：只要 title/content 出现已知内部 scaffold marker，就在审批创建前拒绝。

也就是说，即使模型再次犯错，污染内容也不会进入审批和文件生成。

## “使用我刚才提供的内容”为什么会被拒绝

MainAgent 当前没有把上一条 QQ 消息自动作为文档正文输入。

所以这种请求：

```text
/agent 生成一份 Word 并发给我，正文使用我刚才提供的完整内容
```

会被确定性拒绝，并要求：

```text
把完整内容粘贴在同一条 /agent 请求里，
或者只提供主题，明确让 MainAgent 自行撰写。
```

如果系统假装知道“刚才的内容”，它很可能会把历史、工具结果或 runtime metadata 拼进正文。当前选择是不猜。

## 第三个问题：提纲里的“下一步”抢走了文档请求

后来我用一个完整提纲测试 Word：

```text
生成一份 Word 并发给我，内容包括：
当前阶段、已完成功能、架构状态、测试情况、待办事项、风险限制和推荐下一步。
```

结果 Bot 没有创建文档审批，反而进入了：

```text
Agent 下一步应该做什么？
```

原因是 MainAgent 之前有一组高优先级确定性管理分类：

```text
下一步
任务状态
审批状态
现在卡在哪
```

它们原本用于避免 Main LLM 自由猜测任务控制面，但文档提纲里同样可能出现这些词。

修复不是简单删除关键词，而是增加更高层的对象判断：

```text
如果整句同时包含：
TXT/Word/PPT/文档对象
+ 生成/撰写/制作意图
```

就把它视为明确文档请求，让完整要求进入文档能力 Main LLM，不再被提纲内部的“下一步、任务、审批”抢走。

独立的：

```text
/agent 下一步
```

仍然走任务控制面。这里的关键是判断整句目标，而不是只扫描局部词。

## 第四个问题：二十多秒无回复，后发的“在吗”先返回

文档请求和普通 Agent 问答有一个明显差异：模型需要先生成完整标题和正文，因此首个审批可能要等二十多秒。

这段时间用户看不到任何反馈。如果再发送：

```text
/agent 在吗
```

第二个请求可能先返回“在”，第一个请求随后才出现审批，看起来像消息顺序错乱。

我增加了两层处理。

第一，文档请求取得执行权后立即发送进度回执：

```text
MainAgent 正在生成文档标题、正文和审批请求，请稍候。
```

第二，按 QQ session 增加独立 MainAgent lock。

同一 session 有请求执行时，后续 `/agent` 不排队、不调用 LLM、不执行工具，而是立即返回：

```text
上一条正在处理，当前消息未执行。
```

锁一直持有到最终回复或审批消息交给 adapter，避免“先释放锁、后发送结果”的小竞态窗口。

这个改动没有让模型变快，但修复了可见时序和重复执行风险。

## 第五个问题：PPT 审批通过后才发现页数超限

第一版 PPT 校验只检查正文字符数，但真实渲染规则是：

```text
自动生成 1 张标题页。
每个 ## 章节生成内容页。
每 8 条非空正文自动拆分续页。
总页数最多 20。
```

模型生成的结构看起来没有超过章节数量，但经过自动续页以后超过 20 页。旧链路在审批前没有用真实分页算法计算，所以主人确认以后，恢复执行才失败。

这类失败很伤体验：

```text
系统已经让主人审批。
主人也确认了。
结果执行器才说这个请求从一开始就不可能成功。
```

于是我提取了纯函数：

```python
presentation_slide_count(content)
```

它复用真实 renderer 的章节和续页算法，在 ToolPolicyCheck 和审批创建之前计算最终页数。

超限时直接提示减少章节或每节正文，不创建注定失败的审批。渲染器内部仍保留 20 页硬限制，形成双层保护。

Main LLM 合同也增加约束：

```text
标题页由 renderer 自动创建。
不要额外创建“封面”章节。
建议最多 12 个 ## 内容章节。
每页 3 到 5 条简洁要点。
标题页、内容页和续页总计不能超过 20。
```

## 能生成 PPT，不等于 PPT 质量合格

超页问题修复后，PPTX 成功生成并发送，但第一次打开，视觉质量仍然不理想。

客观问题包括：

```text
纯白背景。
所有页面都是同一个“标题 + 项目符号”布局。
封面、页标题和正文整体偏小。
内容集中在左上，大量无效留白。
没有主题色、页码、分隔和章节节奏。
文字覆盖完整，但更像大纲，不像演示文稿。
```

这里不能只检查 `python-pptx` 能否重新打开。文件结构正确，只能证明它是合法 PPTX，不能证明版式可用。

我把本地 renderer 升级为一个受控主题：

```text
16:9 页面
深色标题页
浅色内容页
蓝/青/紫循环强调色
52pt 封面标题
36pt 内容标题
22pt 正文
顶部强调线
章节编号和页码
分隔线与页脚
下一步/总结页使用收束背景
```

同时清理 Markdown 标记，避免 `#`、`##`、列表前缀进入页面；重复 H1 不再生成重复标题页。

内容 Prompt 也从“列出所有能力”改成：

```text
总览
  -> 分组能力
  -> 当前亮点和边界
  -> 下一步
```

每页一个主旨，3 到 5 个具体要点，减少空泛市场化句子和重复表述。

最后我没有只看 XML，而是使用本机 PowerPoint 把全部页面导出成 PNG，逐页检查：

```text
文字是否裁切
标题是否意外换行
元素是否重叠
页码是否一致
页脚是否越界
留白和信息密度是否合理
```

这一步才真正完成 PPT 的视觉 QA。

## QQ 文件发送为什么是一次性待交付状态

审批恢复生成文件后，系统会创建一条与以下信息绑定的内存待发送状态：

```text
approval ID
task ID
session key
owner user ID
artifact ID
文件大小
完整 SHA-256
```

当前 `/agent 确认` 处理器只消费这次确认新产生的待发送状态。

发送前再次核对：

```text
文件仍在固定工作区
后缀符合命令
不是符号链接逃逸
字节数一致
SHA-256 一致
当前仍是原主人私聊
```

然后只调用一次 OneBot 文件发送。

待发送状态在尝试发送前就被消费，因此失败不会自动重试、换接收者或改成群发。本地产物仍然保留，用户可以看到它已经生成，但 QQ 发送失败是独立结果。

## 让失败提示也成为产品能力

当 PPT 超页时，最早返回的是：

```text
Approval resume failed: document_delivery_too_many_slides
```

对开发者来说能定位，对普通使用者却不够友好。

所以在文档链路稳定以后，我又增加了统一故障分类：

```text
configuration：配置问题
model：模型问题
permission：权限问题
network：网络问题
data：数据问题
```

每个失败都有稳定 code 和建议。例如：

```text
presentation_slide_limit_exceeded
artifact_integrity_failed
document_delivery_failed
approval_context_invalid
required_arguments_unavailable
request_timeout
model_rate_limited
authorization_failed
```

现在 PPT 超页会变成类似：

```text
审批恢复失败（数据问题 / presentation_slide_limit_exceeded）：
PPT 预估或渲染页数超过安全上限。
请减少章节或每页内容后重新发起任务；系统未生成或发送超限文件。
```

错误日志也不再无界写入原始异常，而是保存：

```text
category
code
exception type
脱敏且限长的 message
```

API Key、token、password、secret 和 URL 会在写入前脱敏。审批恢复失败的任务事件只保存安全分类，不持久化任意工具异常原文。

## 最后补一条只读可靠性巡检

文档能力从只读走到外部文件发送以后，快速确认系统状态变得更重要。

我增加了：

```text
/agent 做一次可靠性巡检
```

它确定性进入现有只读聚合诊断，不由 Main LLM 猜测当前状态，输出：

```text
关键配置是否存在
本机服务端口状态
SQLite immutable read-only 状态
近 24 小时失败、超时和异常退出信号
五类错误统计
RootGraph/MainAgent 最近安全观测
```

本机还有一个可放进 Windows 任务计划程序的脚本：

```powershell
.\scripts\inspect-reliability.ps1 -Hours 24 -WriteReport
```

它只刷新固定报告，不自动创建计划任务，不发送告警，不重启服务，不修改配置，也不修复数据库。

这条巡检并不是文档工具的必需组件，但它让“外部写能力已经开放”不再意味着“出错后只能翻原始日志”。

## 测试和 QQ live

这轮实际测试过：

```text
TXT 本地生成
DOCX 本地生成与重新打开
PPTX 本地生成与重新打开
本地写审批
外部交付审批
审批恢复
文件完整性复核
QQ Word 文件发送
QQ PPT 文件发送
文档意图优先级
runtime metadata 污染拒绝
上一条内容引用拒绝
会话并发保护
PPT 精确页数预检
PPT 全页渲染视觉 QA
错误分类与脱敏
可靠性巡检
```

真实 live 也暴露并验证了多个问题：

```text
Word 工具不可见 -> registry 单一事实源修复
Word 正文污染 -> Prompt 分区 + 本地 marker 拒绝
“推荐下一步”误路由 -> 文档整句意图优先
二十多秒无回执 -> 进度消息 + session lock
PPT 审批后超页 -> 审批前真实分页预检
PPT 质量不佳 -> 主题 renderer + PowerPoint 逐页 QA
TXT 未发送 -> 明确区分“生成”和“生成并发给我”
```

最新完整回归：

```text
607 tests OK
```

## 最后

把 MainAgent 从只读扩展到文档产物，并不是简单增加三个 Python 库调用。

真正需要设计的是：

```text
模型能决定什么。
本地代码必须决定什么。
审批前允许发生什么。
审批后冻结执行什么。
本地写和外部发送如何分权。
文件怎样证明自己完整。
失败怎样被用户理解。
真实格式质量怎样验证。
```

这次迭代最后保留了几条原则：

```text
不要为了文档能力开放任意文件系统。
工具可见性、策略和执行必须来自同一 registry。
内部 metadata 不是用户内容，Prompt 和本地校验都要防污染。
文档对象优先于提纲里的局部管理关键词。
长任务先给进度回执，同一 session 不并发乱序。
能在审批前确定失败的请求，不要等确认后再失败。
合法 PPTX 不等于可用 PPT，视觉产物必须渲染检查。
没有说“发给我”，就不要把本地写自动升级成外部发送。
外部发送采用单次尝试，失败不重试、不换接收者。
错误分类和巡检不是附属品，而是写能力上线的一部分。
```

现在 MainAgent 能做的事情仍然很有限：

```text
它不能改项目源码。
不能执行 shell。
不能指定任意路径。
不能覆盖文件。
不能自由选择 QQ 接收者。
不能绕过审批。
```

但在这条很窄的边界内，它已经可以稳定完成：

```text
准备内容
请求审批
生成 TXT/Word/PPT
复核文件
通过 QQ 单次交付
失败时给出可理解的原因
```

对真实 Agent 系统来说，窄而完整的能力闭环，往往比“什么都能做一点”更有价值。
