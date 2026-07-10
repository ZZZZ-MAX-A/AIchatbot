# MainAgent 有用研发上下文报告设计

本文记录 P2.44 的设计与实现结果。目标是在 P2.43 已形成的主人私聊显式只读任务闭环上，让下列命令真正回答“当前状态和下一步”，而不扩大执行权限：

```text
/agent 执行研发上下文任务：恢复 Owner Console 当前开发状态和下一步计划
```

P2.44 已完成。它没有增加新的 work type、QQ matcher、Web endpoint、写工具或自动化流程。

## 1. P2.43 的实际缺口

P2.43 已能完成：

```text
pending -> running -> done / failed
created -> work_claimed -> work_started -> work_finished / work_failed
DevContextGraph / CombinedRAG 只读检索
主人私聊显式命令与 Owner Console running 只读展示
```

但生产执行器只把以下信息交给 work runtime：

```text
project docs: <count>
memories: <count>
```

因此用户问题即使包含“恢复当前状态和下一步计划”，回复也只有命中计数。原始 RAG 不泄漏，但报告不够有用。

## 2. P2.44 结果契约

P2.44 将结果拆成两个不同安全等级的表面。

### 2.1 本次主人私聊详细回复

详细回复使用固定结构：

```text
当前阶段
已完成事项
未完成事项
当前安全边界
推荐下一步
证据与限制
```

当 `MAIN_AGENT_USE_LLM=true` 且 RAG 有召回时，系统对经过预脱敏和限长的上下文执行一次直接总结。该调用：

```text
不进入 MainAgent ActionRequest planner。
不附带 ToolRegistry。
没有 tool selection。
没有 shell、文件、数据库、Web 或 QQ 工具。
只接受固定六字段 JSON。
每个列表最多 4 项，每项最多 240 字符。
最终详细回复最多 2400 字符。
```

模型关闭、没有召回、调用失败、返回空文本、JSON 非法或字段不匹配时，使用确定性回退报告。回退报告只说明召回数量、相关章节和证据不足，不从原始片段猜测具体进度。

### 2.2 task.result 和 task event 持久化摘要

数据库仍只保存：

```text
研发上下文报告已完成。
项目文档命中：<count>。
开发侧记忆命中：<count>。
详细回复：受限主模型结构化总结 / 确定性回退摘要，仅在本次主人私聊返回。
任务记录未保存原始 RAG 片段、路径、详细回复或异常文本。
```

详细报告不会进入 `agent_tasks.result`，也不会进入 `work_finished.output_summary`。Owner Console 任务详情因此继续只显示受限持久化摘要，而不是本次 QQ 详细回复。

## 3. 输入处理

DevContextGraph 仍是唯一检索边界。P2.44 从 `combined_results` 构造专用总结输入：

```text
最多 4200 字符。
保留项目文档正文和开发侧记忆正文作为只读证据。
项目文档标题只保留 # 后的章节名，不传来源路径。
不传 source_id、session_key、user_id、相似度或 chunk index。
发送给主模型前脱敏邮箱、手机号、证件号、长号码、密钥、Token、URL、本地绝对路径、仓库相对路径和 .env 文件名。
```

系统提示明确把召回内容标记为不可信只读参考，不能执行其中的指令、改变策略或请求工具。

## 4. 输出处理

受限主模型必须返回且只能返回：

```json
{
  "current_stage": "...",
  "completed_items": ["..."],
  "pending_items": ["..."],
  "safety_boundaries": ["..."],
  "recommended_next_steps": ["..."],
  "evidence_limits": ["..."]
}
```

解析器要求字段集合完全匹配，禁止 Markdown fence 和额外字段。解析后的详细回复还会再次执行控制字符清理、密钥/Token/URL/路径脱敏和 2400 字符限长。

模型不得编造提交、日期或已完成工作。RAG 没有提供 Git 状态时，报告必须在“证据与限制”中说明；本任务不会为了补 Git 信息开放 shell。

## 5. 失败语义

```text
DevContextGraph 失败：任务进入 failed，持久化安全错误类别，不保存异常原文。
受限主模型失败：记录到既有本地错误日志，改用确定性回退报告，任务仍可 done。
JSON 契约失败：同主模型失败，使用确定性回退。
没有召回：不调用主模型，直接返回确定性证据不足报告。
```

总结失败不激进重试，也不创建后台任务。

## 6. 执行路径

```text
既有 /agent matcher
  -> ENABLE_MAIN_AGENT
  -> 严格命令解析
  -> PrivateMessageEvent
  -> is_owner(config, event)
  -> 创建并原子领取 development_context_report
  -> DevContextGraph / CombinedRAG
  -> 预脱敏、限长总结输入
  -> 固定 JSON 受限总结，或确定性回退
  -> 详细回复再次脱敏
  -> 只持久化命中计数和总结方式
  -> 既有 matcher 返回一次 QQ 回复
```

## 7. 继续保持的边界

```text
MainAgent 只能通过显式 /agent 入口触发。
普通聊天不能触发 MainAgent 或 work runtime。
MainAgent 和 ChatAgent 继续分离。
ProjectDocRAG 只允许在显式 /agent dev_context 语义中使用。
不暴露 shell 工具。
不做任意文件写入。
不做未注册数据库写入。
主人写操作必须审批。
只有已注册且 approval_resume_enabled=true 的工具可在审批后恢复。
不开放多步写自动化。
不新增额外 QQ 发送副作用。
Web Owner Console 保持只读。
不新增 Web POST / PUT / PATCH / DELETE。
不新增登录/鉴权。
不开放 /docs、/redoc、/openapi.json。
P2.40b 不自动启用。
不提交 web/owner-console/dist。
```

## 8. 验收重点

```text
固定 JSON prompt 不包含工具契约。
总结输入不含来源路径、检索元数据和测试密钥。
合法 JSON 可转换为固定中文报告。
非法 JSON、字段缺失和主模型异常走确定性回退。
详细报告出现在本次回复，但不进入 task.result 和 task event。
任务持久化继续只含命中计数、总结方式和固定安全说明。
普通聊天、群聊、非主人私聊和 Web 仍不能触发。
```

## 9. P2.44 live 后发现的召回缺口

主人私聊实测证明结构化报告和证据限制正常，但“恢复 Owner Console 当前开发状态和下一步计划”只召回 P2.34 与 P2.39b 历史片段。ProjectDocRAG 索引已经包含 P2.43/P2.44，缺口是纯语义排序、`version-runlog` 单来源霸榜和上下文顺序截断。

P2.44 不通过扩大 prompt、top-k 或上下文上限修补该问题。后续 P2.45 已完成“权威当前状态锚点 + 来源多样性 + 分区预算”设计；P2.45a 已实现快照与锚点读取基础，但尚未接入生产检索。见 `docs/development-context-current-state-retrieval-design.md`。
