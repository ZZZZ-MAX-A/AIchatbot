# 本地部署入门：下载、按需安装与源码导航

本文说明如何取得代码、运行最小 QQ 聊天服务、选择需要的可选组件，并按功能定位源码。
文中的部署值均为示例；实际服务状态应以本机配置和运行诊断为准。

## 1. 下载项目

任选一种方式：

```powershell
# Git 克隆
git clone https://github.com/ZZZZ-MAX-A/AIchatbot.git
cd AIchatbot
```

或打开 GitHub 仓库页面，选择 **Code → Download ZIP**，解压后在 PowerShell 进入解压出的项目目录。

项目源码和必需 Python 依赖由仓库提供。NapCat、Ollama 模型、TTS 模型、表情图片等较大的第三方程序或本地素材不放在 Git 仓库中，需要时单独取得。

## 2. 必需的本地配置

运行 QQ AI 聊天至少需要：

- Windows、Python 3.12 或更新版本。
- DeepSeek API Key，或兼容配置的模型服务凭据。
- QQ 接入端 NapCatQQ，以及由使用者本人完成的 QQ 登录。NapCat 不随本项目下载；只运行后端、不连接 QQ 时可以暂不安装。

在项目根目录创建本地配置文件：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少设置 `OPENAI_API_KEY` 和 `BOT_OWNER_QQ`。如果使用其他 OpenAI 兼容服务，再按服务方要求检查 `OPENAI_BASE_URL` 与 `OPENAI_MODEL`。不要把真实凭据写入 `.env.example` 或提交 `.env`。

安装项目依赖并启动 NoneBot 后端：

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

`setup.ps1` 会建立项目虚拟环境并安装 `pyproject.toml` 列出的 Python 依赖。需要通过 QQ 使用机器人时，另行安装并启动 NapCatQQ，按 [NapCatQQ 接入说明](napcatqq-setup.md)配置 OneBot v11 反向 WebSocket。登录、扫码、账号验证由部署者本人完成。

## 3. 哪些本地组件可以不下载

默认配置适合先运行基础聊天。可选功能保持关闭时，不需要安装或下载它们对应的服务、模型或素材。调整开关后重新启动 Bot。

| 组件或服务 | 对应功能 | 默认配置 | 不安装时的影响 |
| --- | --- | --- | --- |
| NapCatQQ | QQ 登录及 OneBot 消息收发 | 不随仓库提供 | 不接 QQ；Python 后端和代码检查仍可独立运行 |
| Ollama 与 `bge-m3` embedding 模型 | MemoryRAG、ProjectDocRAG 本地向量检索 | `ENABLE_MEMORY_RAG=false`、`ENABLE_PROJECT_DOC_RAG=false` | 两种 RAG 检索不可用；普通聊天、SQLite 历史和摘要仍可使用 |
| Node.js / npm 前端依赖 | Web Owner Console 浏览器界面 | 前端可独立安装；静态托管默认关闭 | 不使用 Web 面板；Bot 与 QQ 命令不受影响。需要时见 [Owner Console 运行手册](web-owner-console-v0-runbook.md) |
| IndexTTS2 服务及模型/音色文件 | 语音合成 | `ENABLE_TTS=false` | 只提供文字回复 |
| UVR5 | 本地音频分离和素材处理工具 | 按需单独使用 | 不影响基础聊天；也不是运行文字或 TTS 服务的必要条件 |
| Tavily 凭据及外部网络读取 | MainAgent 外部网页搜索 | `ENABLE_MAIN_AGENT=false`、`ENABLE_AGENT_WEB=false` | 外部读取不可用；普通聊天和本地工具不受影响 |
| 视觉 API 凭据 | QQ 图片识别 | `ENABLE_VISION=true`，凭据模板为空 | 未配置可用提供方前，建议将 `ENABLE_VISION=false`；不用单独下载本地视觉模型 |
| 图片生成服务凭据 | 主人私聊图片生成/编辑 | `ENABLE_IMAGE_GEN=false` | 图片生成与普通聊天分离，不启用时不需要配置服务 |
| Hugging Face Qwen Space | 远程图片编辑 | `ENABLE_QWEN_SPACE_EDIT=false` | 不使用此项图片编辑，不需要本地模型下载 |
| 本地表情图片与分类服务 | 自动表情意图及附件 | 本地表情库、分类和自动附件开关默认关闭 | 不自动挑选或发送表情；不影响文字聊天 |
| 私人人格卡、共享世界卡、风格样本 | 定制角色表达与本地背景 | 可选；目录可留空 | 使用应用的基础提示词和可用默认行为；没有定制卡不妨碍安装依赖或启动 |

组件与开关的当前细节以仓库根目录 `.env.example` 注释和对应专题运行手册为准。不要因为未使用某项功能而下载它的大型模型或素材。

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
| 安装、启动和诊断脚本 | `scripts/setup.ps1`、`start.ps1`、`start-napcat-shell.ps1`、`diagnose.ps1` | Python 安装、Bot/NapCat 启动和本机诊断 |

查看设计和运维流程可从 [文档导航](README.md) 进入。
