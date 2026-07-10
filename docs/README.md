# AIchatbot 文档导航与命名规范

本文是 `docs/` 的人工导航和新文档命名约定。它解释版本文档与领域文档为何采用不同文件名，并为后续新增文档建立统一规则。本次不批量重命名现有文件：已有路径已经进入 Git 历史、交叉链接和 ProjectDocRAG `source_id`，应优先保持兼容。

## 1. 阅读入口与证据顺序

| 目的 | 首选文档 | 说明 |
|---|---|---|
| 查看当前阶段 | [current-development-status.md](current-development-status.md) | 当前完成项、延后项、安全边界和建议；不代表实时 Git 或进程状态 |
| 查看实际完成记录 | [version-runlog.md](version-runlog.md) | 实现、测试、live 验收、补丁和经验 |
| 启动和维护 Bot | [runbook.md](runbook.md) | 环境、启动、诊断、维护和常见故障 |
| 使用或维护 RAG | [project-rag-usage.md](project-rag-usage.md) | MemoryRAG、ProjectDocRAG、DevContextGraph 和索引维护 |
| 了解整体架构 | [architecture.md](architecture.md) | 基础架构草案 |
| 了解未来方向 | [future-runtime-architecture.md](future-runtime-architecture.md) | 未来运行时方向，不等于已批准计划 |
| 运行 Web Owner Console | [web-owner-console-v0-runbook.md](web-owner-console-v0-runbook.md) | 当前只读控制台的构建、启动、停止和排障 |
| 阅读对外文章 | [juejin/](juejin/) | 按文章序号排列的稀土掘金草稿 |

当前状态发生冲突时，人工判断顺序为：

```text
当前状态快照
  -> 版本运行日志中的较新完成/live 记录
  -> 对应领域或版本设计文档
  -> runbook 中的当前操作说明
  -> 历史任务、重启上下文和文章草稿
```

该顺序是阅读约定。普通 ProjectDocRAG 仍按语义相似度检索；只有正式主人研发上下文报告对 `current-development-status.md` 使用代码固定的当前状态锚点。

## 2. 命名规则

早期文档围绕较大的产品版本组织，使用 `vX.Y-<主题>.md`，例如 `v1.3-langgraph-agent-runtime.md` 和 `v1.4-memory-rag.md`。后续 Owner Console、MainAgent 开发拆成很多 P2 小步，同一份设计会跨多个任务持续更新，因此改用 `<领域>-<能力>-<文档类型>.md`，例如 `main-agent-first-readonly-work-task-design.md`。前者表达版本级总体目标和共同边界，后者表达长期存在的专题；差异不是运行时或构建系统要求，而是文档组织方式随项目规模变化后的结果。

新文件统一使用小写英文、kebab-case、`.md` 后缀，并将领域放在前面、具体能力居中、文档类型放在末尾。P2 任务编号记录在 `version-runlog.md` 和正文中，不默认写入长期文件名，避免文件因阶段推进而反复改名。

推荐形式：

```text
vX.Y-<主题>.md                    版本总体设计
<领域>-<能力>-design.md           长期设计与决策
<领域>-<对象>-audit.md            安全或契约审计
<领域>-<场景>-runbook.md          操作与排障
<领域>-<主题>-usage.md            使用说明
vX.Y-<主题>-release.md            发布收口
<领域>-<主题>-draft.md            明确未定稿的预研
restart-context-YYYY-MM-DD.md     特定日期的历史恢复上下文
juejin/NN-<主题>.md               对外文章草稿
```

推荐领域前缀包括 `main-agent-`、`owner-console-`、`memory-rag-`、`project-rag-`、`rootgraph-`、`chat-`、`vision-` 和 `voice-`。Owner Console 新文档统一使用 `owner-console-`；现有 `web-owner-console-*` 保留原路径，标题仍可使用完整产品名 “Web Owner Console”。不要用 `final`、`new`、`latest` 或连续追加 `v2` 表达状态，完成状态应写入正文和版本运行日志。

避免以下形式：

```text
NewDesign.md
P2.46-plan.md
web_doc_final_v2.md
临时方案.md
owner-console-new.md
```

`current-development-status.md` 是唯一权威当前状态快照，不按日期复制多个 `current-*` 文件。`restart-context-*` 必须在正文中明确历史属性，不能覆盖当前快照。`juejin/` 文章用于对外叙事，不作为当前实现状态的首要证据。

## 3. 路径稳定性与 RAG 约束

ProjectDocRAG 使用相对路径作为 `source_id`。重命名 `docs/web-owner-console-read-model-design.md` 之类的普通文档后，索引会把新路径视为新 source；重建时旧 source 被软删除，新 source 重新建立文档和向量。因此文件名调整不是纯展示修改。

`docs/current-development-status.md` 还由代码固定注册：

```text
CURRENT_DEVELOPMENT_STATUS_SOURCE_ID=docs/current-development-status.md
```

禁止单独重命名该文件。若未来确需迁移，必须同时修改固定 source ID、全部交叉链接和测试，重建 ProjectDocRAG，验证正式报告仍加载锚点，并完成主人 live 验收。

普通文档也只允许通过一次受控迁移统一改名：

