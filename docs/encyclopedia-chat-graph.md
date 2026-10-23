# 角色百科查询与聊天子图

## 两个角色的执行方式

默认人格和独立人格共用明确查询入口：短指令“查一下初音未来”，以及“默认人格知不知道超时空辉夜姬”、
“那独立人格知道沃雅妮莎吗”、“独立人格知道超时空辉夜姬的故事吗”等明确专名问句，
直接提取词条并执行百科子图，不依赖模型预判或主动调用工具。
支持问句前的括号动作和“没有就考考独立人格”等有限前缀，仅公共词条传给百科网站，
聊天模型仍收到完整原句。私人指代、账号、密钥、时间和情绪等问句不使用该捷径；
复杂语句仍交由原预判或工具流程处理。

明确查询完成后，两个人格各只生成一次聊天回复；默认人格本轮不再附带百科工具，避免重复查询。
其他消息中，默认人格继续在自己的聊天请求中获得 `lookup_unknown_slang` 工具说明。
模型没有请求工具时，只有一次聊天模型请求；请求工具时执行公共百科子图，
把结果交回同一角色模型生成最终回复。工具交互和页面资料不作为独立聊天消息保存。

独立人格支持明确查询和普通聊天中的自动查词。
其他需要判断的消息由 `AIKE_LLM_*` 指向的 DS 线路做短预判；
预判只分析本次消息，不加载角色卡、世界卡、历史、私聊记忆、QQ 身份或维护工具。
判断需要百科时查询公共资料，随后仍由独立人格当前聊天模型生成一次最终回复。

自动判断提示词已按主人要求改为“当前句子出现公共人物/角色名、作品名、技能名、剧情专名、网络梗等就查询”，
取消“模型不熟悉或不确定才查询”的条件。默认人格工具说明与独立人格 DS 预判共用
`PUBLIC_ENCYCLOPEDIA_QUERY_RULE`，避免两处规则维护不一致；DS 对这些公共专名应返回 `needed=true`。
对当前聊天角色的称呼、私人熟人和账号配置等不作为公共词条。
取得有效正文后，结合本句和当前话题适量补充相关事实，不堆砌无关内容。
本次修改提示词，不增加关键词规则或更改工具调用方式；模型自动分支的实际遵循程度仍需在线验证。

问候和短确认通过确定性规则跳过预判。其他普通聊天可能增加一次预判等待，
即使最后判断无需百科。自动触发是模型决策，离线测试不保证真实模型每次识别准确。
预判不是提前生成角色回复，不增加一次独立人格角色模型请求。

### DeepSeek 思考参数修复（2026-10-14）

19:26:51 的实际预判日志显示：输出预算 512，completion_tokens 与 reasoning_tokens 均为 512，
content_chars 为 0，finish_reason 为 length。预判耗时 4.59 秒，未触及 8 秒总预算；
本轮查询没有执行。该证据定位为思考过程耗尽输出预算，不是词条未找到或查询超时。

按主人确认，DeepSeek 百科预判通过 OpenAI SDK 的
`extra_body={"thinking": {"type": "disabled"}}` 显式关闭思考。
识别 DeepSeek 模型名或官方 API 主机，兼容使用 DeepSeek 模型名的代理；
其他模型线路不发送此供应商字段。现有模型、提示词、直接问句规则、512 token、
JSON 字段校验、等待预算与重试次数继续保留。角色聊天不继承预判的思考开关。
日志增加 `query_runs.planner.thinking_mode`，disabled 表示请求发送了关闭参数，
unspecified 表示未发送；这是请求配置，实际是否生效仍需结合返回的 reasoning_tokens 与 content_chars 核对。

默认人格在 DeepSeek 工具调用后继续请求时，保留第一条模型消息返回的原始
`reasoning_content`，与 content、tool_calls 一起回传。空字符串保留，缺失或非字符串不编造。
只在当前请求序列中保留；不添加到持久聊天历史、记忆、公共查询参数或过程日志。
非 DeepSeek 线路不新增此字段。模型第一阶段思考和最终角色回复的配置不受影响。

