# MainAgent v1.6：把 QQ Adapter 里的 Agent 运行时拆成 service

标签建议：`AI Agent`、`NoneBot`、`Agent 架构`、`Python`、`工程化`

## 开头

前几篇里，我给这个 QQ AI 机器人补了很多 MainAgent 能力：

```text
/agent 显式主人入口
ToolRegistry 工具注册
owner_read_command 主人只读管理工具
owner_write_command 审批门控写工具
agent_task_read 任务/审批只读查询
agent_task_command 任务/审批控制面
任务详情卡、审批详情卡、任务工作台
```

这些能力跑起来以后，一个新问题开始变得明显：

```text
功能越来越像“主人控制台”。
代码却还挤在 QQ 插件入口里。
```

`src/plugins/ai_chat/__init__.py` 原本只是 NoneBot 插件入口，负责接收 QQ 消息、鉴权、调度、发送回复。可随着 MainAgent 发展，它慢慢开始承载更多业务运行时：

```text
任务和审批怎么查？
确认审批后怎么恢复工具？
owner_read_command 怎么分发？
owner_write_command 审批通过后怎么执行？
怎样把 QQ event 转成 session/user 上下文？
```

短期这样写最快，但长期会有两个问题。

第一，QQ 入口会越来越重，任何改动都像在拆炸弹。

第二，如果以后要做 Web Owner Console，或者把 Runtime service 做成更明确的后端层，这些逻辑不能继续绑死在 `MessageEvent` 上。

所以这次 v1.6 的一段工作，我没有继续加新工具，而是做了一轮代码层解耦：

```text
把 MainAgent owner 侧 task/read/write runtime 从 QQ adapter 里抽出来。
不拆进程。
不加 HTTP API。
不做 Web Console。
不改数据库。
不新增任何能力。
```

这篇文章记录这次解耦的过程，以及我为什么选择小步拆，而不是一上来就把它变成一个独立服务。

## 为什么先做代码层解耦，而不是直接上 Web Console

一开始讨论 v1.6 方向时，有几个方向都很诱人：

```text
MainAgent 多步只读诊断
任务协作
Runtime service 解耦
Web Owner Console
桌宠长期方向
```

但真正跑过一轮以后，我发现当前最该做的不是“继续加界面”，而是先把 MainAgent 自己站稳。

之前 MainAgent 已经能语义理解主人指令，比如：

```text
/agent 删除摘要 41
/agent 清空图片缓存
/agent 把群 123456 加入群白名单
/agent 添加事实记忆 主人喜欢先看结论
```

但早期只有只读工具时，会出现一种非常糟糕的体验：

```text
模型语义上答应了。
控制层却没有真正执行。
或者执行边界没有明确停住。
```

后来我补上了审批门控写工具：写操作必须先创建审批，主人确认后，只有已注册且 `approval_resume_enabled=true` 的工具可以恢复执行。

这让行为闭环稳定了，但也让 `__init__.py` 变得更复杂。

此时如果直接做 Web Console，就会被迫复用 QQ adapter 里的业务代码。那不是“加一个前端”，而是在一个已经变重的入口上继续叠楼。

所以这次我定了一个很保守的边界：

```text
只做代码层 Runtime service 解耦。
不拆成独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改 DB schema。
不改变现有 /agent 行为。
不新增 shell、任意文件写入、未注册数据库写入或多步写执行能力。
```

这样做的目标不是立刻变漂亮，而是先让结构变得可移动。

## 解耦前：QQ Adapter 什么都管

解耦前，`__init__.py` 大概同时做这些事：

```text
NoneBot command 注册
QQ MessageEvent 解析
owner 鉴权
RootGraph 调度
MainAgent LLM 接入
任务列表、任务详情、任务工作台
审批列表、审批详情、审批确认/拒绝
审批恢复 ToolRegistry 构造
owner_read_command 分发
owner_write_command 执行
诊断、RAG、记忆、角色卡、名单等读取函数绑定
回复发送
```

这不是“不能运行”的问题，而是职责边界变糊了。

比如任务详情本质上只需要：

```text
session_key
user_id
task_id
```

但它被写在 QQ event 里，就会天然依赖：

```text
MessageEvent
PrivateMessageEvent
GroupMessageEvent
session_key(event)
user_id(event)
```

这会让同一段逻辑很难在别的入口复用。

Web Console 想看任务详情怎么办？

CLI 想做一次诊断怎么办？

测试想不构造 QQ event 直接验证 runtime 怎么办？

如果答案都是“那就模拟一个 MessageEvent”，说明业务层已经被 adapter 污染了。

## 第一步：抽出任务和审批 runtime

第一刀是 `owner_agent_runtime.py`。

它引入了一个很小的上下文：

```python
@dataclass(frozen=True)
class OwnerAgentContext:
    session_key: str
    user_id: str
```

