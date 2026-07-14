# 主人审核的本地表情包库设计（静态与动态）

状态：A1–A4、独立 DeepSeek 有限分类器和 B2 主人私聊自动附带均已实现并通过 QQ live。旧 ChatAgent 内嵌 marker/JSON envelope 方案保持关闭；当前运行配置为远程分类开启、旧 marker shadow 关闭、自动附件开启。2026-07-14 按主人明确指定逐项批准 14 个候选后，正式库为 schema 2、revision 18、enabled 14、disabled 2、invalid 0；剩余 16 个候选继续保留且不参与运行时选择。

日期：2026-07-14。

## 1. 目标

建立一个范围可核对、内容由主人决定、运行时只读、发送次数受限的本地表情包库。

```text
图片只来自本地固定目录。
每个可发送文件都必须经过主人审核。
运行时只读取已批准索引，不扫描任意路径。
ChatAgent 不接触文件路径，也不能下载、生成或修改图片。
主人私聊显式预览与普通回复后的受限自动附带均已单独授权并完成 live 验收。
自动附带只能在正常正文发送成功后运行，分类或图片失败不得修改、替换或重试正文。
QQ 动态、空间、群发和额外主动消息继续延后。
```

## 2. 非目标

第一版不实现：

```text
联网搜索、抓取或下载表情包。
调用 Tavily、浏览器、任意 URL fetch 或图片生成模型。
从用户消息图片、QQ 缓存图片或视觉缓存自动入库。
让 Chat LLM 输出或读取路径、URL、QQ file_id。
修改、覆盖或删除主人原图。
发送视频、合成图或 QQ 动态；受控 GIF/APNG/动态 WebP 属于已实现的本地表情范围。
群聊自动发图、非主人私聊发图、主动私聊或批量发送；当前只允许主人私聊每次最多附带一张。
Owner Console 写接口、Web 审批按钮或自动审批。
把图片、路径或预览内容写入聊天记忆、RAG 或 Agent 任务。
```

## 3. 风险分层

```text
候选检查：本地只读，不发送。
主人批准：主人显式触发的本地写操作。
QQ 发送：主人显式预览，或未来单独批准的普通回复附带发送。
```

图片位于本机不等于允许通过 QQ 发送。只有已批准索引中的精确文件哈希才具有发送资格。

## 4. 本地目录

真实图片和索引保存在 Git 已忽略的 `data/` 下：

```text
data/stickers/
  inbox/                 待审核候选，只允许检查
  approved/              已批准规范化静态/动态文件，运行时只读
  quarantine/            校验失败或撤销批准的文件
  reports/               本地审核报告，不进入聊天、RAG 或 Git
  library.json           已批准索引，不包含绝对路径
```

边界：

```text
不提交图片、真实索引或报告。
不使用 output/、tmp/、logs/、QQ 图片缓存或用户路径作为正式库。
运行时根目录由固定配置推导，不能由聊天文本覆盖。
解析文件必须保持在 approved 根目录内。
符号链接、目录联接、UNC、盘符跳转和路径穿越一律拒绝。
```

## 5. 文件准入

候选检查和 A3 规范化批准接受静态与受控动态栅格图片：

```text
静态允许：PNG、JPEG、静态 WebP，单文件上限 2 MiB。
动态候选允许：GIF、APNG、动态 WebP，单文件上限 5 MiB。
拒绝：SVG、ICO、BMP、视频和未知格式。
宽高：32 至 2048 像素。
总像素：不超过 4,194,304。
动态最大帧数：120。
动态最大时长：10 秒。
最小单帧时长：20 ms。
动态总解码像素：不超过 60,000,000。
```

校验必须读取魔数并真实解码，不能只信扩展名或 MIME。损坏、截断、异常色彩模式、压缩炸弹或无法确定帧数的文件全部 fail closed。

动态 WebP 的逐帧时长由受限 RIFF/ANMF 解析读取，因为 Pillow 12 不暴露该字段；块长度、帧数或时长不一致时拒绝。代表帧最多 6 张，在内存中选择首帧、四分位帧、末帧和变化较大帧，组成 PNG 联系表，不写临时帧文件。

