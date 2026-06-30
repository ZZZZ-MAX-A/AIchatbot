# 重启后继续测试上下文

日期：2026-06-28

用途：电脑重启、上下文丢失或换会话后，用这份文档快速恢复当前判断，避免把显存/服务状态问题误判成代码链路问题。

## 当前仓库状态

- 分支：`main`
- 基准状态：本文档初始记录时已同步 `origin/main`；后续收口提交后以 `git status --short --branch` 和 `git log --oneline -5` 为准。
- 初始最新提交：

```text
2c5a9b3 Route semantic voice through ChatGraph node
c0243b8 Route chat postprocess through ChatGraph nodes
79ccdf1 Move chat prompt setup into ChatGraph bridge
4472413 Bridge legacy chat tail into ChatGraph
c389dd2 Add executable graph runner skeleton
```

## 当前架构状态

项目仍然保留原本 NoneBot / QQ / NapCat 启动方式。默认生产聊天路径没有被强制切换。

关键开关：

```env
ENABLE_CHAT_GRAPH_RUNTIME=false
ENABLE_MAIN_AGENT=false
```

默认情况下：

- 普通聊天仍走 legacy 聊天路径。
- 语义语音仍可走 legacy 语义语音路径。
- ChatGraph 正式运行路径只有在 `ENABLE_CHAT_GRAPH_RUNTIME=true` 时启用。

## 已接入 ChatGraph 的内容

当前 ChatGraph 聊天节点顺序包含：

```text
VALIDATE_INPUT
-> RESOLVE_IMAGE_CONTEXT
-> PREPARE_MEMORY
-> BUILD_PROMPT_CONTEXT
-> CALL_CHAT_AGENT
-> MAYBE_VOICE_RESPONSE
-> PERSIST_TURN
-> UPDATE_TRIAL_ACCOUNTING
-> UPDATE_TTS_CANDIDATE
-> SCHEDULE_COMPRESSION
-> RENDER_RESPONSE
```

已经接入图运行路径的功能：

- 图片上下文解析：`RESOLVE_IMAGE_CONTEXT`
- prompt/user content 构建：`BUILD_PROMPT_CONTEXT`
- 聊天模型调用：`CALL_CHAT_AGENT`
- 语义语音发送：`MAYBE_VOICE_RESPONSE`
- 消息持久化：`PERSIST_TURN`
- 私聊试用次数更新：`UPDATE_TRIAL_ACCOUNTING`
- TTS 候选缓存：`UPDATE_TTS_CANDIDATE`
- 压缩调度：`SCHEDULE_COMPRESSION`
- 最终渲染：`RENDER_RESPONSE`

## 语音链路当前判断

现在项目里有两类语音请求。

第一类：直接读文本 / 读上一条回复。

示例：

```text
请用语音回复上一条信息
把上一条读给我听
用语音念刚刚那句
```

当前这类请求会被 `parse_voice_intent()` 识别成：

```python
VoiceIntentType.LAST_REPLY
```

然后走 `VoiceGraphRunner` 中的直接朗读/上一条回复线路，内部仍复用原有 TTS 发送能力：

```text
CHECK_VOICE_POLICY
-> SELECT_TEXT_SOURCE
-> ADAPT_SPEECH_TEXT
-> CHECK_TTS_HEALTH
-> GENERATE_TTS
-> SEND_PRIVATE_RECORD
```

这类请求目前不进入 ChatGraph。

第二类：语义语音回复。

示例：

```text
用语音和我说晚安
用语音哄我睡觉
用语音安慰我一下
```

当前这类请求会被 `parse_voice_intent()` 识别成：

```python
VoiceIntentType.SEMANTIC_REPLY
```

然后走：

```text
handle_chat(..., semantic_voice=True)
```

如果 `ENABLE_CHAT_GRAPH_RUNTIME=true`，这类请求会进入 ChatGraph：

```text
CALL_CHAT_AGENT
-> MAYBE_VOICE_RESPONSE
-> PERSIST_TURN
-> UPDATE_TTS_CANDIDATE
```

图路径下的关键边界：

- `CALL_CHAT_AGENT` 只负责生成文本。
- `MAYBE_VOICE_RESPONSE` 负责调用 TTS 并发送语音。
- 语音节点返回的 `voice_text` 会继续进入持久化、候选缓存和最终渲染。

## “语音和聊天耦合”是什么意思

旧 legacy 路径中，`generate_legacy_chat_response()` 同时做两件事：

```text
ask_llm() 生成文本
send_tts_record() 发送语音
```

也就是说，聊天响应函数里直接包含了 TTS side effect。

图路径现在拆成：

```text
CALL_CHAT_AGENT：只生成文本
MAYBE_VOICE_RESPONSE：只负责语音生成/发送
```

这让后续 Main Agent / LangGraph 可以更清楚地控制：

- 是否要发语音
- 哪个节点发语音
- TTS 失败时如何停止
- 结果是否进入持久化和候选缓存

## 已完成的纯本地验证

最近完整纯本地验证通过：

```text
Ran 124 tests
OK
git diff --check OK
```

语音相关定向测试通过：

```text
test_vision_voice_units OK
test_graph_runners OK
test_chat_graph_bridge OK
```

这些测试不触发 QQ / NapCat / 真实模型 API / 真实发语音。

## TTS 服务测试记录

测试时间：2026-06-28 晚上。

TTS 服务健康检查通过：

```json
{"ok": true, "loaded": true, "language": "zh"}
```

本地 `request_tts()` 到 `/tts` 的链路已经证明能生成有效 wav。

第一次测试文本：

```text
语音链路测试。
```

客户端配置超时：

```env
TTS_TIMEOUT_SECONDS=180
```

结果：

- 客户端 180 秒超时。
- 服务端之后实际生成成功。
- 生成文件有效。