这一步的关键不是 dataclass 本身，而是把“任务/审批 runtime 需要什么”说清楚：

```text
它不需要 QQ event。
它不需要 matcher。
它不需要知道消息来自私聊还是群聊。
它只需要当前 owner 范围下的 session_key 和 user_id。
```

于是这些能力被搬进 service：

```text
任务状态
任务详情
任务工作台
审批状态
审批详情
确认审批
拒绝审批
审批演练
owner_write 审批请求创建
```

QQ adapter 里只剩一层转换：

```python
def owner_agent_context_from_event(event: MessageEvent) -> OwnerAgentContext:
    return OwnerAgentContext(
        session_key=session_key(event),
        user_id=user_id(event),
    )
```

后来这个转换又被收进总装 factory，这个后面再说。

这一刀完成后，任务/审批这块就可以不依赖 QQ event 做单测：

```text
OwnerAgentContext(session_key="private:10001", user_id="10001")
```

然后直接验证：

```text
任务工作台能否读取
最新任务详情能否展示
最新审批详情能否展示
```

这一步很朴素，但它是后续 Owner Console 的基础。

因为 Web Console 未来也只需要传入同样的 owner context，而不是伪造 QQ 消息。

## 第二步：抽出 owner_read_command 分发

第二刀是 `owner_read_runtime.py`。

`owner_read_command` 是主人侧只读管理命令，覆盖面很广：

```text
诊断状态
模型配置
视觉状态
最近错误
图片缓存状态
记忆状态
MemoryRAG 检索
摘要状态
角色卡
角色卡列表
访问控制
RAG 索引详情
MainAgent 最近观测
RootGraph 最近观测
群白名单
私聊白名单
黑名单
```

这些命令的共同点是：

```text
只读。
不创建任务。
不确认审批。
不写数据库。
不发额外 QQ 消息。
```

但它们读取的数据源不一样。有些来自 DiagnosticsGraph，有些来自 MemoryRAG，有些来自角色卡，有些来自动态名单。

所以我没有把所有底层读取函数都一起搬走，而是加了一个依赖注入对象：

```python
@dataclass(frozen=True)
class OwnerReadRuntime:
    bot_status_lines: LinesProvider
    ops_health_reply: TextProvider
    vision_troubleshoot_reply: TextProvider
    memory_rag_troubleshoot_reply: TextProvider
    run_diagnostics: DiagnosticsRunner
    run_memory_retrieval: MemoryRetrievalRunner
    run_memory_admin: MemoryAdminRunner
    ...
```

然后 service 只负责分发：

```python
async def run_owner_read_command(
    runtime: OwnerReadRuntime,
    command: str,
    context: Any,
) -> str:
    ...
```

这一步有一个取舍：为什么不把 DiagnosticsGraph、MemoryRAG、MemoryAdmin 都一起抽出来？

因为那样会把拆分面拉得太大。

当前更稳的做法是：

```text
底层读取能力先不动。
命令分发先抽出去。
QQ adapter 只负责把当前 event 绑定到这些读取能力。
```

也就是说，`owner_read_runtime.py` 不知道 QQ 是什么，但它知道：

```text
如果 command 是 config_status，就调用 run_diagnostics(CONFIG)。
如果 command 是 memory_retrieval，就从 tool context 里取 query，再调用 MemoryRAG 检索。
如果 command 是 role_card_list，就调用 role_card_list_lines。
```

这让它将来可以被 Web Console 复用。

Web Console 不需要走 QQ event，只需要提供另一套 `OwnerReadRuntime` 依赖即可。

## 第三步：抽出 owner_write_command 执行器

第三刀是 `owner_write_runtime.py`。

这一步最敏感，因为它涉及真实写操作。

不过这里必须强调：这次没有新增任何写能力，也没有绕过审批。

已有规则仍然是：

```text
owner_write_command 必须先生成审批。
主人确认后才恢复执行。
只有已注册且 approval_resume_enabled=true 的工具可以恢复。
不执行 shell。
不执行任意文件写入。
不执行未注册数据库写入。
```

`owner_write_runtime.py` 只接管已经存在的、审批通过后会执行的主人管理写命令：

```text
clear_image_cache
clear_error_log
select_persona
add_fact_memory
add_preference_memory
clear_session_summaries
delete_session_summary
allow_group
deny_group
allow_private
deny_private
block_user
unblock_user
```

和 `OwnerReadRuntime` 一样，我没有让它直接 import 一堆具体实现，而是用依赖注入：

```python
@dataclass(frozen=True)
class OwnerWriteRuntime:
    clear_image_cache: ClearImageCache
    clear_error_log: ClearErrorLog
    add_access_item: AccessOperation
    remove_access_item: AccessOperation
    select_role_card: SelectRoleCard
    add_manual_memory: AddManualMemory
    clear_session_summaries: ClearSessionSummaries
    delete_session_summary: DeleteSessionSummary
    ...
```

