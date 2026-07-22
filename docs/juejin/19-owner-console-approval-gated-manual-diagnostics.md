# 从只读页面到可控真实探针：我如何给 Owner Console 加手动诊断

标签建议：`AI Agent`、`FastAPI`、`React`、`RAG`、`可观测性`

## 开头

前面几轮开发里，我给自己的 QQ AI Chatbot 做了一个本地 Web Owner Console。

最初它很克制：

```text
只读取任务、审批、配置和运行观测。
不执行工具。
不修改配置。
不写业务数据库。
前端请求受 GET allowlist 约束。
```

这套只读边界解决了“主人怎样看见系统”的问题，但很快又暴露出另一个问题：

```text
看见配置开启，不等于功能真的可用。
看见索引计数，不等于一次真实检索能够完成。
看见服务地址，不等于依赖链已经跑通。
```

尤其是 Diagnostics 页面，即使把中英文状态、原始 `code` 和区块层级整理得很清楚，它仍然更像一份配置目录。

于是我开始做下一步：允许主人在页面上显式触发少量、后端固定、可证明边界的手动诊断。

这一篇记录我怎样从只读页面走到真实探针，又怎样避免“加一个诊断按钮”演变成任意操作入口。

## 可读性优化没有解决真实性问题

在开放手动动作之前，我先重做了 Reliability 和 Diagnostics 页面的信息层级。

Reliability 页面保留英文原始证据：

```text
component
operation
category
code
recovery_state
```

中文只负责解释，不覆盖这些值。确定性总结只根据结构化数据生成，不调用 LLM，也不会在缺少等长对比窗口时武断地说“故障上升”或“故障下降”。

Diagnostics 页面也采用同样原则：

```text
中文含义
解释值
原始英文证据
```

页面变得好读以后，主人给了一个很准确的反馈：它仍然主要在展示开关和快照，没有真正执行诊断，也不能判断某条实际链路是否工作。

这个反馈让我重新区分了两个概念：

```text
read snapshot
  读取已有状态，适合自动刷新。

manual diagnostic action
  主人显式批准后，执行一次有真实成本或真实外部调用的固定动作。
```

第二类动作不能伪装成普通 GET，也不能因为名字叫“诊断”就默认安全。

## 手动诊断不是自由工具面板

我没有给页面增加这些输入框：

```text
自由 prompt
模型名称
Base URL
SQL
工具名
top_k
超时
重试次数
```

因为一旦接受这些字段，Owner Console 就不再是在运行“已注册诊断”，而是在提供一个通用执行器。

我最终采用的是固定工作流注册模型：

```text
前端只知道工作流名称和说明。
后端拥有完整输入、预算和执行逻辑。
请求体只携带固定 confirmation。
每次动作只执行一个已注册工作流。
```

首批开放的是：

```text
project_doc_rag_fixed_retrieval
memory_rag_index_consistency
```

它们都属于 RAG，但安全边界完全不同，所以没有强行塞进一个“通用 RAG 测试”接口。

## 一个按钮背后需要多层授权

本地控制台只监听 loopback，并不意味着 POST 可以随便开放。

每个手动诊断都要经过这些条件：

```text
服务启动时显式启用对应工作流。
页面第一次点击只展开风险说明。
主人第二次点击才真正确认。
请求必须来自允许的同源 Origin。
请求必须携带进程内动作 Cookie。
请求必须使用固定动作 Header。
Content-Type 必须正确。
JSON body 必须精确匹配固定 confirmation。
多余字段也会被拒绝。
```

动作 Cookie 通过同源 GET 获得，设置为：

```text
HttpOnly
SameSite=Strict
```

服务每次启动生成新的进程内动作 session。仅知道 POST 路径还不够，旧进程的 Cookie 也不能拿到新进程继续使用。

前端原有 guard 也从“只允许 GET”升级为精确 allowlist：

```text
允许已有只读 GET。
只额外允许已注册的固定 POST。
未知 POST、动态路径和自由请求仍然失败。
```

这不是把整个控制台改成可写，而是在只读控制台上切出几个非常窄的动作孔径。

## 所有真实探针共享一把全局锁

手动动作还有一个容易被忽略的问题：并发。

如果主人连续点击两个工作流，系统可能同时执行 embedding、SQLite 扫描或 LLM 请求。即使每个动作单独看都安全，并发后也会让结果、资源消耗和最近运行状态变得难以解释。

所以这些工作流共享同一个进程内全局运行锁：

```text
正在运行一个工作流时，其他工作流直接返回 busy。
不排队。
不自动等待。
不自动重试。
完成后也不自动串行启动下一个工作流。
```

最近结果只存在 Owner Console 进程内。重启后自然清空，不写入：

```text
聊天历史
Agent task
approval
reliability event
业务诊断表
```

对这种主人临时确认的本机探针来说，进程内状态反而让边界更清楚。

## ProjectDocRAG：一次真实 embedding，但数据库必须只读

第一个工作流要回答的问题很朴素：

```text
当前 ProjectDocRAG 能不能对后端固定问题生成向量，
并从现有项目文档索引中返回固定前五项？
```

审计现有检索入口后，我没有直接复用它。原因是生产检索链会经过数据库初始化和普通可提交连接，无法证明 `database_write=false`。

因此这个工作流使用专用路径：

```text
固定问题只存在后端局部内存。
当前 embedding provider 只调用一次。
不做 legacy fallback。
不自动重试。
SQLite 使用 URI mode=ro。
只查询 source_id、chunk_index 和 embedding。
本地计算相似度并取 top 5。
```

