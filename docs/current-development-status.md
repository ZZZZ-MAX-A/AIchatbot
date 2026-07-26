# AIchatbot 当前开发状态

## 1. 快照元数据

| 字段 | 当前值 |
|---|---|
| 快照日期 | 2026-07-27（Asia/Shanghai） |
| Git 分支 | `main` |
| 已提交基线 | `0055dcc Add Owner Console and Main LLM diagnostic articles` |
| 远端关系 | 本次只读核对时 `main...origin/main`，无领先或落后 |
| 工作区 | 有未提交修改；包含主人已批准的 P2.49d、P2.49e、本轮百炼云视觉实现、文档治理修改和主人保留文件 |
| 运行态观测 | 2026-07-27 Owner Console PID 15220 继续监听 8090。Bot 已由主人通过 `scripts/start.ps1` 启动，父/子 PID 24552/15332，监听 8080 并完成 QQ live；主人连续发送两张图片，均得到快速且准确的百炼描述。只读结构化可靠性证据在同一 runtime 记录两次 `vision/infer/operation_succeeded/succeeded`，未读取聊天正文或图片。11434 现有 listener PID 4388 保持在线，7861 无 listener。运行态只代表对应观测时点 |
| 权威范围 | 当前主人批准方向、阶段完成度、待办优先级、授权与禁止动作 |

运行态只代表表中时间点，不代表持续状态。Git 事实以实时 `git status -sb` 和 `git log --oneline -5` 为准；详细历史证据见 [version-runlog.md](version-runlog.md)。

## 2. 当前主人批准方向

主人当前明确批准的工作已经推进到以下状态：

