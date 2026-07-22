# P2.48b Owner Console 诊断页最小可读性设计

状态：现状审计、最小实现、自动化和生产静态加载已完成；主人确认可读性没有问题，但指出当前页面仍是配置快照，实用性不足。可读性验收通过，诊断动作与实际判断转入 P2.49 固定手动工作流。

设计日期：2026-07-21。

基线提交：`8f34819 Complete P2.47 reliability and pure-image workflows`。

## 1. 目标

诊断页沿用已经通过主人验收的可靠性页标准：不扩大数据面，不堆叠装饰性内容，先让主人读懂现有证据，同时保留原始英文技术字段。

页面需要按以下顺序回答问题：

```text
本次诊断快照的八个区块是否都成功读取。
如果有读取异常，具体是哪个区块。
每项配置、统计或取证边界的中文含义是什么。
对应的原始英文 key=value 或英文错误是什么。
哪些“未执行/未采集”只是只读边界，不能据此判断服务故障。
```

## 2. 现状审计

原页面已经具备八个安全快照区块：

```text
bot_status
diagnostics
config
vision
image_cache
memory
tts
recent_errors
```

此外已有 MainAgent/RootGraph 观测区与运行边界。后端只返回安全的 `summary_text`、`display_lines` 和固定边界字段，不读取聊天正文、原始异常、QQ、Key、URL 或路径，也不执行外部探测。

主要可读性问题不是缺少更多功能，而是表达层级不准确：

```text
section.ok 表示快照区块是否读取成功，原页面却统一显示为“正常/异常”。
这可能被误读为视觉、TTS、Ollama 或 Bot 已完成实时健康检查。
summary_text 通常与 display_lines 完全相同，页面重复展示同一批技术行。
display_lines 是平铺的英文 key=value，主人必须自行翻译字段和布尔语义。
external_probes_executed=false、recent_error_log_read=false 等安全边界容易被误读为功能故障。
英文错误与普通明细没有明确的证据层级。
```

现有 API 已足够支撑可读性优化。本轮没有必要增加后端 label 字段，也不需要重启 Owner Console 后端。

## 3. 最小信息架构

保留原页面结构，只做以下重排：

```text
工具栏：快照时间、读取成功数、读取异常数。
紧凑解读：一行区块读取结论，一行只读取证限制。
八个原有快照卡片：中文区块名 + 英文 section.title。
卡片明细：中文字段含义 + 中文/原值解释 + 原始英文 key=value。
观测区：保留原始观测，只增加记录数和明确空态。
运行边界：保持现有次级位置与只读含义。
```

不新增总体指标大卡、图表、时间线、自由文本搜索、折叠后才能看到的证据或页面写操作。

## 4. 语义合同

### 4.1 区块状态

`section.ok=true` 只显示“快照已读取”，不得写成外部服务“正常”。

`section.ok=false` 显示“读取异常”，顶部列出对应中文区块，并在卡片中直接展示英文原始错误。页面不能根据一个区块读取失败猜测根因。

八个区块都读取成功时，只能总结“当前没有区块级读取异常”，不能总结“所有服务健康”或“系统持续在线”。

### 4.2 中文解释与英文证据

已知字段采用三层紧邻展示：

```text
中文含义：外部探测
解释值：未执行（符合只读边界）
原始证据：external_probes_executed=false
```

中文只提供解释，不替换英文稳定值。原始证据不得藏在 tooltip、折叠区或复制后才能看到的位置。未知字段不猜测含义，使用原 key/value 并保留完整原始行。

### 4.3 只读取证边界

以下值描述本次快照没有主动做某项动作，不等于对应功能异常：

```text
external_probes_executed=false
ollama_probe_executed=false
vision_inference_executed=false
tts_probe_executed=false
recent_error_log_read=false
retrieval_executed=false
index_rebuild_executed=false
```

`recent_errors_collected=false` 必须明确解释为“未采集，不代表没有错误”。

## 5. 实用性边界

本轮明确不做：

```text
不调用视觉、TTS、Ollama、QQ、RAG 或 external-read 探测。
不使用 LLM 生成诊断总结或猜测根因。
不读取聊天正文、RAG 正文、原始异常、身份或秘密字段。
不增加自动刷新 timer、告警、修复、重试、重启或清理。
不增加后端写 API、配置修改或页面写按钮。
不把“没有观测记录”解释为功能健康或功能故障。
不为了页面完整而增加无明确排障用途的新卡片。
```

页面定位仍是“只读配置与统计快照”，不是实时监控平台或自动诊断系统。

## 6. 发展方向

完成本轮人工验收后，诊断页后续只有在出现明确排障问题时再扩展：

```text
若主人经常需要定位某个区块，可评审卡片内的本地筛选或异常优先排序。
若需要判断服务实时健康，必须先为对应组件设计独立、显式、主人触发的安全探测合同。
若需要历史变化，必须先建立固定时间窗和安全历史 read model，不能从单次快照推断趋势。
若需要更多核心、聊天或 MainAgent 诊断详情，应先注册严格 scope，并保持首故障短路和零自动处置。
```

当前最合适的发展方向仍是先验收现有信息是否足够好读，而不是继续添加内容。

## 7. 验收标准

```text
1. 主人能立即区分快照读取状态与外部服务健康状态。
2. 八个原有区块全部保留，没有新增低价值面板。
3. 已知字段有中文含义，原始英文 key=value 同屏直接可见。
4. 英文原始错误不被中文覆盖或隐藏。
5. “未执行/未采集”的只读语义不会被写成功能异常。
6. 重复 summary_text 不再占用页面空间。
7. 读取异常区块具有明确但不过度的视觉优先级。
8. 空观测只说明本次快照无结构化记录，不推断健康结论。
9. 所有请求继续为 GET，API 保持 read_only=true、web_write_enabled=false。
10. 查询前后 SQLite 大小和 mtime 不变。
11. 不新增模型、探测、重试、重启、告警、修复、清理或写副作用。
12. 自动化、生产静态加载和主人人工页面验收同时通过后才收口。
```

## 8. 当前实现结果

实现为纯前端变化，后端 API 合同未变，因此不需要重启 Owner Console。新增诊断页 3 个测试，覆盖快照与健康语义分离、中英证据共存、英文错误保留、异常区块优先、空观测和无写按钮。

当前验证结果：

```text
诊断页定向 3 tests OK。
完整前端 18 tests OK。
TypeScript typecheck OK。
Vite production build OK。
GET-only guard OK，检查 28 个 TypeScript 源文件。
git diff --check OK，只有既有 Windows 换行提示。
生产诊断路由 HTTP 200。
API read_only=true、web_write_enabled=false。
GET 前后数据库大小和 mtime 不变。
8090 保持原单一监听进程，没有重启。
stderr 只有 4 行正常启动 INFO，ERROR/Traceback/Exception 为 0。
```

当前静态页面已经加载，等待主人在真实页面确认可读性和信息密度。