有效音频示例：

```text
temp_audio\tts_ca4a7d6705954e9799762214594496e1.wav
约 7.294 秒
22050 Hz
单声道
约 321 KB
```

第二次测试临时提高超时：

```powershell
$env:TTS_TIMEOUT_SECONDS='420'
```

测试文本：

```text
好。
```

结果成功：

```json
{
  "audio_path": "D:\\AIchatbot\\temp_audio\\tts_59ae80da06244beb8e5aade2e9e128a9.wav",
  "exists": true,
  "reported_duration_seconds": 2.21,
  "elapsed_seconds": 22.691,
  "configured_timeout_seconds": 420
}
```

注意：`TTS_TIMEOUT_SECONDS=420` 只是那次命令里的临时环境变量，没有改 `.env`。

## 当前 TTS 风险判断

目前更像是显存/GPU 状态导致的慢生成，不像代码链路断裂。

依据：

- TTS 服务 `/health` 可用。
- 模型能加载。
- 服务端能返回 `/tts 200 OK`。
- `temp_audio` 能生成有效 wav。
- 短文本在热加载后能成功返回。
- 冷启动或显存压力下生成可能超过 180 秒。

所以重启电脑后再测更干净。

## 重启后建议测试顺序

先不要直接测 QQ 真实语音，先确认服务状态。

1. 检查仓库状态：

```powershell
git status --short --branch
git log --oneline -5
```

期望：

```text
main...origin/main
2c5a9b3 Route semantic voice through ChatGraph node
```

2. 跑纯本地测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_vision_voice_units.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_graph_runners.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_chat_graph_bridge.py" -v
```

3. 检查 TTS 服务健康：

```powershell
try {
  Invoke-RestMethod -Uri 'http://127.0.0.1:7861/health' -TimeoutSec 5 | ConvertTo-Json -Compress
} catch {
  Write-Output "TTS_HEALTH_ERROR: $($_.Exception.Message)"
}
```

如果服务未启动，可以使用：

```powershell
.\scripts\start-tts-service.ps1
```

4. 先测本地 TTS 生成，不经过 QQ：

```powershell
$env:TTS_TIMEOUT_SECONDS='420'
@'
from __future__ import annotations

import asyncio
import json
import time
import wave
from pathlib import Path

from tests.pure_ai_chat_loader import load_legacy_media_modules

mods = load_legacy_media_modules()
config = mods["config"].load_config()
voice = mods["voice"]

async def main():
    started = time.perf_counter()
    adapted = voice.adapt_speech_text("好。", force_language="zh")
    result = await voice.request_tts(config, adapted, refresh_cache=True)
    elapsed = time.perf_counter() - started
    path = Path(result.audio_path)
    with wave.open(str(path), "rb") as reader:
        info = {
            "audio_path": str(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size,
            "reported_duration_seconds": result.duration_seconds,
            "elapsed_seconds": round(elapsed, 3),
            "channels": reader.getnchannels(),
            "sample_width": reader.getsampwidth(),
            "frame_rate": reader.getframerate(),
            "frames": reader.getnframes(),
            "wave_duration_seconds": round(reader.getnframes() / reader.getframerate(), 3),
            "segments": len(result.segments),
            "cache_hit": result.cache_hit,
            "configured_timeout_seconds": config.tts_timeout_seconds,
        }
    print(json.dumps(info, ensure_ascii=False))

asyncio.run(main())
'@ | .\.venv\Scripts\python.exe -
```

5. 如果本地 TTS 生成稳定，再测 QQ/NapCat 真实发送。

注意：真实 QQ/NapCat 测试属于非纯本地测试，需要明确确认后再执行。

推荐先测：

```text
请用语音回复上一条信息
```

这条验证 `LAST_REPLY -> handle_direct_or_last_tts()`。

再测：

```text
用语音和我说晚安
```

如果 `.env` 中：

```env
ENABLE_CHAT_GRAPH_RUNTIME=true
ENABLE_TTS=true
```

这条会验证：

```text
ChatGraph CALL_CHAT_AGENT
-> MAYBE_VOICE_RESPONSE
-> PERSIST_TURN
-> UPDATE_TTS_CANDIDATE
```

如果 `ENABLE_CHAT_GRAPH_RUNTIME=false`，它仍然验证 legacy 语义语音路径。

## 不要误判的点

- `请用语音回复上一条信息` 当前不进入 ChatGraph，这是预期行为。
- `用语音和我说晚安` 在图开关打开后才进入 ChatGraph。
- TTS 首次冷启动很慢，不代表 ChatGraph 语音节点坏了。
- 180 秒超时可能不够，尤其在显存不足或模型刚加载时。
- 看到 `temp_audio` 里生成了有效 wav，说明服务端 TTS 至少完成过生成。
- 当前没有必要为了这次超时立即改代码，优先重启电脑后复测。

## 后续建议

短期：

- 重启后先复测本地 TTS。
- 再测 QQ/NapCat 真实语音发送。
- 如果 180 秒仍频繁超时，再考虑调大 `.env` 中的 `TTS_TIMEOUT_SECONDS`。

中期：

- 直接读文本 / 读上一条回复已整理成 `VoiceGraph`。
- `VoiceGraph` 当前包含：
  - `DIRECT_TEXT`
  - `LAST_REPLY`
  - `SEMANTIC_REPLY`
- 语义语音继续走 `ChatGraph -> MAYBE_VOICE_RESPONSE`。

长期：

- 接入 Main Agent 后，让 Main Agent 在受限 schema 内判断：
  - 普通聊天
  - 语义语音
  - 朗读上一条
  - 直接读文本
  - 忽略
- 具体执行仍由 LangGraph/策略层控制，不能让聊天 agent 自由决定发语音。