1. `completed`：文档治理规范已落实到权威快照、导航、历史免责声明、陈旧事实、能力审计和 Owner Console 手动诊断 runbook。
2. `implemented`、`regression_passed`：主人批准的 Owner Console TTS 一键受控生命周期诊断已完成 fake-only 代码、页面、合同和回归；明确离线时可启动受管理子进程，验证后只清理本次产物，并只停止本次持有句柄的进程。
3. `completed`：未获方向批准的 `system_diagnostics_report/core` 命令、scope、运行时、测试和正式能力表述已撤销；只保留 `_system_database_read_probe()` 改用 `connect_read_only()` 的独立安全修正。
4. `live_retry_failed_service_start`、`fix_effect_verified`：主人于 2026-07-25 第二次执行 P2.49d 后，`ConnectTimeout` 已正确进入受管理启动；但当时版本的子进程在固定 45 秒内始终未提供有效 `/health`，结果为 `failed/tts_service_start_timeout`。本次 `service_start_attempted=true`、`service_stop_attempted=true`、`service_stopped=true`、`tts_called=false`，没有模型合成或 WAV。
5. `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_technical_passed`：主人随后批准 P2.49d lazy bootstrap 最小修复。第三次真实动作已在 `startup_elapsed_ms=1054` 后获得轻量 health，首次 `/tts` 完成 runtime 导入、模型合成、132140-byte/2995-ms WAV 验证、精确清理和本次服务停止；证明 lazy bootstrap 与基础技术链可用。
6. `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted`：主人听检门控真实验收通过。新 run 总计 59780 ms，合成 56579 ms，WAV 140844 bytes/3193 ms；技术结果成功，主人完成试听并接受，`audio_quality_reviewed=true`、`audio_quality_accepted=true`。接受后内存预览已清除，受保护 GET 返回 409；磁盘产物和本次服务均已收尾。
7. `live_vision_passed`、`live_cleanup_attention`：主人已执行 P2.49e 真实视觉动作。固定 311-byte PNG 与严格四色回答合同均通过；`qwen2.5vl:3b` 完成一次推理，`vision_called=true`、`response_contract_valid=true`。由于旧实现只在响应后 8 ms 读取一次 `/api/ps`，当时未确认模型释放，严格保留 `attention/vision_model_cleanup_incomplete`；稍后只读检查已见目标模型消失。
8. `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_passed`：主人批准 P2.49e 最小收口验证修订。重跑为 `succeeded/vision_managed_lifecycle_succeeded`，模型调用前未驻留、`keep_alive=0`、收口轮询 2 次/284 ms 后确认释放；不重复 `/api/chat`、不执行 `ollama stop`、不停止已有服务。
9. `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_failed`、`owner_rejected`：固定正式表情严格结构化版完成主人 live。模型完成一次推理且资源收口通过，但多个结构字段返回 `unknown`，自然描述误判为“黑色帽子、白色披风、眼睛被红色心形遮住”；后端正确返回 `failed/result_validation/vision_response_contract_mismatch`，未伪装成成功，也未进入接受门控。
10. `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_technical_passed`、`owner_rejected`：主人执行最小自然描述单变量实验。模型一次请求、usage 与资源收口均完成，底层 `technical_outcome=succeeded`、`technical_code=vision_managed_lifecycle_succeeded`、`model_cleanup_verified=true`；但自然回复仍把黑白长发说成黑帽子和披风，把眼睛说成被心形遮住，对被爱心遮挡的嘴部作无依据判断，并把透明背景说成纯黑背景。主人审核后最终严格保留 `failed/owner_visual_review/vision_response_quality_rejected`，证明关闭 Schema 没有使当前本地模型达到所需描述质量。
11. `owner_approved`、`configured_privately`、`isolated_live_passed`、`owner_accepted`：主人配置百炼北京地域 OpenAI-compatible URL/Key，并明确批准对同一固定 `owner_private` PNG 做三次逐步提示词实验。最终固定 `qwen3.7-flash`、`enable_thinking=false`、一次请求、零工具、零重试；最佳一次为 1578 ms、input/output/total token 316/98/414，主人接受其对黑白头发、可见眼睛、大小爱心以及爱意/兴奋/撒娇情绪的描述。有限清理只移除完整前导 `<think>…</think>` 或前导孤立 `</think>`。
12. `owner_approved`、`implemented`、`regression_passed`、`owner_console_loaded`、`ui_smoke_passed`、`bot_loaded`、`qq_live_passed`、`owner_accepted`：主人随后批准把百炼 `qwen3.7-flash` 作为生产 `describe_images()` 的主视觉模型，并原位替换 Owner Console 的本地视觉配置/诊断面板。2026-07-27 Owner Console 页面验收无问题；Bot 加载后主人连续发送两张 QQ 图片，均得到快速且准确的描述，结构化事件记录两次成功。生产云视觉链现已完成 QQ live 验收。
13. `owner_approved`、`implemented`、`regression_passed`、`next_start_effective`：主人指出 `scripts/start.ps1` 仍因 `ENABLE_VISION=true` 检查本地 `qwen2.5vl:3b`。现已从 `ensure-ollama.ps1` 移除视觉对本地 Ollama 的依赖；未来启动只有启用 MemoryRAG/ProjectDocRAG 且 embedding provider 为 Ollama 时才检查 `bge-m3`。新增 3 项零网络合同测试，全量 Python 737 tests OK（skipped=4）；未重启当前 Bot/Ollama。

方向选择规则：

```text
事实仍存在 != 应立即实现
未完成事项 != 当前下一阶段
候选范围 != 主人批准范围
历史“下一步” != 当前路线图
未明确命名方向的“继续下一阶段” != 可以自行选择旧 backlog
```

任何新阶段开始前，必须先向主人说明目标方向、实际问题、能证明什么、不能证明什么、真实调用、写入、副作用、重启范围、影响模块和验收方式。只有标记为 `owner_approved` 的事项可以开始。

## 3. 当前阶段已完成

完成度必须区分 `implemented`、`regression_passed`、`loaded`、`live_passed` 和 `owner_accepted`，不能把本地实现写成线上通过。

