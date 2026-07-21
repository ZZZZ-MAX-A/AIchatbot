# 可靠性错误分类与周期巡检设计

状态：第一版五类错误与只读巡检、P2.47 结构化事件、确定性 QQ 故障趋势命令和 Owner Console 可靠性只读页均已实现并完成既有 live。真实用户视觉推理和 TTS 合成的结构化接线、本地假依赖回归及 Bot 加载均已完成，Owner Console 接入范围已由 5 项加载为 7 项。媒体真实 live 已产生安全结构化证据：视觉观察链通过但识图功能失败；TTS 经冷启动超时后成功合成并由主人确认 QQ 语音送达，故障趋势形成恢复证据。

## 1. 目标

本轮把分散的错误、超时、失败调用和异常退出信号统一为可统计、可解释、可复查的可靠性信息。重点不是自动修复，而是让主人能快速回答：

```text
当前核心服务和关键配置是否可用
最近是否出现高频错误或超时
失败主要属于哪一类
下一步应该先检查什么
巡检做了什么，以及明确没有做什么
```

## 2. 五类错误合同

所有关键失败统一归入以下五类，不把模型原始异常、密钥、URL 或完整堆栈直接返回给用户：

| 类别 | 稳定值 | 典型场景 | 默认建议 |
| --- | --- | --- | --- |
| 配置问题 | `configuration` | 缺少必填项、无效地址、未注册 scope、恢复参数不完整 | 检查开关、必填配置、服务地址和模型名，不自动修改 |
| 模型问题 | `model` | 模型不存在、429/额度/限流、空响应或非法模型响应 | 检查模型、额度、限流和响应格式，避免连续重试 |
| 权限问题 | `permission` | 401/403、主人策略、审批上下文不一致 | 检查鉴权、主人身份和审批状态，不绕过权限 |
| 网络问题 | `network` | 超时、连接失败、DNS/TLS/代理、本地服务不可达、QQ 文件发送失败 | 先确认服务和网络可达，再由主人决定是否重试 |
| 数据问题 | `data` | SQLite、索引、schema、JSON、文件完整性、PPT 超页、未知运行状态 | 检查数据与文件，不覆盖原文件，不自动修复 |

分类结果包含稳定 `code`。已明确覆盖：

```text
request_timeout
connection_failed
model_rate_limited
model_not_found
authorization_failed
invalid_configuration
data_validation_failed
presentation_slide_limit_exceeded
artifact_integrity_failed
document_delivery_failed
approval_context_invalid
required_arguments_unavailable
unexpected_runtime_state
```

未来新增可读提示时应优先增加精确 code，不解析或依赖完整异常原文。

## 3. 日志与用户提示

新的 `log_ai_event_error` 记录：

```text
timestamp
安全 user/group 审计字段
category
code
exception type
脱敏且有长度上限的 message
```

API Key、token、password、secret 和 URL 会在写入前脱敏。MainAgent 观测文本同样先脱敏并限制长度。

Main LLM 失败继续保留原有针对性提示，同时追加 `类别 / code`。只读工具失败、正式只读工作失败和审批恢复失败不再直接回显任意异常原文，而是返回组件名、类别、稳定 code、简要原因和下一步建议。审批恢复失败写入任务/事件时只保存安全分类，不持久化工具异常原文。

## 4. 巡检入口

### 4.1 QQ 只读入口

```text
/agent 做一次可靠性巡检
```

该自然命令确定性映射到现有 `owner_read_command/ops_health`，复用视觉、MemoryRAG、RootGraph、MainAgent 和近 24 小时错误分类证据。它不调用 Main LLM 来猜测当前状态。

Bot 重启前仍可使用原入口：

```text
/agent 做一次系统健康检查
/agent 帮我看一下最近错误
/最近错误
```

### 4.2 本机脚本

默认检查最近 24 小时：

```powershell
.\scripts\inspect-reliability.ps1
```

检查最近 7 天：

```powershell
.\scripts\inspect-reliability.ps1 -Hours 168
```

