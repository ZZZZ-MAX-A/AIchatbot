# Web Owner Console v0 runbook

核心精简下载不包含本前端。需要独立取得前端源码并连接核心 API 时，先按 [本地部署入门：独立前端](getting-started-local-deployment.md#31-单独下载前端) 操作；本文中的同目录构建命令适用于完整检出布局。

本文记录 Web Owner Console 的本地使用手册和启动排障流程。它把 FastAPI 业务只读 HTTP adapter、Vite 前端、固定手动诊断例外、前端边界 guard 和后端 HTTP contract 测试串成一套日常开发验证步骤。

当前 runbook 只覆盖 loopback 本地开发、只读查看和主人显式启用的固定手动诊断，不是公网部署手册。

## 1. 定位

Web Owner Console v0 是 AIchatbot 的本地主人控制台：

```text
FastAPI 提供本地业务只读 JSON read model，以及启动时逐项授权的固定手动诊断例外。
Vite + React 前端展示结构化状态和只读详情；固定动作只在独立开关启用后出现并要求二次确认。
前端通过 Vite dev proxy 访问 127.0.0.1:8090。
主界面访问地址是 http://127.0.0.1:5173/owner-console。
```

它不是：

```text
QQ adapter。
普通聊天入口。
MainAgent 自动执行入口。
公网管理后台。
登录/鉴权系统。
审批写操作页面。
```

## 2. 当前页面

主导航页面：

```text
Dashboard：总览任务、审批和诊断摘要。
Tasks：任务列表，支持只读状态筛选。
Approvals：审批列表，支持只读状态筛选。
Diagnostics：诊断快照，只展示状态，不执行探测。
Memory：记忆快照，只展示计数和边界，不暴露正文。
Access Control：访问控制快照，只展示名单统计和策略。
Settings：设置快照，只展示脱敏配置和功能开关。
```

详情页不放在主导航里，只从列表进入：

```text
Task Detail：/owner-console/tasks/:task_id
Approval Detail：/owner-console/approvals/:approval_id
```

顶部状态条应始终能看到：

```text
主人控制台
只读模式=true
网页写入=false
后端已连接 / 后端未连接
schema_version
最后刷新时间
自动刷新开关，完整页面加载后默认关闭
```

## 3. 启动前检查

在项目根目录检查当前仓库状态：

```powershell
cd D:\AIchatbot
git status -sb
git log --oneline -5
```

确认后端端口未被占用：

```powershell
netstat -ano | Select-String ':8090'
```

确认前端端口未被占用：

```powershell
netstat -ano | Select-String ':5173'
```

如果端口被占用，可以先停止对应开发进程。后端也可以临时改成 8091，但此时需要同步调整 Vite proxy 或环境配置；日常开发推荐继续使用 8090。

Owner context 页面依赖 `BOT_OWNER_QQ`。如果未配置，以下页面可能显示后端 403，这是预期的权限边界，不代表服务挂了：

```text
Dashboard
Tasks
Task Detail
Approvals
Approval Detail
```

以下页面通常不依赖 owner 私聊上下文：

```text
Diagnostics
Memory
Access Control
Settings
```

## 4. 启动后端

打开第一个 PowerShell，在项目根目录启动 FastAPI：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

看到类似输出表示后端已启动：

```text
Uvicorn running on http://127.0.0.1:8090
```

这个窗口不要关闭。

必须使用 `src.owner_console_fastapi_launcher:app`，不要直接用：

```text
src.plugins.ai_chat.owner_console_fastapi_app:app
```

原因是 `src.plugins.ai_chat` 是 NoneBot / QQ 插件包。Web Owner Console 后端需要通过 launcher 安装 package stub 后再加载 FastAPI app，避免执行 QQ adapter 入口。

## 5. 启动前端

打开第二个 PowerShell：

```powershell
cd D:\AIchatbot\web\owner-console
npm install
npm run dev
```

看到 Vite 输出后访问：

```text
http://127.0.0.1:5173/owner-console
```

`npm install` 只需要首次或依赖变化后运行。日常启动只需要：

```powershell
cd D:\AIchatbot\web\owner-console
npm run dev
```

当前 Vite dev server 会代理：

```text
/healthz -> http://127.0.0.1:8090/healthz
/api/v1/owner-console -> http://127.0.0.1:8090/api/v1/owner-console
```

## 5.1 本地静态模式

如果只想本地打开控制台，而不单独启动 Vite dev server，可以先构建前端：

```powershell
cd D:\AIchatbot\web\owner-console
npm run build
```

然后打开新的 PowerShell，从项目根目录启动带静态页面的 FastAPI：

```powershell
cd D:\AIchatbot
$env:OWNER_CONSOLE_STATIC_ENABLED='true'
$env:OWNER_CONSOLE_STATIC_DIR='web/owner-console/dist'
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

访问：

```text
http://127.0.0.1:8090/owner-console
```

更方便的后台启动方式：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1
```

如果还没有构建前端，可以让脚本先构建：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1 -Build
```

脚本会：

```text
检查 .venv\Scripts\python.exe 是否存在。
检查 8090 是否已被占用。
检查 web/owner-console/dist/index.html 是否存在。
设置 OWNER_CONSOLE_STATIC_ENABLED=true。
设置 OWNER_CONSOLE_STATIC_DIR=web/owner-console/dist。
后台隐藏启动 uvicorn。
写日志到 logs/owner-console.out.log 和 logs/owner-console.err.log。
```

停止后台控制台：

```powershell
cd D:\AIchatbot
.\scripts\stop-owner-console.ps1
```

需要前台调试时：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1 -Foreground
```

边界：

```text
/api/v1/owner-console/* 仍然只返回 JSON API。
/owner-console/* 只服务前端页面或静态资源。
/owner-console/tasks/1 刷新时会 fallback 到 index.html。
/owner-console/assets/missing.js 返回 404，不 fallback。
/docs、/redoc、/openapi.json 仍然关闭。
静态页面的业务 read model 仍只能调用 GET allowlist；只有启动时逐项显式启用的 P2.49 固定手动诊断，才可调用五条精确 POST allowlist。
```

## 6. 手动验收顺序

### P2.40a 自动刷新基础设施

当前顶部状态区已经提供“自动刷新”开关：

```text
默认关闭。
只保存在当前 AppShell 内存中，浏览器完整刷新后恢复关闭。
开启后当前只每 60 秒检查一次 /healthz。
页面隐藏时暂停 timer 并取消自动 health 请求。
连续 3 次网络/5xx 失败后暂停；400/403/404 或 contract mismatch 立即暂停。
手动刷新成功后恢复调度。
Dashboard、Tasks、Approvals 和 Detail 业务数据当前仍然只支持首次加载和手动刷新。
```

业务页面不会在 P2.40a 自动接入轮询。P2.43c 已形成真实 running 任务生命周期，但仍需根据实际工作负载单独评估是否以 60-120 秒低频刷新接入。Diagnostics、Memory、Access Control 和 Settings 继续保持手动刷新。

建议按这个顺序看页面：

```text
1. Dashboard：确认顶部状态条显示后端已连接、只读模式=true、网页写入=false。
2. Diagnostics：确认诊断快照只展示状态，不执行外部探测。
3. Memory：确认 memory_content_exposed=false，retrieval_executed=false，index_rebuild_executed=false。
4. Access Control：确认只展示名单和策略摘要，没有添加/移除按钮。
5. Settings：确认 API Key 不展示原文，模型和 base_url 为脱敏状态。
6. Tasks：确认只有刷新和状态筛选，没有创建/取消/重试按钮。
7. Task Detail：从任务列表进入，确认只展示目标、结果、事件和关联审批。
8. Approvals：确认只有刷新和状态筛选，没有确认/拒绝/恢复按钮。
9. Approval Detail：从审批列表进入，确认只展示审批请求、风险和关联任务。
```

如果 `BOT_OWNER_QQ` 未配置，Dashboard、Tasks、Approvals 返回 403 是正常表现。此时重点检查顶部连接状态和非 context 页面即可。

### P2.49 固定手动诊断

普通启动不显示动作面板，也不接受手动诊断 POST：

```powershell
.\scripts\start-owner-console.ps1
```

只有主人批准本次人工操作后，才按需逐项增加开关。例如同时开放前三个已完成 live 的工作流：

```powershell
.\scripts\start-owner-console.ps1 `
  -EnableProjectDocRagProbe `
  -EnableMemoryRagConsistencyProbe `
  -EnableMainLlmContractProbe `
  -EnableTtsSynthesisProbe `
  -EnableCloudVisionProbe
```

| 启动开关 | workflow | 真实动作 | 已确认副作用 |
|---|---|---|---|
| `-EnableProjectDocRagProbe` | `project_doc_rag_fixed_retrieval` | 一次固定 embedding + SQLite `mode=ro` 前五项检索 | 远程/本地 embedding 调用；业务数据库零写入 |
| `-EnableMemoryRagConsistencyProbe` | `memory_rag_index_consistency` | SQLite `mode=ro` 计数一致性 | 不读记忆正文、不检索、不 embedding、不修复 |
| `-EnableMainLlmContractProbe` | `main_llm_fixed_contract` | 一次固定 Main LLM 问答 | 少量 token；无工具、RAG、聊天历史或业务数据库写入 |
| `-EnableTtsSynthesisProbe` | `tts_managed_lifecycle` | 一次受控服务检查/必要时临时启动 + 固定 TTS 合成 + 精确产物清理 + 所有权收尾 | 可能冷加载 GPU 模型；只删除本次 artifact ID；不停止已有服务，不扫描其他进程；无重试、QQ、可靠性事件或业务数据库写入 |
| `-EnableCloudVisionProbe` | `cloud_vision_fixed_description` | 把固定 owner_private 表情 PNG 发送到百炼北京地域 `qwen3.7-flash` 一次，并由主人对照参考图质检 | URL/Key 只显示配置布尔值；图片会外发且供应商侧留存不受应用控制；无 tools/thinking/retry，不 fallback 到 Ollama/Plus，不写 QQ、RAG、聊天、可靠性或业务数据库 |

固定操作顺序：

```text
1. 先核对启动参数和页面显示的 supported_workflows。
2. 确认对应 latest_run 为空；启动不得自动执行动作。
3. 第一次点击只展开中文风险说明，不发送 POST。
4. 主人阅读后点击“确认并执行”，只发送一次固定 POST。
5. 核对 run_id、attempt_count、workflow、stage、code 和零副作用布尔证据。
6. 不因 attention 自动重试、修复、串行执行其他工作流或重启服务。
```

五个动作共享一个 Owner Console 进程内全局锁：同一时间最多运行一个，不排队；并发请求返回 409。最近结果只存在当前 Owner Console 进程内，重启后消失。状态 GET 本身不执行 embedding、模型、检索、一致性、TTS 或视觉动作。

固定 POST 只接受 loopback 同源 Origin、进程内动作 Cookie、`application/json`、精确 Header 和精确 confirmation。页面不提供 prompt、模型、URL、路径、工具或参数输入。操作完成后保留英文 `workflow/stage/code`；中文只能解释，不能覆盖英文证据。

P2.49d 的启动开关、页面二次确认和固定 POST 已实现。2026-07-25 已加载到 Owner Console；首次主人动作在无 7861 listener 时得到 `ConnectTimeout`，旧分类没有进入启动，未加载模型、未调用 `/tts`、未创建 WAV。主人批准的最小修复只把连接建立阶段的 `ConnectTimeout` 归为离线；`ReadTimeout`、HTTP、JSON 或 health contract 异常仍不盲目启动。真实操作必须满足“只显式启用 `-EnableTtsSynthesisProbe`、主人在页面二次确认”的顺序；无需主人预先启动 TTS。按钮执行时，已有服务只复用且不停止；明确离线时由 Owner Console 启动一个持有句柄的受管理子进程，完成一次固定合成、精确清理本次产物，再只停止该进程。不得按端口或进程名扫描、结束其他 TTS/Python 进程。

TTS 固定 POST 为：

```text
POST /api/v1/owner-console/manual-diagnostics/tts-synthesis
Content-Type: application/json
X-Owner-Console-Action: manual-tts-synthesis-v1
{"confirmation":"run_registered_tts_synthesis"}
```

页面不提供文本、voice、emotion、URL、timeout 或输出路径控件。确认文案必须说明：明确离线时会启动受管理子进程，已有服务绝不停止；`loaded=false` 时可能冷加载 IndexTTS2；验证后只清理本次 artifact ID 的 WAV 与分段目录；只停止本次持有句柄的进程，不扫描其他进程；不会发 QQ、写可靠性事件/业务数据库、调用 LLM/RAG 或重试合成。

初始 health 分类固定为：

```text
ConnectError / connection refused / ConnectTimeout
  => 连接未建立，允许进入受管理启动和 owner fingerprint 校验

ReadTimeout / HTTP error / invalid JSON / invalid health contract
  => 可能存在已连接或未知服务，不启动第二个进程
```

2026-07-25 主人第二次 live 已确认 `ConnectTimeout` 分类修复生效，但受管理服务在 45 秒内仍未健康：

```text
stage=service_start
code=tts_service_start_timeout
service_start_attempted=true
service_started=false
service_stop_attempted=true
service_stopped=true
tts_called=false
```

第二次 live 的结论永久保留为失败，不能被后续代码修订覆盖。主人随后已批准并完成 lazy bootstrap：`tts_service.py` 启动和 `/health` 不再依赖 torch/IndexTTS 导入，health 会显示 `loaded` 与 `runtime_imported`；首次 `/tts` 才导入 runtime 并构造模型。页面结果新增“调用前 runtime”和英文 `runtime_imported_before=true|false`。45 秒启动、180 秒合成、owner fingerprint、一次执行、精确清理和只停止本次句柄未改变。

2026-07-25 lazy-bootstrap 版本第三次主人 live 已完成技术验证：总计 70802 ms，启动 1054 ms，合成 67565 ms，WAV 132140 bytes/2995 ms；`runtime_imported_before=false`、`service_started=true`、`tts_called=true`、`artifact_cleanup_succeeded=true`、`service_stopped=true`。但该版本在页面试听前已删除 WAV，因此只证明技术链，不证明固定内容和听感。

主人批准后，当前页面已改为两阶段门控：

```text
第一次页面二次确认：只执行一次固定 TTS，并完成磁盘与服务收尾。
技术失败：直接 failed，不出现试听。
技术通过：显示“等待试听”，不是最终通过。
点击“加载临时试听”：从 Owner Console 进程内存读取当前 run 的 audio/wav。
音频播放结束：“语音合格”按钮解锁。
明确接受：恢复底层技术 outcome/code；底层 attention 仍保留。
明确拒绝：failed/owner_audio_review/tts_audio_quality_rejected。
```

页面固定显示：

```text
应听到：这是一次固定语音合成检查。
```

主人应检查内容完整准确、中文清晰，并确认没有明显截断、重复、卡顿、爆音、杂音或不合理长静音。发现明显问题可在音频加载后直接点“语音不合格”；只有完整播放后才能点“语音合格”。两个按钮都不再次调用 TTS。

预览安全边界：磁盘 WAV 和分段目录在合成 POST 内仍立即精确清理；试听只使用当前 Owner Console 进程内单一受限 WAV 字节槽，绑定 run_id，不持久化、不返回路径。GET 要求 loopback、动作 Cookie、固定 `manual-tts-audio-preview-v1` Header；响应为 `audio/wav`、`Cache-Control: no-store`。接受/拒绝使用两个固定同源 POST，错误 run、额外字段、重复审核或并发均 409/400 fail closed。开始下一次 TTS 或 Owner Console 重启会使旧预览失效。

主人已按上述流程重新运行、试听并明确接受。本次最终为 `succeeded/result_validation/tts_managed_lifecycle_succeeded`，总计 59780 ms、合成 56579 ms、WAV 140844 bytes/3193 ms；`audio_quality_reviewed=true`、`audio_quality_accepted=true`、`audio_review_action_executed=true`。审核后 `audio_preview_available=false`，受保护 preview GET 返回 409；磁盘 WAV/分段目录已清理，7861 无 listener。P2.49d 已完成主人验收，无需重复运行。

P2.49e 本地 Ollama v1 的接口和资源收口已 live 通过，但固定正式表情的严格结构版与自然描述版都未通过主人内容质量验收。百炼第三次隔离回复随后获主人接受。2026-07-27 Owner Console PID 15220 的新页面由主人确认无问题；Bot PID 24552/15332 加载生产主链后，主人连续发送两张 QQ 图片，均得到快速准确描述，同一 runtime 记录两次结构化 vision success。生产云视觉验收已通过。

当前云视觉固定 POST 为：

```text
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description
Content-Type: application/json
X-Owner-Console-Action: manual-cloud-vision-fixed-description-v1
{"confirmation":"run_registered_cloud_vision_fixed_description"}
```

页面不提供图片上传、任意路径、自由 prompt、模型、URL、Key、工具、token 参数、fallback 或连续测试控件。当前云诊断只读取正式 manifest 与固定启用的 `aike_affection_005.png`，并在外发前校验 owner_private、普通文件边界、文件名、MIME、500×500、162977 bytes 和固定 SHA-256；不扫描其他表情。固定 prompt 为：“请用80至150字的自然中文，描述这张图片中明确可见的内容，并概括它传达的情绪或感情色彩；可以结合人物表情、动作和画面元素判断，但不要猜测被遮挡或无法确认的细节。”请求固定 `qwen3.7-flash`、`enable_thinking=false`、无 tools、无 retry；失败不调用本地 Ollama 或 Plus。

页面原位替换旧视觉面板，显示 provider、北京地域、模型、URL/Key 配置布尔值、owner_private 外发说明、固定参考图、清理后回复、`response_cleanup_applied`、input/output/total token、耗时和主人审核。完整 URL、Key、Base64 和供应商原始错误正文不显示。Owner Console 普通加载未执行诊断；Bot 生产主链随后通过两张 QQ 图片 live。

以下本地视觉合同只作为 P2.49e 历史证据保留；当前启动脚本和默认页面不再提供 `-EnableVisionInferenceProbe`：

v1 以下四色 JSON 只作为历史基础合同，不再是当前 v2 验收输入：

```json
{"contract_version":"vision.fixed.v1","grid":["red","blue","green","white"],"status":"ok"}
```

自然描述版自动层只要求响应完成、assistant role、无工具、非空、未超 2048 字符、非重复乱码并至少有 8 个汉字；不自动判断人物、发色、眼睛、爱心或主题。空回答、重复无效符号、基本中文不足、服务无法启动、模型缺失、请求失败、超时或 `done=false` 全部 failed。基础回复通过后先返回 `attention/owner_visual_review/vision_response_quality_review_required`，页面展示实际自然回复和受保护固定参考图；`semantic_contract_automatically_validated=false`，主人接受后才恢复底层 technical 结果，拒绝则 `failed/vision_response_quality_rejected`。审核不再次推理。

当前云固定参考图 GET 与主人质检 POST：

```text
GET  /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/reference-preview
      X-Owner-Console-Action: manual-cloud-vision-reference-preview-v1

POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept
     X-Owner-Console-Action: manual-cloud-vision-response-quality-accept-v1
     {"confirmation":"accept_latest_cloud_vision_response_quality","run_id":<当前 run>}

POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject
     X-Owner-Console-Action: manual-cloud-vision-response-quality-reject-v1
     {"confirmation":"reject_latest_cloud_vision_response_quality","run_id":<当前 run>}
```

## 7. 自动化验证

前端验证：

```powershell
cd D:\AIchatbot\web\owner-console
npm run guard:readonly
npm test
npm run typecheck
npm run build
npm audit
```

关键期望：

```text
guard:readonly 通过。
test 显示 4 个测试文件、31 项测试通过。
typecheck 通过。
build 通过。
npm audit 显示 found 0 vulnerabilities。
```

后端 HTTP contract 验证：

```powershell
cd D:\AIchatbot
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
```

关键期望：

```text
Ran 29 tests OK
```

目前测试中可能出现 Starlette / httpx deprecation warning。只要最终结果是 OK，不影响当前判断。

## 8. 只读边界

当前必须保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent。
MainAgent 和 ChatAgent 保持分离。
ProjectDocRAG 只允许在显式 /agent dev_context 中使用。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复执行。
不开放多步写自动化。
不新增额外 QQ 发送副作用。
业务 read model 保持 GET-only；P2.49 固定手动诊断是逐项启动授权的受限运行时动作，不开放通用网页写能力。
```

前端当前只允许调用：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/diagnostics
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/manual-diagnostics
GET /api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-preview
GET /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/reference-preview

仅在对应启动开关开启时允许：
POST /api/v1/owner-console/manual-diagnostics/project-doc-rag
POST /api/v1/owner-console/manual-diagnostics/memory-rag-consistency
POST /api/v1/owner-console/manual-diagnostics/main-llm-contract
POST /api/v1/owner-console/manual-diagnostics/tts-synthesis
POST /api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-quality/accept
POST /api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-quality/reject
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept
POST /api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject
```

不要在 v0 中加入：

```text
上述固定 allowlist 之外的 POST，以及任何 PUT / PATCH / DELETE。
审批确认/拒绝按钮。
恢复执行按钮。
创建、取消、重试任务按钮。
保存设置按钮。
切换角色卡按钮。
修改名单按钮。
新增/删除记忆按钮。
自由 prompt、自由模型、自由 URL、自由路径、自由工具或自由参数的诊断按钮。
未经 P2.40b 页面接入和 guard 验证的业务自动轮询、WebSocket 或 SSE。
登录页假实现。
```

## 9. 常见问题

### 后端未连接

现象：

```text
顶部状态条显示后端未连接。
页面出现 fetch failed 或加载失败。
```

检查：

```powershell
netstat -ano | Select-String ':8090'
```

确认后端是否用正确方式启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

### 页面返回 403

通常是 `BOT_OWNER_QQ` 未配置，或当前本地数据没有 owner 私聊上下文。检查：

```powershell
$env:BOT_OWNER_QQ
```

如果使用项目根目录 `.env`，修改后需要重启 Uvicorn。

### 详情页返回 404

详情页 ID 必须来自列表。返回 404 通常表示：

```text
ID 不存在。
ID 存在但不属于 owner 私聊上下文。
```

这是 owner 过滤边界，不应绕过。

### /docs、/redoc、/openapi.json 返回 404

这是预期行为。当前 v0 故意不暴露 OpenAPI 页面。

### npm run dev 启动失败

先确认依赖是否安装：

```powershell
cd D:\AIchatbot\web\owner-console
npm install
```

再确认 5173 是否被占用：

```powershell
netstat -ano | Select-String ':5173'
```

### build 后直接打开 dist 没有数据

不要直接双击打开 `web/owner-console/dist/index.html`。当前本地静态模式需要由 FastAPI 服务：

```powershell
cd D:\AIchatbot
$env:OWNER_CONSOLE_STATIC_ENABLED='true'
$env:OWNER_CONSOLE_STATIC_DIR='web/owner-console/dist'
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

然后访问：

```text
http://127.0.0.1:8090/owner-console
```

或者直接使用脚本：

```powershell
cd D:\AIchatbot
.\scripts\start-owner-console.ps1 -Build
```

## 10. 相关文档

```text
docs/web-owner-console-read-model-design.md
docs/web-owner-console-read-only-shell-design.md
docs/web-owner-console-local-deployment-design.md
docs/owner-console-fastapi-smoke-runbook.md
docs/web-owner-console-frontend-stack-design.md
docs/web-owner-console-ui-layout-design.md
docs/web-owner-console-frontend-readonly-audit.md
docs/web-owner-console-frontend-contract-guard.md
docs/web-owner-console-readonly-auto-refresh-design.md
docs/owner-console-manual-diagnostics-design.md
web/owner-console/README.md
```

## 11. 历史路线与当前授权

下列 P2.39–P2.44 内容是 Owner Console 形成过程中的历史顺序，不是当前路线图；P2.40b、P2.41、P2.42 等候选也不因仍未完成而自动获得授权。当前唯一下一步必须读取 [current-development-status.md](current-development-status.md)。

历史顺序：

```text
P2.39：本地部署方式设计，见 docs/web-owner-console-local-deployment-design.md。
P2.39a：按设计实现可选本地静态模式。已完成。
P2.39b：Owner Console 本地一键启动/停止脚本。已完成。
P2.40：只读自动刷新策略设计。已完成，见 docs/web-owner-console-readonly-auto-refresh-design.md。
P2.40a：受控自动刷新基础设施、AppShell health 检查和生命周期测试。已完成。
P2.43：首个正式 MainAgent 只读工作任务模型与 Owner Console `running` 只读展示。已完成，见 docs/main-agent-first-readonly-work-task-design.md。
P2.44：显式研发上下文任务已返回受限结构化详细回复；Owner Console 仍只显示不含详细回复的安全持久化摘要，见 docs/main-agent-useful-development-context-report-design.md。
P2.40b：仍保持人工评估；只有实际工作负载需要时才接入 Dashboard、Tasks、Approvals 和两个 Detail 页面。
P2.40c：guard、runbook 和浏览器 smoke 收口。
P2.41：设计本地访问保护 / 鉴权。
P2.42：单独设计 Web 审批操作，不能直接在 v0 只读页面上加按钮。
```

此后 P2.48 完成可靠性页和诊断页可读性优化，P2.49a–c 完成 ProjectDocRAG、MemoryRAG 一致性和 Main LLM 固定手动诊断。P2.49d 的 TTS 技术链、主人音质和资源收尾已通过。P2.49e 本地视觉的接口与资源收口通过，但复杂表情内容质量被拒绝。百炼 `qwen3.7-flash` 隔离回复、Owner Console 页面与两张 QQ 生产图片现均已由主人接受；生产云视觉完成 live。
