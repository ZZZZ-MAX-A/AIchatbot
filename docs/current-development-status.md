# AIchatbot 当前开发状态

快照版本：P2.45a

当前阶段：P2.44 已完成有用研发上下文报告；P2.45 已完成当前状态锚点与来源多样性设计；P2.45a 已实现固定当前状态快照、ProjectDocRAG 精确锚点读取基础和 anchor/semantic 结果模型分离，但尚未接入 QQ 正式研发任务。

最近完成事项：显式主人私聊研发上下文任务具备 pending、running、done/failed 生命周期和固定六字段详细回复；详细回复与任务持久化摘要保持分离；当前状态锚点只能读取代码注册的本快照 source id，不能由用户或 LLM 指定任意路径。

当前未完成事项：P2.45b 候选扩展、单来源去重和分区预算尚未实现；P2.45c 尚未把锚点接入 development_context_report；P2.45d 索引与主人 live 验收尚未完成。

明确延后事项：P2.40b 未批准，Dashboard、Tasks、Approvals 和详情页继续初次加载加手动刷新；登录鉴权和 Web 审批操作仍需单独设计。

当前安全边界：MainAgent 只能通过显式 /agent 入口触发；普通聊天不能进入 ProjectDocRAG；不开放 shell、Git 工具、任意文件读取、任意文件写入、未注册数据库写入、多步写自动化或额外 QQ 发送；Owner Console 保持只读 GET；/docs、/redoc、/openapi.json 继续关闭。

推荐下一步：实现 P2.45b 的纯候选选择逻辑和单元测试，先不接生产 QQ 路径。

证据限制：本快照描述已写入项目文档的里程碑状态，不代表实时 Git、未提交工作区、进程运行状态或外部服务状态；相关状态仍需通过各自只读诊断确认。