参数依据：[DeepSeek 思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode)
和 [Chat Completion 接口](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion)。
官方默认启用思考且默认强度 high；低强度不等于关闭，temperature 在思考模式下不生效。
携带 tools 时，官方要求在后续请求中回传 reasoning_content；当前转换函数此前遗漏此字段。
本次补齐同轮工具请求，不将内部思考内容写入长期历史。

离线验证使用实际 SDK 与模拟 HTTP 传输，确认发送到 API 的顶层 JSON 为
`"thinking": {"type": "disabled"}`，而不是嵌套的 extra_body。
真实供应商是否返回有效查询计划、角色是否自然使用资料仍待重新加载代码后实测。
此前发现的查询总预算取消时部分正文丢失、额外候选请求等问题仍留待后续处理。

账号固定人格决定百科方式，与角色使用哪条聊天模型线路分开。
独立人格专用群聊原有 DS 演员线路保持不变，也使用资料预取方式。
SceneHub 仅主人触发的回复允许查询，预判输入仅为主人本次消息；
自主消息不执行查询，不发送私聊连续性内容到预判或百科服务。

## Graph 与维护边界

`graph/encyclopedia.py` 提供可执行百科子图：
准备查询 → 校验参数 → 执行公共百科 → 构建证据。
角色聊天使用独立 `ToolRegistry`，仅注册 `lookup_unknown_slang`。
数组参数经专用校验，MainAgent 的维护工具不进入角色工具集合。

`ask_llm` 在聊天模型工具交互或独立人格资料预取处调用该子图；
因此 ChatGraph、兼容聊天、语义语音和 SceneHub 共用同一执行逻辑。
ChatGraph 将子图观察保留在 `encyclopedia_graph` artifact，
现有聊天路由观察展示方式、状态、触发来源、预判及查询耗时、结果数和缓存命中。
观察不保存本句、候选词、页面正文或私人角色内容。

聊天和 SceneHub 的实际百科尝试还写入既有结构化可靠性记录，组件为 `public_encyclopedia`，
按 `aike_query` / `linyin_query` 区分人格；仅保存固定状态码，不保存检索词、原句、正文或 QQ 标识。
成功、预判空返回/截断/无效 JSON、超时、数据源不可用分别记录；未找到或无正文记录为 skipped，
普通问候、未请求工具和关闭能力不写故障事件。现有故障趋势可查看失败/降级，不新增重复维护入口。
数据库约束与 Python 注册表统一；旧诊断表在下次数据库初始化时事务迁移，
保留全部事件、记录 ID 和自增序列，复制失败回滚。不修改聊天、记忆或表情库数据。

### 每轮过程日志

普通文本聊天与 SceneHub 的角色生成在结束、异常或取消时追加一行 JSON 到
`logs/encyclopedia.log`，时间固定使用北京时间并带 `+08:00`，每轮有独立 `trace`。
关闭百科、未请求工具和预判决定不查也会记录，便于区分“没触发”和“触发后失败”。
日志写入失败不会中断聊天，现有聊天路由观察显示 `log_written` 和诊断位置。

