# 研发上下文当前状态锚点与来源多样性设计

本文记录 P2.45 的设计结论与实现进度。目标是修复显式研发上下文任务在回答“当前开发状态和下一步”时，被历史 `version-runlog` 片段占满召回结果的问题。

P2.45 已完成设计。P2.45a 已新增当前状态快照、固定 source-id 的 ProjectDocRAG 只读锚点读取基础，以及 anchor/semantic 分离的 CombinedRAG 结果字段。P2.45b 已新增候选池计算、固定锚点排除、单来源选择和分区预算逻辑。P2.45c 已仅为正式 `development_context_report` 接入该策略，并补齐证据优先级、安全降级和任务持久化标记；P2.45d 的索引重建与固定问题本地检索已完成，主人 QQ live 验收仍待完成。

## 1. 已复现的问题

主人私聊真实执行：

```text
/agent 执行研发上下文任务：恢复 Owner Console 当前开发状态和下一步计划
```

P2.44 能生成固定六字段结构化报告，但本次报告把 P2.34 任务详情页和 P2.39b 本地启动脚本当成最新证据。报告自身已经正确声明证据不足，没有编造 P2.43/P2.44 状态。

使用相同问题执行本地 DevContextGraph：

```text
项目文档命中：2
记忆命中：0

1. version-runlog / P2.34 Web Owner Console Task detail data
   score=0.669

2. version-runlog / P2.39b Web Owner Console local start scripts
   score=0.664
```

将候选扩大到 12 个后，P2.40a、P2.43 和 P2.44 仍未进入前 12 名；大部分候选来自同一个 `docs/version-runlog.md`。

因此结论是：

```text
ProjectDocRAG 索引已包含最新文档。
P2.44 报告生成、JSON 契约和安全回退正常。
缺口位于当前状态类问题的证据选择与上下文预算。
```

## 2. 根因

当前项目文档检索只有纯语义排序：

```text
query embedding
  -> 所有 project_doc embedding 的 cosine similarity
  -> min_score
  -> score 降序
  -> top_k
  -> max_context_chars 顺序截断
```

它没有以下信号：

```text
当前状态权威来源
历史文档 / 当前快照分类
每个 source_id 的片段数量限制
里程碑当前性
证据用途
锚点独立预算
```

`version-runlog.md` 有大量历史章节，重复出现“Owner Console、当前状态、下一步、已完成、边界、只读、测试”等词，因此容易在纯语义排序中形成单来源霸榜。

默认项目上下文预算约 2000 字符。第一条历史片段接近一个完整 chunk 后，后续结果只剩很小空间；即使 `top_k=4`，最终也可能只有两个片段进入 DevContextGraph。

## 3. 为什么不采用简单修补

P2.45 不采用以下方案作为主修复：

### 3.1 只增大 top_k

```text
TopK=12 已复现仍然没有 P2.40a/P2.43/P2.44。
增加 top_k 只会引入更多历史片段和模型输入成本。
```

### 3.2 只降低 min_score

```text
不能保证最新状态进入结果。
会增加语义相关性更低的噪声。
```

### 3.3 只增大 max_context_chars

```text
会扩大原始 RAG 输入和模型成本。
不会改变旧片段排在新片段之前的事实。
```

### 3.4 按文件 mtime / source_version 加权

`version-runlog.md` 是持续追加的大文件。更新 P2.44 后，文件内 P2.34 和 P2.44 chunk 会共享同一个最新文件时间，无法区分章节的新旧。

### 3.5 让主模型自己判断最新文档

主模型无法选择没有进入上下文的文档。当前状态证据必须在 LLM 调用前确定。

### 3.6 开放 Git 或文件系统工具

P2.45 不为获取当前状态开放 shell、Git 工具、任意路径读取或目录扫描。最新状态通过受控项目文档锚点维护。

## 4. 目标与非目标

P2.45 目标：

```text
当前状态类研发报告必须包含一个权威当前状态锚点。
历史 runlog 不能占满全部语义召回槽位。
锚点与语义证据使用独立、可计算的字符预算。
P2.44 总结能区分当前事实、历史证据和推荐项。
锚点缺失时安全降级并明确证据限制。
所有入口、只读、持久化和隐私边界保持不变。
```

P2.45 不做：