主人批准时生成规范化副本：静态图修正方向、移除 EXIF/GPS/文本 metadata 并统一编码 PNG；GIF/APNG/动态 WebP 逐帧解码后按原动画类型重新编码，保留总时长、可见变化与 loop 语义。编码器可以合并连续相同画面，因此最终帧数允许少于源容器帧数，但不得丢失动画属性或改变总时长；manifest 记录最终真实帧数。最终字节重新执行 metadata、格式、帧数、时长、像素与大小预算并计算 SHA-256。检查、分析和草稿命令不得隐式生成副本。

## 6. 已批准索引

`library.json` 建议结构：

```json
{
  "schema_version": 2,
  "library_revision": 1,
  "stickers": [
    {
      "sticker_id": "aike_happy_001",
      "relative_file": "aike_happy_001.png",
      "sha256": "64 个小写十六进制字符",
      "source_sha256": "主人确认候选的 64 位源哈希",
      "media_type": "image/png",
      "width": 512,
      "height": 512,
      "bytes": 123456,
      "animated": true,
      "frame_count": 24,
      "duration_ms": 1440,
      "persona_key": "aike",
      "moods": ["happy"],
      "intensity": "medium",
      "actions": ["smile"],
      "usage_tags": ["greeting", "affection"],
      "scope": "owner_private",
      "enabled": true,
      "approved_at": "合法 ISO 8601 时间",
      "approval_source": "owner_local_command"
    }
  ]
}
```

运行时重新检查 schema、唯一安全 ID、单层相对文件名、最终与来源 SHA-256、格式、尺寸、字节数、动态属性、固定情绪/强度/动作/场景、当前角色、owner-private scope 和 enabled。未知枚举、重复 ID、重复文件、重复最终/来源哈希或任意不一致只拒绝对应条目，不扩大读取范围。schema v2 用于新批准；旧 schema v1 静态索引继续只读兼容，不由 A3 自动迁移。

索引不保存绝对路径、URL、QQ file_id、用户消息、聊天回复、审核备注正文、API Key、数据库 ID 或 RAG 内容。

## 7. 主人审核流程

建议入口名称只代表设计意图，实现前仍需核对现有命令空间。

### 7.1 `/表情检查`

仅主人私聊；只扫描 inbox 直接子文件；返回候选 ID、格式、尺寸、字节数、短哈希和拒绝类别；不移动、不改写、不批准、不发送。

A2 已实现该入口：总开关默认关闭；模块只显示 `candidate_<12位短哈希>`，不显示文件名、绝对路径或完整哈希。缺少 inbox 时明确报告且不自动创建；直接子项超过 200 个时整体拒绝扫描；报告最多展开 30 项。

### 7.1.1 `/表情分析 <candidate_id>`

仅主人私聊、总开关与本地视觉均开启时可用。入口只接受 `/表情检查` 返回的 `candidate_<12位短哈希>`，重新扫描固定 inbox、复核路径和完整哈希、按动态预算解码，在内存中生成联系表，再调用固定本地 Ollama JSON prompt。它返回情绪、三级强度、动作、兼容场景和三类置信度建议；不显示路径，不写正式标签，不批准或发送图片。

情绪低于 0.85、强度低于 0.75、场景低于 0.70，或包含 mixed/ambiguous 时标记“需要主人复核”；高置信度也只标记“待主人确认”。AI 建议永远不作为正式 manifest 标签，A3 必须使用主人确认结果。

### 7.2 `/表情候选预览 <candidate_id>`

这是显式 QQ 外部写操作。仅主人私聊，每次一张，不重试、不连发；发送前重新验证 inbox 根目录和候选哈希。

### 7.3 `/表情批准 <candidate_id> <短哈希确认>`

仅主人私聊严格命令。候选必须存在于本地 `reports/approval-drafts.json`，草稿必须带完整源哈希、唯一 sticker ID、白名单标签和 `owner_confirmed=true`；命令中的 12 位确认必须与 candidate ID 完全一致。批准时重新解析当前候选并匹配完整源 SHA-256，再生成无 metadata 规范化副本，写入 approved 并原子更新 schema v2 索引。批准成功只返回安全 ID、revision、动态摘要和最终短哈希，不自动发送，也不自动启用普通聊天选择。错误确认、候选替换、重复来源、无效草稿、预算失败或 manifest 失败均不得形成有效条目；manifest 失败时清理本轮新文件。

