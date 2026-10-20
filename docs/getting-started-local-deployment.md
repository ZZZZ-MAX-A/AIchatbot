# 本地部署入门：核心下载、必需向量模型与独立前端

本文提供 Windows PowerShell 部署流程、带注释的环境变量样例、按需下载清单，以及功能到源码文件的对应关系。
核心安装方案必须准备 Ollama `bge-m3`，默认开启普通聊天的 MemoryRAG；视觉、TTS、图片生成等其他模型权重不下载，Owner Console 前端单独取得。

## 1. 一行下载核心项目和必需向量模型

先安装 Git for Windows、Python 3.12+（加入 PATH）和 Ollama，安装后重新打开 PowerShell。核心部署不需要 Node.js。首次模型下载需要网络和足够磁盘空间，`bge-m3` 通常约 1.2 GB，以 Ollama 实际显示为准；运行时还需要内存。

在准备存放项目的父目录执行以下一行：

```powershell
& ([scriptblock]::Create((Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/ZZZZ-MAX-A/AIchatbot/codex/docs-neutral-persona/scripts/install-core.ps1').Content)) -Ref 'codex/docs-neutral-persona'
```

此命令使用当前审查分支，脚本下载地址与 `-Ref` 指向同一分支。该更新合并到 `main` 后，可以把地址中的 `codex/docs-neutral-persona` 和参数值一起改为 `main`。不要只改其中一处。

执行结果：

- 在当前目录创建 `AIchatbot/`，通过 Git partial clone 和 sparse checkout 取得根文件及 `config/`、`docs/`、`prompts/`、`scripts/`、`src/`、`tests/`。
- 不检出 `web/owner-console/` 前端，不安装 Node/npm 依赖。Git 服务端支持过滤时，前端文件 blob 也不会下载；Git 元数据可能仍包含路径名，不等于前端文件已安装。
- 从 `.env.example` 自动创建 `.env`，供你填写凭据。
- 连接本地 Ollama，必要时启动服务，只执行 `ollama pull bge-m3`，并通过 `/api/embed` 验证一次 1024 维 CPU 向量。已有模型会复用，但仍检查向量能否生成。
- 不拉取本地聊天、视觉、TTS、重排或图片生成模型，不安装 NapCat。源码中保留可选功能的配置字段与实现，关闭的功能不需要填写凭据或下载权重。

目标目录已存在时会拒绝覆盖。Ollama 未安装、模型下载失败或向量检查失败时，安装会报错，不会报告完成。模型失败后代码目录会保留；排除网络或 Ollama 问题后可在该目录重试：

```powershell
cd .\AIchatbot
.\scripts\install-vector-model.ps1
```

这是“下载核心源码并准备向量模型”的一行命令；Python 依赖安装、填写私人配置和 QQ 登录按下文完成。若 PowerShell 拦截本地脚本，可在当前终端临时执行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试。

模型权重由 Ollama 管理，不放入 Git 仓库。默认模型目录是 `%USERPROFILE%\.ollama\models`；自定义目录请在启动 Ollama 和 Bot 的终端里设置同一个 `$env:OLLAMA_MODELS`，或为启动检查脚本显式传入 `-ModelDir`。

完整源码也可以使用 `git clone https://github.com/ZZZZ-MAX-A/AIchatbot.git`，或 GitHub **Code → Download ZIP** 取得，但这两种方式会包含前端源码，而且不会自动下载 `bge-m3`；应另行运行向量安装脚本。

## 2. 编辑 .env、安装依赖并启动

### 2.1 必填项与最小样例

进入核心目录，打开安装器生成的配置：

```powershell
cd .\AIchatbot
notepad .env
```

根目录 [`.env.example`](../.env.example) 是完整配置样例，`config/.env.example` 是兼容副本。下面列出基础部署需要编辑或保留的值；建议直接编辑安装器生成的完整 `.env`。