| 字段 | 用途 |
| --- | --- |
| `persona` / `mode` / `trigger` | 默认人格或独立人格，模型工具或预取，明确问句、指令或自动判断 |
| `policy` | 正常启用、场景不允许、开关关闭、线路不支持或配置不完整 |
| `planner_used` / `planner_needed` | 是否执行 DS 预判，预判是否选择查询；直接查询时 needed 为 null |
| `status` / `query_failure_code` / `source_error_types` | 百科阶段结果、最近一次捕获的错误分类、公开源异常类型；不记录原始错误文本 |
| `lookup_attempted` / `evidence_count` / `evidence_provided` | 是否实际执行查询，有效正文是否已放入角色模型请求 |
| `tool_statuses` | 默认人格本轮多个工具请求各自的结果，避免后一条失败掩盖前一条查到的资料 |
| `plan_ms` / `lookup_ms` / `lookup_total_ms` | 预判、外站查询和子图累计耗时；多次工具查询累加 |
| `chat_requests` / `chat_ms` / `chat_route` | 角色模型请求次数、累计耗时及实际线路；不包含 DS 预判请求 |
| `reply_status` / `reply_failure_code` | 角色模型文本生成成功、空文本、异常或取消；不代表 QQ 已送达 |
| `reply_uncertainty_cue` / `location` / `detail` | 回复是否出现“没听过”等措辞、排查阶段及固定中文说明 |

`not_requested` 表示默认人格模型没有调用工具；`not_needed` 表示 DS 决定不查；
`planner_*` 定位预判问题，`not_found` / `no_content` / `lookup_timeout` / `source_unavailable` 定位公共查询。
当有正文已交给模型，而回复仍含陌生或不确定措辞时，标记 `reply_review` 供人工核对。
该标记只是词句线索，不能自动判定资料未被使用或回答错误；消歧和自然角色表达也可能出现这些措辞。
日志不保存问题、检索词、页面正文、模型回复正文、角色卡、记忆、账号或密钥；不增加任何模型请求。

### 模型与查询过程诊断（2026-10-14 补充）

主人要求保留现有直接入口，不再通过扩展关键词或句式来绕过自动查询故障。
本次仅增加诊断，不改变模型、提示词、触发规则、512 token 预判预算、等待时间或重试策略。
记录增加 `schema_version=2`，原有顶层字段继续保留；旧日志不补写或覆盖。

18:47～18:52 的实际日志已经确认：默认人格问薇斯纳时模型调用工具后查询超时；
独立人格问新海天时预判响应被长度截断，没有执行查询。
旧日志无法说明实际请求停在哪一步，也没有预判 usage，不能把截断直接认定为思考 token 耗尽。

每轮增加 `query_runs`（最多两次子图查询）：

| 字段 | 用途 |
| --- | --- |
| `plan_budget_ms` / `lookup_budget_ms` / `source_timeout_ms` | 子图预判总预算、查询总预算及外站 HTTP 超时配置 |
| `timeout_origin` | `plan_deadline` / `lookup_deadline` 表示总预算取消；`operation_timeout` 表示内部操作抛出 TimeoutError；外部取消不冒充预算超时 |
| `planner.max_tokens` / `request_timeout_ms` / `sdk_max_retries` | 本次预判实际请求参数 |
| `planner.thinking_mode` | disabled 表示显式发送关闭思考参数；unspecified 表示未设置；实际返回需核对 usage |
| `planner.finish_reason` / `validation` / `json_valid` | 接口结束原因、程序校验阶段和返回内容能否解析为 JSON；JSON 可解析不代表字段合同有效 |
| `planner.prompt_tokens` / `completion_tokens` / `reasoning_tokens` | 接口实际报告的用量；缺失记为 null，不将未知伪装成零 |
| `planner.content_chars` / `reasoning_chars` | 返回正文与供应商思考字段的长度，不记录内容 |
| `planner.input_chars` / `input_truncated` | 实际送入预判的本句长度，是否受 600 字符限制 |
| `planner.json_error_line` / `json_error_column` | JSON 失败位置，不记录原始 JSON 或异常文本 |
| `candidates` | 最多三个候选的字符数与进程内匿名引用，用于比较两轮是否提取同一候选及顺序 |
| `cache` / `evidence_collected` | 实际缓存状态、查询期间累计取得的正文条数；与顶层 evidence_provided 区分 |
| `requests` | 逐次外站请求，最多 24 条，保留取消前已经完成的请求 |