写入固定最新报告：

```powershell
.\scripts\inspect-reliability.ps1 -Hours 24 -WriteReport
```

报告只能写到 Git 忽略的：

```text
output/reliability-inspections/latest.txt
```

脚本不会接受任意报告路径，不创建时间戳历史文件，避免无人值守运行导致无界增长。

## 5. 检查范围

本地状态检查包括：

```text
.env 是否存在
聊天模型必填项是否配置（不输出值）
MainAgent 开启时其模型必填项是否配置（不输出值）
NoneBot 本机 8080 端口是否可达
SQLite 是否可用 immutable read-only 方式读取 schema_version
虚拟环境是否存在
视觉开启时本机 Ollama 11434 端口是否可达
```

日志信号来自固定文件尾部，单文件最多读取 2,000 行：

```text
logs/ai_chat_error.log
logs/nonebot.err.log
logs/owner-console.err.log
logs/tts-service.err.log
```

无行内时间戳的日志使用文件最后修改时间参与窗口过滤，避免把很旧的服务日志错误计入当前时间窗。成功、完成和正常审批等待信号不会作为失败统计。

“疑似异常退出”只识别明确的 `SystemExit`、unexpected exit、fatal/critical 和非零 exit code 信号。没有信号只能表述为“未发现”，不能证明进程在整个时间窗持续在线。

## 6. 周期运行建议

第一版不由 Bot 自动创建 Windows 计划任务。主人如需无人值守巡检，可以在 Windows 任务计划程序中设置：

```text
程序：powershell.exe
参数：-NoProfile -ExecutionPolicy Bypass -File "D:\AIchatbot\scripts\inspect-reliability.ps1" -Hours 24 -WriteReport
起始于：D:\AIchatbot
频率：每 30 分钟
```

计划任务只刷新固定 `latest.txt`。自动 QQ 告警、邮件告警、自动下钻、自动重试、服务重启、配置修改和数据修复仍未开放。

## 7. 2026-07-14 本机基线

本轮实际只读巡检结果：

```text
当前本地状态：正常
NoneBot 8080：可达
SQLite immutable read-only：通过
聊天与 MainAgent 模型必填项：已配置
最近 24 小时：0 个失败信号
最近 7 天：11 个失败信号
  数据问题 8
  网络问题 3
  超时 1
  失败调用 3
  疑似异常退出 0
```

7 天统计是日志信号盘点，不等于存在 11 个仍未解决的当前故障，也不等于 11 次独立事故。24 小时窗口和当前本地状态均正常；后续结构化 `category/code` 日志会提高趋势统计精度。

## 8. 安全边界

巡检不执行：

```text
外部模型或 Tavily 请求
真实聊天、视觉、TTS、embedding 或 RAG 主动探针
QQ 测试发送
审批确认
服务启动、停止或重启
失败重试
配置修改
数据库、索引或文件修复
日志清理
```

本轮只新增诊断代码、只读脚本、固定可选报告和可读提示；没有扩大 MainAgent 对项目文件、shell、Git、数据库写入或任意 QQ 发送的权限。

## 9. P2.47 结构化可靠性事件第一刀

P2.47 不再只依赖文本日志关键词推断新故障。新增事件 schema 1，必需字段为：

```text
occurred_at
runtime_id
component
operation
category
code
outcome
```

事件没有 `message`、`content`、`metadata`、用户、QQ、session、路径、URL、Key、模型响应、异常类型或堆栈字段。`component + operation` 使用成对白名单；`code` 使用稳定注册表并固定映射 category。失败与降级必须属于既有五类；成功和正常跳过的 category 为空。合法 outcome 只有：

```text
succeeded
failed
degraded
skipped
```

SQLite schema 7 新增 `reliability_event_buckets`。同 runtime、五分钟桶、component、operation、category、code、outcome 的重复事件只增加 `occurrence_count` 并更新 first/last seen。Python 合同与 SQL `CHECK` 双重限制枚举；可靠性写入异常全部 fail-open，不能影响聊天、分类、文档交付、RAG 或 Bot 启动。

