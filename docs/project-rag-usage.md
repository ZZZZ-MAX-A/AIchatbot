# 项目 RAG 使用手册

本文说明 AIchatbot 项目层 RAG 的日常使用方式，重点面向本地开发、Codex 新窗口恢复上下文、后续 MainAgentGraph 只读上下文工具接入。

当前项目里 RAG 分为几层：

```text
MemoryRAG
  QQ 侧语义记忆检索。
  用于长期事实记忆、长期偏好记忆、正式会话摘要。
  可以注入 QQ 普通聊天上下文。

ProjectDocRAG
  QQ 外项目文档检索。
  用于 README、docs、公开 prompt 等项目资料。
  不注册 QQ 命令，不进入 QQ 普通聊天。

CombinedRAG
  QQ 外开发侧合并检索。
  同时查询 ProjectDocRAG 和 MemoryRAG，并保持来源分区。

DevContextGraph
  QQ 外开发侧上下文恢复图节点。
  内部调用 CombinedRAG，用于 Codex / 后续 MainAgentGraph 恢复项目上下文。

MainAgentGraph
  QQ /agent 只读主 Agent 入口。
  当前只允许调用 dev_context 只读工具。
  可在 MAIN_AGENT_USE_LLM=true 时使用真实 MainAgent LLM 生成 ActionRequest。
  不执行 shell，不写文件，不发 QQ 消息。
```

## 最推荐入口

平时恢复项目上下文，优先使用：

```powershell
cd D:\AIchatbot

.\scripts\rebuild-rag-index.ps1 -QueryDevContext "你要恢复或查询的项目问题"
```

`-QueryDevContext` 会走 DevContextGraph：

```text
VALIDATE_CONTEXT_REQUEST
RETRIEVE_COMBINED_CONTEXT
RENDER_CONTEXT_ARTIFACT
```

它的输出会包含：

```text
DevContextGraph 开发侧上下文恢复：
查询：...
项目文档命中：...
记忆命中：...

CombinedRAG 开发侧召回：
  项目文档召回
  记忆召回
```

这比直接查 ProjectDocRAG 更适合“恢复开发上下文”，因为它既能看项目文档，也能看已经进入 MemoryRAG 的长期记忆和正式摘要。

## 三个查询入口的区别

如果只做项目 RAG 查询，主要使用下面三个入口。

### 只查项目文档

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryProjectDocs "NapCat 怎么接 NoneBot"
```

适合查询：

```text
项目怎么启动
NapCat / NoneBot 怎么接
某个设计文档里怎么规划
版本运行日志记录了什么
RAG 边界在文档里怎么写
TTS / Vision / MemoryGraph 怎么排查
```

只会返回项目文档：

```text
README.md
docs/**/*.md
prompts/base/**/*.json
prompts/persona-cards/public/**/*.md
```

### 查项目文档和记忆

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryCombined "MemoryRAG 当前做到哪了"
```

适合查询：

```text
项目文档 + 长期记忆一起看
想确认文档结论和记忆结论是否一致
想看某个主题是否既在版本运行日志里出现过，也在长期记忆里出现过
```

输出会保持分区：

```text
项目文档召回：
  来自 project_docs / project_doc

记忆召回：
  来自 semantic_memory / manual_fact / manual_preference / session_summary
```

### 恢复开发上下文

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "当前项目做到哪一步，下一步做什么"
```

这是推荐入口。

适合查询：

```text
新开 Codex 窗口时恢复上下文
继续开发前确认当前进度
询问下一步最稳妥的开发方向
恢复某个模块的设计边界
给后续 MainAgentGraph 提供只读上下文材料
```

## MainAgentGraph 只读入口

当前 MainAgentGraph 还不是完整自动 Agent。第一版只接入了一个只读工具：

```text
dev_context
```

并且已经加了受控 ActionRequest schema。也就是说，它目前做的事情是：

```text
MainAgentGraph
  -> 验证主人/私聊/查询文本
  -> 构建只读上下文模式
  -> CALL_MAIN_AGENT 生成 action=tool_request, tool_name=dev_context 的 ActionRequest
  -> 校验 ActionRequest
  -> 通过 ToolPolicyCheck
  -> 调用 DevContextGraph
  -> 渲染结果
```

当前允许的 action：

```text
final_answer
tool_request
ask_owner
stop
```

当前允许的 tool：

```text
dev_context
```

使用方式：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryMainAgent "项目 RAG 使用手册怎么让新 Codex 恢复上下文" -TopK 2 -MaxContextChars 1400
```

输出会类似：

```text
MainAgentGraph 只读工具执行结果：
工具：dev_context
策略：allow

DevContextGraph 开发侧上下文恢复：
...
```

当前它主要用于验证后续 MainAgentGraph 的工具调用链路，日常恢复上下文仍优先使用 `-QueryDevContext`。

边界：

```text
不执行 shell。
不写文件。
不写数据库。
不发送 QQ 消息。
不绕过 ToolPolicyCheck。
只调用 dev_context 只读工具。
```