每条 `requests` 包含候选序号、阶段（`exact` 准确词条、`search` 搜索标题、
`search_page` 读取搜索结果正文）、耗时、完成/错误/取消、HTTP 状态、响应字节数、
内容类型、JSON 类型及固定 API 错误码。另记录页面数、有效正文页数或搜索结果数。
底层传输有 trace 时记录连接、TLS、发送、等待响应头、读取正文的最后阶段及失败阶段；
不读取 trace 中的地址、请求头、缓冲区或异常文本。未提供的传输信息记为 unreported。

`model_requests` 记录角色模型的最多两次请求：是否允许工具、结束原因、工具调用数量、
输出/思考字符数、接口报告的 token 用量及请求耗时，区分“没有请求工具”和“输出被截断，未形成工具调用”。
角色模型记录与 DS 预判分开，不能把两者的用量混为一谈。

候选与模型名使用进程随机密钥计算 HMAC 引用，不记录原词或模型名；引用仅在同一进程中可比较，
重启后会改变。这些引用不能判断候选本身是否正确，也不能替代有针对性的人工语义核对。
所有嵌套字段仍经过封闭白名单，任意正文、未知异常文本及自由格式字段不会写入日志。
上下文按异步任务隔离；预算取消和外部取消都会保留已经采集的过程记录。

离线模拟已复现一个流程缺口：先查到第一候选正文，后续候选超时触发整次预算取消时，
已有正文仍留在服务局部变量中，没有返回给模型。新日志能显示 evidence_collected 大于零而
evidence_provided 为 false。该缺口尚未在本次修改中修复，也不能认定它就是默认人格那次真实超时的原因。

下一次加载新代码后，查看一轮完整记录：

```powershell
Get-Content -LiteralPath 'D:\AIchatbot\logs\encyclopedia.log' -Tail 1 -Encoding utf8 |
    ConvertFrom-Json | ConvertTo-Json -Depth 12
```

排查顺序：先看 `status`、`query_runs.planner`，再看 `timeout_origin` 和逐次 `requests`；
最后核对已取得正文与已交给模型的正文。重试、预算调整、预判恢复或部分证据保留应根据这些证据实施。
新增记录不增加外部请求，本次未重启 Bot、未调用真实模型；修复后的在线稳定性尚未验收。

PowerShell 查看最近记录：

```powershell
Get-Content -LiteralPath 'D:\AIchatbot\logs\encyclopedia.log' -Tail 10 -Encoding utf8 |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Select-Object time, persona, trigger, status, evidence_provided, reply_status, location, detail
```

共享服务位于 `encyclopedia.py`，仅查询固定萌娘百科端点。
候选词先做准确标题及重定向查询，无有效正文时尝试搜索候选标题。
页面存在但正文为空不算有效证据；多义搜索结果仍需角色模型结合本句判断，
不会宣称搜索命中就是唯一正确解释。

公共结果提供标题、正文、来源和查询状态。外部资料按数据传递，
不能覆盖角色、身份或权限，不自动写入人格长期记忆。
聊天请求加入统一证据使用要求：有效且相关的正文应自然用于回答，不能忽略资料只让主人自行解释；
本轮获得的知识不必假装原本就知道。多义词应结合已有作品线索，缺少线索时确认含义，
查询失败时不能声称已核实。不固定角色台词，不用另一人格模型代答。
发送给百科网站的只有必要候选词，原句和语境提示不作为外站参数。
长数字账号、链接、邮箱和明显密钥表达不作为搜索候选。

公共证据采用进程内缓存：最多 128 组，有效期 30 分钟，不写盘。
两个角色可复用词条证据，不能通过缓存共享私人聊天或人格记忆。
缓存只缓存成功公共结果；模型预判仍可能需要执行，重启后缓存清空。

## 配置和等待预算

