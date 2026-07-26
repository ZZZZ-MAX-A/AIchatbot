# Owner Console 阿里云百炼固定线上视觉诊断设计与配置说明

## 1. 文档状态

| 字段 | 当前值 |
|---|---|
| 设计日期 | 2026-07-26（Asia/Shanghai） |
| 设计状态 | `owner_approved_design`、`designed` |
| 实现状态 | `owner_approved`、`implemented`、`regression_passed` |
| 配置状态 | `configured_privately`、`owner_console_loaded`、`bot_loaded` |
| 真实调用状态 | 隔离固定样本、Owner Console 页面与两张 QQ 生产图片均 `live_passed`、`owner_accepted` |
| 当前授权 | 当前 live 已完成；不自动重复图片请求或扩大测试 |

本文定义一个独立的 Owner Console 手动诊断，用同一张固定表情 PNG 请求阿里云百炼北京地域视觉模型，判断线上视觉模型能否返回可读、且经主人对照图片确认准确的自然中文描述。

本文最初的分阶段方案已由主人后续逐步批准扩展：先完成三次隔离固定图片请求并接受第三次回复，再批准生产 `describe_images()` 改用百炼以及 Owner Console 原位面板替换。2026-07-27 Owner Console 加载后页面由主人确认无问题；Bot 随后加载生产主链，主人连续发送两张 QQ 图片，均快速获得准确描述，结构化事件记录两次成功。当前实现、页面和 QQ 生产路径均已验收。

## 2. 背景与问题

本地 `workflow=vision_managed_lifecycle` 已证明以下技术链真实可运行：

- 固定 PNG 可以送入本机 Ollama；
- `qwen2.5vl:3b` 可以完成一次图片推理并返回自然中文；
- 调用前未驻留的模型可以通过 `keep_alive=0` 和有界 `/api/ps` 轮询确认释放；
- 诊断不自动重试、不停止原有 Ollama、不调用 QQ、RAG、TTS 或 Main LLM。

但固定正式表情的两次主人质检均未达到内容质量要求。自然描述版最近一次运行的技术结果为 `succeeded/vision_managed_lifecycle_succeeded`，主人最终审核结果为 `failed/owner_visual_review/vision_response_quality_rejected`。模型把黑白双色长发误认为黑帽子和披风，把清晰可见的眼睛误认为被爱心遮住，并对被大爱心遮挡的嘴部作了无依据描述，还把透明背景描述为纯黑背景。

这说明当前主要问题不是 JSON Schema、请求能否完成或模型能否释放，而是本地 3B 视觉模型对复杂、透明背景的二次元表情图片描述质量不足。线上诊断用于隔离并观察“同一固定图片换成线上模型后，内容描述质量是否改善”。

## 3. 诊断目标与非目标

### 3.1 目标

该诊断只回答四个问题：

1. 固定的阿里云百炼北京地域 endpoint、Workspace 和凭据是否可用。
2. 固定模型能否在一次请求内完成固定 PNG 的基础视觉描述。
3. 返回内容是否满足有限的技术合同：非空、可读、无工具调用、非重复乱码且 usage 可核对。
4. 主人对照同一固定参考图后，是否接受本次中文描述质量。

### 3.2 非目标

该诊断不能证明：

- 任意聊天图片、截图、照片、OCR、动态图或多图理解质量；
- Main LLM 或 MainAgent 能否正确选择视觉工具；
- QQ 图片下载、缓存、发送或生产聊天视觉链正常；
- 本地 Ollama、GPU、`qwen2.5vl:3b` 或模型资源收口正常；
- 阿里云长期稳定性、并发能力、SLA、配额或月度成本上限；
- 图片内容不会被云厂商处理或留存；应用无法控制供应商侧处理与留存策略；
- 线上模型能进行 RAG 索引、MemoryRAG、ProjectDocRAG 或任何数据库操作。

## 4. 独立工作流与状态边界

新增工作流建议固定为：

```text
workflow=cloud_vision_fixed_description
provider=aliyun_bailian
region=cn-beijing
```

它必须独立于现有：

```text
workflow=vision_managed_lifecycle
```

