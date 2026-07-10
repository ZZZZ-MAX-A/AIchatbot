# MainAgent 分区分层系统诊断报告设计

状态：P2.46a 设计、P2.46b 系统概览和 P2.46c 视觉区详情均已完成本地实现与回归；P2.46d 主人 QQ live 尚未完成。运行中的 Bot 需要在后续 live 前重启，当前不能把本地测试通过表述为 QQ 命令已经验证。

本文定义并记录第二个正式只读工作类型 `system_diagnostics_report`。它的首要职责不是复制现有 `/诊断`、`/视觉状态`、`ops_health` 和多步排查输出，而是先把系统状态归并为少量诊断大区，进行短输出分诊；只有发现某个大区需要关注时，才建议主人显式进入该区域的详情排查或更深探针。

## 1. 结论

`system_diagnostics_report` 使用三级诊断模型：

```text
系统概览分诊
  -> 区域详情排查
  -> 针对性深度探针
```

默认概览必须短，正常和按设计关闭的大区分别合并为一行，只单独展开异常、降级、需要关注或影响判断的未知大区。报告最多推荐一个优先排查区域；只有对应区域 scope 已注册时才给出可执行严格命令，不自动创建下一级任务，不自动连续排查，不自动修复。P2.46c 已注册 `vision` 区域详情；其他区域详情和所有深度 scope 仍保持未注册。

系统状态由确定性代码和结构化证据判断，不由主模型凭自然语言猜测。第一版不调用 MainAgent LLM，不向外部聊天 API 发测试请求，不执行视觉推理、embedding 生成、RAG 召回或 ProjectDocRAG 正文读取。

## 2. 与现有诊断能力的关系

仓库已经存在：

```text
DiagnosticsGraph 的配置、视觉、错误、缓存、记忆和 TTS 视图
旧 /诊断 的聊天接口、Ollama、数据库和角色卡检查
owner_read_command/ops_health 聚合诊断
vision_troubleshoot 多步只读视觉排查
memory_rag_troubleshoot 多步只读记忆检索排查
RootGraph 和 MainAgent 最近观测
Owner Console 只读 health snapshot
```

新工作类型不废弃这些入口，也不把它们返回的长文本拼成另一份长文本。已有低层检查函数和观测可以成为证据提供者；新层负责：

```text
把证据归入诊断大区
区分当前可用性和最近使用状态
执行确定性严重度判断
压缩默认输出
选择一个最值得下钻的区域
保持任务持久化摘要安全
```

实现时优先复用结构化低层结果或抽取共享 provider，不依赖解析现有中文格式化字符串，也不让 Bot 反向请求 Owner Console HTTP API。

## 3. 诊断对象不是模型“内心状态”

本报告可以评价：

```text
功能是否配置开启
能力或工作类型是否注册
当前调用上下文是否通过策略
本地依赖是否可访问
最近运行观测是成功、失败还是缺失
诊断证据是否足够和是否过旧
高风险能力是否仍保持预期边界
```

本报告不能评价：

```text
模型隐藏推理是否“健康”
模型主观信心
没有运行证据时的端到端正确性
未主动探测的外部服务当前是否可用
Git 工作区、独立 Owner Console 进程或所有 NapCat 行为是否正常
```

执行本任务能证明主人私聊消息已经进入当前 Bot 和 `/agent` 入口，但在回复真正发送之前，不能声称 QQ 出站发送已经被独立验证。

## 4. 正式工作与入口合同

当前工作类型：

```text
name=system_diagnostics_report
display_name=系统诊断报告
risk_level=read_local
requires_approval=false
approval_resume_enabled=false
```

默认严格入口：

```text
/agent 执行系统诊断任务
```

区域入口只能映射到预注册枚举，例如：

```text
/agent 执行系统诊断任务：视觉
/agent 执行系统诊断任务：记忆与RAG
/agent 执行系统诊断任务：MainAgent
/agent 执行系统诊断任务：聊天
/agent 执行系统诊断任务：语音
/agent 执行系统诊断任务：Owner Console
```

