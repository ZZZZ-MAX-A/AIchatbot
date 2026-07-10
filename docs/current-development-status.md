# AIchatbot 当前开发状态

快照版本：P2.46c

当前阶段：P2.46c 视觉区详情已完成本地实现和回归，尚未进行主人 QQ live。`system_diagnostics_report` 现在开放 `overview` 与 `vision` 两个严格 scope：`/agent 执行系统诊断任务` 返回六区短概览，`/agent 执行系统诊断任务：视觉` 仅在主人再次显式选择后返回视觉状态链和第一定位层级。

最近完成事项：新增独立 `VisionDiagnosticsReportPayload`、1800 字符视觉详情、配置/服务/模型/调用/质量/观测固定层级和首故障短路；概览与视觉详情共用视觉证据采集器。视觉详情只读取功能开关、loopback Ollama `/api/tags` 和最近安全计数，不执行真实视觉推理或测试图片；`vision_invocation`、`vision_inference` 只作为未注册建议，不创建下一级任务。聚焦回归 166 tests、全量回归 375 tests 均通过。

当前未完成事项：P2.46d Bot 重启和主人 QQ live 尚未执行，因此不能声称当前运行进程已经加载 P2.46c，也没有 live 视觉任务编号和任务详情证据。核心、聊天、MainAgent、记忆与RAG、语音和 Owner Console 区域详情仍未注册；`vision_invocation`、`vision_inference` 深度范围同样未注册。

明确延后事项：自动周期诊断、自动告警、自动下钻、真实视觉推理、embedding/RAG 主动探针、外部聊天连通性探针和诊断后自动修复均未批准；P2.40b、登录鉴权和 Web 审批操作继续延后。Agent 联网仍应在系统诊断概览和本地区域详情稳定后单独设计。

当前安全边界：MainAgent 只能通过显式 /agent 入口触发；普通聊天不能触发 MainAgent 或正式工作任务；ProjectDocRAG 正文仍只进入显式 /agent dev_context；不开放 shell、Git 工具、任意文件读写、未注册数据库写入、多步写自动化、自动诊断修复或额外 QQ 发送；Owner Console 保持只读 GET；/docs、/redoc、/openapi.json 继续关闭。

推荐下一步：进入 P2.46d，主人重启 Bot 后依次执行 `/agent 执行系统诊断任务` 与 `/agent 执行系统诊断任务：视觉`。验收短概览、显式下钻、首故障短路和安全任务摘要，并确认没有真实视觉推理、自动子任务、外部请求、修复动作或额外 QQ 发送。

证据限制：本快照记录 P2.46c 本地代码与测试状态，不代表实时 Git、未提交工作区、当前 Bot 进程、QQ、Owner Console 或其他本地/外部服务状态。运行中的 Bot 需要重启才能加载 Python 变更；P2.45 的任务 #28 仍是最近一次正式主人 QQ live 证据。