真正执行时：

```python
def run_owner_write_command(
    runtime: OwnerWriteRuntime,
    command: str,
    context: Any,
) -> str:
    ...
```

这里保留了原有参数校验和文案，比如：

```text
select_persona 必须有 target
add_fact_memory / add_preference_memory 必须有 content
delete_session_summary 必须有数字 summary_id
动态名单修改必须有数字 target
```

这些校验其实非常重要。

因为对 Agent 系统来说，最危险的不是“它拒绝执行”，而是“它猜着执行”。

比如：

```text
/agent 删除摘要 最新
```

当前系统不会猜最新摘要 ID，而是要求主人明确指定数字 ID。

这看起来没那么智能，但它更可靠。

## 第四步：加一个 owner_runtime_factory 总装层

前面三刀之后，业务逻辑已经从 QQ adapter 里分出来了，但 `__init__.py` 里还散着三块装配代码：

```text
如何从 event 得到 OwnerAgentContext
如何构造 OwnerReadRuntime
如何构造 OwnerWriteRuntime
```

所以第四刀是 `owner_runtime_factory.py`。

它不是新能力，只是总装层：

```python
@dataclass(frozen=True)
class OwnerRuntimeFactory:
    session_key_from_event: EventValue
    user_id_from_event: EventValue
    run_diagnostics_graph: GraphRunner
    run_memory_retrieval_graph: GraphRunner
    run_memory_admin_graph: GraphRunner
    ...
```

它集中提供这些方法：

```text
agent_context(event)
read_runtime(event)
write_runtime()
run_task_command(event, query, ...)
format_task_read(event, command, reference)
execute_task_command(event, command, reference, goal, ...)
create_approval_request(event, ...)
run_read_command(event, command, context)
run_write_command(command, context)
```

于是 QQ adapter 里只保留一个绑定点：

```python
def owner_runtime_factory() -> OwnerRuntimeFactory:
    return OwnerRuntimeFactory(
        session_key_from_event=session_key,
        user_id_from_event=user_id,
        bot_status_lines=status_lines,
        run_diagnostics_graph=run_diagnostics_graph,
        run_memory_retrieval_graph=run_memory_retrieval_graph,
        ...
    )
```

这一步完成后，结构变成：

```text
__init__.py
  QQ / NoneBot adapter
  负责事件接入、鉴权、RootGraph 调度、回复发送和依赖绑定

owner_runtime_factory.py
  MainAgent owner runtime 总装层
  负责组装 task/read/write runtime

owner_agent_runtime.py
  任务、审批、工作台、详情卡、审批恢复入口

owner_read_runtime.py
  主人只读管理命令分发

owner_write_runtime.py
  已审批主人写命令执行
```

这就是我这次想要的形状。

不是微服务，不是“为了抽象而抽象”，而是让 adapter 重新像 adapter。

## 这次最重要的边界：解耦不等于放权

做 Agent 系统时，很容易把“能力变强”和“边界变松”混在一起。

这次我刻意反过来做：

```text
结构变清晰。
权限不增加。
行为不变化。
```

整个 P2.1 到 P2.4 的边界都保持一致：

```text
不拆独立进程
不新增 HTTP API
不新增 Web Owner Console
不改数据库 schema
不改变现有 /agent 行为
不新增工具
不扩大审批恢复范围
不开放 shell
不开放任意文件写入
不开放未注册数据库写入
不开放多步写执行能力
普通聊天仍不会触发 MainAgent owner runtime
```

尤其是 `owner_write_command`：

```text
语义识别到写意图
创建审批
主人确认
ToolRegistry 校验注册工具
确认 approval_resume_enabled=true
恢复执行受控工具
记录任务事件
返回执行结果
```

这条链路没有因为 service 解耦而变短。

只是原本散在 QQ adapter 里的逻辑，被挪到了更明确的位置。

## 测试怎么兜住这种重构

这种重构最怕两类回归。

第一类是行为变了。

比如 `/agent 角色卡列表` 还能不能走 owner_read？

`/agent 删除摘要 41` 还能不能创建审批？

`/agent 确认 最新` 还能不能恢复已注册工具？

第二类是边界变松了。

比如普通聊天会不会误触发 MainAgent？

LLM 能不能看到隐藏工具？

未注册写工具会不会被执行？

为了兜住这些风险，我主要用了三类测试。

第一类是 service 级单测：

```text
OwnerAgentContext 不依赖 QQ event 也能读任务工作台、任务详情、审批详情。
OwnerReadRuntime 不依赖 QQ event 也能分发 bot_status、config_status、memory_retrieval 等命令。
OwnerWriteRuntime 不依赖 QQ event 也能执行 clear_image_cache、select_persona、delete_session_summary 等已审批写命令。
OwnerRuntimeFactory 不依赖 QQ event 也能组装 owner context、read runtime 和 write runtime。
```

