# MainAgent 受控文档产物设计

状态：TXT、Word（DOCX）和 PowerPoint（PPTX）本地渲染、Main LLM 工具合同、主人审批门控与恢复执行接线已实现。本地生成命令继续保持 `write_local` 且不发 QQ；独立 `document_delivery_command` 在 `ENABLE_AGENT_EXTERNAL_WRITE=true` 时允许“生成并发送”三种文档，经 `write_external` 审批后只向当前主人私聊发送一次。首次主人 QQ live 证明 Word 生成和 OneBot 文件发送可达，同时暴露 Main LLM 把内部 runtime metadata 包装复制进正文的污染问题；随后已修正 prompt 分区、增加内部 scaffold marker 审批前拒绝，并对“使用刚才/上一条内容”的缺失历史引用执行确定性 `ask_owner`。又修复文档提纲中“推荐下一步”被 `agent_task_read` 抢占的意图优先级冲突。主人重启复验后反馈 Word 文档成功生成且内容质量不错，因此 Word 的主题型正文生成、审批、DOCX 渲染和 QQ 交付已通过完整 live 验收。

日期：2026-07-14。

## 1. 目标

MainAgent 可以根据主人私聊中的明确要求生成三类文档产物：

```text
TXT：UTF-8 纯文本文档。
Word：标准无宏 DOCX。
PowerPoint：标准无宏 PPTX。
```

该能力只创建工作产物，不修改 AIchatbot 项目源码、测试、文档、配置、数据库、RAG、真实表情或正式 manifest。

## 2. 调用与审批流程

```text
主人私聊显式 /agent 请求
  -> Main LLM 生成一个 ActionRequest
  -> owner_write_command
  -> command + title + complete content 参数校验
  -> ToolPolicyCheck(write_local)
  -> 创建任务和审批，不写文件
  -> 主人 /agent 确认 <审批ID>
  -> 重新加载注册表并校验原审批参数
  -> 本地渲染器创建一个新文件
  -> 重新打开/解码并核对格式、大小和 SHA-256
  -> 返回安全 artifact ID、相对路径、大小、计数和短哈希
```

示例：

```text
/agent 帮我写一份 TXT：整理今晚的 QQ live 测试结果
/agent 帮我写一份 Word：总结 AIchatbot 当前开发进度
/agent 帮我写一份 PPT：介绍 MainAgent 当前能力和下一阶段计划
```

这三类自然语言请求依赖 Main LLM 生成完整 `title` 和 `content`。没有 Main LLM、参数缺失、内容超预算或 ActionRequest 非法时不会创建审批，也不会写文件。

如果主人明确要求生成后直接发回 QQ，使用独立外部写链路：

```text
主人私聊显式 /agent 请求“生成并发给我”
  -> document_delivery_command
  -> create_and_send_txt_document / create_and_send_word_document / create_and_send_presentation
  -> ToolPolicyCheck(write_external)
  -> 主人确认审批
  -> 在固定工作区生成一个新文件
  -> 发送前重新校验路径、格式、大小和完整 SHA-256
  -> OneBot send_private_msg 向当前主人发送一个 file segment
  -> 成功或安全失败后结束，无重试、无替代接收者、无换文件
```

旧的 `create_*` 审批不会被追溯扩权。例如已确认的本地审批 `#20` 只完成当时授权的本地生成，不会因新功能被自动发送。

## 3. 固定工作区

生产输出根固定为：

```text
output/main-agent-workspace/
```

该目录已加入 Git 忽略。工具参数没有 `path` 字段；Main LLM 和主人文本都不能指定绝对路径、相对路径或文件名。文件名由本地代码生成：

```text
artifact_<UTC时间>_<随机安全后缀>.txt
artifact_<UTC时间>_<随机安全后缀>.docx
artifact_<UTC时间>_<随机安全后缀>.pptx
```

标题不会进入文件名。工作区存在符号链接或解析后离开项目根时 fail closed。

## 4. 内容合同

```text
title：必填、单行、最多 120 字符。
content：必填、最多 20,000 字符。
输出文件：最多 10 MiB。
PPT：最多 20 张幻灯片，包括标题页。
```

控制字符、空标题、空正文、未知 command 和超预算内容全部拒绝。

Word 和 PPT 使用有限 Markdown 风格结构：

```text
# 一级标题
## 二级标题；PPT 中作为新幻灯片边界
### 三级标题
- 项目符号
1. 编号项
--- PPT 显式分页
```

第一版不解析 HTML、不下载图片、不读取 URL、不嵌入宏、不嵌入可执行文件，也不调用 shell、Tavily、RAG 或未注册数据库。只有独立外部写工具在审批恢复后可以调用一次固定 QQ 文件 sender。

## 5. 格式实现

TXT：使用 UTF-8 和 LF，包含标题、分隔线与正文，写入后重新读取并精确比较。

DOCX：使用 `python-docx`，设置中文字体、标题、三级标题、项目符号和编号列表；保存后校验 ZIP/OOXML 结构、`word/document.xml`，并用 `python-docx` 重新打开统计非空段落。

PPTX：使用 `python-pptx`，生成 16:9 标题页和标题/正文页；每页最多 8 个正文项，超出时受控拆页；保存后校验 ZIP/OOXML 结构、`ppt/presentation.xml`，并重新打开核对幻灯片数。