```dotenv
# 【必填】替换为你自己的聊天服务 API Key
OPENAI_API_KEY=replace_with_your_api_key
# 【必须核对】服务商的 OpenAI 兼容接口地址及账户可用的模型名
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash

# 【必填】管理者 QQ 号，用于管理命令、长期记忆与 RAG 调试；不是机器人 QQ
BOT_OWNER_QQ=replace_with_your_qq_number
# 【条件必填】NapCat 启用访问 Token 时，两端填写相同值；否则留空
ONEBOT_ACCESS_TOKEN=

# 本地 Bot 接收 NapCat 连接的地址；同机部署可保持默认
HOST=127.0.0.1
PORT=8080
DRIVER=~fastapi+~httpx+~websockets

# 【基础 RAG 必需】核心安装器已下载 bge-m3；以下设置请保留
ENABLE_MEMORY_RAG=true
MEMORY_RAG_INJECT_IN_CHAT=true
MEMORY_RAG_EMBEDDING_PROVIDER=ollama
MEMORY_RAG_EMBEDDING_MODEL=bge-m3
MEMORY_RAG_EMBEDDING_BASE_URL=http://127.0.0.1:11434
MEMORY_RAG_EMBEDDING_DIMENSION=1024
MEMORY_RAG_EMBEDDING_TIMEOUT_SECONDS=60
# 默认使用 CPU，无需独立显卡
MEMORY_RAG_EMBEDDING_NUM_GPU=0
# 项目文档检索独立启用；基础记忆检索不依赖它
ENABLE_PROJECT_DOC_RAG=false

# 可选功能先关闭：无需额外模型和服务凭据
ENABLE_VISION=false
ENABLE_TTS=false
ENABLE_IMAGE_GEN=false
ENABLE_MAIN_AGENT=false
OWNER_CONSOLE_STATIC_ENABLED=false
```

`OPENAI_MODEL` 必须是服务商为你开放的模型；示例值不保证每个账户可用。普通聊天默认复用 `OPENAI_*`，完整样例中的 `CHAT_LLM_*` 保持注释。如果单独启用它们，需要填写可用值，不能取消注释后留空。不要将真实 Key、Token 或 `.env` 上传到 GitHub。

### 2.2 安装 Python 依赖，检查并初始化 RAG

从核心项目根目录执行：

```powershell
.\scripts\setup.ps1
.\scripts\install-vector-model.ps1
.\scripts\rebuild-rag-index.ps1 -Memory
```

`setup.ps1` 创建 `.venv` 并安装 Python 依赖，任一步失败会停止。第二条可重复执行，用于检查 Ollama 与 `bge-m3`。第三条为现有长期记忆和会话摘要建立索引。

全新数据库没有长期记忆和正式摘要时，索引为空是正常现象，模型安装成功不代表已经有可检索资料。此流程索引手动事实、偏好记忆和已完成的会话摘要，不索引短期原始消息或空窗场景摘要。Persona V2 隔离账户的持久记忆仍受既有功能边界限制。

### 2.3 启动 Bot 并接入 QQ

```powershell
.\scripts\start.ps1
```

保持该终端运行。脚本检查启用的本地 Ollama RAG 依赖后启动 NoneBot，默认监听 `127.0.0.1:8080`。启动检查不会替你下载缺失模型；缺失时应重跑 `install-vector-model.ps1`。

另行安装、启动并登录 NapCatQQ，在 NapCat 配置 OneBot v11 **反向 WebSocket**：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

如配置访问 Token，必须与 `.env` 的 `ONEBOT_ACCESS_TOKEN` 一致。QQ 登录、扫码及验证由部署者完成。详细接入方式见 [NapCatQQ 接入说明](napcatqq-setup.md)。只检查后端启动可暂不安装 NapCat；要通过 QQ 收发消息就必须接入。

连接后用 `BOT_OWNER_QQ` 对应的账号私聊机器人，可执行 `/状态`、`/RAG状态`。用 `/添加事实记忆 内容` 或 `/添加偏好记忆 内容` 写入测试资料后，可重建记忆索引，再执行 `/记忆检索 查询内容` 检查召回。索引与排障见 [RAG 使用手册](project-rag-usage.md)。

## 3. 必需组件、可选下载与独立前端

下表的默认值指随本次核心安装复制的 `.env.example`；既有用户的 `.env` 不会被自动修改。