| 项目 | 已确认状态 | 关键结论 |
|---|---|---|
| P2.48 Owner Console 可读性 | `implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted` | 可靠性页和诊断页保留英文证据，中文只作解释；主人页面验收通过 |
| P2.49a ProjectDocRAG 固定检索 | `implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted` | 二次确认；一次真实 embedding；SQLite `mode=ro` 前五项；数据库零写入 |
| P2.49b MemoryRAG 一致性 | `implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted` | 37 个活动文档、35 个有效向量、2 个 `manual_fact` 缺失向量；只报告 `attention`，未读取正文、未检索、未修复 |
| P2.49c Main LLM 固定问答 | `implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted` | Main LLM 能完成一次固定问答；严格五字段 JSON 未通过，保留 `attention/main_llm_contract_mismatch`；不证明任意工具选择能力 |
| P2.49a–c 完整回归 | `regression_passed` | 提交前记录为 Python 674 tests OK（skipped=3）、前端 21 tests、TypeScript、Vite build、三条 POST guard、AST 148 files、pip check、`git diff --check` 通过 |
| 文档治理第二轮 | `implemented`、`docs_validated` | 权威快照改为固定九段；补主人批准状态、优先级和唯一下一步；修正 external-read、能力审计、runbook 和导航陈旧事实 |
| P2.49d TTS 一键受控生命周期 | `audited`、`designed`、`implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted` | 主人最终听检 run 总计 59780 ms、合成 56579 ms，WAV 140844 bytes/3193 ms；技术合同通过，主人试听并接受。审核后内存预览、磁盘产物和本次受管理服务均已收尾，不自动重复合成 |
| P2.49d 完整回归 | `regression_passed` | Python 693 tests OK（skipped=4）、前端 24 tests、Owner Console 相关 57 tests、RAG/QQ 边界 13 tests、TypeScript、Vite build、四条 POST guard、Python AST 154 files、pip check、文档链接/围栏和 `git diff --check` 通过 |
| P2.49e v1 视觉生命周期 | `loaded`、`live_passed` | 第二次主人 live：固定四色结构合同通过；总计 8821 ms、推理 8373 ms、收口 284 ms，`model_cleanup_poll_count=2`、`model_cleanup_verified=true`，证明 5 秒有界轮询修订生效。该版本只能作为接口/结构/资源基础证据；图片简单且 prompt 含预期颜色，不能继续作为内容理解质量终态 |
| P2.49e v2 严格结构化描述 | `implemented`、`regression_passed`、`loaded`、`live_failed`、`owner_rejected` | 固定资产与单次推理、模型释放均正常；结构合同失败，描述把黑白头发误认为黑帽子/白披风并误称眼睛被爱心遮住。该结果证明严格 Schema 版不满足描述质量，不能倒写成功 |
| P2.49e 自然描述实验 | `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_technical_passed`、`owner_rejected` | 请求无 `format`、无 JSON Schema、无字段枚举和视觉答案；本次 `elapsed_ms=11035`、推理 10474 ms、input/output/total token 为 1058/66/1124，模型收口轮询 2 次并确认释放。技术链通过但描述仍有黑帽子/披风、眼睛被遮、嘴型和纯黑背景等错识别，主人拒绝质量，最终为 `failed/owner_visual_review/vision_response_quality_rejected` |
| P2.49e 自然描述完整回归 | `regression_passed` | 视觉 executor 15 tests、手动诊断 17 tests、Python 720 tests OK（skipped=4）、前端 31 tests、TypeScript、Vite build 通过；没有访问真实视觉、停止/重启 Ollama、修改正式表情资产或执行 QQ |
| 阿里云百炼隔离真实探测 | `owner_approved`、`configured_privately`、`isolated_live_passed`、`owner_accepted` | 同一固定 `aike_affection_005` owner_private PNG；北京地域 `qwen3.7-flash`；三次主人逐步批准的单次请求。最终 prompt 允许概括可见画面的情绪/感情色彩，最佳回复获主人接受；最后一次 1578 ms，token 316/98/414，没有第四次请求 |
| 百炼生产视觉与 Owner Console 收口 | `owner_approved`、`implemented`、`regression_passed`、`owner_console_loaded`、`ui_smoke_passed`、`bot_loaded`、`qq_live_passed`、`owner_accepted` | 生产 `describe_images()` 使用百炼且无 Ollama/Plus fallback；Owner Console 原位替换完成。主人确认页面无问题，并在 QQ 连续发送两张图片，均得到快速准确描述；同一 runtime 有两次结构化 vision success |
| 启动脚本 Ollama 依赖收口 | `owner_approved`、`implemented`、`regression_passed`、`next_start_effective` | `ENABLE_VISION`、`VISION_OLLAMA_BASE_URL`、`VISION_MODEL/qwen2.5vl:3b` 不再参与 `ensure-ollama.ps1`；仅 Ollama-backed MemoryRAG/ProjectDocRAG 检查 embedding URL 与 `bge-m3`。聚焦 3 tests、Python full 737 tests（skipped=4）、PowerShell parse、`git diff --check` 通过 |
| P2.49d ConnectTimeout 最小修复 | `implemented`、`regression_passed`、`reloaded`、`live_effect_verified` | 新增 `ConnectTimeout -> 受管理启动` fake 端到端测试；主人重试时 `service_start_attempted=true`，证明分类修复生效。`ReadTimeout -> 不盲目启动` 继续成立；新的失败发生在受管理启动后的 health 等待 |
| P2.49d lazy bootstrap 最小修复 | `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_technical_passed` | `/health` 不导入 torch/IndexTTS 即可就绪；首次 `/tts` 才导入 runtime 和构造模型；第三次 live 的 `runtime_imported_before=false`、`service_started=true`、`tts_called=true` 和有效 WAV 证明修复真实生效 |
| P2.49d 主人听检门控 | `owner_approved`、`implemented`、`regression_passed`、`loaded`、`live_passed`、`owner_accepted` | 固定文本“这是一次固定语音合成检查。”已由主人真实试听并接受；最终 `succeeded/result_validation/tts_managed_lifecycle_succeeded`。`technical_outcome=succeeded`，听检后预览不可再取、磁盘无 WAV、7861 无 listener。Python 719 tests OK（skipped=4）、TTS 18 tests（skipped=1）、Owner Console 102 tests（skipped=1）、前端 29 tests及全部静态边界通过 |
| `core` 处置 | `implemented`、`regression_passed` | 未批准命令及能力全部撤销；只保留 `connect_read_only()`，源码/测试搜索已无 `core` 正式入口符号 |