第二类是 QQ 边界测试：

```text
__init__.py 仍然是 /agent 入口。
ProjectDocRAG 不进入普通聊天。
MainAgent 仍然 feature gated。
__init__.py 不回退成承载 task/read/write runtime 的大杂烩。
owner_runtime_factory.py 才引用三块 runtime。
```

第三类是审批恢复测试：

```text
delete_session_summary 审批确认后能真实删除当前会话摘要。
add_fact_memory 审批确认后能真实写入长期记忆。
SQLite database is locked 问题不会复发。
只有注册且启用 approval_resume_enabled 的工具可以恢复。
```

最后一轮全量测试：

```text
Ran 284 tests OK
```

这类重构没有截图，也没有立刻让人惊呼的效果。

但 284 个测试全绿时，我心里非常踏实。

## 这次解耦后的代码变化

今天最后的几个 checkpoint 是：

```text
3baafcd Decouple MainAgent owner task runtime
05b90f7 Decouple MainAgent owner read runtime
d61f30e Decouple MainAgent owner write runtime
262f1b0 Add MainAgent owner runtime factory
```

核心文件变成：

```text
src/plugins/ai_chat/owner_agent_runtime.py
src/plugins/ai_chat/owner_read_runtime.py
src/plugins/ai_chat/owner_write_runtime.py
src/plugins/ai_chat/owner_runtime_factory.py
```

而 `src/plugins/ai_chat/__init__.py` 的职责被收窄：

```text
NoneBot command 注册
QQ event 接入
owner 鉴权
RootGraph 调度
LLM handler 装配
OwnerRuntimeFactory 依赖绑定
matcher.finish 回复
```

这还不是最终形态，`__init__.py` 仍然很大。

但 MainAgent owner 这条主线已经从里面剥离出来了。

这一步之后，我再看代码时，心智负担明显小了很多：

```text
要改任务/审批：去 owner_agent_runtime.py
要改主人只读命令分发：去 owner_read_runtime.py
要改已审批写命令执行：去 owner_write_runtime.py
要改 QQ 入口依赖绑定：去 owner_runtime_factory() / owner_runtime_factory.py
```

## 给后续 Web Owner Console 留出的入口

这次没有做 Web Console，但它其实已经被“铺路”了。

未来 Web Console 不应该直接调用 QQ adapter。

它更应该像这样接入：

```text
Web request
  -> 鉴权得到 owner 身份
  -> 构造 session_key/user_id 或 owner scope
  -> 使用 OwnerRuntimeFactory 或另一套 factory 组装 runtime
  -> 调用 owner_agent_runtime / owner_read_runtime
  -> 对写操作继续走审批链路
```

也就是说，Web Console 未来可以复用：

```text
任务工作台 read model
任务详情卡
审批详情卡
owner_read_command 分发
审批创建
审批确认后的受控恢复
```

而不是复制一份 QQ 命令逻辑。

这就是这次代码层解耦的价值。

它没有让用户立刻看到一个新页面，但它让“新页面应该接哪里”变清楚了。

## 一点工程感受

这次重构最大的感受是：Agent 项目里，真正难的不是让模型“会说”，而是让系统知道什么时候不能做。

比如删除摘要这件事。

一个看起来更聪明的 Agent 可能会说：

```text
好的，我帮你删除最新摘要。
```

但在这个系统里，我更希望它说：

```text
请提供数字 summary_id。
```

或者：

```text
已创建审批，尚未执行，等待主人确认。
```

这种“不猜”的体验，短期看不够丝滑，长期看更可靠。

而当系统开始有任务、审批、记忆、RAG、角色卡、动态名单这些能力时，代码结构也要服务于同一个原则：

```text
能读的地方明确只读。
能写的地方必须审批。
适配器只做适配。
业务 runtime 不绑死入口。
```

这就是我这次拆 `owner runtime` 的原因。

## 下一步

接下来我会先做一轮回归体验检查，而不是继续盲目大拆。

重点看这些路径：

```text
/agent 任务工作台
/agent 角色卡列表
/agent 访问控制
/agent 删除摘要 <ID>
/agent 确认 最新
/agent 完整排查图片识别问题
/agent 完整排查记忆检索问题
```

如果这些都稳定，下一步才考虑：

```text
Runtime service 更明确的应用层接口
Web Owner Console 的只读工作台
审批列表和任务详情的 Web read model
角色卡记忆隔离
更长期的桌宠形态
```

但今天这一步，我觉得已经很关键。

因为 MainAgent 不再只是一个堆在 QQ 插件里的“大函数”，而开始有了自己的 runtime 边界。

这对一个长期运行的 Agent 项目来说，比多加一个炫酷工具更重要。