| 组件或服务 | 是否必需 / 是否随核心取得 | 不安装或不配置时的影响 |
| --- | --- | --- |
| Git、Python 3.12+、Python 依赖 | 必需；工具预装，依赖由 `setup.ps1` 安装 | 无法完成核心部署 |
| 聊天 API 凭据 | 必需；自行填写，不下载本地聊天大模型 | 无法生成聊天回复 |
| Ollama + `bge-m3` | **基础 RAG 必需**；Ollama 预装，核心安装器自动拉取并检查模型 | 不满足本文基础 RAG 部署要求 |
| NapCatQQ | QQ 收发必需；单独安装与登录 | 无法通过 QQ 使用 Bot |
| Owner Console 前端、Node/npm | 可选；核心不检出前端，见下方独立下载 | 无 Web 面板，Bot 与 QQ 命令仍可使用 |
| 本地视觉模型 / 云视觉凭据 | 可选；`ENABLE_VISION=false`，不下载视觉模型 | 不提供图片理解 |
| IndexTTS2 服务、TTS 模型和音色 | 可选；`ENABLE_TTS=false` | 仅文字回复 |
| UVR5 | 可选；音频素材处理工具 | 不影响聊天或 RAG |
| MainAgent / Tavily 等外部服务 | 可选；默认关闭，需要时单独配置 | 不提供相应 Agent / 外部搜索能力 |
| 图片生成、Qwen Space 等服务 | 可选；对应开关默认关闭 | 不提供图片生成或编辑 |
| 本地表情素材与分类服务 | 可选；素材与自动附件默认关闭 | 不自动选取或发送表情 |
| 私人人格卡、共享世界卡、风格样本 | 可选；私人资料不随仓库下载 | 使用可用基础提示词与默认行为 |
| 项目文档 RAG | 可选；`ENABLE_PROJECT_DOC_RAG=false`，复用同一向量模型 | 不检索项目文档，不影响 MemoryRAG |

### 3.1 单独下载前端

需要 Web 面板时，在存放核心项目的同级父目录执行另一条命令：

```powershell
& ([scriptblock]::Create((Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/ZZZZ-MAX-A/AIchatbot/codex/docs-neutral-persona/scripts/install-owner-console.ps1').Content)) -Ref 'codex/docs-neutral-persona'
```

它创建 `AIchatbot-owner-console/`，只检出同一仓库的 `web/owner-console/` 及 sparse checkout 必带的根文件，不下载后端目录或任何模型。前后端目前仍在同一 GitHub 仓库中，独立下载和运行，不是另建了一个已发布仓库。

安装 Node.js 22.12+（或更新受支持版本）后，在一个终端从核心目录启动 API：

```powershell
cd .\AIchatbot
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

另一个终端从同级父目录进入前端：

```powershell
cd .\AIchatbot-owner-console\web\owner-console
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:5173/owner-console/`。Vite 将 API 请求代理到 `127.0.0.1:8090`；前端本身不启动 Bot，也不代替 API 后端。

如需使用构建后的静态页面，在前端目录执行 `npm run build`，然后从核心目录启动：

```powershell
# 同级目录布局；先停止前面手动运行的 8090 API，再启动静态托管
.\scripts\start-owner-console.ps1 -StaticDir "..\AIchatbot-owner-console\web\owner-console\dist" -Foreground
```

此时访问 `http://127.0.0.1:8090/owner-console/`。独立前端布局不要使用假定前端位于核心目录内的 `-Build`。更多功能与排障见 [Owner Console 运行手册](web-owner-console-v0-runbook.md)。

## 4. 人格资料与本地数据：哪些不能提交

以下内容属于部署者的本地配置或运行数据，应留在本地，不能上传到公开 GitHub：

| 路径 | 内容 | 仓库处理 |
| --- | --- | --- |
| `.env` 及其他实际凭据文件 | API Key、OneBot Token、真实 QQ 号、私有名单及服务地址 | `.gitignore` 忽略；仅提交不带真实值的 `.env.example` |
| `prompts/persona-cards/private/` | 真实人格卡、称呼、关系和个性化设定 | 忽略；只保留公开脱敏示例和目录说明 |
| `prompts/world-cards/private/` | 私人共同背景或关系事实 | 忽略；不随项目复制或公开 |
| `prompts/style-examples/` | 私人语言风格参考材料 | 忽略；如有需要，由部署者本机添加 |
| `data/`（`.gitkeep` 除外） | SQLite 数据库、访问名单、当前选择项、缓存、图片和记忆索引 | 忽略；属于运行实例的本地状态 |
| `logs/`（`.gitkeep` 除外） | Bot、服务和错误日志 | 忽略；提交前还需确认未复制到其他目录 |
| `tools/`、`voice-samples/`、`temp_audio/`、`tts-validation/` | 第三方程序、模型音色和音频产物 | 忽略或不纳入仓库；按需由部署者本机安装 |
| `backups/`、`tmp/`、`output/`、`picture/` | 备份、临时文件、生成物和本地图片 | 忽略或作为本地素材维护，不提交 |

允许提交的角色卡内容仅限明确脱敏的示例文件，例如 `prompts/persona-cards/public/*.example.md` 和 `*.example.auto-reply.json`。自定义人格卡请放在 `prompts/persona-cards/private/`，不要在公开模板中填入真实关系、姓名、偏好或私密资料。共享背景卡应放在本机的 `prompts/world-cards/private/`。

检查 Git 忽略规则：