P2.49c live 的核心证据：

```text
workflow=main_llm_fixed_contract
outcome=attention
stage=result_validation
code=main_llm_contract_mismatch
configured_model=gpt-5.5
elapsed_ms=8146
input_tokens=74
output_tokens=126
total_tokens=200
attempt_count=1
llm_called=true
contract_valid=false
tool_definitions_sent=false
client_automatic_retry=false
database_write_allowed=false
```

## 4. 当前阶段待完成

| 事项 | 是否仍存在 | 实际影响 | 优先级 | 批准状态 | 下一动作 | 可自动开始 |
|---|---|---|---|---|---|---|
| P2.49d 主人试听质量验收 | 否 | 主人已完成真实试听并明确接受；技术、质量、内存清除、磁盘清理和服务收尾证据完整 | COMPLETED | `live_passed_owner_accepted` | 无后续动作；不自动重复合成 | 否 |
| P2.49e 本地自然描述复验 | 否 | 主人已执行并拒绝回复质量；技术链和收口通过，但本地 `qwen2.5vl:3b` 对固定复杂表情的语义质量不足 | COMPLETED | `live_technical_passed_owner_rejected` | 不自动重复本地推理；结论作为线上方案对照基线 | 否 |
| 百炼云视觉页面与 QQ 生产验收 | 否 | Owner Console 页面由主人确认无问题；Bot 已加载，连续两张 QQ 图片均快速准确描述 | COMPLETED | `owner_console_loaded_bot_loaded_qq_live_passed_owner_accepted` | 不自动重复图片测试；按正常生产使用观察 | 否 |
| `core` 诊断实验 | 否 | 未批准能力已撤销，不再占用路线图；只读连接安全修正独立保留 | REJECTED | `owner_approved_removal_completed` | 无后续动作，不得从历史文档恢复 | 否 |
| 2 条 MemoryRAG 缺失向量 | 是 | 一致性缺口已观测；当前未影响本阶段验收 | DEFERRED | `not_approved` | 保持现状，不补建、不修复 | 否 |
| Main LLM 任意工具选择评估 | 未建立 | 单次固定问答不能代表通用 planner/policy 正确性 | DEFERRED | `not_approved` | 未来按具体工具与场景分别设计验收 | 否 |
| external-read 时间线、页面 stale 提示、更多移动端优化 | 是 | 有用但不是当前阻断 | P2 | `not_approved` | 保留候选，不从历史文档自动启动 | 否 |