PPT 结构预检与渲染共用同一分页语义：`## ` 或 `---` 切分内容节，每节每 8 条非空正文拆成一张幻灯片，渲染器再自动增加 1 张标题页。`presentation_slide_count` 在 ActionRequest 校验时计算确切最终页数，超过 20 时在审批创建前拒绝；实际 `_render_pptx` 仍执行同样硬门控作为第二层保护。Main LLM 软约束为最多 12 个内容节、每节最多 6 条非空正文，并禁止另建“封面”节，为续页和模型小偏差保留余量。

PPT 视觉系统为纯本地、无联网和无外部素材的受控主题。标题页使用深色背景、52pt 微软雅黑标题、20pt 副标题和单一强调线；内容页使用浅色背景、36pt 页标题、22pt 正文、蓝/青/紫循环强调色、顶部强调线、章节编号、分隔线、页脚和页码。“下一步/总结/结论/展望/行动”页使用浅青收束背景，建立结尾节奏。渲染器忽略与已有 title 重复的顶层 Markdown H1，不创建重复内容页；正文的 H1–H6、列表和编号前缀在进入页面前归一化。实际产物仍不访问图片、网络、模板下载或任意本地资产。

PPT 内容合同要求 Main LLM 从 `## ` 内容节直接开始，不重复 deck title；按总览、分组能力、当前亮点/边界和下一步建立连续叙事，每页仅一个主旨、3–5 条简洁具体要点，禁止空泛市场化描述和重复句式。该要求同时减少文字密度和不必要的自动续页。

视觉 QA 使用系统临时目录：生成一份不进入正式工作区的 9 页代表性 PPTX，由本机 PowerPoint 以 1600×900 导出全部页面，并检查联系表与代表页原图。当前未见标题换行、文字裁切、元素重叠、页码不一致或页脚越界；临时 PPTX/PNG 只用于本地 QA，不加入正式产物、Git 或 QQ 发送。

所有格式先在目标目录创建唯一临时文件，刷新后原子替换为最终新文件；最终文件再次核对字节数和 SHA-256。失败时清理临时文件，不覆盖已有产物。

## 6. 权限与数据边界

```text
只允许主人私聊显式 /agent。
普通 ChatAgent 不注册该能力。
群聊和非主人不可使用。
风险等级为 write_local。
必须审批；确认后只执行一次。
审批参数固定为 command/title/content/query，不接受 path。
不修改项目文件。
本地 create_* 命令不自动 commit、push、重启或发送 QQ 文件。
不在结果中返回绝对路径。
```

“生成并发送”另外满足：

```text
独立工具：document_delivery_command。
风险等级：write_external。
显式配置：ENABLE_AGENT_EXTERNAL_WRITE=true；默认 false。
只允许当前主人私聊，接收者不是工具参数。
一个审批只生成并尝试发送一个文件。
发送前重新校验完整性；失败不重试、不换文件、不换接收者。
待发送内存状态在发送尝试前消费，重复确认不会重发。
```

审批数据库会保存受限工具参数以支持确认后恢复；QQ 审批卡只显示既有截断输入摘要。内容上限用于限制数据库、模型输出和文件生成预算。后续若需要更长文档，应改为独立 proposal 文件和内容哈希审批，而不是继续扩大数据库参数。

文档 ActionRequest 必须在审批前生成完整 `title/content`，因此 Main LLM 撰写 Word/PPT 时可能需要数十秒。QQ 入口对文档意图先发一条不含文档内容的“正在生成”状态回执；同一会话在当前 `/agent` 完成前使用独立内存锁。后续 `/agent` 不排队、不抢占、不调用 LLM 或工具，只返回“上一条正在处理，当前消息未执行”。互斥锁保持到最终审批/结果消息已交给 QQ adapter，确保后续请求不会先返回。该设计不进行后台排队、无并发文档生成、无 LLM 重试，也不伪造“已完成”进度。

## 7. 当前非目标

```text
读取、修改或覆盖主人已有 Word/PPT/TXT。
自定义输出路径和自定义文件名。
模板上传、图片嵌入、图表、表格、页眉页脚或演讲备注。
PDF 转换。
发送已生成的任意历史文件。
主动发送、定时发送、群发或发给非主人。
Owner Console 下载按钮。
批量生成多个文件。
生成后自动继续修改、提交或发布。
```

QQ 文件发送已作为独立 `write_external` 能力实现，但只覆盖本次审批后“生成的那一个新文件”，不提供通用历史文件发送工具。

## 8. 验证与 live

纯测试使用临时目录，不写真实工作区。覆盖 TXT 精确重读、DOCX 重开、PPTX 重开、标题/正文预算、幻灯片上限、临时文件清理、符号链接拒绝、依赖声明、固定工具参数和审批前零执行。外部发送另覆盖哈希篡改拒绝、`write_external` 配置门控、Main LLM 可见合同、发送前复核、主人私聊约束、待发送状态先消费和单次 OneBot 调用源码审计。

推荐 QQ live 顺序：

```text
1. 保留一次本地 `create_txt_document` 请求，确认审批后只生成文件、不发 QQ。
2. 明确启用 `ENABLE_AGENT_EXTERNAL_WRITE=true` 并重启 Bot。
3. 新请求“生成一份短 TXT 并发给我”，确认先得到 `write_external` 审批而不是文件。
4. 确认新审批，核对 QQ 只收到一个 TXT，确认命令回复包含单次发送成功状态。
5. 重复确认同一审批，核对不再生成、不再发送。
6. 再分别验收短 DOCX 和 PPTX 的基础版式与 QQ 文件可打开性。
```

Bot 重启和 live 需要主人另行执行或授权；本阶段本地测试不会调用 Main LLM、不会消耗文档生成 API token，也不会通过 QQ 发送测试文件。
