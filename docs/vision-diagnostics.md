# 图片识别诊断

## 日志入口

每张图片的诊断追加到 `logs/vision.log`，UTF-8 JSONL，一行一条。
普通聊天的 `describe_images`、按人格选择线路、DeepSeek、Grok 和百炼请求共用记录；
同一张图不会因嵌套调用重复写入。并发任务按 trace 隔离。
新代码需要 Bot 下次加载后才会用于在线聊天；本次没有重启 Bot。

在项目根目录查看最近记录：

```powershell
Get-Content .\logs\vision.log -Encoding UTF8 -Tail 10 |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Select-Object time, persona, trace, status, stage, error_code,
        requested_model, returned_model, request_ms, filter_reason, filter_markers, summary |
    Format-List
```

## 字段和判断

| 字段 | 用途 |
| --- | --- |
| time、trace、batch、image_index | 北京时间、单图追踪号、同轮批次和图片序号 |
| persona、provider、endpoint_host | 所属人格、实际线路和接口主机；不记录密钥或完整 URL |
| image_sha256、image_bytes、width、height、image_format | 模型入参图片字节的指纹、大小和尺寸；便于核对是否同图 |
| requested_model、returned_model、model_name_matches | 请求模型名、响应模型名及是否相同；不同不会自动拒绝或回退 |
| max_tokens、timeout_seconds | 本次模型请求参数 |
| reasoning_effort | 显式指定的视觉思考强度；null 表示该请求未指定，实际消耗仍看返回用量 |
| download_ms、request_ms、total_ms | 读取/下载、接口请求和整条单图流程耗时 |
| request_started、response_received | 是否已调用供应商、是否已拿到 SDK 解析后的响应 |
| finish_reason | 供应商返回的 stop/length 等结束原因；缺失时为空 |
| prompt_tokens、completion_tokens、total_tokens | 供应商报告的用量；不自行补算缺失值 |
| reasoning_tokens、reasoning_chars、cached_tokens、image_tokens | 可用时记录思考/缓存/图片用量、思考字符数；不记录思考正文 |
| raw_description_chars、description_chars | 本地过滤前后字符数；不保存过滤前的原文 |
| filter_changed、filter_reason、filter_markers | 是否被本地改写、原因、命中的固定过滤词；不记录原文片段 |
| summary | 已经业务过滤、再次脱敏后的简短摘要，最多 180 字符 |
| status、stage、error_code、error_type、cause_type、http_status | 流程结果、最后阶段、固定错误码和异常类型；HTTP 状态仅在实际取得时记录 |

`status=succeeded` 仅表示接口和本地校验通过，**不表示内容已经核实正确**。
`status=response_truncated` 表示非空正文以 length 结束；保留原有返回行为。
截断且正文为空时仍按原有错误流程处理，日志保留 finish_reason 和用量。
取消会记录 cancelled 后继续传播取消。

`stage=download` 且 `request_started=false` 表示尚未进入模型请求。
`image_size_limit` 表示图片被现有大小限制拦截，不应归因于模型识别失败。
此时可能没有模型名、图片指纹或用量，不能将其当成空模型回复。

`filter_reason=prompt_marker` 表示摘要命中了现有规则词。
例如普通画面描述中使用“忽略”也可能触发整段替换；需结合人工核对图片判断。
本次增加诊断，不改变该过滤策略。

null 表示供应商未提供或流程未到该阶段；0 表示供应商明确返回零，不能混用。
尤其不能单凭 image_tokens=0 断定图片没有传入，也不能把未返回的用量解释为零。
Grok 的成功响应目前没有通过 SDK 取得 HTTP 状态，日志保持 null，不猜填 200。
百炼使用现有结果对象中的模型名和用量，未暴露的结束原因/思考明细保持缺失。

## 独立人格当前视觉配置（2026-10-18 切换后）

独立人格视觉已改为 `deepseek-flash`，provider 为 `persona_deepseek`。
本地 `.env` 删除了原 Grok 视觉地址覆盖；省略 `PERSONA_VISION_API_KEY` 和
`PERSONA_VISION_BASE_URL` 时从 `AIKE_LLM_API_KEY` / `AIKE_LLM_BASE_URL` 读取连接，
无需复制密钥。两项仍可显式配置独立连接，显式空值会阻止 DeepSeek 请求，
不会改用独立人格聊天的 Grok 凭据。

```dotenv
PERSONA_VISION_MODEL=deepseek-flash
PERSONA_VISION_TIMEOUT_SECONDS=60
PERSONA_VISION_MAX_TOKENS=4096
PERSONA_VISION_REASONING_EFFORT=high
```

DeepSeek 缺省输出额度为 4096，其他人格视觉兼容模型保持原 400；
额度可独立配置，DeepSeek 思考强度支持 low/high/max，主人随后指定日常采用 high，默认同步为 high。
参数独立于两个人格的聊天模型；默认人格视觉仍为阿里百炼，独立人格文字聊天仍为原 Grok。
旧 Grok 路由能力保留供后续明确配置，当前独立人格视觉不调用它，失败也不会回退。
配置页显示实际视觉服务、模型、额度与思考设置；新日志含 reasoning_effort。