## 5. 任务优先级

```text
P0              会误导当前方向、安全边界或实际操作，或正在阻断当前阶段
P1              主人已明确指定的下一方向
P2              有价值但不是当前主线
P3              低频或结构性候选
DEFERRED        主人明确延后
REJECTED        明确不采用
SUPERSEDED      已被后续方案替代
NEEDS_REVALIDATION  只能在重新核对 Git、代码或 live 后引用
```

同一事项的“优先级”和“批准状态”必须分别记录。高优先级不自动等于获准执行；旧任务仍存在也不自动获得优先级。

## 6. 主人授权与禁止动作

当前已授权：

- 只读核对 Git、源码、测试和指定文档。
- 修改文档以落实本快照合同、修正陈旧事实并补齐操作说明。
- 完成 P2.49d 一键受控生命周期的 fake-only 实现、页面、临时 WAV/fake process 测试和回归，不发起真实请求。
- 完成 P2.49e Owner Console 固定视觉诊断的独立 executor、显式开关、固定 POST、页面二次确认、fake HTTP/fake process/内存 PNG 自动化和完整回归，不启动、不推理。
- 按主人批准完成 P2.49d `ConnectTimeout` 最小离线分类修复、fake 回归并重启 Owner Console；不自动重新执行 TTS，重试仍由主人页面二次确认。
- 按主人批准完成 P2.49d lazy bootstrap：轻量 health 先监听，首次 `/tts` 才导入 torch/IndexTTS；完成 fake/全量回归并重启 Owner Console，不自动执行第三次 live。
- 按主人批准完成 P2.49d 内存临时试听与主人质量门控，完成完整回归并重载 Owner Console；不自动重新合成或代替主人判断听感。
- 按主人批准完成 P2.49e 模型收口验证最小修订与 fake/全量回归；只增加有界 `/api/ps` 轮询和安全证据，不自动执行视觉复验。
- 按主人批准完成 P2.49e v2 固定正式表情样例、无答案泄露 prompt、实际描述展示和主人质检门控的实现与回归；不自动重载或执行 live。
- 按主人批准完成 P2.49e 最小自然描述单变量实验：移除严格 JSON Schema、枚举与语义答案比对，保留固定图片、固定模型、单次推理和主人质检；不自动重启或执行 live。
- 按主人逐步批准完成百炼北京地域 `qwen3.7-flash` 的三次隔离固定图片测试、有限 think 标签清理、生产云视觉主链、Owner Console 原位面板替换、服务加载和两张 QQ 图片 live；不自动重复图片请求或扩大测试范围。
- 撤销未批准的 `core` 命令/scope/运行时/测试，只保留 `connect_read_only()` 安全修正。

持续禁止：