趋势按 `component + operation + category + code` 聚合。恢复不是生产组件自行声明，而是由时间顺序推导：最后一次失败之后同一 component/operation 出现真实 `succeeded` 才是 `recovered`；曾成功后又失败是 `recurring`；没有后续成功是 `unresolved`；不具备可靠成功语义的生命周期事件为 `insufficient_evidence`。`skipped` 不算失败，也不能恢复故障。

生命周期使用每次进程随机 UUID。启动记录 `runtime_started`，正常关闭记录 `runtime_stopped`；下次启动发现上一 runtime 有 start 无 stop 时，只记录 `suspected_abnormal_exit / data / degraded`。该信号不等于已证明崩溃，不读取 PID、进程命令行或 Windows 事件日志，也不触发自动告警、重启或修复。

首批运行接线：

```text
main_llm / plan_action
sticker_classifier / classify_intent
document_delivery / send_document
project_doc_rag / rebuild_index
bot_runtime / lifecycle
```

自动化覆盖合同拒绝、category/code 不一致、五分钟去重、恢复/复发顺序、skip 不恢复、异常退出推断、直接 SQL 白名单、原始秘密不落库和 observer fail-open。完整回归为 625 tests OK（skipped=3）。2026-07-19 00:25 Bot 重启后，8080、OneBot 和 stderr 正常；主人 QQ 普通聊天、表情状态与 Main LLM 纯文字请求产生 `runtime_started`、`sticker_classifier/classify_intent/operation_succeeded` 和 `main_llm/plan_action/operation_succeeded` 三组事件。三个 matcher 全部完成，0 错误，0 失败/降级，0 异常退出误报，0 新任务/审批/文档交付。结构化趋势 QQ 命令、Owner Console 页面、自动告警、自动清理和更多组件接线继续延后。

## 10. P2.47 结构化故障趋势只读命令

第二刀新增 `owner_read_command/reliability_trend`，严格支持：

```text
/agent 查看故障趋势
/agent 查看最近故障趋势
/agent 查看可靠性趋势
```

分类器在 Main LLM 之前确定性命中；命令不调用 Main LLM、Tavily、MemoryRAG、ProjectDocRAG 或外部模型，不创建 Agent 任务/审批，不告警、修复、重试、重启或清理。运行 provider 在线程中使用 SQLite `mode=ro`，不调用 `ensure_database`；数据库或表不存在时只读失败，不在查询时建库或迁移。

报告默认展开最近 24 小时的结构化失败/降级故障组，并给出最近 7 天摘要。每组只显示 component/operation、中文类别、稳定 code、次数、首次/最后失败时间及 `unresolved/recovered/recurring/insufficient_evidence`；不显示 runtime UUID、数据库 ID、原始异常、路径、URL、Key、用户或 QQ。无故障时必须说明“不等于已证明系统持续在线”。生命周期证据不足即使同一 operation 后来有 `runtime_started`，也不显示“最近成功”来暗示恢复。

真实只读 smoke 查询前后 `chatbot.db` 文件大小和修改时间完全一致。该 smoke 同时发现当前生产 Bot 在 2026-07-19 18:35 发生一次外部重启：上一 runtime 有 start 无 stop，因而正确形成 `suspected_abnormal_exit / data / degraded`；新 Bot 进程、8080、OneBot 和 stderr 均正常。该记录是生命周期未闭合证据，不等于已证明崩溃原因。