内部保持一个 work type，由严格 `scope` 区分范围。第一批候选 scope：

```text
overview
core
chat
main_agent
memory_rag
vision
voice
owner_console
```

更深 scope 只能在对应设计和测试完成后逐项注册：

```text
vision_invocation
vision_inference
rag_index
rag_retrieval
main_agent_work_runtime
```

自由文本不会扩大 scope。诸如“顺便重启服务”“自动修好”“清空缓存后重试”等内容不进入当前只读任务。第一版只允许主人私聊显式入口；普通聊天、群聊、非主人私聊、普通语义 fallback、Web Owner Console 和 `/agent-debug` 都不能触发正式系统诊断工作任务。

P2.46c 当前只有 `overview` 和 `vision` 会创建并执行正式任务。其他已知区域名称会被严格解析，但在区域 executor 注册前只返回“区域详情尚未注册”，不创建 `agent_tasks`，也不执行任何区域探针。未知 scope 同样在任务创建前拒绝。

## 5. 三级诊断模型

### 5.1 第一级：系统概览分诊

`scope=overview` 只回答：

```text
整体是否正常
哪些大区正常或按设计关闭
哪些大区需要关注、降级或异常
未知是否影响判断
最建议先排查哪个大区
本次执行了什么级别的探针
```

概览使用被动证据和廉价本地读取。正常大区不展开功能明细，高风险能力符合预期时只显示一条边界摘要。

### 5.2 第二级：区域详情排查

主人显式选择区域后，任务沿该区域的固定依赖链检查。区域详情遵守“第一故障层优先”：上游已经失败时，不继续输出大量下游证据；上游正常但最近使用异常时，才进入调用层或结果层判断。

区域详情仍以判断和下一步为主，不默认展示全部配置、完整日志、完整观测或所有健康检查文本。

### 5.3 第三级：针对性深度探针

只有区域详情无法定位时，才建议更深 scope。深度探针可能执行一次受控的本地推理、embedding 或固定召回测试，因此必须由主人再次显式触发，并分别声明探针成本、超时、读取范围和不产生的副作用。

概览和区域详情不得自动执行深度探针，不得在一次任务内形成“发现问题 -> 连续运行全部检查 -> 自动修复”的 agent loop。

## 6. 诊断大区

第一版核心概览包含六个大区。Owner Console 作为可选区域，不因独立服务未启动而默认降低 Bot 总体状态。

### 6.1 核心运行区

依赖链：

```text
主人私聊 /agent 请求
  -> 当前 Bot/NoneBot 执行
  -> DiagnosticsGraph
  -> 数据库只读访问
  -> 正式工作任务运行时
```

概览只输出类似：

```text
核心运行：正常
核心运行：异常｜数据库只读检查失败
```

数据库检查只能执行只读查询；不得通过诊断任务创建业务记录、清理数据或修复 schema。任务自身既有的创建、领取、完成事件仍属于注册工作任务的审计生命周期，不算诊断探针写操作。

### 6.2 聊天区

依赖链：

```text
聊天开关
  -> ChatGraph 路由
  -> 模型配置完整性
  -> 最近聊天调用观测
  -> 最近回复/持久化观测
```

概览不发送真实 chat completion，只区分配置与最近证据：

```text
聊天：正常｜最近调用成功
聊天：需要关注｜配置完整，但最近调用失败
聊天：无近期使用证据
```

“无近期使用证据”是中性状态，不能自动判为故障。

### 6.3 MainAgent 区

依赖链：

```text
MainAgent 开关
  -> 显式入口和主人私聊策略
  -> work/tool 注册
  -> ToolPolicy
  -> 任务领取和执行
  -> 安全结果持久化
```

概览只报告控制面是否一致以及最近正式工作是否成功。完整工具列表、风险级别、审批和 `approval_resume_enabled` 只在区域详情中显示。

高风险能力保持预期时合并为：

```text
高风险能力：Shell、任意文件写入、外部写入和多步写自动化保持关闭
```