两者诊断对象不同：

| 工作流 | 被诊断对象 | 可以证明 | 不能证明 |
|---|---|---|---|
| `vision_managed_lifecycle` | 本地 Ollama、固定本地视觉模型及其资源生命周期 | 本地服务、一次推理、模型驻留与释放 | 线上供应商、云凭据、互联网链路 |
| `cloud_vision_fixed_description` | 阿里云百炼固定 endpoint、固定模型和一次线上请求 | 云配置、鉴权、单次请求、固定图片回复与主人质检 | 本地 GPU/Ollama、QQ 生产链、工具选择 |

云端工作流通过不能把本地工作流改写为通过；本地工作流失败也不能自动触发云端调用。两个工作流不得自动串行、并行或互相 fallback。

## 5. 供应商、地域、模型与成本合同

### 5.1 第一候选

第一版固定使用：

```text
provider=aliyun_bailian
region=cn-beijing
model=qwen3.7-flash
enable_thinking=false
```

选择理由：

- 百炼提供 OpenAI-compatible 多模态接口，可用 `image_url` 发送 Base64 Data URL；
- 北京地域适合当前国内运行环境，Workspace、API Key 与 endpoint 的地域关系可以固定校验；
- `qwen3.7-flash` 支持视觉输入，非思考档刊例单价低，适合作为固定、低频、主人手动诊断；
- 固定关闭思考可以减少输出 token、成本和诊断变量。

### 5.2 费用估算

根据 2026-07-25 核对的阿里云百炼官方模型价格页，`qwen3.7-flash` 低输入档非思考价格为：

```text
input: 0.20 CNY / 1M tokens
non-thinking output: 0.80 CNY / 1M tokens
thinking output: 4.80 CNY / 1M tokens
```

以官方视觉示例量级约 1270 输入 token、诊断最多约 100 输出 token 粗估：

```text
单次约 0.000334 CNY
1000 次约 0.334 CNY
```

这是设计估算，不是账单承诺。图片 token、模型版本、阶梯价格、免费额度和厂商调价都会改变实际费用。页面应显示本次 provider 返回的 token usage；不在客户端伪造精确金额，也不自动累计或写数据库。

### 5.3 第二候选与禁止自动降级

只有 `qwen3.7-flash` 完成主人 live 且描述质量仍被拒绝后，才可以另行讨论：

```text
model=qwen3.7-plus
```

`qwen3.7-plus` 的刊例价约为输入 2.00 CNY/1M、输出 8.00 CNY/1M，按同一 token 假设约 0.00334 CNY/次。它不是第一版配置，也不得作为隐藏 fallback。切换模型会改变被诊断对象，必须单独批准、实现和验收。

### 5.4 官方资料入口