- 执行 DevContext、CombinedRAG、QueryDevContext 或私人记忆查询；引用或持久化私人聊天记忆。
- 修复或补建 2 条 MemoryRAG 缺失向量。
- 自动修复、自动告警、无归属清理、自动重启、自动视觉/TTS 重试；已获合同批准的“只清理本次 TTS artifact”和未来需另行批准的“只释放本次加载视觉模型”不等于通用自动清理授权。
- 任意 MainAgent shell、任意项目写入或未批准工具执行。
- QQ 文件、图片、表情或语音发送。
- 不由开发代理自动执行 TTS 固定诊断或听检审核；新的质量 live 只允许主人在页面二次确认、试听后手动接受或拒绝。
- 未经新的 live 批准加载或执行 P2.49e 真实动作；不得调用真实视觉模型、停止已有 Ollama、卸载原本驻留模型或访问主人/QQ 图片。
- 不读取、输出、记录或改写百炼 API Key 原值；未经新的 live 批准，不再次发送固定 `owner_private` PNG、不调用百炼、不重启 Bot/Owner Console，也不执行生产 QQ 图片验收。不得自动改用更贵模型，不得 fallback 到本地 Ollama 或 Plus。
- 恢复或扩展已撤销的 `core` 命令、scope 或正式能力。
- 自动 `commit`、`push` 或 `git add -A`。

必须保留且不得清理、删除、移动、覆盖、暂存或提交的主人文件：

```text
docs/juejin/17-local-dynamic-sticker-library-and-decoupled-classifier.md
docs/juejin/18-approval-gated-mainagent-document-artifacts.md
output/
tmp/
scripts/install-codex-browser-mcp-bridge.ps1
scripts/repair-codex-browser.ps1
scripts/switch-codex-staged-build.ps1
```

## 7. 已知问题和真实风险