路由、dispatcher、零 LLM/RAG、只读不建库、格式、隐私、恢复状态和生命周期展示测试已补齐；完整回归 630 tests OK（skipped=3）。主人批准后，Bot 于 2026-07-19 20:31 重启并成功加载 `ai_chat`，8080 与 OneBot 正常、stderr 为空。主人于 20:42 执行 `/agent 查看故障趋势`：matcher 正常完成、0 错误，真实报告将两次强制停止后遗留的生命周期未闭合聚合为 2 次失败/降级、1 个故障组，24 小时和 7 天状态均为“证据不足”1 组，没有误报“已恢复”。报告明确限定已接入 P2.47 的固定结构化事件、不读取聊天正文或原始异常，并声明没有调用 Main LLM、Tavily、RAG 或外部模型。查询后生产 `chatbot.db` 大小与修改时间仍保持启动时数值，QQ live 通过。Owner Console 可靠性只读页见下一节；自动告警、自动清理和更多组件接线继续延后。

## 11. P2.47 Owner Console 结构化可靠性只读页

第三刀新增 `/api/v1/owner-console/reliability` GET-only 接口和 `/owner-console/reliability` 页面。后端在同一 UTC 生成时刻分别执行 24 小时与 168 小时 `mode=ro` 查询，复用既有分组与恢复推导，不调用 `ensure_database`。HTTP read model 只返回 component、operation、category/中文标签、稳定 code、次数、首末失败、合格的最近成功和恢复状态；不返回 runtime UUID、数据库 ID、用户/QQ、正文、路径、URL、Key、异常或 metadata。

页面展示六项摘要、24 小时/7 天切换、故障组表格、组件/类别/恢复状态本地筛选、五项当前接入范围和显式只读边界。筛选只作用于浏览器内已返回的固定数据，不发起额外查询或写入。生命周期 `insufficient_evidence` 即使存在后续 `runtime_started` 也保持最近成功为空。无事件和筛选为空均继续显示“没有结构化故障不等于已证明持续在线”。

Owner Console 于 2026-07-19 在 `127.0.0.1:8090` 启动。生产 GET 返回最近 24 小时和 7 天均为 2 次失败/降级、1 个 `bot_runtime / lifecycle / suspected_abnormal_exit` 故障组、状态“证据不足”，接入范围 5 项；SQLite `mode=ro=true`，ensure database、正文/异常读取、LLM、RAG、写副作用均为 false。查询前后 `chatbot.db` 大小和 mtime 一致。Python 全量 632 tests OK（skipped=3），前端 13 tests、typecheck、GET-only guard 与生产构建通过。2026-07-20 主人人工浏览器验收确认恢复状态与最近成功显示正确、清除筛选可用、5 项范围和只读边界正常，缩小窗口后没有明显重叠。由于生产只有 1 个真实故障组，无法现场演示跨组件筛选；自动化使用 `bot_runtime` 与 `main_llm` 两个故障组验证了 7 天切换和本地组件筛选，未向生产库写入假故障。自动告警、修复、重试、重启、清理和网页写操作继续关闭。

2026-07-20 15:36 Owner Console 再次受控启动。生产 API 的接入范围为 7 项，最近 24 小时与 7 天都返回 9 次失败/降级、4 个真实故障组：`bot_runtime/lifecycle/suspected_abnormal_exit` 5 次、`insufficient_evidence`；`tts/synthesize/request_timeout` 2 次、`recovered`；`vision/infer/invalid_model_response` 1 次、`recovered`；`sticker_classifier/classify_intent/data_validation_failed` 1 次、`unresolved`。视觉与 TTS 最近成功分别为 15:15:59、14:06:28。查询前后数据库大小和 mtime 不变；HTTP read-only、Web write 与 boundary 字段继续全部符合只读合同。生产数组按页面同一精确筛选谓词得到全部 4 组、bot_runtime/vision/tts 各 1 组、recovered 2 组且恰为 vision/tts，组合筛选各 1 组；清除筛选会把 component/category/recovery 三项恢复为 `all`。页面路由 200、ReliabilityPage Vitest、TypeScript 和 27 文件 GET-only guard 通过。当前工具会话未暴露技能要求的内置浏览器接口，因此没有借外部自动化绕过；主人随后人工打开真实页面并确认各阶段符合预期，三组件、两组 recovered、组合筛选及清除后恢复 4/4 的 DOM 验收通过。新增 sticker_classifier 未恢复事件不读取或保存异常原文，不为验收删除、伪造恢复或自动修复。