### 7.3.1 `/表情草稿`

仅主人私聊只读。显示草稿 revision、数量、candidate ID、未来 sticker ID、情绪、强度和场景，不显示源/最终完整哈希、文件名或路径。真实 32 条主人确认草稿已生成；草稿本身不是批准。

### 7.3.2 `/表情撤销 <sticker_id> <最终短哈希确认>`

仅主人私聊严格命令。重新加载并完整校验 schema v2 manifest，sticker ID 和最终文件 12 位短哈希都必须精确匹配；原子递增 revision 并把 `enabled` 改为 false。第一版不删除或移动规范化文件，避免误删并保留审计依据；disabled 条目不可被运行时选择。

### 7.4 `/表情预览 <sticker_id>`

已实现，仅主人私聊。严格接受一个安全 sticker ID；重新加载并完整校验正式 manifest，要求条目 `enabled=true`，再在发送前复核目标文件的最终哈希、MIME、尺寸、字节、metadata、动画属性、帧数和总时长。每条命令只调用一次 OneBot `send_private_msg`，用 `MessageSegment.image` 发送该正式本地文件；3 秒主人级冷却。成功只发送图片，不追加文字；失败返回固定安全类别，不 retry、不换图、不随机选择，也不调用 ChatAgent、MainAgent、Tavily、视觉模型、RAG、数据库或 Agent 任务。disabled 条目在冷却检查前即拒绝，不消耗图片发送机会。

撤销批准已实现为独立主人写命令并标记 disabled；不能由普通聊天或模型触发。

## 8. 运行时加载

建议新增独立纯模块 `sticker_library.py`，只负责固定根目录、manifest 解析、不可变 `StickerAsset`、路径/哈希复核和无路径安全计数。

```text
ENABLE_LOCAL_STICKERS 默认 false。
缺目录、缺索引、索引损坏、哈希不符或依赖缺失时安全关闭。
表情库失败不得阻止 Bot 文本聊天启动。
配置 repr、状态页和日志不显示文件名、路径或完整哈希。
不使用文件监控。显式预览在每次命令时重新加载 manifest；B2 在每次远程分类完成后重新加载 manifest 再做本地选择，因此批准或撤销资产不需要单独重启 Bot。
```

## 9. QQ 发送边界

第一阶段必须同时满足：主人私聊、严格预览命令、全局开关打开、条目已启用且 owner-private、当前文件复核通过、单次尚未发图、冷却通过。

OneBot 只使用已批准本地文件的 `MessageSegment.image`，禁止 HTTP URL、用户路径、QQ 临时 URL 或模型路径。

```text
每个命令最多 1 张。
无 retry，无替代图片 fallback。
主人预览冷却 3 秒。
未来普通聊天自动附带冷却至少 120 秒。
失败只记录安全错误类别，不记录路径、图片或原始异常。
```

## 10. ChatAgent 自动选择：第二阶段

本节同时记录 B1/B2 的演进过程和当前最终边界。第一阶段曾只允许显式审核与预览；当前 B2 已经单独授权，仅允许正常正文发送成功后的主人私聊受限自动附带。

B1 首版使用严格末尾标记承载 `attach`、单个 `mood`、`intensity`、`scene` 和 0–1 `confidence`。主人 QQ shadow live 发现当前 `deepseek-v4-flash` 在完整角色卡下会省略标记；标记缺失时正文仍可原样返回，因此该版本只失去表情建议，不影响正常聊天。

曾尝试改为同一次 ChatAgent 调用的 JSON object envelope。当前 DeepSeek 兼容接口支持 `response_format={"type":"json_object"}`，但不支持严格 `json_schema`；最小探针可返回 `reply/sticker_intent`，真实长会话却连续产生空或不合格的可见 reply，触发普通聊天固定兜底。该方案违反“表情功能失败不得影响文本回复”的优先边界，已从主链完整回退，不能通过放宽控制对象校验继续使用。

当前旧 B1 marker shadow 默认并实际关闭，主 ChatAgent 保持普通文本输出；旧末尾标记解析器只保留为有限实验代码，不再注入运行中的聊天。后续采用的独立分类器与完整正文解耦：无论分类超时、错误、缺失或低置信度，已经生成并发送的正常文本都保持不变。