## 新开 Codex 窗口怎么恢复上下文

新开的 Codex 窗口不会自动知道旧窗口的对话。需要让它运行 DevContextGraph 查询，或者你先运行查询再把结果贴给它。

### 推荐方式：让新 Codex 自己运行

新窗口里可以直接发：

```text
我们继续 D:\AIchatbot 项目。请先不要直接改代码，先恢复项目上下文。

请运行：
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "继续 AIchatbot 当前开发，恢复 RAG、MemoryRAG、ProjectDocRAG、CombinedRAG、DevContextGraph、MainAgentGraph 下一步计划和边界" -TopK 5 -MaxContextChars 2400

然后请总结：
1. 当前 RAG 系统各层状态
2. QQ 侧 MemoryRAG 和 QQ 外 ProjectDocRAG 的边界
3. 最近完成的 CombinedRAG / DevContextGraph 内容
4. 下一步最稳妥的开发任务
5. 开始前需要检查的文件

注意：
- ProjectDocRAG 只用于 QQ 外开发侧。
- 不要新增 QQ 侧项目文档检索命令。
- 不要把 ProjectDocRAG 注入普通聊天。
- MemoryRAG 才是 QQ 普通聊天可用的语义记忆层。
```

上面这段只是示范。后续如果开发方向变了，查询句可以换掉。

比如之后要继续 TTS：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "继续 AIchatbot TTS 方向开发，恢复 TTS 服务、语音输出、错误排查和下一步计划" -TopK 5 -MaxContextChars 2400
```

如果要继续 MainAgentGraph：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "继续 AIchatbot MainAgentGraph 开发，恢复 RootGraph、DevContextGraph、只读工具和权限边界" -TopK 5 -MaxContextChars 2400
```

如果要继续 MemoryRAG：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "继续 AIchatbot MemoryRAG 开发，恢复 QQ 侧语义记忆注入、索引、状态命令和测试结论" -TopK 5 -MaxContextChars 2400
```

### 备用方式：你先运行，再贴结果

你也可以先在 PowerShell 运行：

```powershell
cd D:\AIchatbot

.\scripts\rebuild-rag-index.ps1 -QueryDevContext "继续 AIchatbot 当前开发，恢复最新项目上下文" -TopK 5 -MaxContextChars 2400
```

然后把输出贴给新 Codex，并补一句：

```text
这是当前项目的 DevContextGraph 恢复上下文。请基于它继续开发，先总结当前状态和下一步，再动代码。
```

这种方式适合新 Codex 暂时没有脚本权限，或者你想控制它看到的上下文内容。

## 提示词怎么写

提示词不需要固定。建议包含四个要素：

```text
1. 项目名或模块名
2. 当前要继续的方向
3. 需要恢复的关键对象
4. 希望输出的内容范围
```

模板：

```text
继续 AIchatbot 的【方向】开发，恢复【关键模块/历史结论/边界/下一步计划】上下文。
```

示例：

```text
继续 AIchatbot 当前开发，恢复 RAG、MemoryRAG、ProjectDocRAG、CombinedRAG、DevContextGraph、MainAgentGraph 下一步计划和边界
```

```text
继续 AIchatbot 语音输出开发，恢复 TTS 服务、语音模式、错误日志和下一步排查计划
```

```text
继续 AIchatbot 权限系统开发，恢复 owner、private whitelist、group whitelist、MainAgent 工具权限边界
```

```text
继续 AIchatbot 文档整理，恢复版本运行日志、架构文档、RAG 使用手册和需要同步的 README 内容
```

## 常用参数

### TopK

控制每个分区最多召回多少条。

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "当前项目状态" -TopK 5
```

常用范围：

```text
2-3：快速看重点
5：默认推荐
8 以上：上下文很散时再用
```

### MinScore

控制相似度阈值。越高越严格，越低越宽松。

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "比较模糊的问题" -MinScore 0.35
```

建议：

```text
0.50 左右：默认项目文档检索
0.55 左右：默认记忆检索
0.30-0.40：查询很模糊时临时放宽
0.60 以上：召回太泛时收紧
```

### MaxContextChars

控制返回上下文的字数上限。

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "MainAgentGraph 下一步怎么做" -MaxContextChars 2200
```

建议：

```text
1200：短摘要
2200-2400：新 Codex 窗口恢复上下文推荐
4000 以上：需要读很多历史时临时使用
```

## 什么时候需要重建索引

查询不需要每次重建。

只有这些内容变了，才需要重建 ProjectDocRAG：

```text
README.md
docs/**/*.md
prompts/base/**/*.json
prompts/persona-cards/public/**/*.md
```

重建命令：

```powershell
cd D:\AIchatbot

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
```

如果刚写了版本运行日志或使用手册，建议马上重建：

```powershell
.\scripts\rebuild-rag-index.ps1 -ProjectDocs
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "刚刚更新的项目 RAG 使用手册是什么" -TopK 3 -MaxContextChars 1800
```