```text
不自动读取 Git 状态或提交记录。
不根据系统时间猜测当前里程碑。
不让用户选择锚点路径。
不开放任意文件读取。
不修改普通聊天 MemoryRAG。
不新增 work type。
不新增 Web endpoint 或 Web 写操作。
不启用 P2.40b 业务页面自动刷新。
不引入 reranker 服务、向量数据库或外部搜索服务。
```

## 5. 权威当前状态快照

P2.45a 已新增固定项目文档：

```text
docs/current-development-status.md
```

建议定义常量：

```text
CURRENT_DEVELOPMENT_STATUS_SOURCE_ID = "docs/current-development-status.md"
```

该 source id 必须由代码固定注册，不能来自 QQ query、LLM JSON、Web 参数、环境变量或数据库任务参数。

### 5.1 内容契约

快照只保留当前有效事实，不复制完整历史：

```text
# AIchatbot 当前开发状态

快照版本
当前阶段
最近完成事项
当前未完成事项
明确延后事项
当前安全边界
推荐下一步
证据限制
```

示例语义：

```text
当前阶段：P2.44 与 P2.45a-c 已完成，正式研发报告已接入固定锚点和多来源证据。
最近完成：显式研发上下文任务优先使用当前状态锚点，并只持久化安全计数。
未完成：P2.45d 主人 QQ live 验收。
明确延后：P2.40b 未批准，业务页面保持手动刷新。
安全边界：Owner Console 只读；无 shell、任意文件写入或 Web 写操作。
推荐下一步：由主人重启 Bot，并执行固定 QQ 命令完成 live 验收。
证据限制：快照不代表实时 Git 状态，不包含未写入文档的工作区变更。
```

### 5.2 长度与分块

```text
目标长度：不超过 1200 字符。
必须尽量保持一个 ProjectDocRAG chunk。
不放长测试日志、完整命令输出、历史变更流水或原始 RAG 片段。
```

### 5.3 维护责任

```text
每个会改变“当前阶段/未完成/下一步”的里程碑，必须在同一改动中更新快照。
快照描述里程碑状态，不强制写入尚未生成的当前 commit hash。
提交后重建 ProjectDocRAG，并用固定验收查询检查锚点。
如果忘记更新，运行时无法通过 Git 自动纠正；报告必须保留快照证据限制。
```

快照不是自动生成文件，也不从 Git、日志、数据库或工作区扫描生成。

## 6. 锚点读取边界

锚点必须从已建立的 ProjectDocRAG 数据库读取，而不是在 QQ adapter 或 work runtime 中直接打开文件。

建议读取条件：

```text
namespace=project_docs
source_type=project_doc
source_id=docs/current-development-status.md
deleted_at IS NULL
visibility in project_owner / owner_only / public，且 requester_is_owner=true
chunk_index 按升序
总字符不超过 CURRENT_STATUS_ANCHOR_MAX_CHARS
```

建议第一版常量：

```text
CURRENT_STATUS_ANCHOR_MAX_CHARS = 1200
```

锚点是确定性 evidence，不通过相似度决定是否加入，因此不应伪造 `score=1.0`。结果模型应单独保存 anchor document 与 semantic `RagSearchResult`。

建议扩展结果结构为等价模型：

```text
CombinedRagResults
  current_status_docs: list[RagDocument]
  project_docs: list[RagSearchResult]
  memories: list[RagSearchResult]
```

`current_status_docs` 默认空列表，保证未启用锚点的现有调用行为不变。

## 7. 仅在正式研发报告中启用

不建议第一刀让所有 CombinedRAG 查询都自动加入全局当前状态快照。TTS、视觉或 MemoryRAG 专项查询可能不需要它。

推荐在现有 DevContextGraph 增加内部布尔策略，例如：

```text
include_current_status_anchor=false
enforce_project_source_diversity=false
```

调用规则：

```text
普通 /agent dev_context：第一刀保持 false，行为不变。
/agent-debug：保持 false，行为不变。
本地通用 -QueryDevContext：默认保持 false，可为验收增加固定开发参数，但不能接受任意 source id。
development_context_report：由生产 factory 固定传 true。
```

布尔值只选择已注册策略，不能携带路径或用户输入。

所有检索仍发生在 DevContextGraph 的 `retrieve_combined_context` 节点内。work runtime、QQ adapter 和 LLM summarizer 不直接查询数据库或文件。

