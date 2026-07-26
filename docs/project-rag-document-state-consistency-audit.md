# ProjectDocRAG 文档状态一致性审计

本文记录稳定设计文档中的“当前状态、尚未实现、下一步”措辞审计。目标是降低普通 ProjectDocRAG / DevContextGraph 把历史阶段描述成当前事实的概率，同时保留版本设计和实施过程的可追溯性。

状态：第一轮与 2026-07-24 第二轮审计均已完成；第二轮将权威快照、版本运行日志、新增设计、命名规范和 Owner Console P2.49 runbook 纳入范围。

本轮只更新文档，不重命名文件、不修改运行时代码、不改变 RAG 排序算法、不开放任何新入口或权限。

## 1. 审计原则

文档中的状态陈述分为三类：

```text
当前权威状态：
  只由 current-development-status.md 描述当前阶段、未完成项、延后项和建议。

稳定设计的后续完成状态：
  在仍被频繁引用的设计文档开头说明后续已经落地到什么程度，并指向当前 runbook / 审计 / 状态快照。

历史阶段状态：
  保留“P2.xx 当时尚未实现”的事实，但必须带明确阶段或日期，不能以无时间限定的“当前仍未实现”出现。
```

发生冲突时，人工阅读优先级遵守 `docs/README.md`：当前状态快照优先，其次是较新的版本运行日志，再到稳定设计、runbook 和历史材料。正式主人研发上下文报告继续由代码固定加载当前状态锚点；本审计主要改善普通语义检索和人工阅读。

## 2. 第一轮范围与排除项

第一轮纳入当时仍作为设计或操作入口的文档：

```text
main-agent-first-readonly-work-task-design.md
main-agent-useful-development-context-report-design.md
web-owner-console-read-model-design.md
web-owner-console-read-only-shell-design.md
web-owner-console-frontend-stack-design.md
web-owner-console-ui-layout-design.md
owner-console-fastapi-smoke-runbook.md
v1.6-runtime-service-audit.md
```

第一轮明确排除：

```text
version-runlog.md：按当时事实记录实现流水，不回写成今天的状态。
current-stage-tasks.md：正文已声明为早期阶段历史参考。
restart-context-*.md：按日期保存的恢复上下文。
juejin/*.md：对外文章叙事，不作为当前状态首要证据。
v0.x / v1.x 版本正文中的版本范围结论：只要明确属于该版本，不因后续实现而重写。
future-runtime-architecture.md：正文已声明为讨论沉淀稿和长期方向，不代表批准计划。
```

这些排除项仍可被普通 RAG 召回，因此回答当前状态时必须结合标题、版本、日期和当前状态快照，不能把单个历史片段直接升级为当前事实。

## 3. 发现与修正

| 文档 | 原风险 | 本轮处理 |
|---|---|---|
| MainAgent 首个只读工作任务设计 | P2.45 路线仍写“整体尚未完成”、P2.45a/b 尚未接生产 | 补 P2.44/P2.45 后续完成状态；将 a/b 的未接线限定为当时阶段；补 c/d 完成记录 |
| MainAgent 有用研发报告设计 | P2.45b 仍写尚未接生产检索 | 明确 P2.45a-d 已完成设计、接线、索引和主人 live；旧结果只作为 P2.44 问题证据 |
| Owner Console read model 设计 | P2.6 “当前阶段不接 HTTP/前端”可能被当作今天状态 | 改为 P2.6 当时边界；补 HTTP、真实前端、静态模式、只读任务和当前延后项 |
| Owner Console read-only shell 设计 | P2.28 “仍不创建前端工程”已过期 | 改为当时边界；补 P2.31-P2.39 完成状态；把旧路线标题标为历史 |
| 前端 stack / UI 设计 | 开头使用无时间限定的“当前阶段只做设计” | 改为 P2.29 / P2.30 当时设计边界；保留后续完成清单 |
| FastAPI smoke runbook | 仍写只返回 JSON、不渲染页面 | 区分默认纯 API smoke 与显式静态模式；API 始终保持 JSON-only |
| v1.6 Runtime service 审计 | 末尾仍写“当前建议优先 P2.6” | 补 Web Owner Console 路线已完成；将该建议标为 2026-07-07 审计时的历史选择 |

本轮没有把所有“尚未”替换为“已完成”。仍未批准的 P2.40b 业务页面轮询、登录鉴权、Web 写操作、公网部署、审批按钮和 Diagnostics runtime 解耦继续保留为未完成或可选方向。

## 4. 防止误改历史

状态一致性不等于把旧文档改写成新文档。以下写法应保留：

```text
P2.28 当时不创建真实前端。
P2.45a 当时尚未接生产 Agent。
2026-07-07 审计时建议先进入 P2.6。
P2.44 live 曾只召回 P2.34/P2.39b 历史片段。
```

不应继续使用：

```text
当前仍不创建前端。
P2.45 整体尚未完成。
下一步优先进入已经完成的 P2.6。
当前 FastAPI 永远不服务静态页面。
```