主人批准只读排查该 sticker_classifier 事件且确认当次 QQ 请求只发送图片。有限映射证明 `data_validation_failed` 只来自 `input_invalid`；生产配置 ready、调用类型为字符串、助手回复已成功发送且字符上限为默认 2400，空 `user_text` 因而成为已证实根因。该校验发生在 DeepSeek transport、本地表情库加载和选择之前；纯函数复现同样得到 `input_invalid`、transport calls=0。库本身仍为 schema 2、revision 18、enabled 14、disabled 2。主人随后批准最小修复：调度器只对字符串空 user_text 设置内存 `skipped/empty_user_text/preflight_blocked` 并立即返回，不调用模型、不写成功/失败事件、不发送表情；类型错误、空回复和超长仍保留 data_validation_failed。自动化确认门控早于 preflight/classifier/observer/send，底层错误语义保持；相邻 56 tests、全量 650 tests OK（skipped=3）。Bot 于 21:26 重启加载；纯图片 live 的状态为 skipped/empty_user_text、匹配 0、无选中 ID，classifier 结构化事件基线前后完全相同，DeepSeek 与发送路径均未进入，运行期 3 个 matcher 完成、0 错误、0 traceback、stderr 为空。旧 data_validation_failed 已由重启前 21:25:23 的真实 classifier success 自然 recovered。同期 vision 有一次 data_validation_failed，41 秒后出现真实 success，因此也为 recovered；两组件严格分开。Owner Console 最新 24 小时为 9 次失败/降级、5 个故障组，recovered 4、unresolved 0、insufficient_evidence 1。随后只细分 `/表情意图状态` 的展示：`preflight_blocked + empty_user_text` 显示“纯图片无文本，已在本地跳过；未调用分类模型，未发送表情”，真实 cooldown/message_gap/hourly_cap 等阻断仍显示旧频率门控文案。该纯函数与 handler 接线由定向 21 tests 覆盖，完整回归 651 tests OK（skipped=3）；门控、结构化事件、模型调用和发送行为均未改变。展示补丁于 2026-07-21 00:50:39 首次加载；该实例稍后在没有正常 shutdown 标记的情况下离线，未据此推断具体原因，也未由开发代理自动重启。当前 Bot 启动链于 10:43:20 恢复，8080 为 Bot 单一监听且 OneBot 会话已建立。主人随后执行新的纯图片 QQ live，状态 matcher 真实返回样本 1、`skipped`、无有效建议、0.00、`empty_user_text`、匹配 0、影子选中 ID 无，并精确显示“纯图片无文本，已在本地跳过；未调用分类模型，未发送表情”。验收前后四个 classifier 桶的固定字段、`occurrence_count` 和 `last_seen_at` 完全一致，没有新增 succeeded、failed、degraded 或 skipped 事件；历史 `data_validation_failed` 与 recovered 证据未删除、修改或伪造，视觉事件也未归因给 classifier。Bot 已加载且 QQ 新文案 live 已通过。

## 12. P2.47 视觉与语音真实运行事件

第四刀只接入真实用户操作：`vision / infer` 表示一次端到端图片理解批次，包含受控图片读取、大小/格式校验、Ollama 请求、响应质量校验和安全清理；`tts / synthesize` 表示一次 TTS 服务准备、IndexTTS2 合成响应和音频产物复核。视觉状态、自检图片、图片缓存、TTS health、候选保存、按需待机、功能关闭、冷却和生成前文本拒绝都不产生事件。TTS 合成成功后若 QQ 发送失败，仍属于后续 QQ Adapter 交付问题，不反向改写 TTS 结果。

`media_reliability.py` 不把任意异常直接交给趋势字段，而是用组件专属有限映射选择既有稳定 code。视觉超时/连接/429/模型不存在/空响应或低质量/图片数据无效分别映射到网络、模型、配置或数据固定 code；TTS 冷启动超时、连接、429、IndexTTS2 缺失、音色/服务脚本配置、服务无效响应、音频缺失/为空/时长异常同样使用固定映射。异常在映射前经过既有内存脱敏和长度限制，SQLite 只收到 component、operation、category、code、outcome 与时间/计数。