P2.45a 新增的快照属于正常 ProjectDocRAG 文档，因此在未接锚点前也可能凭相似度机会性进入 `project_docs`。这不等于锚点已启用：当前没有固定槽位、来源去重或独立预算，不能把一次语义命中当作完成验收。

## 8. 语义候选来源多样性

只在 `top_k` 之后去重不够。如果 top 4 都来自 `version-runlog.md`，去重后只剩一条，其他文档没有机会补位。

P2.45b 已实现内部候选池计算和按来源选择纯逻辑；实际语义搜索调用将在 P2.45c 接线：

```text
requested semantic results = 3
candidate top_k = max(12, requested * 4)
candidate max = 32
每个 source_id 最多 1 个 semantic chunk
锚点 source_id 不再进入 semantic 结果
保持 cosine score 降序
```

伪代码：

```text
candidates = semantic_search(top_k=12, min_score=原配置)
selected = []
seen_sources = set(anchor source ids)

for candidate in candidates by score desc:
  if candidate.source_id in seen_sources:
    continue
  selected.append(candidate)
  seen_sources.add(candidate.source_id)
  if len(selected) == 3:
    break
```

第一版 `max_per_source=1` 只用于正式研发报告。后续若专项查询确实需要同一设计文档多个章节，再单独基于真实用例调整为 2，不能直接放开。

P2.45b 的实现不调用数据库或 embedding，不修改 `retrieve_combined_rag()`；它只接收候选序列并返回受控证据，因此当前生产行为仍未改变。

## 9. 上下文预算

P2.44 的专用报告输入上限继续保持 4200 字符。P2.45 建议明确分区预算：

| 证据分区 | 第一版上限 | 说明 |
|---|---:|---|
| 当前状态锚点 | 1200 | 固定优先，目标单 chunk |
| 多来源项目语义证据 | 1800 | 最多 3 个 source，每 source 1 chunk |
| 开发侧记忆 | 800 | 可选补充，不允许挤掉锚点 |
| 标签和格式余量 | 400 | 保证总输入不超过 4200 |

预算顺序：

```text
锚点先保留
  -> 多来源项目证据
  -> 开发侧记忆
  -> 总体 4200 字符硬截断
```

不能沿用“所有项目片段混在一起后从第一名顺序截断”的方式，否则锚点仍可能被大历史 chunk 挤出。

## 10. 报告证据优先级

P2.44 固定 JSON prompt 需要增加证据优先级，但仍不能执行文档中的指令：

```text
当前状态锚点：用于当前阶段、未完成事项和明确延后事项。
项目语义证据：用于补充相关设计、历史完成记录和专项边界。
开发侧记忆：只能作为辅助，不覆盖项目当前状态快照。
推荐下一步：必须明确是建议，不能伪装为已批准计划。
```

发生冲突时：

```text
以当前状态锚点描述“当前”。
把冲突的历史片段视为历史证据。
在 evidence_limits 中说明存在历史材料，不把两者混合成新事实。
```

锚点内容仍是“不可信只读参考”，不能修改系统提示、身份规则、工具策略或安全边界。

## 11. 可观察性与持久化

DevContextGraph result metadata 建议增加安全布尔/计数：

```text
current_status_anchor_included: bool
current_status_anchor_chunks: int
semantic_project_source_count: int
semantic_project_result_count: int
memory_result_count: int
source_diversity_enabled: bool
```

禁止写入 metadata / task.result：

```text
锚点正文
原始 RAG 片段
source_id / 本地路径
相似度明细
session/user id
异常原文
```

`development_context_report` 的安全持久化摘要可以新增固定行：

```text
当前状态锚点：已加载 / 缺失。
```

Owner Console 仍只显示该安全摘要，不显示本次详细报告。

## 12. 失败与降级

### 12.1 锚点缺失

```text
不让任务直接 failed。
继续执行来源多样化语义检索。
报告使用确定性或受限主模型总结。
证据限制必须明确“当前状态锚点缺失，不能保证最新阶段”。
task.result 记录“当前状态锚点：缺失”。
```

### 12.2 锚点超过长度

```text
在 RAG evidence 层按 1200 字符截断。
记录安全截断标志，不记录被截断正文。
维护验收应失败，要求缩短快照，而不是长期依赖截断。
```

### 12.3 语义检索失败