当某份设计后来已经落地，推荐在开头增加简短“当前完成状态”，正文仍按原设计阶段叙述；只有明确错误的无时间限定状态才需要改写。

## 5. 验收与后续维护

本轮验收要求：

```text
所有新增和修改的 Markdown 链接存在。
文档导航覆盖新增审计文档。
ProjectDocRAG 重建无错误。
普通项目文档查询能命中本审计或更新后的完成状态，而不是只返回旧“尚未接入”段落。
正式 Owner Console 当前状态报告继续加载固定锚点，warning/error 为 0。
不修改 current-development-status.md 固定路径。
不修改 version-runlog 历史流水。
不新增 QQ、Web、数据库或文件写运行时能力。
```

以后每个改变“当前阶段、未完成事项、延后事项、推荐下一步”的里程碑，应优先更新 `current-development-status.md`。如果稳定设计中的后续路线已经落地，再在同一文档增加带阶段限定的完成状态；不要依赖后续 RAG 或 LLM 自行猜测哪段更新。

## 6. 2026-07-24 第二轮审计

### 6.1 触发原因

一次“继续下一阶段”被错误解释为批准旧 backlog 中的 `system_diagnostics_report/core`，说明第一轮只修正文档局部措辞仍不够。根因不是单个技术条目存在，而是权威快照、历史 runlog 和领域设计没有把“事实存在、候选任务、优先级、主人批准”分开。

第二轮建立以下硬规则：

```text
事实仍存在 != 应立即实现
未完成事项 != 当前下一阶段
候选范围 != 主人批准范围
历史“下一步” != 当前路线图
只有 owner_approved 可以自动开始
```

### 6.2 覆盖与结果

第二轮重点核对：

```text
current-development-status.md
version-runlog.md
docs/README.md
main-agent-external-read-security-design.md
main-agent-command-capability-audit.md
main-agent-system-diagnostics-report-design.md
owner-console-manual-diagnostics-design.md
web-owner-console-v0-runbook.md
可靠性、表情、文档产物和 P2.48/P2.49 新增设计
```

主要问题与处理：

| 问题 | 处理 |
|---|---|
| 权威快照约 50 KB、混入过期监听/等待/live/工作区状态 | 重写为九段固定合同，约 9 KB、150 行，加入批准状态、优先级和唯一下一步 |
| runlog 中大量历史“当前/下一步/等待”可被误作路线图 | 在文件顶部增加历史阅读规则，明确不构成当前授权 |
| external-read 文档开头仍称未开放联网，但后文已记录 Tavily live | 把早期章节标为历史设计起点，并在开头写明当前稳定事实 |
| `/agent` 能力审计基线停留在 `a9e7c4b`，external-read 行仍称未开放 | 更新到 2026-07-24 / `0055dcc` 已提交基线与真实 live 结论 |
| Owner Console runbook 仍称全站只能 GET、禁止主动探测 | 区分业务 GET-only 与三个逐项授权的固定 POST，补齐启动、二次确认、全局锁和证据核对步骤 |
| README 漏列六份新文档，文章仍称只有 01–16 | 补齐导航；记录已跟踪 19/20 与主人保留的未跟踪 17/18 |
| 未获方向批准的 core 实验被写成主人批准 | 先在快照、设计和 runlog 中标明未批准、未加载、未 live；主人随后批准完全撤销正式能力，只保留 `connect_read_only()` 安全修正，且不得从历史记录恢复 |

### 6.3 命名规范复核

命名规范自提交 `f986a27 Add documentation navigation and naming rules` 建立后，Git 新增的 13 份 Markdown 文档机械检查结果为：

```text
13/13 小写英文
13/13 kebab-case
13/13 使用 .md
13/13 不含 final/new/latest/v2
13/13 长期文件名不含 P2 编号
3/3 新 Owner Console 文档使用 owner-console- 前缀
3/3 新掘金文章使用 NN-topic.md
```

主人保留的未跟踪文章 17、18 也符合 `NN-topic.md`。`reliability-failure-taxonomy-and-inspection.md` 的 `-inspection.md` 不属于推荐后缀，是唯一软偏差；由于路径已进入 Git、交叉链接和 ProjectDocRAG `source_id`，本轮将其登记为兼容例外，不自动重命名。

### 6.4 后续维护验收

每次里程碑收口至少检查：

```text
权威快照是否只保留当前批准方向和一个下一步。
新文档是否进入 README 导航。
设计中的“当前/尚未/下一步”是否带阶段或日期。
runbook 是否覆盖已上线的真实操作入口。
主人批准是否与本地实现、回归、加载、live 分开记录。
实时运行态是否带 observed_at。
历史 backlog 是否被误标为 owner_approved。
```

本轮只修改文档，不执行 ProjectDocRAG 重建、RAG 查询、私人记忆查询、模型调用、TTS、视觉、服务启动/重启、QQ 发送、commit 或 push。