如果某个配置开关开启但没有真实注册工具，必须报告“配置开启、未注册、实际不可用”，不能把环境变量等同于能力上线。

### 6.4 记忆与 RAG 区

依赖链：

```text
MemoryRAG 配置
  -> embedding provider 状态
  -> 索引统计
  -> 最近召回观测
  -> 最近聊天注入观测
```

概览可读取非正文统计和最近安全观测，但不执行新的 embedding 或语义召回。ProjectDocRAG 在概览中只报告边界和已有任务安全摘要：

```text
普通聊天注入禁止
只允许显式 /agent dev_context 读取正文
本次诊断没有执行 ProjectDocRAG 检索
最近 development_context_report 的锚点/警告安全摘要（如存在）
```

本任务不得读取 ProjectDocRAG 文档片段、当前状态锚点正文、检索分数或来源路径。未来若要增加纯索引 metadata 检查，需单独确认其边界并提供不返回内容的 provider。

### 6.5 视觉区

视觉区是第一候选区域详情试点。依赖链：

```text
视觉功能开关
  -> Ollama 服务在线
  -> 视觉模型已安装/可用
  -> 模型驻留状态（后续；仅在有独立可靠证据时判断）
  -> 最近是否使用视觉
  -> 最近使用成功、失败或低质量
  -> 是否需要真实推理自检
```

“服务在线”“模型已安装”“模型驻留”和“最近使用成功”是不同状态，不能互相替代。概览示例：

```text
视觉：正常｜服务在线｜模型可用｜最近使用成功
视觉：需要关注｜服务在线｜模型可用｜最近使用失败
视觉：正常｜服务在线｜模型可用｜近期未使用
```

视觉详情短路规则：

```text
视觉关闭：按设计关闭，停止后续检查。
Ollama 离线：定位服务层，停止模型和调用层展开。
服务在线但模型缺失：定位模型层，停止调用层展开。
服务和模型正常、最近使用失败：建议 vision_invocation。
服务和模型正常、最近结果低质量：建议 vision_inference。
没有近期使用：报告无近期证据，不主动推理。
```

`scope=vision` 不执行内置测试图推理；真实推理只能进入未来单独注册的 `vision_inference`。
P2.46c 的 `/api/tags` 只用于判断配置模型是否存在，不把“模型已安装”表述为“模型当前已驻留”。

### 6.6 语音区

依赖链：

```text
TTS 开关
  -> 本地服务健康
  -> 模型加载
  -> 最近候选
  -> 最近发送观测
```

TTS 关闭时显示“按设计关闭”并跳过服务检查。只有功能开启但依赖不可用时，才升级为降级或异常。

### 6.7 Owner Console 可选区

Owner Console 是独立本地服务。默认概览只在已有安全观测显示其读模型或安全边界异常时提及，不主动访问 `127.0.0.1:8090`，也不因控制台没有启动而降低 Bot 状态。

显式 `scope=owner_console` 后，未来可以检查：

```text
本地服务是否可访问
只读 API 是否返回预期结构
静态模式是否开启
GET-only allowlist 是否保持
/docs、/redoc、/openapi.json 是否关闭
是否意外出现 Web 写入口
```

该 scope 仍不能启动或停止 Owner Console、构建前端、修改配置或触发 MainAgent。

## 7. 区域状态模型

每个区域至少保留：

```text
zone
status
headline
configured_state
current_availability
recent_usage
evidence_freshness
reason_code
recommended_scope
probe_mode
deep_probe_executed
```

固定 `status`：

```text
normal             正常
attention          需要关注
degraded           降级
error              异常
off_by_design      按设计关闭
unknown            未知/证据不足
```

注册状态是区域证据，不单独取代健康状态：

```text
registered
not_registered
not_applicable
```

判断规则：

```text
按设计关闭不计入异常。
无近期使用不等于异常。
错误日志非空只表示近期记录，不能单独证明当前故障。
当前廉价探针失败的权重高于旧观测失败。
配置开启但能力未注册属于需要关注或降级。
已开启功能的必要依赖当前失败属于降级或异常。
证据没有可靠时间时，只能写“最近一条记录”，不能写“当前仍失败”。
未执行主动探针时必须明确“未检查”，不能声称端到端健康。
```