- TTS 当前高层 `request_tts()` 会先调用 `ensure_tts_service()`；配置允许时可能启动本地 TTS 服务，并会记录可靠性事件。它不适合作为“无自动启动、无数据库写入”的 Owner Console 固定探测入口。
- TTS 服务 `/tts` 会在 `temp_audio/` 创建最终 WAV 和分段目录；P2.49d 专属 executor 已建立按后端 artifact ID 精确清理合同，但仍必须把短暂文件写入明确列为副作用，不能宣称整体只读。
- 历史 `/视觉状态` 已经执行程序生成 32×32 PNG 的真实 Ollama 推理，但会把异常细节整理进 QQ 状态文本，且没有 Owner Console 独立开关、二次确认、全局锁、受管理服务句柄或 `/api/ps` 模型驻留收口，因此 P2.49e 已新建独立 executor，没有复用生产视觉链。
- `scripts/start-ollama-vision.ps1` 默认会结束名为 `ollama`/`ollama app` 的所有进程；P2.49e 没有复用该脚本。Ollama 还可能承载 RAG embedding，因此已有服务绝不停止，原本驻留模型绝不卸载；只有初始明确离线且本次 `Popen` 仍可证明所有权时才停止本次句柄。
- P2.49e 不创建项目图片或诊断 artifact，但真实动作可能启动 Ollama、加载 GPU 模型，Ollama 外部运行时可能写自身日志/缓存；不能宣称整个外部进程零本地写入。
- P2.49e 首次主人 live 的固定图片与回答合同通过：模型 `qwen2.5vl:3b`，总计 34656 ms、推理 34392 ms、输入/输出/总 token 为 1103/32/1135。调用前模型未驻留并发送 `keep_alive=0`；旧实现仅在响应后 8 ms 立即读取一次 `/api/ps`，当时仍见模型而返回 `attention/vision_model_cleanup_incomplete`。稍后只读 `/api/ps` 显示目标模型不存在，支持异步释放与即时检查之间的竞态，但不能倒写为原运行当时已验证收口；该待复验状态已由下一条第二次 live 更新。
- P2.49e v1 第二次主人 live 已把上一条“尚未复验”更新为通过：`elapsed_ms=8821`、`inference_elapsed_ms=8373`、`cleanup_elapsed_ms=284`、`model_cleanup_poll_count=2`、`model_cleanup_verified=true`、最终 `succeeded/vision_managed_lifecycle_succeeded`。但源码审计确认 v1 prompt 直接包含预期四色数组，因此该结果只证明基础传输、结构响应和资源生命周期，不能充分证明感知内容来自图片。
- P2.49e v2 使用 scope=`owner_private` 的正式启用表情资产，只发送给本机 loopback Ollama并通过受保护 Owner Console GET 展示；这明确改变旧 `image_content_exposed=false` 边界为“固定登记参考图对主人可见”，但仍不读取或暴露聊天、QQ 临时图片、图片缓存、其他表情文件或任意路径。
- 严格结构化版主人 live 为 `failed/result_validation/vision_response_contract_mismatch`；模型实际描述为“一个戴着黑色帽子和白色披风的卡通角色，眼睛被红色心形遮住。”，与参考图主要可见内容不符。模型资源收口已验证通过；失败不能归因于资源生命周期。
- 最小自然描述版已完成主人 live：`run_id=1`、`elapsed_ms=11035`、推理 10474 ms、input/output/total token 为 1058/66/1124；底层模型请求与 2 次收口轮询成功，`model_cleanup_verified=true`。自然回复仍错误描述黑帽子/披风、眼睛遮挡、嘴部表情和实体纯黑背景，主人执行拒绝，最终为 `failed/owner_visual_review/vision_response_quality_rejected`。这证明问题不能简单归因于严格 JSON Schema；也不能仅凭该样本断言所有本地视觉任务都不可用。
- 百炼隔离探测已经按主人批准把固定 `scope=owner_private` PNG 发给外部供应商三次，并产生极低但非零的 token 使用；应用无法控制供应商侧数据处理与留存。隔离结果本身不证明 QQ 生产链，但后续两张 QQ 图片 live 已独立证明当前 Bot 的生产路径可用；仍不证明长期稳定性、工具选择或任意图片质量。
- 生产 `describe_images()` 已加载百炼北京地域 `qwen3.7-flash`，图片进入该函数后会自动外发；没有本地 Ollama 或 Plus 自动 fallback。主人已完成两张 QQ 图片 live 并接受质量。应用仍无法控制供应商侧处理与留存，不能把两张成功外推为所有图片或长期 SLA。
- `scripts/start.ps1` 仍调用 `ensure-ollama.ps1`，但视觉已不再构成本地 Ollama 依赖；只在启用 MemoryRAG/ProjectDocRAG 且 embedding provider 为 Ollama 时检查/准备 `bge-m3`。当前运行中的 Bot 不需为该脚本修订重启，效果从下一次启动开始体现。
- P2.49d 首次主人动作结果为 `workflow=tts_managed_lifecycle / stage=health_check / code=tts_health_contract_invalid`，`health_elapsed_ms=2014`、`service_start_attempted=false`、`tts_called=false`。只读复现确认无 7861 listener 时 httpx 返回 `ConnectTimeout`（约 2110 ms），无法进一步归因其 Windows 网络根因；最小修复只调整分类，不把 `ReadTimeout` 或健康合同异常视为离线。
- P2.49d 第二次主人 live 结果为 `stage=service_start / code=tts_service_start_timeout`，`elapsed_ms=49634`、`startup_elapsed_ms=47304`、`health_elapsed_ms=40542`、`service_start_attempted=true`、`service_started=false`、`service_stop_attempted=true`、`service_stopped=true`、`tts_called=false`。这证明 ConnectTimeout 分类修复生效，并证明受管理句柄安全收尾；不证明 TTS 服务、模型或合成可用。
- 第二次 live 所用版本曾在 uvicorn 监听前顶层导入 `torch` 和 `indextts.infer_v2.IndexTTS2`；该结构已按主人批准改为 lazy bootstrap。当前 `/health` 不触发 runtime import，首次 `/tts` 才进入重依赖导入与 `IndexTTS2(...)` 构造，并继续受 180 秒固定请求超时约束。第三次 live 已证明该结构与当前机器基础技术合成可用，但最终成功仍受新的主人音质门控约束。
- P2.49d 第三次主人 live 返回旧合同的 `succeeded/tts_managed_lifecycle_succeeded`：`elapsed_ms=70802`、`startup_elapsed_ms=1054`、`health_elapsed_ms=3201`、`synthesis_elapsed_ms=67565`、`cleanup_elapsed_ms=1`、WAV 132140 bytes/2995 ms；服务与磁盘收尾均通过。该结果证明技术链，不证明音频内容和听感；旧 WAV 已精确清理，不能恢复为本轮试听。
- 新听检门控会把技术成功先降为 `attention/owner_audio_review/tts_audio_quality_review_required`。预览只在 Owner Console 进程内存存在，不持久化、不暴露路径；主人接受后清除并恢复技术结果，拒绝后清除并返回 `failed/tts_audio_quality_rejected`。浏览器播放结束只负责解锁按钮，最终质量仍是主人明确判断。
- 主人质量 live 最终结果：`run_id=1`、`outcome=succeeded`、`stage=result_validation`、`code=tts_managed_lifecycle_succeeded`、`elapsed_ms=59780`、`startup_elapsed_ms=1031`、`health_elapsed_ms=3157`、`synthesis_elapsed_ms=56579`、`cleanup_elapsed_ms=1`、WAV 140844 bytes/3193 ms。`audio_quality_reviewed=true`、`audio_quality_accepted=true`、`audio_review_action_executed=true`；听检后 `audio_preview_available=false`，受保护预览 GET 返回 409，7861 无 listener。
- P2.49c 只证明一次固定 Main LLM 请求能够得到回答；它不验证通用工具选择、MainAgent planner/policy、RAG 索引或 TTS。
- MemoryRAG 的 2 条缺失向量是已确认事实，但主人未批准修复。
- 历史 `core` 实验已经按主人决定撤销；旧文档历史条目只说明曾发生，不得据此恢复命令或 scope。保留的 `connect_read_only()` 只加强既有数据库探针，不增加新命令。
- 2026-07-24 本次观察未发现 8080、8090、7861 监听；没有 shutdown、ERROR 或 traceback 证据时不得臆测原因。

