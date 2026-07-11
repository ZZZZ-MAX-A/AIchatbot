# AIchatbot 当前开发状态

快照版本：P2.46（系统诊断当前扩展）

当前阶段：`system_diagnostics_report` 已开放 `overview`、`vision`、`voice` 和 `memory_rag` 四个严格 scope。主人私聊可以分别执行 `/agent 执行系统诊断任务`、`/agent 执行系统诊断任务：视觉`、`/agent 执行系统诊断任务：语音` 和 `/agent 执行系统诊断任务：记忆与RAG`。P2.46a-c 的设计、概览和视觉详情已经完成；P2.46d 的 Bot 加载与主人 QQ live 已由主人反馈未发现问题。本轮语音与记忆/RAG 扩展不另设新的阶段编号。

最近完成事项：语音详情按功能配置、loopback 地址、服务健康、IndexTTS2 模型加载和安全运行观测执行首故障短路；记忆与RAG详情按配置、存储、索引、运行观测执行首故障短路。两者都只保存状态、定位层级、推荐 scope 和安全计数，不保存 URL、日志、路径、RAG 正文、查询正文或错误原文。`/agent 语音状态怎么样` 已补全服务可达性、health、模型加载、语言、最近候选和“未做端到端验证”的说明；`/agent 查看配置状态` 已改为基础入口、聊天模型、MainAgent、记忆与RAG、视觉、语音和高风险边界分区概览。

路由收口：明确 `/agent 查 <问题>`、`/agent 查询 <问题>`、`/agent search <问题>` 和 `/agent-debug <问题>` 才确定性进入 `dev_context`。没有 Main LLM 且未命中确定性命令的未知表达改为 `ask_owner`，只返回澄清和真实已注册命令，不执行工具、不查询 RAG、不创建 pending intent。Main LLM 的 Action Planner 同样被要求把运行状态/故障与研发上下文分开；对象、范围或运行/研发含义不清时优先 `ask_owner`，不得以 `dev_context` 猜测当前服务、模型、配置、进程、数据库、TTS 或视觉状态。

MainAgent 输出边界：工具与 RAG 结果是只读证据，不是身份设定。MainAgent 不采用召回内容里的角色名，不自称“爱可”或其他聊天角色，不添加括号动作旁白，不声称执行工具未执行的检查。ChatAgent 的角色卡和聊天风格仍只属于普通聊天链路。

本地验证：聚焦回归 148 tests OK；全量回归 405 tests OK；Python compile、AST 和 `git diff --check` 通过。新增交叉合同覆盖视觉 8 种、语音 6 种、记忆与RAG 8 种证据状态，确认同一 evidence 在概览与区域详情中保持相同区域状态；三类详情均保持定位层级、状态链、初步判断、下一范围和未执行边界。当前工作区包含代码、测试及本文档的未提交修改；本地 `main` 相对 `origin/main` 仍 ahead 3，未自动 commit 或 push。

主人 QQ live：正式任务 #33 为系统概览、#34 为视觉详情、#35 为语音详情、#36 为记忆与RAG详情，四条命令均成功完成。主人核对任务详情后确认 `external_request_count=0`、`deep_probe_count=0`、`repair_action_count=0`，其他功能输出正常。#35 准确定位为语音服务层降级：TTS 已开启且地址为本机 loopback，但本地服务不可达；因此按第一故障链没有继续判断 health、IndexTTS2、语言或生成/发送状态。live 同时发现下游“未继续判断”说明不够直观，以及工作任务尾部边界仍只写 overview/vision；代码补充逐项跳过原因并更新四个 scope 边界后，主人通过正式任务 #37 完成 QQ live 复验：服务层降级和首故障短路保持不变，health、IndexTTS2、语言、生成与发送均明确标记为因服务不可达而未继续判断，尾部边界正确列出视觉、语音、记忆与RAG。该验收不等于执行过真实视觉推理、TTS 音频生成、QQ 语音端到端发送、embedding、语义召回或索引重建。

当前保留现象：系统概览曾报告 MemoryRAG 有 2 条活动文档缺少向量。该现象仅作为已发现状态保留，不自动重建 MemoryRAG，不自动创建修复任务，也不擅自升级为下一阶段主任务。

当前未完成事项：核心、聊天、MainAgent 和 Owner Console 区域详情仍未注册；所有真实视觉推理、TTS 生成/发送、embedding/语义召回等深度 scope 仍未注册。下一阶段编号与范围等待后续讨论，不在本文预设。

明确延后事项：自动周期诊断、自动告警、自动下钻、真实视觉推理、真实 TTS 推理和 QQ 发送、embedding/RAG 主动探针、外部聊天连通性探针、服务重启、模型下载、配置修改和诊断后自动修复均未批准；P2.40b、登录鉴权和 Web 审批操作继续延后。

当前安全边界：MainAgent 只能通过显式 `/agent` 入口触发；普通聊天不能触发 MainAgent 或正式工作任务；ProjectDocRAG 正文仍只进入显式 `/agent` dev_context；不开放 shell、Git 工具、任意文件读写、未注册数据库写入、多步写自动化、自动诊断修复或额外 QQ 发送；Owner Console 保持只读 GET；`/docs`、`/redoc`、`/openapi.json` 继续关闭；不提交 `web/owner-console/dist`。

推荐下一步：先保持当前四个 scope 稳定使用，结合后续真实故障样例审计 `ask_owner` 的澄清质量、各区域第一故障层和证据不足输出。是否补充其他区域详情、深度探针或修复审批，应由主人另行确认，不从本轮 live 结果自动推导。

证据限制：本快照记录 2026-07-11 的仓库工作区、本地回归和主人反馈，不代表未来实时 Git、当前进程、QQ、Owner Console 或其他本地/外部服务状态。配置、`/health` 正常和最近安全观测均不能替代端到端功能验证。