总体状态取最严重且与已启用能力相关的大区状态。`off_by_design` 不拉低总体；`unknown` 只有影响核心结论时才使总体进入“需要关注”。

## 8. 概览采集预算

`overview` 允许：

```text
读取进程内布尔配置和非敏感枚举
读取工作类型和工具注册表
执行当前上下文的只读策略判断
数据库 SELECT 1 和非正文计数
读取已经脱敏的错误类别/计数
读取 RootGraph、MainAgent 和任务的安全观测摘要
读取图片缓存和记忆索引非正文计数
使用严格超时查询本地 Ollama 模型列表
在 TTS 已开启时使用严格超时读取本地健康接口
```

`overview` 禁止：

```text
外部聊天 API completion
真实视觉推理
embedding 生成或自检
MemoryRAG/ProjectDocRAG 语义召回
读取 RAG、记忆或聊天正文
读取完整错误堆栈或长响应体
访问任意 URL
启动、停止或重启服务
重建索引
清空日志或缓存
修改配置
业务数据库写入
额外 QQ 发送
```

每个 provider 独立捕获失败，单区失败不阻断其他大区。总体执行使用有限预算；超时区域进入 `unknown` 或 `degraded`，不激进重试。具体超时常量在实现阶段根据现有探针审计确定，本设计不假定所有旧格式化函数都适合直接复用。

## 9. 自适应输出合同

默认概览目标不超过 1200 字符，顺序固定：

```text
总体状态
大区状态计数
异常/降级/需要关注区域
合并的正常区域
合并的按设计关闭区域
一个优先下一步
本次探针和安全说明
```

压缩规则：

```text
正常区域合并为一行。
按设计关闭区域合并为一行。
异常、降级和需要关注区域各写一行关键原因。
不影响总体结论的 unknown 不逐条展开，只计数。
同一严重度按核心依赖优先级选择下一步。
最多推荐一个主区域，不自动列出完整排查清单。
超过响应预算时保留异常和限制，先裁剪正常区域说明。
```

推荐优先级先比较严重度，再比较依赖层级：

```text
核心运行
  -> MainAgent 控制面
  -> 聊天
  -> 记忆与 RAG
  -> 视觉
  -> 语音
```

Owner Console 只在显式 scope 或已有异常证据时参与优先级。

概览示例：

```text
系统诊断：需要关注
大区状态：正常 4｜需要关注 1｜按设计关闭 2｜未知 0

需要关注：
- 视觉：Ollama 服务在线，模型可用，但最近一次视觉使用记录出现错误。

正常：核心运行、聊天、MainAgent、记忆与RAG。
按设计关闭：语音、Agent Web/写入能力。

建议先排查：视觉区。
如需详情，请由主人显式执行 `/agent 执行系统诊断任务：视觉`；本次未自动创建区域详情任务。

本次未执行模型推理、外部请求、修复或配置修改。
```

区域详情目标不超过 1800 字符，固定顺序：

```text
区域和定位层级
截至第一故障层的状态链
初步判断
一个推荐下一级 scope，或无需继续
未执行的深度探针
安全说明
```

## 10. 显式确认与任务边界

区域详情和深度探针是新的显式任务，不由上一任务自动创建：

```text
概览任务完成
  -> 返回建议命令
  -> 等待主人发送
  -> 新建对应 scope 的系统诊断任务
```

纯本地区域详情仍是 `read_local`，不需要写操作审批，但需要主人显式命令。深度探针若涉及外部服务，必须先有单独的 `read_external` 工具、配置和 URL/数据安全设计；不得借系统诊断绕过 `ENABLE_AGENT_WEB` 或 ToolPolicy。

任何修复动作都不属于 `system_diagnostics_report`：

```text
重启服务
拉取模型
重建索引
清空缓存或日志
修改配置
写入记忆或数据库
Web/文件/外部写操作
```