主人随后选择使用第二个 DeepSeek API Key 建立完全解耦的远程分类器。新增 `sticker_classifier.py`，只在完整 owner-private 文本回复已成功发送后异步调用固定 HTTPS OpenAI-compatible endpoint；ChatAgent 继续使用原 Key，分类器只使用 `STICKER_CLASSIFIER_API_KEY`，禁止缺失时回退到聊天 Key。分类请求只包含本轮有限长度的用户文本和最终回复，不包含历史、QQ 号、角色卡、记忆、RAG、图片、文件、路径、哈希或 sticker ID。

远程分类合同仍只有 `attach/mood/intensity/scene/confidence`。客户端固定 temperature=0、JSON object、180 token 上限、8 秒默认超时、`max_retries=0`；只接受 HTTPS、显式安全模型名和 1–5000 字输入预算。额外字段、未知枚举、非布尔 attach、非法 confidence、过大/空/非 JSON 输出全部 fail closed。分类后台任务最多同时存在一个；忙碌、鉴权、限流、超时、无效响应或内部错误只更新内存 shadow 状态，绝不修改、重发或替换正文。

首次独立 DeepSeek `deepseek-v4-flash` 手动探针通过：明确卖萌得到 `playful/medium/acting_cute`、confidence 0.95；日期事实得到 `not_requested`。该探针不经过 QQ、不写历史、不调用 Tavily/MainAgent/RAG。此后主人先后明确授权 owner-private 远程 shadow 与 B2 发送；当前实际配置为 `ENABLE_REMOTE_STICKER_CLASSIFIER=true`、旧 marker shadow=false、attachments=true。

主人随后授权打开 remote classifier shadow，并于 2026-07-14 完成 QQ live：日期事实为 not_requested 且无匹配，明确卖萌为 requested + `playful/medium/acting_cute` + 0.95，并由本地精确选中 `aike_act_cute_001`。两轮均先发送完整正常正文，分类结果只进入内存状态，attachments=false，因此没有图片。该结果验证 C1 主链，不自动构成 B2 外部写授权。

主人之后明确授权 B2 owner-private 自动附带。B2 只在完整文字已发送后工作；选中资产重新执行 A4 同级安全复核，每回复只允许一次 private image API，失败不重试、不替代，只有发送成功才提交冷却和 shuffle-bag。首轮 QQ live 成功按“文字 → 动态 GIF”顺序发送 `aike_act_cute_001`，状态显示 0.95、selected、attachment sent。主人随后表示不喜欢该 GIF，使用正式撤销语义把条目设为 disabled；library revision 4、enabled 0、disabled 2、invalid 0。撤销当时库内没有 enabled 资产，B2 只能 no_match。2026-07-14 主人又明确指定并逐项批准 14 个候选，当前 enabled 资产为 14 个；撤销默认仍保留规范化文件以支持审计，物理删除需要单独不可逆授权。

本地选择要求 owner-private、正式库无 invalid、条目 enabled、当前 persona/scope 匹配、mood/intensity/scene 三字段精确匹配且 confidence 至少 0.82。频率采用确定性硬门控：至少 120 秒冷却、至少 4 条消息间隔、每小时最多 6 张、每回复最多 1 张。同类候选使用内存 shuffle-bag，袋内用完前不重复；只有未来图片实际发送成功后才提交冷却、小时计数和袋消费，shadow 决策不消费状态。

B2 自动附件开启时，在创建远程分类任务前先执行纯本地频率预检。若当前命中 120 秒冷却、4 条消息间隔、每小时上限或附件熔断，则直接跳过本轮表情分类模型，不发送图片、不消费分类 token；正文仍已正常发送和持久化，因此消息进度会继续增长，后续可以自然解除 message-gap 门控。预检不读取意图、不加载图片或 manifest、不消费 shuffle-bag，也不提交任何发送状态；预检异常时 fail closed，跳过分类且不影响正文。仅开启 C1 shadow、自动附件关闭时不应用此优化，继续保留分类观察能力。

建议配置全部默认关闭：

