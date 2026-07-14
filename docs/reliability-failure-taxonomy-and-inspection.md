# 可靠性错误分类与周期巡检设计

状态：第一版已实现，等待 Bot 重启后的主人 QQ 快速巡检 live。脚本只读巡检已在本机通过。

## 1. 目标

本轮把分散的错误、超时、失败调用和异常退出信号统一为可统计、可解释、可复查的可靠性信息。重点不是自动修复，而是让主人能快速回答：

```text
当前核心服务和关键配置是否可用
最近是否出现高频错误或超时
失败主要属于哪一类
下一步应该先检查什么
巡检做了什么，以及明确没有做什么
```

## 2. 五类错误合同

所有关键失败统一归入以下五类，不把模型原始异常、密钥、URL 或完整堆栈直接返回给用户：

| 类别 | 稳定值 | 典型场景 | 默认建议 |
| --- | --- | --- | --- |
| 配置问题 | `configuration` | 缺少必填项、无效地址、未注册 scope、恢复参数不完整 | 检查开关、必填配置、服务地址和模型名，不自动修改 |
| 模型问题 | `model` | 模型不存在、429/额度/限流、空响应或非法模型响应 | 检查模型、额度、限流和响应格式，避免连续重试 |
| 权限问题 | `permission` | 401/403、主人策略、审批上下文不一致 | 检查鉴权、主人身份和审批状态，不绕过权限 |
| 网络问题 | `network` | 超时、连接失败、DNS/TLS/代理、本地服务不可达、QQ 文件发送失败 | 先确认服务和网络可达，再由主人决定是否重试 |
| 数据问题 | `data` | SQLite、索引、schema、JSON、文件完整性、PPT 超页、未知运行状态 | 检查数据与文件，不覆盖原文件，不自动修复 |

分类结果包含稳定 `code`。已明确覆盖：

```text
request_timeout
connection_failed
model_rate_limited
model_not_found
authorization_failed
invalid_configuration
data_validation_failed
presentation_slide_limit_exceeded
artifact_integrity_failed
document_delivery_failed
approval_context_invalid
required_arguments_unavailable
unexpected_runtime_state
```

未来新增可读提示时应优先增加精确 code，不解析或依赖完整异常原文。

## 3. 日志与用户提示

新的 `log_ai_event_error` 记录：

```text
timestamp
安全 user/group 审计字段
category
code
exception type
脱敏且有长度上限的 message
```

API Key、token、password、secret 和 URL 会在写入前脱敏。MainAgent 观测文本同样先脱敏并限制长度。

Main LLM 失败继续保留原有针对性提示，同时追加 `类别 / code`。只读工具失败、正式只读工作失败和审批恢复失败不再直接回显任意异常原文，而是返回组件名、类别、稳定 code、简要原因和下一步建议。审批恢复失败写入任务/事件时只保存安全分类，不持久化工具异常原文。

## 4. 巡检入口

### 4.1 QQ 只读入口

```text
/agent 做一次可靠性巡检
```

该自然命令确定性映射到现有 `owner_read_command/ops_health`，复用视觉、MemoryRAG、RootGraph、MainAgent 和近 24 小时错误分类证据。它不调用 Main LLM 来猜测当前状态。

Bot 重启前仍可使用原入口：

```text
/agent 做一次系统健康检查
/agent 帮我看一下最近错误
/最近错误
```

### 4.2 本机脚本

默认检查最近 24 小时：

```powershell
.\scripts\inspect-reliability.ps1
```

检查最近 7 天：

```powershell
.\scripts\inspect-reliability.ps1 -Hours 168
```

写入固定最新报告：

```powershell
.\scripts\inspect-reliability.ps1 -Hours 24 -WriteReport
```

报告只能写到 Git 忽略的：

```text
output/reliability-inspections/latest.txt
```

脚本不会接受任意报告路径，不创建时间戳历史文件，避免无人值守运行导致无界增长。

## 5. 检查范围

本地状态检查包括：

```text
.env 是否存在
聊天模型必填项是否配置（不输出值）
MainAgent 开启时其模型必填项是否配置（不输出值）
NoneBot 本机 8080 端口是否可达
SQLite 是否可用 immutable read-only 方式读取 schema_version
虚拟环境是否存在
视觉开启时本机 Ollama 11434 端口是否可达
```

日志信号来自固定文件尾部，单文件最多读取 2,000 行：

```text
logs/ai_chat_error.log
logs/nonebot.err.log
logs/owner-console.err.log
logs/tts-service.err.log
```

无行内时间戳的日志使用文件最后修改时间参与窗口过滤，避免把很旧的服务日志错误计入当前时间窗。成功、完成和正常审批等待信号不会作为失败统计。

“疑似异常退出”只识别明确的 `SystemExit`、unexpected exit、fatal/critical 和非零 exit code 信号。没有信号只能表述为“未发现”，不能证明进程在整个时间窗持续在线。

## 6. 周期运行建议

第一版不由 Bot 自动创建 Windows 计划任务。主人如需无人值守巡检，可以在 Windows 任务计划程序中设置：

```text
程序：powershell.exe
参数：-NoProfile -ExecutionPolicy Bypass -File "D:\AIchatbot\scripts\inspect-reliability.ps1" -Hours 24 -WriteReport
起始于：D:\AIchatbot
频率：每 30 分钟
```

计划任务只刷新固定 `latest.txt`。自动 QQ 告警、邮件告警、自动下钻、自动重试、服务重启、配置修改和数据修复仍未开放。

## 7. 2026-07-14 本机基线

本轮实际只读巡检结果：

```text
当前本地状态：正常
NoneBot 8080：可达
SQLite immutable read-only：通过
聊天与 MainAgent 模型必填项：已配置
最近 24 小时：0 个失败信号
最近 7 天：11 个失败信号
  数据问题 8
  网络问题 3
  超时 1
  失败调用 3
  疑似异常退出 0
```

7 天统计是日志信号盘点，不等于存在 11 个仍未解决的当前故障，也不等于 11 次独立事故。24 小时窗口和当前本地状态均正常；后续结构化 `category/code` 日志会提高趋势统计精度。

## 8. 安全边界

巡检不执行：

```text
外部模型或 Tavily 请求
真实聊天、视觉、TTS、embedding 或 RAG 主动探针
QQ 测试发送
审批确认
服务启动、停止或重启
失败重试
配置修改
数据库、索引或文件修复
日志清理
```

本轮只新增诊断代码、只读脚本、固定可选报告和可读提示；没有扩大 MainAgent 对项目文件、shell、Git、数据库写入或任意 QQ 发送的权限。