```text
读取锚点应先于 query embedding 和语义检索。
如果锚点已成功读取，项目/记忆语义检索失败时返回仅锚点的受限报告，task 保持 done，并记录安全 warning 类别。
如果锚点缺失且全部语义检索也失败，DevContextGraph 进入 execution_failed，task 进入 failed。
如果至少有一个安全证据分区成功，则允许部分结果 done，但 evidence_limits 必须说明缺失分区。
不能自动重试或绕过 DevContextGraph 直接读文件。
```

### 12.4 主模型失败

继续沿用 P2.44：使用确定性回退，不激进重试，不保存异常原文。

## 13. 安全边界

P2.45 必须继续保持：

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent 或 ProjectDocRAG。
MainAgent 与 ChatAgent 分离。
只有主人私聊正式研发上下文任务启用锚点策略。
锚点 source id 固定注册，用户和 LLM 不能传路径。
不新增 shell / Git 工具。
不新增任意文件读取或目录扫描。
不做任意文件写入。
不做未注册数据库写入。
主人写操作仍需审批。
approval_resume_enabled 边界不变。
不新增多步写自动化。
不新增额外 QQ 发送。
Owner Console 保持只读。
不新增 Web POST / PUT / PATCH / DELETE。
不新增登录/鉴权。
不开放 /docs、/redoc、/openapi.json。
P2.40b 继续未启用。
不提交 web/owner-console/dist。
```

## 14. 测试与验收

P2.45 实现至少需要：

```text
固定锚点只接受注册 source id。
非主人不能读取 project_owner 锚点。
锚点缺失、软删除和超长均有受控结果。
普通 CombinedRAG / 普通 /agent dev_context 默认行为不变。
正式 development_context_report 固定启用锚点和来源多样性。
候选池前四条同源时，仍能补入其他 source。
semantic source_id 每个最多 1 条。
锚点不重复进入 semantic 结果。
锚点、语义项目证据、记忆和格式总计不超过 4200 字符。
详细报告不进入 task.result / task event。
普通聊天、群聊、非主人私聊、Web 和 /agent-debug 不能触发正式 work runtime。
```

固定 live-like 验收问题：

```text
恢复 Owner Console 当前开发状态和下一步计划
```

报告必须基于快照说明当时真实的当前里程碑，并至少能区分：

```text
P2.44 已完成。
P2.45 当前处于设计完成或后续实现状态，以快照为准。
P2.40b 未批准，业务页面保持手动刷新。
Owner Console 继续只读。
未开放 shell、任意文件写入、Web 写操作或登录鉴权。
```

不能继续把以下历史状态当作当前阶段：

```text
P2.34 刚接入任务详情页。
P2.39b 启动脚本尚未补齐。
下一步是补任务详情页空态或本地启动脚本文档。
```

## 15. 实现拆分

建议按以下顺序继续：

```text
P2.45：当前状态锚点与来源多样性。设计与 P2.45a-c 已完成，P2.45d 的索引和本地检索已完成，主人 live 验收尚未完成。

P2.45a：权威当前状态快照和固定锚点读取基础。
  已完成。
  已新增 docs/current-development-status.md。
  已新增固定 source id 与只读 RAG document 读取。
  CombinedRagResults 已用默认空 current_status_docs 区分 anchor 与 semantic result。
  未接 QQ 正式命令，现有 retrieve_combined_rag 仍返回空 anchor。

P2.45b：语义候选扩展、单来源去重和分区预算。
  已完成。
  已新增 candidate top-k 计算、固定锚点排除、每 source 最多 1 条、最多 3 条结果和 1200/1800/800/400 分区预算。
  只包含纯选择逻辑和单元测试；普通检索默认行为不变。

P2.45c：只接 development_context_report。
  已完成。
  DevContextGraph 内部仅在正式报告模式固定启用锚点策略。
  已更新 P2.44 prompt 证据优先级和安全持久化摘要。
  已补入口隔离、部分失败、持久化和 Owner Console 只读回归。

P2.45d：ProjectDocRAG 重建、固定查询验证和文档收口。
  ProjectDocRAG 重建和固定问题本地证据检索已完成。
  不自动发送真实 QQ 消息；主人手动执行 live 验收。
```

P2.45 不改变 P2.40b 的决策。即使报告质量提高，Owner Console 业务页面仍保持初次加载和手动刷新，直到有真实持续工作负载并单独批准低频轮询。