未来若注册修复工具，仍需独立工作类型、严格参数、风险策略和适用的审批恢复合同。诊断任务只能建议，不能直接恢复执行修复。

## 11. 结构化结果和持久化

候选内部结果：

```text
SystemDiagnosticsReportPayload
  scope
  overall_status
  zone_statuses
  primary_recommended_scope
  probe_counts
  warning_count
  external_request_count
  deep_probe_count
  repair_action_count
  report_text
```

主人私聊只返回经过限长和脱敏的详细概览或区域报告。`agent_tasks.result` 与 `work_finished.output_summary` 只保存安全摘要。

概览持久化示例：

```text
系统诊断概览已完成。
总体状态：需要关注。
大区：正常 4，需要关注 1，降级 0，异常 0，按设计关闭 2，未知 0。
优先排查区域：视觉。
深度探针：0。
外部请求：0。
修复操作：0。
任务记录未保存完整诊断证据、配置值、错误原文、路径或观测明细。
```

区域详情持久化示例：

```text
视觉区详情诊断已完成。
区域状态：需要关注。
定位层级：调用层。
推荐下一范围：vision_invocation。
本地检查：1。
深度探针：0。
外部请求：0。
修复操作：0。
任务记录未保存日志、图片、路径、配置值、完整观测或详细报告。
```

不得持久化：

```text
密钥、Token、Cookie 或认证头
完整 URL、本地绝对路径和 .env 值
用户消息、聊天记录、记忆正文或 RAG 片段
图片 URL、图片描述正文或测试推理正文
完整错误日志、堆栈和外部响应体
RootGraph/MainAgent 完整观测
详细报告全文
```

## 12. 完成与失败语义

任务成功生成“系统异常”结论时，任务状态仍是 `done`，因为诊断执行已经成功。只有以下情况才进入 `failed`：

```text
正式工作任务无法领取或完成
scope 非法却未在入口拒绝
结构化结果无法生成安全摘要
执行器没有任何可用证据且自身发生技术失败
持久化生命周期发生不可恢复错误
```

单个区域 provider 失败时，优先完成部分报告并把该区标为 `unknown`、`degraded` 或 `error`。不得保存异常原文，不自动重试，不自动创建补偿任务。

## 13. 安全边界