视觉以逻辑批次为计数单位，不按图片下载、Ollama HTTP 和清理步骤重复计数：全部成功为 `succeeded`，全部失败为 `failed`，部分成功为 `degraded`。TTS 当前不伪造降级，只有完整产物通过复核才成功。两类 observer 捕获自身异常并返回 false，不改变原业务返回或异常传播。

Owner Console 已受控重启并在生产 API 显示 7 项接入范围，新增 `vision/infer` 与 `tts/synthesize`；接线前查询前后 `chatbot.db` 大小和 mtime 未变化，媒体事件为 0，没有为展示筛选写假故障。媒体/可靠性/Owner Console 定向 76 tests OK，视觉语音 Graph 与诊断相邻 80 tests OK，Python 全量 647 tests OK（skipped=3），AST 148 files、pip check 与 `git diff --check` 通过。

主人批准后，Bot 于 2026-07-20 01:07 重启并正常加载。01:11 的一条真实图片批次只产生一条 `vision / infer / model / invalid_model_response / failed`；Ollama、视觉模型和 Bot matcher 当时可用，无 stderr 或 traceback。事件合同有意不保存模型原始输出，因此只能确认响应没有通过质量校验，不能在空响应、无效 JSON、低质量重复或超长响应之间继续武断归因。用户收到的角色化回复却声称没有看图能力，这与“单次识别失败”不一致；结构化接线验收通过，但识图功能和原失败文案验收未通过。主人随后批准确定性失败提示：`describe_images` 对失败项只返回固定无异常细节的内部描述；`ChatUserContent.vision_failed` 只在非空批次全部失败时为 true；`generate_chat_text_response` 在 `ask_llm` 之前直接返回固定提示“本次图片识别失败了，请稍后再试，或者换一张更清晰的图片。”；两条文本渲染路径也对该固定回复跳过远程表情分类和自动附件。部分成功批次不触发短路，结构化 observer 的 attempted/success/error 与单批次计数保持不变。视觉专项与可靠性/Graph 相邻 105 tests、完整回归 650 tests OK（skipped=3）。Bot 于 15:00 重启加载补丁，未停止或重启 Ollama；主人 15:15 的单条真实请求返回连贯可用的图片内容描述，结构化表只新增一条 `vision / infer / operation_succeeded / succeeded`，matcher 正常完成、0 错误、0 traceback、stderr 为空。最后失败之后出现真实成功，原 `invalid_model_response` 故障组判为 recovered。该次未触发失败分支，因此固定失败提示仍只有自动化证据；不为补验主动制造故障，不自动停止、重试或修复。图片内容与回复原文没有写入本文或结构化事件。

真实 TTS 首次在 01:17 记录 `tts / synthesize / network / request_timeout / failed`。当日下午再次冷启动时，同一固定故障于 14:00 再出现一次；两次都与 `TTS_STARTUP_WAIT_SECONDS=45` 的服务等待边界吻合，发生在 `/tts` 提交及 IndexTTS2 模型加载之前，不能归因为显存不足或模型推理失败。服务就绪后，14:06 的请求生成唯一 `tts / synthesize / operation_succeeded / succeeded`，音频文件、非零大小和有效时长均通过观察边界，主人确认 QQ 语音成功送达。同一 runtime 中最后失败之后出现真实成功，趋势将该 `request_timeout` 故障组判为 `recovered`。成功后 health 为 `ok=true`、`loaded=true`，GPU allocated 约 6931.8 MiB、reserved 约 7476.0 MiB；本机约 8GB 显存可以完成这次实际合成，但余量较小，视觉与 TTS 同时驻留仍需受控管理。没有自动重试、自动卸载其他模型、自动重启或自动修改超时配置。