```text
ENABLE_CHAT_STICKER_ATTACHMENTS=false
ENABLE_CHAT_STICKER_INTENT_SHADOW=false
CHAT_STICKER_OWNER_PRIVATE_ONLY=true
CHAT_STICKER_COOLDOWN_SECONDS=120
CHAT_STICKER_MIN_MESSAGES_BETWEEN=4
CHAT_STICKER_MAX_PER_HOUR=6
CHAT_STICKER_MAX_PER_REPLY=1
CHAT_STICKER_MIN_INTENT_CONFIDENCE=0.82
```

## 11. 能力隔离

```text
ChatAgent：第一阶段不可自动选择表情包。
MainAgent：不注册表情包工具，不读取图片、索引或路径。
Tavily：不查询或下载图片。
MemoryRAG：不写入图片、路径、哈希或发送记录正文。
ProjectDocRAG：只索引设计文档，不索引 data/stickers。
视觉链：不自动识别候选，不把 QQ 收图转为表情包。
Owner Console：继续 GET-only，不增加审核写接口。
QQ 动态：继续作为独立高风险外部写操作延后。
```

## 12. 可观测性

只记录开关、ready、schema、approved/disabled/invalid 计数、reload 类别、发送尝试/成功计数和安全失败类别。不记录路径、文件名、图片、完整哈希、用户消息、回复正文、OneBot 原始异常或临时 URL。

第一阶段不创建 Agent 工作任务；显式预览属于主人 QQ 管理命令，不进入 MainAgent work runtime。

## 13. 测试与 live

纯测试覆盖：格式/单帧/尺寸/像素/字节，伪扩展名、损坏、压缩炸弹、metadata，路径穿越/链接/UNC，schema/重复/哈希/原子更新，默认关闭和 repr 脱敏，非主人/群聊/普通聊天/MainAgent 不发送，单张/冷却/无重试，以及日志无路径正文。

集成测试只使用临时目录和假 OneBot sender，不读取真实库、不发送 QQ。

已完成的关键 QQ live：

```text
显式预览：已批准动态 GIF 经 NapCat/OneBot 正确接收并播放。
远程 shadow：日期事实得到 not_requested；明确卖萌得到 playful/medium/acting_cute 0.95，均不影响正常正文。
B2 自动附带：明确卖萌先收到正常正文，随后收到一张动态 GIF；图片成功后才提交频率状态。
```

上述 live 均确认 Agent 任务和 Tavily 请求没有增加。下一轮验收应覆盖偷看/参与聊天、震惊、请求/撒娇、喜欢、记录和困倦样本，并观察 shuffle-bag、120 秒冷却、4 条消息间隔和每小时 6 张上限是否符合体感。

## 14. 推荐实施顺序

```text
A1. 配置、数据类、manifest parser、路径/哈希/图片校验。
A2. 主人候选检查和安全报告，不写文件、不发 QQ。
A3. 主人批准与规范化副本，原子写索引。
A4. 主人显式预览，假 sender 回归后做一次 QQ live。
A5. 安全状态，只展示计数和类别。
B1. 单独设计 ChatAgent 语义意图合同。
B2. 主人明确批准后才打开 owner-private 自动附带测试。
B3. live 稳定后再讨论范围；群聊和非主人不默认开放。
```

A1、A2 和动态标签建议骨架已按主人确认完成。32 个真实候选全部通过安全扫描并完成人工辅助初判和主人语义确认。第 1 个定义为“卖萌 / 中等”，第 3、4 个共用“探头/围观”场景，第 6 个兼容“撒娇/拜托”。固定合同已补充卖萌、探头、展示爱心、双手合拢、感叹号及对应受控场景，并增加避免默认 `neutral/embarrassed` 的视觉证据规则。

校准后复跑只部分改善，本地 3B 模型仍对部分候选产生明显误判，因此没有使用无人复核批量定标。A3 据主人确认结果生成 32 条唯一严格草稿；其中最初逐项批准 2 个并撤销 2 个，2026-07-14 又按主人指定序号逐项批准 14 个，形成 revision 18、enabled 14、disabled 2、invalid 0。其余 16 个候选未批准、未移动、未删除；未经新的逐项主人命令仍不得生成规范化副本或进入自动发送。