```powershell
git check-ignore -v .env data/chatbot.db prompts/persona-cards/private/local.md prompts/world-cards/private/local.md
```

角色卡目录的更多说明见 [`prompts/persona-cards/README.md`](../prompts/persona-cards/README.md)。代码与 `.env` 中既有的角色键、配置变量名和素材 ID 是运行时兼容标识；不要为了文档措辞而擅自更改这些值，它们本身也不应包含真实人格卡正文。

## 5. 功能对应的主要源码文件

以下是主要入口和实现位置，按职责定位；单项功能通常由多个文件协作完成。

| 功能 | 主要文件 | 职责 |
| --- | --- | --- |
| NoneBot 启动与插件加载 | `bot.py`、`pyproject.toml` | 注册 OneBot v11 适配器并加载 `src/plugins`；声明 Python 依赖 |
| QQ 事件和命令入口 | `src/plugins/ai_chat/__init__.py` | 注册事件处理器、命令并连接各业务运行模块 |
| 配置读取与校验 | `src/plugins/ai_chat/config.py` | 读取环境变量、解析配置并提供运行时设置 |
| 权限和访问名单 | `src/plugins/ai_chat/access.py`、`access_store.py` | 访问策略、白名单/黑名单存储和权限判断 |
| 模型客户端与普通聊天 | `src/plugins/ai_chat/llm.py`、`graph/chat.py` | 角色提示词、模型调用及聊天子图 |
| RootGraph 路由 | `src/plugins/ai_chat/graph/root.py`、`graph/runtime.py`、`graph/state.py` | 运行状态、主路由和能力分发 |
| MainAgent | `src/plugins/ai_chat/graph/main_agent.py`、`owner_agent_runtime.py`、`graph/tool_registry.py` | 主人专用 Agent 流程、任务运行和受控工具注册 |
| SQLite 与消息历史 | `src/plugins/ai_chat/database.py`、`memory.py` | 数据库连接、表结构、历史读写与上下文组装 |
| 摘要压缩 | `src/plugins/ai_chat/summaries.py`、`compressor.py`、`gap_scene_summaries.py` | 会话摘要及空窗场景摘要维护 |
| 手动长期记忆 | `src/plugins/ai_chat/manual_memory.py` | 主人管理的长期记忆读写与展示 |
| RAG 检索 | `src/plugins/ai_chat/rag/`，尤其 `search.py`、`memory_sources.py`、`project_docs.py`、`embeddings.py` | 记忆和项目文档索引、向量、召回与搜索 |
| 人格卡和角色卡选择 | `src/plugins/ai_chat/role_cards.py`、`persona_scope.py`、`prompts/persona-cards/` | 加载角色卡、解析隔离范围及公开模板/本地卡目录 |
| 共享世界卡 | `src/plugins/ai_chat/world_cards.py`、`prompts/world-cards/private/` | 按映射读取本地共享背景，不提供公开内容 |
| 视觉识图 | `src/plugins/ai_chat/vision.py`、`aliyun_bailian_vision.py`、`graph/vision.py` | 图片上下文、云视觉客户端和视觉运行节点 |
| 语音与 TTS | `src/plugins/ai_chat/voice.py`、`tts_service.py`、`graph/voice.py` | 语音消息处理、TTS 服务接入和语音运行节点 |
| 表情分类与发送 | `sticker_intent.py`、`sticker_classifier.py`、`sticker_selection.py`、`sticker_attachment.py`、`sticker_library.py` | 意图合同、分类、候选选择、本地素材校验和发送门控 |
| Owner Console 后端 | `src/plugins/ai_chat/owner_console_fastapi_app.py`、`owner_console_read_runtime.py`、`src/owner_console_fastapi_launcher.py` | 本地管理 API、读取运行时和 FastAPI 启动入口 |
| Owner Console 前端 | `web/owner-console/src/` | 页面、API 客户端、组件、样式与前端构建 |
| 核心与前端独立下载 | `scripts/install-core.ps1`、`scripts/install-owner-console.ps1` | Git 稀疏检出核心或前端，拒绝覆盖已有目录；核心下载必须准备向量模型 |
| 必需向量模型准备 | `scripts/install-vector-model.ps1` | 下载或复用 `bge-m3`，检查一次 1024 维 CPU 向量；失败则停止安装 |
| 安装、启动和诊断脚本 | `scripts/setup.ps1`、`start.ps1`、`start-napcat-shell.ps1`、`diagnose.ps1` | Python 安装、Bot/NapCat 启动和本机诊断 |

查看设计和运维流程可从 [文档导航](README.md) 进入。
