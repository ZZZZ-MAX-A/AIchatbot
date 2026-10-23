# 本地部署入门：从下载到跑通

本文面向第一次拿到本项目的使用者，回答三个问题：

1. 哪些文件和目录**永远不要提交到 Git**（尤其是人设卡和人格设置）。
2. 哪些功能组件是**可选的**，本地部署时可以选择下载或不下载。
3. 最小可用的启动步骤是什么。

## 一、绝对不要写入仓库的文件

以下路径已被 `.gitignore` 默认拒绝，`scripts/check_repository_privacy.py` 会在提交前再次拦截。请保持它们留在本地。

| 路径 | 内容 | 为什么不能提交 |
| --- | --- | --- |
| `.env` | 全部密钥、QQ 号、白名单、私聊边界 | 含 API Key 和真实账号信息 |
| `prompts/persona-cards/private/` | 真实人设卡（如 `aike.md`、`linyin.md`） | 人设卡包含真实称呼、关系设定、隐私边界、触发词和个人偏好 |
| `prompts/persona-cards/` 根目录的本地真实卡（如 `aike.auto-reply.json`、`moyan.md`） | 旧位置的真实卡 | 同上；新卡请放到 `private/` |
| `prompts/world-cards/private/` | 共享世界观卡（如 `aike-linyin.md`） | 包含真实关系事实，永远只在本地运行时读取 |
| `prompts/style-examples/` | 私密语言风格样本 | 含角色特定表达，运行时本地加载 |
| `data/`（`.gitkeep` 除外） | `chatbot.db`、`chat-interactions.db`、`access.json`、`active-role-card.json`、生成的图片、表情包、记忆数据 | 全部是运行时私人数据 |
| `logs/` | 运行日志 | 可能包含聊天片段和账号信息 |
| `tools/` | 本地安装的 NapCat、UVR5 等第三方程序 | 体积大且非本项目源码 |
| `backups/`、`tmp/`、`output/`、`voice-samples/`、`temp_audio/`、`tts-validation/` | 本地产物和备份 | 私人数据或大文件 |
| `/picture/` | 本地表情包原始图片 | 私人素材 |

仓库里允许提交的只有：

- `prompts/persona-cards/public/*.example.md` 和 `*.example.auto-reply.json`：脱敏示例模板。
- `prompts/persona-cards/README.md`、`prompts/world-cards/README.md`：目录说明。
- 对应目录下的 `.gitkeep` 占位文件。
- `config/.env.example`、`web/owner-console/.env.example`：配置模板（不含真实 Key）。

首次使用的人只需要：把 `.env.example` 复制为 `.env` 并填入自己的 Key；把 `public/default.example.md` 复制到 `private/` 下改写成自己的人设卡。运行时加载顺序是 `private/` → 根目录旧本地卡 → `public/` 示例，同名卡优先取更私密的版本。

提交前自检：

```powershell
python scripts/check_repository_privacy.py
```

## 二、可选组件：按需下载

核心运行只需要 Python + NoneBot + DeepSeek API Key + NapCat（QQ 接入）。其余功能都可以在 `.env` 中保持关闭（默认即关闭），不下载对应程序完全不影响启动。

| 组件 | 对应功能 | 开关（`.env`） | 不装会怎样 |
| --- | --- | --- | --- |
| DeepSeek API Key | 基础聊天 | `OPENAI_API_KEY` | **必需**，没有它无法聊天 |
| NapCatQQ | QQ 消息接入 | `NAPCAT_QQ` | **必需**；只装了也能先本地跑通 Owner Console |
| Ollama + bge-m3 模型 | 记忆 RAG、项目文档 RAG | `ENABLE_MEMORY_RAG` / `ENABLE_PROJECT_DOC_RAG`（默认 false） | 不装则 RAG 功能关闭，普通聊天和会话摘要不受影响；`scripts/ensure-ollama.ps1` 检测到 RAG 关闭会直接跳过 |
| IndexTTS2 | 语音回复（TTS） | `ENABLE_TTS`（默认 false） | 不装则全部文字回复；`scripts/start-tts-service.ps1` 只在启用时需要 |
| UVR5 | 语音参考素材处理 | 无直接开关，服务于 TTS 音色 | 不装不影响 TTS 基础功能 |
| Owner Console 前端（`web/owner-console`） | 本地 Web 管理面板 | `OWNER_CONSOLE_STATIC_ENABLED`（默认 false） | 不装则用 QQ 命令管理；需要时再 `npm install && npm run build` |
| 阿里云百炼 / 云端视觉 | 识图 | 视觉相关配置 | 不配则图片消息不触发识图 |
| Tavily API Key | 主人外部检索工具 | `TAVILY_API_KEY`（默认空，且总开关默认关） | 不配则外部检索不可用，其余功能正常 |

所有 `ENABLE_*` 类开关默认值都是关闭或最保守状态，这正是设计意图：最小安装 = 复制 `.env.example` + 填 DeepSeek Key + 启动。

## 三、最小启动步骤

1. 复制项目到本地（克隆或下载 ZIP 均可）。
2. 复制 `.env.example` 为 `.env`，至少填写 `OPENAI_API_KEY`（DeepSeek Key）、`BOT_OWNER_QQ`。
3. 复制 `prompts/persona-cards/public/default.example.md` 到 `prompts/persona-cards/private/`，改写为自己的角色卡。
4. 安装 Python 依赖，启动主程序：

   ```powershell
   python bot.py
   ```

5. 需要 QQ 接入时，按 `scripts/install-napcat.ps1` 的说明安装 NapCat（安装包需自行下载到 `tools/NapCatQQ/`，该目录不会进 Git）。
6. 想用 Web 管理面板时，再执行 `cd web/owner-console && npm install && npm run dev`，并按 `docs/web-owner-console-v0-runbook.md` 启动后端。
7. 想开可选功能（RAG / TTS / 群聊 / 视觉），再按 `.env.example` 中的注释逐项打开开关并安装对应组件。

各版本的详细设计见 `docs/` 下的专题文档；运行问题优先查 `docs/web-owner-console-v0-runbook.md` 第 9 节和 `docs/version-runlog.md`。