- [阿里云百炼模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)
- [阿里云百炼视觉理解](https://help.aliyun.com/zh/model-studio/vision)
- [阿里云百炼获取 API Key](https://help.aliyun.com/zh/model-studio/get-api-key)
- [阿里云百炼通过环境变量配置 API Key](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)

价格和能力必须在实际实现或 live 前重新查看官方页面；本文记录的是设计日期时点，不把别名、价格或能力视为永久事实。

## 6. 固定输入合同

### 6.1 固定图片

第一版继续使用已经登记并由主人可见的正式静态表情：

```text
sticker_id=aike_affection_005
scope=owner_private
media_type=image/png
width=500
height=500
bytes=162977
sha256=1b0db22d21fc7ed998cec9da0568c0987ccf9738eea69bf5c8c436609bfed249
```

每次请求前必须按现有固定资产合同校验 manifest、启用状态、scope、普通文件边界、路径、文件名、MIME、尺寸、字节数和 SHA-256。任何漂移都在外发前失败，不回退到其他图片。

第一版发送原始 PNG 字节，不做缩放、裁剪、透明背景合成或中间文件写入。这样本地与云端使用相同输入，主要变量保持为 provider/model。以后若要测试“透明背景合成到白底”，必须建立新的固定图片合同，不能静默改变本工作流输入。

### 6.2 固定问题

最终经主人接受的固定自然中文问题为：

```text
请用80至150字的自然中文，描述这张图片中明确可见的内容，并概括它传达的情绪或感情色彩；可以结合人物表情、动作和画面元素判断，但不要猜测被遮挡或无法确认的细节。
```

页面、HTTP body、配置文件和环境变量均不能覆盖 prompt。prompt 不写人物、发色、眼睛、爱心或背景答案，不要求 JSON Schema，不评价模型工具选择；允许模型根据明确可见的表情、动作和画面元素概括情绪或感情色彩，但明确禁止猜测遮挡和无法确认的细节。

### 6.3 固定请求参数

```text
model=qwen3.7-flash
stream=false
temperature=0
max_tokens=256
enable_thinking=false
tools omitted
client_max_retries=0
request_count=1
request_timeout_seconds=60
```

图片使用 OpenAI-compatible content block：

```json
{
  "type": "image_url",
  "image_url": {
    "url": "data:image/png;base64,<fixed image>"
  }
}
```

Base64 内容只能在请求内存中短暂存在，不进入 DTO、页面、日志、异常文本、测试快照或持久化文件。

## 7. 配置说明

### 7.1 主人需要提供的环境变量

实际只新增两个敏感或部署相关字段：

```dotenv
ALIYUN_BAILIAN_BASE_URL=
ALIYUN_BAILIAN_API_KEY=
```

不要把真实值写入 `.env.example`、文档、Git、启动参数、PowerShell 历史示例、页面或日志。配置完成前保持空值；本文不要求主人现在创建或提供凭据。

不要复用以下现有密钥字段：

```text
MAIN_LLM_API_KEY
CHAT_LLM_API_KEY
OPENAI_API_KEY
STICKER_CLASSIFIER_API_KEY
```

独立凭据可以避免把 Main LLM 或其他能力的权限范围扩大到云端图片诊断，也便于后续单独撤销与轮换。

### 7.2 固定代码配置

以下内容应写入后端固定合同，不提供页面、HTTP body 或通用环境变量覆盖：

```text
provider=aliyun_bailian
region=cn-beijing
model=qwen3.7-flash
enable_thinking=false
temperature=0
max_tokens=256
request_timeout_seconds=60
client_max_retries=0
```

Base URL 由主人从北京地域 Workspace 的 OpenAI-compatible 地址复制，但后端只接受以下严格格式，不接受 Anthropic URL、其他地域、任意 host/path、query 或 fragment：

```text
https://ws-<lowercase-id>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

Base URL 不属于 API Key，但仍不返回页面或日志。页面只展示 `workspace_configured=true|false`，不展示原值、长度、前后缀、hash 或掩码。

### 7.3 API Key 处理

API Key 必须：

- 配置对象使用 secret 类型，并设置 `repr=False`；
- 不进入 dataclass/model 的普通序列化；
- 不进入异常消息、HTTP DTO、页面、日志或测试 snapshot；
- 页面只展示 `credentials_configured=true|false`；
- 不显示长度、前后缀、hash、掩码或供应商返回的鉴权正文；
- 401/403 只映射到固定错误码，不能透传原始响应。

### 7.4 显式启用

启动脚本已经扩展为：

```powershell
.\scripts\start-owner-console.ps1 -EnableCloudVisionProbe
```

它只设置：

```text
OWNER_CONSOLE_CLOUD_VISION_ENABLED=true
```

存在 URL/API Key 不代表启用；启用也不代表自动执行。固定诊断请求仍必须由主人在页面第一次点击进入确认、第二次明确确认后才发送一次。

### 7.5 当前配置与后续加载步骤

主人已在私密 `.env` 中填写 `ALIYUN_BAILIAN_BASE_URL` 与 `ALIYUN_BAILIAN_API_KEY`，并通过隔离脚本完成固定样本验证。代码和页面只读取配置状态，不打印 Key 或 URL 原值。

Owner Console 加载步骤已经完成：PID 15220 监听 `127.0.0.1:8090`，页面/health 为 200，五个 workflow 与 28 条路由启用，URL/Key 配置布尔值为 true，云最近结果为空。后续按以下顺序操作：

1. 再次确认 `.env` 中 URL 仍为北京地域 OpenAI-compatible Workspace 地址，Key 仍有效；不要把值贴入页面、日志或对话。
2. 主人打开页面检查原位替换后的云视觉面板；页面加载和普通 GET 不发送图片。
3. 若主人决定执行固定诊断，先阅读外发说明，再第二次确认；这会产生一次百炼请求。
4. 单独决定是否重启 Bot 以加载生产 `describe_images()` 云视觉主链；Bot 重启后，进入该函数的图片可能自动外发百炼，不能把它视为单纯页面变化。
5. 生产 QQ 图片集成验收需独立安排；不再使用时由主人手动撤销或轮换 Key、关闭诊断开关并决定是否重启。

配置前还应在官方控制台确认服务已开通、当前模型在北京地域可用、账户有可用额度，并重新核对价格。缺额度、模型下线或地域不匹配都应作为配置/请求失败处理，不得为了跑通而静默改地域、模型或 endpoint。

### 7.6 模型版本漂移

`qwen3.7-flash` 是产品别名，供应商未来可能更新其指向。实现前应重新核对官方文档是否提供仍可用的具体快照模型名：若存在并适合固定诊断，应在主人确认后固定快照；若继续使用产品别名，结果必须显示 provider 实际返回的 model 字段，并把供应商升级造成的质量变化列为已知变量。任何别名到快照、Flash 到 Plus 的切换都改变被诊断对象，需要文档、测试和主人验收，不能由运行时自动完成。

## 8. 外发、网络与隐私边界

本工作流与本地视觉诊断最重要的差异是：它会把一张 `scope=owner_private` 的固定 PNG 发送到外部云服务。确认文案必须明确写出：

> 本次会把固定 owner_private 表情 PNG 发送到阿里云百炼北京地域，进行一次 qwen3.7-flash 图片描述请求。应用无法控制供应商侧的数据处理与留存策略。

结果证据至少包含：

```text
external_image_upload_planned=true
external_image_upload_executed=true|false
provider_side_persistence_controlled_by_app=false
```

网络客户端固定要求：

```text
HTTPS only
fixed cn-beijing host suffix and compatible-mode path
follow_redirects=false
trust_env=false
client_max_retries=0
bounded connect/read/write/pool timeout
bounded response bytes
```

`trust_env=false` 用于避免静默继承环境代理。若以后确需代理，必须作为独立配置和威胁边界设计，不能为了请求成功而自动打开。

诊断不得读取或发送：

- QQ 临时图片、聊天图片缓存或用户上传；
- 其他表情资产、任意本地路径或任意 URL；
- 聊天历史、MemoryRAG、ProjectDocRAG、DevContext 或 CombinedRAG 内容；
- 主人标识、QQ 标识、对话文本、数据库行或项目文档。

## 9. Owner Console 页面与 HTTP 合同

### 9.1 页面

实际 UI 不增加第六个视觉面板，而是原位替换旧的本地视觉配置/诊断面板，标题与固定对象为：

```text
阿里云百炼固定图片识别
```

页面只展示固定 provider、地域、模型、图片 scope、URL/Key 是否已配置、外发说明、固定参考图、清理后的最近回复、`response_cleanup_applied`、input/output/total token、请求耗时和主人审核状态。不得提供：

- 图片上传、路径、URL 或表情选择；
- 自由 prompt、model、endpoint、temperature、token、工具或参数输入；
- “自动选择模型”“失败后改用 Plus”“连续测试”按钮；
- API Key 或 Workspace ID 查看、编辑和保存功能。

### 9.2 固定执行 POST

建议路由：

```text
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description
X-Owner-Console-Action: manual-cloud-vision-fixed-description-v1
Content-Type: application/json
```

精确 body：

```json
{
  "confirmation": "run_registered_cloud_vision_fixed_description"
}
```

沿用 Owner Console 的 loopback Host、同源 Origin、动作 Cookie、精确 Header、精确 JSON body、无额外字段与全局运行锁合同。第一次点击只展示确认信息，零 POST；第二次确认恰好发送一个 POST。其他手动诊断忙时返回 409，不排队、不延迟自动执行。

### 9.3 固定参考图预览

建议独立路由：

```text
GET /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/reference-preview
X-Owner-Console-Action: manual-cloud-vision-reference-preview-v1
Cache-Control: no-store
Content-Type: image/png
```

该路由不接受 path、URL、sticker ID、run ID 或 query 参数，只能重新校验并返回固定参考 PNG。它不调用百炼。

### 9.4 主人接受与拒绝

基础技术合同通过后必须先进入主人质检，不直接显示最终成功。接受/拒绝使用两个固定 POST，并绑定当前 `run_id`。审核动作只更新当前 Owner Console 进程内结果，不再次请求 provider，不写数据库、reliability、文件或聊天历史。

建议语义：

```text
accept: accept_latest_cloud_vision_response_quality
reject: reject_latest_cloud_vision_response_quality
```

错误 run、过期结果、重复审核、缺 Cookie/Header、额外 body 字段或其他诊断运行中均 fail closed。

## 10. 自动合同与主人语义质检

### 10.1 自动基础合同

自动层只验证：

- HTTP/API 请求正常完成，响应 envelope 可解析；
- assistant 自然文本非空且最多 2048 字符；
- 清除有限控制字符与双向控制符后仍至少包含 8 个汉字；
- 不是空白、重复单字、重复标点或其他低信息乱码；
- 没有 tool call，`tool_definitions_sent=false`；
- usage 存在且 input/output/total token 为非负整数、关系自洽；
- 本次 `request_count=1`，客户端没有自动重试。

自动层不判断人物、头发、眼睛、爱心、背景或情绪是否准确，也不使用第二个 LLM 充当裁判。基础合同通过后的中间结果固定为：

```text
outcome=attention
stage=owner_visual_review
code=cloud_vision_response_quality_review_required
```

### 10.2 主人对照检查

页面应同时显示固定参考图和完整有限模型回复。主人至少检查：

- 是否识别为单个二次元/卡通人物；
- 是否看出主要是黑白双色长发，而不是黑帽子与披风；
- 是否看出粉红红色眼睛清晰可见，而不是被爱心遮住；
- 是否看出双手抱着下方大爱心，周围还有多颗爱心；
- 是否避免猜测被大爱心遮挡的嘴型或嘴角；
- 是否避免把 PNG 透明区域当作实体纯黑背景。

这份检查表只展示给主人，不放入发给模型的 prompt，也不作为隐藏的自动关键词合同。它用于判断描述是否忠于实际可见内容，而不是要求逐字复述标准答案。

主人拒绝：

```text
outcome=failed
stage=owner_visual_review
code=cloud_vision_response_quality_rejected
```

主人接受：

```text
outcome=succeeded
stage=result_validation
code=cloud_vision_fixed_description_succeeded
```

若底层已有鉴权、usage、延迟或合同 attention，主人接受语义质量不能覆盖底层问题。

## 11. 结果证据合同

建议 DTO 和页面保留以下英文证据：

```text
workflow
stage
code
provider=aliyun_bailian
region=cn-beijing
configured_model=qwen3.7-flash
endpoint_contract_valid
workspace_configured
credentials_configured
external_image_upload_planned=true
external_image_upload_executed
provider_side_persistence_controlled_by_app=false
cloud_vision_called
request_count
client_automatic_retry=false
tool_definitions_sent=false
thinking_enabled=false
response_mode=natural_text
structured_output_requested=false
semantic_contract_automatically_validated=false
owner_visual_judgment_required=true
response_contract_valid
response_cleanup_applied
input_tokens
output_tokens
total_tokens
request_elapsed_ms
technical_outcome
technical_code
visual_quality_review_required
visual_quality_reviewed
visual_quality_accepted
visual_review_action_executed
api_key_exposed=false
workspace_id_exposed=false
base_url_exposed=false
image_base64_exposed=false
response_preview_persisted=false
local_gpu_model_loaded=false
database_write_allowed=false
project_artifact_write_expected=false
reliability_event_written=false
qq_write_executed=false
chat_history_written=false
agent_task_written=false
approval_written=false
memory_rag_called=false
project_doc_rag_called=false
dev_context_called=false
combined_rag_called=false
main_llm_called=false
tts_called=false
local_vision_called=false
```

中文只解释结论；`workflow`、`stage`、`code`、模型、token、延迟、外发和安全布尔证据必须保留英文原值。

## 12. 结果分级与错误映射

### 12.1 分级

| 结果 | 条件 |
|---|---|
| `succeeded` | 一次请求完成、基础合同通过、usage 合同通过、主人接受描述，且没有更高优先级 attention |
| `attention` | 基础合同通过但等待主人质检；或延迟超阈值、usage 缺失等不应伪装为完全通过的情况 |
| `failed` | 配置、资产、鉴权、连接、超时、限流、请求、响应或主人语义质检失败 |

延迟阈值建议第一版设为 30 秒提示关注，60 秒客户端硬超时。延迟 attention 不触发重试，也不改用其他模型。

### 12.2 固定错误码

```text
cloud_vision_feature_disabled
cloud_vision_credentials_missing
cloud_vision_configuration_invalid
cloud_vision_reference_asset_unavailable
cloud_vision_authentication_failed
cloud_vision_rate_limited
cloud_vision_request_timeout
cloud_vision_connection_failed
cloud_vision_request_rejected
cloud_vision_empty_response
cloud_vision_low_quality_response
cloud_vision_response_too_large
cloud_vision_response_contract_mismatch
cloud_vision_usage_metadata_unavailable
cloud_vision_latency_attention
cloud_vision_response_quality_review_required
cloud_vision_response_quality_rejected
cloud_vision_fixed_description_succeeded
cloud_vision_unexpected_failure
```

401/403 映射 `cloud_vision_authentication_failed`，429 映射 `cloud_vision_rate_limited`，连接失败和请求超时分开。任何 401、403、429、5xx、连接失败、超时或无效响应都不自动重试、不自动切模型、不执行后续工作流。页面和 DTO 不透传供应商原始错误正文、request ID、endpoint、凭据或 traceback。

## 13. 写入与副作用边界

该工作流允许的真实副作用只有：

1. 从项目内固定登记路径读取一张 PNG。
2. 在进程内短暂生成其 Base64 Data URL。
3. 发起一次到固定百炼北京地域 endpoint 的 HTTPS 请求。
4. 在当前 Owner Console 进程内保存有限、脱敏的最近结果供主人审核。

不得：

- 写聊天历史、Agent task、approval、reliability event 或业务数据库；
- 写项目 artifact、缓存图片、响应文件或请求 dump；
- 调用 MemoryRAG、ProjectDocRAG、DevContext、CombinedRAG、Main LLM、TTS、本地视觉或 Tavily；
- 打开 MainAgent 工具，执行 shell、QQ 写入或文件发送；
- 自动重试、自动告警、自动修复、自动执行第二模型或后续工作流。

供应商自身可能产生计费、审计、运行日志或按其政策处理输入，应用无法把整个外部系统声明为零写入。页面必须保留该事实。

## 14. 实际实现范围

主人批准后已新增：

```text
src/plugins/ai_chat/aliyun_bailian_vision.py
src/plugins/ai_chat/owner_console_cloud_vision.py
tests/test_owner_console_cloud_vision.py
tests/test_aliyun_bailian_vision.py
```

并完成以下有限扩展：

- 配置模型：URL/Key 两个部署字段，provider/model 固定在代码；
- 生产视觉：`describe_images()` 改用百炼客户端，失败时不 fallback 到本地 Ollama 或 Plus；
- Owner Console runtime：独立 executor、最近结果与既有全局锁；
- FastAPI：一个固定执行 POST、一个固定预览 GET、两个固定审核 POST；
- 前端：原位替换旧视觉面板，保留固定图、回复、cleanup、token、耗时和接受/拒绝；
- 启动脚本：`-EnableCloudVisionProbe`；
- fake HTTP、配置、路由、锁、脱敏、前端与源码边界测试；
- 本文、权威快照、总设计、runbook 和版本运行日志同步。

以下边界保持不变：

- 不修改 QQ 图片获取、下载与发送逻辑；仅替换进入 `describe_images()` 后的模型 provider；
- 本地 `vision_managed_lifecycle` executor 与历史测试保留，但不再作为默认 UI/生产入口；
- Ollama 启动、驻留或卸载逻辑；
- RAG、TTS、MainAgent、数据库或 reliability observer；
- `data/stickers` 中固定表情原文件及其 manifest。

自动化使用 fake transport 和测试内存数据，不读取真实 API Key，不连接百炼，不发送固定 owner_private 图片。隔离 live 的三次真实请求是主人逐次批准的独立验证，不属于自动回归；第三次之后没有第四次请求。

## 15. 分阶段批准与验收

| 阶段 | 内容 | 当前状态 | 是否可自动开始 |
|---|---|---|---|
| A | 设计、配置说明、成本与外发边界审阅 | `owner_approved_design`、`designed` | 已完成 |
| B | fake-only 后端、页面、路由与测试实现 | `owner_approved`、`implemented`、`regression_passed` | 已完成 |
| C | 主人配置 OpenAI-compatible URL/API Key | `owner_approved`、`configured_privately`、`owner_console_loaded`、`bot_loaded` | 配置与两个进程加载均完成 |
| D | 隔离脚本把固定 owner_private PNG 发送百炼并由主人审核 | `owner_approved`、`isolated_live_passed`、`owner_accepted` | 三次逐步实验已完成，不自动重复 |
| E | 生产 `describe_images()` 与 Owner Console 原位替换 | `owner_approved`、`implemented`、`regression_passed`、`owner_console_loaded`、`bot_loaded`、`qq_live_passed`、`owner_accepted` | 页面无问题；两张 QQ 图片快速准确描述 |
| F | Flash 质检失败后评估 `qwen3.7-plus` | `deferred`、`not_approved` | 否，禁止自动 fallback |

### 15.1 fake-only 验收

- 配置缺失、非法 Workspace、禁用开关、资产漂移均在网络调用前失败；
- client 固定一次请求、零 retry、固定 host/path、`trust_env=false`、redirect=false；
- prompt、model、图片、参数不能由 UI/HTTP/env 任意覆盖；
- key、Workspace、Base64、原始错误正文不进入 DTO、页面、日志或测试快照；
- 与现有所有手动诊断共享同一个全局锁；
- 自动测试证明不会调用 QQ、RAG、TTS、Main LLM、本地视觉、数据库或 reliability；
- 所有网络均为 fake，没有真实图片外发和费用。

### 15.2 已完成的隔离 live 与未来集成验收

隔离 live 已确认：第三次固定请求为 1578 ms，input/output/total token 316/98/414；主人接受其对主要画面和爱意、兴奋、撒娇感情色彩的描述。该结果只证明固定脚本、固定 URL/Key、固定模型和固定图片一次回复质量。

Owner Console 与生产集成仍需验证：

- 主人明确看见并确认 `owner_private` 图片外发说明；
- 一次确认只产生一个 provider 请求，无客户端重试和模型 fallback；
- 页面展示 provider/model、token、延迟、完整有限中文回复和安全证据；
- 主人能对照固定参考图接受或拒绝描述；
- 拒绝时严格保留 `failed/cloud_vision_response_quality_rejected`，不因 API 200 倒写成功；
- live 后不产生项目文件、数据库、聊天、QQ、RAG、reliability 或 Agent task 写入；
- 本地 Ollama 和 GPU 状态不因本工作流改变。

## 16. 当前结论与下一步

阿里云百炼 `qwen3.7-flash` 已从候选推进为主人接受的固定样本模型和代码中的生产主视觉 provider。实现固定同一图片、单次请求、零工具、零重试、独立凭据、北京地域 endpoint、显式外发说明、主人语义质检和不可自动 fallback。

当前代码、离线回归、Owner Console 页面和 QQ 生产图片均已通过。主人对两张 QQ 图片的描述质量与响应速度均明确接受；结构化可靠性事件只证明两次 vision success，不保存图片或回复正文。该结果不能外推为所有图片或长期 SLA，后续不自动重复 live。