切换后通过真实 `describe_images` 入口，以此前识别出错的代码截图再次调用：
实际请求发往 api.deepseek.com/chat/completions，HTTP 200，返回对应 Python 代码摘要。
该独立验收没有启动 Bot、发送 QQ 或写聊天记忆；Bot 下次加载新代码及 .env 后用于在线图片。
切换验证记录为被 Git 忽略的 `tmp/linyin-vision-audit-20261018/deepseek-runtime-switch.json`。
原有 5 MiB 大小限制、提示词与过滤策略保留。

### 当前失败返回与识别错误边界

普通聊天中，图片下载/大小/格式错误、接口错误或超时、空候选、空正文及低质量重复正文，
会产生单图标记“这张图片本次没有识别成功。”。当本轮尝试的图片全部失败时，
聊天生成入口直接返回“本次图片识别失败了，请稍后再试，或者换一张更清晰的图片。”，
不调用角色聊天模型，不启用 Grok 视觉回退。多图部分失败时仍将成功摘要及失败标记交给聊天模型。

非空且正常的文字摘要不会经过自动事实核验：即使画面是代码、摘要却写成动漫，
本地也可能将其作为观察结果交给角色模型；status=succeeded 不能证明识别准确。
非空正文以 length 结束时当前仍保留摘要并记录 response_truncated；不等同于硬失败。
疑似提示注入摘要被本地替换为安全概括，也不会自动变成识图失败。
high 思考不能保证消除这些错误，日志用于检查图片指纹、请求/返回模型、结束原因和摘要过滤过程。

## 切换前的第三方模型标识

2026-10-18 切换前独立人格配置请求 `grok-4.6`，第三方接口主机为 `api.shuaiapi.com`。
三张样本的模型请求均返回 `model=grok-4.6-build`。
这只能证明该服务的响应使用此标识，不能证明它对应某个官方 xAI 版本、权重或固定后端。
本次公开资料核查因搜索工具不可用、官方文档连接超时未取得可验证说明。
不要据此把 `.env` 改成返回标识，也不要把名字不同直接判断为调用失败。

本次请求使用 max_tokens=400，但三次返回 completion_tokens 分别为 2091、1474、2356，
其中 reasoning_tokens 为 1998、1394、2248。服务对额度和用量字段的定义尚未核实，
不能按其他供应商的规则推断思考是否包含在 400 之内，也不能据此认定本地参数没有发出。

## 2026-10-18 切换前的 Grok 样本检查

沿用切换前独立人格视觉模型、提示词、90 秒超时、400 token 参数；不带聊天历史或角色卡。
用户原图仅从本地读取，不复制进仓库，不写入聊天记忆，不发送 QQ。

| 样本 | 当前正式预处理 | 模型请求结果 |
| --- | --- | --- |
| 10-01 140855，2559×1593，6502963 字节 | 超过 5242880 字节限制，模型未调用 | 仅测试时绕过大小门控，原图请求约 53.30 秒；场景、人物外观和构图基本匹配 |
| 10-03 172756，2559×1599，4804615 字节 | 通过 | 约 35.98 秒；射击游戏结算、士兵、胜利 10-2 基本匹配，未包含完整战绩数字 |
| 10-07 083115，2559×1579，2931850 字节 | 通过 | 首次约 55.59 秒；API 返回 132 字，本地过滤后仅剩 38 字提示注入替代文本；复测约 63.85 秒，正确描述十连界面和左侧五星角色，但将其余三星武器错称为四星 |

这些是视觉阶段耗时，不包括之后角色聊天生成和消息发送。
三张样本不足以证明稳定性；原有小尺寸色块测试仍有错误描述记录。
第三张首次测试发生在增加 filter_markers 字段之前，未保留过滤前原文，无法追溯具体命中词。
复测 filter_reason=unchanged，未重现整段替换；不能将推测的命中词写成首次实测结论。
离线另用“账号已忽略”验证现有规则确会因“忽略”将普通事实摘要整段替换。
这证明规则存在误伤情形，不证明首次第三张就是命中了这个词。
本地复核数据在被 Git 忽略的 `tmp/linyin-vision-audit-20261018/`。

## 数据范围

默认人格聊天配置的 DeepSeek 独立图片测试及官方名称核对见
[DeepSeek 图片能力实测](deepseek-vision-evaluation.md)。该测试没有切换正式视觉线路。

日志不保存图片本体、Base64、源地址、聊天文本、密钥、原始响应、原始异常消息或思考正文。
摘要包含有限的图片事实，不保证涵盖任意私人文字；对 UID/账号等标签、长数字、邮箱、
链接和密钥进行额外脱敏。该日志沿用项目本地日志管理方式，不应作为公开资料提交。
日志写入失败不会改变识图返回；既有过滤、路由、超时、重试和失败回退行为保持原样。