页面不显示固定问题、文档正文、片段内容、文件路径或原始异常，只展示完成判断所需的有限证据：

```text
活动片段数
当前 provider/model 的有效向量数
返回数量
固定目标是否命中
最高相似度
workflow / stage / code
零副作用字段
```

还有一个实际踩到的坑：生产配置里的 `enable_project_doc_rag=false`，最初被我当成手动探针的硬阻断。

但这两个开关语义不同：

```text
生产功能开关
  控制普通运行链是否使用 ProjectDocRAG。

手动探针开关
  主人是否在本次 Owner Console 启动中批准固定诊断。
```

最终实现把生产开关保留为 `runtime_feature_enabled` 证据，但不让它覆盖主人对固定动作的独立授权。

真实页面验收中，这个工作流完成了：

```text
一次真实 embedding
一次 SQLite mode=ro 检索
top 5 返回
固定目标命中
数据库大小和 mtime 不变
```

这才是“真实检索通过”，而不只是“索引看起来存在”。

## MemoryRAG：只审计一致性，不读取私人正文

第二个工作流故意没有做真实私人记忆检索。

我想先回答一个更基础、也更容易控制暴露面的事实问题：

```text
活动 MemoryRAG 文档与当前有效向量是否一致？
```

专用 SQL 仍然使用 SQLite `mode=ro`，并且不选择：

```text
content
summary
其他私人正文列
```

它只统计：

```text
活动文档数量
当前 provider/model/content_hash 的有效向量数量
manual_fact、preference、session_summary 各自缺失数量
来源映射缺口
软删除历史文档所带向量数量
```

这个工作流不会：

```text
生成查询向量
调用 embedding
执行 retrieve_memory
读取私人记忆正文
调用 ProjectDocRAG、DevContext 或 CombinedRAG
重建索引
补写缺失向量
自动创建修复任务
```

真实结果发现：

```text
活动文档 37
有效向量 35
缺失向量 2
两条缺失都属于 manual_fact
来源缺失 0
软删除历史向量 5
```

页面给出的结论是：

```text
outcome=attention
stage=result_validation
code=memory_rag_active_embedding_gap
```

注意，这不是工作流失败。

工作流成功完成了只读一致性检查，并发现了一个真实缺口。因此它需要关注，但不应该标成“执行失败”。

## succeeded、attention 和 failed 必须分开

手动诊断最容易把两件事混在一起：

```text
诊断程序有没有正常完成？
被诊断对象有没有完全满足期望？
```

我最终采用三类结果：

```text
succeeded
  工作流完成，目标合同满足。

attention
  工作流完成，但发现兼容性、性能或一致性问题。

failed
  工作流本身没有完成，例如配置缺失、连接失败、超时或内部错误。
```

并且每个结果必须保留英文定位证据：

```text
workflow
stage
code
```

中文可以写“需要关注”，但不能把 `memory_rag_active_embedding_gap` 藏掉。否则后续排障只能依赖页面文案，接口合同会重新退化成不可搜索的自然语言。

## 为什么发现缺口后不顺手修复

看到两条缺失向量时，最诱人的下一步是：

```text
自动补一下。
```

但“知道缺少两条向量”和“批准读取相应正文并调用 embedding 写回数据库”是两种完全不同的授权。

自动修复至少会扩大这些边界：

```text
读取私人内容
调用外部或本地模型
产生新的向量数据
修改数据库
处理部分成功和失败恢复
决定是否重试
```

所以本轮只记录事实，不创建修复任务，也不在页面放一个看似方便的“立即修复”按钮。

诊断的职责是让问题变得可验证，不是替主人扩大授权。

## 自动化必须证明“没有做什么”

这类功能的测试不能只断言响应是 200。

我给它补了几类负向合同：

```text
错误 Origin、Cookie、Header、Content-Type 或 confirmation 必须被拒绝。
多余 JSON 字段必须被拒绝。
页面一次确认只能产生一个 POST。
两个工作流不能并发。
SQLite 查询前后文件大小和 mtime 不变。
MemoryRAG 查询不选择正文列。
MemoryRAG provider 不能调用 embedding。
ProjectDocRAG embedding 只能调用一次。
前端 guard 只能放行注册过的固定 POST。
```

最终回归覆盖了后端、前端、TypeScript、生产构建、固定 POST guard、Python AST、依赖一致性和 `git diff --check`。

真实页面验收时，我还单独核对了访问日志中的 POST 次数、最近运行 ID、数据库文件大小与 mtime，以及后端日志中的 ERROR、Traceback 和 Exception。

## 最后

这次改造让我对“只读控制台”有了一个更细的理解。

一个控制台可以默认只读，同时允许少量主人批准的真实诊断；关键不在于 HTTP 方法是不是 POST，而在于动作是否满足这些条件：

```text
输入后端固定。
能力启动时显式启用。
主人二次确认。
接口精确 allowlist。
执行预算有上限。
不同工作流共享并发锁。
结果区分 succeeded、attention 和 failed。
原始英文证据可见。
不自动重试、修复或启动后续动作。
```

ProjectDocRAG 的价值是证明一次真实 embedding 和只读检索能跑通。

MemoryRAG 一致性检查的价值是发现两条真实缺口，同时证明私人正文没有被读取、向量没有被补建、数据库没有被修改。

好的诊断不只告诉我系统做了什么，也要让我能够确认：

```text
它这次没有越过哪些边界。
```