| 配置 | 默认 | 含义 |
| --- | --- | --- |
| `ENABLE_UNKNOWN_SLANG_TOOL` | true | 兼容原总开关，关闭后两个角色都不查询 |
| `ENABLE_AIKE_ENCYCLOPEDIA` | true | 默认人格明确问句直接查询，其余按需工具查询 |
| `ENABLE_LINYIN_ENCYCLOPEDIA` | true | 独立人格资料预取 |
| `LINYIN_ENCYCLOPEDIA_AUTO` | true | 独立人格普通聊天自动预判；false 时仅明确查询 |
| `ENCYCLOPEDIA_PLAN_TIMEOUT_SECONDS` | 8 | 单次预判完整操作预算，不自动重试 |
| `ENCYCLOPEDIA_LOOKUP_TIMEOUT_SECONDS` | 8 | 一次子图查询总预算，不是每个页面各等 8 秒 |

现有 `.env` 无需写入新字段即可读取这些默认值。本次仅更新示例配置，不修改实际密钥配置。
预算支持 1～30 秒；参数非法或超出范围会停用相应查询能力，
在账号配置中显示不完整，普通角色回复继续执行。
独立人格预判要求现有 `AIKE_LLM_*` 配置完整；未配置时不借用独立人格慢模型做两次回复。
预判请求使用 JSON object 响应格式、512 token 输出预算和严格字段校验；
DeepSeek 预判显式发送 thinking.type=disabled，角色聊天保持原有思考设置；
空响应、截断和合同不符分别降级，无自动重试，不额外调用独立人格模型。

每次子图最多三个候选词、六条结果、合计 8000 字符正文；
默认人格一次模型工具返回最多执行两次查询，之后关闭继续调用工具再生成最终回复。
明确短指令/专名问句只有一个查询预算；默认人格工具阶段最多累积两个查询预算；
独立人格复杂/自动查询最多一个预判预算加一个查询预算。
以上不包含角色最终回复所需时间，不是整轮回复的速度承诺。

查询失败、超时、无正文、无结果及参数错误均有结构化状态。
查询失败不会终止角色回复，但模型不能声称已经查证；
角色模型本身失败仍沿用原聊天失败处理，不换用另一个角色模型代答。

Web 账号配置使用同一能力解析器显示启用、停用、尚不支持或配置不完整，
并显示独立人格资料预判模型、触发范围和预算。
其他能力如表情包仍保留原有角色范围。

## 验收

离线测试使用假模型和假百科服务，验证请求次数、模型选择、查询状态、参数校验、
超时取消、公共缓存、总正文预算、隐私输入、语音元数据和 ChatGraph artifact。
2026-10-14 针对主人验收反馈，使用现有查询代码对五个公共名称进行实际 API 探测，
“超时空辉夜姬”、“尼古猫猫”、“沃雅妮莎”、“奥黛塔”、“牛来”均返回有效正文；
其中“超时空辉夜姬”和“尼古猫猫”分别重定向到“超辉夜姬！”和“尼古喵喵”，奥黛塔命中“奥黛塔·苏佩茜娃”。
这证明当次公共词条可获取，不能证明此前角色查询成功，也不能将重名词条当成主人唯一意图。
证据保存在本地 `tmp/encyclopedia-acceptance-repair-20261014/public-terms-probe.json`。

本轮未启动 Bot、未发送 QQ、未调用真实模型、未迁移实际数据库、未提交推送。
真实模型是否自然使用资料、自动查词质量、接口持续稳定性及最终速度仍待重启后在线验收。
相关后端回归 279 项通过，Web 账号人格展示 5 项通过，TypeScript 检查通过。
扩展检查另外执行 66 项：64 项通过、1 项因 Windows 文件链接能力跳过、1 项已有测试失配。
失配项为 `test_memory_units.SummaryPureUnitTests.test_gap_scene_should_update_uses_creation_final_and_step_thresholds`，
测试调用已移除的 `_should_update`，当前代码改用 `next_gap_scene_take_count`；
实现与测试文件均与本轮开始前哈希一致，单独执行同样失败，本轮记录后不扩大修复范围。