P2.46 继续保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent 或正式工作任务。
MainAgent 和 ChatAgent 保持分离。
ProjectDocRAG 正文只允许显式 /agent dev_context 使用。
不开放 shell、Git、任意文件读写或未注册数据库写入。
主人写操作仍必须经过适用的审批合同。
只有已注册且 approval_resume_enabled=true 的工具可在确认后恢复。
不开放多步写自动化或诊断后自动修复。
不新增额外 QQ 发送。
Owner Console 保持只读 GET，不新增登录/鉴权或 Web 写操作。
/docs、/redoc、/openapi.json 继续关闭。
P2.40b 业务页面轮询继续未批准。
不提交 web/owner-console/dist。
```

## 14. 实现拆分

### P2.46a：设计

本文件完成：

```text
大区定义
三级诊断模型
状态和严重度规则
默认输出压缩合同
显式下钻协议
持久化和失败语义
现有诊断复用边界
```

本步不修改运行时代码，不新增 QQ 命令或 work type。

### P2.46b：系统概览分诊

状态：本地实现和回归已完成，尚未进行主人 QQ live。

已完成：

```text
新增 system_diagnostics_report.py：六区结构化证据、确定性 evaluator、自适应格式化和 1200 字符上限。
OwnerAgentWorkRuntime 同时注册 development_context_report 和 system_diagnostics_report。
OwnerRuntimeFactory 注入 event-bound 系统诊断 executor，并提供 execute_system_diagnostics_report。
严格主人私聊命令 /agent 执行系统诊断任务 只执行 scope=overview。
区域 scope 和未知 scope 在任务创建前停止；不进入普通语义、LLM 或 dev_context fallback。
概览只读取数据库、注册表、配置、非正文索引统计和安全运行观测。
视觉只允许 loopback Ollama /api/tags；TTS 只允许 loopback health。
远程服务地址不主动探测，状态进入 unknown 而不是发起外部请求。
MainAgent 区验证两个正式只读工作，以及 owner_write_command 的审批与受控恢复标记。
任务详情只持久化总体状态、六区计数、优先区域和探针/外部请求/修复计数。
无 LLM、无视觉推理、无 embedding/RAG 召回、无 ProjectDocRAG 正文、无自动下钻或修复。
```

本地验证：

```text
系统诊断、work runtime、MainAgent bridge、QQ 边界、持久化、Owner Console、既有诊断和配置聚焦回归：155 tests OK。
全量 unittest discover：364 tests OK。
既有非失败提示：FastAPI TestClient 依赖产生 StarletteDeprecationWarning。
```

### P2.46c：视觉区详情试点

状态：本地实现和回归已完成，尚未进行主人 QQ live。

已完成：

```text
严格主人私聊命令 /agent 执行系统诊断任务：视觉 创建 scope=vision 正式任务。
独立 VisionDiagnosticsReportPayload 记录区域状态、定位层级、下一范围和安全计数。
按功能配置 -> loopback Ollama 服务 -> 模型可用性 -> 最近调用/质量执行首故障短路。
概览和视觉详情共用视觉 evidence collector；vision-only 任务不运行数据库、MemoryRAG、MainAgent、TTS 或聊天概览探针。
远程或非 loopback Ollama 地址不主动访问，服务状态为 unknown。
最近调用错误只建议尚未注册的 vision_invocation；低质量结果只建议尚未注册的 vision_inference。
无近期使用保持正常/中性，并明确不等于端到端验证。
QQ 详细状态链仅在当次主人私聊返回；任务记录只保存状态、层级、推荐 scope 和安全计数。
不执行真实视觉推理、测试图片、模型拉取、服务重启、自动子任务、外部请求、自动重试或修复。
聚焦回归 166 tests、全量回归 375 tests 均通过。
```

### P2.46d：主人 QQ live

在 Bot 重启后分别验证：

```text
默认概览足够短
正常区域被合并
异常区域能被准确突出
不会自动创建详情任务
主人显式选择视觉后才执行视觉详情
视觉详情按第一故障层停止，不堆叠下游状态
任务详情只保存安全摘要
没有额外 QQ、外部请求、深度探针或修复动作
```

其他区域详情和深度探针根据概览及视觉试点的真实使用结果另行批准，不因 P2.46b/c 完成而自动进入。

## 15. 验收标准

设计后续实现至少需要覆盖：

```text
所有正常时概览不展开单项指标。
按设计关闭不计入异常。
一个区域异常时只突出该区域并推荐一个 scope。
多个区域异常时按严重度和依赖优先级选择一个主区域。
无近期使用记录不被误判为故障。
旧错误记录不被表述为当前仍失败。
视觉服务在线、模型已安装、驻留状态和最近使用彼此独立。
上游故障后区域详情不继续堆叠无关下游证据。
overview 不调用外部聊天 API、视觉推理、embedding 或 RAG 召回。
非法 scope 在执行器前拒绝。
普通聊天、群聊、非主人私聊和 Web 不能触发。
详细回复和任务持久化严格分层。
系统发现异常时任务仍可 done；执行器技术失败才 failed。
不产生自动下钻、自动重试、自动修复或额外 QQ 发送。
```

## 16. 明确延后

P2.46a 不决定或实现：

```text
自动周期诊断
故障自动告警
Owner Console 发起诊断
聊天 API 外部连通性探针
真实视觉推理探针
embedding 或 RAG 召回探针
Agent 联网、web_search 或 web_fetch
服务重启、索引重建或配置修复
跨消息自动诊断计划和 checkpoint
登录鉴权和 Web 审批操作
```

联网只读能力仍适合在 `system_diagnostics_report` 的概览和本地区域详情稳定之后单独设计；仅设置 `ENABLE_AGENT_WEB=true` 不代表联网工具、安全策略或实际能力已经存在。