## 8. 唯一下一步

```text
P2.49d 已完成 live_passed/owner_accepted。P2.49e 本地视觉的接口与资源收口已经 live 通过，但严格结构化版和最小自然描述版都未通过主人内容质量验收；自然描述版最终为 failed/owner_visual_review/vision_response_quality_rejected。

阿里云百炼固定样本、Owner Console 新页面和 QQ 生产视觉均已通过主人验收。2026-07-27 Bot runtime 对两张主人图片均快速返回准确描述，结构化记录两次 vision success。`scripts/start.ps1` 的陈旧 qwen2.5 检查也已收口：视觉不再触发 Ollama ensure，Ollama-backed RAG 仍保留 `bge-m3` 检查。当前阶段没有自动下一项；后续方向等待主人明确指定。
```

## 9. 证据入口

- [owner-console-manual-diagnostics-design.md](owner-console-manual-diagnostics-design.md)：P2.49 固定手动诊断合同、P2.49d/e 实现与 live 边界。
- [owner-console-cloud-vision-diagnostic-design.md](owner-console-cloud-vision-diagnostic-design.md)：百炼固定线上视觉诊断、独立凭据、固定成本、图片外发、主人质检和分阶段批准合同。
- [web-owner-console-v0-runbook.md](web-owner-console-v0-runbook.md)：Owner Console 启动、固定开关、人工操作和验收说明。
- [version-runlog.md](version-runlog.md)：按日期保存实现、测试和 live 历史；历史条目中的“当前/下一步/等待”只对条目日期有效。
- [main-agent-command-capability-audit.md](main-agent-command-capability-audit.md)：`/agent` 能力面审计，不作为主人当前路线图。
- Git：实时提交、差异和工作区状态的最终代码证据。