## 当前索引范围和排除范围

ProjectDocRAG 当前会索引：

```text
README.md
docs/**/*.md
prompts/base/**/*.json
prompts/persona-cards/public/**/*.md
```

ProjectDocRAG 当前明确排除：

```text
.git
.venv
data
docs-archive
logs
prompts/persona-cards/private
temp_audio
tools
tts-validation
voice-samples
__pycache__
.env*
*.db
*.sqlite
*.sqlite3
*.log
```

这意味着：

```text
不会索引 .env。
不会索引数据库。
不会索引日志。
不会索引私有角色卡。
不会索引工具目录。
```

## 必须保持的边界

当前边界非常重要：

```text
QQ 侧只做 MemoryRAG。
ProjectDocRAG 不注册 QQ 命令。
ProjectDocRAG 不进入 QQ 普通聊天上下文。
CombinedRAG 不进入 QQ 普通聊天上下文。
DevContextGraph 不进入 QQ 普通聊天上下文。
```

可以进入 QQ 普通聊天上下文的是：

```text
MemoryRAG 召回的长期事实记忆
MemoryRAG 召回的长期偏好记忆
MemoryRAG 召回的正式会话摘要
```

不能进入 QQ 普通聊天上下文的是：

```text
ProjectDocRAG 项目文档
CombinedRAG 合并结果
DevContextGraph 开发侧上下文
```

## 常见问题

### 查询“当前状态和下一步”为什么可能召回旧里程碑

当前 ProjectDocRAG 使用纯 cosine similarity 排序，再按 `top_k` 和 `max_context_chars` 截断。`docs/version-runlog.md` 包含大量历史章节，并反复出现“当前状态、下一步、Owner Console、边界、测试”等词，因此可能由 P2.34/P2.39 等旧片段占据前几名。

这不代表索引没有重建。可以用明确的里程碑关键词验证最新文档是否已进入索引：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "P2.44 研发上下文报告 当前状态 下一步 安全边界" -TopK 3 -MaxContextChars 1400
```

不要把 `top_k` 或上下文上限无限增大，也不要仅按整个文件的修改时间判断章节新旧。P2.45 已完成固定当前状态锚点、单来源去重和分区预算设计；P2.45a 已加入快照和固定锚点读取基础，但尚未接入 DevContextGraph / QQ 的保证锚点路径。快照可能被普通语义检索机会性召回，检索算法仍未改变。见 `docs/development-context-current-state-retrieval-design.md`。

### 新 Codex 会自动使用 RAG 吗

不会。

新 Codex 窗口需要显式运行：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "..."
```

或者你把这条命令的输出贴给它。

### 查询结果没有记忆召回怎么办

可能是 query 更像项目文档，不像长期记忆。可以临时放宽阈值：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "你的问题" -MinScore 0.35 -TopK 5
```

也可以换更贴近记忆内容的问法。

### 查询结果太多怎么办

收紧参数：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "你的问题" -TopK 3 -MinScore 0.60 -MaxContextChars 1200
```

### 查询结果太少怎么办

放宽参数：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "你的问题" -TopK 6 -MinScore 0.35 -MaxContextChars 3000
```

### 重建失败怎么办

优先检查：

```text
1. Ollama 是否启动。
2. bge-m3 是否可用。
3. data/chatbot.db 是否可写。
4. 是否有多个 bot.py 进程同时运行。
5. 是否需要在沙箱外运行脚本。
```

如果看到 SQLite / WAL 打开失败，通常先检查是否有重复 bot 进程或数据库写入权限问题。

## 推荐日常流程

### 新开 Codex 窗口

```text
1. 告诉 Codex 仓库在 D:\AIchatbot。
2. 让它运行 -QueryDevContext。
3. 让它根据输出总结当前状态、边界和下一步。
4. 再开始改代码。
```

如果你想验证 MainAgentGraph 只读工具链，也可以让新 Codex 运行：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryMainAgent "继续 AIchatbot 当前开发，恢复最新项目上下文" -TopK 3 -MaxContextChars 1800
```

但日常恢复仍建议先用 `-QueryDevContext`，它更直接。

### 写完重要文档或版本运行日志

```powershell
.\scripts\rebuild-rag-index.ps1 -ProjectDocs
```

### 开始新开发方向

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "继续 AIchatbot 某个方向开发，恢复相关设计、当前状态、边界和下一步计划" -TopK 5 -MaxContextChars 2400
```

### 只想查项目文档

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryProjectDocs "查询内容"
```

### 想同时查文档和记忆

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryCombined "查询内容"
```

## 一句话总结

日常最推荐记住这一条：

```powershell
.\scripts\rebuild-rag-index.ps1 -QueryDevContext "你要继续的开发方向和需要恢复的上下文" -TopK 5 -MaxContextChars 2400
```

它是当前项目层 RAG 最适合给 Codex / MainAgentGraph 恢复上下文的入口。