```text
1. 列出旧路径到新路径的完整映射。
2. 使用 Git rename 保留可读历史。
3. 更新 README、设计、runbook、文章和源码测试中的链接。
4. 检查所有 Markdown 链接。
5. 重建 ProjectDocRAG。
6. 确认旧 source 已软删除、新 source 已建立。
7. 记录迁移结果和兼容影响。
```

当前决定是建立规则和索引但不批量改名、不修改固定状态路径、不为旧路径创建内容重复的镜像文档。未来若确实需要统一 `web-owner-console-*`，先单独设计迁移映射和验收方案。

## 4. 当前文档分类索引

**状态与历史记录**

- [current-development-status.md](current-development-status.md)：当前有效状态。
- [version-runlog.md](version-runlog.md)：实现、验证和 live 流水。
- [current-stage-tasks.md](current-stage-tasks.md)：早期记忆系统任务拆分，历史参考。
- [restart-context-2026-06-28.md](restart-context-2026-06-28.md)：特定日期恢复上下文，历史参考。

**运行、部署与项目维护**

- [runbook.md](runbook.md)、[project-rag-usage.md](project-rag-usage.md)
- [napcatqq-setup.md](napcatqq-setup.md)、[push-to-github.md](push-to-github.md)
- [web-owner-console-v0-runbook.md](web-owner-console-v0-runbook.md)
- [owner-console-fastapi-smoke-runbook.md](owner-console-fastapi-smoke-runbook.md)

**版本与架构设计**

- [architecture.md](architecture.md)、[plan-c-nonebot.md](plan-c-nonebot.md)、[future-runtime-architecture.md](future-runtime-architecture.md)
- [v0.2-access-control.md](v0.2-access-control.md)、[v0.3-sqlite-memory.md](v0.3-sqlite-memory.md)、[v0.4-memory-compression.md](v0.4-memory-compression.md)
- [v0.5-long-term-memory.md](v0.5-long-term-memory.md)、[v0.6-persona-expression.md](v0.6-persona-expression.md)、[v0.7-group-auto-reply.md](v0.7-group-auto-reply.md)、[v0.8-owner-notifications.md](v0.8-owner-notifications.md)
- [v0.9-vision-image-context.md](v0.9-vision-image-context.md)、[v1.0-diagnostics-and-operations.md](v1.0-diagnostics-and-operations.md)、[v1.1-voice-output-draft.md](v1.1-voice-output-draft.md)
- [v1.2-memory-runtime.md](v1.2-memory-runtime.md)、[v1.3-langgraph-agent-runtime.md](v1.3-langgraph-agent-runtime.md)、[v1.4-memory-rag.md](v1.4-memory-rag.md)
- [v1.5-rootgraph-runtime.md](v1.5-rootgraph-runtime.md)、[v1.5-rootgraph-chat-release.md](v1.5-rootgraph-chat-release.md)、[v1.6-runtime-service-audit.md](v1.6-runtime-service-audit.md)

**MainAgent 与研发上下文**

- [main-agent-first-readonly-work-task-design.md](main-agent-first-readonly-work-task-design.md)
- [main-agent-useful-development-context-report-design.md](main-agent-useful-development-context-report-design.md)
- [development-context-current-state-retrieval-design.md](development-context-current-state-retrieval-design.md)
- [project-rag-document-state-consistency-audit.md](project-rag-document-state-consistency-audit.md)：稳定设计中的当前/历史状态一致性审计。

**Web Owner Console**

- [web-owner-console-read-model-design.md](web-owner-console-read-model-design.md)、[owner-console-http-surface-audit.md](owner-console-http-surface-audit.md)
- [web-owner-console-read-only-shell-design.md](web-owner-console-read-only-shell-design.md)、[web-owner-console-frontend-stack-design.md](web-owner-console-frontend-stack-design.md)
- [web-owner-console-ui-layout-design.md](web-owner-console-ui-layout-design.md)、[web-owner-console-frontend-readonly-audit.md](web-owner-console-frontend-readonly-audit.md)
- [web-owner-console-frontend-contract-guard.md](web-owner-console-frontend-contract-guard.md)、[web-owner-console-local-deployment-design.md](web-owner-console-local-deployment-design.md)
- [web-owner-console-readonly-auto-refresh-design.md](web-owner-console-readonly-auto-refresh-design.md)、[web-owner-console-v0-runbook.md](web-owner-console-v0-runbook.md)
- [owner-console-fastapi-smoke-runbook.md](owner-console-fastapi-smoke-runbook.md)

**对外文章草稿**

- [juejin/](juejin/)：当前按 `01` 至 `15` 排序。文章可以解释设计取舍，但不能替代当前状态、运行手册或正式设计。

## 5. 新增文档检查清单

新增或拆分文档前检查：

```text
是否已有同一职责的文档可以更新
这是版本级设计还是长期领域文档
领域前缀和文档类型后缀是否明确
是否误把 P2 任务号写进长期文件名
是否在本导航和相关领域文档中增加入口
是否包含当前边界、非目标和验收方式
是否误写入密钥、环境值、私人路径、用户标识或日志正文
是否需要重建 ProjectDocRAG
```

仅修改正文且文档属于 ProjectDocRAG 索引范围时，也应在稳定结论完成后运行：

```powershell
.\scripts\rebuild-rag-index.ps1 -ProjectDocs
```

这套规则允许后续文件名逐步一致，同时避免为了目录外观破坏现有链接、RAG source identity 和历史可追溯性。
