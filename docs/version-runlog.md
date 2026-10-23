# 版本运行日志

## 2026-10-23 项目进度上传前验证

本次整理记忆时间与受众隔离、共用记忆读取、聊天路由与配置治理、百科与视觉诊断、表情可靠性、控制台账号视图，以及 B 站独立浏览、分享、对话留存和主人文字私聊的当前源码、测试与运行文档。

公开 Markdown 中的具体人格称呼统一使用“默认人格”“独立人格”；既有配置变量、角色键、命令参数和文件路径保留兼容。提交前检查候选文件，未发现真实密钥、私人卡片复制或受保护运行数据。私人 `.env`、数据库、浏览器资料、日志和本地产物继续留在本地。

全量验证发现并修正两处问题：账号设置视图延迟加载表情分类模块，恢复控制台启动时不导入模型 SDK 的边界；历史持久化测试验证新增的记录时间标记，同时继续检查消息原文和顺序。后端 1613 项测试中 1608 项通过、5 项条件跳过，无失败；前端 15 个文件共 87 项测试通过，TypeScript 检查、Vite 生产构建及前端边界 guard 均通过。

以上为源码和离线回归证据，不替代真实 QQ/B 站跨平台记忆效果验收；该项已知失败案例及待查根因继续保留。本次上传准备没有重启 Bot、启动真实浏览或发送测试私信。

## 2026-10-23 跨平台记忆实际效果验收补充

主人反馈：QQ 可提及 B 站分享记录，但在 00:58 的实际对话中否认收到刚发生的 B 站私聊；B 站使用 QQ 记忆的效果仍未实测确认。
只读核对：00:52 主人消息、00:53 默认人格回复及索引已留存，入库早于该次 QQ 提问；当前背景重建包含完整双方对话，四条近期消息无截断，占用 779/1200 粗估 token。
当前重建不能替代那轮真实模型请求，根因尚未确定；此前文字收发成功记录仍成立，但不应扩展为跨平台私聊记忆已验收。
未发送测试私信、请求聊天模型、重启 QQ 或修改记忆读取规则。

## 2026-10-23 主人私聊文字回复与独立收件进程

新增浏览器内限定主人会话的逐条私信读取、分页游标、初次基线、持久消息队列和短暂合并。
专用 reply 任务复用角色与 QQ 记忆，附本平台近期对话、独立 RAG 和相关当天小记；真实收发留存，不改 QQ 原有记忆规则。
发送沿用原投递账本，固定批次键防重发，生成中断不自动重新生成，未知发送不自动重放，已发可恢复留存。
新增私聊回复的启动/状态/停止双击入口；保留自动浏览独立控制，浏览器控制锁缩短至读写操作，模型生成不占锁。
真实专用 Edge 收件 HTTP 200、业务成功，已建立跳过旧消息的基线；没有伪造主人新消息或补答历史。
237 项 B 站回归、13 项共用记忆测试通过；修正 Windows 后台继承句柄后新增 2 项，通过 23 项收件专项，相关累计 252 项。
已启用独立监听，主人发送新文字并确认收到回复；本地核对一批已发送并归档，双方各一条留存、两个索引条目写入。
实际停止/重开后启动控制约 4 秒返回，接收游标保留、已发批次未重复；原自动浏览发送模式及 09:51 的下一轮计划保留，未重启 QQ。
第一阶段为文字回复，主人分享视频的字幕理解及其他媒体解析仍未接入；角色语气后续以主人实际体验调整。

## 2026-10-22 独立自动浏览进程与持久分享额度

主人要求落实自主刷视频并提供明确启动方式。新增随机间隔工作循环与 PowerShell 前台/隐藏后台启动脚本。
默认 90–180 分钟、每天最多 6 轮、精选 1 条、00–09 点休息；原始配置集中在仓库外 JSON，可停止后修改重启。
按 BVID 过滤近期已评估候选，首页刷新序号持久递增，复用原角色/QQ 记忆、字幕校验、小记与自然分享格式。
发送账本原子预留日主动上限 3 条和至少两小时间隔，手动/自动共用，失败/未知/旧记录按文档明确分类。
状态与停止由跨进程 OS 锁和运行身份控制，进程崩溃不重放旧任务，错误至少 4 小时后再调度。
209 项 B 站离线回归与 13 项共用记忆读取测试通过，共 222 项；新增专项 29 项，包含跨进程真实进程启动、status/stop/退出验证，以及 Windows 中文路径 UTF-8 状态输出修正。
本轮未自动启动真实浏览、调用付费模型、发送私信、重启 QQ 或创建开机任务；新入口启用后的持续运行待实际验收。

## 2026-10-22 今日观影小记与 QQ 当天经历背景

主人接受随机间隔小轮浏览方向，并要求将已经理解但没有分享的视频用于当天的内容与感想小记。
新增按固定身份隔离的独立单日存储，预览逐轮合并、同片去重，北京日期变化后不再注入旧小记，下一次写入替换。
只收通过身份、引用及主题一致性校验的字幕总结；感想来自同一次 summarize 请求的新字段，不额外发起日记模型调用。
QQ 的 viewing_today 与原 3 轮/5 条背景共用 1200 粗估 token、20% 相对帽，不改 QQ 原文及记忆维护规则。
小记不是私信或送达记录，不建立长期索引；已有报告和真实私聊留存不删除。
180 项 B 站离线回归通过，新增 18 项覆盖日切换、去重、来源拒绝、预算、身份隔离及故障降级。
本轮未请求真实 B 站/模型、发送私信、启用自动刷视频或重启 QQ；真实新预览及 QQ 正常重载后的体验待验收。

## 2026-10-22 B 站时间化留存与 QQ 独立背景

保留既有 B 站按视频检索 QQ 记忆的 RAG；新增 B 站实际对话独立归档、最近 3 轮注入及最多 5 条未展示消息召回。
QQ 原有近期原文、摘要、状态卡、人工长期记忆、向量索引与检索配额不变，新材料位于 QQ 近期对话之前。
独立背景上限 1200 粗估 token、同时不超过 QQ 近期原文加当前输入的 20%，只裁切展示，完整原文留存。
时间区分平台发送、本地确认、仅记录和历史发送尝试；当前时间动态渲染，不以导入或摘要时间冒充原发送时间。
实际发送接受后记录，失败/未知不回写；归档或 embedding 失败不改变送达状态且不重发。
从既有报告和成功台账只回填 1 条发送原文、跳过 4 份报告，索引 1 条；真实只读预览约 398 粗估 token。
组合回归 451 项，450 通过、1 项文件链接环境限制跳过；新增相关覆盖 30 项。
未发送新私信、调用聊天模型、启动接收/刷视频调度、修改角色卡或重启 QQ。
QQ 新代码需正常重载；B 站接收器及跨平台重逢台账未实现。详见 [留存说明](bilibili-history-runbook.md)。

## 2026-10-22 QQ 与 B 站共用只读记忆读取

主人明确批准对齐 QQ 现有记忆系统，撤销 B 站独立候选池和关键词筛选设计。
新增纯读取 `memory_reader.py`，QQ build_history 使用共用历史查询/时间格式，人工长期记忆列表与格式化复用共用实现。
B 站保留精确身份映射，按 QQ 配置直接读取近期原文、最近正式摘要、现有当前场状态卡与最新手动记忆。
不再限制 12 条原文、查询 80 条摘要候选或 40 条长期候选，也不以 4000 字符总帽再次缩短完整热场。
固定角色卡不修改，记忆为本轮临时模型数据；QQ 与 B 站仍不是一个实时模型会话。

已有语义索引在同一只读事务中捕获；B 站复用 QQ 的 retrieve_memory、相似度、provider 与 top-k/字符预算，
对本轮公开视频元数据做查询 embedding，不重新向量化源记忆或写入索引。
受众校验和源记录版本核对先于 top-k，其他用户/人格、群来源、删除/过期索引不进入上下文。
索引缺失或查询失败明确记录固定状态，无命中不补旧内容，不回退关键词筛选；基础上下文仍可用。

本机只读状态：40 条原文、1 条正式摘要、0 张已有状态卡、4 条长期记忆，语义索引可读。
随后一次真实本地 embedding 查询命中 5 条，完整序列化背景为 12778 字符；未调用聊天模型，不能据此给出新版本 token 价格。
新增专项覆盖 QQ/B 站一致性、完整文本、只读无迁移、时间/快照边界、语义召回与隔离及失败退化。
本轮相关回归 356 项，355 通过、1 项因本机无法创建文件链接跳过；共享读取专项 13 项通过。
编译、局部 diff 检查与 12 个变更文件隐私检查通过。
未调用聊天模型、请求 B 站、额外发送私信、生成摘要/状态卡、维护索引或重启 Bot；QQ 共用实现需正常重载后在运行进程生效。
旧版发送样本的 token 数不适用于新的完整热场输入，后续应按供应商实际用量验收。

## 2026-10-22 固定会话整轮浏览、真实视频私信与自然分享格式

主人批准继续固定会话验证，并要求测试通过 B 站私信分享合格视频。
新增浏览器 BrowseClient 与限定 HTTP bridge：候选和详情在专用 Edge 内 fetch，字幕捕获网页原生 WBI player；
网页元数据、候选详情、player 身份与分 P 时长相互核对，沿用无 Cookie CDN、整轨时间轴和引用校验。
旧保存 Cookie 的 nav 实测 -101，固定会话 nav 为 0；预览改用固定会话账号，不导出 Cookie，也不再依赖旧凭据。
私信 CSRF 在浏览器内读取并加入唯一允许的发送接口，不返回 Python 或落盘；复用原主人绑定、互关、占位和未知结果处理。
桥接初始化读取私信域名未读数量接口以建立同源文档，不读取私信正文。

`preview` 默认 browser，`--send-one` 显式提交首条合格结果；按双方账号和 BVID 稳定去重，无合格项不强行分享，无自动重试。
真实运行读取首页/关注各 3 条，共 6 条候选，精选 2 条，其中 1 条有效总结、1 条仅元数据；只提交 1 条私信。
平台 HTTP 200/code=0，发送库 sent，日志写入失败 0；主人已确认收到，总结基本正确，但分享呈现过于报告化。
原因是草稿函数额外把结构化 claims 与字幕说明拼到了角色 `why_share` 之前。
现改为完整自然分享话语加规范链接，不添加“想分享给你：”前缀、不在 85 字处截断；证据和总结仅留本机报告。
提示词同步明确 why_share 为直接私信正文；发送前仍复核来源、引用与草稿一致性。原已发正文保留作历史审计，未补发。

QQ 近期私聊已纳入每轮只读快照，最近最多 12 条消息，另有每次最多 2 条摘要/8 条长期记忆，包上限 4000 字符。
本轮两次各注入 8/1/4 条、2865/2898 字符，两次模型请求总计 15143 token，已含记忆输入。
未启用完整热场、空窗状态卡或 RAG，未写回 QQ、重启 Bot、创建常驻任务或增加其他真实发送。
全部 B 站相关回归 130 项通过。固定会话整轮与原格式送达已验证；新分享格式仅离线验证，未标主人接受。

## 2026-10-22 固定会话单片网页原生字幕读取成功

主人在固定会话登录保留验收后要求继续，新增 `src/bilibili_browser_probe.py` 与
`bilibili_browser.py subtitle-check --bvid <BVID> --page 1`。
账号精确匹配后在同一持久上下文创建一个临时视频页，导航前启用 Fetch 拦截并异步发送导航，
捕获网页自行签名的首个 WBI player GET，不重签或回退旧接口。
阻断非读取方法、媒体和播放地址、历史上报、其他 BVID 及后续重复 player；
注入禁播脚本，退出仅关闭临时标签页。凭据、Cookie、原始 player、签名 URL 不进报告或日志。
沿用既有视频/分 P 身份、无 Cookie CDN、大小限制和全轨时间轴校验；不重建浏览、模型或记忆链路。

2026-10-22 20:03（Asia/Shanghai）对原字幕错配样本实测：nav 200/code=0、网页 200、
原生 player 200/code=0、CDN 200，一次 player 请求得到 14 段/73 字自动字幕，
aid/bvid/cid、分 P 时长和全轨时间轴通过，日志写入失败 0。
该片时长 508 秒，末段到 426.7 秒；本地抽查为台词型字幕，与旧科普长文错配不同，
但不足以还原画面或完整战斗过程，不能标记完整理解或内容可分享。
报告明确 content_reviewed=false、share_eligible=false；有效正文仅保留仓库外私人诊断报告。

新增网页字幕专项 15 项；全部 B 站相关回归 110 项通过。
真实执行仅一次单片命令，没有额外换片或重复 player 请求，没有调用模型、读取 QQ 记忆、生成草稿或发私信。
本次通过范围为该账号固定会话下的单样本来源读取；原 inspect/preview/diagnose 仍走旧接口，
没有全站恢复、浏览器整体迁移或自动分享验收。操作见 [固定浏览器说明](bilibili-browser-runbook.md)。

## 2026-10-22 B 站固定会话真实登录与重开保留验收

主人确认已在默认人格专用 Edge 扫码登录。19:57（Asia/Shanghai）只读 check 为 HTTP 200/code=0、
logged_in、account_verified=true，与既有默认人格账号绑定匹配。
随后正常 close，status 确认 browser_running=false；19:58 使用同一资料目录重新 open，
reused_process=false，确认本次为新启动而非复用仍在运行的实例。
再次 check 仍 HTTP 200/code=0、logged_in、account_verified=true，两个检查日志均无写入失败。
固定会话真实登录和关闭重开保留标记 live_passed，专用窗口保持打开供后续使用；平台登录仍可能过期。
本轮仅执行会话生命周期与账号检查，没有请求视频或字幕、读取 QQ 记忆、调用模型或发送私信。
未改动既有浏览接口后端，不能据此标记字幕风控解除。上一轮 B 站专项 95 项回归结果保留，本轮仅更新验收文档。
操作与范围见 [固定浏览器会话说明](bilibili-browser-runbook.md)。

## 2026-10-22 B 站专用固定浏览器会话

按主人“先尝试一下”授权新增 `src/bilibili_browser.py` 和 `scripts/bilibili_browser.py`。
使用固定仓库外 Edge 用户资料、正常默认上下文和可见扫码窗口；通过本机随机 CDP 端口控制。
提供 open/check/status/close，已运行实例复用，不创建隐身上下文、不注入或导出 Cookie。
只读 nav 核对现有绑定；绑定摘要变化、非空未绑定资料、仓库内或重定向资料拒绝复用。
控制命令有 OS 文件锁，浏览器响应和消息有界，协议错误转换为固定安全消息；
检查状态和沿用的诊断日志不含昵称、明文 UID、Cookie 或服务端错误原文。
显式声明已有本机 websockets 依赖，无需新增 Playwright。

浏览器专项 23 项、全部 B 站相关回归 95 项通过；新增代码编译、局部 diff 与 10 个变更文件的隐私检查通过。
本机真实 open 成功（首次新进程），窗口保留供主人扫码；
19:51（Asia/Shanghai）最终 check 为 HTTP 200/code=-101、login_required，日志无写入失败。
当前仅会话管理实现通过；真实扫码匹配和关闭重开保留待主人完成登录后验收，未标 live_passed。
浏览读取后端尚未迁移，字幕恢复未验收；本轮无模型、QQ 库读取、私信或自动浏览调度。
详见 [固定浏览器会话操作说明](bilibili-browser-runbook.md)。

## 2026-10-22 B 站诊断日志与单片来源实测

按主人要求补充脱敏结构化日志，所有浏览请求的阶段、HTTP/JSON 业务码、响应类型、长度/指纹、
耗时及账号/签名编码/字幕校验结果均可按 trace 关联，主题冲突和模型否决也保留固定分类。
日志白名单拒收 Cookie、签名值、完整 URL、UID、服务端自由文本、角色卡和 QQ 记忆；
非 200 正文最多读 64 KiB 提取固定信号，单文件上限 512 KiB，保留最近 20 份本模块日志。
新增 diagnose 单片只读入口；日志故障不覆盖原错误，状态及路径由 CLI 输出。

实测：绑定登录态与视频详情正常（200/code=0），WBI player 返回 412 HTML，
包含“请求被拒绝”“风控”信号；时间差约 0.3 秒、无系统/环境显式代理配置、请求编码一致。
已确认拒绝页，尚未确认具体触发条件，不能推断旧错配字幕的上游原因或断言签名服务端验证通过。
本轮无模型/QQ 记忆/私信/后台任务，可靠字幕仍阻塞；专项共 72 项测试通过。

## 2026-10-22 B 站字幕错配排查与撤回修复

主人反馈预览描述与实际视频明显不符。原始报告显示游戏视频元数据对应核能科普字幕，
不是只有最终文案的措辞偏差；旧 player 实测在请求身份字段一致时仍返回不同主题字幕。
模型实际上已给出主题冲突说明和 worth_sharing=false，代码却仍生成草稿。

修复：签名键从 nav 即时读取，改用 WBI player 并取消旧接口回退；核对 aid/bvid/cid。
全轨时间轴在字符截断之前校验，排除非有限时间、逆序和超出分 P 时长的字幕，记录正文指纹和来源端点。
总结 JSON 增加 content_alignment/alignment_reason，不一致或不确定时必须空摘要、禁止分享；模型否决不再生成草稿。
来源错误明确显示安全错误类别，不用空字幕或 metadata_only 掩盖；有分 P 来源异常时也不生成该视频总结。
两份旧内容预览标记 withdrawn，清空分享草稿并保留私人诊断证据；原用量数字仍为真实历史消耗，内容可信验收撤回。

账号/浏览/记忆专项共 59 项通过。真实同片复核的签名接口仍 HTTP 412，按预期无字幕、无模型请求和无草稿。
可靠字幕读取尚未恢复，不能将拒绝错误内容等同于成功理解视频。
没有发送分享、重启 Bot、写 QQ 库、创建后台任务或自动启用 ASR/视觉。

## 2026-10-22 B 站接入 QQ 主人私聊记忆

主人明确要求在继续浏览功能之前接入同一默认人格的 QQ 记忆。
新增独立只读适配器，依据既有 B 站双方绑定、QQ 配置主人与唯一固定默认人格机器人映射生成仓库外 memory-binding.json。
后续先核对映射再读取，身份/会话/存储模式变化直接拒绝，不静默改绑。
使用原 scope 解析选中 legacy 或人格专用库，V2 仅临时模式不读取其他库。
mode=ro/query_only 事务内读取主人近期私聊、摘要和长期事实/偏好；精确限定 owner、session、消息类型及来源，排除群聊及其他人格。
每次按视频元数据作本地关键词排序，序列化记忆包最多 4000 字符，注入筛选与总结的数据字段，不开放历史命令执行。
不增加 embedding 或记忆提炼模型请求；生成依据仍由字幕约束。
新增 memory-status 本地状态入口、--without-qq-memory 对照选项、报告来源状态和逐调用注入长度/粗估审计。
供应商实际输入用量已含记忆，粗估不重复计费；记忆包不复制到报告，生成结果仍保存在仓库外私人目录。

验证：账号/浏览/记忆专项共 52 项通过，包括临时合成库隔离、V2 路径、映射变化先拒读、预算、时间和数据库内容不变。
真实状态检查成功；带记忆预览读取 12 条候选、精选并总结 1 条，两次调用总用量 17347 token。
两步注入记忆分别 3188 / 2781 字符；本地粗估记忆 token 分别 2221 / 1788，非供应商独立分词结果。
样本字幕正文 1128 字符，不能与先前不同视频总量相减推导净增。
未发送 B 站浏览分享、写回 QQ 记忆、重启 Bot、创建后台任务、改变首页刷新参数或更新 RAG。
操作与完整范围见 [B 站 QQ 记忆接入说明](bilibili-memory-runbook.md)。

## 2026-10-22 B 站浏览与分享本地预览

主人确认先前测试私信在 B 站收到，账号接入获得首次真实送达验收。
随后明确批准实现单轮候选发现、角色初筛、可用字幕读取和本地总结预览。
新增独立浏览模块、人格配置适配器、CLI 和操作说明；发现与字幕线路为本项目独立实现。
来源为首页推荐和关注动态，分别记录失败/空列表；过滤普通视频、按 BVID 合并，并逐条读取规范详情。
精确校验固定默认人格映射，复用已有角色卡和模型线路，不执行聊天插件初始化或打开聊天库。
单次最多两条精选、每条前两个分 P、12000 字符字幕；无字幕不生成内容总结和可分享草稿。
字幕 CDN 与账号客户端分离，HTTPS 域名限制、无 Cookie、禁止重定向、2 MiB 响应上限。
结构化筛选需覆盖全部候选且只引用候选 ID；总结需匹配字幕段 ID 和原句，否则不生成草稿。
报告保留覆盖范围、自动字幕、未读分 P、证据、草稿和用量，置于仓库外私人目录，不保存角色卡、凭据或签名字幕 URL。
紧凑字幕数组降低重复字段开销；最多三次模型请求、失败不重试，失败尝试也记录为用量未知。

验证：新增浏览专项 19 项、账号专项 18 项，共 37 项通过。
真实账号成功读取两个来源各 6 条候选，模型选中 1 条并生成带字幕引用的总结和分享草稿；
该样本为单 P 自动中文字幕，末条字幕接近视频结束，实测两次模型请求共返回 32437 token。
真实结果只在本机预览，未发送浏览分享、未创建定时任务、未读取 QQ 记忆、未重启 Bot、未更新 RAG 或写聊天库。
详情见 [B 站浏览预览说明](bilibili-browsing-runbook.md)。下方第一步条目为此前验收状态，真实送达状态以本条为准。

## 2026-10-22 B 站账号接入第一步

按主人明确授权新增独立 `src/bilibili_connector.py` 与 `scripts/bilibili_connect.py`。
支持本机隐藏输入 Cookie、nav 验证登录身份后 Windows DPAPI 加密保存、精确 UID 绑定、
互关检查及文本/链接私信预检；只有显式 `--go` 才提交平台私信接口。
发送前通过独立 SQLite 原子占位去重，明确区分 pending / sent / failed / unknown；
超时、异常响应、中断与结果记录失败不直接重试，相同任务并发只能有一个进入提交。
不保存正文或凭据到发送记录，不把平台原始消息或 Cookie 写入错误输出，不跟随认证请求重定向。

验证：B 站专项 18 项全部通过（模拟 HTTP），包含本机 Windows DPAPI 加密往返、
新建客户端重跑去重、并发占位、发送记录故障、目标与表单、默认无 POST 及 CLI 异地目录启动。
Python 编译、独立导入烟雾测试及 diff 空白检查通过；本次改动文件隐私扫描未发现问题。
未配置真实 Cookie/UID、未访问真实账号、未发送私信，不能标记 live_passed / owner_accepted。
未启动常驻任务、加载 QQ 插件、重启现有服务、调用 LLM 或修改聊天数据库。
自主浏览、私信接收、视频理解及跨平台记忆继续留在后续阶段。
使用和首次本机验收见 [B 站账号接入说明](bilibili-connection-runbook.md)。

本文作为 AIchatbot 的版本运行日志，用于汇总每个版本的实际落地状态、live 验证、补丁和后续边界。

> 历史阅读规则：本文件按日期保留当时事实。每个条目中的“当前”“下一步”“等待主人”“尚未完成”只对该条目的日期与阶段有效，不构成现在的主人授权，也不得据此自行恢复旧 backlog。当前批准方向、优先级和唯一下一步只以 [current-development-status.md](current-development-status.md) 为准，并在执行前用实时 Git/代码/运行态复核。

文档分工：

```text
版本设计文档：
  记录该版本主要要实现的目标、边界和设计方案。

版本运行日志：
  记录该版本实际做到了哪里、哪些 live 验证已通过、哪些补丁已完成、哪些内容仍不开放。

每日 runlog：
  仅作为开发过程和上下文恢复材料；后续与版本具体内容相关的稳定结论，应整理回本文。

项目 RAG 使用手册：
  docs/project-rag-usage.md 保留为本地 RAG / DevContextGraph / Codex 恢复上下文手册。
```

## 2026-07-11 MainAgent external-read 安全设计

状态：设计和前三刀本地合同已建立，未新增阶段编号；未启用任何真实联网工具。

本次完成：

```text
确认 system_diagnostics_report 是第二个正式只读工作任务；其基本稳定后的原主线是 external-read security design，而不是第二个审批写操作。
确认 RiskLevel.READ_EXTERNAL、PolicyEngine enable_external_read 和 ENABLE_AGENT_WEB 已存在，但当前没有 external-read ToolSpec/provider/executor/sanitizer。
新增 docs/main-agent-external-read-security-design.md。
第一版建议固定 external_search provider，禁止 arbitrary URL fetch。
第一版建议 llm_visible=false，只允许主人私聊严格命令；外部读取不创建写审批，也不保存 pending intent。
定义三重门控：工具注册、ENABLE_AGENT_WEB、严格主人命令。
定义 query 数据最小化、HTTPS/provider allowlist、IPv4/IPv6/metadata 阻断、redirect/DNS rebinding、响应预算和 prompt injection 边界。
定义 external_read_report 候选 work type 和独立 sanitizer；不得复用 external_request_count=0 的 system diagnostics sanitizer。
定义从纯策略、fake provider、正式 work、严格 QQ 命令到真实固定 provider live 的分步路线。
第一刀纯安全策略随后已实现：新增 external_read_security.py 和无网络参数化测试。
query 规范化后限制 300 字，并拒绝 URL、本地路径、API key/token/Authorization/cookie/JWT 等常见秘密形态。
固定 endpoint 只允许 HTTPS/443、无 userinfo/query/fragment，且 host 必须精确命中 allowlist。
解析后地址必须为公网 IPv4/IPv6；除 is_global 外显式拒绝 private、loopback、link-local、multicast、reserved 和 unspecified。
ExternalReadBudget 固定单请求、0 redirect、0 retry，最多 3 结果、256 KiB 和 15 秒。
实现不执行 DNS、HTTP、provider 调用或 ToolRegistry 注册。
第二刀 fake provider 链随后已实现：新增 external_search.py、async ExternalSearchProvider 协议、结构化 response/result、确定性 sanitizer 和 execute_external_search。
executor 在 provider 前执行 query policy，provider 只调用一次，并按 budget 强制总超时和 response_bytes 上限。
外部结果移除 HTML/script/style/template/noscript、控制字符和双向控制符；title/snippet/time 限长。
提示注入结果替换为中性占位；输出只显示 source_host，不显示完整 URL/query/fragment。
结果按 title + host 去重并最多保留 3 条；非法结果按条丢弃，全无可用结果时返回证据不足而不扩大查询或重试。
确定性 formatter 不调用 LLM，不写 RAG/记忆，不打开来源页面，也不发送额外 QQ。
fake provider 只存在于测试；生产模块没有 DNS/HTTP client、ToolSpec 或 QQ 接线。
第三刀正式 work runtime 随后已实现：新增可选注入的 external_read_report，risk_level=read_external，requires_approval=false。
未注入 external executor 时，生产 OwnerRuntimeFactory 仍只注册既有两个本地只读 work；当前 QQ 不会看到 external-read。
独立 ExternalReadReportPayload/sanitizer 强制单次外部请求、最多 3 条结果、合法 provider 枚举、来源/丢弃计数和成功/无结果状态一致性。
外部 query 只传给本次 executor；任务 goal 和 work event 使用固定占位摘要，不保存 query 原文。
title、snippet 和 source host 明细只进入本次经过清理的临时回复；持久化结果只包含 provider 名称和安全计数。
无结果为 done；执行器原始异常只保存异常类型和固定错误类别，不保存异常正文。
第三刀仍只注入 fake executor 做 runtime 测试，没有严格 QQ parser、ToolSpec、DNS、HTTP 或真实 provider。
第四刀严格 QQ 命令随后已实现：只接受 /agent 执行外部只读查询：<问题>。
命令按主人私聊、ENABLE_AGENT_WEB、固定 executor 和 query policy 顺序门控；任何拒绝都发生在任务创建和 provider 调用之前。
生产 OwnerRuntimeFactory 仍不注入 external executor，ENABLE_AGENT_WEB 默认 false；因此当前命令只返回关闭或 provider 未配置提示。
fake executor 只用于测试可选注册和 work 合同；未给普通聊天或 Main LLM ToolRegistry 注册 external-read。
没有 pending intent、模糊“可以”确认、额外 QQ、DNS、HTTP、真实 provider 或自动重试。
```

当前边界：

```text
ENABLE_AGENT_WEB 继续 false。
不注册 web_search、web_fetch 或 arbitrary URL 工具。
不发起真实外部请求。
不让 Main LLM 自由选择 external read。
不把外部内容写入 MemoryRAG、ProjectDocRAG 或长期记忆。
不新增额外 QQ、自动 retry、浏览器自动化、下载、Web 写操作或诊断自动修复。
P2.40b、P2.41 和 P2.42 继续未批准。
```

第一刀验证：

```text
external-read 纯策略：11 tests OK
现有 PolicyEngine：10 tests OK
external-search fake executor：9 tests OK
MainAgent bridge：54 tests OK
external-read 正式 work runtime：22 tests OK
全量回归：438 tests OK
Python AST：108 files OK
git diff --check：通过
第四刀严格入口聚焦：OwnerAgentWorkRuntime 25 tests、MainAgent bridge 54 tests、QQ 边界 12 tests OK
第四刀完成后全量回归：442 tests OK
```

## 2026-07-11 MainAgent 局部诊断按 view 采集收口

状态：本地实现和回归已完成，未新增阶段编号；尚未单独进行主人 QQ live。

本次完成：

```text
新增内部 docs/main-agent-command-capability-audit.md，逐项记录 /agent 路由、工具、provider、读写、LLM/RAG、副作用、输出和测试。
DiagnosticsGraph 从所有 view 共用全量节点序列，改为完整的 DiagnosticsView -> node sequence 映射。
FULL 保持原有 config/runtime/TTS/errors/memory/image cache 全量采集。
CONFIG 只经过 config 和 render。
VISION 只经过 config、image cache 和 render；既有视觉 formatter 继续负责视觉检查。
RECENT_ERRORS 只经过 errors 和 render。
IMAGE_CACHE 只经过 config、image cache 和 render。
MEMORY 只经过 memory stats 和 render，并把已采集 stats 传给 formatter，避免基础统计重复查询。
TTS 只经过 config、TTS health 和 render。
所有 DiagnosticsView 枚举成员都必须出现在显式映射中；新增参数化测试验证局部 view 不调用无关 handler。
```

边界：

```text
不改变 QQ 命令名称、确定性语义分类或现有输出格式。
不改变正式 system_diagnostics_report 的四个 scope。
不增加外部请求、深度探针、自动下钻、修复、写操作或额外 QQ。
formatter 自身已有的合法读取仍保留；node trace 不能被误读为 renderer 内部零读取。
```

测试：

```text
Graph 合同：21 tests OK
Graph runner：46 tests OK
诊断 formatter：10 tests OK
MainAgent bridge + QQ/RAG boundary + system diagnostics + formal work runtime：124 tests OK
全量回归：412 tests OK（补充 runner 建议后）
Python AST：104 files OK
git diff --check：通过
```

补充 live 现象与提示边界：

```text
主人确认 Ollama Model location 已指向 D:\OllamaModels，单实例、模型存在和显存余量均正常。
qwen2.5vl:3b 曾在真实图片后持续返回低质量重复内容；手动执行 ollama stop qwen2.5vl:3b 后，固定自检恢复为正常、返回 74 字，随后真实 QQ 图片和再次自检均成功。
/agent 查看视觉状态 和 /agent 完整排查图片识别问题 现在只在服务/模型可用且推理明确为低质量重复内容时提示“runner 可能处于异常状态”。
提示给出手动命令 ollama stop qwen2.5vl:3b，并明确只卸载模型、下次请求重新加载；诊断不自动执行、不自动重试。
超时、服务不可达、模型不存在等其他失败不会误用 runner 恢复建议。
相关聚焦回归 121 tests OK；全量回归 412 tests OK。
```

## v1.5 MemoryRAG embedding 自检

状态：已落地。`/记忆状态` 和 `/RAG状态` 现在会显示当前 MemoryRAG embedding 链路的真实自检结果。

本次完成：
```text
新增 check_embedding_provider，使用固定测试文本真实调用当前 embedding provider。
默认配置下该自检会验证 Ollama bge-m3 是否能返回可用向量。
自检请求沿用 MEMORY_RAG_EMBEDDING_DIMENSION 校验，并将诊断超时上限限制为 20 秒。
/记忆状态 新增 MemoryRAG 开关和 Embedding 自检摘要。
/RAG状态 新增 Embedding 自检详情。
自检成功时展示耗时和向量维度；失败时展示 provider 错误摘要。
```

边界：
```text
不读取用户聊天内容，不读取记忆正文。
不记录 embedding 向量，不写数据库，不重建索引。
不改变普通聊天 MemoryRAG 注入逻辑。
不改变 ProjectDocRAG 与 QQ 普通聊天的隔离边界。
bge-m3 失效时，普通聊天继续兜底运行，但 MemoryRAG / ProjectDocRAG 语义搜索不可用。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary tests.test_rag_units -v
Ran 24 tests OK
```

## v1.5 /视觉状态 推理自检

状态：已落地。`/视觉状态` 现在除了检查 Ollama `/api/tags` 和视觉模型是否存在，还会用一张内置的小型 PNG 测试图执行一次真实的 Ollama 视觉推理。

本次完成：
```text
新增 diagnostic_vision_image_base64，使用标准库生成 32x32 PNG 测试图，不依赖 Pillow/cv2。
新增 check_vision_inference，复用真实 Ollama /api/chat 视觉链路。
自检请求沿用 VISION_NUM_CTX，但将诊断超时上限限制为 45 秒，避免 /视觉状态 长时间卡死。
/视觉状态 新增“推理自检”行，成功时只展示耗时和返回字数。
如果 Ollama 服务异常、视觉模型不存在或视觉未开启，则跳过推理自检。
如果模型返回 @@@@@@ 这类低质量重复内容，自检会显示失败原因。
```

边界：
```text
不记录测试图的模型描述正文。
不读取用户图片，不记录图片 URL。
不改变普通聊天图片识别链路。
不改变 RootGraph 路由、聊天权限、图片缓存策略或视觉安全脱敏策略。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_diagnostics_units tests.test_vision_voice_units -v
Ran 24 tests OK
```

## 当前总览

```text
普通聊天：
  ChatAgent 路线保持稳定。
  MemoryRAG 已可用于普通聊天语义记忆召回。

/agent：
  QQ live 只读 MainAgent 已验证。
  真实 MainAgent LLM 可生成 ActionRequest。
  真实可见工具包括 dev_context、owner_read_command、agent_task_read、owner_write_command。
  隐藏的确定性控制面工具包括 agent_task_command，用于语义创建/取消任务、确认/拒绝审批、创建审批演练。
  ActionRequest tool_request 已改为 ToolRegistry-backed 校验。
  dev_context 返回后可进行 tool_result 二次总结；本地管理工具结果直接返回，避免角色卡语气污染。
  owner_read_command 可语义触发诊断、最近错误、多步只读图片识别/记忆检索排查、角色卡、角色卡列表、模型配置、访问控制、摘要、RAG、记忆检索、RAG索引详情、MainAgent观测、白名单等只读主人管理查询。
  agent_task_read 可语义触发任务列表、任务详情、审批列表、审批详情。
  agent_task_command 可语义触发任务/审批控制面操作，但不暴露给 LLM 工具契约。
  owner_write_command 已开放清空图片缓存、清空错误日志、选择角色卡、添加事实/偏好长期记忆、清空当前会话摘要、删除当前会话指定摘要、动态黑白名单修改；必须先生成审批，确认后才恢复执行。
  /agent 任务 <目标> 可创建 pending 任务记录。
  /agent 新增任务：<目标> 等明确本地别名可创建 pending 任务记录。
  /agent 把“目标”加入任务 等明确本地别名可创建 pending 任务记录。
  /agent 执行研发上下文任务：<问题> 仅允许主人私聊显式执行 development_context_report，并形成 running -> done / failed 生命周期。
  研发上下文任务在有召回且 MainAgent LLM 开启时返回固定六字段受限报告；不可用时确定性回退，任务记录只保存命中计数和总结方式。
  /agent 执行系统诊断任务 与 /agent 执行系统诊断任务：视觉 仅允许主人私聊显式执行 system_diagnostics_report/overview 或 vision；分别使用确定性六区分诊和首故障视觉状态链，任务记录只保存安全状态/层级/计数。
  /agent 任务状态 可查看当前会话任务。
  /agent 任务详情 <任务ID> 可查看任务和事件。
  /agent 取消任务 <任务ID> 可取消当前会话 pending 任务。
  /agent 审批演练 <目标> 可创建 dry-run 任务和审批请求，用于 QQ 侧实测 Route B。
  内部审批请求链路可生成 agent_approvals，并写入 approval_requested 任务事件。
  ToolPolicyCheck 适配层可将 require_approval 转为 approval_required 中断。
  /agent 审批状态 可查看当前会话审批记录。
  /agent 审批详情 <审批ID> 可查看审批详情。
  /agent 确认 <审批ID> 可确认当前会话 pending 审批；仅已注册且启用 approval_resume_enabled 的工具会受控恢复。
  /agent 拒绝 <审批ID> 可拒绝当前会话 pending 审批，不恢复执行。
  /agent 工具状态 / /agent 能力列表 可列出当前开放语义工具、风险等级、可见性、审批要求和示例命令。
  shell 越权请求已验证会拒绝。

项目文档 RAG：
ProjectDocRAG 不进入普通聊天。
ProjectDocRAG 只通过开发侧命令或 /agent owner 显式命令进入 dev_context。

RootGraph：
  v1.5 RootGraph 统一运行入口设计已新增：docs/v1.5-rootgraph-runtime.md。
  RootGraphRunner Phase 1 已补齐 normalize_event / load_actor_context / hard_policy_gate / route_intent / build_runtime_context / dispatch_capability / commit_side_effects / render_response 节点序列。
  RootGraph artifact 现在记录 policy、route、context、commit 和 root_graph 元数据。
  RootGraph 可稳定分发 MAIN_AGENT / CHAT / IGNORE；owner private MAIN_AGENT 放行，非 owner MAIN_AGENT 在 RootGraph 层提前拒绝，不进入 MainAgentGraph。
  handler 异常会被 RootGraph 捕获并写入 state.error 与 root_graph.error。
  本轮全量单测：$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  Ran 238 tests OK。
```

当前不开放：

```text
shell 工具
写文件工具
真实写文件工具（dry_run_write_file 只用于内部 dry-run 审批测试，不写文件，且不对 LLM 可见）
数据库写工具（除 /agent 任务固定命令、agent_task_command 控制面语义命令、内部审批记录链路，以及已审批的注册 owner_write_command 主人管理写命令）
额外 QQ 发送
Agent API
多步 agent loop
通用真实任务执行链路
通用真实审批恢复执行链路（目前仅 owner_write_command 已注册主人管理命令和 dry_run_write_file 可恢复）
长期记忆自动写入
角色卡自动修改
清空全部上下文或删除记忆
```

## v1.6 MainAgent 单步审批闭环第一步

状态：已落地第一步。目标是先修正 MainAgent “语义上答应了，但控制层没有真实执行或没有明确阻止”的体验问题。当前先以“删除当前会话指定摘要”为黄金路径收紧参数、审批和恢复执行边界。

本次完成：

```text
删除当前会话摘要必须携带数字 summary_id。
/agent 删除摘要 123 仍会进入 owner_write_command，并创建审批，不会立即执行。
/agent 删除摘要、/agent 删除摘要 最新、/agent 删除当前摘要 会进入 ask_owner，提示先查看摘要 ID；不会创建审批，也不会删除任何摘要。
真实 MainAgent LLM 如果生成缺少 summary_id 的 owner_write_command/delete_session_summary，也会在 ActionRequest 校验后以 need_argument 中断，不会进入审批。
owner_write_command executor 统一复用命令参数校验，缺 target/content/summary_id 的写命令不会被执行。
审批请求回复新增“尚未执行，等待主人确认”提示，避免把 approval_requested 误读为已执行。
非 dry-run 审批恢复回复新增“执行状态/执行结果”，让确认审批和真实工具结果分开可见。
/agent 同意、/agent 通过、/agent 执行吧、/agent 不同意 等裸确认/拒绝语义现在被解析为“隐式最新审批”引用；只有 QQ 入口解析到唯一 pending 审批时才会实际确认/拒绝，多个 pending 时要求指定审批 ID。
修复审批恢复执行中的 SQLite 锁问题：resume_agent_approval 现在先记录 tool_resume_started 并提交，再关闭 agent_tasks 写事务后执行真实工具，最后重新打开连接记录 tool_resume_finished 或 tool_resume_failed。
新增真实 session_summaries 删除恢复测试，覆盖 owner_write_command/delete_session_summary 在审批恢复阶段再次写数据库的场景，避免外层任务事务锁住摘要删除。
新增真实 long_term_memories 写入恢复测试，覆盖 owner_write_command/add_fact_memory 在审批恢复阶段再次写数据库的场景。
补齐 owner_write_command 语义预检：选择角色卡缺 target、添加事实/偏好记忆缺 content、动态名单修改缺数字 target 时直接 ask_owner，不进入 dev_context、LLM 猜测或审批创建。
已知禁止批量写意图会直接停止：清空全部摘要、清空全部上下文、删除长期记忆；不会创建审批，也不会执行清理或删除。
owner_read_command 在只读路由前先识别写意图，避免“使用角色卡”等写请求被误判成查看角色卡。
任务/审批边界文案更新为“不执行任意 shell、任意真实写文件或未注册数据库写入”，和已审批注册写工具的真实执行能力保持一致。
修复角色卡列表枚举：`README.md` 和 `*.example.md` 这类说明/模板文件不再作为可选角色卡展示，也不能被 `/选择角色卡` 选中。
本地验证当前 `prompts/persona-cards/` 只展示 `aike`、`moyan` 两张真实角色卡。
QQ live 已验证：/agent 删除摘要 <ID> -> /agent 确认 最新 -> 当前会话摘要实际删除成功。
```

边界：

```text
普通聊天里的“同意”不触发 MainAgent；仍必须走 /agent 入口。
缺少摘要 ID 时不猜“最新摘要”或“第二条摘要”。
delete_session_summary 仍只作用于当前会话，不跨会话删除。
owner_write_command 仍必须先审批，确认后才恢复执行。
不开放 shell、任意文件写入、未注册数据库写入、多步写操作自动执行、删除长期记忆、清空全部上下文或清空全部摘要。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge tests.test_persistence_units -v
Ran 64 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary tests.test_graph_runners -v
Ran 53 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 268 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 46 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 18 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_operation_units tests.test_memory_rag_qq_boundary -v
Ran 22 tests OK
```

## v1.6 MainAgent 多步只读诊断第一步

状态：已落地第一条 P1 多步只读诊断命令。目标是让 MainAgent 不只是调用单个状态页，而是能为常见故障读取多个只读证据源并给出可验证的判断。

本次完成：

```text
新增 owner_read_command/vision_troubleshoot。
/agent 完整排查图片识别问题 和 /agent 排查识图为什么失败 会语义路由到 vision_troubleshoot。
广义 “诊断一下 Ollama / 看一下视觉和记忆状态” 仍保持 ops_health 聚合诊断；单独看视觉状态仍可走 vision_status。
QQ 执行 vision_troubleshoot 时会依次读取：
  1. DiagnosticsGraph 视觉/Ollama 状态
  2. DiagnosticsGraph 图片缓存状态
  3. 最近错误日志
  4. RootGraph 最近聊天观测
  5. MainAgent 最近观测
返回内容包含步骤、初步判断、视觉/Ollama 证据、图片缓存证据、最近错误证据、RootGraph 证据和 MainAgent 证据。
回复中明确只读保证：未清理缓存、未修改配置、未写入数据库、未发送额外 QQ 消息。
视觉排查判断逻辑移入 diagnostics 纯函数，避免 “Ollama 服务：正常” 被误判为异常。
RootGraph Vision detail 会按 errors / low_quality 的正数计数判断，不会因为同一批观测里同时存在 0 和非 0 而漏报。
```

边界：

```text
只读多步诊断不等于多步任务执行。
不开放清空图片缓存、修改视觉配置、拉取模型、重启 Ollama 或发送额外 QQ 消息。
不读取新的用户图片，不下载外部网络资源；视觉自检只复用 DiagnosticsGraph 的 Ollama 状态和内置测试图。
普通聊天仍不会触发 MainAgent 诊断，必须走 /agent 主人私聊入口。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_diagnostics_units -v
Ran 5 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 46 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 9 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 272 tests OK
```

## v1.6 MainAgent 多步只读诊断第二步

状态：已落地第二条 P1 多步只读诊断命令，复用图片识别排查的报告形态，补上 MemoryRAG/Embedding/索引链路的主人侧可观测性。

本次完成：

```text
新增 owner_read_command/memory_rag_troubleshoot。
/agent 完整排查记忆检索问题 和 /agent 排查 MemoryRAG 为什么没有召回 会语义路由到 memory_rag_troubleshoot。
显式 /agent 记忆检索 <查询内容> 仍保持 memory_retrieval，不会被排查命令抢走。
同时包含图片和 RAG 的广义问题，例如“最近图片和 RAG 有没有问题”，仍保持 ops_health 聚合诊断。
QQ 执行 memory_rag_troubleshoot 时会依次读取：
  1. MemoryRAG/Embedding 状态和 embedding 自检
  2. RAG 索引详情
  3. 最近错误日志
  4. RootGraph MemoryRAG 最近观测
  5. MainAgent 最近观测
返回内容包含步骤、初步判断、MemoryRAG/Embedding 证据、RAG 索引证据、最近错误证据、RootGraph 证据和 MainAgent 证据。
回复中明确只读保证：未重建索引、未写入记忆、未删除文档、未修改配置、未写入数据库、未发送额外 QQ 消息。
MemoryRAG 排查判断逻辑移入 diagnostics 纯函数，覆盖 RAG 关闭、聊天注入关闭、embedding 自检失败、索引为空、向量为空、待索引、RootGraph commit 错误、最近召回 0 命中和最近错误日志非空。
```

边界：

```text
只读多步诊断不等于自动修复。
不开放重建索引、写入长期记忆、删除 RAG 文档、修改 embedding 配置、重启 Ollama 或发送额外 QQ 消息。
该命令会执行现有 MemoryRAG 状态自检；embedding 自检只使用固定测试文本，不读取用户记忆正文。
普通聊天仍不会触发 MainAgent 诊断，必须走 /agent 主人私聊入口。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_diagnostics_units -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 46 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 276 tests OK
```

## v1.6 Ollama 启动前自愈

状态：已落地本地启动脚本层面的 Ollama ensure，解决频繁出现的 `WinError 10061` / 11434 未监听问题。

本次完成：

```text
新增 scripts/ensure-ollama.ps1。
scripts/start.ps1 默认先调用 ensure-ollama，再启动 bot.py。
ensure-ollama 会读取当前进程环境变量和 .env，判断是否需要本地 Ollama：
  ENABLE_VISION=true
  或 ENABLE_MEMORY_RAG / ENABLE_PROJECT_DOC_RAG=true 且 MEMORY_RAG_EMBEDDING_PROVIDER=ollama
如果不需要 Ollama，则直接跳过。
如果需要 Ollama，则检查 http://127.0.0.1:11434/api/tags。
检查必需模型：
  视觉：VISION_MODEL，默认 qwen2.5vl:3b
  MemoryRAG/ProjectDocRAG：MEMORY_RAG_EMBEDDING_MODEL，默认 bge-m3
如果 11434 未监听、/api/tags 不可用或必需模型不可见，且目标是本地 11434，则调用 scripts/start-ollama-vision.ps1。
start-ollama-vision 会用 OLLAMA_MODELS=D:\OllamaModels 重新拉起 ollama serve。
支持临时跳过：.\scripts\start.ps1 -SkipOllamaEnsure 或设置 SKIP_OLLAMA_ENSURE=1。
支持只检查不启动：.\scripts\ensure-ollama.ps1 -NoStart。
```

边界：

```text
不在 MainAgent/ChatAgent 运行时中自动启动外部进程。
不在 QQ 消息处理过程中拉起 Ollama。
只改本地启动脚本，保持运行时边界清晰。
如果配置为远程或非 11434 Ollama 地址，ensure 只检查，不尝试启动本地服务。
```

## v1.6 MainAgent 任务协作第一步

状态：已落地 P1.3 小范围任务协作增强。目标是让 `/agent 下一步` 从“查开发上下文”转为“只读任务协作台”，优先告诉主人当前卡点和最该处理的一步。

本次完成：

```text
新增 agent_task_read/next_step 只读命令。
/agent 下一步、/agent 现在卡在哪、/agent 接下来该做什么、/agent 有什么待我确认 会走任务协作摘要，不再默认进入 dev_context。
协作摘要读取当前会话 agent_tasks / agent_task_events / agent_approvals。
建议优先级：
  1. 有待审批：提示查看审批详情，并确认或拒绝具体审批。
  2. 有失败任务：提示查看失败任务详情。
  3. 有待处理任务但无审批：提示查看任务详情，并说明当前版本不会自动多步执行普通任务。
  4. 无待处理事项：提示可创建任务或显式 /agent 查 <问题>。
协作摘要会列出待主人确认项和近期任务，并显示最近事件摘要。
```

边界：

```text
这是只读协作查询，不创建任务、不取消任务、不确认/拒绝审批、不恢复工具。
普通聊天仍不会触发 MainAgent 任务协作。
/agent-debug 下一步 仍可走原始 dev_context 调试路径；普通 /agent 下一步 走任务协作摘要。
不开放多步自动执行任务、自动修复失败任务、shell、任意文件写入或未注册数据库写入。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 278 tests OK
```

## v1.6 MainAgent 任务详情卡第一步

状态：已落地 P1.4 小范围任务协作增强。目标是让任务和审批不再是两张割裂的表，而是在重启、中断或切换工作后，主人能从任意一张详情卡看懂当前接续点。

本次完成：

```text
任务详情从普通事件列表升级为任务详情卡。
/agent 任务详情 <任务ID> / 最新任务详情 会展示：
  任务状态、目标、结果、创建/更新时间
  当前建议下一步
  关联审批摘要
  任务事件列表
  /agent 下一步 协作入口
审批详情从普通审批记录升级为审批详情卡。
/agent 审批详情 <审批ID> / 最新审批详情 会展示：
  审批状态、工具、风险、原因、输入摘要
  关联任务摘要
  关联任务最近事件
  当前建议下一步
新增 list_agent_approvals(task_id=...)，用于只读查询某个任务的关联审批。
固定 /agent 入口和语义 agent_task_read 入口都接入详情卡。
```

边界：

```text
详情卡仍是只读协作查询，不创建任务、不取消任务、不确认/拒绝审批、不恢复工具。
详情卡只读取当前会话、当前用户范围内的 agent_tasks / agent_task_events / agent_approvals。
普通聊天仍不会触发 MainAgent 任务协作。
不开放多步自动执行任务、自动修复失败任务、shell、任意文件写入或未注册数据库写入。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 20 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 279 tests OK
```

## v1.6 MainAgent 任务工作台第一步

状态：已落地 P1.5 任务协作 read-model 增强。目标是让 `/agent 下一步` 和新工作台视图从“近期任务列表”升级成更接近 Owner Console 后端读模型的分区摘要。

本次完成：

```text
新增 AGENT_TASK_COMMAND_WORKBENCH / workbench 只读命令。
/agent 任务工作台、/agent 任务看板、/agent 协作台 会展示 Agent 任务工作台。
语义 MainAgent 任务读工具也能识别“看看任务工作台”“打开任务看板”等说法，路由到 agent_task_read/workbench。
/agent 下一步 继续保留最高优先级建议，同时新增工作台概览分区。
工作台分区包括：
  待主人确认
  失败任务
  待处理任务
  可复盘/已完成
每条任务行包含任务 ID、状态、标题、最近事件和 /agent 任务详情入口。
待审批任务会在任务行上标出待审批编号。
待审批行包含 /agent 审批详情、/agent 确认、/agent 拒绝入口。
工作台待处理分区现在优先显示有待审批的任务；没有待审批的普通 pending 任务会作为“普通待处理/积压”默认折叠为计数，避免旧测试任务刷屏。
可复盘/已完成分区默认只展示最近少量记录，其余折叠为计数，避免历史执行结果刷屏。
折叠只是只读降噪，不会批量取消或修改旧任务。
```

边界：

```text
任务工作台是只读查询，不创建任务、不取消任务、不确认/拒绝审批、不恢复工具。
只读取当前会话、当前用户范围内的 agent_tasks / agent_task_events / agent_approvals。
普通聊天仍不会触发 MainAgent 任务协作。
不开放多步自动执行任务、自动修复失败任务、shell、任意文件写入或未注册数据库写入。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 21 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 280 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 21 tests OK
```

## v1.6 MainAgent Owner Runtime service 解耦第一步

状态：已落地 P2.1 代码层 service 解耦。目标是先让主人侧任务/审批 runtime 脱离 QQ `MessageEvent`，为后续 Runtime service、Owner Console 后端读模型和更清晰的适配层边界铺路。

本次完成：

```text
新增 src/plugins/ai_chat/owner_agent_runtime.py。
新增 OwnerAgentContext(session_key, user_id)，作为主人侧任务/审批 runtime 的最小上下文。
将任务状态、任务详情、任务工作台、审批详情、确认/拒绝、审批演练和审批请求创建逻辑从 QQ adapter 抽到 owner_agent_runtime service。
src/plugins/ai_chat/__init__.py 现在只负责 NoneBot/QQ 事件接入、owner 鉴权、session/user 上下文转换、RootGraph 调度和回复发送。
run_main_agent_task_command、语义 agent_task_read、语义 agent_task_command、owner_write 审批请求创建均改为委托 service。
新增 service 层单测，验证 OwnerAgentContext 可在没有 QQ event 的情况下读取工作台、任务详情和审批详情。
更新 QQ 边界测试，约束 __init__.py 继续保持 adapter 形态，不回退到直接承载任务/审批 runtime。
docs/runbook.md 补充 P2.1 边界说明。
```

边界：

```text
这是代码层解耦，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent 命令行为。
不新增 shell、任意文件写入、未注册数据库写入或多步写执行能力。
owner_write_command 仍必须审批，确认后仅已注册且 approval_resume_enabled=true 的工具会受控恢复。
普通聊天仍不会触发 MainAgent 任务/审批 runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 22 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 47 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 281 tests OK
```

## v1.6 MainAgent owner_read runtime service 解耦第一步

状态：已落地 P2.2 代码层 service 解耦。目标是继续把 `src/plugins/ai_chat/__init__.py` 从“承载业务 runtime”收窄为 QQ/NoneBot adapter，让主人只读管理命令分发可以被后续 Runtime service / Owner Console 后端复用。

本次完成：

```text
新增 src/plugins/ai_chat/owner_read_runtime.py。
新增 OwnerReadRuntime 依赖注入对象，用于承载 DiagnosticsGraph、MemoryRAG、MemoryAdmin、角色卡、名单和观测等只读 provider。
新增 run_owner_read_command(runtime, command, context)，集中分发 owner_read_command。
src/plugins/ai_chat/__init__.py 新增 owner_read_runtime_from_event(event)，只负责把 QQ event 绑定到现有只读读取函数。
run_main_agent_qq_command 内部的 execute_owner_read_command 现在只委托 owner_read_runtime service。
owner_read_runtime 单测验证不依赖 QQ event，也能分发 bot_status、ops_health、config_status、memory_retrieval、summary_status 和 view_persona。
QQ 边界测试改为检查 owner_read_runtime.py 承载只读命令分发，__init__.py 继续保留底层 QQ/event 绑定和诊断证据读取。
```

边界：

```text
这是代码层解耦，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent owner_read_command 行为。
不新增 shell、任意文件写入、未注册数据库写入或多步写执行能力。
owner_read_runtime 只做只读命令路由，不直接写数据库、不发额外 QQ 消息。
普通聊天仍不会触发 MainAgent owner_read runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 48 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 282 tests OK
```

## v1.6 MainAgent owner_write runtime service 解耦第一步

状态：已落地 P2.3 代码层 service 解耦。目标是把已审批恢复会调用的主人管理写执行器也从 QQ adapter 中抽出，让 task/read/write 三块 MainAgent owner runtime 都具备 service 边界。

本次完成：

```text
新增 src/plugins/ai_chat/owner_write_runtime.py。
新增 OwnerWriteRuntime 依赖注入对象，用于绑定现有受控写函数。
新增 run_owner_write_command(runtime, command, context)，集中执行已审批 owner_write_command。
src/plugins/ai_chat/__init__.py 新增 owner_write_runtime()，只负责把现有 clear_image_cache、clear_error_log、select_role_card、add_manual_memory、clear_session_summaries、delete_session_summary、动态名单 add/remove 等函数绑定给 service。
execute_owner_write_command 现在只委托 owner_write_runtime service。
owner_write_runtime 单测验证不依赖 QQ event，也能执行 clear_image_cache、allow_group、select_persona、add_fact_memory、clear_session_summaries 和 delete_session_summary。
QQ 边界测试改为检查 owner_write_runtime.py 承载写命令分发，__init__.py 不再承载 access_operations 分发表。
```

边界：

```text
这是代码层解耦，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent owner_write_command 行为。
不新增写工具。
不绕过审批；owner_write_command 仍必须先生成审批，确认后仅通过已注册且 approval_resume_enabled=true 的工具恢复。
不开放 shell、任意文件写入、未注册数据库写入、删除长期记忆、清空全部摘要或清空全部上下文。
普通聊天仍不会触发 MainAgent owner_write runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 49 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 22 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 283 tests OK
```

## v1.6 MainAgent owner runtime factory 总装层

状态：已落地 P2.4 代码层 service 总装。目标是在 task/read/write 三块 runtime 都抽离后，再把 QQ adapter 中散落的 runtime 绑定点收敛为一个 factory，为后续 Runtime service / Web Owner Console 复用同一套 owner runtime 装配铺路。

本次完成：

```text
新增 src/plugins/ai_chat/owner_runtime_factory.py。
新增 OwnerRuntimeFactory，集中组装 OwnerAgentContext、OwnerReadRuntime 和 OwnerWriteRuntime。
OwnerRuntimeFactory 提供 run_task_command、format_task_read、execute_task_command、create_approval_request、run_read_command 和 run_write_command。
src/plugins/ai_chat/__init__.py 移除 owner_agent_context_from_event、owner_read_runtime_from_event 和 owner_write_runtime 三个分散 helper。
QQ adapter 现在只保留 owner_runtime_factory() 依赖绑定点，/agent 入口通过 factory 委托 task/read/write runtime。
新增 factory 单测，验证不依赖 QQ event 也能组装 owner context、owner_read 和 owner_write。
QQ 边界测试改为约束 __init__.py 只挂 OwnerRuntimeFactory，三块 runtime 细节由 owner_runtime_factory.py 引用。
```

边界：

```text
这是代码层总装整理，不是独立进程。
不新增 HTTP API。
不新增 Web Owner Console。
不改数据库 schema。
不改变现有 /agent task/read/write 行为。
不新增工具，不扩大审批恢复范围。
不开放 shell、任意文件写入、未注册数据库写入或多步写执行能力。
普通聊天仍不会触发 MainAgent owner runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 22 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 284 tests OK
```

## v1.6 Runtime service 解耦审计

状态：已落地 P2.5 文档审计。目标是在 P2.1-P2.4 把 MainAgent owner task/read/write runtime 抽离并总装后，先暂停继续大拆，明确当前边界、QQ live 回归点和 `src/plugins/ai_chat/__init__.py` 剩余职责。

本次完成：

```text
新增 docs/v1.6-runtime-service-audit.md。
记录当前 owner runtime 分层：
  __init__.py
  owner_runtime_factory.py
  owner_agent_runtime.py
  owner_read_runtime.py
  owner_write_runtime.py

记录本轮仍保持的行为边界：
  不拆独立进程
  不新增 HTTP API
  不新增 Web Owner Console
  不改 DB schema
  不新增工具
  不扩大审批恢复范围
  普通聊天仍不会触发 MainAgent owner runtime

记录已观察到的 QQ live 路径：
  /agent 访问控制
  /agent 删除摘要 41
  /agent 确认 19
  /agent 确认 最新

审计 __init__.py 剩余职责：
  QQ adapter 必须保留
  Chat runtime 仍然很重
  Diagnostics / MemoryRAG / MemoryAdmin 可继续 service 化
  Voice / Notification 可独立拆但不是当前瓶颈

给出下一步建议：
  优先 P2.6 Web Owner Console read-model 设计，不写前端、不接 HTTP
  备选 P2.6-alt Diagnostics runtime service 解耦
  暂不建议立刻拆 Chat runtime
```

边界：

```text
本步只做审计和文档，不改变运行时代码。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增测试依赖。
```

## v1.6 Web Owner Console read-model 设计

状态：已落地 P2.6 设计文档。目标是在 MainAgent owner runtime service 解耦后，先定义未来 Web Owner Console 的只读页面和结构化 read model，而不是直接写前端或接 HTTP。

本次完成：

```text
新增 docs/web-owner-console-read-model-design.md。

明确 Web Owner Console v0 定位：
  只做 read-model 设计
  不写前端
  不接 HTTP
  不做登录/鉴权
  不新增数据库表
  不做 Web 写操作

梳理现有 QQ 文本输出后端形态：
  lines provider -> str
  Graph execution reply_text -> str
  AgentTask / AgentApproval -> QQ formatter -> str

确定 Web read model 不应长期复用 QQ 文本输出：
  不解析 QQ 文案
  不把文案当接口契约
  任务/审批优先复用 AgentTask / AgentTaskEvent / AgentApproval 等结构化来源

页面范围分层：
  v0 必须清楚：Dashboard、Tasks、Task Detail、Approvals、Approval Detail、Diagnostics、Access Control
  v0 浅层快照：Memory、Settings

定义 read model 草案：
  OwnerConsoleOverview
  OwnerConsoleTaskList
  OwnerConsoleTaskDetail
  OwnerConsoleApprovalList
  OwnerConsoleApprovalDetail
  OwnerConsoleHealthSnapshot
  OwnerConsoleMemorySnapshot
  OwnerConsoleAccessControlSnapshot
  OwnerConsoleRuntimeBoundary

写清未来升级路线：
  v0 全只读
  v0.1 只读 actionability metadata
  v1 如支持审批决定，也必须复用现有 approval resume / owner_write_runtime 链路
```

稀土掘金文章：

```text
新增 docs/juejin/14-web-owner-console-read-model-design.md。
主题：为什么 Web Owner Console 不直接复用 QQ 文本输出，以及为什么要先设计结构化 DTO。
```

边界：

```text
本步只做设计和文档，不改变运行时代码。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增 HTTP API。
不新增 Web 前端。
不新增工具能力。
不新增数据库表。
不执行测试；本次为纯文档变更。
```

## v1.6 Owner Console Task / Approval read-model builder

状态：已落地 P2.7 第一刀。目标是把 P2.6 中“不要复用 QQ 文本、先做结构化 DTO”的设计落到任务/审批只读 builder 上，验证未来 Web Owner Console 可以不依赖 QQ formatter 读取结构化数据。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_read_models.py。

第一批结构化 DTO：
  OwnerConsoleContext
  OwnerConsoleRuntimeBoundary
  OwnerConsoleTaskRow
  OwnerConsoleTaskEventRow
  OwnerConsoleTaskList
  OwnerConsoleTaskDetail
  OwnerConsoleApprovalActionability
  OwnerConsoleApprovalRow
  OwnerConsoleApprovalList
  OwnerConsoleApprovalDetail
  OwnerConsoleToolInputPreview

新增 src/plugins/ai_chat/owner_console_read_runtime.py。

第一批只读 builder：
  build_owner_console_task_list
  build_owner_console_task_detail
  build_owner_console_approval_list
  build_owner_console_approval_detail
  build_tool_input_preview

实现边界：
  使用 OwnerConsoleContext(session_key, user_id)，不依赖 QQ MessageEvent。
  任务/审批直接复用 AgentTask、AgentTaskEvent、AgentApproval 和持久化查询函数。
  不解析 QQ formatter 文本。
  不改变现有 /agent 输出。
  不接 HTTP。
  不写前端。
  不调用 owner_write_runtime。
```

actionability 第一版保持保守：

```text
pending approval:
  can_approve=true
  can_reject=true
  resume_enabled=None
  blocked_reason=""
  future_operation_only=true

非 pending approval:
  can_approve=false
  can_reject=false
  resume_enabled=None
  blocked_reason="approval is not pending"
  future_operation_only=true
```

其中 `resume_enabled=None` 表示 P2.7 尚未接入 tool registry，不声称该审批确认后一定可恢复工具。后续如进入 Web 操作阶段，必须由后端基于 tool registry 和 `approval_resume_enabled=true` 计算真实值。

安全预览：

```text
tool_input_json 只生成 preview。
支持敏感 key 脱敏：api_key、token、cookie、password、secret 等。
支持长度截断，避免把长内容或潜在隐私正文完整塞进 read model。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 4 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units.AgentTaskPersistenceUnitTests -v
Ran 17 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 288 tests OK
```

边界：

```text
本步只新增只读 read-model builder。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增 HTTP API。
不新增 Web 前端。
不新增数据库表。
不新增工具能力。
不开放 Web 写操作。
```

## v1.6 Owner Console Overview read-model builder

状态：已落地 P2.8 第一刀。目标是在 P2.7 Task / Approval 结构化 read model 的基础上，新增 Dashboard / Overview 的轻量只读聚合模型，为未来 Web Owner Console 首页做准备。

本次完成：

```text
agent_tasks.py 新增只读计数 helper：
  count_agent_tasks
  count_agent_approvals

owner_console_read_models.py 新增：
  OwnerConsoleOverviewCounters
  OwnerConsoleOverview

owner_console_read_runtime.py 新增：
  build_owner_console_overview

Overview 当前聚合：
  pending_tasks
  failed_tasks
  pending_approvals
  recent_tasks
  pending_approvals rows
  runtime boundary
```

本步刻意不做深层 Dashboard：

```text
不接 Diagnostics 深层结构。
不接 Access Control 深层结构。
不接 Memory / Settings snapshot。
不接 HTTP。
不写前端。
```

原因是 P2.8 只验证 Dashboard 可以复用 P2.7 的结构化 rows 和精确计数，避免第一版 overview 同时牵扯诊断、访问控制、记忆和设置而膨胀。

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 5 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units.AgentTaskPersistenceUnitTests -v
Ran 17 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 289 tests OK
```

边界：

```text
本步只新增只读 overview builder。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
不新增 HTTP API。
不新增 Web 前端。
不新增数据库表。
不新增工具能力。
不开放 Web 写操作。
```

## v1.6 Owner Console Access / Settings snapshot

状态：已落地 P2.9 第一刀。目标是在 Task / Approval / Overview 之后，继续补齐未来 Owner Console 的浅层配置类 read model，先做 Access Control 和 Settings，只读、结构化、脱敏，不接 HTTP 或前端。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleAccessList
  OwnerConsoleAccessControlSnapshot
  OwnerConsoleModelConfigSnapshot
  OwnerConsoleRoleCardRow
  OwnerConsoleSettingsSnapshot

owner_console_read_runtime.py 新增：
  build_owner_console_access_control_snapshot
  build_owner_console_settings_snapshot
```

Access Control snapshot 当前包含：

```text
owner_configured
private_chat_enabled
group_chat_enabled
unknown_private_policy
private_whitelist
group_whitelist
user_blacklist
runtime boundary
```

Settings snapshot 当前包含：

```text
chat_model
main_agent_model
embedding
role_cards
active_role_card_key
feature_flags
runtime boundary
```

安全处理：

```text
base_url 使用 redacted_base_url 脱敏，不保留 userinfo/query/token。
API Key 只展示 api_key_configured 布尔值，不暴露原文。
访问名单支持 item_limit 截断，避免一次性把大量名单项塞进 read model。
Settings builder 由调用方传入 role_cards 和 active_role_card_key，不读取角色卡正文。
```

边界：

```text
不 import access.py，避免引入 NoneBot MessageEvent。
不依赖 QQ adapter。
不读取角色卡正文。
不修改名单。
不切换角色卡。
不修改模型配置。
不写 .env。
不接 HTTP。
不写前端。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 7 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units.AgentTaskPersistenceUnitTests -v
Ran 17 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_legacy_business_rules.AccessRuleTests tests.test_legacy_business_rules.AccessStoreTests tests.test_config_loading -v
Ran 11 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 291 tests OK
```

附记：

```text
本轮短暂验证过独立 Web 入口不能直接 import src.plugins.ai_chat.* 包路径，
因为 Python 会先执行 QQ 插件包 __init__.py 并触发插件初始化副作用。
后续如做 FastAPI，只能作为薄 Web adapter 接 read-model 层，不能直接 import QQ adapter。
```

## v1.6 Owner Console Diagnostics snapshot

状态：已落地 P2.10 第一刀。目标是在不重构 DiagnosticsGraph、不接 HTTP、不写前端的前提下，给未来 Owner Console 的 Diagnostics 页面提供浅层结构化 read model。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleTextSnapshotSection
  OwnerConsoleObservationSnapshot
  OwnerConsoleHealthSnapshot

owner_console_read_runtime.py 新增：
  build_owner_console_health_snapshot
```

Health snapshot 当前包含：

```text
bot_status
diagnostics
config
vision
image_cache
memory
tts
recent_errors
observations.main_agent
observations.root_graph
runtime boundary
```

设计取舍：

```text
P2.10 不强行把 DiagnosticsGraph 内部全部结构化。
现阶段允许 summary_text / display_lines 过渡。
builder 可接收 str、list[str]、tuple[str, ...]，也可接收带 result.reply_text / result.error 的 Graph execution-like 对象。
错误状态会转成 section.ok=false 和 section.error，不让前端猜文本。
```

边界：

```text
不 import diagnostics.py，避免引入 nonebot.get_driver / OpenAI 等诊断实现依赖。
不依赖 QQ adapter。
不改变 DiagnosticsGraph node sequence。
不改变 /诊断、/配置状态、/视觉状态、/最近错误 等 QQ 命令输出。
不接 HTTP。
不写前端。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 292 tests OK
```

## v1.6 Owner Console Memory snapshot

状态：已落地 P2.11 第一刀。目标是在不读取记忆正文、不触发检索、不重建索引的前提下，给未来 Owner Console 的 Memory 页面提供只读结构化快照。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleMemoryCounts
  OwnerConsoleMemoryContextPolicy
  OwnerConsoleMemoryRagSnapshot
  OwnerConsoleProjectDocRagSnapshot
  OwnerConsoleMemorySnapshot

owner_console_read_runtime.py 新增：
  build_owner_console_memory_snapshot
```

Memory snapshot 当前包含：

```text
counts:
  message_count
  session_count
  session_summary_count
  summarized_message_count
  manual_memory_count
  manual_memory_subject_count
  gap_scene_summary_count
  gap_scene_source_message_count
  rag_document_count
  rag_active_document_count
  rag_embedding_count

context_policy:
  memory_compression_enabled
  gap_scene_summaries_enabled
  long_term_memory_context_enabled
  max_context_messages
  max_stored_messages_per_session
  summary_keep_recent_messages
  summary_batch_messages
  summary_min_source_messages
  max_session_summaries_in_context
  max_gap_scene_summaries_in_context
  max_long_term_memories_in_context

memory_rag:
  enabled
  inject_in_chat
  owner_only_debug
  top_k
  min_score
  max_context_chars
  include_manual_facts
  include_manual_preferences
  include_session_summaries
  include_short_messages
  include_gap_scene_summaries

project_doc_rag:
  enabled
  explicit_agent_dev_context_only=true
  ordinary_chat_injection_allowed=false
  top_k
  min_score
  max_context_chars
```

设计取舍：

```text
builder 接收调用方传入的 stats dict，不直接 import memory.py、manual_memory.py、rag.documents 或 __init__.py。
这样未来 Web adapter 可以在 adapter 层选择调用现有 stats provider，
但 read-model 层仍保持纯粹、无 QQ adapter、无插件初始化副作用。

stats dict 中即使携带 content/summary 等额外字段，builder 也只取计数字段。
OwnerConsoleMemorySnapshot 明确标记：
  memory_content_exposed=false
  project_doc_content_exposed=false
  retrieval_executed=false
  index_rebuild_executed=false
```

边界：

```text
不暴露长期记忆正文。
不暴露会话摘要正文。
不暴露 gap scene 摘要正文。
不暴露 ProjectDocRAG 文档正文。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不写数据库。
不 import QQ 插件 __init__.py。
不接 HTTP。
不写前端。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 9 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 293 tests OK
```

## v1.6 Owner Console read-model facade

状态：已落地 P2.12 第一刀。目标是在 P2.7-P2.11 的分散 builder 之上收拢一个只读 facade，给未来 FastAPI / Web adapter 一个稳定调用边界，同时继续避免 HTTP、前端和 QQ adapter 依赖。

本次完成：

```text
owner_console_read_runtime.py 新增 OwnerConsoleReadRuntime。

OwnerConsoleReadRuntime 当前统一暴露：
  build_overview
  build_task_list
  build_task_detail
  build_approval_list
  build_approval_detail
  build_access_control_snapshot
  build_settings_snapshot
  build_memory_snapshot
  build_health_snapshot
```

依赖注入形式：

```text
config_provider
access_provider
role_cards_provider
active_role_card_key_provider
memory_stats_provider
manual_memory_stats_provider
gap_scene_stats_provider
rag_document_stats_provider
```

设计取舍：

```text
facade 不直接 import QQ 插件入口，不依赖 MessageEvent。
facade 不直接 import memory.py、manual_memory.py、rag.documents 或 diagnostics.py。
需要读取运行时状态时，由未来 adapter 在外层注入 provider。
这样 FastAPI 未来只需要作为薄 adapter：
  HTTP request / auth / serialization
  -> OwnerConsoleContext
  -> OwnerConsoleReadRuntime
  -> 结构化 DTO
而不是直接调用 QQ formatter 或拼接文本输出。
```

边界：

```text
本步只新增只读 facade。
不新增 HTTP API。
不写前端。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 294 tests OK
```

## v1.6 Owner Console serialization contract

状态：已落地 P2.13 第一刀。目标是在 read-model builder 和未来 FastAPI / Web adapter 之间定义一个稳定 JSON-safe 序列化契约，避免将来临时把 dataclass、QQ 文本或 Python 对象直接丢给 HTTP 层。

本次完成：

```text
owner_console_read_models.py 新增：
  OWNER_CONSOLE_SCHEMA_VERSION
  owner_console_to_jsonable
  owner_console_page_response

owner_console_read_runtime.py / OwnerConsoleReadRuntime 新增：
  serialize_model
  serialize_page
```

序列化契约：

```text
owner_console_to_jsonable:
  dataclass -> dict
  dict key -> str
  list / tuple -> list
  set / frozenset -> sorted list
  datetime / date -> isoformat string
  enum -> enum.value
  None 保留为 null
  bool / int / finite float / str 保留原类型
  non-finite float 拒绝
  其他未知 Python 对象拒绝

owner_console_page_response:
  schema_version
  page
  generated_at
  read_only=true
  http_api_enabled=false
  web_write_enabled=false
  data
```

设计取舍：

```text
序列化层不做 HTTP，不决定状态码，不做鉴权。
序列化层只保证 read model 可以安全进入 JSON response envelope。
敏感信息仍应在 builder 阶段脱敏；序列化层不负责猜测业务语义。
page response 明确 read_only=true / web_write_enabled=false，避免未来 Web adapter 把只读 DTO 误当可写接口。
```

边界：

```text
不新增 HTTP API。
不写前端。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 11 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 295 tests OK
```

## v1.6 Owner Console provider wiring audit

状态：已落地 P2.14 第一刀。目标是在不接 FastAPI、不写 Web adapter 的前提下，把未来 Web Owner Console 需要注入哪些 provider 固化成显式契约，并提供轻量 factory，避免以后在路由层散落临时 lambda 胶水。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleProviderWiringRow
  OwnerConsoleProviderWiringSnapshot

owner_console_read_runtime.py 新增：
  OwnerConsoleReadProviderSpec
  OWNER_CONSOLE_READ_PROVIDER_SPECS
  OwnerConsoleReadProviders
  build_owner_console_provider_wiring_snapshot
  create_owner_console_read_runtime
```

当前 provider 契约：

```text
required:
  config_provider
  access_provider

optional:
  role_cards_provider
  active_role_card_key_provider
  memory_stats_provider
  manual_memory_stats_provider
  gap_scene_stats_provider
  rag_document_stats_provider
```

optional provider fallback：

```text
role_cards_provider -> empty role card list
active_role_card_key_provider -> empty active role card key
memory_stats_provider -> zero memory counters
manual_memory_stats_provider -> zero manual memory counters
gap_scene_stats_provider -> zero gap scene counters
rag_document_stats_provider -> zero RAG document counters
```

Provider wiring snapshot 明确记录：

```text
runtime_ready
missing_required
provider_name
required
configured
read_model_area
owner_console_methods
fallback_behavior
direct_qq_dependency_allowed=false
write_side_effect_allowed=false
runtime boundary
```

设计取舍：

```text
audit 只检查 provider 是否注入，不调用 provider，不读取数据库。
factory 只把 provider bundle 转成 OwnerConsoleReadRuntime，不 import QQ 插件入口。
factory 不直接 import memory.py、manual_memory.py、rag.documents 或 diagnostics.py。
未来 FastAPI adapter 只需要组装 OwnerConsoleReadProviders，再调用 create_owner_console_read_runtime。
```

边界：

```text
不新增 HTTP API。
不写前端。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 12 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 296 tests OK
```

## v1.6 Owner Console read-only route contract

状态：已落地 P2.15 第一刀。目标是在 P2.12 facade、P2.13 serialization 和 P2.14 provider wiring 之后，把未来 Web Owner Console 的只读页面入口固化成显式 route contract，避免后续接 FastAPI 时临时把页面、DTO、runtime method 和参数散落在路由层。

本次完成：

```text
owner_console_read_models.py 新增：
  OwnerConsoleReadRouteRow
  OwnerConsoleReadRouteContractSnapshot

owner_console_read_runtime.py 新增：
  OwnerConsoleReadRouteSpec
  OWNER_CONSOLE_READ_ROUTE_SPECS
  build_owner_console_route_contract_snapshot

OwnerConsoleReadRuntime 新增：
  build_route_contract_snapshot
```

当前只读页面契约：

```text
dashboard:
  runtime_method=build_overview
  read_model=OwnerConsoleOverview
  requires_context=true
  optional_params=task_limit, approval_limit

tasks:
  runtime_method=build_task_list
  read_model=OwnerConsoleTaskList
  requires_context=true
  optional_params=status, limit

task_detail:
  runtime_method=build_task_detail
  read_model=OwnerConsoleTaskDetail
  requires_context=true
  required_params=task_id
  optional_params=event_limit, preview_limit

approvals:
  runtime_method=build_approval_list
  read_model=OwnerConsoleApprovalList
  requires_context=true
  optional_params=status, limit

approval_detail:
  runtime_method=build_approval_detail
  read_model=OwnerConsoleApprovalDetail
  requires_context=true
  required_params=approval_id
  optional_params=event_limit, preview_limit

diagnostics:
  runtime_method=build_health_snapshot
  read_model=OwnerConsoleHealthSnapshot
  requires_context=false

memory:
  runtime_method=build_memory_snapshot
  read_model=OwnerConsoleMemorySnapshot
  requires_context=false

access_control:
  runtime_method=build_access_control_snapshot
  read_model=OwnerConsoleAccessControlSnapshot
  requires_context=false

settings:
  runtime_method=build_settings_snapshot
  read_model=OwnerConsoleSettingsSnapshot
  requires_context=false
```

每一行 route contract 都显式标记：

```text
read_only=true
http_api_enabled=false
web_write_enabled=false
direct_qq_dependency_allowed=false
write_side_effect_allowed=false
```

设计取舍：

```text
P2.15 仍不是 HTTP API。
route contract 只是未来 Web adapter 的页面到 read-model facade 映射表。
它不决定 URL path、HTTP method、鉴权、状态码或前端布局。
真正接 FastAPI 时，路由层应只做薄适配：
  HTTP request / auth
  -> OwnerConsoleContext / 参数校验
  -> OwnerConsoleReadRuntime
  -> serialize_page

这样可以继续保持：
  Web 页面不解析 QQ 文本输出
  Web adapter 不 import QQ 插件 __init__.py
  Web adapter 不直接拼业务 DTO
  页面可用性由 read model / facade / route contract 三层共同约束
```

边界：

```text
不新增 HTTP API。
不写前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime -v
Ran 13 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 50 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.DiagnosticsGraphRunnerTests tests.test_diagnostics_units -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 297 tests OK
```

## v1.6 Owner Console RESTful HTTP adapter contract

状态：已落地 P2.16 第一刀。目标是在不接 FastAPI、不启动 HTTP 服务、不写前端的前提下，先把未来 Web Owner Console 的 HTTP 命名规范、RESTful 路径契约和统一响应 envelope 固化下来，避免后续接口路径和项目命名发散。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_http_models.py。

HTTP adapter DTO / 常量：
  OWNER_CONSOLE_HTTP_SCHEMA_VERSION = owner_console.http.v1
  OWNER_CONSOLE_HTTP_API_PREFIX = /api/v1/owner-console
  OWNER_CONSOLE_HTTP_ALLOWED_METHODS = GET
  OWNER_CONSOLE_HTTP_ERROR_CODES
  OwnerConsoleHttpError
  OwnerConsoleHttpRouteRow
  OwnerConsoleHttpRouteContractSnapshot

HTTP envelope helper：
  owner_console_http_success_response
  owner_console_http_error_response

新增 src/plugins/ai_chat/owner_console_http_contract.py。

RESTful route contract：
  OwnerConsoleHttpRouteSpec
  OWNER_CONSOLE_HTTP_ROUTE_SPECS
  build_owner_console_http_route_contract_snapshot
```

当前 HTTP namespace 固定为：

```text
/api/v1/owner-console
```

当前只读 RESTful 路径契约：

```text
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/diagnostics
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
```

命名规范：

```text
API prefix 统一为 /api/v1/owner-console。
HTTP path 静态段统一小写 kebab-case。
集合资源使用复数：tasks、approvals。
详情资源使用 /{id}：tasks/{task_id}、approvals/{approval_id}。
查询参数沿用 Python / DTO 的 snake_case。
第一版只允许 GET。
Dashboard 页面在 HTTP 资源层命名为 overview，避免把前端页面名和 API 资源名混在一起。
```

HTTP route contract 复用 P2.15 read route contract：

```text
overview -> read_page=dashboard -> build_overview -> OwnerConsoleOverview
tasks -> read_page=tasks -> build_task_list -> OwnerConsoleTaskList
tasks.detail -> read_page=task_detail -> build_task_detail -> OwnerConsoleTaskDetail
approvals -> read_page=approvals -> build_approval_list -> OwnerConsoleApprovalList
approvals.detail -> read_page=approval_detail -> build_approval_detail -> OwnerConsoleApprovalDetail
diagnostics -> read_page=diagnostics -> build_health_snapshot -> OwnerConsoleHealthSnapshot
memory -> read_page=memory -> build_memory_snapshot -> OwnerConsoleMemorySnapshot
access-control -> read_page=access_control -> build_access_control_snapshot -> OwnerConsoleAccessControlSnapshot
settings -> read_page=settings -> build_settings_snapshot -> OwnerConsoleSettingsSnapshot
routes -> build_route_contract_snapshot -> OwnerConsoleReadRouteContractSnapshot
```

HTTP success envelope：

```text
schema_version=owner_console.http.v1
read_model_schema_version=owner_console.read_model.v0
transport=http
api_prefix=/api/v1/owner-console
resource
generated_at
read_only=true
http_api_enabled=false
web_write_enabled=false
data
error=null
```

HTTP error envelope：

```text
schema_version=owner_console.http.v1
read_model_schema_version=owner_console.read_model.v0
transport=http
api_prefix=/api/v1/owner-console
resource
generated_at
read_only=true
http_api_enabled=false
web_write_enabled=false
data=null
error:
  code
  message
  details
```

第一版错误码固定为：

```text
bad_request
forbidden
not_found
provider_unavailable
internal_error
```

上下文策略先只进入契约，不开放实现：

```text
context_strategy=owner_private_session_from_config
context_override_allowed=false
write_routes_enabled=false
```

设计取舍：

```text
P2.16 仍不是 HTTP API。
本步不接 FastAPI，不启动服务，不注册 route。
http_api_enabled=false 表示当前只是 adapter contract，不声称真实 HTTP 已开放。
HTTP contract 只规定未来路径、方法、资源名、read model 映射和 envelope。
未来 FastAPI 层必须作为薄 adapter 服从该 contract：
  HTTP request / auth
  -> OwnerConsoleContext / 参数校验
  -> OwnerConsoleReadRuntime
  -> owner_console_http_success_response / owner_console_http_error_response
```

边界：

```text
不新增真实 HTTP API。
不写前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不 import QQ adapter。
不依赖 FastAPI。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_http_contract -v
Ran 3 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 300 tests OK
```

## v1.6 Owner Console FastAPI local smoke adapter

状态：已落地 P2.17 第一刀。目标是在 P2.16 RESTful HTTP contract 之后，验证 FastAPI 可以作为极薄的本地 HTTP adapter 承载 Owner Console 只读 contract，但仍不接全量页面、不写前端、不做登录鉴权、不开放 Web 写操作。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_fastapi_app.py。

新增：
  OWNER_CONSOLE_FASTAPI_APP_TITLE
  OWNER_CONSOLE_FASTAPI_SMOKE_ROUTES
  create_owner_console_fastapi_app
  app

当前 FastAPI smoke app 只注册：
  GET /healthz
  GET /api/v1/owner-console/routes
```

`GET /healthz` 返回本地 smoke 状态：

```text
ok=true
service=owner-console
schema_version=owner_console.http.v1
api_prefix=/api/v1/owner-console
read_only=true
http_api_enabled=true
web_write_enabled=false
enabled_routes:
  /healthz
  /api/v1/owner-console/routes
```

`GET /api/v1/owner-console/routes` 返回 P2.16 定义的 RESTful route contract，并通过 HTTP envelope 包装：

```text
schema_version=owner_console.http.v1
read_model_schema_version=owner_console.read_model.v0
transport=http
api_prefix=/api/v1/owner-console
resource=routes
read_only=true
http_api_enabled=true
web_write_enabled=false
data=OwnerConsoleHttpRouteContractSnapshot
error=null
```

设计取舍：

```text
FastAPI app factory 默认关闭 docs/redoc/openapi。
当前不注册 /api/v1/owner-console/tasks 等页面接口。
当前不接 OwnerConsoleContext。
当前不装配 OwnerConsoleReadProviders。
当前只证明 FastAPI 能按 P2.16 envelope 和路径规范返回 routes contract。

本步中 response envelope 的 http_api_enabled=true 只表示当前 smoke endpoint 已通过 HTTP 暴露。
route contract data 内仍由 P2.16 contract 记录未来完整页面接口的只读映射和边界。
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不接任务/审批/记忆/诊断等完整页面接口。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不 import QQ adapter。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 4 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 16 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 304 tests OK
```

## v1.6 Owner Console side-effect-free FastAPI launcher

状态：已落地 P2.18 第一刀。目标是在 P2.17 已有 FastAPI smoke app 后，补上独立启动边界：未来本地 Uvicorn 应从 side-effect-free launcher 进入，而不是直接 import `src.plugins.ai_chat.owner_console_fastapi_app`，避免 Python 先执行 QQ/NoneBot 插件入口 `src/plugins/ai_chat/__init__.py`。

本次完成：

```text
新增 src/owner_console_fastapi_launcher.py。

新增：
  OWNER_CONSOLE_FASTAPI_MODULE
  ensure_owner_console_import_boundary
  load_owner_console_fastapi_module
  create_app
  app
```

推荐未来本地启动入口：

```text
.\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090
```

设计取舍：

```text
launcher 位于 src/owner_console_fastapi_launcher.py，而不是 src/plugins/ai_chat 包内。
导入 launcher 只会执行 src/__init__.py 这个空包入口，不会正常 import src.plugins.ai_chat 包。
launcher 会先在 sys.modules 中建立轻量 package stub：
  src
  src.plugins
  src.plugins.ai_chat

然后再 import：
  src.plugins.ai_chat.owner_console_fastapi_app

这样 owner_console_fastapi_app 内部的相对导入仍然可用，
但不会执行 src/plugins/ai_chat/__init__.py。
```

安全保护：

```text
如果 src.plugins.ai_chat 已经以真实 __file__ 初始化，
launcher 会拒绝继续建立 side-effect-free import boundary。

这避免在同一进程已经加载 QQ 插件入口后，
又误以为当前 FastAPI app 仍处于无 QQ side effect 的独立边界。
```

当前 launcher 仍只承载 P2.17 smoke app：

```text
GET /healthz
GET /api/v1/owner-console/routes
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不新增数据库表。
不新增工具能力。
不接完整 tasks / approvals / memory / diagnostics 页面接口。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher -v
Ran 3 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 7 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 307 tests OK
```

## v1.6 Owner Console FastAPI overview endpoint

状态：已落地 P2.19 第一刀。目标是在 P2.18 已解决 side-effect-free launcher 后，接入第一个真正需要 `OwnerConsoleContext` 的只读 HTTP endpoint：`GET /api/v1/owner-console/overview`。本步仍不接完整页面、不做登录鉴权、不开放 Web 写操作。

本次完成：

```text
新增 src/plugins/ai_chat/owner_console_http_adapter.py。

新增：
  OwnerConsoleHttpAdapterError
  build_owner_console_context_from_config
  build_owner_console_access_from_config
  create_owner_console_http_read_runtime
  parse_owner_console_positive_int

更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/overview

更新 src/plugins/ai_chat/owner_console_http_contract.py：
  build_owner_console_http_route_contract_snapshot 支持 enabled_route_names。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
```

`GET /api/v1/owner-console/overview` 策略：

```text
从 load_config() 读取 BOT_OWNER_QQ。
构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

创建 OwnerConsoleReadRuntime：
  config_provider = 当前请求读取到的 config
  access_provider = merged_access(config.private_whitelist, config.group_whitelist, config.user_blacklist)

调用：
  runtime.build_overview(context, task_limit, approval_limit)

返回：
  owner_console_http_success_response(resource=overview, data=OwnerConsoleOverview)
```

查询参数：

```text
task_limit:
  默认 5
  必须为 >= 1 的整数

approval_limit:
  默认 5
  必须为 >= 1 的整数
```

错误处理：

```text
BOT_OWNER_QQ 未配置：
  HTTP 403
  error.code = forbidden
  error.details.config_key = BOT_OWNER_QQ

task_limit / approval_limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = 对应字段名

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
直接调用 build_owner_console_http_route_contract_snapshot() 时仍保持设计态：
  http_api_enabled=false

FastAPI /routes endpoint 返回时传入 enabled_route_names：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks / approvals / memory / diagnostics / settings 等仍为 false
```

设计取舍：

```text
第一版没有登录系统，因此不允许 query 参数覆盖 user_id 或 session_key。
context_override_allowed 仍为 false。
overview 只查询 owner 私聊上下文 private:{BOT_OWNER_QQ}。
本步只读取 agent_tasks / agent_approvals 的只读 read model。
access_provider 使用 merged_access，但 overview 当前不会读取访问名单；这是给后续 settings/access-control endpoint 复用的 adapter 边界。
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不接 tasks / approvals / memory / diagnostics / settings 等完整页面接口。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 6 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 309 tests OK
```

## v1.6 Owner Console FastAPI task / approval list endpoints

状态：已落地 P2.20 第一刀。目标是在 P2.19 接通 overview 后，继续接入两个只读列表资源：`GET /api/v1/owner-console/tasks` 和 `GET /api/v1/owner-console/approvals`。本步仍不接详情页、不做登录鉴权、不开放 Web 写操作。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/tasks
  GET /api/v1/owner-console/approvals

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  parse_owner_console_optional_status

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 tasks / approvals 列表读取、owner context 作用域、status 过滤、limit 校验和写方法拒绝。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 tasks / approvals。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/approvals
```

`GET /api/v1/owner-console/tasks` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

查询参数：
  status，可选，必须属于 agent task status 集合
  limit，可选，默认 20，必须为 >= 1 的整数

调用：
  runtime.build_task_list(context, status, limit)

返回：
  owner_console_http_success_response(resource=tasks, data=OwnerConsoleTaskList)
```

`GET /api/v1/owner-console/approvals` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

查询参数：
  status，可选，必须属于 agent approval status 集合
  limit，可选，默认 20，必须为 >= 1 的整数

调用：
  runtime.build_approval_list(context, status, limit)

返回：
  owner_console_http_success_response(resource=approvals, data=OwnerConsoleApprovalList)
```

错误处理：

```text
BOT_OWNER_QQ 未配置：
  HTTP 403
  error.code = forbidden

status 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = status
  error.details.allowed = 当前允许的 status 列表

limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = limit

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  approvals.http_api_enabled=true

仍未开放：
  task_detail.http_api_enabled=false
  approval_detail.http_api_enabled=false
  diagnostics.http_api_enabled=false
  memory.http_api_enabled=false
  access-control.http_api_enabled=false
  settings.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不接 task_detail / approval_detail 详情页。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 8 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 311 tests OK
```

## v1.6 Owner Console FastAPI task / approval detail endpoints

状态：已落地 P2.21 第一刀。目标是在 P2.20 列表端点之后，继续接入两个只读详情资源：`GET /api/v1/owner-console/tasks/{task_id}` 和 `GET /api/v1/owner-console/approvals/{approval_id}`。本步仍不做审批确认/拒绝，不接 Web 前端，不新增登录鉴权，也不改变 QQ / `/agent` 的任何运行时行为。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/tasks/{task_id}
  GET /api/v1/owner-console/approvals/{approval_id}

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  parse_owner_console_required_positive_int

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 task detail / approval detail 的 owner context 作用域、path id 校验、event_limit / preview_limit 校验、not_found envelope 和写方法拒绝。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 task detail / approval detail。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
```

`GET /api/v1/owner-console/tasks/{task_id}` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

路径参数：
  task_id，必填，必须为 >= 1 的整数

查询参数：
  event_limit，可选，默认 20，必须为 >= 1 的整数
  preview_limit，可选，默认 DEFAULT_PREVIEW_LIMIT，必须为 >= 1 的整数

调用：
  runtime.build_task_detail(context, task_id, event_limit, preview_limit)

返回：
  找到时 owner_console_http_success_response(resource=tasks, data=OwnerConsoleTaskDetail)
  不存在或不属于 owner 私聊上下文时 HTTP 404 / error.code=not_found
```

`GET /api/v1/owner-console/approvals/{approval_id}` 策略：

```text
从 BOT_OWNER_QQ 构造 OwnerConsoleContext：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

路径参数：
  approval_id，必填，必须为 >= 1 的整数

查询参数：
  event_limit，可选，默认 5，必须为 >= 1 的整数
  preview_limit，可选，默认 DEFAULT_PREVIEW_LIMIT，必须为 >= 1 的整数

调用：
  runtime.build_approval_detail(context, approval_id, event_limit, preview_limit)

返回：
  找到时 owner_console_http_success_response(resource=approvals, data=OwnerConsoleApprovalDetail)
  不存在或不属于 owner 私聊上下文时 HTTP 404 / error.code=not_found
```

错误处理：

```text
BOT_OWNER_QQ 未配置：
  HTTP 403
  error.code = forbidden

task_id / approval_id 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = task_id 或 approval_id

event_limit / preview_limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = event_limit 或 preview_limit

详情不存在或不属于 owner 私聊上下文：
  HTTP 404
  error.code = not_found

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true

仍未开放：
  diagnostics.http_api_enabled=false
  memory.http_api_enabled=false
  access-control.http_api_enabled=false
  settings.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 10 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 313 tests OK
```

## v1.6 Owner Console FastAPI access / settings endpoints

状态：已落地 P2.22 第一刀。目标是在 P2.21 接通 task / approval 详情后，继续开放两个低风险只读页面资源：`GET /api/v1/owner-console/access-control` 和 `GET /api/v1/owner-console/settings`。本步仍不接 Web 前端、不新增登录鉴权、不开放写操作，也不执行 MemoryRAG / Diagnostics 运行态读取。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/access-control
  GET /api/v1/owner-console/settings

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  HTTP read runtime 注入只读 role card providers：
    list_role_cards
    active_role_card -> active key

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 access-control / settings 只读 envelope、配置脱敏、访问名单展示、item_limit 校验和无 owner context 读取。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 access-control / settings。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
```

`GET /api/v1/owner-console/access-control` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取访问控制配置：
  BOT_OWNER_QQ
  ENABLE_PRIVATE_CHAT
  ENABLE_GROUP_CHAT
  ALLOW_UNKNOWN_PRIVATE_CHAT
  PRIVATE_WHITELIST
  GROUP_WHITELIST
  USER_BLACKLIST

通过 build_owner_console_access_from_config(config) 合并 env 与 data/access.json 的只读访问名单。

查询参数：
  item_limit，可选，默认 50，必须为 >= 1 的整数

调用：
  runtime.build_access_control_snapshot(item_limit=item_limit)

返回：
  owner_console_http_success_response(resource=access-control, data=OwnerConsoleAccessControlSnapshot)
```

`GET /api/v1/owner-console/settings` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取模型、RAG、MainAgent、TTS、Web/shell/write capability flags。

HTTP read runtime 注入只读 role card provider：
  role_cards_provider = list_role_cards
  active_role_card_key_provider = active_role_card().key 或空字符串

调用：
  runtime.build_settings_snapshot()

返回：
  owner_console_http_success_response(resource=settings, data=OwnerConsoleSettingsSnapshot)
```

脱敏策略：

```text
settings endpoint 复用 OwnerConsoleSettingsSnapshot：
  base_url 通过 redacted_base_url 输出
  API key 只输出 api_key_configured=true/false
  不输出 AIKE_LLM_API_KEY / MAIN_LLM_API_KEY 正文
  embedding API key 固定不暴露
```

错误处理：

```text
item_limit 非法：
  HTTP 400
  error.code = bad_request
  error.details.field = item_limit

其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true
  access-control.http_api_enabled=true
  settings.http_api_enabled=true

仍未开放：
  diagnostics.http_api_enabled=false
  memory.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 Diagnostics 外部探测。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 12 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 315 tests OK
```

## v1.6 Owner Console FastAPI memory endpoint

状态：已落地 P2.23 第一刀。目标是在 P2.22 接通 access-control / settings 后，继续开放 `GET /api/v1/owner-console/memory`。本步仍只返回结构化只读快照：计数、配置、RAG 边界与安全标志；不返回任何记忆正文，不执行检索，不重建索引。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/memory

更新 src/plugins/ai_chat/owner_console_http_adapter.py：
  HTTP read runtime 注入只读 memory stats providers：
    memory_stats
    manual_memory_stats
    gap_scene_summary_stats
    rag_document_stats

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 memory endpoint 的只读 envelope、消息计数、上下文策略、MemoryRAG / ProjectDocRAG flags、内容不暴露、检索不执行、索引不重建。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 memory。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
```

`GET /api/v1/owner-console/memory` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取：
  memory compression 配置
  gap scene summaries 配置
  long term memory context 配置
  MemoryRAG 配置
  ProjectDocRAG 配置

只读统计：
  memory_stats -> message_count / session_count / summary_count / summarized_message_count
  manual_memory_stats -> memory_count / subject_count
  gap_scene_summary_stats -> summary_count / source_message_count
  rag_document_stats -> document_count / active_document_count / embedding_count

调用：
  runtime.build_memory_snapshot()

返回：
  owner_console_http_success_response(resource=memory, data=OwnerConsoleMemorySnapshot)
```

强边界：

```text
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
ProjectDocRAG ordinary_chat_injection_allowed=false
ProjectDocRAG 仍只允许显式 /agent dev_context
```

错误处理：

```text
其他异常：
  HTTP 500
  error.code = internal_error
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true
  access-control.http_api_enabled=true
  settings.http_api_enabled=true
  memory.http_api_enabled=true

仍未开放：
  diagnostics.http_api_enabled=false
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 Diagnostics 外部探测。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 13 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 316 tests OK
```

## v1.6 Owner Console FastAPI diagnostics endpoint

状态：已落地 P2.24 第一刀。目标是在 P2.23 接通 memory 后，开放最后一个 v0 只读页面资源：`GET /api/v1/owner-console/diagnostics`。本步采用轻量 read-only diagnostics snapshot：只组合安全文本和已有 read model 计数，不主动调用 `diagnostics.py`，不跑 OpenAI / Ollama / TTS / 图片缓存探测，不读取 QQ adapter。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  GET /api/v1/owner-console/diagnostics

新增内部 helper：
  _owner_console_bool
  _build_owner_console_http_diagnostics

更新 tests/test_owner_console_fastapi_app.py：
  覆盖 diagnostics endpoint 的只读 envelope、外部探测跳过标记、QQ adapter 未导入标记、memory 计数摘要、正文不暴露。

更新 tests/test_owner_console_fastapi_launcher.py：
  launcher route smoke 增加 diagnostics。
```

当前 FastAPI app 已开放：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/diagnostics
```

`GET /api/v1/owner-console/diagnostics` 策略：

```text
不需要 OwnerConsoleContext。
不要求 BOT_OWNER_QQ 已配置。

从 load_config() 读取安全配置摘要：
  owner 是否配置
  private/group chat 开关
  MainAgent flags
  ChatGraph flag
  Vision 配置摘要
  TTS 配置摘要

复用 runtime.build_memory_snapshot() 读取只读计数：
  message_count
  session_count
  session_summary_count
  manual_memory_count
  rag_document_count
  rag_embedding_count

调用：
  runtime.build_health_snapshot(...)

返回：
  owner_console_http_success_response(resource=diagnostics, data=OwnerConsoleHealthSnapshot)
```

强边界：

```text
external_probes_executed=false
qq_adapter_imported=false
diagnostics_module_imported=false
ollama_probe_executed=false
vision_inference_executed=false
image_cache_stats_collected=false
tts_probe_executed=false
recent_error_log_read=false
recent_errors_collected=false
memory_content_exposed=false
project_doc_content_exposed=false
retrieval_executed=false
index_rebuild_executed=false
```

为什么暂不直接复用 diagnostics.py：

```text
diagnostics.py 会导入 NoneBot / OpenAI / Vision 探测相关依赖。
Web Owner Console v0 的目标是先建立 side-effect-free HTTP read surface。
因此 diagnostics endpoint 第一版只暴露结构化、可预测、无外部探测的快照。
后续如果要做主动诊断，应单独设计 explicit probe endpoint，并继续保持 GET 只读与 probe 操作分离。
```

route contract 行为：

```text
FastAPI /routes endpoint 当前标记：
  routes.http_api_enabled=true
  overview.http_api_enabled=true
  tasks.http_api_enabled=true
  tasks.detail.http_api_enabled=true
  approvals.http_api_enabled=true
  approvals.detail.http_api_enabled=true
  access-control.http_api_enabled=true
  settings.http_api_enabled=true
  memory.http_api_enabled=true
  diagnostics.http_api_enabled=true
```

边界：

```text
不新增 Web 前端。
不新增登录/鉴权。
不允许任意 user_id / session_key 查询。
不新增数据库表。
不新增工具能力。
不调用写 runtime。
不确认/拒绝审批。
不恢复工具。
不执行 MemoryRAG / ProjectDocRAG 检索。
不重建 RAG 索引。
不执行 Diagnostics 外部探测。
不 import diagnostics.py。
不执行 QQ/NoneBot 插件入口。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
ProjectDocRAG 仍只允许显式 /agent dev_context，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 14 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 317 tests OK
```

## v1.6 Owner Console HTTP surface audit

状态：已落地 P2.25。目标是在 P2.21-P2.24 完成 Owner Console v0 只读 HTTP surface 后，补一份集中审计文档，把 RESTful route、HTTP envelope、context 策略、只读边界、diagnostics 取舍和后续升级路线写清楚。

本次完成：

```text
新增 docs/owner-console-http-surface-audit.md。

更新 docs/web-owner-console-read-model-design.md：
  在开头补充后续实现状态说明。
  明确 P2.6 的“不接 HTTP”是当时设计阶段边界。
  指向 P2.25 HTTP surface audit。
```

审计结论：

```text
Owner Console HTTP v0 已经具备完整只读资源面。
它仍然不是 Web 前端。
它仍然不做登录/鉴权。
它仍然不开放写操作。
它仍然不替代 QQ / NoneBot adapter。
它仍然不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

当前 HTTP surface：

```text
GET /healthz
GET /api/v1/owner-console/routes
GET /api/v1/owner-console/overview
GET /api/v1/owner-console/tasks
GET /api/v1/owner-console/tasks/{task_id}
GET /api/v1/owner-console/approvals
GET /api/v1/owner-console/approvals/{approval_id}
GET /api/v1/owner-console/access-control
GET /api/v1/owner-console/settings
GET /api/v1/owner-console/memory
GET /api/v1/owner-console/diagnostics
```

文档重点：

```text
启动入口：
  .\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090

禁止直接使用：
  uvicorn src.plugins.ai_chat.owner_console_fastapi_app:app

原因：
  必须避免执行 src/plugins/ai_chat/__init__.py。
  Web adapter 不能加载 QQ/NoneBot 插件入口。
```

RESTful 规范：

```text
API prefix 固定为 /api/v1/owner-console。
只使用 GET。
静态路径 segment 使用 lowercase kebab-case。
JSON 字段和 query 参数使用 snake_case。
集合资源使用复数：tasks、approvals。
详情资源挂在集合资源下：tasks/{task_id}、approvals/{approval_id}。
```

HTTP envelope：

```text
schema_version
read_model_schema_version
transport
api_prefix
resource
generated_at
read_only
http_api_enabled
web_write_enabled
data
error
```

context 策略：

```text
需要 owner context：
  overview
  tasks
  tasks.detail
  approvals
  approvals.detail

构造方式：
  user_id = BOT_OWNER_QQ
  session_key = private:{BOT_OWNER_QQ}

禁止：
  query 覆盖 user_id
  query 覆盖 session_key
```

非 context 快照：

```text
routes
access-control
settings
memory
diagnostics
```

diagnostics 取舍：

```text
GET /diagnostics 第一版只返回轻量 read-only snapshot。
不 import diagnostics.py。
不执行 OpenAI / Ollama / TTS / Vision 探测。
不读取 QQ adapter 图片缓存。
不读取最近错误日志。
未来如果需要主动诊断，应设计 explicit probe endpoint，不把 GET diagnostics 变成探测执行器。
```

后续建议路线：

```text
P2.26：HTTP surface contract cleanup，收敛重复 endpoint glue。
P2.27：本地 FastAPI smoke runbook。
P2.28：Web Owner Console 前端只读壳。
P2.29：登录/鉴权设计。
P2.30：审批操作设计。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract -v
Ran 6 tests OK
```

## v1.6 Owner Console FastAPI adapter glue cleanup

状态：已落地 P2.26。目标是在不新增接口、不改变 HTTP 行为的前提下，收敛 `owner_console_fastapi_app.py` 中重复的成功 envelope、错误 envelope 和 runtime 装配胶水，让 FastAPI 层继续保持薄 adapter。

本次完成：

```text
更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  新增 _owner_console_runtime_from_config。
  新增 _owner_console_success。
  新增 _owner_console_error_response。
  新增 _owner_console_adapter_error。
  新增 _owner_console_internal_error。

各 endpoint 仍保留显式路由函数和显式参数解析。
重复的 owner_console_http_success_response / owner_console_http_error_response 调用收敛到本地 helper。
OwnerConsoleHttpAdapterError 的 status_code、code、message、details 透传语义保持不变。
task / approval detail 的 404 not_found envelope 保持不变。
```

边界：

```text
不新增 endpoint。
不改变 RESTful path。
不改变 query 参数。
不改变 HTTP status code。
不改变 response envelope。
不开放 Web 写操作。
不新增登录/鉴权。
不写前端。
不引入 QQ / NoneBot adapter 依赖。
不触碰 owner_write_runtime。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_app -v
Ran 14 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_http_contract tests.test_owner_console_read_runtime -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 317 tests OK
```

## v1.6 Owner Console FastAPI smoke runbook

状态：已落地 P2.27。目标是在 Owner Console HTTP v0 完成只读 surface 和 adapter glue cleanup 后，补一份本地启动与 smoke 验证手册，避免后续调试时误用 QQ plugin 包路径启动，或把 404/405/403 边界误判为故障。

本次完成：

```text
新增 docs/owner-console-fastapi-smoke-runbook.md。

文档覆盖：
  启动前检查。
  推荐 Uvicorn 启动命令。
  禁止直接使用 src.plugins.ai_chat.owner_console_fastapi_app:app。
  /healthz smoke 检查。
  /routes contract 检查。
  access-control / settings / memory / diagnostics 非 context 快照检查。
  overview / tasks / approvals owner context 端点检查。
  /docs /redoc /openapi.json 关闭检查。
  POST 写方法 405 检查。
  Owner Console 相关 unittest 回归命令。
  import boundary 自检。
  常见问题排查。

更新 docs/owner-console-http-surface-audit.md：
  增加 P2.27 smoke runbook 链接。
```

边界：

```text
不新增 endpoint。
不修改 FastAPI 运行时代码。
不启动常驻服务。
不写前端。
不新增登录/鉴权。
不开放 Web 写操作。
不改变 QQ / NoneBot adapter。
不改变 /agent、普通聊天、审批恢复、MemoryRAG、Diagnostics 或 QQ 命令行为。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console read-only shell design

状态：已落地 P2.28 设计文档。目标是在真正写前端之前，先把未来只读页面壳如何消费现有 Owner Console HTTP GET endpoints 定清楚，避免前端实现时把登录、写操作、审批恢复或 diagnostics 主动探测混进第一版。

本次完成：

```text
新增 docs/web-owner-console-read-only-shell-design.md。

文档覆盖：
  Web Owner Console read-only shell 定位。
  App Shell 范围。
  Dashboard / Tasks / Task Detail / Approvals / Approval Detail 页面映射。
  Diagnostics / Memory / Access Control / Settings 页面映射。
  API 到页面 mapping table。
  HTTP envelope handling 规则。
  loading / empty / error / forbidden / not_found / contract_mismatch 状态模型。
  前端 ownerConsoleApi 命名建议。
  显式刷新策略。
  安全与隐私检查清单。
  第一版完成标准。
  后续路线。

更新 docs/web-owner-console-read-model-design.md：
  补充 P2.28 只读前端壳设计链接。

更新 docs/owner-console-http-surface-audit.md：
  补充 P2.28 页面到 API 映射链接。
```

边界：

```text
不实现真实前端。
不新增 endpoint。
不修改 FastAPI 运行时代码。
不新增登录/鉴权。
不开放 Web 写操作。
不新增审批确认/拒绝入口。
不触发 MainAgent。
不触发 MemoryRAG / ProjectDocRAG 检索。
不触发 diagnostics 主动探测。
不改变 QQ / NoneBot adapter。
```

设计结论：

```text
第一版前端壳只允许调用 GET。
第一版只做显式刷新，不做自动轮询。
第一版必须检查 read_only=true、http_api_enabled=true、web_write_enabled=false。
actionability 只能作为只读展示；不能绑定真实 click handler。
如果未来需要 approve/reject，必须单独设计 POST endpoint、鉴权和审计。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console frontend stack design

状态：已落地 P2.29 设计文档。目标是在创建真实前端工程之前，先确定技术栈、目录边界、启动命名、API client 边界和 Python/Node 分层，避免把前端工程混入 `src/plugins/ai_chat` 或让 Web 入口绕过 HTTP read model。

本次完成：

```text
新增 docs/web-owner-console-frontend-stack-design.md。

设计推荐：
  未来前端目录使用 web/owner-console。
  技术栈使用 Vite + React + TypeScript。
  路由使用 React Router。
  图标使用 lucide-react。
  样式先用 plain CSS 或 CSS Modules。
  数据请求先用 native fetch。
  第一版不引入 Next.js、SSR、TanStack Query、Redux/Zustand、Tailwind 或大型 UI 框架。

文档覆盖：
  为什么不放在 Python src 里。
  未来目录草案。
  ownerConsoleApi 方法命名。
  TypeScript DTO 策略。
  前端页面路径设计。
  状态管理策略。
  样式和组件策略。
  Vite dev proxy 与 CORS 边界。
  npm scripts 命名建议。
  Python / Node 禁止 import 边界。
  未来测试策略。
  第一版前端工程创建标准。

更新 docs/web-owner-console-read-only-shell-design.md：
  补充 P2.29 前端栈设计链接。

更新 docs/owner-console-http-surface-audit.md：
  补充 P2.29 前端栈与目录边界链接。
```

边界：

```text
不创建 package.json。
不安装 Node 依赖。
不写 React 组件。
不写 CSS。
不启动前端 dev server。
不修改 FastAPI 运行时代码。
不新增 endpoint。
不新增 CORS。
不开放 Web 写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot adapter。
```

设计结论：

```text
前端工程未来放在 web/owner-console，而不是 src/ 或 src/plugins/ai_chat。
前端只能通过 GET /healthz 和 GET /api/v1/owner-console/* 读取数据。
第一版只接 /healthz 和 /routes，验证 App Shell 和 contract boundary。
Vite dev proxy 可以解决本地开发跨端口问题，不提前打开 FastAPI CORS。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console UI layout design

状态：已落地 P2.30 设计文档。目标是在创建真实前端工程前，先确定简约 UI 风格、中文导航、中文顶部状态条、页面信息层级和只读边界展示规则。

本次完成：

```text
新增 docs/web-owner-console-ui-layout-design.md。

设计结论：
  页面走简约工具风格。
  优先展示结构、内容和状态。
  左侧固定导航全部中文化。
  顶部状态条全部中文化。
  后端 JSON 字段继续保持英文 snake_case，前端展示统一转为中文标签。

中文主导航：
  概览
  任务
  审批
  诊断
  记忆
  访问控制
  设置

任务详情和审批详情不放入主导航，从列表点击进入。

顶部状态条中文标签：
  主人控制台
  只读模式：已开启
  网页写入：已关闭
  后端连接：已连接 / 已断开
  接口版本：owner_console.http.v1
  最后刷新：YYYY-MM-DD HH:mm:ss
  刷新
```

文档覆盖：

```text
三段式布局：左侧导航、顶部状态条、主内容区。
字段中文化规则。
页面状态中文化规则。
只读边界 UI 规则。
概览 / 任务 / 任务详情 / 审批 / 审批详情 页面信息层级。
诊断 / 记忆 / 访问控制 / 设置 页面信息层级。
通用组件清单。
视觉风格约束。
第一版 UI 完成标准。
```

更新：

```text
docs/web-owner-console-read-only-shell-design.md
docs/web-owner-console-frontend-stack-design.md
docs/owner-console-http-surface-audit.md
```

边界：

```text
不创建前端工程。
不安装 npm 依赖。
不写 React 组件。
不写 CSS。
不修改 FastAPI 运行时代码。
不新增 endpoint。
不开放 Web 写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot adapter。
```

测试：

```text
git diff --check
OK，仅有 Windows LF/CRLF 提示

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console minimal App Shell

状态：已落地 P2.31 第一刀。目标是创建 `web/owner-console` 最小 Vite + React + TypeScript 前端工程，只接 `/healthz` 和 `/api/v1/owner-console/routes`，先跑通中文 App Shell、左侧导航、顶部状态条和只读 route contract 展示。

本次完成：

```text
新增 web/owner-console 前端工程。

新增：
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  index.html
  .env.example
  README.md
  src/main.tsx
  src/vite-env.d.ts
  src/api/ownerConsoleApi.ts
  src/api/ownerConsoleEnvelope.ts
  src/api/ownerConsoleTypes.ts
  src/app/App.tsx
  src/app/AppShell.tsx
  src/app/PlaceholderPage.tsx
  src/components/StatusBadge.tsx
  src/components/EmptyState.tsx
  src/styles/app.css

更新 .gitignore：
  忽略 web/owner-console/dist/
  忽略 web/owner-console/.vite/
```

前端第一刀能力：

```text
左侧中文固定导航：
  概览
  任务
  审批
  诊断
  记忆
  访问控制
  设置

顶部中文状态条：
  主人控制台
  只读模式：已开启 / 异常
  网页写入：已关闭 / 异常
  后端连接：连接中 / 已连接 / 已断开
  接口版本
  最后刷新
  刷新

概览页展示：
  只读接口状态
  route contract rows
  route_count
  allowed_methods
  write_routes_enabled=false
```

依赖与安全：

```text
npm install 后初始 Vite 5.x 链路触发 npm audit 漏洞提示。
根据 npm audit 修复建议，升级到 vite 8.1.4 和 @vitejs/plugin-react 6.0.3。
npm audit 后为 0 vulnerabilities。
```

边界：

```text
只调用 GET /healthz。
只调用 GET /api/v1/owner-console/routes。
不接 overview / tasks / approvals 业务数据。
不新增 FastAPI endpoint。
不修改 FastAPI 行为。
不打开 /docs /openapi.json。
不新增 CORS。
不新增登录/鉴权。
不开放 Web 写操作。
不新增审批确认/拒绝入口。
不触发 MainAgent。
不读取 Python 文件、数据库、.env 或日志。
```

本地 smoke：

```text
FastAPI backend:
  .\.venv\Scripts\python.exe -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1 --port 8090

Vite frontend:
  npm run dev

本地访问：
  http://127.0.0.1:5173/owner-console

进程状态：
  127.0.0.1:8090 LISTENING
  127.0.0.1:5173 LISTENING

HTTP smoke：
  GET http://127.0.0.1:5173/owner-console -> 200
  GET http://127.0.0.1:5173/healthz -> ok=true, read_only=true, web_write_enabled=false
  GET http://127.0.0.1:5173/api/v1/owner-console/routes -> resource=routes, route_count=10, methods=GET
```

浏览器验证：

```text
已尝试使用本地浏览器控制工具。
当前环境返回可用浏览器列表为空，因此本轮未完成截图级浏览器验证。
已用 Vite build、HTTP smoke 和 API proxy smoke 兜底验证。
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Dashboard data

状态：已落地 P2.32 第一刀。目标是在已有中文 App Shell 上接入概览页真实只读数据，先读取 `/overview` 和 `/diagnostics`，让页面能看到任务/审批计数、最近任务、待审批摘要、运行边界和轻量诊断状态。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleOverview / counters / task row / approval row 类型。
  增加 OwnerConsoleHealthSnapshot / text section / observation 类型。
  增加 overview 和 diagnostics envelope 类型。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /overview 和 /diagnostics。
  新增 getOverview({ task_limit, approval_limit })。
  新增 getDiagnostics()。
  增加 OwnerConsoleApiError，用于保留 HTTP status、error code 和 details。

新增 web/owner-console/src/pages/DashboardPage.tsx：
  并行读取 overview 和 diagnostics。
  overview 失败时用中文错误态展示，diagnostics 仍可独立展示。
  403 时提示检查 BOT_OWNER_QQ。
  展示待处理任务、失败任务、待审批、网页写入状态。
  展示最近任务表、待审批表、运行边界、轻量诊断分区。

新增 web/owner-console/src/components/ErrorState.tsx。
更新 App route：/owner-console 使用 DashboardPage。
更新 app.css：增加 dashboard、metric、compact table、diagnostic section、error/loading 状态样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/overview。
只调用 GET /api/v1/owner-console/diagnostics。
不接任务详情。
不接审批详情。
不显示审批确认/拒绝按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
不触发 diagnostics 主动探测。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console -> 200
GET http://127.0.0.1:5173/api/v1/owner-console/overview?task_limit=5&approval_limit=5
  resource=overview
  read_only=true
  web_write_enabled=false
  pending_tasks=9
  pending_approvals=2

GET http://127.0.0.1:5173/api/v1/owner-console/diagnostics
  resource=diagnostics
  read_only=true
  web_write_enabled=false
  bot_status_lines=4
  diagnostics_lines=4
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Tasks list data

状态：已落地 P2.33 第一刀。目标是在中文 App Shell 和 Dashboard 之后，接入任务列表页真实只读数据，让 `/owner-console/tasks` 可以读取 `/api/v1/owner-console/tasks` 并以表格展示主人私聊上下文内的任务。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleTaskList。
  增加 OwnerConsoleTaskListEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /tasks。
  新增 getTasks({ status, limit })。

新增 web/owner-console/src/pages/TasksPage.tsx：
  读取 GET /api/v1/owner-console/tasks?limit=20。
  支持中文状态筛选：全部、待处理、已完成、失败、已取消。
  展示任务 ID、目标摘要、状态、最近事件、待审批、下一步、详情入口。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查任务状态筛选或 limit。

更新 App route：
  /owner-console/tasks 使用 TasksPage。

更新 app.css：
  增加 data toolbar。
  增加 segmented filter tabs。
  增加 task table。
  增加只读详情链接样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/tasks。
不创建任务。
不取消任务。
不重试任务。
不推进任务。
不新增审批按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/tasks -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/tasks?limit=20
  resource=tasks
  read_only=true
  web_write_enabled=false
  total_visible=20
  rows=20

GET http://127.0.0.1:5173/api/v1/owner-console/tasks?status=pending&limit=20
  resource=tasks
  status_filter=pending
  total_visible=9
  rows=9
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Task detail data

状态：已落地 P2.34 第一刀。目标是在任务列表之后接入任务详情页真实只读数据，让 `/owner-console/tasks/:task_id` 可以读取 `/api/v1/owner-console/tasks/{task_id}` 并展示单个任务的目标、结果、关联审批和事件时间线。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleTaskEventRow。
  增加 OwnerConsoleTaskDetail。
  增加 OwnerConsoleTaskDetailEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /tasks/{positive_int} 动态路径校验。
  新增 getTaskDetail(task_id, { event_limit, preview_limit })。
  继续只使用 GET，不接受 owner context query 参数。

新增 web/owner-console/src/pages/TaskDetailPage.tsx：
  读取 GET /api/v1/owner-console/tasks/{task_id}?event_limit=20&preview_limit=800。
  展示任务信息、目标、结果、下一步、关联审批和事件时间线。
  支持从详情页返回任务列表。
  400 / 403 / 404 使用中文错误态说明。

更新 App route：
  /owner-console/tasks/:task_id 使用 TaskDetailPage。

更新 app.css：
  增加详情页 header action。
  增加返回链接、详情分区、关联审批小表格和事件时间线表格样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/tasks/{task_id}。
不创建任务。
不取消任务。
不重试任务。
不推进任务。
不确认或拒绝审批。
不新增审批操作按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/tasks/24 -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/tasks/24?event_limit=20&preview_limit=800
  resource=tasks
  read_only=true
  web_write_enabled=false
  task_id=24
  events=5
  approvals=1
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Approvals list data

状态：已落地 P2.34 第二刀。目标是在任务列表和任务详情之后补齐审批列表页真实只读数据，让 `/owner-console/approvals` 可以读取 `/api/v1/owner-console/approvals` 并以中文表格展示主人私聊上下文内的审批记录。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleApprovalList。
  增加 OwnerConsoleApprovalListEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /approvals。
  新增 getApprovals({ status, limit })。

新增 web/owner-console/src/pages/ApprovalsPage.tsx：
  读取 GET /api/v1/owner-console/approvals?limit=20。
  支持中文状态筛选：全部、待审批、已确认、已拒绝、已过期。
  展示审批 ID、任务 ID、工具、风险等级、状态、原因摘要、操作状态、创建时间和详情入口。
  操作状态只展示“网页只读”等元信息，不提供确认/拒绝入口。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查审批状态筛选或 limit。

更新 App route：
  /owner-console/approvals 使用 ApprovalsPage。

更新 app.css：
  增加 approval table 样式。
  移动端保持横向滚动，避免表格挤压布局。
```

边界：

```text
只调用 GET /api/v1/owner-console/approvals。
不确认审批。
不拒绝审批。
不恢复执行工具。
不新增审批操作按钮。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/approvals -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/approvals?limit=20
  resource=approvals
  read_only=true
  web_write_enabled=false
  total_visible=19
  rows=19

GET http://127.0.0.1:5173/api/v1/owner-console/approvals?status=pending&limit=20
  resource=approvals
  pending_total=2
  pending_rows=2
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Approval detail data

状态：已落地 P2.34 第三刀。目标是在审批列表之后补齐审批详情页真实只读数据，让 `/owner-console/approvals/:approval_id` 可以读取 `/api/v1/owner-console/approvals/{approval_id}` 并展示审批风险、脱敏工具输入、关联任务和近期任务事件。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleToolInputPreview。
  增加 OwnerConsoleApprovalDetail。
  增加 OwnerConsoleApprovalDetailEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /approvals/{positive_int} 动态路径校验。
  新增 getApprovalDetail(approval_id, { event_limit, preview_limit })。
  继续只使用 GET，不接受 owner context query 参数。

新增 web/owner-console/src/pages/ApprovalDetailPage.tsx：
  读取 GET /api/v1/owner-console/approvals/{approval_id}?event_limit=5&preview_limit=800。
  展示审批信息、审批原因、工具输入预览、关联任务和近期任务事件。
  工具输入只展示后端已生成的 preview_json，并显示是否脱敏、是否截断。
  支持从详情页返回审批列表。
  支持跳转到关联任务详情。
  400 / 403 / 404 使用中文错误态说明。

更新 App route：
  /owner-console/approvals/:approval_id 使用 ApprovalDetailPage。

更新 app.css：
  增加详情页 section header / footer。
  增加工具输入预览块样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/approvals/{approval_id}。
不确认审批。
不拒绝审批。
不恢复执行工具。
不新增审批操作按钮。
不读取原始 tool_input_json。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/approvals/19 -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/approvals/19?event_limit=5&preview_limit=800
  resource=approvals
  read_only=true
  web_write_enabled=false
  approval_id=19
  has_task=true
  events=5
  redacted=false
  truncated=false
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Diagnostics data

状态：已落地 P2.35 第一刀。目标是在任务/审批主链路之后接入诊断页真实只读数据，让 `/owner-console/diagnostics` 可以读取 `/api/v1/owner-console/diagnostics` 并展示当前 Owner Console 可见的系统诊断快照。

本次完成：

```text
新增 web/owner-console/src/pages/DiagnosticsPage.tsx：
  读取 GET /api/v1/owner-console/diagnostics。
  展示快照时间、机器人状态、最近错误状态。
  展示机器人状态、诊断状态、配置状态、视觉状态、图片缓存、记忆状态、语音状态、最近错误。
  展示 MainAgent 观测和 RootGraph 观测。
  展示运行边界。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查诊断快照请求。

更新 App route：
  /owner-console/diagnostics 使用 DiagnosticsPage。

更新 app.css：
  增加 diagnostic card grid。
  增加 diagnostic card / diagnostic lines / empty line 样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/diagnostics。
不主动运行诊断探测。
不测试模型。
不读取新的图片。
不清理缓存。
不清理错误日志。
不重建索引。
不修改配置。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/diagnostics -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/diagnostics
  resource=diagnostics
  read_only=true
  web_write_enabled=false
  bot_status_lines=4
  diagnostics_lines=4
  memory_lines=11
  recent_errors_ok=true
  main_agent_observations=0
  root_graph_observations=0
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Memory data

状态：已落地 P2.35 第二刀。目标是在诊断页之后接入记忆页真实只读数据，让 `/owner-console/memory` 可以读取 `/api/v1/owner-console/memory` 并展示 Memory / MemoryRAG / ProjectDocRAG 的计数、配置和隐私边界。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleMemoryCounts。
  增加 OwnerConsoleMemoryContextPolicy。
  增加 OwnerConsoleMemoryRagSnapshot。
  增加 OwnerConsoleProjectDocRagSnapshot。
  增加 OwnerConsoleMemorySnapshot。
  增加 OwnerConsoleMemoryEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /memory。
  新增 getMemory()。

新增 web/owner-console/src/pages/MemoryPage.tsx：
  读取 GET /api/v1/owner-console/memory。
  展示消息、会话、会话摘要、长期记忆等计数。
  展示 RAG 文档、RAG 向量、场景摘要等详细计数。
  展示上下文策略。
  展示 MemoryRAG 配置。
  展示 ProjectDocRAG 配置。
  展示记忆正文、项目文档正文、检索、索引重建等隐私边界状态。
  403 时中文提示检查 BOT_OWNER_QQ。
  400 时中文提示检查记忆快照请求。

更新 App route：
  /owner-console/memory 使用 MemoryPage。

更新 app.css：
  增加 detail-list 样式，用于配置型只读字段展示。
```

边界：

```text
只调用 GET /api/v1/owner-console/memory。
不展示 messages.content。
不展示 long_term_memories.content。
不展示 rag_documents.content。
不执行 MemoryRAG 检索。
不执行 ProjectDocRAG 检索。
不重建索引。
不新增记忆。
不删除记忆。
不修改配置。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/memory -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/memory
  resource=memory
  read_only=true
  web_write_enabled=false
  message_count=384
  session_count=5
  manual_memory_count=13
  rag_document_count=977
  memory_content_exposed=false
  project_doc_content_exposed=false
  retrieval_executed=false
  index_rebuild_executed=false
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Access Control data

状态：已落地 P2.35 第三刀。目标是在记忆页之后接入访问控制页真实只读数据，让 `/owner-console/access-control` 可以读取 `/api/v1/owner-console/access-control` 并展示主人配置、聊天入口、陌生私聊策略、白名单、黑名单和运行边界。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleAccessList。
  增加 OwnerConsoleAccessControlSnapshot。
  增加 OwnerConsoleAccessControlEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /access-control。
  新增 getAccessControl({ item_limit })。

新增 web/owner-console/src/pages/AccessControlPage.tsx：
  读取 GET /api/v1/owner-console/access-control?item_limit=50。
  展示主人配置状态。
  展示私聊入口、群聊入口和陌生私聊策略。
  展示私聊白名单、群聊白名单、用户黑名单的数量、可见条目和截断状态。
  展示运行边界。
  400 时中文提示检查列表数量限制。

更新 App route：
  /owner-console/access-control 使用 AccessControlPage。

更新 app.css：
  增加 access-list-items 样式，用于只读名单条目展示。
```

边界：

```text
只调用 GET /api/v1/owner-console/access-control。
不添加白名单。
不移除白名单。
不拉黑用户。
不解除拉黑。
不修改私聊/群聊开关。
不修改陌生私聊策略。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/access-control -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/access-control?item_limit=50
  resource=access-control
  read_only=true
  web_write_enabled=false
  owner_configured=true
  private_chat_enabled=true
  group_chat_enabled=true
  unknown_private_policy=deny
  private_whitelist_count=2
  group_whitelist_count=2
  user_blacklist_count=0
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console Settings data

状态：已落地 P2.35 第四刀。目标是在访问控制页之后接入设置页真实只读数据，让 `/owner-console/settings` 可以读取 `/api/v1/owner-console/settings` 并展示模型配置、Embedding、功能开关、角色卡摘要和运行边界。

本次完成：

```text
更新 web/owner-console/src/api/ownerConsoleTypes.ts：
  增加 OwnerConsoleModelConfigSnapshot。
  增加 OwnerConsoleRoleCardRow。
  增加 OwnerConsoleSettingsSnapshot。
  增加 OwnerConsoleSettingsEnvelope。

更新 web/owner-console/src/api/ownerConsoleApi.ts：
  只读 allowlist 增加 /settings。
  新增 getSettings()。

新增 web/owner-console/src/pages/SettingsPage.tsx：
  读取 GET /api/v1/owner-console/settings。
  展示聊天模型、MainAgent 模型和 Embedding 配置。
  API Key 只展示“已配置/未配置”。
  Base URL 只展示后端返回的脱敏值。
  展示功能开关。
  展示角色卡 key/title 和当前启用项。
  展示运行边界。
  400 时中文提示检查设置快照请求。

更新 App route：
  /owner-console/settings 使用 SettingsPage。

更新 app.css：
  增加 feature-flag-grid。
  增加 role-card-list / role-card-row 样式。
```

边界：

```text
只调用 GET /api/v1/owner-console/settings。
不展示 API Key 原文。
不展示未脱敏 Base URL 密钥参数。
不保存配置。
不切换角色卡。
不写 data/active-role-card.json。
不修改功能开关。
不新增 FastAPI endpoint。
不修改 FastAPI 运行时代码。
不开放 Web 写操作。
不新增登录/鉴权。
不触发 MainAgent。
```

本地 smoke：

```text
GET http://127.0.0.1:5173/owner-console/settings -> 200

GET http://127.0.0.1:5173/api/v1/owner-console/settings
  resource=settings
  read_only=true
  web_write_enabled=false
  chat_model=deepseek-v4-flash
  chat_api_key_configured=true
  main_model=gpt-5.5
  main_api_key_configured=true
  embedding_model=bge-m3
  embedding_api_key_configured=false
  role_cards=2
  active_role_card_key=aike
  enable_main_agent=true
  enable_agent_shell=false
  enable_agent_web=false
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 Web Owner Console frontend read-only audit

状态：已落地 P2.36 前端只读收口审计。目标是在主导航页面全部接入真实只读数据后，确认前端请求面、页面操作入口和文档边界仍符合 Web Owner Console v0 只读定位。

本次完成：

```text
新增 docs/web-owner-console-frontend-readonly-audit.md：
  记录主导航页面覆盖状态。
  记录 ownerConsoleApi 只读请求面。
  记录 allowlist 和动态详情路径校验。
  记录页面 button / Link 操作入口审计。
  记录写相关搜索命中的只读解释。
  记录当前仍保持的 MainAgent / ProjectDocRAG / Web v0 边界。
  给出后续建议：优先前端 smoke / contract guard、runbook、部署设计，再单独讨论登录/鉴权和审批操作。

移除 web/owner-console/src/app/PlaceholderPage.tsx：
  主导航页面已经全部接入真实只读数据。
  删除未使用占位组件，避免后续审计误把占位文案当作真实页面状态。
```

审计结论：

```text
所有 API client 请求都通过 ownerConsoleApi。
ownerConsoleApi 只使用 fetch GET。
前端 allowlist 只包含 Owner Console 只读 HTTP 资源。
动态详情路径只允许正整数 ID。
没有请求 /docs、/redoc 或 /openapi.json。
没有 approve / reject / resume / create / cancel 类型 API client。
页面按钮仅用于刷新或筛选。
页面链接仅用于查看详情或返回列表。
没有 Web 审批确认、拒绝、恢复执行、配置保存、角色卡切换、名单修改、记忆写入或索引重建入口。
```

边界：

```text
不新增后端接口。
不新增前端写能力。
不新增登录/鉴权。
不修改 FastAPI 运行时代码。
不触发 MainAgent。
不改变 QQ / /agent 行为。
```

测试：

```text
npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v1.6 MainAgent zoned system diagnostics overview

状态：已完成 P2.46a 设计、P2.46b 系统概览、P2.46c 视觉区详情和 P2.46d 主人 QQ live。随后在不另设阶段编号的前提下，增加了语音、记忆与RAG区域详情以及 MainAgent 路由/表达收口。设计见 `docs/main-agent-system-diagnostics-report-design.md`。

当前扩展（不另设阶段编号）：

```text
system_diagnostics_report 当前严格注册 overview、vision、voice 和 memory_rag。
/agent 执行系统诊断任务：语音 沿 configuration -> endpoint -> service -> model -> observation 首故障链检查，只读 loopback TTS health、loaded、language、最近候选和最近安全发送观测。
/agent 执行系统诊断任务：记忆与RAG 沿 configuration -> storage -> index -> runtime -> observation 首故障链检查，只读非正文存储/索引统计和最近安全观测。
voice 不生成音频、不创建音频文件、不发送 QQ、不重启或加载/下载模型；memory_rag 不执行 embedding、语义召回、ProjectDocRAG 正文读取或索引重建。
/agent 语音状态怎么样 已显示总体状态、开关、服务可达性、health、IndexTTS2 loaded、语言、最近候选和端到端未验证声明。
/agent 查看配置状态 已更新为基础入口、聊天模型、MainAgent、记忆与RAG、视觉、语音和高风险边界分区，并继续对 URL 与 Key 脱敏。
未知且无 Main LLM 的 /agent 表达现在进入 ask_owner，不再默认调用 dev_context/RAG；显式 /agent 查、/agent 查询、/agent search 和 /agent-debug 仍可进入研发上下文。
Main LLM 遇到对象、范围或运行/研发歧义时优先 ask_owner；运行状态禁止由 dev_context 兜底猜测。
MainAgent 工具总结新增中性身份边界：RAG/工具结果不是身份设定，不采用角色名、自称、动作旁白，也不虚构未执行检查。
OwnerAgentWorkRuntime sanitizer 已支持四种报告 payload；任务记录只保留区域状态、定位层级、推荐 scope 和安全计数，任何 external/deep/repair 非零结果都拒绝完成。
```

当前扩展验证：

```text
聚焦回归：148 tests OK。
全量 unittest discover：407 tests OK。
新增视觉 8 种、语音 7 种、记忆与RAG 8 种概览—详情状态一致性合同，以及三类详情共同实用性输出合同。
Python compile、AST 和 git diff --check 通过。
既有非失败提示：FastAPI/Starlette TestClient 与 httpx 弃用警告。
```

主人 QQ live：

```text
正式任务：#33 系统概览、#34 视觉详情、#35 语音详情、#36 记忆与RAG详情；四条命令均成功完成。
主人核对任务详情后确认 external_request_count=0、deep_probe_count=0、repair_action_count=0，其他功能输出正常。
#35 定位为语音服务层降级：TTS 开启、地址为本机 loopback，但本地服务不可达；第一故障链因此没有继续判断 health、IndexTTS2、语言或生成/发送状态。
live 发现服务失败时下游“未继续判断”原因不够直观，且任务回复尾部仍只写 overview/vision。代码已补充 health、模型、语言、生成、发送的逐项跳过原因，并把边界更新为 overview、vision、voice、memory_rag。
正式任务 #37 当时完成主人 QQ live 复验：输出仍按旧语义定位服务层降级；health、IndexTTS2、语言、最近生成和最近发送均明确写明因本地服务不可达而未继续判断；尾部正确列出视觉、语音、记忆与RAG区详情。该段是运行策略补充前的历史输出，不代表当前严重度结论。
主人随后明确 TTS 为节省显存采用真实语音请求时按需冷启动。当前实现新增 `auto_start_enabled` evidence 和启动策略层：自动冷启动开启且服务未运行时为正常/按需待机；服务在线但 `loaded=false` 时为模型等待首次生成按需加载；自动启动关闭且服务不可达或 health 明确异常时才降级。overview、正式语音详情和快速语音状态复用同一纯状态 evaluator。
快速语音状态 QQ live 已正确显示“按需待机”。正式语音任务 #40 随后失败：纯报告已生成 `fault_layer=startup`，但 OwnerAgentWorkRuntime 的 `expected_statuses` 遗漏该新层，访问映射时触发 `KeyError`。补上 `startup -> normal` 并新增真正经过任务创建、sanitizer、持久化和格式化的回归后，聚焦 59 项、全量 407 项通过；主人重启 Bot 重新验证正式语音详情和 overview，反馈均没有问题。新的成功任务 ID 未提供，因此不补写编号。该 live 没有触发真实 TTS 冷启动、模型加载、音频生成或 QQ 发送。
该 live 不代表执行了真实视觉推理、TTS 音频生成、QQ 语音端到端发送、embedding、语义召回或 MemoryRAG 重建。
系统概览曾显示 2 条活动文档缺少向量；仅保留为已发现现象，不自动重建索引或创建修复任务。
```

本次完成：

```text
将 system_diagnostics_report 定位为第二个候选正式只读工作类型。
默认任务只做系统大区概览分诊，不复制现有诊断系统的完整输出。
采用“系统概览 -> 区域详情 -> 针对性深度探针”三级模型。
正常和按设计关闭的大区合并输出，只单独突出异常、降级、需要关注和影响判断的未知区域。
概览最多推荐一个优先排查区域，并返回严格的主人确认命令；不自动创建详情任务。
首批核心大区定义为核心运行、聊天、MainAgent、记忆与RAG、视觉和语音；Owner Console 为可选区。
区域详情沿固定依赖链查找第一故障层，上游失败后不继续堆叠无关下游证据。
视觉区作为首个候选详情试点，明确区分服务在线、模型已安装、模型驻留和最近使用状态。
概览不调用 LLM、外部聊天 API、视觉推理、embedding、RAG 召回或 ProjectDocRAG 正文。
定义了自适应短输出、安全持久化摘要、部分失败、任务 done/failed 和显式下钻合同。
```

拟定拆分：

```text
P2.46b：只实现结构化大区快照、确定性 evaluator、overview 和第二个正式只读 work type。
P2.46c：实现 vision 区域详情试点，不执行真实推理。
P2.46d：重启 Bot 后完成主人 QQ live，验证短输出、显式下钻和安全持久化。
其他区域详情和深度探针根据实际使用结果另行批准。
```

P2.46b 实现：

```text
新增 src/plugins/ai_chat/system_diagnostics_report.py：
  六个固定大区的结构化 evidence 和 status。
  normal / attention / degraded / error / off_by_design / unknown 确定性判断。
  严重度和核心依赖优先级选择一个 primary scope。
  正常/按设计关闭区域合并，异常区域单行突出，概览最多 1200 字符。
  只允许 loopback 服务 URL 进入廉价本地探针判断。

OwnerAgentWorkRuntime：
  注册第二个 system_diagnostics_report/read_local work type。
  新增严格“执行系统诊断任务”解析；overview 可执行，已知区域和未知 scope 均在任务前停止。
  系统概览 sanitizer 强制 external_request_count、deep_probe_count、repair_action_count 全为 0。
  QQ 详细报告只在本次主人私聊返回；task.result 和 work_finished 只保存总体状态、六区计数、优先区域和安全计数。

OwnerRuntimeFactory / QQ 入口：
  注入 event-bound system_diagnostics_report executor。
  /agent 执行系统诊断任务 只允许主人私聊且先于普通语义/LLM 路径执行。
  /agent-debug、普通聊天、群聊、非主人私聊和 Web 不能触发。
  区域详情未注册时不创建任务，不执行探针，不 fallback 到 dev_context。

overview 证据：
  核心运行：当前入口和数据库 SELECT 1。
  聊天：开关、模型配置完整性和最近 RootGraph 安全错误布尔值；不发 completion。
  MainAgent：两个正式 work type、主人私聊策略和 owner_write_command 审批/受控恢复标记。
  记忆与RAG：MemoryRAG 非正文索引/向量/待索引计数和最近安全观测；不做 embedding/召回。
  视觉：只对 loopback Ollama 查询服务和模型列表，结合最近视觉计数；不做推理。
  语音：关闭时跳过；开启且 loopback 时只读 health；不生成音频。
```

P2.46c 实现：

```text
system_diagnostics_report.py：
  新增 VisionDiagnosticsReportPayload、vision scope、1800 字符上限和固定定位层级。
  按 configuration -> service -> model -> invocation/quality/observation 首故障短路。
  视觉关闭为 off_by_design；非 loopback/未验证服务为 unknown；服务或模型不可用为 degraded。
  最近调用错误只建议 vision_invocation，低质量只建议 vision_inference；两个深度 scope 均未注册且不会自动执行。
  无近期使用保持 normal/neutral，并明确不等于端到端验证。

OwnerAgentWorkRuntime：
  system_diagnostics_report sanitizer 同时接受 overview 与 vision 两种结构化 payload。
  vision task.result/work_finished 只保存区域状态、定位层级、推荐 scope 和本地/深度/外部/修复计数。
  external_request_count、deep_probe_count、repair_action_count 任一非 0 都拒绝完成任务。
  不持久化详细状态链、日志、图片、路径、配置值或完整观测。

OwnerRuntimeFactory / QQ 入口：
  /agent 执行系统诊断任务：视觉 仅允许主人私聊显式执行并创建 scope=vision 正式任务。
  overview 与 vision 共用视觉 evidence collector，避免两个输出漂移。
  vision-only 在数据库、MemoryRAG、MainAgent 注册表、TTS 和聊天概览探针之前返回。
  只允许 loopback Ollama /api/tags；非 loopback 地址不主动访问。
  不执行 describe_images、真实视觉推理、测试图片、模型拉取、服务重启、自动子任务、重试或修复。
  其他已知区域和未知 scope 仍在任务创建前停止，不 fallback 到语义 MainAgent、LLM 或 dev_context。
```

P2.46c 验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_system_diagnostics_report tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract tests.test_diagnostics_units tests.test_config_loading -q
Ran 166 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -q
Ran 375 tests OK

既有非失败提示：FastAPI TestClient 依赖产生 StarletteDeprecationWarning。
```

P2.46c 文档与检索验证：

```text
.\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=62
  chunks_seen=1320
  created_documents=1
  updated_documents=221
  embeddings_created=1
  embeddings_updated=75
  errors=0

P2.46c 当时的固定查询“P2.46c system_diagnostics_report vision 视觉区详情 当前实现 P2.46d QQ live 待验收”：
  project_results=5
  第 1 条为 current-development-status P2.46c 当前状态锚点
  第 2 条为 main-agent-system-diagnostics-report-design 的 P2.46c 实现清单
  第 4、5 条为设计总状态和 version-runlog 当前阶段
  当时召回结论一致：P2.46c 本地完成，P2.46d Bot 重启和主人 QQ live 待完成
  历史 P2.46a/b 片段只作为后排阶段记录，没有覆盖当前状态锚点
```

边界：

```text
本段是 P2.46c 完成时的历史边界；当时尚未重启 Bot 或进行 P2.46d live 验收，后续 live 已完成。
普通聊天仍不能触发 MainAgent；ProjectDocRAG 正文仍只进入显式 /agent dev_context。
不新增 shell、Git、任意文件读写、未注册数据库写入、外部请求、自动诊断、自动下钻、自动修复或额外 QQ 发送。
Owner Console 继续只读 GET；P2.40b、登录鉴权和 Web 审批操作继续未批准。
```

P2.46b 验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_system_diagnostics_report tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract tests.test_diagnostics_units tests.test_config_loading -v
Ran 155 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 364 tests OK

既有非失败提示：FastAPI TestClient 依赖产生 StarletteDeprecationWarning。
```

P2.46b 文档与检索验证：

```text
.\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=62
  chunks_seen=1318
  new_documents=1
  new_embeddings=1
  errors=0

固定查询“P2.46b system_diagnostics_report overview 当前实现 视觉区域待完成 QQ live”：
  project_results=4
  memory_results=0
  第 1 条为 current-development-status P2.46b 快照
  其余命中来自 main-agent-system-diagnostics-report-design 和 version-runlog
  全部一致声明 P2.46b 本地完成、P2.46c 视觉详情和 P2.46d QQ live 未完成
```

文档与检索验证：

```text
Markdown 相对链接检查：没有缺失目标。
git diff --check：通过。
第一次 ProjectDocRAG 重建因执行工具 64 秒上限被中断，未将其记为成功。
使用更长命令超时重新执行 .\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=62
  chunks_seen=1317
  errors=0

P2.46a 设计阶段固定查询“P2.46a system_diagnostics_report 分区分层诊断 默认短概览 视觉区域 尚未实现”：
  project_results=5
  memory_results=0
  5 条均来自 main-agent-system-diagnostics-report-design 或 version-runlog 的 P2.46a 记录
  当时结果明确区分 P2.46a 设计完成与 P2.46b-d 尚未实现
  该记录是 P2.46a 历史检索验证，不覆盖本节前面的 P2.46b 当前实现状态
```

## v1.6 Development context current-state production connection

状态：已完成 P2.45c 实现、回归及 P2.45d 本地索引和主人 QQ live 验收。目标是只为主人私聊正式 `development_context_report` 接入固定当前状态锚点和多来源语义证据，不改变普通 `/agent`、`/agent-debug`、本地通用 DevContext 或普通聊天。

本次完成：

```text
src/plugins/ai_chat/rag/development_report.py：
  固定先从 ProjectDocRAG 读取 current-development-status 锚点，再生成一次 query embedding。
  项目语义候选固定至少 12 条，排除锚点 source，每 source 最多 1 条，最终最多 3 条。
  记忆继续只读检索，并与 anchor 1200 / project 1800 / memory 800 / format 400 分区预算合并。
  只返回 current_status_anchor_missing、current_status_anchor_failed、query_embedding_failed、project_retrieval_failed、memory_retrieval_failed 等固定类别，不把异常原文写进结果。

DevContextGraph：
  新增默认关闭的内部 development-report evidence 模式。
  只有 run_development_context_report_for_event 固定传 true；普通 MainAgent dev_context 继续使用原 retrieve_combined_rag。
  正式模式的图 metadata 只保留锚点布尔值/块数、项目来源数/结果数、记忆结果数、来源多样性标志和固定 warning/error 类别。
  原始 RagDocument/RagSearchResult 只存在于单次图执行闭包，报告 source 经过脱敏后进入 context_text，不写入 metadata 或任务持久化。

报告与持久化：
  当前状态锚点固定排在项目语义证据和开发侧记忆之前。
  主模型提示明确：锚点决定当前阶段、未完成项和明确延后项；语义文档只补设计/历史；记忆不能覆盖锚点。
  锚点与历史材料冲突时，历史材料必须按历史说明。
  确定性回退和受限主模型结果都追加固定的锚点/检索限制说明。
  agent_tasks.result 与 work_finished.output_summary 只新增“当前状态锚点：已加载/缺失”和“检索警告：N”，不保存详细报告、路径、分数、source id、片段或异常原文。
```

部分失败策略：

```text
锚点成功、embedding 或语义检索失败：使用锚点完成部分报告，任务可保持 done，并显示固定证据限制。
锚点缺失、语义证据成功：使用语义证据完成报告，并明确不能保证最新阶段。
没有任何证据且存在技术检索错误：DevContextGraph execution_failed，任务 failed。
干净地没有命中且没有技术错误：返回证据不足回退，不伪造系统故障。
不自动重试，不直接读文件兜底，不发送额外 QQ。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_development_context_report tests.test_main_agent_llm tests.test_owner_agent_work_runtime tests.test_memory_rag_qq_boundary -v
Ran 48 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 222 tests OK

既有非失败提示：FastAPI 测试依赖产生 StarletteDeprecationWarning。

更新快照和文档后执行 .\scripts\rebuild-rag-index.ps1 -ProjectDocs：
  scanned_files=59
  chunks_seen=1271
  errors=0

使用重建后的真实本地索引和固定问题“恢复 Owner Console 当前开发状态和下一步计划”执行正式证据检索干跑：
  anchor_included=true
  anchor_chunks=1
  anchor 包含 P2.45c、P2.40b 和 Owner Console 只读边界
  project_results=3
  project_sources=web-owner-console-read-model-design、owner-console-http-surface-audit、version-runlog
  memory_results=0
  warnings=0
  errors=0
  execution_failed=false
  evidence_chars=2720
```

主人 QQ live 验收：

```text
任务 #27 仍返回 P2.34 任务详情和 P2.39b 本地启动脚本等旧阶段材料，没有加载当前状态锚点策略。
重启 Bot 后再次执行固定命令，任务 #28 正确返回：
  当前处于 P2.45c，P2.45a-c 已完成。
  P2.45d 本地索引和固定问题检索已完成，live 是当时剩余验收项。
  P2.40b 未批准，业务页面继续初次加载加手动刷新。
  Owner Console 保持只读 GET，不开放 shell、Git、任意文件读写、Web 写操作或登录鉴权。
  证据与限制明确“当前状态锚点已加载”，并把旧 P2.34 材料降为历史参考。

任务 #28 详情持久化摘要：
  状态=已完成
  项目文档命中=2
  开发侧记忆命中=0
  当前状态锚点=已加载
  检索警告=0
  summary_mode=受限主模型结构化总结

任务详情和 work_finished 事件均未保存详细六字段报告、原始 RAG 片段、路径、source id、分数或异常原文。
项目文档最终命中 2 少于选择上限 3 属正常结果：来源多样性选择之后仍受 1800 字符项目证据预算约束。
```

边界：

```text
P2.45c 没有新增 work type、QQ 命令、Web endpoint、Web 写操作、登录鉴权、shell、Git、任意文件读写、未注册数据库写入或多步写自动化。
Owner Console 继续只读 GET；P2.40b 继续未启用；/docs、/redoc、/openapi.json 继续关闭。
本地干跑没有发送 QQ；live 命令由主人手动发送。P2.45 已完成，不新增任何自动 QQ 发送。
```

## v1.6 Development context diverse evidence policy

状态：已完成 P2.45b。目标是在不查询数据库、不调用 embedding、不接 QQ 生产路径的前提下，把研发报告所需的候选扩展、固定锚点排除、单来源去重和分区预算实现为独立纯策略。

本次完成：

```text
新增 src/plugins/ai_chat/rag/development_report.py：
  development_report_candidate_top_k：requested<=0 返回 0；正常至少 12；requested*4；最大 32。
  select_development_report_project_results：固定排除 current-development-status source；空 source 跳过；每 source 最多 1 条；最多 3 条；保持候选原 score 顺序。
  build_development_report_evidence：分别裁剪 current_status_docs、project candidates 和 memories，返回 CombinedRagResults。
  固定预算：anchor 1200、project 1800、memory 800、format reserve 400；与 P2.44 4200 source limit 启动时严格校验一致。
  输入使用不可变 RagDocument 替换裁剪，不修改原候选对象。

tests/test_development_report_retrieval.py：
  覆盖候选池边界、单来源霸榜、锚点语义重复、空 source、缺失锚点、三个分区精确限长、总证据 3800 和输入不变。
```

边界：

```text
纯策略模块没有数据库、embedding、QQ、Web、MainAgent 或 work runtime 依赖。
retrieve_combined_rag、DevContextGraph 和 development_context_report 尚未调用该策略。
当前 Agent 仍使用旧纯语义召回；不需要主人 QQ 测试。
不新增 shell、任意文件读写、数据库 schema、外部 reranker 或 Web 写操作。
P2.40b 继续未启用。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_rag_units -v
Ran 23 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_report_retrieval tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -q
Ran 214 tests OK

源码调用审计：除策略定义、RAG export 和测试外，没有生产模块调用 build_development_report_evidence 或 development_report_candidate_top_k。

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 59，扫描片段 1269，错误：无。

使用原问题“恢复 Owner Console 当前开发状态和下一步计划”执行真实本地 embedding + 前 12 候选纯策略演练：
  candidate_count=12
  前 12 候选实际只有 3 个不同 source，多条历史片段重复占位。
  selected_sources=web-owner-console-read-model-design、owner-console-http-surface-audit、version-runlog
  anchor_count=1
  evidence_anchor_count=1
  evidence_project_count=3
  evidence_content_chars=2721

该演练仅手动调用纯策略，没有修改 DevContextGraph/Agent 生产链，也没有发送 QQ。
```

## v1.6 Development context current-state anchor foundation

状态：已完成 P2.45a。目标是在不接入 QQ 正式任务、不修改语义排序的前提下，先建立固定当前状态快照、ProjectDocRAG 精确锚点读取和 anchor/semantic 结果模型分离。

本次完成：

```text
新增 docs/current-development-status.md：
  目标保持单 chunk，记录当前阶段、完成项、未完成项、明确延后、安全边界、下一步和证据限制。
  当前准确声明 P2.45a 已完成基础、P2.45b-c 尚未实现、P2.40b 未批准。

src/plugins/ai_chat/rag/project_docs.py：
  固定注册 CURRENT_DEVELOPMENT_STATUS_SOURCE_ID=docs/current-development-status.md。

src/plugins/ai_chat/rag/documents.py：
  list_rag_documents 增加内部 source_id 精确过滤，不暴露为 QQ/Web 参数。

src/plugins/ai_chat/rag/project_index.py：
  新增 retrieve_current_development_status(is_owner, max_context_chars)。
  函数不接受 source_id/path；只读取固定锚点，校验 owner 可见性、软删除、chunk 顺序和 1200 字符预算。

src/plugins/ai_chat/rag/combined.py：
  CombinedRagResults 新增默认空 current_status_docs。
  anchor 使用 RagDocument，不伪造 similarity score；只有非空时才由 debug formatter 显示。
  现有 retrieve_combined_rag 未调用锚点函数，普通格式化输出不变。
```

边界：

```text
尚未修改 DevContextGraph、MainAgent、owner work runtime 或 QQ adapter。
development_context_report 当前仍使用旧纯语义 project_docs + memories。
新增快照可能被普通语义检索机会性命中，但尚无固定锚点保证，也没有来源去重或分区预算。
普通聊天、普通 /agent dev_context、/agent-debug 和 Web 行为不变。
不新增任意路径读取、shell、Git 工具、文件写入、数据库 schema 或 Web endpoint。
P2.40b 继续未启用。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_rag_units -v
Ran 19 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary -q
Ran 134 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_rag_units tests.test_graph_runners tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -q
Ran 210 tests OK

覆盖固定 source id、无路径参数、owner scope、chunk 顺序、字符预算、软删除、单 chunk 快照、默认空 anchor 和现有格式输出不变。

docs/current-development-status.md 本地检查：
  773 characters
  1 个 Markdown heading
  重建后 1 个 ProjectDocRAG chunk

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 59，扫描片段 1266，错误：无。

真实索引固定读取验证：
  owner_anchor_count=1
  source_id=docs/current-development-status.md
  chunk_index=0
  content_chars=772
  non_owner_anchor_count=0

原始查询“恢复 Owner Console 当前开发状态和下一步计划”仍只召回 P2.34 与 P2.39b 历史片段。
这证明 P2.45a 尚未改变生产检索；P2.45b-c 的来源多样性和固定接入仍然必要。
```

## v1.6 Development context current-state retrieval design

状态：已完成 P2.45 设计，尚未修改运行时。主人私聊 live 结果证明 P2.44 能安全生成结构化报告，但同一问题只召回 P2.34 任务详情和 P2.39b 本地启动脚本；索引包含最新文档，缺口位于纯语义排序、单来源历史片段霸榜和上下文顺序截断。

本次设计：

```text
新增 docs/development-context-current-state-retrieval-design.md。
规划固定 docs/current-development-status.md 作为权威当前状态快照。
锚点 source id 由代码固定注册，用户、LLM、Web 和环境变量不能传任意路径。
锚点仍从 ProjectDocRAG 数据库读取，不在 QQ adapter/work runtime 直接打开文件。
正式 development_context_report 计划固定启用锚点；普通 /agent dev_context 第一刀保持现状。
语义检索计划先扩大内部候选池，再限制每个 source_id 最多 1 个片段。
报告 4200 字符输入计划拆为：锚点 1200、项目语义证据 1800、开发侧记忆 800、格式余量 400。
锚点、semantic project results 和 memories 在结果模型中分开，不伪造锚点相似度。
```

不采用：

```text
不只增大 top_k、降低 min_score 或扩大上下文。
不按整个 version-runlog 文件 mtime 判断章节新旧。
不让主模型从缺失的上下文猜最新状态。
不新增 shell、Git 工具、任意文件读取、目录扫描或自动状态生成。
```

实现拆分：

```text
P2.45a：当前状态快照和固定锚点读取基础，不接 QQ。
P2.45b：候选扩展、单来源去重和分区预算。
P2.45c：只接 development_context_report，并补持久化/入口/Owner Console 回归。
P2.45d：重建索引和主人手动 live 验收。
```

边界：

```text
本次仅文档设计，没有运行时代码、数据库 schema、QQ 命令、Web endpoint 或前端改动。
普通聊天继续不能进入 ProjectDocRAG。
Owner Console 继续只读。
P2.40b 继续未批准，业务页面保持手动刷新。
```

验证：

```text
git diff --check
Markdown fence check
OK

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 58，扫描片段 1264，错误：无。

.\scripts\rebuild-rag-index.ps1 -QueryDevContext "P2.45 当前状态锚点 来源多样性 分区预算 尚未实现" -TopK 4 -MaxContextChars 2200
项目文档命中 4，均能明确召回 P2.45 已完成设计、尚未实现，以及 P2.45a-d 的实现拆分；记忆命中 0。

原始“恢复 Owner Console 当前开发状态和下一步计划”查询仍会召回旧片段，符合本步仅设计、未修改运行时的预期。
```

## v1.6 MainAgent useful development context report

状态：已落地 P2.44。目标是让主人私聊显式研发上下文任务返回真正有用的“当前阶段、完成项、未完成项、安全边界和下一步”，同时继续禁止原始 RAG、路径、详细回复和异常文本进入任务记录。设计与边界见 `docs/main-agent-useful-development-context-report-design.md`。

本次完成：

```text
新增 src/plugins/ai_chat/development_context_report.py：
  定义固定六字段报告结构、JSON 严格解析、确定性回退、报告格式化和限长。
  总结输入最多 4200 字符；移除来源路径、检索元数据，并预脱敏密钥、Token、URL、本地路径和 .env。

src/plugins/ai_chat/graph/main_agent_llm.py：
  新增专用 development-context report system prompt 和直接 LLM 调用。
  不进入 ActionRequest planner，不附带工具，只接受固定 JSON；禁止编造提交/日期或输出原始 RAG、路径、标识符和异常文本。

src/plugins/ai_chat/__init__.py：
  DevContextGraph 成功后构造受限总结输入。
  MAIN_AGENT_USE_LLM=true 且有召回时执行一次固定 JSON 总结；模型关闭、无召回、调用或 JSON 失败时使用确定性回退。
  总结失败不把任务标成 failed，不重试，不新增消息发送。

src/plugins/ai_chat/owner_agent_work_runtime.py：
  详细 QQ 回复与持久化摘要分层。
  task.result 和 work_finished 继续只保存命中计数、总结方式和固定安全说明。
  详细回复再次脱敏并限制为 2400 字符，不持久化。
```

边界：

```text
唯一执行入口仍是主人私聊 /agent 执行研发上下文任务：<问题>。
普通聊天、群聊、非主人私聊、/agent-debug、Web Owner Console 和 MainAgent LLM 工具选择不能触发该 work runtime。
专用总结调用没有 ToolRegistry、ActionRequest、shell、文件写入、数据库写入、Web 写操作或 QQ 发送能力。
DevContextGraph 失败仍进入 failed；只有总结失败才安全回退为 done。
P2.40b 继续保持未启用，业务页面仍手动刷新。
```

验证：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_development_context_report tests.test_owner_agent_work_runtime tests.test_main_agent_llm tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -q
Ran 146 tests OK

cd web/owner-console
npm run guard:readonly
npm run typecheck
OK

.\scripts\rebuild-rag-index.ps1 -ProjectDocs
扫描文件 57，扫描片段 1230，错误：无。

.\scripts\rebuild-rag-index.ps1 -QueryDevContext "P2.44 研发上下文报告 当前状态 下一步 安全边界" -TopK 3 -MaxContextChars 1400
项目文档命中 3，包含 P2.44 已完成、详细回复/持久化分层和 P2.40b 仍需单独批准；记忆命中 0。

未向真实 QQ 会话发送测试消息，避免额外外部副作用。
```

## v1.6 MainAgent explicit development context task command

状态：已落地 P2.43c + P2.43d。目标是把 P2.43b 中唯一注册的只读 work runtime 接到严格的主人私聊 `/agent` 命令，并确认 Owner Console 只读展示 `running` 任务，不扩展任何写能力。

本次完成：

```text
src/plugins/ai_chat/owner_agent_work_runtime.py：
  新增严格命令解析：执行研发上下文任务：<query>（支持中英文冒号）。
  裸命令返回空 query；旧 /agent 任务 <目标> 和普通 /agent 查询不会匹配。
  新增安全结果渲染：只展示 task id、状态、受限报告摘要和任务详情入口。

src/plugins/ai_chat/owner_runtime_factory.py：
  新增 execute_development_context_report(event, query)，固定调用唯一注册的 development_context_report。

src/plugins/ai_chat/__init__.py：
  既有 /agent handler 在静态回复、旧任务命令和 MainAgent/LLM 路径之前检查显式研发上下文任务命令。
  强制 PrivateMessageEvent 与 is_owner(config, event)，不受 main_agent_allow_group 放宽影响。
  /agent-debug 不执行这个任务；一次命令只由既有 matcher 返回一次结果，不发送额外 QQ 消息。
  更新 /agent 帮助、状态和边界文字。

src/plugins/ai_chat/owner_console_read_runtime.py：
  running 任务的只读 next_action 为 monitor_running_task。
  既有 GET task list/detail 和 status=running 筛选可展示 created / work_claimed / work_started。
  不新增 Web 写 endpoint、执行、取消或重试按钮。
```

边界：

```text
只允许主人私聊显式 /agent 执行研发上下文任务：<问题>。
普通聊天、群聊、非主人私聊、/agent-debug、旧 /agent 任务 <目标> 和 MainAgent LLM 都不能触发该 runtime。
不新增审批、approval resume、后台 worker、队列、timer、自动 retry、shell、任意文件写入、未注册数据库写入、Web 写操作或额外 QQ 发送。
P2.40b 不因命令可用而自动开启；业务页面继续手动刷新，等待实际工作负载单独决定。
```

验证：

```text
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units -v
Ran 89 tests OK

.\.venv\Scripts\python.exe -m unittest tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary tests.test_persistence_units tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 125 tests OK

未向真实 QQ 会话发送测试消息，避免额外外部副作用。
```

## v1.6 MainAgent read-only work runtime registration

状态：已落地 P2.43b。目标是在 P2.43a 的状态机和持久化边界之上，提供唯一已注册的只读 work type 及 factory 注入，但不开放 QQ 或 Web 执行入口。

本次完成：

```text
新增 src/plugins/ai_chat/owner_agent_work_runtime.py：
  OwnerAgentWorkContext、AgentWorkSpec、OwnerAgentWorkRuntime 和 OwnerAgentWorkExecution。
  registry 固定只包含 development_context_report：read_local、query 参数、无需审批、结果上限 1600。
  execute 先验证 work type 与 query，再创建 pending task、claim 为 running、调用注入执行器、写入 done / failed。
  无效 query 或未注册 work type 不创建任务。
  DevContextGraph 原始输出只解析项目文档/开发侧记忆命中计数；task.result 和事件不持久化 RAG 片段、路径或异常原文。

src/plugins/ai_chat/owner_runtime_factory.py：
  新增 work_runtime(event)，只将 OwnerAgentContext 和 event-bound development_context_report executor 注入 runtime。

src/plugins/ai_chat/__init__.py：
  新增受 factory 注入的 run_development_context_report_for_event callback。
  callback 只调用现有 DevContextGraph 并返回命中计数，不返回原始 RAG 内容。
  未新增 /agent 命令、普通聊天入口或 Web endpoint。

tests/test_owner_agent_work_runtime.py：
  覆盖唯一 registry、成功持久化安全摘要、无效/未注册输入不建任务、失败不泄漏异常文本。
```

边界：

```text
不新增 QQ 命令，不从普通聊天调用 runtime，不让 MainAgent LLM 选择或指定 work type。
不新增后台 worker、队列、timer、自动 retry、shell、任意文件写入、未注册数据库写入、额外 QQ 发送或 Web 写操作。
不改变审批创建、确认、拒绝、approval_resume_enabled 或 owner_write_runtime。
Web Owner Console 仍只有 GET read model；P2.40b 仍等待 P2.43c 的真实 running 任务生命周期。
```

验证：

```text
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_owner_agent_work_runtime tests.test_main_agent_bridge tests.test_persistence_units -v
Ran 78 tests OK
```

## v1.6 MainAgent read-only work task persistence foundation

状态：已落地 P2.43a。目标是把 P2.43 的第一个正式只读工作任务状态机落实到持久化边界，但不接执行器、factory、QQ 命令或 Web 写操作。

本次完成：

```text
src/plugins/ai_chat/agent_tasks.py：
  新增 AGENT_TASK_RUNNING 并纳入任务状态筛选与状态标签。
  新增 claim_agent_task_for_work：scoped pending -> running 条件更新；已有 pending approval 的任务不能被 claim。
  claim 成功后在同一持久化事务写入 work_claimed 和 work_started；重复 claim 不再追加事件。
  新增 complete_agent_task_work / fail_agent_task_work：只允许 running -> done / failed，写入 work_finished / work_failed。
  task.result 限制 1600 characters；query_summary 限制 480 characters；event output/error summary 限制 240 characters。
  cancel_agent_task 改为 scoped status=pending 条件更新，避免取消与 claim 竞争时覆盖 running。

tests/test_persistence_units.py：
  覆盖 scoped claim、重复 claim、已有审批任务兼容、running 不可取消、成功/失败终态和摘要长度限制。
```

边界：

```text
尚未新增 OwnerAgentWorkRuntime、work registry、DevContextGraph executor、factory 注入或 /agent 执行研发上下文任务命令。
没有新 QQ 发送副作用、后台 worker、队列、定时器、自动 retry、shell、任意文件写入、未注册数据库写入或 Web 写操作。
现有审批创建、确认、拒绝和 approval_resume_enabled 恢复链路保持不变。
Web Owner Console 仍然只读；其现有 GET status filter 现在可以安全识别 running，但不新增任何 Web 操作。
P2.40b 仍等待 P2.43c 出现真实 running 任务生命周期后再评估。
```

验证：

```text
$env:PYTHONPATH='tests'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 24 tests OK

.\.venv\Scripts\python.exe -m unittest tests.test_owner_console_read_runtime tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 35 tests OK

.\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge tests.test_memory_rag_qq_boundary -v
Ran 60 tests OK
```

## v1.6 MainAgent first read-only work task design

状态：已落地 P2.43 设计。目标是不再把 `agent_tasks` 只当待办记录，而是先定义一个已注册、单步、只读、可审计的正式工作任务闭环；本步只做设计，不实现任务执行。

本次完成：

```text
新增 docs/main-agent-first-readonly-work-task-design.md：
  首个 work_type 固定为 development_context_report（研发上下文报告）。
  只允许主人私聊显式 /agent 执行研发上下文任务：<query> 入口。
  复用 DevContextGraph / dev_context 的只读依赖，不让 MainAgent LLM 自由选择工具。
  旧 /agent 任务 <目标> 继续只创建待办，不自动执行。

定义首个执行链路：
  validate -> create pending -> atomic claim running -> work_started
  -> registered read-only executor -> work_finished / work_failed
  -> bounded task.result 和 event summary。

定义状态和兼容策略：
  P2.43 实现时新增 running。
  首个只读任务使用 pending -> running -> done / failed，或 pending -> cancelled。
  既有审批任务继续使用现有 pending / approval status，不在本步引入 waiting_approval。
  running 任务不支持现有取消命令中断；失败后不自动 retry。

定义边界：
  不引入后台 worker、队列、定时器或独立进程。
  不新增 shell、文件写入、未注册数据库写入、额外 QQ 发送或 Web 写操作。
  不从 work runtime 调用 owner_write_runtime。
  不扩展 approval_resume_enabled。
  任务结果、事件输入和错误均需受限保存，不能持久化完整 RAG 原文、traceback 或敏感配置。

更新 Owner Console 路线：
  P2.40b 业务页面低频刷新延后到 P2.43c 有真实 running 任务生命周期之后再评估。
```

边界：

```text
本次只新增设计文档和路线记录，不修改 Python 或前端运行时代码。
当前没有正式 work runtime，没有新的 /agent 执行命令。
任务列表、审批和 Diagnostics 继续保持首次加载与手动刷新。
Web Owner Console v0 继续只读。
普通聊天继续不触发 MainAgent。
ProjectDocRAG 继续只在显式 /agent dev_context 中使用。
```

验证：

```text
文档设计变更，无运行时代码改动。
通过 DevContextGraph 查询现有 agent_tasks / approvals / owner runtime 基线后完成设计。
```

## v1.6 Web Owner Console controlled auto-refresh foundation

状态：已落地 P2.40a。目标是先实现自动刷新的受控基础设施和 AppShell health 低频检查，验证 timer、页面可见性、失败暂停和 AbortController 生命周期；本步不接业务页面轮询。

本次完成：

```text
新增 web/owner-console/src/hooks/useControlledAutoRefresh.ts：
  使用请求完成后再 setTimeout 的 completion-based 调度。
  不使用 setInterval。
  页面 hidden 时清 timer 并 abort 自动请求。
  页面恢复 visible 时，过期请求最多延迟 1 秒补一次。
  同一资源不并发、不积压 tick。
  手动刷新开始前暂停 timer，结束后再恢复调度。
  自动请求执行期间拒绝并发手动刷新。
  transient 失败按正常周期重试，连续 3 次后暂停。
  terminal 失败立即暂停。
  手动成功可以清失败状态并恢复调度。

新增 AutoRefreshContext / AutoRefreshControl / ownerConsoleRefreshPolicy：
  AppShell 内存态开关默认 false。
  浏览器完整刷新后恢复关闭。
  不写 localStorage、sessionStorage、cookie 或数据库。
  AppShell 开启后每 60 秒检查 GET /healthz。
  routes contract 不周期读取。
  顶部“最后刷新”调整为语义更准确的“连接检查”。

新增前端生命周期测试：
  Vitest + jsdom + @testing-library/react renderHook。
  覆盖默认关闭、周期调度、慢请求不重叠、hidden 暂停、visible 补一次、连续失败暂停、terminal 失败、手动恢复、隐藏/关闭 abort 和错误分类。

扩展 readonly guard：
  timer 和 visibility API 只能出现在受控 hook，测试文件除外。
  第一版禁止 setInterval。
  业务组件不能自行创建 timer 或监听 visibilitychange。

本地启动兼容修复：
  start-owner-console.ps1 在后台 Start-Process 前规范化当前进程 Path 环境项。
  避免部分启动环境同时携带 Path / PATH 时触发 duplicate-key 异常。
  后台启动由固定等待 2 秒改为最多等待 10 秒，并在进程提前退出时立即失败。
  避免冷启动超过 2 秒时被误报为启动失败。
  Path 值本身保持不变，不改变端口、launcher、日志或静态模式行为。
```

边界：

```text
Dashboard、Tasks、Approvals、Task Detail、Approval Detail 尚未接周期刷新。
Diagnostics、Memory、Access Control、Settings 继续手动刷新。
不新增后端 API，不修改 FastAPI app。
所有自动请求继续经过 ownerConsoleApi GET allowlist。
不新增 POST / PUT / PATCH / DELETE。
不新增登录/鉴权或 Web 写操作。
不触发 MainAgent、ProjectDocRAG、MemoryRAG 检索或 QQ 发送。
不开放 /docs、/redoc、/openapi.json。
```

验证：

```text
npm run guard:readonly
Owner Console frontend read-only guard passed.
Checked 24 TypeScript source files.

npm test
Test Files 1 passed
Tests 12 passed

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities
```

## v1.6 Web Owner Console read-only auto-refresh design

状态：已落地 P2.40 设计。目标是在 Web Owner Console 本地静态模式可用后，先定义低频、可控、页面可见时才运行的只读自动刷新策略，不直接实现轮询，也不引入 WebSocket / SSE。

本次完成：

```text
新增 docs/web-owner-console-readonly-auto-refresh-design.md：
  默认关闭自动刷新，用户显式开启后只在 AppShell 内存生命周期内生效。
  页面完整刷新后恢复关闭，不写 localStorage、sessionStorage、cookie 或数据库。
  页面隐藏时停止 timer 并取消自动请求，恢复可见时最多补一次。
  同一资源不允许并发或重叠请求。
  自动失败不立即重试；连续 3 次网络/5xx 失败后暂停。
  400 / 403 / 404 / contract mismatch 立即暂停自动刷新。
  手动刷新继续保留，手动成功后可以恢复调度。

定义页面策略：
  AppShell health 60 秒。
  Dashboard overview、Tasks / Task Detail、Approvals / Approval Detail 在 P2.43c 有真实 running 任务前均保持手动。
  届时如接入，业务页面候选周期为 60-120 秒；diagnostics 保持手动。
  Diagnostics / Memory / Access Control / Settings 保持手动。
  routes contract 只在首次加载和手动刷新时读取。

定义后续实现边界：
  使用单一 useControlledAutoRefresh hook。
  推荐请求完成后再 setTimeout，不使用固定节拍 setInterval。
  readonly guard 后续限制 timer 和 visibility API 只能出现在受控 hook。
  自动刷新仍只调用现有 ownerConsoleApi GET allowlist。
  不新增后端 endpoint、WebSocket、SSE、TanStack Query 或全局状态库。

同步文档：
  修正 local deployment design 中“不新增启动脚本”的过期描述。
  将 v0 runbook 的后端 contract 基线从 20 项更新为 22 项。
  更新 frontend stack、UI layout、readonly audit、contract guard、local deployment、runbook 和 frontend README。
```

边界：

```text
本次只做设计，不修改 web/owner-console/src 运行时代码。
当前自动刷新仍默认不存在，不产生周期请求。
不新增后端 API，不修改 FastAPI app。
不新增 POST / PUT / PATCH / DELETE。
不新增登录/鉴权。
不开放审批确认、拒绝或恢复执行。
不开放 /docs、/redoc、/openapi.json。
不改变 QQ / NoneBot / /agent 行为。
ProjectDocRAG 仍只允许在显式 /agent dev_context 中使用。
Web Owner Console v0 继续只读。
```

验证：

```text
设计前重新执行 Owner Console 后端 HTTP contract：
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 22 tests OK

本次无运行时代码改动，后续 P2.40a 实现时再增加 timer / visibility 生命周期测试并执行前端 guard、typecheck、build 和 audit。
```

## v1.6 Web Owner Console local start scripts

状态：已落地 P2.39b。目标是让 Web Owner Console 本地静态模式可以一键后台启动和停止，避免日常使用时每次手动输入 uvicorn 环境变量和启动命令。

本次完成：

```text
新增 scripts/start-owner-console.ps1：
  默认以本地静态模式后台隐藏启动 FastAPI。
  默认访问 http://127.0.0.1:8090/owner-console。
  检查 .venv\Scripts\python.exe 是否存在。
  检查 8090 是否已被占用。
  如果已存在 Owner Console 进程，直接提示已运行，不重复启动。
  如果端口被其他进程占用，拒绝启动并显示进程信息。
  检查 web/owner-console/dist/index.html 是否存在。
  支持 -Build 在缺少 dist 时先执行 npm run build。
  支持 -Foreground 前台调试。
  支持 -CheckOnly 做启动预检。
  输出日志到 logs/owner-console.out.log 和 logs/owner-console.err.log。

新增 scripts/stop-owner-console.ps1：
  只查找 python owner_console_fastapi_launcher:app 且匹配指定端口的进程。
  默认停止 8090 上的 Owner Console。
  支持 -Force 强制停止。
  不按端口杀无关进程。

更新文档：
  web/owner-console/README.md 增加一键启动/停止命令。
  docs/web-owner-console-v0-runbook.md 增加脚本用法、日志路径、前台调试方式和 -Build 说明。
  docs/web-owner-console-local-deployment-design.md 和 docs/web-owner-console-frontend-stack-design.md 标记 P2.39b 已完成。
```

边界：

```text
不新增后端 API。
不新增 Web 写操作。
不新增登录/鉴权。
不新增开机自启。
不注册 Windows Service。
不改变 QQ / NoneBot / /agent 行为。
脚本只服务本地 Owner Console 静态模式。
```

验证：

```text
PowerShell Parser ParseFile scripts/start-owner-console.ps1
OK

PowerShell Parser ParseFile scripts/stop-owner-console.ps1
OK

.\scripts\start-owner-console.ps1 -CheckOnly
Owner Console start preflight OK.

npm run guard:readonly
Owner Console frontend read-only guard passed.

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 22 tests OK
```

## v1.6 Web Owner Console optional local static mode

状态：已落地 P2.39a。目标是按 P2.39 设计实现可选本地静态模式，让 FastAPI 在显式开关打开时服务 `web/owner-console/dist`，同时继续保持 API 路径、页面路径和只读边界隔离。

本次完成：

```text
更新 web/owner-console/vite.config.ts：
  设置 Vite build base=/owner-console/。
  build 后资源路径变为 /owner-console/assets/...。

更新 src/plugins/ai_chat/owner_console_fastapi_app.py：
  新增 OWNER_CONSOLE_STATIC_ENABLED 开关，默认 false。
  新增 OWNER_CONSOLE_STATIC_DIR，默认 web/owner-console/dist。
  静态模式开启时，/owner-console 和 /owner-console/* 返回前端页面。
  /owner-console/assets/{file} 返回真实静态资源。
  缺失 assets 返回 404，不 fallback 到 index.html。
  /api/v1/owner-console/* 仍然只承载 JSON API。
  /docs、/redoc、/openapi.json 仍然关闭。
  静态模式开启但 index.html 不存在时拒绝创建 app。

更新测试：
  默认静态模式关闭时 /owner-console 仍是 404。
  静态模式开启时 /owner-console、/owner-console/tasks/1、/owner-console/approvals/1 返回 text/html。
  静态资源存在时返回资源，缺失时 404。
  POST /owner-console/tasks 返回 405。
  API route、POST API 405、docs/redoc/openapi 404 均不受静态 fallback 影响。
  launcher 测试显式关闭静态模式，避免本机环境变量干扰 smoke。

更新 .env.example 和 config/.env.example：
  增加 OWNER_CONSOLE_STATIC_ENABLED=false。
  增加 OWNER_CONSOLE_STATIC_DIR=web/owner-console/dist。

更新文档：
  docs/web-owner-console-local-deployment-design.md 标记 P2.39a 已实现。
  docs/web-owner-console-v0-runbook.md 增加本地静态模式启动方式。
  web/owner-console/README.md 增加静态模式命令。
  docs/web-owner-console-frontend-stack-design.md 追加 P2.39a 实现状态。
```

边界：

```text
不提交 dist 构建产物。
不新增 API endpoint。
不新增 POST/PUT/PATCH/DELETE。
不新增登录/鉴权。
不新增审批确认/拒绝页面。
不改变 QQ / NoneBot / /agent 行为。
不开放 /docs、/redoc、/openapi.json。
Web Owner Console v0 仍然只读。
```

验证：

```text
npm run guard:readonly
Owner Console frontend read-only guard passed.

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 22 tests OK
```

## v1.6 Web Owner Console local deployment design

状态：已落地 P2.39 设计。目标是先把 Web Owner Console 的本地部署形态、路径隔离、静态页面 fallback、docs/openapi 边界和只读 allowlist 说清楚，后续再决定是否实现 FastAPI 挂载 dist。

本次完成：

```text
新增 docs/web-owner-console-local-deployment-design.md：
  定义开发模式：FastAPI 8090 + Vite 5173 + Vite proxy。
  定义本地静态模式：FastAPI 可选挂载 web/owner-console/dist 到 /owner-console。
  明确 /api/v1/owner-console 只承载 JSON API。
  明确 /owner-console 只承载前端页面。
  明确 /owner-console/* 客户端路由刷新时 fallback 到 index.html。
  明确 /api/v1/owner-console/*、/docs、/redoc、/openapi.json 不 fallback 到 index.html。
  明确 /docs、/redoc、/openapi.json 继续关闭。
  明确静态页面当前仍只能调用 GET allowlist。
  补充实现优化和防偏建议：fallback 只服务 /owner-console，不做 API fallback，不做敏感配置注入。
  记录未来实现步骤和测试清单。

更新 docs/web-owner-console-v0-runbook.md：
  增加 P2.39 设计文档引用。
  调整后续路线为 P2.39a 静态模式实现、P2.40 只读自动刷新、P2.41 访问保护、P2.42 Web 审批操作。

更新 docs/web-owner-console-frontend-stack-design.md：
  追加 P2.39 本地部署方式设计状态。

新增 docs/juejin/15-web-owner-console-local-deployment-design.md：
  生成稀土掘金文章，说明为什么本地 Web 控制台要先设计部署边界、路径隔离、SPA fallback 和 GET allowlist。
```

边界：

```text
不修改 FastAPI app。
不修改 Vite 配置。
不生成或提交 dist。
不新增接口。
不新增前端写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot / /agent 行为。
```

验证：

```text
文档更新，无运行时代码改动。
```

## v1.6 Web Owner Console v0 runbook

状态：已落地 P2.38。目标是把 Web Owner Console v0 的后端启动、前端启动、页面验收、只读边界、自动化验证和常见问题整理成一份本地使用手册，方便后续继续做部署、鉴权或审批操作前有稳定基线。

本次完成：

```text
新增 docs/web-owner-console-v0-runbook.md：
  记录 Web Owner Console v0 定位。
  记录当前页面和详情页范围。
  记录后端 FastAPI launcher 启动方式。
  记录前端 Vite dev server 启动方式。
  记录页面手动验收顺序。
  记录 guard/typecheck/build/audit 和后端 HTTP contract 验证组合。
  记录只读边界和禁止加入的写入口。
  记录 backend disconnected、403、404、/docs 404、5173 端口占用等常见排障。

更新 web/owner-console/README.md：
  增加完整 runbook 引用。
```

边界：

```text
不修改 FastAPI 代码。
不修改 React 代码。
不新增接口。
不新增前端写操作。
不新增登录/鉴权。
不改变 QQ / NoneBot / /agent 行为。
```

验证：

```text
文档更新，无运行时代码改动。
P2.37 提交前已通过：
  npm run guard:readonly
  npm run typecheck
  npm run build
  npm audit
  owner console 后端 HTTP contract 20 tests OK
```

## v1.6 Web Owner Console frontend contract guard

状态：已落地 P2.37。目标是把 P2.36 的人工前端只读审计固化成本地自动检查，避免后续新增页面或 API client 时无意间扩大 Web Owner Console v0 的能力边界。

本次完成：

```text
新增 web/owner-console/scripts/readonly-guard.mjs：
  检查 fetch() 只出现在 ownerConsoleApi.ts。
  检查 HTTP method 只允许 GET。
  检查源码不引用 /openapi、/docs、/redoc。
  检查源码不出现 approveApproval / rejectApproval / resumeApproval 等写操作风格 API 名称。
  检查 ownerConsoleApi.ts 保留当前只读 allowlist。
  检查任务详情 / 审批详情动态路径仍使用正整数 ID 校验。
  检查主导航页面路由仍全部存在。
  检查 PlaceholderPage 没有被重新引入。

更新 web/owner-console/package.json：
  新增 npm run guard:readonly。

更新 web/owner-console/README.md：
  更新当前已接入的只读端点列表。
  增加 guard:readonly 检查命令。

新增 docs/web-owner-console-frontend-contract-guard.md：
  记录 guard 定位、命令、检查项、禁止项、验证组合和后续路线。

更新 docs/web-owner-console-frontend-readonly-audit.md：
  将人工审计命令升级为包含 npm run guard:readonly。
  标记 P2.37 guard 已落地。

更新前端栈和 UI 布局设计文档的后续实现状态。
```

边界：

```text
不新增后端接口。
不新增前端写能力。
不新增登录/鉴权。
不修改 FastAPI 运行时代码。
不触发 MainAgent。
不改变 QQ / /agent 行为。
guard 只是前端静态边界检查，不替代后端 HTTP contract 测试。
```

测试：

```text
npm run guard:readonly
Owner Console frontend read-only guard passed.

npm run typecheck
OK

npm run build
OK

npm audit
found 0 vulnerabilities

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_owner_console_fastapi_launcher tests.test_owner_console_fastapi_app tests.test_owner_console_http_contract -v
Ran 20 tests OK
```

## v0.1 基础聊天

状态：已落地。

已完成：

```text
QQ -> NapCatQQ -> OneBot v11 -> NoneBot2 -> DeepSeek/OpenAI-compatible chat -> QQ 回复。
私聊和授权群聊基础回复可用。
```

## v0.2 权限与安全

状态：已落地。

已完成：

```text
主人识别。
私聊白名单。
群白名单。
黑名单。
冷却。
消息长度限制。
主人管理命令。
```

## v0.3 SQLite 记忆

状态：已落地。

已完成：

```text
data/chatbot.db 保存聊天上下文。
重启后短期上下文保留。
陌生人私聊试用次数持久化。
/记忆状态。
/清空全部上下文。
```

## v0.4 会话摘要压缩

状态：已落地。

已完成：

```text
session_summaries 表。
自动压缩旧聊天原文。
手动压缩当前会话。
查看、删除、清空摘要。
摘要参与普通聊天上下文。
```

## v0.5 主人手动长期记忆

状态：已落地，并完成旧长期回忆摘要退出。

当前结论：

```text
主人手动长期事实/偏好记忆保留。
旧长期回忆摘要退出正式运行链路。
AI 不自动写长期记忆。
```

## v0.6 人格表达提示词

状态：已落地。

已完成：

```text
base chat-core 底层协议。
角色卡加载。
主人 / 非主人身份注入。
/查看角色卡。
/选择角色卡。
人格表达只控制说话方式，不写入记忆。
```

## v0.7 群聊主动回复

状态：已落地，默认关闭。

已完成：

```text
ENABLE_GROUP_AUTO_REPLY 开关。
规则评分器。
群全局冷却、主人冷却、用户冷却。
角色卡配套 auto-reply 配置。
白名单群内非 @ 消息可按规则评分决定是否回复。
```

仍不做：

```text
随机插话。
大模型判断是否主动回复。
跨群主动关联。
AI 自动写记忆。
```

## v0.8 主人通知与转告

状态：已落地。

已完成：

```text
/转告主人 内容。
/留言给主人 内容。
固定模板私聊主人。
长度限制。
敏感内容拒绝。
不调用 LLM。
不走角色卡。
不写长期记忆。
```

## v0.9 视觉识图与图片上下文

状态：已落地。

已完成：

```text
本地 Ollama 视觉模型。
私聊图片等待合并文字。
群聊图片缓存后按 @ 查询。
图片观察结果不可信，不能改写系统规则、主人身份或隐私边界。
VisionGraphRunner 已接入。
图片段支持 file / path / file_id / url。
支持 http(s)、data:image、本地绝对路径和 file://。
```

稳定运行经验：

```text
视觉模型建议使用 scripts/start-ollama-vision.ps1 启动。
该脚本会设置 OLLAMA_MODELS=D:\OllamaModels 并用 ollama serve 启动 11434。
如果托盘版 ollama app.exe 接管中文用户目录，可能出现 CLIP/mmproj 路径乱码和 HTTP 500。
出现 C:\Users\ÓêÔó 或 Failed to load CLIP model 时，先关闭托盘版 Ollama，再运行 start-ollama-vision.ps1。
```

## v1.0 稳定性与双通道诊断

状态：已落地第一批。

已完成：

```text
QQ 内诊断命令。
本地 diagnose.ps1。
配置状态。
最近错误。
视觉状态。
图片缓存状态。
错误日志清空。
DiagnosticsGraphRunner 已接入。
NotificationGraphRunner 已接入 /转告主人 链路。
```

已验证：

```text
/诊断、/配置状态、/视觉状态、/最近错误、/图片缓存状态、/记忆状态、/语音状态可用。
/转告主人 保持固定模板、长度限制、敏感内容拒绝和冷却，不调用 LLM。
```

## v1.1 语音输出

状态：已落地第一批。

已完成：

```text
本地 IndexTTS2。
主人私聊语音输出。
直接文本朗读。
上一条回复朗读。
语义语音回复。
TTS 服务自动拉起。
VoiceGraphRunner 已接入。
DIRECT_TEXT / LAST_REPLY / SEMANTIC_REPLY 三类语音请求已统一。
```

稳定运行经验：

```text
IndexTTS2 推理可能较慢，更多是显存、GPU 状态或冷启动问题，不是 VoiceGraph 链路问题。
如经常超时，优先检查 TTS 服务状态和 TTS_TIMEOUT_SECONDS。
```

## v1.2 记忆系统运行结构

状态：已落地。

当前结构：

```text
短期原文。
会话摘要。
空窗场景摘要。
主人手动长期记忆。
语义 MemoryRAG。
MemoryContextGraphRunner。
MemoryPersistGraphRunner。
MemoryAdminGraphRunner。
```

当前边界：

```text
AI 不自动写长期记忆。
长期事实和偏好由主人命令手动维护。
正式摘要和长期记忆可参与 MemoryRAG。
```

已完成 Graph 化：

```text
MemoryContextGraph：
  ENSURE_GAP_SCENE
  BUILD_MANUAL_MEMORY_CONTEXT
  RETRIEVE_SEMANTIC_MEMORY
  BUILD_HISTORY

MemoryPersistGraph：
  SAVE_USER_MESSAGE
  SAVE_ASSISTANT_MESSAGE
  SCHEDULE_COMPRESSION

MemoryAdminGraph：
  VALIDATE_ADMIN_REQUEST
  EXECUTE_ADMIN_OPERATION
  RENDER_ADMIN_REPLY
```

MemoryAdminGraph 已接入：

```text
/摘要状态
/查看摘要
/查看空窗摘要
/压缩当前会话
/压缩当前对话
/清空当前摘要
/清空当前对话摘要
/删除摘要
/清空全部摘要
/添加事实记忆
/添加偏好记忆
/查看长期记忆
/删除长期记忆
/清空全部上下文
```

## v1.3 LangGraph Agent Runtime

状态：部分落地，QQ live 只读 MainAgent 已验证。

已完成：

```text
RootGraph 显式分发。
RuntimeIntent.MAIN_AGENT。
DevContextGraph。
MainAgentGraph。
ActionRequest schema。
ToolRegistry v0。
ToolPolicyCheck。
CALL_MAIN_AGENT stub。
MainAgent LLM adapter。
LangChain MainAgent wrapper。
QQ /agent 只读入口。
/agent-debug 原始召回入口。
MAIN_AGENT_USE_LLM 显式开关。
真实 MainAgent LLM QQ live 验证。
tool_result 二次总结。
main_llm_failed 失败观测日志。
shell 越权请求拒绝验证。
/agent 状态主模型摘要。
/agent 状态不显示主模型接口。
常见 Main LLM 错误 QQ 侧友好化。
agent_tasks 表。
agent_task_events 表。
agent_approvals 表。
approval_requested 任务事件。
/agent 任务 <目标> 固定命令。
/agent 新增任务：<目标>、/agent 记录任务：<目标>、/agent 把“目标”加入任务 等固定本地别名。
/agent 任务状态 固定命令。
/agent 任务详情 <任务ID> 固定命令。
/agent 取消任务 <任务ID> 固定命令。
/agent 审批状态 固定命令。
/agent 审批详情 <审批ID> 固定命令。
```

已验证 live 行为：

```text
/agent 状态 可用。
/agent 查 MainAgentGraph 当前状态 可由真实主模型回复。
/agent-debug MainAgentGraph 当前状态 可返回原始 dev_context / CombinedRAG。
/agent 帮我执行 dir 会拒绝 shell，不执行命令。
/agent 任务 整理 MainAgentGraph 下一步计划 只创建 pending 任务记录。
/agent 新增任务：整理审批流 只创建 pending 任务记录。
/agent 把“整理审批流”加入任务 只创建 pending 任务记录。
不明确的自然句，例如“后面记得做一下审批流”，不会创建任务。
/agent 任务状态 只列出当前会话任务，不触发 LLM 或 dev_context。
/agent 任务详情 <任务ID> 只展示任务记录和事件，不触发 LLM 或 dev_context。
/agent 取消任务 <任务ID> 只把当前会话 pending 任务标记为 cancelled，并记录 cancelled 事件。
/agent 审批演练 <目标> 创建 dry-run 任务和 dry_run_write_file 审批请求，只用于实测审批闭环，不执行工具。
审批演练回复会明确显示 任务ID：#X 和 审批ID：#Y，并支持 审批详情 最新、确认 最新、拒绝 最新、任务详情 最新。
内部审批请求创建会写入 agent_approvals，并追加 approval_requested 任务事件，不触发执行。
PolicyEngine 返回 require_approval 时，create_tool_policy_checker 会触发 approval_required 中断，不进入 execute_tool。
/agent 审批状态 只列出当前会话审批，不触发 LLM 或 dev_context。
/agent 审批详情 <审批ID> 展示审批记录；不会触发执行。
/agent 确认 <审批ID> 把当前会话 pending 审批标记为 approved；仅 dry_run_write_file 会进入受控 dry-run resume。
/agent 拒绝 <审批ID> 只把当前会话 pending 审批标记为 rejected，并记录审批决定事件，不恢复执行。
/agent 审批详情 最新、/agent 确认 最新、/agent 拒绝 最新、/agent 任务详情 最新 可直接操作当前会话最近记录，避免手动查 ID。
MainAgentGraph 的 tool_request 现在通过 ToolRegistry 校验注册工具、参数和风险等级；真实 registry 只向 LLM 暴露 dev_context。
dry_run_write_file 只在显式 dry-run/test registry 中注册，llm_visible=false，risk_level=write_local，进入 approval_required 中断但不执行真实写入。
```

当前 `/agent 状态` 会显示：

```text
入口是否开启。
只读模式。
可用工具 dev_context。
ToolRegistry v0，当前真实可见工具仍只有 dev_context。
任务状态和事件记录能力。
审批请求生成、查看、确认和拒绝能力；确认后仅 dry-run 工具会受控恢复。
Main LLM 是否接入 ActionRequest 生成。
主模型名。
主模型 Key 是否配置。
```

`MAIN_LLM_API_KEY` 原文不在 QQ 状态、文档或日志中显示；`MAIN_LLM_BASE_URL` 也不在 `/agent 状态` 中展示，只保留在本地配置和脱敏错误日志中。

Main LLM 常见错误会在 QQ 侧转换为中文短提示：

```text
Connection error -> 主模型连接失败，请检查 MAIN_LLM_BASE_URL、网络、代理或中转服务。
timeout -> 主模型请求超时。
401 / unauthorized -> 主模型鉴权失败。
404 / model_not_found -> 主模型或接口不存在。
429 / quota / rate limit -> 主模型额度或限流异常。
```

当前仍不开放：

```text
shell 工具。
写文件工具。
数据库写工具。例外：/agent 任务固定命令和内部审批记录链路只写 agent_tasks / agent_task_events / agent_approvals，不由 MainAgent/LLM 执行。
额外 QQ 发送。
Agent API。
多步 agent loop。
真实任务执行链路。
真实审批恢复执行链路。
```

### 2026-07-04 Route B dry-run resume update

```text
MainAgent Route B now supports a narrow approval resume path for dry-run tools.
/agent approve/confirm still scopes approvals by current session and user.
Only approved dry_run_write_file approvals can resume.
The resume path uses ToolRegistry to require and validate the registered tool.
It records tool_resume_started and tool_resume_finished task events.
It marks the drill task done with the dry-run ToolResult.
It is idempotent: repeated resume attempts do not execute again.
Unapproved approvals, non-current-session approvals, repeated resume attempts, and non-dry-run tools do not resume.
No real file writes, shell commands, database business writes, extra QQ sends, or LLM-visible write tools were opened.
QQ live verified:
  /agent approval drill xxx
  /agent confirm latest
  /agent task detail latest
Result:
  task reached done
  events include approval_requested, approval_approved, tool_resume_started, tool_resume_finished
  dry_run_write_file returned side_effect: none
```

### 2026-07-04 Approval Resume Runner safety gate

```text
The approval resume path has been extracted behind resume_agent_approval(...).
resume_agent_approval_dry_run(...) remains as a compatibility wrapper.
ToolSpec now has approval_resume_enabled, default false.
dev_context keeps approval_resume_enabled=false.
dry_run_write_file has approval_resume_enabled=true, requires_approval=true, llm_visible=false.
/agent confirm now calls the generic registry-backed resume runner.
The runner requires:
  current session/user scoped approval
  approved approval status
  registered enabled tool
  approval_resume_enabled=true
  validated ToolRegistry arguments
Repeated resume attempts remain idempotent.
Tools registered without approval_resume_enabled do not resume even after approval.
No real write, shell, database business write, extra QQ send, or LLM-visible write tool was opened.
```

## v1.4 语义记忆检索与项目文档 RAG

状态：核心能力已落地，并已被 MainAgentGraph 只读调用。

已完成：

```text
MemoryRAG。
ProjectDocRAG。
CombinedRAG。
DevContextGraph。
ProjectDocRAG 本地索引脚本。
QQ 侧 MemoryRAG 调试命令。
MainAgentGraph 通过 dev_context 只读查询项目上下文。
```

QQ 侧 MemoryRAG 已验证：

```text
/RAG状态
/记忆检索 查询内容
/重建记忆索引
普通聊天 MemoryRAG 自动注入
旧问题问答可通过 RAG 召回补充
```

当前推荐参数形态：

```text
ENABLE_MEMORY_RAG=true
MEMORY_RAG_INJECT_IN_CHAT=true
MEMORY_RAG_TOP_K=5
MEMORY_RAG_MIN_SCORE=0.55
MEMORY_RAG_MAX_CONTEXT_CHARS=1600
MEMORY_RAG_OWNER_ONLY_DEBUG=true
```

如果召回偏泛，可观察后再收紧为：

```text
MEMORY_RAG_TOP_K=3
MEMORY_RAG_MIN_SCORE=0.60
MEMORY_RAG_MAX_CONTEXT_CHARS=1000
```

ProjectDocRAG 扫描范围：

```text
README.md
docs/**/*.md
prompts/base/**/*.json
prompts/persona-cards/public/**/*.md
```

ProjectDocRAG 明确排除：

```text
.git
.venv
data
docs-archive
logs
prompts/persona-cards/private
temp_audio
tools
tts-validation
voice-samples
__pycache__
.env*
*.db
*.sqlite
*.sqlite3
*.log
```

CombinedRAG 稳定边界：

```text
只用于本地脚本、开发侧工具、Codex 上下文恢复和 MainAgentGraph dev_context。
不注册 QQ 普通命令。
不进入普通聊天上下文。
输出保持项目文档召回和记忆召回分区。
```

当前边界：

```text
MemoryRAG 可以进入普通聊天上下文。
ProjectDocRAG 不进入普通聊天上下文。
ProjectDocRAG 只在本地开发命令或 /agent owner 显式命令下通过 dev_context 查询。
```

保留手册：

```text
docs/project-rag-usage.md
```

## MainAgent owner_read_command 语义只读管理工具

状态：第一批只读语义主人命令骨架已落地，保留原 QQ 斜杠命令。

本次完成：

```text
ToolRegistry 新增 owner_read_command 可见工具。
owner_read_command 仅开放只读诊断/状态类命令：
  diagnostics
  config_status
  vision_status
  recent_errors
  image_cache_status
  memory_status
  memory_retrieval
  bot_status
  rag_status
  summary_status
  view_summaries
  view_gap_scene_summaries
  view_long_term_memory
  view_persona
  tts_status
  group_whitelist
  private_whitelist
  blacklist
/agent 语义入口可把“帮我看一下最近错误”等请求映射到 owner_read_command。
/agent 语义入口可把“记忆检索 Route B 审批流”“查一下记忆里有没有审批流”等请求映射到 memory_retrieval，并复用原 MemoryRAG 检索图。
ToolRegistry 新增 agent_task_read 可见工具。
agent_task_read 仅开放任务/审批只读查询：
  list_tasks
  task_detail
  list_approvals
  approval_detail
可语义触发：
  /agent 看看任务表
  /agent 最新任务详情
  /agent 有没有待审批的东西
  /agent 最新审批详情
语义只读工具现在在 LLM/dev_context 前置拦截。
当 MAIN_AGENT_USE_LLM=true 时，明确命中的只读管理/任务查询不会先交给主模型去做项目 RAG 检索。
owner_read_command / agent_task_read 的工具结果现在直接返回，不再交给 LLM 二次总结。
原因：角色卡查看等管理输出如果被 LLM 总结，模型可能模仿角色卡语气；管理命令必须保持操作台式原文输出。
任务语义增加“任务卡/任务表/任务列表”说法，默认映射到 list_tasks。
原有 /诊断、/配置状态、/视觉状态、/最近错误、/图片缓存状态、/记忆状态 继续保留。
QQ RuntimeState 已把 message_id、session_key、session_type、user_id、actor_role、group_id、raw_text 注入 ToolContext.metadata。
```

边界：

```text
owner_read_command risk_level=read_local。
agent_task_read risk_level=read_local。
仍然只允许主人私聊默认执行。
owner_read_command 本身不清空日志，不清空图片缓存，不写数据库，不改白名单/黑名单，不切换角色卡。
agent_task_read 不创建任务、不取消任务、不确认审批、不拒绝审批、不恢复执行。
有副作用的主人管理命令必须走 owner_write_command 审批任务链路。
ProjectDocRAG 仍只通过 dev_context 进入 /agent，不进入普通聊天。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_llm -v
```

## MainAgent owner_read_command 第二批只读工具

状态：第二批只读主人控制台查询已接入 owner_read_command，仍保留原 QQ 固定命令。

本次完成：

```text
新增只读命令：
  role_card_list
  model_config_status
  access_overview
  rag_index_detail
  main_agent_observations

可语义触发：
  /agent 看看有哪些角色卡
  /agent 角色卡列表
  /agent 看看模型配置
  /agent 当前主模型是什么
  /agent 看看访问控制
  /agent 权限状态
  /agent 看看项目文档索引
  /agent 看看记忆索引
  /agent RAG 索引详情
  /agent MainAgent 最近失败
  /agent 最近 agent 观测

role_card_list 只展示角色卡 key/title 和当前启用项，不输出角色卡正文。
model_config_status 只展示模型、base_url、超时和 Key 是否配置，不泄露 Key。
access_overview 汇总主人配置状态、私聊/群聊开关、白名单/黑名单数量和列表。
rag_index_detail 汇总 MemoryRAG / ProjectDocRAG 开关、embedding 配置和 rag_documents/rag_embeddings 分 namespace 统计。
main_agent_observations 从错误日志里筛选 MainAgent/LLM/tool summary 相关观测，方便定位语义命令是否误路由。
```

边界：

```text
全部 risk_level=read_local。
不切换角色卡，不修改模型配置，不修改白名单/黑名单，不重建索引，不清理日志。
普通聊天不触发这些工具。
本地管理工具结果继续直接返回，不交给 LLM 二次总结。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
```

## RootGraph / CHAT 只读观测入口

状态：RootGraph 普通聊天路径新增最近一次观测快照，并接入 `/agent` 只读语义工具。

本次完成：

```text
新增只读命令：
  root_graph_observations

可语义触发：
  /agent RootGraph 最近观测
  /agent RootGraph 状态
  /agent 看看普通聊天路由
  /agent chat commit 状态

普通聊天经 RootGraph CHAT 路径执行后，会记录最近一次非正文观测快照。
快照包含会话类型、消息 ID、是否有文本、是否有图片、Actor role、policy、route、context、commit、chat_runtime、chat_access_policy、chat_commit、shadow snapshot/validation 摘要。
快照不记录用户原文、不记录 LLM 回复正文，只记录布尔值、长度、计数和阶段信息。
```

边界：

```text
risk_level=read_local。
仅主人私聊默认执行。
不触发普通聊天，不调用 ChatGraph，不修改白名单/黑名单，不清理日志，不切换角色卡。
该入口用于回答“上一条普通聊天为什么处理/未处理、路由到哪里、副作用提交到哪一步”。
旧固定命令继续保留。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
```

## MainAgent owner_write_command 审批门控主人管理工具

状态：有副作用语义主人命令已接入 ToolRegistry 和审批恢复链路，保留原 QQ 固定命令作为 fallback。

本次完成：

```text
ToolRegistry 新增 owner_write_command 可见工具。
owner_write_command risk_level=write_local，requires_approval=true，approval_resume_enabled=true。
当前开放审批门控本地命令：
  clear_image_cache
  clear_error_log
  select_persona
  add_fact_memory
  add_preference_memory
  clear_session_summaries
  delete_session_summary
  allow_group
  deny_group
  allow_private
  deny_private
  block_user
  unblock_user

/agent 语义入口可把下列请求映射为 owner_write_command：
  /agent 帮我清空图片缓存
  /agent 帮我清空错误日志
  /agent 帮我选择角色卡 moyan
  /agent 帮我添加事实记忆 主人喜欢先看结论
  /agent 帮我添加偏好记忆 技术讨论先给结论
  /agent 帮我清空当前摘要
  /agent 删除摘要 123
  /agent 把群 123456 加入群白名单
  /agent 把群 123456 移出群白名单
  /agent 把用户 10001 加入私聊白名单
  /agent 把用户 10001 移出私聊白名单
  /agent 把用户 10002 加入黑名单
  /agent 解除拉黑 10002

命中后不会立刻执行工具，而是创建 agent_tasks + agent_approvals，并返回审批提示。
/agent 确认 <审批ID> 或 /agent 确认 最新 会在确认后通过注册表恢复执行对应工具。
恢复执行会写入 tool_resume_started / tool_resume_finished 事件。
重复确认同一个审批不会重复执行；已有 tool_resume_finished 时直接跳过。
拒绝审批后不会恢复执行。
```

边界：

```text
owner_write_command 仍只允许主人私聊走 /agent 入口。
普通聊天不触发 ProjectDocRAG，也不触发主人管理工具。
选择角色卡必须带明确 target 参数，确认审批后才调用 select_role_card。
添加事实/偏好长期记忆必须带明确 content 参数；/agent 私聊语义工具确认后只写 owner 用户自身长期记忆。
旧 /添加事实记忆、/添加偏好记忆 固定命令继续保留；需要群场景 fact 记忆时仍由旧命令兜底。
清空当前摘要只删除当前会话 session_summaries，不清空全部摘要。
删除摘要必须带数字 summary_id，且只删除当前会话中匹配的 session_summary。
动态黑白名单修改必须带数字 target；/agent 私聊语义工具确认后只修改 data/access.json 动态访问控制，不修改 .env 静态配置。
旧 /加入群白名单、/移出群白名单、/加入私聊白名单、/移出私聊白名单、/加入黑名单、/移出黑名单 固定命令继续保留。
旧 /启用本群、/禁用本群 仍由群聊固定命令兜底；/agent 当前仍是主人私聊入口，不支持无数字群号的“本群”语义写入。
不开放清空全部上下文、清空全部摘要、删除记忆、shell、任意文件写入或未注册数据库写入。
LLM 即使生成 tool_request，也必须通过 ToolRegistry 参数校验和 ToolPolicyCheck 审批中断。
只有注册且 approval_resume_enabled=true 的工具可以在审批确认后恢复。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge tests.test_persistence_units tests.test_main_agent_llm tests.test_memory_rag_qq_boundary -v
Ran 75 tests OK
```

## MainAgent agent_task_command 语义任务/审批控制面工具

状态：任务和审批控制面已接入确定性语义工具；原固定命令继续保留。

本次完成：

```text
ToolRegistry 新增 agent_task_command 工具。
agent_task_command risk_level=internal，llm_visible=false。
它不出现在主模型工具契约里，只由本地确定性语义分类器命中。

当前开放命令：
  create_task
  cancel_task
  approve_approval
  reject_approval
  create_approval_drill

可语义触发：
  /agent 帮我创建一个任务：整理审批流
  /agent 把整理 Route B 加入任务
  /agent 取消最新任务
  /agent 帮我确认最新审批
  /agent 拒绝审批 #7
  /agent 创建审批演练：写入版本日志

agent_task_command 在 agent_task_read 前面拦截，避免“确认最新审批”被误判成审批详情查询。
确认审批时沿用现有审批恢复链路；如果对应审批已执行过，不会重复执行。
```

边界：

```text
只允许主人私聊 /agent 入口。
不交给 LLM 自由选择，避免模型误确认或误取消。
只操作 agent_tasks / agent_task_events / agent_approvals 控制面记录。
确认审批可能恢复已经批准的注册工具，但仍受 approval_resume_enabled 和幂等事件保护。
普通聊天不触发 agent_task_command。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
```

## MainAgent 工具状态/能力列表

状态：QQ 侧已新增自描述能力面板，方便查看当前开放工具和边界。

本次完成：

```text
新增静态命令：
  /agent 工具状态
  /agent 能力列表
  /agent 工具列表

返回内容包括：
  dev_context
  owner_read_command
  agent_task_read
  agent_task_command
  owner_write_command
  dry_run_write_file（隐藏演练工具）

每个条目展示：
  风险等级
  LLM 可见性
  是否需要审批
  用途
  示例命令

同时明确当前不开放：
  shell
  任意文件写入
  未注册数据库写入
  删除长期记忆
  清空全部摘要
  清空全部上下文
```

边界：

```text
工具状态只是静态只读说明，不触发 ToolRegistry 执行，不调用 LLM，不写数据库。
普通聊天不触发；仅 /agent 静态命令入口返回。
```

测试：

```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
```

## v1.5 RootGraph CHAT 接入第一步

状态：已落地第一步，普通聊天入口开始经过 RootGraph 的 CHAT intent 分发。

本次完成：
```text
handle_chat 在非语义语音路径下改为 run_chat_via_root_graph。
RootGraph CHAT handler 复用现有 run_legacy_chat_session，不重写聊天主体逻辑，不改变现有 ChatGraph/legacy 分支的回复、持久化和压缩行为。
shadow_chat production_route 新增 root_graph_chat，用于标识普通聊天已从 RootGraph 外层进入。
run_legacy_chat_session 可接收预构建 shadow_state，并返回最终 ChatState，便于 RootGraph 同步 response、error 和 chat_graph artifact。
RootGraphRunner 新增 passthrough_exceptions，QQ matcher.finish / matcher.pause / matcher.reject 等 NoneBot 控制流不会被误包装成 Agent Runtime error。
语义语音路径暂时保留旧入口，避免 matcher.finish 控制流和语音提交链路在本步被扩大改动。
RootGraph 对 CHAT 的 response 使用 should_reply=false，因为实际 QQ 回复仍由现有聊天运行链路发送，避免重复回复。
```

边界：
```text
ProjectDocRAG 仍不进入普通聊天。
普通聊天仍不触发 MainAgent ToolRegistry 或主人管理工具。
RootGraph 当前只是普通聊天的外层调度和观测入口，尚未接管 check_access / check_message_limits / commit_side_effects 的全部职责。
旧固定命令继续由现有 NoneBot matcher 兜底。
```

测试：
```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners tests.test_graph_adapters_and_shadow -v
Ran 54 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 241 tests OK
```

## v1.5 RootGraph CHAT 权限前置第一步

状态：已落地。普通聊天在解析图片和进入聊天主体前，会先构建 `chat_access_policy` artifact，并交给 RootGraph hard policy 判定。

本次完成：
```text
新增 chat_access_policy artifact，记录普通聊天 preflight 的 allow/deny、reason、should_reply、response_text、actor_role、session_type、消息长度、限速等信息。
RootGraph hard_policy_gate 现在能读取 chat_access_policy；当 allow_dispatch=false 时，直接把 CHAT 路由改为 IGNORE，不进入聊天 handler。
已前置的普通聊天策略包括：
  私聊/群聊是否开启
  黑名单
  owner / 私聊白名单 / 陌生私聊试用
  群白名单
  私聊试用次数是否耗尽
  消息长度限制
  普通聊天限速
普通聊天非语义语音路径现在先构建 RuntimeState，再经 RootGraph CHAT 分发；图片上下文解析被移动到 CHAT handler 内，在 policy 放行后才执行。
旧 prepare_chat_request / check_access / check_message_limits 仍保留，并继续服务语义语音等旧路径，作为防御性兜底。
```

边界：
```text
本步没有把 owner 管理工具暴露给普通聊天。
ProjectDocRAG 仍不进入普通聊天。
RootGraph 只做硬策略和分发，不接管 ChatGraph 内部 prompt、MemoryRAG、持久化和压缩。
语义语音路径仍暂时走旧 prepare_chat_request，后续单独收敛。
```

测试：
```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners tests.test_graph_adapters_and_shadow tests.test_memory_rag_qq_boundary -v
Ran 60 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 243 tests OK
```

## v1.5 RootGraph CHAT 提交观测第一步

状态：已落地。RootGraph 仍不搬迁聊天数据库写入和 QQ 发送动作，但现有聊天链路会把关键提交结果写入 `chat_commit` artifact，RootGraph `commit` artifact 会统一汇总。

本次完成：
```text
新增 chat_commit artifact，用于记录普通聊天已完成的提交类动作。
普通 legacy chat 路径在 finalize_chat_result 中记录：
  persisted_turn_saved
  trial_updated
  qq_reply_sent
  tts_candidate_updated
  compression_scheduled
  reply_chars / stored_user_chars / stored_assistant_chars
ChatGraph runtime 路径在各 side-effect callback 中记录：
  persisted_turn_saved
  trial_updated
  tts_candidate_updated
  compression_scheduled
  voice_response_sent / voice_send_suppressed
render_chat_result 记录普通文本回复是否已经发送。
图片上下文等待合并时记录 image_context_deferred，不进入聊天主体。
RootGraph commit artifact 现在汇总：
  chat_reply_sent
  chat_voice_sent
  chat_persisted
  chat_trial_updated
  chat_compression_scheduled
  chat_tts_candidate_updated
  chat_image_context_deferred
  chat_runtime_stage
```

边界：
```text
本步只增加观测，不改变现有 QQ 回复、数据库持久化、试用次数、压缩调度和 TTS 候选更新的执行位置。
RootGraph 仍不直接执行聊天提交动作，只读取 handler 写入的 artifact。
ProjectDocRAG 仍不进入普通聊天。
```

测试：
```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners -v
Ran 44 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 244 tests OK
```

## v1.5 RootGraph error artifact 与审批恢复 metadata 清理

状态：已落地。RootGraph 在已有 `root_graph.error` 之外，新增结构化 `error` artifact；审批恢复上下文的 `resume_mode` 命名也从 dry-run 专用语义收敛为通用审批恢复语义。

本次完成：

```text
RootGraphRunner 在以下场景写入 artifacts["error"]：
  policy 拒绝，例如 chat_access_policy 阻断 CHAT 分发
  dispatch handler 抛出异常
  handler 自身设置 state.error 但没有抛异常

error artifact 字段：
  source
  message
  route
  policy_decision
  dispatched
  should_reply
  response_text_set

该 artifact 不记录用户原文，不记录 LLM 回复正文，只记录错误来源、路由和响应布尔状态。
root_graph.error 继续保留，兼容已有 RootGraph 最近观测和测试。

审批恢复 ToolContext.metadata：
  resume_mode=approval_resume
  resume_tool_name=<approval.tool_name>

这样 owner_write_command 恢复执行时不再被标成 dry_run；dry_run_write_file 仍保持无副作用演练工具语义。
```

边界：

```text
本步不改变 RootGraph 路由策略。
本步不迁移聊天副作用执行位置。
本步不新增任何 LLM 可见工具。
本步不开放 shell、任意文件写入、任意数据库写入或额外 QQ 发送。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners -v
Ran 45 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_persistence_units -v
Ran 15 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_main_agent_bridge -v
Ran 42 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 245 tests OK
```

## v1.5 RootGraph 最近观测展示 error artifact

状态：已落地。`/agent RootGraph 最近观测` 现在会展示 RootGraph 结构化 `error` artifact 的摘要。

本次完成：

```text
RootGraph/CHAT 观测快照新增 error_artifact。
最近观测输出在存在 error_artifact 时展示：
  source
  route
  policy
  dispatched
  should_reply
  response_text
  message

该输出仍不记录用户原文，也不记录 LLM 回复正文。
旧 observation.error fallback 保留；没有结构化 error_artifact 时继续按旧 Error 行输出。
```

边界：

```text
本步只增强只读观测输出。
不改变 RootGraph 路由、权限、提交、副作用位置或审批策略。
普通聊天仍不触发 MainAgent 工具。
```

测试：

```text
$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 5 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest tests.test_graph_runners.RootGraphRunnerTests -v
Ran 12 tests OK

$env:PYTHONPATH='tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 246 tests OK
```

## v1.5 视觉电脑截图上下文与低质量输出兜底

状态：已落地。电脑截图经 `qwen2.5vl:3b` 识别时，默认 Ollama 上下文可能触发重复符号输出；本次将视觉请求默认 `num_ctx` 提升到 16384，并把 `@@@@@@@@...` 这类低信息量重复内容判为视觉失败。

本次完成：
```text
新增 VISION_NUM_CTX，默认 16384。
Ollama /api/chat 视觉请求写入 options.num_ctx。
新增低质量视觉描述检测，重复符号输出不再写入聊天上下文。
/配置状态 和 /视觉状态 展示视觉上下文配置。
.env.example、config/.env.example、docs/runbook.md 补充 VISION_NUM_CTX。
```

边界：
```text
不改变 RootGraph 路由、聊天权限、图片缓存策略和安全脱敏策略。
不引入图像处理依赖，不做截图切片；本次只修 Ollama 上下文和坏输出兜底。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_vision_voice_units -v
Ran 19 tests OK
```

## v1.5 RootGraph 最近观测展示 vision detail

状态：已落地。`/agent RootGraph 最近观测` 现在会展示普通聊天图片链路的非正文观测字段，便于定位图片未缓存、未解析、模型返回低质量内容或视觉上下文不足等问题。

本次完成：
```text
chat_commit 新增图片上下文观测字段：
  image_context_has_context
  image_context_url_count
  image_context_should_continue

chat_commit 新增视觉描述统计字段：
  vision_description_count
  vision_error_count
  vision_low_quality_count
  vision_num_ctx

/agent RootGraph 最近观测 新增 Vision detail 行：
  context
  urls
  continue
  descriptions
  errors
  low_quality
  num_ctx
```

边界：
```text
只记录计数、布尔值和上下文配置。
不记录图片 URL。
不记录图片描述正文。
不改变 RootGraph 路由、聊天权限、图片缓存策略或视觉模型调用策略。
```

测试：
```text
$env:PYTHONPATH='tests'; .\.venv\Scripts\python.exe -m unittest tests.test_memory_rag_qq_boundary -v
Ran 6 tests OK
```

## MainAgent external-read：Tavily 配置与 executor 装配

状态：生产条件接线已打开，认证 executor 和主人 QQ strict command live 均已完成。

本次完成：
```text
新增 TAVILY_API_KEY（配置 repr 脱敏）和 TAVILY_TIMEOUT_SECONDS=10。
现有 OpenAI/Main/Chat API Key 同步改为不进入配置 repr。
新增未注册的 create_tavily_external_read_executor 装配 factory。
固定把 ExternalSearchExecution 映射为 ExternalReadReportPayload。
成功和无结果均保持 external_request_count=1；无二次请求、retry 或 fallback。
fake transport 集成测试验证 Basic 固定参数、最多 3 条、关闭 answer/raw content/images。
测试验证 Key、raw_content、完整 URL 不进入临时 report。
为内部 AutoBackend 路径声明 httpx 0.28.x / httpcore 1.0.x 兼容窗口。
最新定向配置/Tavily/QQ 边界/MainAgent bridge 92 tests OK。
全量回归 465 tests OK；115 个 Python 文件 AST/尾随空白检查通过；git diff --check 通过。
生产 OwnerRuntimeFactory 已增加延迟、条件接线：默认关闭时不导入 Tavily HTTP 模块。
开关 true 但 Key/超时非法或 Tavily 依赖导入失败时失败关闭，不创建任务或网络请求。
TAVILY_TIMEOUT_SECONDS 非数字时配置加载为安全哨兵 0，Bot 可启动但 executor 保持未配置。
普通聊天和 Main LLM ToolRegistry 仍无 external-read 工具。
```

生产边界：
```text
ENABLE_AGENT_WEB 已由主人明确批准在本地 .env 打开。
真实 TAVILY_API_KEY 仅存在于被 Git 忽略的本地 .env；示例文件继续为空。
插件入口只在 ENABLE_AGENT_WEB=true 时延迟导入并条件注入 Tavily executor。
普通聊天和 Main LLM ToolRegistry 不可触发。
已按主人预算发起唯一一次 Tavily Basic 认证请求：3 条结果、3 个来源、0 丢弃、external_request_count=1。
认证 harness 与随后主人 QQ live 是两个独立 operation；每个 operation 均为一次请求，无自动 retry、fallback 或来源页抓取；未 commit 或 push。
tracked files 和 Bot 日志均未发现真实 Key 或 Authorization header。
主人随后反馈 QQ live 能够成功发送；正式 external-read 任务 #43 为 done。
任务 #43 事件链为 created、work_claimed、work_started、work_finished。
持久化 goal/event input 使用固定原文未持久化占位，只保存 provider、请求数和状态等安全元数据；未发现 URL、Bearer 或 Key 前缀。
```

## MainAgent external-read：QQ live 后结果质量优化

状态：已落地，未新增联网请求。

```text
新增保守来源类型：中国政府域名、已识别的官方文档域名、中央媒体域名、一般公开来源。
域名匹配使用 host/subdomain 边界，docs.python.org.evil.example 不会被标为官方文档。
时间敏感 query 增加临时核验提示；缺失 published_at 明确显示未提供。
QQ 结果改为标题、类型、来源、时间、摘要分层格式，继续不展示完整 URL。
Tavily content 额外清理反引号和 ¶，仍固定最多 360 字符。
request_timeout、provider_unavailable、response_too_large、invalid response 和 sanitizer 等错误改为中文安全回复。
新增 /agent 联网状态：仅主人私聊、纯本地、不请求 Tavily、不消耗 credit。
ChatAgent、普通聊天、角色卡、情感表达、Main LLM external-read 可见性均未改变。
定向 external-search/Tavily/work/QQ 边界 59 tests OK；MainAgent/config 80 tests OK。
全量回归 469 tests OK。
```

## MainAgent external-read：个人信息、日期与 provider 错误收口

状态：已落地，未新增 Tavily 请求。

```text
Query policy 新增邮箱、明确手机号/电话、QQ号和身份证号拒绝。
保留 RFC 9110、CVE-2026-12345 和无标签产品编号，避免宽泛长数字误伤。
published_at 只接受有效 ISO 类日期并规范为 YYYY-MM-DD；无效日期不展示。
发布日期字段加入提示注入检测，命中时整条外部结果中和。
Tavily 401/403 -> authentication_failed；429 -> rate_limited；503 等 -> provider_unavailable。
鉴权失败和限流分别使用中文安全回复，不记录 response body 或原始异常。
/agent 联网状态新增 httpx/httpcore 实际版本和已验证兼容范围判断；状态查询仍不联网。
ChatAgent、普通聊天、角色卡、情感表达和 Main LLM external-read 可见性未改变。
定向 security/search/Tavily/work/QQ 边界 74 tests OK。
全量回归 473 tests OK。
```

## MainAgent external-read：Unicode 注入与最近任务安全快照

状态：已落地，未新增 Tavily 请求。

```text
外部可见文本新增 Unicode NFKC 规范化。
提示注入检测新增 compact 检测副本，覆盖全角英文、拆分空白、零宽字符、有限标点、双向字符和 HTML 标签分段。
新增 external_read_status 纯只读模块，SQLite mode=ro、当前 session/user、固定任务标题、limit 1。
最近任务只展示 ID、白名单状态、provider、安全计数、类别和合法 ISO 更新时间。
数据库任意 status/updated_at 污染文本不会回显；缺失或损坏时安全显示无可用元数据。
/agent 联网状态不读取 query、goal、事件正文或结果详情，不访问 Tavily、不消耗 credit。
ChatAgent、普通聊天、角色卡、情感表达和 Main LLM external-read 可见性未改变。
定向 external-search/status/QQ/work 60 tests OK。
全量回归 479 tests OK。
主人随后在 QQ live 验证 /agent 联网状态成功；本地兼容性与最近正式任务安全快照已加载生效。
该状态命令未发起 Tavily 请求，不消耗 credit；主人未提供新的 external-read 任务 ID，因此不臆造编号。
```

## Owner Console：external-read 只读观测页

状态：已落地，未新增 Tavily 请求或 Web 写操作。

```text
新增 GET /api/v1/owner-console/external-read，并纳入统一 HTTP/read-model 路由契约。
新增独立“联网查询”页面、侧栏入口和 Dashboard 摘要卡片。
页面展示 Tavily Basic、本地开关、凭据存在性、executor 就绪状态、timeout、httpx/httpcore 兼容性和最近正式任务安全元数据。
接口不返回 Key、query、goal、标题、摘要、完整 URL、事件正文、原始响应或原始异常。
接口通过 SQLite mode=ro 按当前主人 session/user 和固定任务标题读取最近任务，不执行实时 Tavily probe，不消耗 credit。
安全边界明确显示 Main LLM/普通聊天/任意 URL/retry/fallback/AI answer/raw content/images 均未开放。
修复正式 work 持久化把换行压为空格后，最近任务安全元数据无法解析的问题；解析仍只接受 provider、计数、状态类别、错误类别和合法时间白名单。
Owner Console 继续只有 GET；/docs、/redoc、/openapi.json 继续关闭；web/owner-console/dist 继续不提交。
全量回归 481 tests OK；Python AST 116 files OK。
前端生产构建、GET-only guard、12 tests 和 git diff --check 通过。
受当前会话浏览器控制接口缺失影响，本轮未完成真实浏览器视觉点击验收；生产构建和路由/组件契约已验证。
```

## Owner Console：任务 work type 标签与筛选

状态：已落地，未新增外部请求或 Web 写操作。

```text
OwnerConsoleTaskRow 新增 work_type，OwnerConsoleTaskList 新增 work_type_filter。
只展示 development_context_report、system_diagnostics_report、external_read_report 三个正式只读 work type。
未知、污染或未注册的事件 tool_name 不作为类型标签回显。
GET /api/v1/owner-console/tasks 新增可选 work_type 参数，并严格拒绝白名单外值。
数据库查询通过 agent_task_events 的 work_claimed 精确 EXISTS 条件先筛选再 LIMIT，避免较旧联网任务被较新普通任务挤出。
前端任务页增加研发上下文、系统诊断、联网查询类型筛选和类型 badge；任务详情摘要同步展示安全 work type。
筛选只读取本地 SQLite，不访问 Tavily、不消耗 credit。
全量回归 482 tests OK；Python AST 116 files OK。
前端生产构建、GET-only guard、12 tests 和 git diff --check 通过。
```

## ChatAgent：本地日期、星期和时间

状态：已落地，已改为 ChatAgent 角色化表达，尚待主人 QQ live 验收。

```text
新增 BOT_TIMEZONE，第一版只允许 Asia/Shanghai，默认无需修改现有 .env。
当前 Windows Python 环境缺少 IANA tzdata，因此采用等价的固定中国标准时间 UTC+8，不新增依赖或网络下载。
新增纯本地 LocalTimeSnapshot、显式意图解析、可信 Prompt 上下文和确定性回退格式化。
支持今天星期几/周几/礼拜几、今天几号/几月几日、日期+星期、现在几点、当前年份。
明确时间问题在 generate_chat_text_response 内生成可信本地事实，并把 system context 追加到本轮 history 副本后正常调用 ChatAgent；当前角色卡负责自然表达。
原 ChatPromptContext history 不被修改，内部时间事实不作为用户文本、聊天历史或 RAG 内容持久化。
模型回复按 intent 校验正确日期、星期、年份或小时分钟；错误值、冲突值、空回复或超长回复统一回退到确定性答案。
Chat LLM 调用异常时记录既有安全错误并直接使用本地回退，不把简单日期问题变成 AI 调用失败提示。
日期能力调用现有 Chat LLM，但不调用 MainAgent、Tavily、MemoryRAG 或 ProjectDocRAG，不消耗 Tavily credit；远程 Chat LLM 不增加本地 GPU 显存。
每条命中消息只读取一次时钟，先转换为 Asia/Shanghai，再从同一不可变快照生成日期和星期。
命令消息、明天星期几、指定历史日期和更宽泛的自然问题不被第一版误拦截。
无效时区配置和 naive 测试时钟明确失败，不静默使用系统时区。
全量回归 490 tests OK；Python AST 118 files OK；git diff --check 通过。
```

## ChatAgent：本地角色卡验证（私人设定已移除）

状态：已落地，尚待主人 QQ live 验收。

```text
当前本地角色卡状态已从公开记录移除。
角色外观私人设定已从公开记录移除。
角色回复长度私人设定已从公开记录移除。
角色表达私人设定已从公开记录移除。
角色自称私人设定已从公开记录移除。
角色称谓和表达私人设定已从公开记录移除。
角色示例私人设定已从公开记录移除。
角色卡私人合同测试已从公开仓库移除。
MainAgent 继续保持中性、无角色身份、无括号动作旁白；本次角色卡修改只影响普通 ChatAgent。
全量回归 493 tests OK；Python AST 119 files OK；git diff --check 通过。
```

## ChatAgent：本地时间自然问法与主人 QQ live 收口

状态：已补丁并通过主人 QQ live，未新增 Tavily 请求或 Agent 任务。

```text
本地角色时间问法的私人原句已从公开记录移除；首次验证未命中可信时间解析。
补充受限自然问法前缀和吗/嘛，同时继续拒绝假设句、更宽泛问题、明天、历史日期和 /agent 命令。
主人加入开头括号动作后仍未命中；解析器因此增加仅用于意图识别的开头括号动作剥离，最多三个中文或 ASCII 括号段。
完整原始消息仍通过 user_content.for_llm 原样交给 ChatAgent；只有解析副本用于追加可信本地时间 system context。
可信上下文要求忽略历史旧日期，不复述、纠正或比较旧值；只陈述一次本轮事实并继续遵守角色卡。
数据库与运行时证据确认“今天几月几号”此前确实调用 ChatAgent；最终裸日期是候选未通过事实校验后的确定性回退，不是跳过模型。
新增主人原话、ASCII 括号、未闭合括号、非直接问题和真实错误候选 2025-05-24 的回归合同。
定向本地时间 7 tests OK；全量回归 493 tests OK；git diff --check 通过。
修复后主人 QQ live 正确包含 2026-07-13、星期一；私人称谓和互动内容已从公开记录移除。
Bot/NapCat/OneBot 正常，错误日志为空；最新 Agent 任务仍为 #43，没有新增 external-read 或 Tavily 请求。
```

## 主人审核的本地静态表情包库设计

状态：第一版安全设计、A1/A2、动态候选预算、代表帧和 AI 标签建议合同已完成；A3 及以后尚未实现，尚未导入主人图片或发送 QQ 表情包。

```text
新增 docs/local-static-sticker-library-design.md。
真实候选、批准文件、隔离文件、报告和索引建议放在 Git 忽略的 data/stickers 下。
静态候选允许 PNG、JPEG、WebP；动态候选允许 GIF、APNG、动态 WebP；拒绝 SVG、视频、未知格式、路径逃逸和链接。
候选按魔数和真实逐帧解码校验尺寸、像素、帧数、时长与字节预算；A3 主人批准时才生成规范化副本和 SHA-256 固定索引。
运行时只读取 approved 索引；ChatAgent、MainAgent 和用户文本都不能提供文件路径或 URL。
第一阶段仅设计主人显式候选检查、候选预览、批准和已批准预览；普通 ChatAgent 不自动发图。
第二阶段若另行批准，ChatAgent 只提出有限 mood/usage_tag，本地策略映射到已批准 ID；默认关闭、主人私聊限定、每次最多一张、至少 120 秒冷却、失败不 retry。
表情包库不调用 Tavily、浏览器、图片生成、视觉入库、MemoryRAG 或 ProjectDocRAG，不开放 Owner Console 写接口。
QQ 动态、群发、非主人自动发图、主动私聊和自动下载继续延后。
主人已批准并完成动态分析骨架；推荐下一步用少量主人 GIF 做 /表情检查 与 /表情分析 live，校准不确定标签后再做批量审核与 A3，QQ 发送继续延后。
```

## 本地静态表情包库 A1：配置、manifest 与图片校验

状态：已实现并完成本地回归；未创建真实表情包目录、未导入图片、未注册 QQ 命令、未发送图片。

```text
新增默认关闭的 ENABLE_LOCAL_STICKERS，以及 2 MiB、32-2048 像素和 4,194,304 总像素安全预算；无效数字加载为 0，后续校验 fail closed。
固定本地根目录为 Git 忽略的 data/stickers，根目录字段不进入配置 repr；聊天文本不能覆盖路径。
显式声明并验证 Pillow 12.x 依赖窗口。
新增纯本地 sticker_library.py，不依赖 NoneBot、网络、数据库、Tavily、MainAgent 或 LLM。
新增不可变 StickerLimits、StickerImageInfo、StickerAsset、StickerIssue 和 StickerLibrary 数据模型。
manifest 顶层严格验证 schema_version、library_revision、条目数量和 1 MiB 预算；逐条非法 entry 以安全 code 隔离，不扩大读取范围。
批准文件只允许 approved 根目录的单层安全文件名；拒绝路径穿越、绝对路径、子目录和符号链接，并在 resolve 后再次确认文件仍位于固定根目录。
按文件魔数和 Pillow 真实解码验证 PNG、JPEG、静态 WebP；拒绝 GIF、动画 PNG、损坏文件、metadata、尺寸/像素/字节超限和未知格式。
重新计算 SHA-256，并复核 manifest 的 MIME、尺寸和字节数；重复 ID、文件和哈希均拒绝后出现条目。
persona、mood、usage tag、owner_private scope、enabled、带时区 ISO approved_at 和固定 approval_source 均使用白名单验证。
定向 sticker/config 22 tests OK，其中 Windows 当前权限不允许创建测试符号链接而安全跳过 1 项；代码路径仍显式拒绝链接。
全量回归 509 tests OK（skipped=1）；Python AST 575 files OK；pip check 无损坏依赖；git diff --check 通过。
真实 Bot 重启加载成功，8080 正常，NapCat/OneBot 自动重连，错误日志为空。
A1 不加载真实 library、不注册表情命令、不产生 Agent 任务或 Tavily 请求。
A2 候选检查与安全报告随后已完成；本节 A1 边界仍保持不批准、不写索引、不发送 QQ。
```

## 本地静态表情包库 A2：只读候选检查与安全报告

状态：代码与回归已完成，真实开关、inbox 候选和主人 QQ live 尚未执行；未批准、改写或发送图片。

```text
新增 StickerCandidate 和 StickerCandidateReport 不可变模型，以及 inspect_sticker_candidates / format_sticker_candidate_report。
只扫描固定 data/stickers/inbox 的直接子项；缺目录时报告“未自动创建”，不创建目录或文件。
根目录、inbox 和候选文件均拒绝符号链接或 Windows junction；真实 resolve 后必须仍是 inbox 的直接普通文件。
直接子项预算固定为 200；超过时整体拒绝扫描，不继续读取文件。
候选在 2 MiB 预算内先计算 SHA-256，再按 A1 真实图片规则解码；重复内容只允许第一项进入审核。
对外只显示 candidate_<12位短哈希>、短哈希、MIME、尺寸、字节数和安全分类；不显示文件名、绝对路径或完整哈希。
metadata 候选可以读取格式/尺寸但标记为待清理，不可直接进入审核；目录、动画、损坏、未知格式、超预算和链接均拒绝。
报告最多展开 30 项，仍保留总扫描、可审核和拒绝计数。
新增严格固定 QQ 命令 /表情检查，仅主人私聊；总开关关闭时直接提示未开启。
handler 延迟导入 Pillow 校验模块；依赖缺失或安全预算无效时给固定中文安全提示，不泄露原始异常。
该命令不进入普通聊天、ChatAgent 或 MainAgent，不调用 LLM、RAG、Tavily、数据库、Agent 任务或图片发送。
定向 sticker/config 30 tests OK（skipped=2，均为 Windows 当前权限无法创建符号链接测试）。
全量回归 517 tests OK（skipped=2）；Python AST 575 files OK；git diff --check 通过。
Bot 重启成功，8080 正常，NapCat/OneBot 自动重连，错误日志为空。
当前 ENABLE_LOCAL_STICKERS 仍保持默认关闭，data/stickers 未自动创建，因此尚未宣称真实候选或 QQ live 通过。
推荐下一步先由主人决定是否本地启用并准备少量自有候选；A2 live 通过后才进入 A3 批准/规范化写入。
```

## 本地表情包 A2.1-A2.3：动态预算、代表帧与 AI 标签建议

状态：代码与假视觉合同回归完成；尚未导入主人 GIF、调用真实候选视觉分析、写正式标签或发送图片。

```text
候选层新增 GIF、APNG 和动态 WebP 支持；静态批准 loader 继续拒绝 GIF/多帧，A3 尚未开放动态正式资产。
新增动态 5 MiB、120 帧、10 秒、最小 20ms 帧间隔和 60,000,000 总解码像素预算；逐帧真实解码并执行首故障短路。
Pillow 12 不暴露动态 WebP 帧时长，因此新增受限 RIFF/ANMF chunk 解析；块越界、帧数不一致或时长不可用时 fail closed。
候选报告新增静态/动态、帧数和总时长；仍不输出文件名、路径或完整哈希。
新增内存代表帧联系表：最多 6 张，包含首尾、四分位和变化较大帧；输出 PNG bytes，不写临时文件。
新增 sticker_labeling.py 固定 JSON 合同，只允许 moods、soft/medium/strong、动作、兼容场景、三类置信度和 ambiguous。
情绪置信度低于 0.85、强度低于 0.75、场景低于 0.70、mixed 或 ambiguous 自动标记 needs_owner_review。
高置信度只标记 suggested/待主人确认；AI 建议不写 library.json，不成为正式标签。
现有本地 Ollama transport 新增固定 prompt 入口；原聊天视觉事实描述仍经过原 sanitize/truncate 行为，回归保持不变。
新增 candidate_<12位短哈希> 精确解析器；只在固定 inbox 中重新匹配完整 SHA-256，碰撞、替换、路径逃逸或预算失败均拒绝。
新增主人私聊严格命令 /表情分析 <candidate_id>；总开关与视觉开关门控，抽帧和视觉调用放入线程，失败只返回固定中文类别。
/表情分析 不发送图片、不写标签、不批准候选，不调用 ChatAgent、MainAgent、Tavily、RAG、数据库或 Agent 任务。
聚焦 sticker/label/config/vision 65 tests OK（skipped=2，均为 Windows 符号链接权限）。
全量回归 530 tests OK（skipped=2）；Python AST 577 files OK；pip check 和 git diff --check 通过。
Bot 重启成功，8080 正常，NapCat/OneBot 自动重连，错误日志为空。
本轮未调用真实 Ollama 标签分析，避免用合成联系表冒充主人 GIF 分类质量；真实置信度阈值等待主人样本校准。
推荐下一步为少量主人 GIF 的 /表情检查 + /表情分析 live；主人反馈不确定项后再做批量审核页和 A3 正式标签。
```

## 本地表情首批真实分析与主人校准

状态：32 个候选已完成只读安全扫描；首批 6 个完成真实本地视觉分析、主人校准和一次改进后复跑；剩余 26 个完成 AI 人工辅助初判。未写正式标签、未批准候选、未发送 QQ 图片，剩余候选未交给当前模型静默批量分类。

```text
data/stickers/inbox 扫描到 32 个候选：31 个动态 GIF、1 个静态 PNG；全部通过字节、尺寸、帧数、时长和总解码像素预算，没有 rejected candidate。
首批 6 个生成 output/sticker-review/initial-batch.png，只包含 candidate_<短哈希> 和代表帧，不包含源文件名、路径或完整 SHA-256。
第一次本地 Ollama 标签结果置信度普遍偏低，并重复输出 neutral + embarrassed；全部正确路由到 needs_owner_review，没有写 library.json。
人工初步建议经主人校准：第 1 个是“卖萌 / 中等”，不是打哈欠；第 3、4 个属于同一探头/围观场景；第 6 个“撒娇”或“拜托”均符合；第 2、5 及其他建议无需修正。
固定标签白名单补充 curious、expectant、playful、pleading；动作补充 act_cute、exclamation_mark、hands_together、peek、show_heart；场景补充 acting_cute、attention_seeking、checking_reaction、joining_chat、request。
固定 prompt 明确：仅凭张嘴不得判断 yawn；从遮挡物后探头不得自动判断 shy/embarrassed/cover_face；爱心、感叹号、闪亮注视和双手合拢按各自可见证据映射；neutral 不得作为不确定时的默认答案。
改进后复跑第 1、4、6 个方向改善，但第 2、3、5 个仍出现明显误判，且 6 个均因低置信度或 ambiguous 保持 needs_owner_review。当前 3B 模型未通过无人复核批量分类质量门槛。
剩余 26 个不再调用该 Ollama 分类器，而是按最多 6 个一批生成 5 张本地审核图，由 AI 直接查看代表帧完成初步建议。结果保存为 Git 忽略的 output/sticker-review/preliminary-analysis.md。8、18、19、20、22、24、25、26、28 共 9 个物品、原梗或触发语义不清项随后由主人逐一确认：喝奶茶表示观望/“请继续说”，手机拍照表示记录，锤子敲头表示受到打击，灵魂出窍用于震惊，趴倒表示摆烂，伸舌舔用于讨好/撒娇，蛋糕用于生日快乐和分享点心，小本本用于“我记住了”或记仇，握方向盘表示出发。32 个候选现均完成初步语义确认。
固定标签合同继续增加 attentive、hurt、resigned、dizzy，以及 drink_milk_tea、take_photo、get_hit、soul_leave_body、lie_flat、lick、offer_cake、take_notes、drive、offer_gift、sway、type_angrily 和相应受控场景。图片动作和聊天用途分层保存；同一小本本 GIF 可兼容普通倾听/记录和有生气证据时的记仇场景，不把 angry 固化为唯一情绪。
本次真实分析只调用 loopback Ollama，不调用 Tavily、ChatAgent、MainAgent、RAG、数据库或 Agent 任务；未消耗 Tavily credit。
推荐下一步先设计 A3 待审草稿与显式批准流程，或先实现并验证两段式客观描述/受控标签映射。未经主人另行授权，不写正式 manifest、规范化副本，不实现 QQ 预览、自动触发或发送。
全量回归 531 tests OK（skipped=2）；仓库范围 Python AST 135 files OK；pip check 和 git diff --check 通过。
```

## 本地表情包 A3：主人显式批准、规范化与撤销核心

状态：A3 代码、纯本地回归和 32 条主人确认草稿已完成；尚未执行真实主人 QQ 命令、生成 `library.json` 或创建 approved 文件，没有发送表情包。

```text
正式 manifest 升级为 schema v2，新增 source_sha256、animated、frame_count、duration_ms、intensity 和 actions；新批准只写 v2，旧 schema v1 静态库继续只读兼容且不自动迁移。
正式情绪、动作和 usage tag 白名单与主人确认的 32 个候选语义对齐；manifest loader 重新验证最终/来源哈希、动态属性和所有枚举，并拒绝重复来源哈希。
新增纯本地 sticker_approval.py；不依赖 NoneBot、网络、Tavily、数据库、ChatAgent、MainAgent、RAG 或 OneBot sender。
批准草稿固定在 data/stickers/reports/approval-drafts.json；只允许严格 schema、完整源哈希、唯一 candidate/sticker/source、白名单标签、owner_private 和 owner_confirmed=true。
/表情草稿 仅主人私聊只读，只返回草稿 revision、数量、安全 candidate/sticker ID、情绪、强度和场景，不显示完整哈希、路径或源文件名。
/表情批准 candidate_<12位短哈希> <同一短哈希> 仅主人私聊；重新解析固定 inbox 当前文件并匹配草稿完整源 SHA-256，候选替换、错误确认、重复来源和无草稿均 fail closed。
静态候选修正方向、清除 metadata 并统一编码 PNG；GIF/APNG/动态 WebP 逐帧解码后按原动画类型重编码，保留帧时长和 loop 语义。规范化结果再次执行全部格式、metadata、帧数、时长、像素和字节预算。
approved 文件先写同目录唯一临时文件并验证，再原子替换最终文件；manifest 通过 fsync 临时文件和 os.replace 原子更新。manifest 失败时清理本轮新文件，不形成有效条目。
批准成功只返回安全 sticker ID、library revision、静态/动态摘要和最终 12 位撤销短哈希；不发送图片、不自动触发、不启用 ChatAgent 选择。
/表情撤销 sticker_id <最终短哈希> 仅主人私聊；重新验证整个 v2 manifest 后原子递增 revision 并设置 enabled=false。第一版保留规范化文件，不删除、不移动，disabled 条目不可选择。
根据 output/sticker-review/preliminary-analysis.md 和主人逐项确认生成 32 条真实本地草稿，draft schema=1、revision=1、32 个唯一 sticker ID；生成前要求实际 eligible candidate 集合与定义精确相等。一次人工报告短哈希笔误被集合检查拦截并修正，没有模糊匹配。
当前 data/stickers/library.json 和 data/stickers/approved 均不存在，证明本阶段没有把“进入 A3”解释为自动批准。
A3 专项覆盖静态 metadata 清理、GIF 帧数/总时长保留、错误确认零写入、候选替换、manifest 失败清孤立文件、重复批准、草稿校验、输出脱敏、撤销短哈希和 owner-private 命令隔离。
全量回归 542 tests OK（skipped=2，均为 Windows 符号链接权限）。
.env 原本没有 ENABLE_LOCAL_STICKERS；已只补充唯一 ENABLE_LOCAL_STICKERS=true，不显示或改动其他配置，也不进入 Git。Bot 于 2026-07-13 16:24 重启成功，ai_chat 插件加载、127.0.0.1:8080、NapCat/OneBot 重连均正常，stderr 为空。
推荐下一步 QQ 私聊先验收 /表情草稿，再由主人挑一张静态和一张短 GIF 逐项批准，最后选择一项验证撤销。A4 QQ 预览、自动触发和发送继续延后。
```

### A3 QQ live：草稿、两项批准与重复批准提示

```text
/表情草稿 live 返回 draft revision 1、32 条安全 candidate/sticker ID 与主人确认标签；未显示路径、文件名或完整哈希，未发送图片。
主人于 16:56:34 批准 candidate_350e629e52e1，生成 aike_angry_002 静态规范化 PNG；随后于 16:56:58 批准 candidate_1ee215ac7c6e，生成 aike_act_cute_001 动态规范化 GIF。
正式库安全复核：schema 2、revision 2、enabled 2、disabled 0、invalid 0。静态最终短哈希 bc295b1266b1；动态最终短哈希 c82a170dcdbb。
动态源容器报告 6 帧/360ms；规范化 GIF 为 2 帧/360ms。Pillow 合并了连续相同画面，总时长、动画属性和可见变化保持；设计与文档改为记录最终真实帧数，不承诺保留冗余相同帧。
主人于 17:04:57 再次批准同一静态候选，重复 sticker ID/来源规则正确拒绝。原统一失败文本无法区分“已批准”和真正安全失败，因此补充分层安全提示：重复批准明确返回“该候选已经批准，正式库未重复写入”；确认哈希、候选变化、manifest 检查和规范化失败分别返回不同固定类别，不输出原异常。
此前两条撤销尝试分别缺少最终短哈希或使用错误命令/候选哈希，均未改变正式库。正确静态撤销命令为 /表情撤销 aike_angry_002 bc295b1266b1；是否执行由主人决定。
A3 专项 12 tests OK；全量回归 543 tests OK（skipped=2）。
细分错误提示已随 17:19 Bot 重启加载；ai_chat 插件、8080 和 OneBot 重连正常，stderr 为空，正式库仍为 revision 2、enabled 2、invalid 0。
```

## 本地表情包 A4：主人显式 QQ 预览

状态：代码、回归、Bot 重启和主人 QQ 动态 GIF live 均完成；正式库 revision 3、enabled 1、disabled 1，普通聊天自动附带仍关闭。

```text
新增纯本地 sticker_preview.py；严格 sticker ID 解析后重新加载完整 manifest，任何 invalid issue 均使预览 fail closed。
只允许 enabled=true 的正式条目；disabled、未知 ID、非法 ID 均返回固定安全类别，不进入发送和冷却。
发送前再次检查正式文件 SHA-256、MIME、尺寸、字节、metadata、动画属性、帧数与总时长，避免批准后文件被替换。
新增 LOCAL_STICKER_PREVIEW_COOLDOWN_SECONDS，默认 3 秒；无效值加载为 0 并安全关闭预览。
新增主人私聊严格命令 /表情预览 <sticker_id>；只接受一个参数，每条命令只有一次 send_private_msg，使用 MessageSegment.image 发送已复核的正式本地文件。
成功只发送图片，不追加文字。OneBot 失败只记录 sticker_preview_send_failed 固定类别，不记录路径或原始异常；不重试、不改发其他图片、不随机选择。
预览入口不调用 ChatAgent、MainAgent、Tavily、视觉、RAG、数据库或 Agent 任务，不开放群聊、普通聊天或自动附带。
定向 config/preview 13 tests OK；全量回归 549 tests OK（skipped=2）。首次全量失败来自旧 A2/A3 源码审计测试截取范围延伸到新 A4 handler；收紧各自 handler 结束边界后通过，隔离要求未降低。
QQ live 顺序：先 /表情预览 aike_angry_002，确认 disabled 只返回拒绝；再 /表情预览 aike_act_cute_001，确认 QQ/NapCat 实际播放动态 GIF。普通聊天自动触发继续延后。
Bot 于 19:07 重启，ai_chat 插件、8080 和 OneBot 重连正常，stderr 为空；重启后正式库仍为 schema 2、revision 3、enabled 1、disabled 1、invalid 0。
主人于 20:53 执行 /表情预览 aike_act_cute_001；OneBot matcher 单次完成，主人确认 QQ 收到的是第 1 张“卖萌”表情且能够播放动态效果。stderr 为空，没有 retry 或替代发送证据。
预览前后正式库保持 schema 2、revision 3、enabled 1、disabled 1、invalid 0，证明 A4 只读预览没有改写 manifest。A4 enabled 动态主链 live 通过；disabled 拒绝 live 可选补验。
```

## 本地表情包 B1：ChatAgent 有限意图与本地 shadow 选择

状态：代码、回归、shadow 配置和 Bot 重启加载完成，自动附件关闭；尚待主人 QQ shadow 样本校准。

```text
新增 sticker_intent.py 固定合同。ChatAgent 正常可见回复结束后只能追加一次末尾标记，字段限定 attach、mood、intensity、scene、confidence；不能选择 sticker ID、文件名、路径或 URL。
控制标记在本地时间事实校验、QQ 发送、TTS 候选、stored_assistant、聊天历史和 RAG 之前解析并剥离。marker 缺失保持原回复；非法 JSON、未知枚举、额外字段、错误置信度、非末尾或残缺标记均丢弃意图并截断控制区域，绝不进入可见/持久化文本。
ask_llm 新增可选 extra_system_context，不增加第二次 LLM 调用；只有 ENABLE_CHAT_STICKER_INTENT_SHADOW=true 时注入固定意图合同。附件开关不赋予模型额外能力。
ChatRuntimeResult 新增可选 StickerIntent，并在 legacy/graph/semantic voice 包装中传递；现有构造保持默认兼容。
新增 sticker_selection.py 纯本地策略：owner-private、回复非空、confidence>=0.82、正式库无 invalid、persona/scope/enabled 和 mood/intensity/scene 精确匹配。
频率为确定性硬门控：120 秒冷却、至少 4 条消息间隔、每小时最多 6 张、每回复最多 1 张。无概率随机触发；同类多候选使用 shuffle-bag，袋内用完前不重复。
选择和发送分成 decide/commit_sent；只有未来 OneBot 图片发送成功后才提交冷却、小时计数和袋消费。B1 shadow 只 decide，不 commit，不发送。
新增 /表情意图状态 主人私聊只读命令，仅显示 marker 状态、有限意图、置信度、本地决策原因、匹配数量和安全 sticker ID；不保存或显示用户原文、回复正文、路径、哈希或文件名。
.env 已设置 ENABLE_CHAT_STICKER_INTENT_SHADOW=true 与 ENABLE_CHAT_STICKER_ATTACHMENTS=false，均唯一；普通聊天仍没有 MessageSegment.image 或 send_private_msg 接入。
意图/config/选择定向 20 tests OK；全量回归 562 tests OK（skipped=2）；Python AST 143 files OK；pip check 和 git diff --check 通过。
推荐 QQ shadow live：先普通事实问题后查 /表情意图状态，确认不建议/不匹配且无图片；再发“默认人格卖个萌给我看看”后查状态，观察是否为 playful/medium/acting_cute 并 shadow 选中 aike_act_cute_001。两轮均不得发图。
Bot 于 21:33 重启，ai_chat 插件、8080 和 OneBot 重连正常，stderr 为空；shadow=true、attachments=false 均为唯一有效配置。

主人首轮 QQ shadow 依次发送“默认人格记得今天几号吗”和“默认人格给我卖萌”。两次文本均正常回复且没有图片，但 `/表情意图状态` 都显示 `marker_absent / intent_absent`。21:41 与 21:57 日志确认消息进入同一普通聊天 matcher 且正常完成，stderr 为空。
使用完整正式 ChatAgent prompt 的无隐私最小探针复现 marker 缺失；简短独立 prompt 可以输出 marker，说明不是解析器、开关、QQ handler 或 DeepSeek 完全不支持该字符格式，而是完整系统/基础/角色组合下的输出合同不稳定。将 system 消息简单合并仍有缺失或错误标签，不能作为修复。
当前 DeepSeek 接口 3/3 支持 `json_object`，但 `json_schema` 返回 HTTP 400，因此曾把 B1 改为同一次 LLM 调用的严格 JSON envelope。最小探针连续三次得到 requested，并不代表真实长会话稳定；22:34 左右主人连续发送“默认人格给我卖萌”时，Bot 一直返回固定“没有组织好回答”兜底。该句来自结构解析后可见 reply 为空触发的本地兜底，不是角色卡正常回复。虽然之后用同一近期历史的独立 JSON 探针又能返回完整结构，但这进一步证明输出具有随机不稳定性，不能靠放宽校验修复。
为恢复“聊天优先”，22:37 先把 `.env` 的 shadow 改为 false 并重启；随后从 ChatAgent 主链完整撤销 JSON response_format、system 合并和结构 envelope 解析，恢复普通文本 + 可选末尾 marker 的安全形态。marker 缺失只会丢弃表情建议，正文原样保留。使用同一近期历史的普通模式探针得到 275 字非 JSON、非固定兜底回复；回退后全量 `562 tests OK（skipped=2）`，git diff --check 通过。Bot 于 22:47 再次重启，shadow=false、attachments=false；普通聊天恢复尚待主人 QQ 复验。正式库、Agent #43 和 Tavily 状态未因该回退改变。
主人随后确认 QQ 中“默认人格给我卖萌”已恢复正常角色回复，并选择新增第二个 DeepSeek API Key 做解耦分类。新 Key 只保存在 `.env` 的 `STICKER_CLASSIFIER_API_KEY`，检查时仅确认非空，没有输出内容；Base URL 固定 `https://api.deepseek.com`，模型为 `deepseek-v4-flash`。新增 `sticker_classifier.py`、独立配置和正文发送后的 owner-private 异步调度；分类器不回退使用 ChatAgent Key，不读取历史/记忆/RAG/图片/文件，不写数据库，不重试，也不发送图片。假 transport 覆盖禁用、错误配置、输入预算、严格字段、额外 ID、超时和调用次数；源码审计确认 legacy 与 graph 两条文字路径都先 `matcher.send(result.reply)`，再调度分类。
独立 Key 手动探针只返回安全有限结果：卖萌为 requested + `playful/medium/acting_cute` + 0.95，日期事实为 not_requested；没有经过 QQ、Tavily、MainAgent、RAG 或聊天存储。补充 401/403/429/500 安全类别与单次调用回归后，全量 `571 tests OK（skipped=2）`，Git 口径 Python AST 145 files OK，pip check 与 git diff --check 通过。Bot 于 23:42 在 remote classifier=false、旧 marker shadow=false、attachments=false 下重启；ai_chat 加载、8080 监听、OneBot 重连均正常，stderr 为空，Agent 最新任务仍为 #43。尚未授权 QQ shadow 或 B2 发送。
主人随后明确要求打开新的远程 shadow。只把 `ENABLE_REMOTE_STICKER_CLASSIFIER` 改为 true；旧 `ENABLE_CHAT_STICKER_INTENT_SHADOW=false`、`ENABLE_CHAT_STICKER_ATTACHMENTS=false` 保持不变。Bot 于 23:57 重启，ai_chat、8080 与 OneBot 重连正常，stderr 为空。当前只允许主人私聊在正文成功发送后产生一次后台分类，不发送 GIF；等待日期事实和卖萌样本 QQ live。
2026-07-14 00:02–00:03 主人完成两组 QQ live。样本 #1“今天是几月几号”先得到正常日期正文，远程分类为 not_requested，本地 intent_absent、0 匹配、无选中；样本 #2“默认人格给我卖萌”先得到正常角色回复，远程分类为 requested + `playful/medium/acting_cute` + 0.95，本地精确匹配 1 项并影子选中 `aike_act_cute_001`。两次状态均明确自动附带关闭，没有 GIF。NoneBot 日志显示四个 matcher 正常完成，stderr 为空；正式库保持 schema 2、revision 3、enabled 1、disabled 1，Agent 最新任务和 Tavily/external-read 最新任务均仍为 #43，`sticker_classifier.py` 不含 MessageSegment.image、send_private_msg 或 commit_sent。C1 日期负样本与卖萌正样本主链通过；B2 真实自动发送仍需主人另行明确授权。
主人明确授权进入 B2。新增 `sticker_attachment.py`，通过注入单次 sender 复用 A4 发送前安全复核；`__init__.py` 只在正文成功发送、远程分类 requested、本地 selected、attachments=true、未熔断时调用一次 OneBot private image。失败不 retry、不替代，成功后才 commit 冷却/消息间隔/小时计数/shuffle-bag；发送成功但 commit 异常时熔断。全量 `576 tests OK（skipped=2）`，Git 口径 Python AST 147 files OK，pip check 和 git diff --check 通过。先在 attachments=false 下于 00:35 重启安全加载，再按授权设为 true 并于 00:36 重启，ai_chat、8080、OneBot 正常。
主人 00:39 发送“默认人格给我卖萌”，确认先收到正常文字、随后收到动态表情；00:40 状态显示 requested、`playful/medium/acting_cute`、0.95、selected、匹配 1、`aike_act_cute_001`、自动附带已发送。stderr 为空，Agent/Tavily 最新任务仍为 #43。主人随即表示不喜欢该表情并要求删除。核对 enabled 与最终短哈希后，调用现有原子撤销函数把 `aike_act_cute_001` 设为 disabled，library revision 从 3 升至 4；完整 loader 复核为 enabled 0、disabled 2、invalid 0。当前不会再自动发送该 GIF；文件按现有安全撤销合同保留作审计，未做不可逆磁盘删除。
```

## 后续整理规则

## 2026-07-14 本地表情批量逐项批准

```text
主人明确指定批准草稿序号 4、5、6、9、12、15、18、21、23、24、29、30、31、32，未授权批准其他候选。
按草稿 revision 1 精确映射到 14 个 candidate_<12位短哈希>，每项确认值与 candidate ID 完全相同。写入前一次性复核 14 项当前候选、完整源 SHA-256、sticker ID、来源去重和目标文件冲突，全部通过。
在受限工作区内首次执行时，安全批准函数无法在 approved 目录创建以点开头的原子临时文件，因此在第一项 normalization 阶段 fail closed 并清理临时文件，manifest 仍为 revision 4。同一张 38 帧 GIF 在隔离临时目录使用相同参数成功规范化，进一步定位为受限环境的目录写入权限，不是素材损坏。获得主人对本地批准写入的明确允许后，使用原有原子写入函数完成，未绕过任何哈希、图片预算、metadata、动画或 manifest 复核。
成功新增：aike_peek_002、aike_surprised_001、aike_pleading_001、aike_pleading_002、aike_pleading_003、aike_affection_003、aike_recording_001、aike_affection_004、aike_surprised_003、aike_pleasing_001、aike_affection_005、aike_peek_003、aike_tired_002、aike_pleading_004。其中 13 张动态 GIF、1 张静态图；每项批准独立递增 revision。
批准后完整 loader 复核：schema 2、revision 18、enabled 14、disabled 2、invalid 0；14 个指定 ID 全部 enabled，missing=none。已撤销的 aike_act_cute_001 和 aike_angry_002 继续 disabled，未物理删除审计副本。其他 16 个候选仍在 inbox/草稿中保留，未批准、未移动、未删除。
表情专项回归运行 81 tests，全部通过，skipped=2 仍为 Windows 当前权限无法创建测试符号链接。运行选择路径在每次分类后重新加载完整 manifest，因此新资产不需要 Bot 重启即可参与主人私聊 B2；本轮没有发送 QQ 图片，仍需主人做新资产 live 验收。
本轮没有修改 .env、API Key、数据库、RAG 索引或网络权限；没有调用 Tavily、MainAgent、ProjectDocRAG 或 QQ 动态；没有 commit 或 push。
```

## 2026-07-14 本地表情设计文档状态收口

```text
按恢复清单重新核对 Git、当前开发状态、版本运行记录和本地表情设计；main 与 origin/main 仍共同指向 cfbda5c，既有大量未提交开发修改全部保留，没有 commit、push 或 reset。
执行指定 rebuild-rag-index 开发上下文查询并成功返回 5 条项目文档、4 条记忆；召回结果命中当前状态文档，但表情主题的前几项仍偏向旧基础文档，因此本轮继续以仓库与最新交接文档为准，没有把召回结果当作运行时事实。
核对独立远程分类、正文发送后调度、B2 单次私聊图片发送和发送成功后 commit_sent 的代码顺序；表情专项重新运行 81 tests OK，skipped=2 仍为 Windows 当前权限无法创建测试符号链接。
修正 local-static-sticker-library-design.md 的过期当前态：不再写 revision 3、shadow 开启、attachments 关闭或 B2 未执行；同步为远程分类开启、旧 marker shadow 关闭、attachments 开启，以及 schema 2、revision 18、enabled 14、disabled 2、invalid 0。
文档明确运行分类后会重新加载 manifest、14 个新资产无需单独重启 Bot；保留 B1 marker/JSON envelope 的历史失败经验、主人私聊限定、正文优先、无重试、频率门控、撤销不物理删除和剩余 16 个候选不自动批准等边界。
除按恢复清单执行开发侧 ProjectDocRAG 索引重建外，本轮只修改设计与运行记录文档；没有修改 .env、API Key、聊天数据库、MemoryRAG、真实表情、正式 manifest 或批准草稿，没有调用 DeepSeek、Tavily、MainAgent 或 QQ 图片发送。
```

## 2026-07-14 B2 冷却期跳过远程表情分类

```text
主人完成一晚 QQ live，反馈基本场景均符合预期，未发现功能问题；提出在表情发送冷却期间跳过表情分类 LLM，以减少 token 使用。
StickerSelectionRuntime 新增纯本地 preflight，不需要 StickerIntent 或正式库即可检查 policy、owner-private scope、正文可用性、120 秒冷却、4 条消息间隔和每小时发送上限。preflight 只读取既有内存发送状态，不消费 shuffle-bag、不提交冷却或小时计数。
B2 自动附件开启时，schedule_remote_sticker_classifier_shadow 在创建异步分类任务前执行 preflight；命中 cooldown、message_gap、hourly_cap 或附件熔断时直接返回 classifier_status=skipped，不调用 classify_sticker_intent。C1 shadow 在 attachments=false 时仍继续分类观察，不受发送频率状态影响。
正文发送顺序保持不变；预检发生在正文成功发送之后。会话消息仍正常持久化，因此跳过分类不会冻结 message_index，达到 4 条间隔后可以自然恢复。预检读取本地消息进度异常时 fail closed 为 preflight_unavailable，跳过分类且不影响已发送正文。
/表情意图状态 新增“频率门控中，未调用分类模型”展示；本地决策保留 cooldown、message_gap、hourly_cap 等安全类别，不显示正文、路径、哈希或异常原文。
新增 preflight 冷却、消息间隔恢复、小时窗口到期、不消费状态和分类前源码顺序测试。表情专项 83 tests OK（skipped=2）；完整回归 578 tests OK（skipped=2）。本轮未调用 DeepSeek、Tavily、MainAgent 或 QQ 图片发送，未修改 .env、API Key、真实表情、正式 manifest 或批准草稿，未重启 Bot，未 commit 或 push。
```

## 2026-07-14 MainAgent TXT/Word/PPT 受控文档产物

```text
主人明确选择下一步同时增加 TXT、Word 和 PPT 三种 MainAgent 文档能力，并保持“不让 Agent 修改项目”的边界。
新增纯本地 document_artifacts.py，生产根固定为 Git 忽略的 output/main-agent-workspace/；工具不接受 path 或文件名参数，只创建 artifact_<UTC>_<安全随机后缀>.txt/.docx/.pptx 唯一新文件，不覆盖已有文件。
TXT 使用 UTF-8/LF 并精确重读；DOCX 使用 python-docx，支持标题、三级标题、项目符号和编号列表；PPTX 使用 python-pptx，生成 16:9 标题页和正文页，以 ## 标题或 --- 分页，每页最多 8 项、总计最多 20 页。
DOCX/PPTX 保存后执行 ZIP test、必需 OOXML member 校验和库级重新打开；三种格式都限制 title<=120、content<=20,000、最终文件<=10 MiB，刷新临时文件后原子替换，并再次核对最终字节和 SHA-256。符号链接、控制字符、空内容、未知格式、超预算和异常依赖均 fail closed。
MainAgent owner_write_command 新增 create_txt_document、create_word_document、create_presentation。Main LLM 工具合同只允许 command/query/title/content/既有管理参数，不暴露 path；模型必须先生成完整 title/content，ToolPolicyCheck 只创建 write_local 审批，主人确认后才通过既有 approval_resume_enabled 注册表执行一次。
帮助、工具状态、边界和 Main LLM prompt 已同步。普通 ChatAgent、群聊、非主人、Owner Console、Tavily、RAG、数据库、shell 和 QQ sender 均未接入；产物完成后只返回 artifact ID、相对路径、大小、计数和短哈希，不自动发送文件。
项目依赖新增 python-docx 1.x 与 python-pptx 1.x，当前虚拟环境已安装 python-docx 1.2.0、python-pptx 1.0.2、lxml 6.1.1 和 XlsxWriter 3.2.9。开发中修正 python-pptx 1.0 的 Pt/Inches 导入位置，以及 Windows 只读句柄 fsync 不兼容；修正后真实 DOCX/PPTX 重开通过。
专项 MainAgent/格式合同 79 tests OK（skipped=1，为 Windows 符号链接权限）；完整回归 587 tests OK（skipped=3，均为符号链接权限）。本轮测试仅写系统临时目录，没有创建真实文档产物，没有调用 Main LLM、Tavily、RAG 或 QQ 发送；Bot 未重启，QQ live 尚未执行，没有 commit 或 push。
```

## 2026-07-14 修复 Main LLM 文档工具可见性接线

```text
主人首次 live 请求 TXT artifact 时收到“当前可用的 visible tool 只有 dev_context，未注册可调用的 owner_write_command”安全拒绝；没有创建审批、没有写文件。
定位结果：run_main_agent_qq_command 的执行侧 create_read_only_main_agent_runtime_handler 会注册 owner_write_command，但 LC handler 使用 create_main_agent_lc_call_handler(config) 时没有传入该运行时 registry；main_agent_llm 因而按默认 registry 只渲染 dev_context。问题不在文档渲染器、审批策略或依赖。
修复为生产路径只构造一份完整 main_agent_tool_registry，同时传给 LC Main LLM prompt、create_read_only_main_agent_runtime_handler；runner 也支持显式 tool_registry，并从 active registry 推导 local-write policy。这样 prompt、ActionRequest 校验、ToolPolicyCheck 和实际执行共享同一注册事实。
新增 LC 接线回归：注入完整 registry 后 prompt 必须包含 owner_write_command、create_txt_document/create_word_document/create_presentation、title/content，并且不能包含 path。同步保留文档产物审批前零执行测试。
完整回归 588 tests OK（skipped=3，均为 Windows 符号链接权限）；定向 MainAgent/LC/文档合同 107 tests OK；Python AST 149 files OK，pip check 与 git diff --check 通过。
本轮没有重新调用 Main LLM、Tavily、RAG 或 QQ 文件发送，没有创建真实文档产物，没有 commit 或 push。Bot 尚未重启；修复需重启后再做主人 QQ live。

## 2026-07-14 MainAgent 文档生成后受控 QQ 直接交付

状态：已实现并通过本地定向回归；配置默认仍关闭，Bot 未重启，真实 QQ 文件 live 尚未执行。

保留 `create_txt_document`、`create_word_document`、`create_presentation` 的本地 `write_local` 语义，不会将旧审批追溯扩权。已完成的审批 `#20` 只授权当时的本地 TXT 生成，不会被自动发送。

新增独立 `document_delivery_command`，包含 `create_and_send_txt_document`、`create_and_send_word_document`、`create_and_send_presentation`。工具为 `write_external`、`llm_visible=true`、`requires_approval=true`、`approval_resume_enabled=true`；仅在 `ENABLE_AGENT_EXTERNAL_WRITE=true` 时注册并通过策略门控。参数仅包含 command/query/title/content，不开放 path、文件名、QQ 号、群号、任意接收者或重试选项。

审批恢复后复用纯本地渲染器生成一个新文件，然后创建与 approval/session/user 绑定的有界内存待发送状态。当前 `/agent 确认` 处理器只消费该次确认新生成的状态，发送前再次核对固定工作区、后缀、字节数和完整 SHA-256。待发送状态在 OneBot `send_private_msg` 尝试前移除；每个审批最多发送一个 file segment，失败不重试、不换文件、不换接收者，且不影响本地产物保留。

文档完整性、MainAgent bridge、Main LLM 工具合同、LC registry 接线和 QQ 边界定向回归为 117 tests OK（skipped=1，仅 Windows 符号链接权限）；最新完整回归 592 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。本轮没有修改 `.env`、没有重启 Bot、没有调用 Main LLM/Tavily/RAG，也没有通过 QQ 发送测试文件；没有 commit 或 push。

## 2026-07-14 MainAgent Word 直接交付 live 的 prompt 污染修复

主人已自行开启 `.env` 外部写开关，真实 QQ 链路成功生成并发送 Word，因而 `document_delivery_command` 审批恢复、DOCX 渲染和 OneBot file segment 达到主人私聊已有 live 证据。但产物正文误包含 `Read-only project context`、`MainAgentGraph read-only local test mode`、可见工具列表、禁止项和 `User query`，不能将该次生成视为内容质量验收通过。

根因是 `create_read_only_agent_context_builder` 的历史文本仍声称“只读本地测试”和“禁止外部写”，即使完整 registry 已注册 `document_delivery_command`；`build_main_agent_action_messages` 又把它标记为 `Read-only project context` 并与 owner query 同置于 user message。Main LLM 因而把控制元数据误当可用正文。

修复后，runtime context 明确标记为非用户文档内容，根据实际 registry 说明文档交付是否可用，不再绝对声称“禁止 QQ/外部写”。Action Planner 明确：主题型文档请求需自行生成完整 title/content；“生成并发送”在工具已注册时必须选择 `document_delivery_command`，不得用 `final_answer` 或本地产物降级；内部 metadata 不得复制进 title/content。

本地校验层新增已知 internal scaffold marker 拒绝，即使模型再次输出包装文本，也会在审批创建前停止。MainAgent 未开放上一条 QQ 消息作为文档正文的读取能力；对“使用我刚才/上一条/上面提供的完整内容”且未同条内联正文的文档请求，确定性规则在 Main LLM 和审批之前返回 `ask_owner`，要求同一条 `/agent` 请求粘贴完整正文或明确仅给主题由 MainAgent 撰写。

新增 prompt 分区、主题型请求、缺失历史引用、scaffold 拒绝和动态 registry context 回归；定向 110 tests OK（skipped=1），最新完整回归 597 tests OK（skipped=3）。修复需重启 Bot 后再用主题型 Word 请求复验；本轮没有修改 `.env`、没有自动重启、没有删除已生成的错误产物，没有 commit 或 push。

主人随后用完整提纲复验，“推荐下一步”被确定性 `agent_task_read` 分类器提前消费，所以 Bot 转而询问 Agent 下一步，没有创建文档交付审批。该问题与外部写开关无关，属于“确定性管理分类优先于 Main LLM”的路由冲突。

新增 `is_document_artifact_request`：当整句同时具有 TXT/Word/PPT/文档对象和生成/撰写/制作意图，且 registry 中存在本地文档或文档交付工具时，跳过任务、审批、主人管理等确定性文本分类，把完整要求交给文档能力 Main LLM。该收口只对明确文档创建请求生效；独立 `/agent 下一步`、任务查询和审批查询仍使用原确定性路由。新增真实提纲复现测试，确认不调 `agent_task_read`、不调 `dev_context`，Main LLM 请求 `document_delivery_command`，策略结果为 `write_external` 审批中断。定向 111 tests OK（skipped=1），完整回归 598 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。修复需重启 Bot 后再做主人 QQ live；本轮未修改 `.env`、未重启、未 commit 或 push。

主人随后重启并用同类主题型 Word 请求完成复验，反馈文档成功生成且内容质量不错。该 live 表明新文档意图优先级已加载，提纲中的“推荐下一步”未再误命中 `agent_task_read`；Main LLM 生成了可用 title/content，内部 runtime metadata、工具列表和 query 包装未再出现在产物正文，审批恢复、DOCX 渲染和主人 QQ 文件交付也均成功。Word 主题型“生成并发送”链路因此完成真实内容质量验收。本次任务 ID 和审批 ID 未由主人提供，不臆造编号；TXT/PPTX 仍只有自动化格式/边界覆盖，尚未记录主人真实内容质量反馈。本次只同步文档状态，未重启 Bot、未修改 `.env`、未 commit 或 push。

## 2026-07-14 MainAgent 文档生成进度回执与会话并发保护

主人在 Word/PPT 测试中观察到 Action Planner 需等待约二十多秒才生成完整文档 `title/content`，期间 QQ 没有首条回执。主人追加 `/agent 在吗` 后，第二个 MainAgent 请求并发返回“在”，第一个文档请求随后才返回审批，导致可见顺序与请求顺序不一致。

新增 `_main_agent_session_locks`，按 QQ session 隔离 `/agent` 和 `/agent-debug`，不复用普通聊天 `_session_locks`。文档请求成功取得锁后，先通过 matcher 发送“MainAgent 正在生成文档标题、正文和审批请求，请稍候”，再调用 Main LLM。同一 session 在锁持有期间收到的后续 `/agent` 不排队、不调 LLM、不调工具，立即返回“上一条正在处理，当前消息未执行”。只引用上一条内容而缺失同条正文的文档请求仍会立即 `ask_owner`，不先发慢任务回执。

互斥锁在 `matcher.finish(reply)` 将最终结果或审批消息交给 adapter 之后才由 `finally` 释放，避免“先释放锁、再发结果”造成新的小竞态窗口。补丁只改善可见响应和顺序，不会缩短 Main LLM 生成完整文档内容的实际耗时，也不增加重试、后台队列或并发生成。

主人本次 PPT 命令已正确生成审批 `#23`、任务 `#47`；工具为 `document_delivery_command`，命令为 `create_and_send_presentation`，标题和 PPT 结构化内容已出现在截断审批摘要中，风险为 `write_external`，状态为待主人确认。因未收到确认后的 PPTX 发送反馈，不宣称 PPT 内容质量或 QQ 交付 live 已通过。定向 124 tests OK（skipped=1），完整回归 599 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。需重启 Bot 后验收进度回执、忙碌拒绝和最终审批顺序；本轮未修改 `.env`、未重启、未 commit 或 push。

## 2026-07-14 MainAgent PPT 审批恢复超页失败与前置结构预检

主人已确认审批 `#23`，但恢复执行返回 `Approval resume failed: document_delivery_too_many_slides`。该错误发生在 PPTX 渲染前置结构阶段：没有成功生成最终 PPTX，没有创建待发送交付状态，也没有调用 OneBot 文件发送。审批已经进入确认/失败语义，不自动重试或改写原审批内容。

根因是审批前 `owner_write_argument_error` 只检查 title/content 类型、空值、控制字符和字符长度，未执行 PPT 的最终分页算法。实际渲染将每个 `## ` 或 `---` 分成一个内容节，每 8 条非空正文拆分续页，并额外生成标题页；结构展开后超过 `DOCUMENT_ARTIFACT_MAX_SLIDES=20`，因而只在主人确认后才 fail closed。

新增纯本地 `presentation_slide_count`，复用 `_ppt_sections` 实际章节和续页语义，返回包含自动标题页的确切渲染页数。MainAgent ActionRequest 校验在 ToolPolicyCheck 和审批创建之前调用该计算，超限时返回明确的“减少 `##` 章节/每节正文，不要另建封面”提示，不创建一个注定失败的审批。渲染器仍保留原硬上限作为第二层保护。

Main LLM 系统 prompt、本地 `owner_write_command` 和外部 `document_delivery_command` 工具合同均补充 PPT 预算：标题页自动生成，不输出独立“封面”内容节；建议最多 12 个 `##` 内容节、每节最多 6 条非空正文；硬上限为标题页、内容页和自动续页合计 20 张。新增确切续页计数和审批前超页拒绝测试；定向 90 tests OK（skipped=1），完整回归 601 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。修复需重启 Bot；主人需重新发起 PPT 请求并确认新审批，不应再确认 `#23`。本轮未修改 `.env`、未重启、未 commit 或 push。

## 2026-07-14 MainAgent PPT 主题、版式与内容叙事升级

主人重新发起 PPT 请求并确认新审批后，PPTX 已成功生成和发送，证明超页结构预检后的真实交付链可达。主人同时反馈产物存在瑕疵且生成质量不高。用本机 PowerPoint 将实际收到的 9 页 PPTX 全部导出为 PNG 后检查，客观问题为：纯白背景、九页均使用同一标题/列表版式、封面 28pt、页标题 24pt、正文 18pt、内容集中于左上而留白过多，并且无主题色、分隔、页码、章节节奏或视觉支撑。内容覆盖完整，但多为并列概括，缺少演示文稿的连续叙事。

本地 `_render_pptx` 升级为受控视觉主题：16:9 深色标题页，52pt 标题、20pt 副标题；浅色内容页，36pt 标题和 22pt 正文；蓝/青/紫循环强调色，顶部强调线、章节/页面双位数编号、分隔线、`AIchatbot · MainAgent` 页脚与页码；“下一步/总结/结论/展望/行动”节使用浅青背景收束。标题和正文都使用微软雅黑；顶层 `# ` 标题被视为与 title 重复而忽略，H1–H6/列表/编号前缀在正文中被归一化，避免 Markdown 符号进入页面。

Main LLM 文档工具合同同步升级：PPT 内容直接从 `## ` 开始，不重复 deck title；按总览、分组能力、当前亮点/边界、下一步组织叙事；每页一个主旨、3–5 条简短具体要点，不使用空泛市场化填充和重复句式。该改动改善文字密度、页间逻辑和自动续页数量，不开放联网图片、任意本地素材或模板下载。

升级后生成一份临时 9 页代表性 PPTX，使用本机 PowerPoint 以 1600×900 导出全部页面，组合联系表并检查代表页原图。所有页均正常打开，未发现文字裁切、标题换行、元素意外重叠、页码不一致或页脚越界。临时 PPTX、单页 PNG 和联系表仅保留在系统临时目录作 QA，未进入 `output/main-agent-workspace/`、Git 或 QQ。演示文稿专项技能对字号、信息密度、留白和逐页视觉检查的要求直接影响了本轮升级。定向 103 tests OK（skipped=1），完整回归 601 tests OK（skipped=3），Python AST 149 files OK，pip check 和 `git diff --check` 通过。

主人明确选择保留当前审批顺序：Main LLM 先生成可审查的 title/content 提案，主人确认后才写入 PPTX 并通过 QQ 发送。不改为“审批时看不到最终内容，确认后才调 Main LLM”的意图审批模式。本轮未修改 `.env`、未重启 Bot、未 commit 或 push。

## 2026-07-14 可靠性错误分类与只读周期巡检

主人确认 TXT 未发送是指令未包含“发给我”，不是工具故障；随后明确把下一步转向近期高频错误、超时、失败调用、异常退出、统一分类、可读提示和定期巡检。

新增 `failure_diagnostics.py`，把关键失败统一为配置、模型、权限、网络和数据五类，并产生稳定 code、简要原因和不带副作用的下一步建议。新增密钥、token、password、secret 和 URL 脱敏；未来 `log_ai_event_error` 直接写安全 `category/code/type/message`，MainAgent 观测限制长度。Main LLM、工具执行、正式只读工作和审批恢复失败均接入分类提示；审批失败任务与事件不再持久化任意工具异常原文。PPT 超页、产物完整性、QQ 文件发送、审批上下文和恢复参数缺失均有专用 code。

`/agent 做一次可靠性巡检` 确定性映射到现有 `owner_read_command/ops_health`，近 24 小时错误区改为分类统计，不调用 Main LLM 猜测状态。新增 `scripts/reliability_inspection.py` 与 `scripts/inspect-reliability.ps1`：只读取 `.env` 配置存在性、本机 8080/11434 端口、SQLite immutable read-only schema 和四个固定日志；无时间戳行使用日志文件 mtime 参与窗口过滤，避免旧 TTS/Owner Console 日志污染当前趋势。`-WriteReport` 只原子刷新 Git 忽略的 `output/reliability-inspections/latest.txt`，不接受任意输出路径。

本机实际巡检：当前状态正常，NoneBot 8080 可达，SQLite 只读检查通过，聊天与 MainAgent 模型必填项已配置；最近 24 小时 0 个失败信号，最近 7 天 11 个失败信号（数据类 8、网络类 3、超时 1、失败调用 3、疑似异常退出 0）。这些是历史日志信号，不等于仍有 11 个当前故障或 11 次独立事故。

最终完整回归 607 tests OK（skipped=3，均为 Windows 符号链接权限）；Python AST 594 files OK，pip check 和 `git diff --check` 通过。固定报告 UTF-8 中文重读通过，无替换字符且无残留临时文件。没有调用外部模型/Tavily/QQ，没有自动重试、重启、修改配置、修复数据、创建系统计划任务、commit 或 push。
```

## 2026-07-18 P2.47 结构化可靠性事件第一刀

```text
主人确认 component / operation / category / code / outcome 严格事件合同后，完成 P2.47 第一刀。新增 reliability_events.py 与数据库 schema 7；reliability_event_buckets 按每次进程随机 runtime UUID 和固定五分钟桶聚合，重复事件只增加 occurrence_count，保留 first_seen_at / last_seen_at。表结构不含消息、用户、QQ、session、路径、URL、Key、异常或 metadata 字段；Python 注册表和 SQLite CHECK 同时拒绝未知组件、操作、类别、code 和 outcome。

失败/降级沿用 configuration/model/permission/network/data 五类和现有稳定 code；operation_succeeded、operation_skipped、runtime_started、runtime_stopped 只表达非故障结果。趋势按 component + operation + category + code 聚合；最后失败之后有真实成功才 recovered，成功后再失败为 recurring，无后续成功为 unresolved，skipped 不算恢复。生命周期 start 无对应 stop 时只推断 suspected_abnormal_exit，不声称已证明崩溃。

首批接线覆盖 Main LLM 完整 ActionRequest 生成边界、独立表情分类状态、文档发送前完整性/QQ 单次发送、ProjectDocRAG 重建返回和 Bot startup/shutdown。Main LLM observer 在完整文本提取后才记录成功，空响应等后续错误不会被误记成功；observer 和 SQLite 异常全部 fail-open，不改变主链结果。

临时 SQLite 测试直接检查数据库原始字节，确认原始异常中的 Key、URL 和用户标识未持久化；未知 direct SQL component/operation 被 CHECK 拒绝。核心定向 80 tests OK，相邻表情/MainAgent/文档/RAG 回归 115 tests OK（skipped=1），完整回归 625 tests OK（skipped=3）。本轮未重启 Bot、未发送 QQ、未调用 Main LLM/DeepSeek/Tavily，未开放趋势命令、Owner Console、自动告警、自动清理、自动修复或自动重启，未 commit 或 push。
```

## 2026-07-19 P2.47 最小运行验收

```text
主人明确批准按最小验收方案重启 Bot。旧 bot.py 被停止，新进程于 00:25 启动并加载 P2.47；8080 正常监听，OneBot V11 已连接，stderr 为空。数据库 schema 为 7，首次加载只写入 bot_runtime/lifecycle/runtime_started/succeeded，没有把旧版本进程停止误报为 suspected_abnormal_exit。

主人随后在 QQ 私聊完成普通聊天、/表情意图状态和“不执行工具”的 Main LLM 文字请求。启动后共 3 个 matcher 完成、0 个 matcher 错误；结构化表恰好出现 runtime_started、sticker_classifier/classify_intent/operation_succeeded、main_llm/plan_action/operation_succeeded 三组事件。invalid allowlist rows=0，失败/降级=0，suspected_abnormal_exit=0；没有新增 Agent 任务、审批或 document_delivery 事件，符合“不执行工具、不发送文件”的验收要求。

本次只读核对没有读取或输出聊天历史正文。结构化表列仍严格限定为 schema、时间桶、runtime UUID、component、operation、category、code、outcome 和计数/first/last seen；没有用户、QQ、session、正文、路径、URL、Key、异常或 metadata 列。P2.47 最小运行验收通过。正常 Ctrl+C shutdown 的 runtime_stopped 和强制退出后的 suspected_abnormal_exit 真实注入未执行，保留为可选深度验收；自动告警、修复、重启、趋势 QQ 命令和 Owner Console 仍未开放。
```

## 2026-07-19 P2.47 结构化故障趋势只读命令

```text
主人确认故障趋势与最近错误、可靠性巡检的职责区别后批准第二刀。OWNER_READ_COMMANDS 增加 reliability_trend；“查看故障趋势/查看最近故障趋势/查看可靠性趋势”在 Main LLM 之前确定性进入 owner_read_command。OwnerReadRuntime 和 OwnerRuntimeFactory 注入专用 provider，帮助文本同步增加入口；命令不创建任务/审批，不调用 LLM、Tavily、RAG、外部模型或 QQ 额外发送。

新增 format_reliability_trend_report：最近 24 小时展开 component/operation、类别/code、次数、首末时间和恢复状态，最近 7 天给出次数、组数及未恢复/已恢复/反复发生/证据不足摘要。无故障不声称持续在线；生命周期 insufficient_evidence 不显示“最近成功”。输出不含 runtime UUID、数据库 ID、用户、QQ、正文、路径、URL、Key 或原始异常。

为保证真只读，database.py 新增 SQLite mode=ro 的 connect_read_only；趋势查询不再调用 ensure_database。生产 smoke 查询前后 chatbot.db 大小和 mtime 一致。smoke 发现 18:35 Bot 确实重新启动，上一 runtime 没有 runtime_stopped，因此已有 suspected_abnormal_exit/data/degraded 被正确展示；当前进程、8080、OneBot 和 stderr 正常，不把该信号升级为已证明崩溃。

定向核心 121 tests OK，相邻组合 147 tests OK，完整回归 630 tests OK（skipped=3）。主人随后明确批准重启，Bot 于 20:31 成功加载 `ai_chat`；8080 正常监听，OneBot V11 已连接，启动日志和 stderr 无错误。由于本次使用已批准的强制停止，上一 runtime 再次缺少 `runtime_stopped`，形成第二条预期的 `suspected_abnormal_exit`，不作为命令缺陷。

主人于 20:42 在 QQ 私聊执行 `/agent 查看故障趋势`。真实返回在最近 24 小时和 7 天均统计失败/降级 2 次、1 个故障组：`bot_runtime / lifecycle`、`data / suspected_abnormal_exit`，首次 18:35:22、最后 20:31:39，状态严格为“证据不足”，未误报恢复。报告明确只统计已接入 P2.47 的固定结构化事件，不读取聊天正文或原始异常，并声明未调用 Main LLM、Tavily、RAG 或外部模型，未告警、修复、重试、重启或清理。运行日志确认该 matcher 单次正常完成、0 matcher 错误、stderr 为空；查询后 `chatbot.db` 大小与修改时间仍为启动时数值，符合真只读合同。P2.47 第二刀 QQ live 验收通过。Owner Console、自动告警、自动修复、自动重启和清理仍未开放，未 commit 或 push。
```

## 2026-07-19 P2.47 Owner Console 结构化可靠性只读页

```text
主人批准下一步最小 Owner Console 可靠性页面。新增 OwnerConsoleReliabilitySnapshot 读模型、OwnerConsoleReadRuntime.build_reliability_snapshot、GET-only /api/v1/owner-console/reliability HTTP 合同和 /owner-console/reliability 前端路由。后端以同一生成时刻读取 24 小时与 168 小时趋势，复用 P2.47 分组和恢复状态；前端显示六项摘要、时间窗口切换、组件/类别/恢复状态筛选、故障组表格、五项接入范围和只读安全边界。

接口和页面均不接收用户/会话上下文，不调用 ensure_database、Main LLM、Tavily、MemoryRAG、ProjectDocRAG 或外部模型，不创建任务/审批，不告警、修复、重试、重启或清理。read model 不含 runtime UUID、数据库 ID、QQ、用户、聊天正文、原始异常、路径、URL、Key、堆栈或 metadata；生命周期证据不足继续隐藏最近成功。前端所有请求仍集中在单一 API client 的 GET allowlist，并通过只读守卫。

Owner Console 生产构建后启动在 127.0.0.1:8090。真实 GET 返回最近 24 小时和 7 天均为 2 次失败/降级、1 个 bot_runtime/lifecycle/suspected_abnormal_exit 故障组、状态 insufficient_evidence，接入范围 5 项。查询前后 chatbot.db 大小和 mtime 完全一致；health read_only=true、web_write_enabled=false，所有 LLM/RAG/写副作用标志为 false。

Owner Console 后端套件 40 tests OK，可靠性与持久化相邻 44 tests OK，Python 全量 632 tests OK（skipped=3）；前端 13 tests OK，TypeScript、GET-only guard、Vite production build、pip check 和 git diff --check 通过。当前工具会话未暴露 Browser 技能所需内置浏览器接口，因此没有使用独立自动化绕过限制。

2026-07-20 主人随后打开真实页面完成人工浏览器验收：恢复状态正确显示“证据不足”，最近成功显示符合预期，清除筛选可用；底部 5 项接入范围和只读边界完整，缩小窗口后没有明显重叠。生产数据只有 bot_runtime 一个真实故障组，因此现场无法充分演示跨组件筛选；前端自动化已使用 bot_runtime 与 main_llm 两个故障组验证 7 天切换和本地组件筛选，不为演示向生产数据库写入假故障。第三刀浏览器验收通过。没有重启 Bot，没有自动告警/修复，未 commit 或 push。
```

## 2026-07-20 P2.47 视觉与语音结构化事件接线

```text
主人确认视觉识图和语音合成是高频故障模块，并批准按严格边界进入第四刀。新增 media_reliability.py，视觉和 TTS 分别使用有限确定性映射选择既有稳定 category/code，不把异常原文、图片、语音文本、QQ、路径、URL 或 Key 交给记录器。映射覆盖鉴权、超时、连接、429、模型不存在、无效模型响应、配置错误、数据校验和未知运行状态；observer 自身异常全部 fail-open。

vision.describe_images 只对真实用户图片理解批次观察一次。功能关闭、无 URL、max_images=0、图片等待/缓存和 diagnostic_vision_image_base64 自检不记录；批次全成功为 succeeded、全失败为 failed、部分成功为 degraded。异常业务行为保持原样：已处理 VisionError 继续返回安全失败描述，未知异常记录固定失败后继续抛给既有 Graph 边界。

voice.request_tts 只在通过非空 segments 前置后进入观察边界，覆盖按需服务准备和 TTS HTTP 生成。成功前新增音频必须为真实非空文件、duration>0 且不超过 max_total_seconds 的复核；失败记录固定 code 后继续抛给既有语音错误处理。健康检查、按需待机、候选保存、功能关闭、冷却和文本过长前置拒绝不记录。QQ record 发送发生在 request_tts 返回之后，发送失败不归因到 tts/synthesize，后续若接入应属于 qq_adapter/send_message。

Owner Console 接入范围由历史 5 项更新为 7 项。受控重启 Owner Console 后，生产 /api/v1/owner-console/reliability 已显示 vision/infer 与 tts/synthesize；read_only=true、web_write=false，查询前后 chatbot.db 大小和 mtime 不变，当前失败趋势仍只有原 2 次生命周期事件，没有制造视觉/TTS 假故障。

媒体/可靠性/Owner Console 定向 76 tests OK，视觉语音 Graph、诊断和 QQ 边界相邻 80 tests OK，Python 全量 647 tests OK（skipped=3）；Python AST 148 files、pip check 和 git diff --check 通过。本轮所有媒体测试均使用 fake Ollama、fake TTS HTTP 和临时 SQLite；未调用真实 Ollama，未冷启动或调用 IndexTTS2，未生成或发送真实 QQ 语音，未重启 Bot，未 commit 或 push。下一步真实验收需要先批准重启 Bot，然后分别执行一条图片识别和一条真实 TTS/QQ 语音请求；语音 live 涉及实际显存和 QQ 发送，继续单独确认。

主人随后批准重启 Bot 和最小媒体验收。Bot 于 2026-07-20 01:07:29 启动，8080、OneBot、ai_chat 均正常，matcher、stderr 和 traceback 为 0。强制停止旧进程按合同形成一组 suspected_abnormal_exit/degraded 与新 runtime_started/succeeded；这属于生命周期证据，不归因到媒体组件。

01:11 的真实图片批次收到正常 QQ 回复，但识图失败。结构化表只新增一条 vision/infer/model/invalid_model_response/failed，occurrence_count=1；Ollama 可达、qwen2.5vl:3b 存在并已加载。由于合同不保存模型原始输出，不能进一步断言具体是空描述、无效 JSON、低质量重复还是超长输出。ChatAgent 最终把本次失败角色化为“看不到图片、能力还做不到”，错误暗示永久缺少视觉能力；这不影响结构化事件正确性，但真实识图和用户失败文案均未通过验收。未自动停止 Ollama、重试图片或修改文案，后续需主人单独批准确定性失败提示与受控复测。

01:17 的首条真实语音请求只新增 tts/synthesize/network/request_timeout/failed，未生成音频或发送 QQ。TTS 进程约在请求后启动，服务健康落在 45 秒 startup wait 边界之后，health 为 ok=true、loaded=false；代码顺序证明该失败早于 /tts 请求和 IndexTTS2 加载，不能归因为显存不足或模型推理慢。当日下午再次冷启动在 14:00:17 产生同一固定超时；服务在线后继续执行的请求于 14:06:28 只新增一条 tts/synthesize/operation_succeeded/succeeded。主人确认真实 QQ 语音收到，合成产物复核和后续 QQ 送达均通过；同一 runtime 的最后失败之后出现成功，request_timeout 故障组具备 recovered 证据。

成功后实时 health 为 ok=true、loaded=true、language=zh；IndexTTS2 GPU allocated 约 6931.8 MiB、reserved 约 7476.0 MiB，证明本机约 8GB 显存可以完成该条真实合成，但余量较小。TTS 模型按需加载并在空闲 600 秒后卸载，Web 服务在线与模型驻留必须分开表述。未自动重试、卸载视觉模型、重启服务、修改 45 秒阈值或发送额外 QQ 消息。第四刀的 TTS 结构化恢复和端到端 live 通过；视觉只通过失败事件观察验收，功能与失败文案仍待下一阶段。

主人批准实现确定性视觉失败提示，但明确不自动重试、不停止或重启 Ollama。新增固定 `VISION_FAILURE_DESCRIPTION` 与 `VISION_FAILURE_REPLY`；处理过的 VisionError、图片源无法解析和 Graph 捕获的未知异常都只把固定失败描述交给聊天链，不再把异常类型或细节放入图片上下文。`ChatUserContent` 增加默认 false 的 `vision_failed`，只在非空描述全部为固定失败标记时置 true；`generate_chat_text_response` 在任何 `ask_llm` 前直接返回“本次图片识别失败了，请稍后再试，或者换一张更清晰的图片。”，因此 ChatAgent 无法再把单次失败扩写成永久没有视觉能力。两条文本发送路径在该固定回复上同时跳过远程表情分类和本地自动附件，避免正文确定后又出现非确定性附加消息。部分成功批次仍进入 ChatAgent 并保留合格观察；视觉模型对每个 URL 的调用次数、全失败/部分失败结构化结果和 observer fail-open 均不变。

新增测试确认全失败固定提示、不包含原始异常中的 Key/URL、单图失败不重试、部分成功不短路，以及生产源码的失败 guard 位于 Chat LLM 调用之前。视觉专项 31 tests、可靠性与 Graph/适配器相邻 74 tests、合计 105 tests OK；完整 Python 回归 650 tests OK（skipped=3），src/tests AST 145 files 和 git diff --check 通过。未调用真实视觉模型，未停止或重启 Ollama，未重启 Bot，QQ 文案 live 待单独批准；未 commit 或 push。

主人随后批准只重启 Bot 加载补丁，并继续禁止停止/重启 Ollama和自动图片重试。旧 Bot 被受控强制停止，新进程于 15:00:08 启动，15:00:10 加载 ai_chat 并监听 127.0.0.1:8080，15:00:37 OneBot V11 连接成功；stderr 为空。强制停止按既有合同形成生命周期疑似异常退出证据，不归因到视觉。

主人在 QQ 手动发送一条图片请求并反馈收到连贯的可见内容描述。安全结构化表在 15:15:59 只新增一条 vision/infer/operation_succeeded/succeeded，occurrence_count=1；本次 runtime 没有第二条视觉事件。运行日志为 1 个 matcher 正常完成、0 matcher 错误、0 traceback，8080 与 OneBot 在线、stderr 为空。该成功晚于 01:11 的 invalid_model_response/failed，因此视觉故障组具备 recovered 证据，真实识图功能验收通过。由于本次走成功路径，固定失败提示没有在 QQ 中触发，不能宣称失败文案 live 已覆盖；自动化证据保持有效，不人为制造模型故障。本文与结构化事件均未保存图片内容或主人贴出的回复原文。本轮未停止/重启 Ollama、未自动重试图片、未 commit 或 push。

主人随后批准重启 Owner Console，并只读验收 bot_runtime、vision、tts 三组件筛选及视觉/TTS 两组恢复。8090 原先无进程，start-owner-console 于 15:36 完成启动，PID 19748 在 127.0.0.1:8090 监听；可靠性页面路由返回 HTTP 200、UTF-8 HTML。生产 `/api/v1/owner-console/reliability` 为 read_only=true、web_write_enabled=false，coverage 7；查询前后 chatbot.db 大小和 mtime 均不变，boundary 中 ensure database、正文/异常/用户/runtime/database ID 暴露、LLM、RAG、告警、修复、重试、重启、清理和写副作用全部 false。没有为筛选制造假故障。

真实 24 小时与 7 天数据当前均为 9 次失败/降级、4 个故障组：bot_runtime/lifecycle/suspected_abnormal_exit 5 次、证据不足；tts/synthesize/request_timeout 2 次、已恢复；vision/infer/invalid_model_response 1 次、已恢复；此外 sticker_classifier/classify_intent/data_validation_failed 1 次、未恢复。该表情分类器事件发生于 15:16:05，是生产结构化观测，不因原验收只点名三个组件而隐藏或删除，也不自动修复。前端同一精确谓词对生产数组计算为全部 4、bot_runtime/vision/tts 各 1、recovered 2 且恰为 tts/vision，vision+recovered 与 tts+recovered 各 1；源码确认清除筛选同时把 component/category/recovery 复位为 all。

ReliabilityPage Vitest 1 test、TypeScript typecheck 和 GET-only guard 通过；guard 检查 27 个 TypeScript 文件、GET-only fetch、只读 allowlist、受控 timer、页面路由及无写式 API 名称。当前会话虽然列出 Browser 技能，但未暴露其唯一允许的内置浏览器控制接口；按技能边界没有改用外部 Playwright 或其他浏览器自动化。主人随后人工打开生产页面，反馈各阶段均符合预期：bot_runtime、vision、tts 组件筛选正确，recovered 只保留 vision/tts 两组，组合筛选结果正确，清除筛选恢复全部 4 组。至此生产 API、页面可达、前端自动化、源码谓词、生产数据计算和真实 DOM 人工验收全部通过。未重启 Bot/Ollama/TTS，未告警、修复、重试、清理、commit 或 push。

主人批准只读排查新 sticker_classifier/classify_intent/data_validation_failed，明确不改配置、不重试、不读取聊天正文。结构化表只含 15:16:05 一次失败，前两次成功均早于失败，故 unresolved 正确。代码有限映射显示 data_validation_failed 只对应 `input_invalid`；配置存在性与默认预算安全检查为远程分类/附件开启、Key/Base/模型均已配置、timeout 8、max input 2400。调用路径保证 user/reply 类型为字符串且回复已发送；主人进一步确认当次只发送图片，因此纯文本 user_text 为空是已证实根因。纯函数占位复现为 status=input_invalid、transport_calls=0；该路径未调用 DeepSeek、未消耗分类 token、未加载本地表情库。库只读复核为 schema 2、revision 18、enabled 14、disabled 2。排查未读取消息/回复正文、QQ、Key、URL 或异常原文，未修改任何状态。

主人随后批准纯图片消息在远程分类前本地跳过，同时要求超长和类型错误继续保留 data_validation_failed。`schedule_remote_sticker_classifier_shadow` 在 sample ID 后、附件频率 preflight 前新增精确门控：仅 `isinstance(user_text, str) and not user_text.strip()` 时写内存安全快照 `skipped / empty_user_text / preflight_blocked` 并 return。该分支不调用 classify、可靠性记录器或发送函数。底层 classify 对空文本、非字符串和超长仍返回 input_invalid；只有调度器已知的合法纯图片空文本被跳过，因此不会掩盖真实错误。分类器专项 8 tests，reliability runtime 7、attachment 5、library 29（skipped=2）、media reliability 7，合计相邻 56 tests OK；完整回归 650 tests OK（skipped=3）。本轮未调用 DeepSeek、未发送表情、未重启 Bot/Ollama/TTS、未改配置、未清理历史事件、未 commit 或 push。门控待批准重启 Bot 加载；旧故障只允许由未来真实合格文本分类成功自然 recovered。

主人批准后只重启 Bot，不重启 Ollama、不自动重试或发送表情。新进程于 21:26:05 启动，21:26:07 加载 ai_chat 并监听 8080，21:26:34 OneBot V11 连接，stderr 为空。重启前只读基线意外但合法地发现 21:25:23 已有一条真实 sticker_classifier operation_succeeded，晚于 15:16:05 的 data_validation_failed，因此历史故障已自然 recovered；未删除、改写或伪造事件。

主人发送纯图片后执行 `/表情意图状态`，真实返回样本 1、classifier_status=skipped、无有效建议、confidence=0、decision_reason=empty_user_text、匹配 0、无选中 ID；自动附带显示“频率门控中，未调用分类模型”。结构化 classifier 基线复核四个桶及所有 occurrence_count/last_seen 完全未变化，证明没有写 succeeded/failed/skipped、没有进入 DeepSeek observer 或表情发送。21:26 后运行日志为 3 个 matcher 完成、0 错误、0 traceback，8080 与 OneBot 在线、stderr 为空。同期 vision 结构化表有 21:50:02 data_validation_failed 与 21:50:43 operation_succeeded，故该组也 recovered；不归因到 sticker classifier。本轮 Owner Console 最新趋势为失败/降级 9 次、5 组，recovered 4、unresolved 0、recurring 0、insufficient_evidence 1。

主人批准继续下一步后，完成 `/表情意图状态` 的最小展示细分。新增纯展示函数按 `attachment_status + decision_reason` 组合映射：仅当 `preflight_blocked + empty_user_text` 同时成立时显示“纯图片无文本，已在本地跳过；未调用分类模型，未发送表情”；cooldown、message_gap、hourly_cap、preflight_unavailable 等真实阻断继续显示“频率门控中，未调用分类模型”，其他既有状态和未知状态回退保持原义。状态 handler 移除内联标签并调用该纯函数。此改动不触碰纯图片门控、结构化事件、DeepSeek 调用、自动附件或发送逻辑。

分类器、状态命令和附件定向 21 tests OK；完整 Python 回归 651 tests OK（skipped=3），pip check 与 git diff --check 通过。未调用模型、未写可靠性事件、未发送表情，未停止或重启 Bot/Ollama/TTS/Owner Console，未重试图片/分类，未 commit 或 push。主人随后批准只重启 Bot。旧目标进程被受控停止，新进程于 2026-07-21 00:50:36 启动，00:50:39 成功加载 ai_chat、启动 8080 和 OneBot V11 adapter，00:51:05 OneBot WebSocket 连接；stderr 为空。未停止或重启 Ollama/TTS/Owner Console，未自动发送图片、调用表情分类或发送表情。展示补丁已经加载，但仍不得宣称 QQ 新文案 live 已通过；下一步由主人发送一条纯图片消息，再执行 `/表情意图状态` 做最小文案验收。

2026-07-21 10:41 的验收前只读检查发现 00:50 实例已不在线，8080 未监听；可访问日志最后活动为 01:37:13，没有正常 shutdown、stderr 或 traceback。生命周期表保留该实例的 `runtime_started` 而没有 `runtime_stopped`，因此只能记录为疑似非正常退出或外部终止，不能推断具体原因；开发代理没有自动重启。当前 Bot 启动链于 10:43:20 恢复，8080 只有一个监听者且归属于该 Bot，OneBot 会话已建立。

主人随后只发送一张图片，等待正文回复完成后执行 `/表情意图状态`。QQ 真实返回样本 1、classifier_status=skipped、无有效建议、confidence=0.00、decision_reason=empty_user_text、匹配 0、影子选中 ID 无；最后一行精确显示“纯图片无文本，已在本地跳过；未调用分类模型，未发送表情”。验收前后 `sticker_classifier` 仍为同四个结构化桶，所有固定字段、occurrence_count 和 last_seen_at 逐项完全一致，没有新增 succeeded、failed、degraded 或 skipped；历史 data_validation_failed 与其后真实成功形成的 recovered 证据保持原样。当前 8080 在线且有已建立会话，可访问错误记录仍为 stderr 空、0 traceback；没有自动重试图片、调用 DeepSeek、进入本地表情选择或发送表情。Bot 已加载且 QQ 新文案 live 已通过，P2.47 这项纯图片门控与展示文案正式收口；未开始下一阶段开发，未 commit 或 push。
```

## 2026-07-21 P2.48 Owner Console 可靠性可用性与演进设计审计

```text
主人批准先做设计与现状审计，要求以实用性、可读性和发展性为主要标准。只读检查确认当前可靠性页的数据合同、24 小时/7 天窗口、恢复推导、本地筛选和只读边界均正确，但页面仍以六个同权指标、三个筛选器和 1080px 七列表格为主要内容；component、operation、code 直接以英文内部标识展示，只有类别和恢复状态中文化。筛选只改变表格，不解释筛选后的共同结论，也没有告诉主人最需要关注什么、证据为何充分或不足、下一步应检查哪一层。

P2.48 第一优先级改为可靠性解释层，而不是立即增加 external-read 时间线。新设计规定 component/operation/code 使用集中式中文标签，英文原值只放次级技术详情；自然总结由固定结构化数据、恢复状态和类别建议确定性生成，不调用 LLM，不读取正文或原始异常。总结最多展开三组重点问题，排序为 recurring、unresolved、insufficient_evidence、recovered，并明确区分未恢复、反复发生、已恢复和证据不足。筛选改为中文“功能 / 问题类别 / 证据状态”，筛选后自然总结与证据明细必须同步变化。

当前 24 小时和 7 天窗口长度不同，不能据此生成故障“上升/下降”结论；第一刀只解释当前窗口结构。后续只有新增 current_24h 与 previous_24h 等长不重叠比较或固定日桶后，才允许环比措辞。页面 stale 只表示快照多久未刷新，不能把 vision、tts、文档交付和表情分类等按需组件长时间无事件误判为服务陈旧；若实现动态刷新，只复用现有受控 hook，业务页面不得新增 timer。

external-read 当前只有最近正式任务快照，没有已评审的多任务历史合同和明确排障问题，因此时间线延后，避免为了展示扩大数据面。实现路线定为 P2.48a 中文解释与确定性总结、P2.48b 信息层级与响应式、P2.48c 自动化及主人真实桌面/窄屏/手机验收。审计时 Owner Console 8090 未监听，未擅自启动；Browser 技能要求的内置控制接口未暴露，未改用外部 Playwright 绕过。本文只写设计和状态文档，没有修改运行代码、API、配置或服务，也没有执行模型、探针、自动处置、commit 或 push。详细设计见 docs/owner-console-reliability-usability-design.md。
```

## 2026-07-21 P2.48a Owner Console 可靠性最小可读性优化

```text
主人批准继续实现，但要求不要向页面增加太多内容，主要优化原有界面；中文标签只能提供解读，不能覆盖或隐藏原始英文报错。实现因此没有增加重点问题大卡片、图表、external-read 时间线或新的复杂筛选。Python read model 为每个趋势项新增 component_label、operation_label、code_label，为 coverage 新增中文标签；原 component、operation、category、code、recovery_state 字段全部保留，FastAPI 契约测试强制核对中英文字段同时存在。

可靠性页仍使用原来的工具栏、指标、故障面板、筛选、证据表和安全边界。故障面板内只新增一段紧凑的两行确定性总结，直接基于当前 filteredRows 生成；筛选后总结同步变化，不调用后端、不调用 LLM。六项指标压缩为四项；筛选显示“中文（英文稳定值）”；原七列表格把首次失败、最后失败、最近成功合并为时间证据列，缩为五列。每行中文解释下一行直接显示英文 component / operation 和 category / code，证据状态同时显示中文 label 与英文 recovery_state；英文报错不是 tooltip，也没有被中文替换。

总结固定覆盖：当前需要关注、只有恢复证据、只有证据不足、筛选为空和窗口无记录。它不会将 recovered 写成根因永久解决，不会将 insufficient_evidence 写成未恢复；当前没有等长前一窗口，因此不输出上升/下降结论。Owner Console read model 与 FastAPI 定向 34 tests、可靠性页 3 tests、完整 Python 651 tests OK（skipped=3）；完整前端 15 tests、TypeScript、Vite production build、GET-only guard、Python AST 144 files、pip check 和 git diff --check 通过。

实现期间 Owner Console 8090 仍未监听，未自动启动或重启，因此当前生产服务尚未加载新增字段，真实桌面/窄屏页面可读性待主人批准后验收。本轮没有调用 LLM/RAG、读取正文或原始异常、写可靠性事件、修改配置、告警、修复、重试、重启或清理，也未 commit 或 push。
```

## 2026-07-21 P2.48a 可靠性页 live 验收与 P2.48b 诊断页最小可读性优化

```text
主人批准启动 Owner Console 后，可靠性页生产路由返回 200，API 为 read_only=true、web_write_enabled=false；当前可靠性数据与新增中英 label 均以严格 UTF-8 正确返回，GET 前后数据库大小和 mtime 不变，stderr 没有 ERROR、Traceback 或 Exception。主人随后在真实页面确认“目前可读性很高”，因此 P2.48a 可靠性页最小可读性优化 live 验收通过。没有把 PowerShell 对 application/json 的旧式解码显示问题误判为浏览器编码错误。

主人批准按同一标准优化诊断页：不向页面加入过多内容，以重整原界面为主，中文标签只能解释、不能覆盖英文报错。只读审计确认原页面八个 SnapshotCard 的 section.ok 实际表示区块读取成功，但 UI 显示为“正常/异常”，容易被误读为视觉、TTS、Ollama 或 Bot 已完成实时健康探测；summary_text 又通常与 display_lines 完全重复。现有 API 已提供足够的安全 key=value 证据，因此本轮采用纯前端实现，没有修改后端合同或重启 Owner Console。

页面仍保留工具栏、八个原有快照区块、两个观测面板和运行边界。工具栏改为读取成功/读取异常计数；只增加一段紧凑的两行确定性解读，明确总体结论只针对快照区块。卡片状态改为“已读取/读取异常”，中文区块名下直接保留英文 section.title；重复 summary_text 不再二次展示。已知明细按“中文含义、解释值、原始英文 key=value”紧邻排列，未知行原样保留，英文 error 置于明确的“原始错误”区域。external_probes、Ollama/vision/TTS probe、近期错误日志、检索和索引重建的 false 都解释为未执行的只读边界，不据此声称服务异常；recent_errors_collected=false 明确写为“未采集，不代表没有错误”。空观测只说明本次快照没有结构化记录。

新增 DiagnosticsPage 3 tests；完整前端 18 tests、TypeScript、Vite production build、GET-only guard 和 git diff --check 通过。新静态包已由当前 8090 原进程直接加载，诊断路由返回 HTTP 200，包内包含新中文解读与原始英文证据；API 仍为 read_only=true、web_write_enabled=false，GET 前后数据库大小和 mtime 不变。8090 没有重启，stderr 只有 4 行正常启动 INFO，ERROR/Traceback/Exception 为 0。当前等待主人真实页面验收；在反馈前不宣称 P2.48b live 已通过。没有调用 LLM/RAG/DeepSeek、主动探测、告警、修复、重试、重启、配置修改、清理、commit 或 push。
```

## 2026-07-21 P2.49a ProjectDocRAG 固定手动诊断第一刀

```text
主人确认诊断页可读性没有问题，但指出现有八区块主要是配置目录，只显示功能是否启用，没有执行诊断动作或形成实际问题判断。主人进一步明确：初期只读边界可以逐步放开，但在通用任务审批流建立前，只允许主人批准的固定工作流；自动探测不做，手动探测先从记忆/文档 RAG 检索开始，再发展 Main LLM 固定用例，最后才进入高显存的 TTS 与视觉。Owner Console 随后按主人要求关闭，8090 当前不监听。

P2.49 新合同是“默认快照只读、配置和业务数据写入关闭、固定手动诊断动作逐项开放”。第一刀只注册 ProjectDocRAG 固定真实检索；没有 MemoryRAG、Main LLM、TTS 或视觉按钮。普通 start-owner-console 继续关闭动作；只有显式 -EnableProjectDocRagProbe 才在本次进程开放。页面第一次点击只展开确认，第二次确认才发送唯一 POST。后端要求 loopback Host、完全同源 Origin、application/json、固定 X-Owner-Console-Action、固定 confirmation，以及通过同源状态 GET 设置的进程内 HttpOnly/SameSite=Strict 动作 Cookie。动作 session 不渲染、不记录，重启后失效。

源码审计发现现有 retrieve_project_docs 最终会调用 ensure_database 和可提交的 connect，不能直接满足 database_write=false。P2.49a 因此新增专用 SQLite mode=ro 查询，不执行 schema 初始化，只统计 ProjectDocRAG 活动文档与当前 provider/model 有效向量，并只 SELECT source_id、chunk_index 和 embedding；文档 content/title 不进入查询结果。固定问题只在后端内存使用，目标为新的 P2.49 设计文档，top_k=5。Ollama provider 新增 embed_once，只调用当前 /api/embed 一次，不走 legacy fallback、不重试。结果只返回计数、最高相似度、阶段、中英 code 和固定零副作用字段；不返回查询、文档标识、片段、原始异常、Key、URL、QQ 或用户。

运行状态只保留在 Owner Console 当前进程内；不新增数据库表，不写 Agent task、approval、可靠性事件或聊天历史。同一进程只允许一个手动诊断，不排队；并发返回 409。动作 envelope 明确 read_only=false、manual_runtime_action=true，同时 configuration_write_enabled=false、business_data_write_enabled=false。自动诊断、索引重建、MemoryRAG、CombinedRAG、DevContext、Main LLM、TTS、视觉和 QQ 副作用继续关闭。

自动化全部使用 fake embedding 和临时 SQLite，没有调用真实 Ollama或真实 RAG。专用测试确认 mode=ro 前后数据库大小和 mtime 不变、结果没有 content、embed_once 无 fallback、并发 fail closed、错误 Origin/Cookie/Header/确认被拒绝、页面必须二次确认且只执行一次。RAG 相邻 20 tests、Owner Console 44 tests、完整 Python 656 tests OK（skipped=3）；完整前端 19 tests、TypeScript、Vite production build、只允许一个固定 POST 的边界守卫、Python AST 146 files、pip check 和 git diff --check 通过。P2.49 文档完成后 ProjectDocRAG 已重新构建且无错误。P2.49a 代码与静态包已完成，但 Owner Console 保持关闭，真实 fixed retrieval 尚未执行；下一步等待主人批准用显式开关启动并手动验收。
```

## 2026-07-21 P2.49a 首次 live 前置门控修复

```text
主人批准以 -EnableProjectDocRagProbe 启动 Owner Console；8090 单一监听、诊断页 200，只有 project_doc_rag_fixed_retrieval 启用，自动诊断、配置写入和业务数据写入均关闭，GET 前后数据库大小与 mtime 不变。主人第一次点击只展开确认，第二次确认成功进入唯一 POST，但结果立即为“项目文档 RAG 当前未启用”，stage=preflight、code=project_doc_rag_disabled、计数全零。

验收后只读核对确认 run_id=1、attempt_count=1，index_rebuild_executed、database_write_allowed、llm_called、dev_context_called 和 automatic_retry 全部 false；源码顺序证明返回发生在 count_reader 和 embed_once 之前，因此本次没有真实 embedding 或 SQLite 检索。8090 保持单一监听，stderr 只有 4 行启动 INFO，ERROR/Traceback/Exception 为 0，没有自动重试。

根因是执行器错误地把生产 enable_project_doc_rag 与主人单独批准的 OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED 绑定。生产开关控制原有 MainAgent/研发上下文运行链；专用开关才是固定手动工作流的执行授权。主人批准最小修复后，没有修改 .env 或全局启用 ProjectDocRAG，而是删除生产开关硬阻断，将其作为 runtime_feature_enabled=false 的中英证据显示，并继续执行专用只读索引计数、一次 embed_once 和一次前五项验证。

新增回归直接令 enable_project_doc_rag=false，确认显式启用的手动 executor 仍调用固定 query 一次并返回 runtime_feature_enabled=false；专用动作关闭时的 403、同源鉴权、无 fallback、无重试和零写入边界保持不变。修复后手动诊断定向 4 tests、诊断页 4 tests、完整 Python 656 tests OK（skipped=3）、完整前端 19 tests、TypeScript、Vite build、单一固定 POST 边界守卫和 git diff --check 通过。等待文档索引同步并仅重启 Owner Console 后，由主人第二次手动点击验收；开发代理不自动重试。
```

## 2026-07-21 P2.49a ProjectDocRAG 手动真实检索 live 通过

```text
最小修复、完整回归、静态构建和 ProjectDocRAG 同步完成后，按主人批准只重启 Owner Console；新实例在 127.0.0.1:8090 单一监听，只有 project_doc_rag_fixed_retrieval 手动动作启用，自动诊断、配置写入和业务数据写入关闭，latest_run 为空，证明开发代理没有自动重试。stderr 只有 4 行启动 INFO，ERROR/Traceback/Exception 为 0。

主人在页面第二次手动点击并确认，真实结果为“固定项目文档真实检索通过”：run_id=1、attempt_count=1、status=completed、outcome=succeeded、stage=result_validation、code=project_doc_rag_probe_succeeded，同时显示生产功能未启用与 runtime_feature_enabled=false。ProjectDocRAG 活动文档片段 1620、当前 ollama/bge-m3 有效向量 1620；前五项返回 5，固定目标文档命中，最高相似度 0.728。

验收后只读核对确认数据库 mtime 早于本次动作开始，证明本次动作没有改写数据库；index_rebuild_executed、database_write_allowed、llm_called、dev_context_called、automatic_retry 全部 false。SQLite mode=ro 复核仍为 1620 个项目文档与 1620 个有效向量，8090 单一监听、stderr 无错误。页面没有显示固定查询或文档片段，也没有自动执行 MemoryRAG、Main LLM、TTS、视觉、索引重建或第二次检索。

至此 P2.49a 同时完成固定工作流注册、同源动作鉴权、二次主人确认、一次真实 embedding、一次只读前五项检索、生产开关证据化、中英原始 code、数据库零写入和真实页面验收，live 正式通过。后续阶段不得自动开始，等待主人决定是继续 P2.49b MemoryRAG 一致性，还是先收口提交当前累计改动。
```

## 2026-07-21 P2.49b MemoryRAG 索引一致性手动诊断

```text
主人当时明确批准进入 P2.49b MemoryRAG 索引一致性检查，但真实私人记忆检索仍需单独审批。P2.49b 因此注册固定 memory_rag_index_consistency，只使用 SQLite mode=ro 核对 MemoryRAG 活动文档、当前 provider/model/content_hash 有效向量、事实/偏好/会话摘要三类缺失向量、来源映射和软删除历史文档向量。SQL 不选择 content 或 summary；provider 对象只提供 provider/model 身份，不调用 embed/embed_once，不执行私人查询，不访问 Ollama，不调用 Main LLM、DevContext 或 CombinedRAG。

普通启动继续关闭所有手动动作。新增独立 -EnableMemoryRagConsistencyProbe，与 -EnableProjectDocRagProbe 分开控制页面和 POST；两个动作共享一个进程内运行锁，不能并发、排队或自动重试。MemoryRAG POST 使用固定路径、固定 confirmation、固定 X-Owner-Console-Action，并复用 loopback 完全同源、HttpOnly SameSite=Strict 进程 Cookie 和严格 application/json 合同。结果只保留在 Owner Console 进程内，不写 Agent task、approval、reliability、聊天或诊断表。

结果明确区分 attention 与 failed。来源映射缺口优先返回 memory_rag_source_mismatch；活动文档缺向量返回 memory_rag_active_embedding_gap；空索引返回 memory_rag_index_empty；全部一致才返回 memory_rag_consistency_succeeded；只有只读执行不可用才返回 failed/memory_rag_consistency_unavailable。当前安全审计为活动文档 37、有效向量 35、缺失 2，缺失均为 manual_fact，来源缺失 0，软删除历史文档向量 5，因此首次 live 预期为 attention，而不是执行失败，也不会自动补向量或清理历史记录。

临时 SQLite 测试确认读前后数据库大小与 mtime 不变、SELECT 不读取 content/summary；provider identity fake 确认 embedding 未调用；并发测试确认 ProjectDocRAG 执行期间 MemoryRAG 返回 busy；API 与页面测试确认独立开关、403 fail closed、同源鉴权、二次确认、一次固定 POST、中英 code 和私人内容缺席。Owner Console 相邻 50 tests、RAG/QQ 边界相邻 41 tests、完整 Python 662 tests OK（skipped=3）；完整前端 20 tests、TypeScript、Vite production build、两个固定 POST 边界守卫、Python AST 146 files、pip check 和 git diff --check 通过。

P2.49b 文档第一次同步后，仅停止并重启 Owner Console，自身于 2026-07-22 00:40 加载新代码；Bot、Ollama 和 TTS 未操作。8090 单一监听，ProjectDocRAG 与 MemoryRAG 两个固定工作流均启用，自动诊断、配置写入和业务数据写入关闭；latest_run、project_doc_rag_latest_run、memory_rag_consistency_latest_run 全为空，证明开发代理没有自动执行。stderr 只有 4 行启动 INFO、0 个 ERROR/Traceback/Exception，启动前后数据库大小与 mtime 不变。当前等待主人在页面二次确认后手动验收；没有修改 .env、执行真实私人记忆检索或 embedding、索引重建、修复、commit 或 push。
```

## 2026-07-22 P2.49b MemoryRAG 索引一致性主人 live 通过

```text
首次加载实例后来在没有 shutdown、ERROR 或 Traceback 日志的情况下消失；三个 latest run 当时仍为空，因此没有证据表明退出与诊断动作有关，也不臆测根因。为继续主人已要求的验收，只重新启动已停止的 Owner Console，没有停止或重启 Bot、Ollama 或 TTS。恢复后 8090 单一监听、两个固定工作流启用、三个 latest run 仍为空，stderr 0 错误。

主人第一次点击展开确认、第二次确认后，页面快速显示“2 个活动记忆文档缺少当前有效向量”和“需要关注”。生产功能已启用；活动文档 37、有效向量 35、缺失 2，事实/偏好/会话摘要为 10/3/24，各自缺失向量为 2/0/0，来源缺失 0，软删除历史向量 5。原始英文证据为 workflow=memory_rag_index_consistency、stage=result_validation、code=memory_rag_active_embedding_gap，并直接显示 memory_content_read=false、private_memory_query_executed=false、embedding_called=false。

后端只存在 run_id=1、attempt_count=1，elapsed_ms=32；Owner Console access log 中该 MemoryRAG POST 恰好 1 次，ProjectDocRAG 最近结果仍为空，证明没有提前运行或自动串行执行。动作快是因为只执行本地 SQLite mode=ro 固定计数，没有 embedding、私人检索、模型或网络等待。验收前后数据库大小均为 26775552 字节，mtime 均为 2026-07-22T03:30:40.3271009Z；index_rebuild_executed、database_write_allowed、llm_called、dev_context_called、automatic_retry 全为 false。8090 保持监听，stderr 4 行启动 INFO、0 个 ERROR/Traceback/Exception。

P2.49b 的二次确认、真实一致性判断、attention/failed 区分、中英证据、私人正文不读取、embedding 不调用、数据库零写入、无自动修复和无自动后续动作同时通过，live 正式收口。2 条缺失 manual_fact 向量仍保持原状；真实私人记忆检索、向量补建和 P2.49c Main LLM 固定合同测试均未自动开始，等待主人另行批准。
```

## 2026-07-22 P2.49c Main LLM 固定合同测试设计草案

```text
主人批准先写固定合同设计供审阅，本轮只更新设计和状态文档，没有实现后端、HTTP、前端或启动开关，也没有调用真实 Main LLM。现状审计确认当前 Main LLM 使用独立 MAIN_LLM_API_KEY/BASE_URL/MODEL/TIMEOUT 配置，生产 Action Planner 会注入可见工具合同并通过 observer 写结构化 reliability event，因此不能直接作为 P2.49c 执行入口。当前 ChatOpenAI 构造也未显式关闭 SDK 重试；本机依赖下现有方式最终使用 2 次默认重试，不符合固定单次测试。

设计草案将工作流固定为 main_llm_fixed_contract，只发送后端注册的两条合成消息，期望唯一五字段 JSON：contract_version=main_llm.fixed.v1、probe_id=p2_49c、marker=amber-17、sum=42、status=ok。专属 executor 不创建 MainAgentState、不进入 MainAgentGraph、ToolRegistry、Policy 或工具执行，不挂 reliability observer；client 固定 max_retries=0、streaming=false、30 秒硬超时、15 秒关注阈值、256 completion tokens 和 1024 字符本地上限。响应必须精确匹配字段、类型和值，且 tool_calls/invalid_tool_calls 为空；原始 prompt、响应和异常只在局部内存用于校验，不返回、不记录、不持久化。

结果区分 succeeded、attention 和 failed：精确合同、usage 与延迟全部合格才 succeeded；已得到响应但合同不匹配、usage 缺失或延迟偏高为 attention；配置、鉴权、模型、限流、超时、连接或请求拒绝为 failed。页面只显示模型名、延迟、有限 token 计数、英文 workflow/stage/code、合同与工具证据和固定零副作用布尔值，不显示 prompt、响应正文、异常、Key、URL 或用户内容。

草案建议新增独立 -EnableMainLlmContractProbe、固定 POST /api/v1/owner-console/manual-diagnostics/main-llm-contract、固定 Header/confirmation，并与现有 ProjectDocRAG、MemoryRAG 共享全局锁。实现阶段必须只用 fake LLM 并完成完整回归；代码通过后仍需主人第二次明确批准，才可只重启 Owner Console 并由主人页面二次确认执行一次真实模型 live。本轮未修改 .env、未执行 RAG/私人记忆、未修复 2 条缺失向量、未重启服务、未 commit 或 push。
```

## 2026-07-22 P2.49c Main LLM 固定问答合同 fake-only 实现

```text
主人确认第一阶段可以采用固定合同，但主要判断应是 Main LLM 能否回答问题、能否正常运行；对于任意问题应该选择何种工具，不适合试图通过一次诊断解决。实现据此继续保持无工具隔离，但明确不把工具选择质量作为结论：专属 executor 不向模型提供候选工具，页面也直接说明本次结果不代表任意问题质量或工具选择能力。

新增 owner_console_main_llm_contract.py，只发送后端注册的固定 system/user messages，期望 contract_version=main_llm.fixed.v1、probe_id=p2_49c、marker=amber-17、sum=42、status=ok 的精确五字段 JSON。响应允许字段重排但不允许缺失、额外或重复键，不接受 Markdown fence、尾随正文、空文本、超 1024 字符或 tool_calls/invalid_tool_calls。完整响应只在局部内存中用于合同、token usage 和工具隔离证据校验，结果不含 prompt、响应正文、异常、Key 或 base URL。

专属 ChatOpenAI 构造固定 max_retries=0、streaming=false、timeout=30、max_tokens=256，不发送 temperature、response_format 或 tools。执行器只调用一次同步 invoke；配置、401/403、404、429、timeout、connection、400 和未知异常映射为固定 stage/code，异常原文不进入运行 DTO。运行结果只保存在 Owner Console 进程内，新增 main_llm_contract_latest_run；与 ProjectDocRAG、MemoryRAG 共享同一全局锁，不排队、不自动重试或自动串行。

新增独立 -EnableMainLlmContractProbe 与 OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED、固定 POST /api/v1/owner-console/manual-diagnostics/main-llm-contract、固定 Header/confirmation、同源 Cookie 边界、HTTP route contract、前端第三个紧凑二次确认面板和三 POST 精确 allowlist。页面显示模型、延迟、有限 token 计数、回答合同、英文 workflow/stage/code、llm_called、client_automatic_retry=false、tool_definitions_sent=false 和 database_write_allowed=false，不显示固定问题或回答正文。

自动化全部使用 fake model；一次 Owner Console 全邻域运行曾因同进程既有 openai stub 与真实 langchain_openai 导入冲突产生 1 个测试隔离错误，产品逻辑未失败。测试随后改为显式注入本地 langchain_openai fake module，既验证最终构造参数又不导入真实 SDK，复跑通过。最终 Owner Console 全邻域 62 tests、完整 Python 674 tests OK（skipped=3）；完整前端 21 tests、TypeScript、Vite production build、三固定 POST guard、Python AST 148 files、pip check 和 git diff --check 均通过。

当前 8090 后端实例没有重启，故新 Main LLM POST 和独立开关尚未加载，也没有自动预跑或真实模型调用。前端静态包虽已构建，但旧后端状态不返回 main_llm_contract_enabled=true，因此页面不会开放动作。未修改 .env，未查询私人记忆或 RAG，未修复 2 条缺失向量，未操作 Bot/Ollama/TTS，未 commit 或 push。真实 Main LLM live 仍等待主人另行明确批准。
```

## 2026-07-22 P2.49c Owner Console 后端加载，真实问答未执行

```text
主人明确要求重新启动后端。停止脚本执行时发现 8090 已经没有 Owner Console 进程，因此没有终止任何进程；该实例此前何时、为何消失没有当前日志证据，本轮不推测原因，也不扩展为自动重启或修复任务。随后只启动 Owner Console，没有操作 Bot、Ollama 或 TTS，并显式启用 -EnableProjectDocRagProbe、-EnableMemoryRagConsistencyProbe、-EnableMainLlmContractProbe。

新实例 PID 18900，单一监听 127.0.0.1:8090。healthz 返回 ok=true、manual_diagnostic_actions_enabled=true，enabled_routes 包含三个固定 POST。手动诊断状态显示 project_doc_rag_probe_enabled=true、memory_rag_consistency_enabled=true、main_llm_contract_enabled=true，supported_workflows 为 project_doc_rag_fixed_retrieval、memory_rag_index_consistency、main_llm_fixed_contract；latest_run、project_doc_rag_latest_run、memory_rag_consistency_latest_run、main_llm_contract_latest_run 全为空，证明启动没有自动执行任何动作。

启动后生产数据库仍为 26779648 字节、mtime 2026-07-22T03:54:11.7725970Z，与本轮重启前已观测值一致。owner-console stderr 只有 Started server process、Waiting for application startup、Application startup complete、Uvicorn running 四行 INFO，没有 ERROR、Traceback 或 Exception。真实 Main LLM 尚未调用；下一步仍需主人在页面第一次点击展开确认、第二次确认才会执行唯一固定问答 POST。
```

## 2026-07-22 P2.49c Main LLM 固定问答主人 live

```text
主人在真实诊断页面第一次点击展开确认、第二次确认后执行唯一固定问答。页面结果为 run_id=1、attempt_count=1、status=completed、outcome=attention、stage=result_validation、code=main_llm_contract_mismatch；配置模型 gpt-5.5，elapsed_ms=8146，input/output/total tokens 为 74/126/200，usage_metadata_available=true、llm_called=true、contract_valid=false、tool_calls_present=false。

主人明确反馈“成功了”。按已确认的第一阶段目标，这次已经证明 Main LLM 能正常运行并回答固定问题：8.146 秒低于 15 秒关注阈值，客户端自动重试关闭，模型调用一次完成且 token usage 完整。严格五字段 JSON 没有精确通过，因此页面保留 attention/main_llm_contract_mismatch；这是一条结构兼容性证据，不否定基础可用性，也不扩展为任意问题应选择何种工具的诊断。原始回答正文按设计未展示、未持久化，后端也已丢弃，因此没有证据进一步归因具体偏离字段，不作猜测。

只读复核确认 Owner Console access log 中 Main LLM 固定 POST 恰好 1 次，后端 latest 与 main_llm_contract_latest_run 均指向同一 run_id=1。tool_definitions_sent、tool_execution_allowed、client_automatic_retry、chat_history_read/write、agent_task_written、approval_written、reliability_event_written、database_write_allowed、MemoryRAG、ProjectDocRAG、DevContext、CombinedRAG、Tavily、TTS、vision、QQ write、prompt_exposed、response_content_exposed 全为 false。生产数据库仍为 26779648 字节、mtime 2026-07-22T03:54:11.7725970Z，与动作前观测一致；8090 PID 18900 保持监听，stderr 4 行启动 INFO、0 个 ERROR/Traceback/Exception。

P2.49c 因此以“Main LLM 基础运行主人 live 通过，严格 JSON 子合同 attention”收口。没有自动重试、修改结果、伪造 contract_valid、补跑第二次模型请求、执行工具或启动后续工作流；未查询私人记忆或 RAG，未修复 2 条缺失向量，未 commit 或 push。
```

## 2026-07-22 未获方向批准的 P2.50a 核心运行区本地实验（待处置）

```text
主人当时只表达“进入下一阶段”，没有批准选择 core 方向。开发代理错误地把旧状态文档中“核心、聊天和 MainAgent 系统诊断区域详情尚未注册”当成路线图，并自行选择 core；该方向后来被主人明确纠正。以下只记录已经发生的本地实验事实，不表示主人批准，不得进入加载、QQ live、提交或后续 scope。

新增 system_diagnostics_report/core 固定详情与 `/agent 执行系统诊断任务：核心`。状态链严格为主人私聊 /agent 入口、正式 system_diagnostics_report work runtime、SQLite mode=ro + SELECT 1；定位层级固定为 entry、runtime、database、none。概览与详情共享 evaluate_core_zone，因此同一 evidence 的区域状态不会漂移。详细回复保留状态链、初步判断、建议范围和未执行事项；Agent task 只持久化区域状态、定位层级和 local/external/deep/repair 安全计数，不保存数据库路径、配置、异常、runtime id 或详细报告。核心探针本身零 schema/业务数据写入；正式任务仍保留既有 agent_tasks/events 审计生命周期，页面不会把两者混写为“整个动作数据库零写入”。

原 _system_database_read_probe 使用普通 connect()，即使只执行 SELECT 1，连接退出仍会 commit，也可能创建数据库目录，不能提供足够强的只读证据。P2.50a 改为 connect_read_only()，SQLite URI 使用 mode=ro，不调用 ensure_database、不初始化 schema、不提交事务。core 分支在 MemoryRAG、语音和视觉 collector 之前返回；源码边界测试确认不调用 _collect_system_memory_rag_evidence、_collect_system_vision_evidence、_collect_system_voice_evidence，不进入 DiagnosticsGraph 全量采集，也不调用聊天、MainAgent、LLM、RAG 或外部服务。

新增 core 入口/运行时/数据库/正常首故障短路、负计数、概览一致性、正式任务脱敏持久化、非零 external/deep/repair 拒绝、严格命令、mode=ro 和 collector 隔离测试。聚焦回归 112 tests OK；相邻诊断/MainAgent/Graph 243 tests OK；完整 Python 682 tests OK（skipped=3）；Python AST 148 files、pip check 和 git diff --check 通过。全部测试使用纯 evidence、源码合同和临时 SQLite，没有访问生产数据库、调用真实模型/RAG/QQ/Ollama/TTS 或重启服务。

本地实验完成过代码、自动化和文档修改；Bot 没有重启，新 core 命令未加载，也没有创建真实 Agent task 或执行主人 QQ live。主人尚未决定完全撤销、只保留 `connect_read_only()` 修正，还是作为低优先级实验保留；在该决定前不得运行、提交或由本文自动恢复。chat 和 main_agent 区域详情继续未注册。
```

## 2026-07-24 文档治理第二轮与 P2.49d TTS 固定合成设计

```text
主人确认应先落实文档规范，再进入原定的 Owner Console TTS 手动诊断方向。本轮只修改文档和审计设计；未执行 DevContext、CombinedRAG、QueryDevContext、私人记忆查询、ProjectDocRAG 重建或检索，也未调用 Main LLM、TTS、视觉、QQ，未启动或重启服务。

current-development-status.md 从约 50 KB 的历史堆叠重写为九段权威快照，固定包含元数据、主人批准方向、近期完成、待完成、优先级、授权/禁止、真实风险、唯一下一步和证据入口。快照明确区分 implemented、regression_passed、loaded、live_passed、owner_accepted，并要求每个待办记录批准状态和能否自动开始。

docs/README.md 增加权威快照内容合同，补齐六份此前缺失的根文档导航，修正掘金文章跟踪状态，并登记 reliability-failure-taxonomy-and-inspection.md 为路径兼容例外。version-runlog.md 顶部增加历史阅读规则；main-agent-external-read-security-design.md 修正开头仍称未开放联网的陈旧事实；main-agent-command-capability-audit.md 更新到 0055dcc 基线和 Tavily live 结论。

web-owner-console-v0-runbook.md 不再笼统宣称全站只能 GET，而是明确区分业务 read model GET-only 与 P2.49 三条逐项启用、固定输入、二次确认的 POST 例外，补全启动参数、共享全局锁、结果证据和禁止自由参数。project-rag-document-state-consistency-audit.md 增加第二轮范围、问题、处理和命名合规结果。

未获方向批准的 system_diagnostics_report/core 保持为未提交本地实验：运行时代码未处置、未运行、未加载、未 live、未提交。相关设计和 runlog 已改为明确的未批准实验，从当前 runbook 命令清单移除；主人仍需另行决定完全撤销、只保留 connect_read_only() 修正，还是低优先级保留。

P2.49d 现状审计确认：现有 health/配置入口不能证明真实合成；生产 request_tts() 可能自动启动服务并写可靠性事件，不适合作为固定 executor；tts_service /tts 会写 temp_audio 最终 WAV 和分段目录且没有自动清理合同。设计因此采用独立开关、共享全局锁、服务必须预先在线、一次固定 health + 一次固定 synthesis、零重试、零 QQ、零可靠性事件和零业务数据库写入。成功产物保留；POST 后失败也可能留下无法由 ok=false 响应精确归属的部分文件，不能伪称零文件写入。

P2.49d 当前只完成审计与合同设计。下一步是主人审阅“可能加载 GPU 模型、写入并保留 temp_audio 产物、服务离线不自动启动”的边界；未经明确批准不进入实现、Owner Console 加载或真实 TTS live。
```

## 2026-07-24 P2.49d fake-only 实现与 core 实验撤销

```text
主人随后批准按固定合同实现 P2.49d，并明确要求 core 按已说明方案处置。本轮完成代码、页面、fake HTTP、临时 WAV 和回归；没有启动 TTS、Owner Console 或 Bot，没有访问真实 127.0.0.1:7861、加载 IndexTTS2、写生产 temp_audio、发送 QQ、执行 LLM/RAG 或私人记忆查询，也没有 commit/push。

未获方向批准的 system_diagnostics_report/core 命令、scope、payload、report builder、正式 work runtime、sanitizer 支持和专项测试已全部撤销。唯一保留的安全修正是既有 _system_database_read_probe() 从普通 connect() 改用 connect_read_only()；对应源码边界测试确认 SQLite mode=ro，且源码/测试搜索已无 SYSTEM_DIAGNOSTICS_CORE_SCOPE、build_core_diagnostics_report、CoreDiagnosticsReportPayload 或 `/agent 执行系统诊断任务：核心`。这不新增命令，也不证明 Main LLM 工具选择、RAG 索引或 TTS。

P2.49d 新增专属 owner_console_tts_synthesis executor、独立 -EnableTtsSynthesisProbe / OWNER_CONSOLE_TTS_SYNTHESIS_ENABLED、固定 POST /api/v1/owner-console/manual-diagnostics/tts-synthesis、精确 Header/confirmation、HTTP route contract、前端第四个紧凑二次确认面板和四 POST allowlist。普通启动保持默认关闭；构造运行时不创建 httpx.Client 或访问 health。

executor 只允许无凭据、无 query/fragment/自定义 path 的 loopback HTTP URL；使用 trust_env=false、follow_redirects=false、2 秒 health 和 180 秒 synthesis 固定超时。请求文本、language、voice/emotion 来源、20 秒上限和 bypass_cache 均由后端固定，页面/HTTP 不能覆盖。它不调用 request_tts、ensure_tts_service、send_tts_record、reliability observer、QQ、数据库、MainAgent、LLM/RAG 或视觉；服务离线直接失败，不自动启动，不自动重试。

成功响应只接受 temp_audio 边界内 tts_<32 hex>.wav 形式的绝对路径，并校验 resolve 后目录、非 symlink 普通文件、44 字节至 50 MiB、WAV 声道/样本宽度/采样率/帧数、计算时长与服务声明 250 ms 容差及 20 秒上限。DTO 不包含固定文本、service URL、路径、音频、原始响应、内部 error、异常或 server run_id。页面明确显示 database_write_allowed=false 与 local_file_write_expected=true，并保留 partial_artifact_state；POST 后失败不能被误写为确定零文件写入，成功和可能的部分文件均不自动清理。

四个手动工作流共享同一个进程内锁；关闭返回 403，错误 Origin/Cookie/Header/content-type/body fail closed，并发返回 409。页面第一次点击零 POST，第二次确认才发送一个固定 POST；确认文案明确服务离线、可能冷加载 GPU、成功/失败文件残留、无清理、无 QQ、无可靠性/业务数据库写入、无 LLM/RAG 和无重试。

所有 TTS 自动化只使用 fake request 与测试临时目录 WAV。Owner Console 邻域 77 tests OK（其中 Windows 符号链接权限相关单项按平台跳过）；语音 31 tests、可靠性 28 tests、RAG/QQ 边界 13 tests、完整 Python 689 tests OK（skipped=4）。前端 4 files / 24 tests、TypeScript、Vite production build、四固定 POST guard、Python AST 150 files和 pip check 通过。文档最终同步后另行复核链接、围栏和 git diff --check。

当前完成度为 audited/designed/implemented/regression_passed；loaded=false、live_passed=false。真实 TTS 从未调用，Owner Console 未重启，生产 temp_audio 未写入。下一步只等待主人另行批准真实 live；在批准前不启动服务、不加载模型、不启用开关、不访问 7861。
```

## 2026-07-24 P2.49d 修订为一键受控 TTS 生命周期

```text
主人指出旧版要求每次先手动启动 TTS、合成后保留文件，实际诊断价值不足且操作繁琐；随后批准改为按钮一次完成“检查、必要时启动、固定合成、验证、精确清理、所有权收尾”。本条修订取代同日旧设计中“服务必须预先在线、产物保留、不自动清理”的当前操作指令；旧条目只保留当时实现历史，不再作为 live 手册。

稳定 workflow 改为 tts_managed_lifecycle，HTTP 路径、action header、confirmation 和独立 -EnableTtsSynthesisProbe 开关保持不变。页面第一次点击仍为零动作，只展开说明；第二次确认才发送一个固定 Owner Console POST。页面现在显示启动/健康/合成/清理耗时、服务原本是否在线、是否尝试/完成启动、是否由诊断持有、是否尝试/完成停止、最终 WAV/分段目录是否仍保留、清理是否成功，并保留英文 workflow/stage/code 和布尔证据。

专属 executor 先对固定 loopback 127.0.0.1/localhost/::1:7861 执行 2 秒 health。有效在线服务标记 service_preexisting=true，只复用、不停止；只有明确 ConnectError/connection refused 才启动一个受管理子进程。启动器保留 Popen 句柄，通过环境变量注入 64 位一次性 owner token；TTS /health 只返回 token 的 SHA-256 fingerprint。诊断最多等待 45 秒并要求 fingerprint 精确匹配，避免把端口上未知服务误认成本次进程。health 超时、畸形响应、进程提前退出、启动超时或 ownership mismatch 均不盲目继续合成。

TTS /tts 新增向后兼容的可选 artifact_id；普通生产请求未传时仍使用随机 UUID，诊断固定传后端生成的 32 位小写十六进制 ID。固定合成仍使用一个后端中文短句、当前配置 voice/emotion、language=zh、20 秒上限、bypass_cache=true 和一次 180 秒 POST，零合成重试。验证器要求最终 tts_<artifact>.wav 与唯一 tts_<artifact>_segments/segment_01.wav 均在固定 temp_audio 边界内，并校验普通文件、symlink、大小、WAV 头、帧数、声明/计算时长和分段字节合同。

收尾只处理本次 artifact ID：删除最终 WAV，删除分段目录中匹配 segment_XX.wav 的文件，目录为空后才移除。遇到未知文件不递归删除并报告 cleanup attention；本次精确 symlink 只解除链接，不跟随目标。不得清空 temp_audio、删除其他 run/QQ 文件、按端口或进程名扫描，也不得结束其他 Python/TTS 进程。若服务由诊断启动，只对本次 Popen 句柄 terminate，固定等待后才可对同一句柄 kill；已有服务绝不停止。清理器自身异常不会跳过句柄收尾。

结果优先级为 artifact cleanup incomplete、owned service stop incomplete、startup latency >30000 ms、synthesis latency >120000 ms、完全通过；成功 code 为 tts_managed_lifecycle_succeeded。启动、所有权、请求、产物和意外失败均有固定 stage/code；DTO 不返回 owner token、fingerprint 原值、artifact ID、路径、固定文本、分段文本、音频、原始响应、内部 error 或异常。仍不调用 request_tts、ensure_tts_service、send_tts_record、QQ、reliability observer、数据库、MainAgent、LLM/RAG、视觉或其他手动工作流。

自动化全部使用 fake HTTP、fake process 和测试临时目录 WAV，未访问真实 7861 或生产 temp_audio。生命周期模块 15 tests（Windows symlink 权限项 skipped=1）、Owner Console 相关 57 tests、RAG/QQ 边界 13 tests通过；完整 Python 693 tests OK（skipped=4）。完整前端 4 files/24 tests、TypeScript、Vite production build、四固定 POST guard通过；Python AST src/tests/scripts 154 files、pip check、四份权威文档链接/围栏和 git diff --check通过。测试收集期间曾误用模块路径导致 5 个 Owner Console 文件找不到 pure_ai_chat_loader，改回仓库既有 unittest discover 方式后全部通过；这是命令用法问题，不是产品失败。

当前严格状态仍为 implemented=true、regression_passed=true、loaded=false、live_passed=false、real_tts_called=false、tts_service_started=false、index_tts_loaded=false、production_temp_audio_written=false。没有启动或重启 Owner Console/Bot/TTS，没有真实 Main LLM/RAG/私人记忆/视觉/QQ 动作，没有修复 2 条 MemoryRAG 缺失向量，也没有 commit/push。下一步只等待主人另行批准真实页面 live；届时无需预先手动启动 TTS。
```

## 2026-07-24 P2.49e 视觉固定推理与资源收口规划

```text
主人认可 P2.49d 一键受控 TTS 行为，但明确暂不做 live；主人要求开始视觉模型诊断规划，并说明等 TTS 与视觉都完成后再统一给予足够运行空间进行 live。本轮因此只做 P2.49e 只读代码审计和设计文档，没有实现新路由、按钮、启动器或 executor，也没有访问 11434、启动/停止 Ollama、加载/卸载视觉模型、读取图片或执行真实推理。

审计确认项目历史 `/视觉状态` 并非纯配置状态：它会先 GET Ollama /api/tags，再由 diagnostic_vision_image_base64() 用标准库生成一张 32x32 四色 PNG，并通过 check_vision_inference() 执行一次真实 /api/chat。该诊断不写视觉 reliability event，也不会自动重试，但它属于 QQ/NoneBot DiagnosticsGraph，缺少 Owner Console 独立开关、二次确认、全局锁、结构化脱敏 DTO、服务启动所有权、/api/ps 模型驻留证据和推理后资源收口；当前只验证非空/非重复回答，没有精确颜色位置合同。

生产 describe_images() 会读取用户 URL/本地图片、进入 Ollama 视觉请求并记录结构化可靠性结果，不能作为不读取私人图片、零业务写入的 Owner Console executor。diagnostics.py 还与数据库、错误日志、角色卡和图片缓存等生产诊断依赖耦合，P2.49e 第一版应新建独立模块，不复用整个 DiagnosticsGraph 或生产 vision chain。

现有 scripts/start-ollama-vision.ps1 默认会按进程名结束所有 ollama/ollama app 后再启动；scripts/ensure-ollama.ps1 在服务不可达或模型缺失时会进入该脚本。Ollama 还可能承载 RAG embedding，因此这两个入口均不满足固定诊断所有权边界。规划要求已有服务绝不停止、模型缺失只报告不 pull/不重启；明确离线时才直接 Popen([ollama, serve]) 并持有本次句柄，不经过 PowerShell、不扫描或结束其他进程。由于 Ollama 无法加入 TTS 式 owner fingerprint，所有权只能如实记录为 initial offline + Popen alive + subsequently ready，不得宣称密码学验证。

建议 workflow=vision_managed_lifecycle。固定输入是在内存中生成的 128x128 PNG：红/蓝/绿/白四象限、黑色分隔线、无文字和隐私；实现时固定字节长度和 SHA-256。后端 prompt 要求唯一 JSON：contract_version=vision.fixed.v1、grid=[red,blue,green,white]、status=ok。主人随后明确收紧通过标准：只有精确满足固定 JSON/颜色语义合同、能够清晰证明模型识别了图片内容时才进入 succeeded。非空但合同不匹配、空回答、重复无效符号、超长回答或 Ollama envelope 不合格均进入 failed；任何服务无法启动、模型无法加载或推理未完成也不得识别为通过。页面、HTTP、URL/Header/body 不允许覆盖图片、prompt、model、service URL、num_ctx、keep_alive 或 timeout。

服务生命周期规划为固定 loopback 11434、3 秒 tags、3 秒 ps、30 秒受管理启动、180 秒单次 chat 硬超时，响应有界、trust_env=false、redirect=false、零 retry。模型必须已在 tags 中存在，不执行 pull。推理前后使用 /api/ps：原本已驻留的视觉模型不卸载；原本未驻留时，固定 /api/chat 使用 keep_alive=0，并要求推理后 /api/ps 已无该模型。服务由本次启动时，再只停止本次 Popen 句柄；已有服务和其他模型不停止。固定 num_ctx=4096 用于基础运行和显存控制，明确不代表生产 VISION_NUM_CTX=16384 已被完整验证。

规划的结果区分 succeeded、attention 和 failed。`succeeded` 只用于服务可用、推理完成且固定颜色语义合同精确通过；合同不匹配属于 failed。模型未释放、持有服务未完全停止、usage 缺失或延迟超过关注阈值可进入 attention，但页面不得把 attention 显示为“诊断正常”。DTO 只保留有限计数、耗时和布尔证据，不返回 prompt、PNG/base64、模型回答、URL、模型路径/digest、原始 tags/ps/chat、异常或其他模型名称。动作不是严格 read-only：可能启动 Ollama 和加载 GPU 模型；但配置/业务数据库/项目文件写入关闭，不创建聊天、缓存、Agent task、approval 或 reliability event，不调用 Main LLM/RAG/TTS/QQ。

若后续获准实现，建议独立 -EnableVisionInferenceProbe、固定 POST /api/v1/owner-console/manual-diagnostics/vision-inference、固定 Header manual-vision-inference-v1 和 confirmation=run_registered_vision_inference，并与现有四个工作流共享全局锁。第一阶段只允许 fake HTTP、fake process、内存 PNG、页面与完整回归；不得访问真实 11434 或真实 D:\OllamaModels。P2.49d/e live 当前均由主人明确延后，只有两个实现都完成并再次汇报后，才由主人安排资源并分别批准串行 live。
```

## 2026-07-24 P2.49e 视觉固定生命周期 fake-only 实现

```text
主人审阅规划后进一步明确：诊断必须真实证明模型清晰识别图片内容，空回答、重复无效符号、服务无法启动、模型无法加载或其他未完成推理的情况均不得通过；随后批准进入实现，但继续禁止真实 live。本轮据此完成 P2.49e fake-only 代码、页面、固定 HTTP 合同和回归，没有访问 11434、运行 ollama、读取真实图片或加载 GPU 模型。

新增 src/plugins/ai_chat/owner_console_vision_inference.py 和 tests/test_owner_console_vision_inference.py。executor 用 Python 标准库在内存生成 128x128 RGB PNG，红/蓝/绿/白四象限与黑色分隔线固定；自动化锁定 png_bytes=311、SHA-256=3d1f6c2a1b1b220a474cb49dcec96841decedf4c0892bfbd66f082bbd098ffcd、尺寸和五处象限/分隔像素。图片不落盘、不读取主人、QQ、缓存、项目或网络图片，DTO/页面不返回 PNG/base64。

稳定 workflow=vision_managed_lifecycle，固定 num_ctx=4096、temperature=0、stream=false、一次 /api/chat、零 tools、零 retry、180 秒硬超时和 64 KiB envelope 上限。固定 prompt 要求唯一 JSON：contract_version=vision.fixed.v1、grid=[red,blue,green,white]、status=ok。只有解析后的对象字段和值精确匹配才进入 succeeded；自由文本、颜色/位置错误、重复 key、额外字段、空白、重复无效符号、超长、HTTP 非 200、done=false 或畸形 envelope 全部 failed/固定 code，不再把非空合同不匹配降为 attention。

服务仅允许固定 loopback HTTP 11434。初始 /api/tags 有效时标记 service_preexisting=true，绝不停止；只有明确 ConnectError/connection refused 才通过 shutil.which(ollama) 直接 Popen([ollama, serve])，固定 OLLAMA_HOST 和 OLLAMA_MODELS，不经过 PowerShell，不调用 start-ollama-vision.ps1/ensure-ollama.ps1，不扫描或结束其他进程。超时、HTTP 或畸形 JSON 不盲目启动；模型缺失只失败，不 pull、不重启。初始明确离线 + 本次 Popen 存活 + 随后服务就绪是唯一 ownership basis；子进程退出但端口出现服务时返回 vision_service_ownership_ambiguous，且不停止端口服务。

/api/ps 在推理前验证当前视觉模型驻留。原本已驻留时不发送 keep_alive=0、不卸载；原本未驻留时发送 keep_alive=0，并在推理后只读取一次 /api/ps 验证该模型已释放。不执行 ollama stop。服务由本次启动时，在模型收口后只 terminate/必要时 kill 本次 Popen 句柄；已有服务和其他模型绝不停止。识图已严格通过但模型未释放、持有服务未停止、usage 缺失或延迟超阈值可进入 attention，页面显示“需要关注”而非“通过”。

OwnerConsoleManualDiagnosticsRuntime 已加入第五个独立开关、latest_run DTO、run_vision_inference() 和五工作流共享全局锁。FastAPI 增加 OWNER_CONSOLE_VISION_INFERENCE_ENABLED、-EnableVisionInferenceProbe、固定 POST /api/v1/owner-console/manual-diagnostics/vision-inference、Header manual-vision-inference-v1 和 confirmation=run_registered_vision_inference；同源 Origin、动作 Cookie、application/json、精确 body 和并发 409 边界保持不变。前端只在显式启用时显示“视觉固定图片识别”，第一次点击零 POST，第二次确认恰好一个 POST；不提供上传、URL、prompt、模型、工具或参数控件，保留 workflow/stage/code 和服务/模型收口布尔证据。

executor 不导入生产 vision.py、DiagnosticsGraph、QQ、RAG、数据库、reliability、MainAgent 或 TTS。它不创建项目图片/业务 artifact，因此 project_artifact_write_expected=false；同时明确 external_runtime_local_write_possible=true，因为真实 Ollama 外部进程仍可能写自己的日志或缓存，不能把业务零写入夸大成整个外部运行时零本地写入。

fake 自动化覆盖固定图片快照、预驻留/未驻留模型、keep_alive 分支、已有服务不停止、离线启动与句柄收尾、启动超时、进程提前退出、ownership ambiguous、畸形/超时服务不盲目启动、模型缺失、ps 不可用、严格回答成功、空/重复/错色/自由文本/超长/done=false/HTTP 错误失败、cleanup/stop evidence、固定 POST 安全合同、页面二次确认和全局锁。所有 HTTP/process 都是 fake。

回归结果：Python 711 tests OK（skipped=4）；Owner Console 相关 99 tests OK（skipped=1）；RAG/QQ 边界 13 tests OK；前端 4 files/26 tests OK；TypeScript、Vite production build、五固定 POST guard、Python AST src/tests/scripts 156 files、PowerShell parse、pip check 和 git diff --check 通过。

当前严格状态：audited=true、designed=true、implemented=true、regression_passed=true、loaded=false、live=false、real_vision_called=false、ollama_service_started=false、vision_model_loaded=false、real_image_read=false、tts_live_executed=false。P2.49d/e 两个实现均已完成，真实 live 继续由主人延后；下一步只等待主人安排足够 GPU/运行空间并分别批准串行 live，不自动启动、加载或连续执行。
```

## 2026-07-25 P2.49d 首次主人动作与 ConnectTimeout 最小修复

```text
主人要求启动 Owner Console 后端并自行做前端测试。启动前只读确认 8090/7861 未监听、11434 已有 Ollama 服务；随后用 -EnableProjectDocRagProbe、-EnableMemoryRagConsistencyProbe、-EnableMainLlmContractProbe、-EnableTtsSynthesisProbe、-EnableVisionInferenceProbe 启动 127.0.0.1:8090。healthz 和 manual-diagnostics GET 确认五个 workflow 全部启用、latest_run=null，启动本身没有自动执行任何动作，也没有触碰已有 Ollama。

主人第一次执行 TTS 后页面返回 outcome=failed、stage=health_check、code=tts_health_contract_invalid、health_elapsed_ms=2014、service_start_attempted=false、service_started=false、tts_called=false、output_file_created=false、partial_artifact_state=none_before_post。netstat 同时确认 7861 无 listener；使用相同 httpx 2 秒、trust_env=false、follow_redirects=false 的 GET /health 只读复现得到 httpx.ConnectTimeout，elapsed≈2110 ms。无法从现有证据归因 Windows 网络层为何没有返回 connection refused，不臆测根因。

因此本次不是“TTS 子进程启动后失败”，而是旧离线分类只接受 ConnectError/ConnectionRefusedError，把连接建立阶段的 ConnectTimeout 保守映射成 health contract invalid，导致 process starter 零调用。没有启动 TTS、加载 IndexTTS2、调用 /tts、生成 WAV/分段目录、清理文件或停止进程；QQ、数据库、reliability、LLM/RAG/视觉副作用均未发生。

主人批准最小修复。owner_console_tts_synthesis._offline() 仅新增 httpx.ConnectTimeout；httpx.ReadTimeout、HTTP/JSON/health contract 异常仍不属于离线，继续 fail closed。即使 ConnectTimeout 进入启动路径，新服务仍必须返回本次 64 位 owner token 的 SHA-256 fingerprint，才能执行一次固定合成；ownership mismatch、进程提前退出或启动超时仍失败，且只收尾本次 Popen。没有加入端口/进程扫描、未知服务停止、自动重试或自动重跑。

新增 fake 端到端测试覆盖 ConnectTimeout -> start once -> fingerprint match -> synthesize once -> exact cleanup -> stop held process；既有 ReadTimeout -> starter zero calls 测试继续通过。回归结果：TTS executor 16 tests OK（skipped=1），Owner Console 手动诊断 17 tests OK，Python 全量 712 tests OK（skipped=4）。随后只重启 Owner Console，新的 server PID=19068；只读确认 8090 正常、五 workflow 启用、latest_run=null、7861 仍未监听、既有 Ollama PID=13412 仍监听 11434。重启本身没有自动执行 TTS 或视觉；仍由主人页面二次确认重试。
```

## 2026-07-25 P2.49d 第二次主人 live：受管理服务启动超时

```text
主人在重启后的 Owner Console 再次二次确认执行 TTS。权威页面结果：workflow=tts_managed_lifecycle、run_id=1、attempt_count=1、outcome=failed、stage=service_start、code=tts_service_start_timeout、elapsed_ms=49634、startup_elapsed_ms=47304、health_elapsed_ms=40542、synthesis_elapsed_ms=0、cleanup_elapsed_ms=0。service_start_attempted=true 证明上一轮 ConnectTimeout 离线分类修复已实际生效。

本次 service_started=false、service_owned_by_diagnostic=false、tts_called=false、output_file_created=false、artifact_cleanup_attempted=false、partial_artifact_state=none_before_post；没有进入 /tts、加载合成模型或创建 WAV。超时后 service_stop_attempted=true、service_stopped=true；只读 netstat 确认 7861 无残留 listener，8090 Owner Console 和启动前已存在的 11434 Ollama 均仍在线。没有自动重试、QQ、reliability、数据库、LLM/RAG 或视觉副作用。

该结果不是 connection 分类失败，也不是已确认的 IndexTTS2 模型加载超时。受管理进程在整个 45 秒窗口内没有提前退出，否则 executor 会返回 tts_managed_process_exited_early；但始终没有得到带 owner fingerprint 的有效 /health。源码显示 tts_service.py 在 uvicorn.run() 之前顶层 import torch 和 indextts.infer_v2.IndexTTS2，而 IndexTTS2(...) 实例本身直到 /tts 的 ensure_loaded() 才构造，因此阻断范围位于 HTTP 端口就绪前 bootstrap/import 阶段。

现有 Popen 把 stdout/stderr 定向到 DEVNULL，Owner Console 日志只有 uvicorn 自身正常启动，无法确定具体是 torch/import 初始化过慢还是其他保持进程存活的 bootstrap 异常。没有证据支持臆测根因，也不能只凭本次失败盲目延长 45 秒。

候选最小后续方向是让 /health 不依赖 torch/indextts 顶层导入而先就绪，把重依赖 import 与 IndexTTS2 构造推迟到 /tts 的 180 秒模型加载/合成阶段，并增加有界脱敏 bootstrap stage/code；owner fingerprint、一次执行、精确 artifact 清理、只停止本次句柄和零自动重试保持不变。该候选尚未获主人实现批准，不自动修改或重跑。当前严格状态仍为 live_failed/tts_service_start_timeout，不是 TTS 可用。
```

## 2026-07-25 P2.49d lazy bootstrap 获批、实现与重载

```text
主人批准按“轻量 health 先启动，torch/IndexTTS 延迟到 /tts”的最小范围继续，并要求不自动进行 live。tts_service.py 删除顶层 torch 与 indextts.infer_v2.IndexTTS2 导入，增加惰性 load_tts_runtime()；GET /health 在重依赖未导入时即可返回 ok=true、loaded=false、runtime_imported=false、language=zh 和既有 owner fingerprint。首次 /tts 才导入 runtime 并构造 IndexTTS2；runtime 成功后在进程内复用，idle unload 只释放模型，不重复 import。

Owner Console TTS executor 将 health 的 loaded/runtime_imported 解析为有限 TtsHealthEvidence。loaded=true/runtime_imported=false 作为不可能合同 fail closed；旧 health 未提供 runtime_imported 时按 loaded 兼容。运行结果、TypeScript DTO 和诊断页新增 runtime_imported_before 及“调用前 runtime 已导入/未导入”，不暴露路径、命令、token、traceback、stderr 或原始异常。45 秒 service bootstrap timeout、180 秒 /tts timeout、owner fingerprint、一次执行、零重试、精确 artifact 清理和只停止本次 Popen 均未改变。

新增/更新自动化覆盖 health 不触发 runtime import、首次模型请求只导入一次、runtime 复用、idle unload 后不重复 import、runtime import 失败保持 unloaded、旧 health 兼容、不可能 health 状态拒绝，以及 DTO/页面 runtime_imported_before 证据。回归结果：TTS bootstrap 5 tests OK；TTS lifecycle 17 tests OK（skipped=1）；Owner Console manual diagnostics 17 tests OK；Owner Console adjacent 101 tests OK（skipped=1）；Python full 718 tests OK（skipped=4）；frontend 26 tests OK；RAG/QQ boundary 13 tests OK；TypeScript、Vite build、五固定 POST guard、Python AST 153 files、PowerShell parse、pip check、git diff --check 全部通过。

随后仅重启 Owner Console 并显式启用原有五个 workflow。新 8090 PID=19156；只读 manual-diagnostics GET 显示五个 workflow、latest_run=null、tts_synthesis_latest_run=null、vision_inference_latest_run=null；7861 无 listener；既有 11434 仍为 PID=13412。启动本身没有执行 TTS、视觉、Main LLM 或 RAG。严格状态：lazy_bootstrap_implemented=true、regression_passed=true、loaded=true、third_live=false、tts_available_unproven=true。下一步只由主人页面二次确认执行第三次 TTS，不由开发代理自动 POST。
```

## 2026-07-25 P2.49d 第三次技术 live 与主人听检门控

```text
主人在 lazy-bootstrap 版本页面二次确认执行第三次 TTS。权威结果为 workflow=tts_managed_lifecycle、outcome=succeeded、stage=result_validation、code=tts_managed_lifecycle_succeeded；elapsed/startup/health/synthesis/cleanup 分别为 70802/1054/3201/67565/1 ms，WAV 为 132140 bytes、2995 ms。调用前 model/runtime 均未加载；服务原本离线，诊断成功启动、持有并停止本次进程；tts_called=true，最终 WAV/分段目录均精确清理，automatic_retry/QQ/reliability/database write 均为 false。

这证明 lazy bootstrap 的真实效果和一次基础技术合成可用：端口不再被重依赖 import 阻断，首次 /tts 完成 runtime 导入与 IndexTTS2 合成，WAV 技术合同和服务/磁盘收尾成立。主人随后指出旧合同没有提供试听，无法确认固定文本“这是一次固定语音合成检查。”是否读对、是否清晰以及有无截断、重复、卡顿、爆音、杂音或异常静音。因此旧 succeeded 只记为 technical_live_passed；output_retained=false 表明该 WAV 已删除，不能恢复或伪称主人已验收音质。

主人批准最小修订：技术通过后磁盘仍立即精确清理，但先把已验证、最大 50 MiB、RIFF/WAVE 的最终字节复制到单一 Owner Console 进程内存槽并绑定 run_id。初始结果统一为 attention/owner_audio_review/tts_audio_quality_review_required，同时保留 technical_outcome/technical_code。受保护 GET 只允许 loopback Host、动作 Cookie、固定 preview Header 和当前正整数 run_id，返回 no-store audio/wav，不暴露路径或文件名。页面用 Blob URL 临时播放，不提供显式下载控件。

主人接受和拒绝分别使用两个固定 same-origin POST、不同固定 Header/confirmation 和当前 run_id。接受只清除内存并恢复 underlying technical result，不能覆盖原有 latency/cleanup/stop attention；拒绝清除内存并返回 failed/owner_audio_review/tts_audio_quality_rejected。重复审核、错误 run、缺 Cookie/Header、额外 body 字段、预览缺失或与其他诊断并发均 fail closed。审核不调用 TTS、不重试、不写文件/数据库/reliability/QQ。页面播放结束后才解锁“语音合格”，但最终质量证据仍是主人明确动作，不伪装成自动语音质量识别。

回归：TTS lifecycle 18 tests OK（skipped=1）；Owner Console adjacent 102 tests OK（skipped=1）；Python full 719 tests OK（skipped=4）；frontend 29 tests OK；RAG/QQ boundary 13 tests OK；TypeScript、Vite build、一个 protected preview GET、七固定 POST guard、Python AST 153 files、PowerShell parse、pip check、git diff --check 全部通过。自动化仅使用 fake HTTP/process 和测试临时 WAV，没有访问真实 7861 或再次合成。

随后仅重载 Owner Console。新 8090 PID=14892；五个 workflow 及 preview/accept/reject 路由启用，latest_run=null、tts_synthesis_latest_run=null；7861 无 listener；既有 11434 仍为 PID=13412。重载未执行任何诊断。当前严格状态：technical_live_passed=true、audio_quality_gate_implemented=true、regression_passed=true、loaded=true、audio_quality_live=false。唯一下一步是主人重新执行一次固定 TTS、加载并听完临时试听，然后明确接受或拒绝；开发代理不自动 POST或代判音质。
```

## 2026-07-25 P2.49d 主人音质 live 通过

```text
主人在新听检门控页面重新执行固定 TTS、加载临时 WAV、完成试听并明确报告测试通过。只读读取当前 Owner Console 最近结果：run_id=1、workflow=tts_managed_lifecycle、status=completed、outcome=succeeded、stage=result_validation、code=tts_managed_lifecycle_succeeded、attempt_count=1。

本次 elapsed/startup/health/synthesis/cleanup 分别为 59780/1031/3157/56579/1 ms，WAV 为 140844 bytes、3193 ms。调用前 model/runtime 均未加载；服务原本离线，诊断启动、持有并停止本次服务；tts_called/output_contract_valid/artifact_cleanup_succeeded 均 true，output_retained/segment_directory_retained 均 false，partial_artifact_state=artifacts_removed。

底层 technical_outcome=succeeded、technical_code=tts_managed_lifecycle_succeeded。主人审核后 audio_quality_review_required=false、audio_quality_reviewed=true、audio_quality_accepted=true、audio_review_action_executed=true，audio_reviewed_at=2026-07-25T10:08:34+00:00。audio_preview_available=false、audio_preview_persisted=false、audio_preview_path_exposed=false。automatic_retry、QQ write、reliability event 和 database write 均 false。

随后使用当前动作 Cookie 和固定 preview Header 对 run_id=1 做只读复核，GET 返回 409，证明接受动作后内存预览已经清除；netstat 确认 7861 无 listener，8090 仍为 PID=14892，既有 11434 仍为 PID=13412。没有再次合成或触发其他工作流。P2.49d 最终状态：lazy_bootstrap_live_passed=true、technical_synthesis_live_passed=true、audio_quality_live_passed=true、artifact_cleanup_passed=true、managed_service_cleanup_passed=true、owner_accepted=true。
```

## 2026-07-25 P2.49e 首次视觉 live 与收口轮询修订

```text
主人在 Owner Console 页面执行视觉固定图片识别。workflow=vision_managed_lifecycle，模型 qwen2.5vl:3b；总计 34656 ms、服务发现 222 ms、驻留检查 26 ms、图片推理 34392 ms、资源收口 8 ms，输入/输出/总 token 为 1103/32/1135。固定 PNG 311 bytes，fixed_image_contract_valid=true、response_contract_valid=true、vision_called=true，因此红/蓝/绿/白固定图片的基础识别合同已经 live 通过。

调用前模型未驻留，已有 Ollama 服务原本在线；请求使用 keep_alive=0，不停止已有服务。旧实现只在 /api/chat 返回后立即读取一次 /api/ps；该次 8 ms 检查仍见目标模型，故原结果严格保留 outcome=attention、stage=result_validation、code=vision_model_cleanup_incomplete、model_cleanup_verified=false。稍后独立只读 /api/ps 显示 qwen2.5vl:3b 不再驻留，支持异步卸载与即时单次检查之间的短暂竞态，但不能据此倒写原运行当时已验证释放。

主人批准最小验证修订：仅在模型调用前未驻留且本次 keep_alive=0 时，把推理后的单次 /api/ps 改为最多 5 秒、每 250 ms 的有界只读轮询；目标模型消失立即结束，并新增 model_cleanup_poll_count 与覆盖整个窗口的 cleanup_elapsed_ms。超时或持续查询异常仍保持 attention/vision_model_cleanup_incomplete。没有重复 /api/chat、没有 ollama stop、没有停止已有 Ollama、没有卸载其他模型、没有自动串行执行后续工作流。

fake 自动化新增延迟 500 ms 后释放场景，并覆盖立即释放、5 秒仍驻留、调用前已驻留和持有服务句柄收尾；视觉推理调用次数始终为一次。视觉 executor 15 tests、Owner Console 手动诊断 17 tests、Python full 720 tests（skipped=4）、前端 29 tests、TypeScript、Vite build、固定动作 guard 和 git diff --check 通过。本轮修订没有执行真实视觉、没有停止/重启 Ollama、没有重载 Owner Console，也没有 commit/push。当前状态为 vision_live_passed=true、original_cleanup_attention=true、cleanup_revision_implemented=true、regression_passed=true、loaded=false、re_live=false。

主人随后明确批准只重启 Owner Console 以加载收口修订。停止脚本仅匹配 `src.owner_console_fastapi_launcher:app --port 8090`，停止旧 Owner Console 进程后启动五个原有诊断开关；没有停止或重启 Ollama、TTS 或 Bot。新 PID 20276 在 127.0.0.1:8090 监听，既有 Ollama PID 13412 继续监听 11434，7861 未监听；stderr 只有正常的 Uvicorn startup 信息。

只读 manual-diagnostics GET 显示五个 workflow 全部启用，manual actions=true，automatic diagnostics/configuration write/business data write 均 false；latest_run=null、vision_inference_latest_run=null，证明重启没有执行任何诊断。Owner Console 页面返回 HTTP 200、text/html; charset=utf-8。当前状态更新为 cleanup_revision_loaded=true、re_live=false；唯一下一步是主人页面二次确认重新执行一次固定视觉诊断，开发代理不自动 POST。
```

## 2026-07-25 P2.49e v1 收口通过与 v2 固定表情质检实现

```text
主人在 5 秒有界收口版本重新执行固定视觉诊断，页面显示通过。只读结果为 run_id=1、workflow=vision_managed_lifecycle、outcome=succeeded、stage=result_validation、code=vision_managed_lifecycle_succeeded、模型 qwen2.5vl:3b；elapsed/inference/cleanup 为 8821/8373/284 ms，输入/输出 token 为 1103/32。调用前模型未驻留，keep_alive=0，model_cleanup_required=true；推理后第 2 次 /api/ps 检查确认释放，model_cleanup_verified=true、model_cleanup_poll_count=2。已有 Ollama 未停止，视觉推理没有自动重试。v1 的接口、固定结构回答和资源收口 live 由此通过。

主人随后要求查看模型回复文本并指出四色图过于简单，希望从此前正式保存的表情包中选择固定参考样例。只读审计还确认 v1 prompt 直接包含预期 grid=[red,blue,green,white]，所以即使结构合同通过，也不能充分证明颜色来自视觉观察。v1 结果继续作为基础传输/结构/生命周期证据，但内容理解终态由 v2 取代。

正式表情库只读审计为 schema 2、revision 18、启用 14、禁用 2；13 个启用资产为动态 GIF，唯一启用静态 PNG 为 aike_affection_005：500×500、162977 bytes、单帧、owner_private、manifest SHA 与文件一致，标签为 affection/happy、show_heart。主人批准将它作为固定参考。原文件没有修改、复制、移动或覆盖。

现有 workflow 和面板原地升级到 contract_version=vision.sticker.v1。executor 每次只读取 data/stickers/library.json 与 approved/aike_affection_005.png，并精确验证启用状态、owner_private、普通文件/非 reparse、approved 边界、文件名、image/png、尺寸、字节数和固定 SHA-256；任何禁用、替换、hash/manifest/path 漂移都在推理前 failed/vision_reference_asset_unavailable，不随机回退其他表情。

新 prompt 只规定字段、输出格式和“根据实际可见内容选择”，不含正确主体、黑白发色、粉红红眼、爱心或亲昵主题。JSON Schema 提供多种主体、颜色、物体、符号和主题候选。后端严格验证 anime_character、subject_count=1、hair_colors black+white（顺序可变）、eye_color_family=pink_red、held_object=heart、floating_symbols=hearts、visual_theme=affection、status=ok，以及 20–180 字、至少 8 个汉字、非重复无效内容的 description_zh。

模型安全原始 JSON（控制/双向字符清理、最多 2048 字符）和 description_zh 进入当前 Owner Console 进程内结果供主人查看，不写文件、数据库、日志、聊天历史或 reliability。失败回答只要存在也保留有限预览，便于观察乱码/重复/错识别；response_preview_persisted=false、response_preview_path_exposed=false。

技术合同通过后统一进入 attention/owner_visual_review/vision_response_quality_review_required，不预先显示最终成功。页面展示中文描述、可展开原始 JSON，并通过固定受保护 GET 加载唯一参考 PNG；该 GET 不接受路径、ID、URL、query 或 run 参数。主人接受/拒绝使用两个不同 fixed POST 并绑定当前 run_id。接受恢复底层 technical outcome/code，不能覆盖 cleanup/stop/usage/latency attention；拒绝为 failed/vision_response_quality_rejected。审核不再次调用视觉、不启动/停止服务、不卸载模型、不写数据库/文件/reliability、不发 QQ。

后端路由合同新增一个 protected vision preview GET 和两个固定 review POST；前端边界现为 protected TTS/vision previews 与九条固定 manual POST。页面不增加第六面板，不提供上传、自由 prompt、路径、URL、sticker 选择、模型或参数控件。旧笼统 image_content_exposed=false 被细分为固定 reference_image_exposed_to_owner，同时聊天/QQ 临时图/缓存/其他表情读取仍为 false。

回归：视觉 executor 15 tests、手动诊断 17、HTTP contract 3、FastAPI app 22、launcher 4 全部通过；Python full 720 tests OK（skipped=4）。前端 4 files/31 tests、TypeScript、Vite production build、九 fixed POST/双 preview guard 通过。实现阶段没有真实调用视觉、停止/重启 Ollama、读取其他图片、发送 QQ、执行 LLM/RAG/TTS、commit 或 push。

主人随后批准只重启 Owner Console。停止脚本只匹配 8090 Owner Console，旧 PID 20276 及同命令行进程条目被停止；新 PID 12960 正常监听 127.0.0.1:8090，stderr 只有 Uvicorn startup。既有 Ollama PID 13412 继续监听 11434，7861 未监听，没有停止/重启 Ollama、TTS 或 Bot。

只读 manual-diagnostics 与 route contract 确认五个 workflow 启用，route_count=24，vision-reference-preview、vision-response-quality-accept/reject 三个新 route 均存在；automatic diagnostics/configuration write/business data write 均 false，页面 HTTP 200 UTF-8。latest_run=null、vision_inference_latest_run=null，证明重启没有自动执行视觉或其他诊断。当前 v2 状态更新为 implemented=true、regression_passed=true、loaded=true、live=false；唯一下一步是主人页面手动执行并完成描述质检。
```

## 2026-07-25 P2.49e 严格结构化 live 失败与最小自然描述修订

```text
主人在严格结构化固定表情版本执行一次真实视觉。模型 qwen2.5vl:3b 完成推理，资源收口验证通过；但多个 JSON 字段为 unknown，模型中文描述为“一个戴着黑色帽子和白色披风的卡通角色，眼睛被红色心形遮住。”。对照参考图，这把黑白双色头发误认为帽子/披风，也错误描述眼睛被爱心遮挡。后端正确返回 workflow=vision_managed_lifecycle、outcome=failed、stage=result_validation、code=vision_response_contract_mismatch、vision_called=true、response_contract_valid=false，没有进入主人接受门控。该失败不能因服务有响应或模型已释放而倒写成功。

主人提出严格 prompt/JSON Schema 可能让小型视觉模型过于拘谨，批准关闭结构化约束做单变量实验。固定正式资产、模型、stream=false、num_ctx=4096、temperature=0、一次 /api/chat、keep_alive=0 条件、5 秒模型释放轮询、已有服务不停止、无自动重试及全部写入边界保持不变。请求删除 format JSON Schema、十字段清单、枚举和后端私有视觉事实比对，只保留“请用自然中文客观描述这张图片中实际可见的内容。”；没有人物、颜色、眼睛、爱心或主题答案。

自动合同现在只验证 Ollama envelope/done、assistant role、无 tool_calls、非空、最多 2048 字符、控制/双向字符清理、非重复乱码和至少 8 个汉字。它明确不验证视觉语义，新增 response_mode=natural_text、structured_output_requested=false、semantic_contract_automatically_validated=false、owner_visual_judgment_required=true。即使自然中文描述事实错误，也只会进入主人对照参考图质检，不能自动宣称识图准确。

页面同步为“基础回复合同”“模型原始回复”，解释无 JSON Schema、语义由主人判断。视觉 executor 15 tests、手动诊断 17 tests、Python full 720 tests OK（skipped=4）、前端 4 files/31 tests、TypeScript 与 Vite production build 通过。自动化使用 fake HTTP/process，没有执行真实视觉、停止/重启 Ollama 或 Owner Console、修改固定资产、发送 QQ、调用 LLM/RAG/TTS、commit 或 push。

production 前端 build 更新后，主人明确批准只重启 Owner Console。停止脚本只结束旧 8090 Owner Console PID 12960 及其父进程，没有按名称或端口扫描停止其他服务；随后用五个既有显式 workflow 开关启动。新 PID 27072 监听 127.0.0.1:8090，页面 HTTP 200、text/html; charset=utf-8，route_count=24。只读 manual-diagnostics 显示五个 workflow 启用，automatic diagnostics/configuration write/business data write 均 false；latest_run 与五个专属最近结果全部为 null，证明重启没有执行视觉、TTS、Main LLM 或 RAG。既有 Ollama PID 13412 继续监听 11434，7861 未监听。

当前严格状态：natural_prompt_revision_implemented=true、regression_passed=true、loaded=true、live=false。唯一下一步是主人页面二次确认执行一次自然描述版，对照固定参考图接受或拒绝回复；开发代理不自动 POST、不代判语义质量。
```

## 2026-07-26 P2.49e 本地自然描述拒绝与百炼线上视觉诊断设计

```text
主人执行已经加载的最小自然描述版固定表情诊断。workflow=vision_managed_lifecycle、run_id=1；底层 technical_outcome/technical_code 为 succeeded/vision_managed_lifecycle_succeeded，elapsed/inference/cleanup 为 11035/10474/296 ms，input/output/total token 为 1058/66/1124。response_contract_valid=true、response_mode=natural_text、structured_output_requested=false、semantic_contract_automatically_validated=false；调用前模型未驻留，keep_alive=0，收口轮询 2 次确认释放。一次请求、usage、服务和模型生命周期均正常。

自然回复仍把主要黑白双色长发误认为黑帽子与披风，把清晰可见的粉红红色眼睛说成被红色心形遮住，对被大爱心遮挡的嘴部作了无依据描述，并把 RGBA 透明背景说成实体纯黑背景。主人完成对照审核并拒绝，最终严格保留 outcome=failed、stage=owner_visual_review、code=vision_response_quality_rejected、visual_quality_reviewed=true、visual_quality_accepted=false。该结果证明关闭严格 JSON Schema 没有使当前 qwen2.5vl:3b 达到固定复杂表情的描述质量要求；不能把技术响应或模型释放倒写为语义成功，也不能把单一图片外推为所有本地视觉任务不可用。

主人随后要求比较低费用线上视觉方案，并批准先写阿里云百炼固定线上视觉诊断设计与配置说明。本轮新增 docs/owner-console-cloud-vision-diagnostic-design.md，规划独立 workflow=cloud_vision_fixed_description；第一候选固定为 provider=aliyun_bailian、region=cn-beijing、model=qwen3.7-flash、enable_thinking=false。继续使用同一登记的 owner_private PNG 和一句不含答案的自然中文问题，固定一次请求、temperature=0、max_tokens=256、60 秒超时、零 retry、无 tools，基础合同通过后仍进入主人语义质检。

设计只暴露独立 ALIYUN_BAILIAN_WORKSPACE_ID 与 ALIYUN_BAILIAN_API_KEY；模型、地域、endpoint 合同和请求参数固定在代码设计中，不复用 Main LLM 密钥，不提供任意 URL/model/prompt/参数。图片外发确认必须明确说明会把固定 owner_private PNG 发送到阿里云百炼北京地域，且应用无法控制供应商侧数据处理与留存。云端工作流与本地 vision_managed_lifecycle 并列，共享全局运行锁；本地失败不自动触发云端，Flash 失败也不自动改用 qwen3.7-plus。

按 2026-07-25 核对的阿里云官方价格，qwen3.7-flash 低输入档非思考约为输入 0.20 CNY/1M token、输出 0.80 CNY/1M token；以 1270 输入、100 输出粗估约 0.000334 CNY/次。该数字只是设计时估算，实际实现或 live 前必须重新核对官方价格和模型能力。

当前严格状态为 owner_approved_design/designed/not_implemented/not_configured/not_loaded/not_live。当前批准不包含运行代码、读取或配置 API Key、发送图片、调用阿里云模型、重启服务或修改 QQ 生产视觉链。本轮没有执行 DevContext、CombinedRAG、QueryDevContext、私人记忆查询、ProjectDocRAG、Main LLM、RAG、TTS、视觉 live、QQ 写入、commit 或 push。唯一下一步是主人审阅设计并决定是否批准 fake-only 实现。
```

## 2026-07-26 百炼隔离 live 通过、生产云视觉与 Owner Console 实现

```text
主人随后提供百炼北京地域 OpenAI-compatible Workspace URL，并在私密 `.env` 中自行填写 URL/Key。配置字段最终固定为 ALIYUN_BAILIAN_BASE_URL 与 ALIYUN_BAILIAN_API_KEY；Key 原值未进入文档、页面、测试输出或 Git 跟踪文件。模型固定为 qwen3.7-flash，不使用 Anthropic URL，也不把模型名交给环境变量或页面覆盖。

在主人逐次明确批准下，隔离脚本对同一固定 owner_private 资产 aike_affection_005 执行三次单请求实验。资产合同保持 500×500 PNG、162977 bytes、SHA-256=1b0db22d21fc7ed998cec9da0568c0987ccf9738eea69bf5c8c436609bfed249；每次均为一次请求、零 tools、零客户端 retry、enable_thinking=false。前两次用于收紧/放宽自然描述长度和观察内容质量；第三次经主人批准允许概括基于可见表情、动作和画面元素的情绪或感情色彩，同时禁止猜测被遮挡或无法确认的细节。

最终固定 prompt 为：“请用80至150字的自然中文，描述这张图片中明确可见的内容，并概括它传达的情绪或感情色彩；可以结合人物表情、动作和画面元素判断，但不要猜测被遮挡或无法确认的细节。”第三次返回耗时 1578 ms，input/output/total token=316/98/414，request_count=1、client_automatic_retry=false、thinking_enabled=false。回复正确覆盖黑白头发、清晰可见的眼睛、下方大爱心和周围漂浮爱心，并概括爱意、兴奋、撒娇，主人接受该内容质量。

供应商回复前导出现孤立 </think>。主人批准的有限清理只处理响应开头的完整 <think>…</think> 块或孤立 </think>；不在正文全局替换标签文本。没有执行第四次请求。

随后主人批准把百炼 qwen3.7-flash 作为主要生产视觉回复模型，并用云视觉面板原位替换 Owner Console 原有本地视觉配置/诊断面板。新增 aliyun_bailian_vision.py 作为可复用生产客户端：固定北京地域 Workspace URL 正则、OpenAI-compatible /chat/completions、HTTPS、trust_env=false、follow_redirects=false、有界超时/响应、PNG/JPEG/GIF/WebP magic 校验、固定模型、无 tools、无 retry、关闭 thinking、严格 model/usage/response 合同和有限 cleanup。鉴权与供应商错误映射为固定安全错误，不透传 Key、原始正文或 endpoint。

生产 vision.py 的 describe_images() 路径改为百炼调用；保留原有输入下载、Base64/大小校验、提示注入/隐私清理、可靠性结果与固定失败标记。旧 _ollama_chat_vision()、本地诊断 executor 和历史测试仍保留，但生产路径不再调用它；云请求失败时不 fallback 到 Ollama 或 Plus。

Owner Console 新增独立 workflow=cloud_vision_fixed_description，固定同一 owner_private 参考图、同一情绪描述 prompt、一次请求和主人语义质检。FastAPI 增加固定执行 POST、受保护参考图 GET、接受 POST、拒绝 POST；全部要求 loopback/same-origin、动作 Cookie、精确 Header/body，并与其他手动诊断共享单一全局锁。接受/拒绝和预览不会再次调用模型。页面没有增加第六块视觉面板，而是原位替换旧视觉面板；显示阿里云百炼、北京地域、qwen3.7-flash、URL/Key 配置布尔值、owner_private 外发说明、固定参考图、清理后回复、response_cleanup_applied、input/output/total token、耗时和主人接受/拒绝。没有图片上传、自由 prompt、模型、URL、Key、fallback 或连续测试控件。

启动脚本将旧 -EnableVisionInferenceProbe 替换为 -EnableCloudVisionProbe；旧本地 HTTP 路由装饰器和 executor 保留为历史兼容，但生产 factory 强制 vision_inference_enabled=false，只有云视觉入口可被新开关启用。诊断只返回 URL/Key 是否配置，不返回原值。

离线回归结果：Python full 734 tests OK（skipped=4）；Owner Console manual diagnostics 19 tests OK；frontend 4 files/31 tests OK；TypeScript typecheck、Vite production build、只读边界 guard、16 个本轮 Python 文件 AST、PowerShell launcher parse、pip check、git diff --check 全部通过。新增 FastAPI fake 端到端测试证明缺 Cookie、非同源、错误 Header、夹带 image/prompt 均在 executor 前失败，预览和主人接受/拒绝不触发模型重跑。所有自动化使用 fake transport/内存数据；没有读取 `.env` 正文、发起第四次云请求、访问本地模型、重启 Bot/Owner Console、写 QQ、执行 RAG 或修复 MemoryRAG。

严格当前状态：isolated_live_passed=true、owner_accepted=true、credentials_configured_privately=true、production_implementation=true、owner_console_replacement_implemented=true、regression_passed=true、bot_restarted=false、owner_console_restarted=false、production_cloud_primary_loaded=false、owner_console_cloud_panel_loaded=false。下一步只能由主人决定是否另行批准重启加载；重启本身不得自动执行云诊断，生产 QQ 图片集成验收也不能由本次固定样本测试替代。
```

## 2026-07-27 Owner Console 云视觉页面加载

```text
主人批准先只重启 Owner Console，以查看原位替换后的云视觉界面和诊断入口；本次授权不包含 Bot、Ollama、TTS 重启，也不包含自动执行百炼请求。

启动前只读核对确认 8090 没有 listener，旧 Owner Console 已不在运行。随后使用 start-owner-console.ps1 同时保留 ProjectDocRAG、MemoryRAG consistency、Main LLM contract、TTS synthesis 四个既有开关，并启用新的 -EnableCloudVisionProbe。新进程 PID=15220，监听 127.0.0.1:8090；静态页面、health、manual-diagnostics、routes 和 diagnostics GET 均为 200。

运行快照显示 supported_workflows=project_doc_rag_fixed_retrieval,memory_rag_index_consistency,main_llm_fixed_contract,tts_managed_lifecycle,cloud_vision_fixed_description；route_count=28。云固定执行、参考图预览、接受和拒绝四条路由启用，旧 manual-diagnostics.vision-inference 路由禁用。静态 bundle 包含 cloud-vision-fixed-description、qwen3.7-flash 与阿里云百炼界面文本。

配置只读证据为 vision_provider=aliyun_bailian、vision_model=qwen3.7-flash、vision_region=cn-beijing、workspace_configured=true、credentials_configured=true、automatic_local_fallback=false。没有读取或输出 URL/Key 原值。

启动后的 latest_run=null、cloud_vision_latest_run=null、vision_inference_executed=false，证明页面加载和只读 smoke 没有发送固定图片、调用百炼或执行其他诊断。11434 的现有 listener PID=4388 未被操作，7861 无 listener；Bot 未重启，生产 describe_images() 百炼主链仍未加载。Owner Console stderr 仅有正常 uvicorn startup 与本次 GET 200 记录。

当前严格状态：owner_console_loaded=true、ui_smoke_passed=true、cloud_diagnostic_not_run=true、bot_not_loaded=true、production_live_not_verified=true。下一步由主人打开页面检查视觉面板；只有主人在外发说明后第二次确认，才会产生一次固定百炼请求。
```

## 2026-07-27 QQ 云视觉 live 通过与启动脚本 Ollama 收口

```text
主人通过 scripts/start.ps1 启动当前代码。Bot 父/子 PID=24552/15332，8080 正常监听并建立 QQ 生产链；Owner Console PID 15220 与既有 11434 Ollama PID 4388 保持运行，7861 无 listener。

主人连续发送两张 QQ 图片，确认 qwen3.7-flash 均能准确描述图片内容且响应速度很快，回复没有内容问题。只读 reliability_event_buckets 查询仅选择 component/operation/category/code/outcome/count/time/runtime_id，不读取图片、消息、用户或回复正文；当前 runtime_id=21c3714e-32d3-4547-b12c-cea686d2dadb 在 2026-07-26T16:50:24+00:00 至 16:51:07+00:00 聚合 occurrence_count=2 的 vision/infer/operation_succeeded/succeeded，与主人两张图片反馈一致。QQ 生产云视觉状态更新为 loaded/live_passed/owner_accepted。

主人同时指出 scripts/start.ps1 仍会因为 ENABLE_VISION=true 调用 ensure-ollama.ps1 检查 VISION_MODEL=qwen2.5vl:3b。生产视觉已经切到百炼后，这一启动依赖属于陈旧合同。最小修订从 ensure-ollama.ps1 删除 ENABLE_VISION、VISION_OLLAMA_BASE_URL、VISION_MODEL 和 qwen2.5vl:3b 对 needsOllama/requiredModels/BaseUrl 的影响。

scripts/start.ps1 仍调用 ensure-ollama.ps1，以保留真实需要的本地 RAG 依赖：只有 ENABLE_MEMORY_RAG 或 ENABLE_PROJECT_DOC_RAG 开启、且 MEMORY_RAG_EMBEDDING_PROVIDER=ollama 时，才检查 MEMORY_RAG_EMBEDDING_BASE_URL 与 MEMORY_RAG_EMBEDDING_MODEL（默认 bge-m3），必要时沿用受控 Ollama 启动逻辑。视觉开启但 RAG 关闭、或 RAG 使用非 Ollama provider 时，脚本立即报告 “Ollama ensure skipped: Ollama-backed RAG is disabled.”，不访问 /api/tags、不启动 Ollama。

新增 test_ensure_ollama_startup_contract.py：源码合同拒绝视觉 Ollama 变量和 qwen2.5vl；两个真实 PowerShell 子进程场景分别验证 vision-only 与 non-Ollama RAG 均在零网络/零启动前提下退出 0。聚焦 3 tests OK；Python full 737 tests OK（skipped=4）；ensure-ollama.ps1/start.ps1 PowerShell parse、git diff --check 通过。

修订期间没有重启当前 Bot、Owner Console 或 Ollama，没有再次发送图片、调用百炼、写 QQ、执行 RAG 或修复两条 MemoryRAG 缺失向量。脚本变化从下一次 start.ps1 启动开始生效；当前 Bot 无需为此重启。
```

## 2026-07-27 QQ 与 Owner Console 启动优化

```text
主人批准四项最小启动优化：QQ 启动前检查 8080/实际 PORT 与进程所有权；Ollama 在线但缺少必需模型时明确失败且绝不重启健康服务，只有明确离线才启动；gap_scene_summaries 延迟导入聊天 LLM；Owner Console 用高频 /healthz 检查替代固定整秒端口轮询并显示 ready 耗时。

scripts/start.ps1 现在先从当前进程环境或 .env 解析 PORT（默认 8080），读取 listener 的 PID、进程名、ExecutablePath 与 CommandLine。同一项目 Python/bot.py 已监听时显示已有 PID 并以 0 退出；其他进程占用时明确失败；端口空闲后才执行 ensure-ollama 和绝对路径 bot.py。新增真实临时 Python listener 行为测试，证明项目 Bot 监听会在 Ollama 和 bot 启动之前被识别，不产生第二个 Bot。

scripts/ensure-ollama.ps1 删除通用 needsRestart 分支。/api/tags 在线且缺少 bge-m3 等必需模型时直接返回错误，明确健康服务不会因缺模型重启；超时、HTTP 或畸形响应属于所有权不明确，拒绝启动/重启。只有异常链中存在 SocketError.ConnectionRefused 才允许本地启动，并固定向既有启动脚本传入 -KeepExisting，不结束任何现有 Ollama 进程。fake /api/tags 空模型行为测试证明返回 1、输出缺模型与不重启说明，且没有进入 Starting Ollama。

gap_scene_summaries.py 不再在模块顶层 from .llm import summarize_gap_scene_messages；只在真正需要生成新 gap-scene summary 的 _ensure_slot 路径延迟导入。Owner Console 只读 gap_scene_summary_stats 因此不加载聊天 llm 或 OpenAI SDK。独立子进程证据为 openai_loaded=false、chat_llm_loaded=false；仅导入并构造 Owner Console app 的修改前稳定样本约 1859.8–2271.3 ms，修改后约 1012.9–1328.6 ms，修改后稳定平均约 1098.4 ms。该基准只代表本机本轮模块导入，不等于生产 HTTP ready 总耗时。

scripts/start-owner-console.ps1 新增固定 loopback health GET：每 200 ms 请求 /healthz，要求 ok=true、service=owner-console，并在成功后继续验证 8090 listener 的命令行所有权；子进程提前退出或 10 秒截止仍按失败处理。成功输出 Stopwatch.ElapsedMilliseconds。没有开放或执行任何诊断动作。

验证结果：聚焦启动/launcher/gap-scene 22 tests OK；Python full 741 tests OK（skipped=4）；scripts/start.ps1、ensure-ollama.ps1、start-owner-console.ps1 PowerShell Parser 均通过，git diff --check 通过。测试只使用临时本地 listener、fake tags HTTP、明确 connection-refused 的未监听临时端口和独立 Python 导入进程；没有调用本地/线上模型、执行 RAG、读取私人记忆、修复缺失向量、发送 QQ、启动 TTS 或重启生产 Bot、Owner Console、Ollama。当前严格状态为 owner_approved/implemented/regression_passed/not_loaded；实际生产 ready 输出与重复启动体验等待主人另行批准重启后观察。
```

## 2026-07-27 external-read 证据回答 v2 fake-only 实现

```text
主人确认此前联网功能没有带来明显业务质量改善，并批准第一优先优化：保留主人私聊严格命令和固定 Tavily provider，把三条短搜索卡片升级为更多候选、同次响应的受限正文证据、一次隔离综合、编号来源/不确定性和主人接受/拒绝。普通聊天、Main LLM 自主工具选择、任意 URL、浏览器、Agent Reach CLI、Jina Reader、Cookie/登录平台和第二 provider 继续不开放。

Tavily 固定参数升级为 search_depth=advanced、chunks_per_source=2、max_results=5、include_raw_content=text、include_answer=false、include_images=false、auto_parameters=false、include_usage=true。仍只有一次 POST api.tavily.com/search，沿用 DNS 公网校验、IP 钉扎、TLS、无 redirect/proxy/retry、256 KiB 与超时上限。external_request_count=1 保留 provider 请求旧语义，新增 provider_request_count=1 与 synthesis_request_count=0|1。

ExternalSearchResult/SanitizedExternalSearchResult 增加 transient raw_content、score 和去 query/fragment 的安全 source_url。raw content 与 title/snippet/date 一起经过 HTML、Unicode、控制字符、外链和提示注入清洗；疑似注入项不进入综合。provider 最多 5 个候选，最终优先不同 host、最多 3 个证据，每来源最多 3500 字、总计最多 9000 字。

新增 external_research_synthesis.py。综合只收到当前公开 query 与编号证据，不读取聊天历史、角色卡、MemoryRAG、ProjectDocRAG、DevContext 或 CombinedRAG。专用 Main LLM 客户端固定 max_retries=0、temperature=0.1、max_tokens=1200，只有 system/user 两条消息且不绑定 tools。回答最多 1800 字并必须引用实际存在的 [n]；空白、无引用、越界引用、过长或调用异常均只请求一次并退回确定性来源列表。模型生成 URL 被移除，最终 URL 只由本地已校验 evidence 附加。

正式任务继续不保存 query、搜索标题/摘要/raw content、URL、完整回答、endpoint 或原始异常。安全摘要新增 provider/综合请求计数、综合状态和主人质量枚举。有结果先为 owner_quality_pending，QQ 回复显示 `/agent 接受联网结果 #ID` 与 `/agent 拒绝联网结果 #ID`；质检只允许同一主人私聊、固定 external-read done 任务，并只更新 owner_accepted/owner_rejected，不重新搜索或综合。无结果为 not_applicable。

Owner Console external-read 页同步显示 advanced、5 候选、隔离综合是否配置、最近 provider/综合计数、综合状态和主人质量；受限 raw content 标为只用于本次证据，本状态页仍不展示 query、正文、URL 或凭据值。

全量回归同时暴露上一阶段未加载的 start.ps1 临时 Python listener 在当前 Windows 测试上下文中可能无法被 Get-NetTCPConnection 枚举且不报错。最小收口保留该 cmdlet 为第一选择，只在结果为空时解析系统 netstat -ano -p tcp 的 LISTENING PID，再沿用进程所有权判断；CIM 命令行不可见时尝试 Get-Process 路径，仍无法证明项目 Bot 所有权就保守报告端口被其他进程占用并退出，不启动第二个 Bot。测试等待 netstat 明确看见临时 listener，并接受“确认项目 Bot后退出 0”或“所有权不可证后拒绝退出 1”两种安全结果，均禁止进入 NoneBot 初始化。

聚焦测试覆盖 advanced 请求体、raw content、URL 清理、证据 host 多样性与字符预算、注入排除、一次零工具综合、无效引用/异常回退、持久化隔离、主人质检和 Owner Console 元数据。最终 Python full 750 tests OK（skipped=4）；Owner Console frontend 4 files/31 tests、TypeScript、Vite production build 与只读 guard 通过。自动化全部使用 fake Tavily transport/fake LLM/临时 SQLite；没有读取真实 Key、访问 Tavily/Main LLM/Agent Reach/本地模型、执行 RAG/私人记忆、修复缺失向量、重启服务、写 QQ、commit 或 push。

当前严格状态：owner_approved/implemented/regression_passed/not_loaded/not_live/owner_quality_not_reviewed。fake-only 只能证明实现与安全合同，不能证明真实来源质量、回答正确性、延迟或主人接受。下一步只能由主人另行批准自然重启加载和一次严格查询 live，再亲自接受或拒绝。
```

## 2026-07-28 external-read #52 拒绝与 v2.1 最小修订

```text
主人批准重启加载累计修改。Owner Console 以五个既有手动诊断开关启动，8090 /healthz 正常且 automatic diagnostics/configuration write/business data write 均 false；external-read 页面确认 enabled/credential/executor/synthesis=true、advanced、max_results=5，启动没有执行 live 探针。Bot 随后通过正式 start.ps1 启动，8080 正常监听并与 QQ 建立连接；既有 Ollama 11434 未重启，7861 未启动。

真实重复启动验收发现受限沙箱内无法读取 WMI/CIM 命令行时脚本会保守报告端口被其他进程占用并退出 1，不启动第二个 Bot；正常 Windows 权限下同一脚本准确识别 venv/bot.py 进程链，输出 already running 并退出 0。补充 netstat listener PID 兜底、WMI/Get-Process/父进程证据后，聚焦 2 tests 与 PowerShell parse 通过。

主人通过严格 QQ 命令执行 advanced/basic 公开问题，任务 #52 的 Tavily advanced 搜索一次成功，返回 5 个候选/5 个 host；隔离综合一次调用为 call_failed，最终进入 synthesis_fallback。兜底包含 Tavily 文档导航/SDK 片段以及两个与 advanced/basic 核心差异关系较弱的第三方博客，没有直接回答问题。主人明确拒绝质量。Owner Console 安全快照仍为 owner_quality_pending，没有绕过 QQ 门控直接改数据库。

旧实现只记录 call_failed，不能确认 provider 根因。与已知可调用 Main LLM 客户端相比，隔离客户端额外设置 temperature=0.1 与 max_tokens=1200，因此它们是高概率兼容变量但不是已证实根因。主人批准四项最小修订：移除两项新增参数并只保留 max_retries=0；增加不含异常正文的安全失败分类；semantic snippet 优先、raw content 仅补充且失败兜底只显示 snippet；综合成功只显示实际引用来源，并区分 call_failed 与 invalid_response 文案。

修订后 Python full 752 tests OK（skipped=4）；Owner Console frontend 4 files/31 tests、TypeScript、Vite production build、只读 guard 通过。自动化继续使用 fake Tavily/fake LLM/临时 SQLite，没有第二次真实搜索、模型调用、服务重启、RAG/私人记忆、QQ 写入、commit 或 push。严格状态为 owner_approved/implemented/regression_passed/not_loaded/not_live/owner_quality_not_reviewed；下一次真实验证必须由主人另行批准重载与严格查询。
```

## 2026-07-28 external-read #55 Main LLM 恢复与主人质量验收待登记

主人确认原 MainAgent 兼容端点 URL 已失效并更新 `.env`，随后只重启 QQ Bot 重新加载配置；Owner Console、Ollama、NapCat 和 TTS 未重启。Bot 8080 正常监听并与 OneBot 建立连接。

主人通过 QQ 先拒绝 #52，修复后的单行任务摘要质检路径真实写入 `owner_rejected`。之后 #54 仍在旧 Main LLM URL 下出现 `synthesis_error_category=connection_failed`。主人更新 URL 后重新执行相同问题，创建任务 #55：

```text
provider_request_count=1
synthesis_request_count=1
synthesis_status=completed
synthesis_error_category=none
status_category=completed
owner_quality_status=owner_quality_pending
```

模型输出中文直接回答、主要依据和不确定性，关键事实带有效引用；Tavily 一次、隔离综合一次、零工具、零自动重试、零 provider fallback。#55 的主人接受/拒绝尚未登记，不能把技术完成自动写成主人接受。

## 2026-07-28 MainAgent 主人普通私聊自主联网实现

主人批准取消“固定联网命令唯一入口”，但只针对主人普通私聊。MainAgent 工具注册新增 `external_read`，风险级别为 `read_external`，执行器复用现有 `prepare_external_read_command` 与 `OwnerAgentWorkRuntime`；不新增 provider、不新增 fallback、不绕过任务和主人质量门控。

普通主人纯文字私聊在 ChatGraph 前增加仅 external-read 工具可见的 MainAgent 预判：模型选择联网时执行一次固定 Tavily 和最多一次隔离综合并直接返回；模型不选择联网时丢弃预判结果，原样继续 ChatGraph。普通聊天不暴露 owner_read、owner_write、document_delivery、agent_task、DevContext 或任何写工具。群聊、非主人、命令消息、图片消息、URL/凭据/本地路径以及 RAG/记忆写入继续禁止。

新增边界/工具/提示合同测试与 Owner Console 动态边界快照测试；Python full `758 tests OK（skipped=4）`，前端 `31 tests OK`，TypeScript 与 Vite production build 通过，`git diff --check` 通过。本轮没有发起 Tavily、Main LLM、RAG、TTS、视觉或 QQ 业务消息；实现尚未重启加载。

主人下一步只需批准一次受控重启，然后在主人私聊发送一条不带 `/agent` 的公开时效问题完成 live 验收；若 MainAgent 判定无需联网，消息会继续原普通聊天链路，不创建外部任务。

## 2026-07-28 external-read #56 时效失败与可信时间窗口修订

主人通过普通私聊自然语言真实触发任务 #56，证明 MainAgent 只暴露 `external_read` 的预判、正式 Tavily 任务和隔离综合已经加载可用。问题要求“当前日期往前一个月”的模型发布，运行环境日期为 2026-07-28，正确窗口应为 2026-06-28 至 2026-07-28；结果却主要列出 2026 年 1 月下旬至 2 月上旬项目。主人指出内容时效不合格。

只读诊断确认旧链路没有给 MainAgent 提供可信当前日期，相对时间未变成绝对窗口，Tavily 请求没有 `topic/start_date/end_date`，本地时效逻辑只提示和排序而不硬过滤，`published_at` 缺失或范围外的聚合页仍可进入隔离综合。隔离模型没有联网工具，也不能扩大证据，只能基于本次错误候选声明不完整并列出旧内容。

主人批准先实现前五项，第六项扩大候选数暂不做。代码新增可信相对日期正规化，按 Bot 本地时区把“当前日期往前一个月”固定重写为 2026-06-28 至 2026-07-28，并给 MainAgent 自主预判和显式 `/agent` planner 同一绝对日期与官方来源要求。Tavily 仍是一次 Advanced 请求、`max_results=5`，有窗口时加入 `topic=news/start_date/end_date`。

搜索结果返回后执行本地硬过滤：窗口内 provider `published_date` 为强证据；标题/摘要/正文只有一个窗口内日期时仅标为 `content_weak`，且至少存在一条强证据才允许作为补充；范围外、无日期、多个正文日期、只有弱证据的结果全部拒绝。过滤后无证据时不调用隔离综合，任务进入 `no_results/not_applicable`，明确无法确认并停止，不列旧项目、不自动重试。综合提示词同步禁止窗口外内容，并声明弱日期不能单独证明发布时间或完整清单。

新增冻结 2026-07-28 的 fake-only 测试，覆盖月末夹取、本月/本周/今天、安全拒绝与长度上限、Tavily 时间请求体和非法参数、强/弱/越界/无日期过滤、无证据零综合调用、两个 MainAgent 入口。定向 68 tests、MainAgent/Owner Console 185 tests 均通过；最终 Python full 772 tests OK（skipped=4），Owner Console frontend 31 tests、TypeScript typecheck、Vite production build 和相关 AST 通过。

本轮没有读取 Key、调用 Tavily/Main LLM/百炼/本地模型、执行 RAG/私人记忆、修复 MemoryRAG 向量、写 QQ、重启 Bot/Owner Console、暂存、提交或推送。严格状态为 `owner_approved/implemented/regression_passed/not_loaded/not_live`。下一步只由主人手动重启 Bot，并在普通主人私聊用相对时效问题验证；证据不足时返回无法确认也是符合合同的成功行为。

## 2026-07-28 撤回日常聊天 MainAgent 预判

主人明确指出“MainAgent 自主触发联网”不等于允许把 MainAgent 注入日常聊天，并要求撤回普通聊天预判。当前永久边界重新固定为：日常聊天只走原 ChatGraph，不调用 MainAgent；只有主人显式输入 `/agent` 后，MainAgent 才能在受控工具表中自主选择 `external_read`。以后任何 MainAgent 能力改进必须区分显式 `/agent` 与日常聊天，未经主人单独授权不得跨越入口。

代码删除 `run_owner_autonomous_external_read`、`handle_chat` 中位于 ChatGraph 前的调用，以及只为普通聊天预判创建的 `create_external_read_main_agent_tool_registry` 和导出。显式 `/agent` 内的 owner-private/executor 配置门控、正式 external-read 任务、可信日期窗口、一次 Tavily、最多一次隔离综合、主人质检均保留。

Owner Console external-read 边界改为：`owner_private_strict_command_only=true`、`main_llm_can_trigger=true` 只表示显式 `/agent` 内可选择联网、`ordinary_chat_can_trigger=false`。页面将日常聊天注入显示为“禁止”，若未来后端返回 true 则按异常展示。反向源码测试要求 `handle_chat` 不出现 MainAgent 或 external-read 预判，并要求已删除的函数和专用注册器不能重新出现。

定向 MainAgent/Owner Console/时间窗口回归 166 tests OK；最终 Python full 772 tests OK（skipped=4），Owner Console frontend 31 tests、TypeScript typecheck 和 Vite production build 通过。本次只进行代码、测试和文档修订，没有重启 Bot/Owner Console，没有调用 Tavily、Main LLM、百炼、本地模型、RAG 或私人记忆，没有发送 QQ、修复向量、暂存、提交或推送。当前为 `removed/regression_passed/not_reloaded`。

## 2026-07-28 external-read 可信窗口执行绑定与模糊时间收口

撤回普通聊天预判后的只读审计发现一个未被既有回归覆盖的显式 `/agent` 参数断点：planner 先把相对日期改成绝对文本，但 MainAgent 自行生成 `arguments.query`，Tavily executor 当时又只从工具 query 重新识别相对关键词。若模型只输出绝对范围或省略时间措辞，executor 会得到 `time_window=None`，从而可能不发送 `topic/news/start_date/end_date`、也不运行本地日期硬过滤。此前测试只分别覆盖 planner 绝对日期和 executor 直接收到相对 query，没有串联这两段。

主人批准最小修复。当前从原始显式 `/agent` query 和 `BOT_TIMEZONE` 计算 `ExternalReadTemporalQuery`，planner 仍只看到绝对日期与官方来源要求；若其选择 `external_read`，同一可信对象通过本次调用闭包和 OwnerRuntimeFactory 绑定到 Tavily executor。executor 使用可信 query/time_window，而不允许 MainAgent 重述文本修改、遗漏或取消日期边界。绝对 `YYYY-MM-DD 至/到 YYYY-MM-DD` 也获得同一 `absolute_range`、Tavily 参数和本地硬过滤合同，非法或反向日期在网络前拒绝。

裸“最近/近期/近来/recently”没有明确周期时不再猜测。MainAgent prompt 要求 `ask_owner`；执行层同时 fail closed，即使模型错误选择工具，也会在 external-read 任务创建前要求主人改为最近一周、最近一个月、本月、本周、今天或绝对起止日期，并明确本次没有调用 Tavily 或综合模型。该保护只属于显式 `/agent` 工具链，普通聊天继续直接进入原 ChatGraph，不调用 MainAgent 或 external-read。

新增 fake-only 回归模拟 MainAgent 把 query 重述为不含相对关键词的文本，仍验证唯一 Tavily 请求固定 `topic=news/start_date=2026-06-28/end_date=2026-07-28`，窗口外 2026 年 1 月证据被过滤。定向 60 tests、相关 259 tests、最终 Python full 778 tests OK（skipped=4）。全量首次运行只有两条旧源码字符串合同因可选参数导致签名文本变化而失败；测试随后改为匹配函数名边界并新增可信参数断言，相同 RAG/只读约束未削弱，重跑通过。

本轮没有读取 Key、调用 Tavily/Main LLM/百炼、本地模型、执行 RAG/私人记忆、修复向量、写 QQ、重启 Bot/Owner Console/Ollama/TTS、暂存、提交或推送。严格状态为 `owner_approved/implemented/regression_passed/not_loaded/not_live`，`max_results=5`、一次 Tavily、最多一次综合、零 retry/fallback 保持不变。

## 2026-07-28 external-read #57 fail-closed 与丢弃原因安全计数

主人手动加载可信窗口修订后，通过显式 `/agent` 查询 2026-07-28 往前一个月的重要模型发布。任务 #57 明确使用 2026-06-28 至 2026-07-28，Tavily Advanced 单次请求取得 5 个候选，但本地日期资格过滤后 `result_count=0`、`dropped_result_count=5`、`source_host_count=0`；没有调用隔离综合，`synthesis_request_count=0`、`synthesis_status=not_run_no_evidence`。回复明确无法确认并停止，没有为了丰富结果而列范围外或日期不可靠的旧内容。该 live 证明时间修订 fail-closed 生效，但不证明搜索召回充分。

旧任务摘要只记录总丢弃数，无法判断 #57 的 5 条分别属于日期缺失、窗口外、仅弱日期、日期冲突、注入嫌疑还是清洗/去重/预算丢弃。主人批准继续做最小可观测性修复：只增加 `provider_candidate_count` 和上述六类互斥整数计数，正式 sanitizer 强制原因和等于总丢弃数、候选数等于结果数加丢弃数。任务摘要、`/agent` 状态/任务详情、Owner Console Python DTO/API/TypeScript 页面全部同步；旧任务缺少字段时显示未知，不读取或恢复历史 query、标题、摘要、正文、URL、host 或 provider 响应。

实现没有改变 `max_results=5`，没有放宽 provider 强日期/正文弱日期资格，没有增加 Tavily 请求、自动重试、provider fallback 或综合调用。定向 Python 106 tests OK；最终 Python full 779 tests OK（skipped=4）。Owner Console frontend 5 files/33 tests、TypeScript typecheck、Vite production build 和只读 guard 通过。自动化只使用 fake provider/fake LLM/临时 SQLite；没有读取 Key、调用 Tavily/Main LLM/百炼/本地模型、执行 DevContext/RAG/私人记忆、修复 MemoryRAG 向量、写 QQ、重启 Bot/Owner Console/Ollama/TTS、暂存、提交或推送。

新计数当时严格状态为 `owner_approved/implemented/regression_passed/not_loaded/not_live`；只对加载后的新任务生效，#57 的具体丢弃原因无法追溯恢复。后续任务 #59 已证明这些计数完成加载。

## 2026-07-28 external-read #58/#59 与官方正文强日期最小修订

主人加载日期丢弃原因计数后，任务 #58 在固定 Tavily provider 单次请求阶段超时；MainAgent、显式 `/agent` 入口、工具选择和正式任务创建均正常。系统按合同失败，没有自动重试、切换 provider 或调用综合模型。主人随后主动创建任务 #59，Tavily Advanced 一次成功返回 5 个候选。

#59 的安全摘要为：`provider_candidate_count=5`、`result_count=0`、日期缺失 4、仅弱日期 1，窗口外、日期冲突、注入嫌疑、清洗/去重均为 0，综合请求为 0。该计数证明本次归零不是因为证据位于 2026-06-28 至 2026-07-28 之外，也不是冲突或安全清洗，而是旧日期解析只识别有限年首格式，加上正文唯一日期必须依附至少一条 provider metadata 强日期。由于任务不保存正文和原始日期，无法确认 4 条是否真的无日期或采用了旧解析器不认识的英文日期格式。

主人批准最小修订：支持完整、无歧义的单双位年首日期、中文年月日、英文月名日期、RFC 日期和 ISO 日期时间中的完整日期；继续拒绝无年份、无日、相对日期和非法日期。新增 `official_content_strong`，只允许既有固定官方域名白名单、标题/摘要明确发布语义、标题/摘要/受限正文合计唯一完整日期、日期位于窗口内且既有清洗全部通过的结果升级。白名单没有扩大，第三方、恶意后缀域名、无发布语义、多日期、窗口外、无日期或注入内容均不能升级。

正式 payload 与任务摘要新增 `official_content_strong_count` / “官方正文强日期数”，强制为 0–5 且不大于结果数；`/agent` 状态/详情和 Owner Console 只读 DTO/API/页面同步显示。隔离综合明确区分 provider metadata、official content strong 和 content weak，不把官方正文日期伪装成 provider 元数据。

fake-only 端到端测试模拟 #59 结构：4 条无完整日期加 1 条没有 provider `published_date`、但 `openai.com` 标题具有发布语义且正文日期为 `July 12, 2026` 的候选。修订后只保留这一条，`official_content_strong_count=1`，并仍只有一次 fake 搜索和最多一次 fake 综合。反向合同覆盖第三方相同日期、`openai.com.evil.example`、无发布语义、多日期、无年份和非法闰日。

定向 Python 181 tests OK；最终 Python full 783 tests OK（skipped=4）。Owner Console frontend 5 files/33 tests、TypeScript typecheck、Vite production build 和只读 guard 通过。本轮没有读取 Key、调用真实 Tavily/Main LLM/百炼/本地模型、执行 RAG/私人记忆、修复向量、写 QQ、重启 Bot/Owner Console/Ollama/TTS、暂存、提交或推送。`topic=news`、`max_results=5`、单次 Tavily、零 retry/fallback、无证据零综合和普通聊天不进入 MainAgent 均保持不变。当前新修订为 `owner_approved/implemented/regression_passed/not_loaded/not_live`。

## 2026-07-28 external-read 官方优先两阶段检索

任务 #60 使用既有单次 `topic=news` 请求成功召回 Business Insider、AP 和 Reuters，但没有发布方官方来源。主人确认这说明“优先官方”的 query 文字不能改变 provider 的新闻召回倾向，并批准先实现官方优先、媒体补充的两阶段固定检索。

实现保留主人原问题的绝对时间化版本。阶段 1 固定使用 `topic=general`、同一 `start_date/end_date` 和第一方/官方来源条款，并在本地只接受可识别官方 host；阶段 1 请求成功但官方合格证据为 0 时，阶段 2 才使用同一核心问题、同一窗口、`topic=news` 和可靠媒体条款。阶段 2 不读取阶段 1 网页内容生成 query，也不由 MainAgent 编写。阶段 1 若超时、认证/连接失败、provider 不可用或响应非法，任务直接失败，不进入阶段 2。固定 provider、每阶段 `max_results=5`、不扩大窗口、零 provider fallback、零自动重试、隔离综合总计最多 1 次保持不变。

任务摘要、`/agent` 状态/详情和 Owner Console 新增安全整数：检索阶段数、官方/媒体阶段候选数与合格数、来源策略丢弃数。两阶段聚合仍校验候选数和丢弃原因总和；媒体证据带 `media_fallback` 标签，隔离综合和最终回复明确不能把它自动表述为发布方官方确认。

fake-only 回归证明：官方命中只有 1 次 transport 调用；官方阶段为 0 时恰好调用第 2 次且保持同一窗口与核心问题；阶段 1 timeout 时只有 1 次调用且不综合；两阶段仍只综合 1 次。定向 Python 181 tests OK，最终 Python full 785 tests OK（skipped=4）；Owner Console frontend 5 files/33 tests、TypeScript typecheck、Vite production build 和只读 guard 通过。本轮没有读取 Key、调用真实 Tavily/Main LLM/百炼/本地模型、执行 RAG/私人记忆、写 QQ、重启 Bot/Owner Console/Ollama/TTS、暂存、提交或推送。当前严格状态为 `owner_approved/implemented/regression_passed/not_loaded/not_live`。

## 2026-07-30 external-read #64 raw content 关闭与阶段失败诊断

主人加载带“两阶段”提示的新 external-read 工作运行时后再次真实测试，任务 #64 在 14:19:23 创建并于 14:19:40 以 `response_too_large` 失败。只读事件为 created、work_claimed、work_started、work_failed；没有自动重试。旧任务安全摘要没有阶段或请求计数，不能从 #64 判断是官方阶段超限，还是官方归零后的媒体阶段超限，也不能只凭提示文案证明两阶段 executor 的完整加载版本。任务没有持久化 query、正文、URL 或 provider 原始响应。

代码审计确认每阶段仍以 Tavily Advanced、`chunks_per_source=2`、`max_results=5` 请求 `include_raw_content="text"`。最多 5 份页面级正文可能在本地字符截断前突破固定 262144 字节门控；重复相似请求继续失败不是网络 timeout，也不是日期过滤或综合模型问题。主人明确批准关闭 raw content 并增加阶段失败诊断，不批准提高字节上限。

固定请求现为 `include_raw_content=false`，adapter 同时忽略 provider 意外返回的 `raw_content`。日期资格只使用 provider 日期、标题和受限搜索摘要；官方 host、发布语义、唯一完整窗口内日期、日期窗口和所有安全清洗仍保持。日期只在页面深处的结果可能降低召回，但不会通过提高安全上限、降 `max_results`、改 basic、自动重试、provider fallback 或打开来源页面补偿。

官方和媒体 provider 调用边界现在把策略异常包装成安全阶段错误。失败任务持久化 `failed_search_stage`、检索/外部/Provider 请求数、固定综合请求 0 和最终错误类别；用户回复显示中文失败阶段。任务状态、Owner Console Python DTO/API、TypeScript 类型和页面同步，`raw_content_enabled=false`。所有字段仅为固定枚举与整数，不保存异常 detail 或外部内容。

fake-only 定向回归：external-read 81、MainAgent bridge 65、Graph/LC 24、普通聊天/RAG/QQ 13；最终 Python full 789 tests OK（skipped=4）。Owner Console frontend 5 files/33 tests、TypeScript typecheck、Vite production build 和只读 guard 通过。本轮没有真实 Tavily/Main LLM、百炼、本地模型、RAG/记忆或 QQ 调用，没有重启服务、暂存、提交或推送。当前修订为 `owner_approved/implemented/regression_passed/not_loaded/not_live`；只有主人手动重启后新任务才会使用关闭 raw content 和阶段失败诊断。

## 2026-07-30 external-read MainAgent 动态检索规划

任务 #65/#66 在关闭 raw content 后能够完成，但仍沿用固定“官方优先、官方为零时媒体补充”。主人指出该链路只硬注入时间和官方要求，没有先理解提示词：本地生活问题通常无需官方文档，也不应在官方结果为 0 后机械消耗第二次搜索；版本与角色问题则需要先分析前置事实并生成更准确、足够短的搜索词。

主人批准放开 MainAgent 的问题理解与检索规划，但保留请求预算。显式 `/agent` 现在向 MainAgent 提供完整问题和内部可信当前日期；`external_read` 工具合同要求主查询与 `official|general|news` 来源范围，可选第二条互补查询、第二来源范围以及 `if_no_results|always` 条件。每条 provider 查询由本地硬限制为最多 50 字，合计最多两条。固定 Tavily、最多两次 provider 读取、零自动重试、零 fallback provider、最多一次零工具隔离综合、普通聊天不进入 MainAgent和主人私聊显式触发边界均未放开。

执行器不再把“优先官方网站/官方博客/官方公告”等长条款拼入实际 Tavily query；可信时间窗口继续通过结构化对象与 `start_date/end_date` 参数强制执行。`official` 继续经过本地官方 host 门控，`general` 不做官方门控，`news` 使用新闻主题。第二条 `if_no_results` 只在第一阶段无合格结果时执行，`always` 用于两个互补子问题都需要证据；未规划第二条时不得自行补查。旧固定两阶段路径保留为 `legacy_fixed`，只服务既有显式严格 external-read 合同与历史测试。

任务 payload、状态解析、FastAPI DTO、TypeScript 和 Owner Console 同步 `planning_mode`、第一/第二阶段来源与第二阶段条件；阶段候选/合格数改为中性名称，并继续解析历史官方/媒体字段。安全摘要只保存这些枚举和整数，不保存问题、搜索词、标题、摘要、URL 或答案。扩大定向 Python 233 tests、Python full 793 tests（skipped=4）、Owner Console 5 files/33 tests、TypeScript typecheck、Vite production build、只读 guard、Python AST 162 files 和 `git diff --check` 通过。没有调用真实 Tavily/Main LLM、重启服务、发送 QQ、写数据库、暂存、提交或推送。当前为 `owner_approved/implemented/regression_passed/not_loaded/not_live`。

## 2026-07-30 external-read #67 双 official 规划归零修复

主人重载动态检索规划后，以 `/agent 原神下一个版本的角色是谁` 创建任务 #67。任务显示 `MainAgent / official / official / always`，两次 Tavily 均执行但没有合格证据。这证明动态计划、两次预算和新版结果格式已真实加载，也证明首版提示仍可能把“需要第一方确认”错误理解为“两条都只接收官方来源”。代码审计同时确认官方 host 表缺少 `genshin.hoyoverse.com` 与 `ys.mihoyo.com`，所以真正的产品官网也可能被本地门控丢弃。

最小修复精确加入上述两个产品官方 host 及真实子域名，不放开包含用户内容的 `hoyolab.com` 或 `miyoushe.com`，并继续拒绝恶意后缀域名。MainAgent system prompt 和 external_read ToolSpec 新增未来游戏版本/未发布角色/复刻名单规则：需要两条时使用 official 确认加 general/news 互补，明确 general 仍可召回官方页面，禁止同一场景再次生成 `official + official`；综合仍必须把报道或预测标为非官方、不确定。桥接层同时增加窄范围确定性兜底：前瞻标记与角色/复刻/卡池/名单/选角标记同时出现时，把残留的第二条 official 改为 general；政策等无关双 official 计划不改变。

定向 131 tests OK，覆盖两个官方 host、真实子域名、恶意后缀、社区域名反向边界、#67 对应的双 official 本地校正、无关政策双 official 保持、official + general 双查询以及提示合同；Python full 795 tests OK（skipped=4）。没有真实调用 Tavily/Main LLM、重启服务、发送 QQ、写数据库、暂存、提交或推送。修复尚未加载或 live。

## 2026-07-30 Tavily Chat 参数对照与并行新闻检索修订

主人在 Tavily 官网 Chat 中抓取工具事件，确认“原神下一个版本的角色是谁”实际被拆成“原神最新版本角色预告”和“原神下一个版本角色”两条查询，均使用 `search_depth=basic/topic=news`，时间范围分别为 week 和 month；两个 `tool_start` 均先于 `tool_end`，说明是一次规划后的并行读取。裸 API 同参数、`max_results=10`、`include_raw_content=false` 对照把官方 7.0 前瞻排到第一，并复现官网 Chat 当时的 6 个 URL；包含“奥黛塔”的腾讯文章后来降到第 9 且返回 404，证明本地参数限制与外部排序/页面失效同时存在。

主人批准先按该行为改造并允许视情况补充。MainAgent 每条查询新增独立 `time_range` 和 `evidence_role`；news 固定 Basic，general/official 固定 Advanced；可信绝对日期仍优先使用 `start_date/end_date`。单次候选上限提高到 10，Basic 不发送 `chunks_per_source`；raw content继续关闭。`always` 两查询通过 `asyncio.gather` 同批执行，`if_no_results` 与 legacy fallback 保持串行；跨查询 URL 去重，显式 404/page not found/页面不存在结果在综合前丢弃。

隔离综合证据预算扩大到最多 10 条、12000 字符，并接收每条 evidence role。新合同要求先回答实体、检查全部证据、区分官方确认与媒体/爆料候选、拒绝失效来源支持事实；报告完整显示每条 scope、Basic/Advanced、time range、evidence role 与执行条件，Provider 总称改为 bounded search。Owner Console 运行时显示动态规划深度和 `max_results=10`。

核心定向 171 tests、状态与 Owner Console 47 tests、Python full 797 tests（skipped=4）、前端 5 files/33 tests、TypeScript typecheck、Vite production build和只读 guard全部通过。实现验证使用 fake transport/fake LLM，没有再次调用真实 Tavily，没有重启服务、发送 QQ、写数据库、暂存、提交或推送。当前为 `owner_approved/implemented/regression_passed/not_loaded/not_live`。

## 2026-07-30 external-read #69 聚合结果合同失败修复

主人重启加载 Tavily Chat 对照修订后执行任务 #69，任务以通用 `data_validation_failed` 失败。该提示来自未受控 ValueError 的通用映射，不是数据库损坏证据。代码审计确认 provider 已改为每查询最多 10 条、两查询最多 20 个候选，但正式任务 sanitizer 仍使用旧的“总量最多 10、每阶段最多 5”限制；真实返回超过旧上限时会在搜索完成后失败。跨查询 URL 去重还可能使去重前阶段结果数之和大于最终结果数，触发另一项一致性校验。由于安全摘要没有保存原始结果或异常 detail，不能证明 #69 最先命中哪一项旧校验。

现把总结果、来源、候选、丢弃及各丢弃原因上限统一为 20，每阶段候选/结果上限统一为 10；阶段结果数改为按聚合去重后的 `search_stage` 标签统计。新增两个阶段各 10 条且一个 URL 重复的回归，固定得到 20 候选、19 结果、1 个清洗去重丢弃，正式任务 sanitizer 接受；超过两阶段总预算的 21 条继续拒绝。结果合同 ValueError 现在包装为不含原始 detail 的 `ExternalReadResultValidationError`，用户提示明确说明不等于数据库、文件或索引损坏。

聚焦 external executor、正式工作运行时、状态和 Owner Console 99 tests OK；增加任务详情故障重新分类回归后，Python full 802 tests OK（skipped=4）。没有自动重试 #69、调用新的真实 Tavily、重启服务、发送 QQ、写数据库/RAG/记忆、暂存、提交或推送。修复尚未重新加载或 live。

## 2026-07-30 external-read #70/#71 检索验收与精简 fallback

任务 #70 真实使用两条 `news/basic` 查询和 week/month 时间范围，成功召回《原神》官方 7.0 特别节目预告，并把第三方候选保持为未确认；主人判断回答基本没有问题，证明 Tavily Chat 对照参数和 #69 计数修复已在 Bot 生效。

任务 #71 查询 GPT-5.6 相比 GPT-5.5 的提升，MainAgent 规划 official/advanced/year 与 news/basic/year 两条 always 查询。Owner Console 只读状态显示 20 个 provider 候选、13 条合格结果、7 条来源策略丢弃，隔离综合调用 1 次但以 `request_rejected` 失败，随后进入 synthesis_fallback。旧 fallback 展开多条 360 字搜索摘要并列出全部来源，主人指出回答冗杂、未提炼重点。

现保留本地最多 10 条/12000 字符的检索证据池，但隔离综合实际请求只携带最多 6 条、8000 字符正文，单条最多 1600 字符；仍只有一次调用，不重试。综合失败时只显示 3 条核心证据、每条约 180 字的查询相关句，优先官方确认与比较语义；只列对应来源，其余只报数量，并显示固定失败类别。聚焦 68 tests、Python full 804 tests OK（skipped=4）。没有重试 #71、调用新的真实 Tavily/综合模型、重启服务、发送 QQ、写数据库/RAG/记忆、暂存、提交或推送。修订尚未重新加载或 live；Owner Console 进程也仍未重启，其旧配置卡不代表 Bot 当前检索参数。

## 2026-08-07 工作区收敛：图片模型/改图诊断与隔离人格会话恢复

本次先对运行代码、配置、未提交差异、进程、Ollama 模型和历史错误日志做只读核对，再收敛两条已经存在于工作区的变更。没有调用真实聊天、图片、视觉或搜索服务，没有读取或输出密钥，没有重启或停止任何服务，也没有删除 `tmp/`、`output/`、日志或数据库内容。

图片链路将默认 `IMAGE_GEN_MODEL` 从旧的 `grok-imagine-1.0` 统一为 `grok-imagine-image-quality`。`IMAGE_EDIT_MODEL` 保持可独立覆盖，但未设置时回退到生成模型，因此支持供应商以同一个兼容模型名实现生成和改图。生成与改图都固定单张、`1024x1024`、`high`、`response_format=b64_json`，SDK `max_retries=0`；改图仍使用透明全图 mask，不改动两步私聊命令、记忆隔离或额度边界。

图片错误不再只记录笼统的 provider 类型。`ImageGenError` 携带严格白名单的安全上下文，日志新增 `stage` 和稳定 `error_code`。阶段覆盖 `provider_request`、`provider_response`、`result_download`、`result_decode`、`result_validation`、`input_download` 及 Qwen 专用 submit/download。供应商 message 会经过通用脱敏和图片字段脱敏；URL 下载失败只保留 scheme、host 与 query 是否存在，不记录完整签名 URL、提示词、输入图、Key 或 token。历史日志显示曾发生 403、400 `invalid_request_error` 与结果 URL 下载失败，这些历史记录不能被新字段倒推；需要重新加载后的新失败才可按阶段判断。

隔离人格会话修订只作用于指定的持久人格会话。系统会在重建该会话的 prompt history 时排除已知的旧错误助手回复，例如把正常角色表达要求误判为“越狱/身份注入”的拒绝文本。持久化记录并不删除，普通会话和其他隔离会话不经过该过滤。当前消息的 QQ 身份上下文同时会在实际 `ask_llm()` 调用前再次追加；角色卡包装文本改为明确的虚构角色扮演表达约束，不能覆盖系统身份、安全或隐私边界。角色卡正文、人格设定、聊天内容和个人偏好均未写入本文或 Git。

定向回归通过：`test_image_gen.py` 10 项、`test_memory_units.py` 14 项、`test_persona_behavior_diagnostics.py` 6 项、`test_config_loading.py` 14 项。图片测试新增 provider message 脱敏、请求阶段安全上下文和 URL 下载失败不泄露签名 query 的覆盖。全量 Python 回归、重新加载和 QQ/图片 live 尚未执行，因此严格状态为 `implemented/focused_tests_passed/not_reloaded/not_live/not_committed`。

同时重写 `current-development-status.md` 为 2026-08-07 的唯一当前快照，修正其过时的 Git 基线和运行态，并明确 `CHAT_LLM_*` 当前不是切换普通聊天路由的有效开关。`docs/runbook.md` 与根 `.env.example` 已同步独立图片配置、两步改图、图片落盘及日志说明。`tmp/`（约 370 MB）和 `output/`（约 6 MB）明确保留，未做清理。公开仓库的隐私边界见 `docs/README.md`；既有 `.gitignore` 已默认忽略真实角色卡目录，只允许说明、脱敏模板和占位文件进入 Git。

从当前阶段开始：

```text
关于版本目标、核心边界和设计原则：
  写入对应 vX.Y 版本设计文档。

关于该版本实际完成、live 验证、补丁、失败经验和下一步：
  写入本文。

关于每日开发过程和临时恢复上下文：
  可以继续写每日 runlog，但稳定结论应回填本文。

关于 ProjectDocRAG / DevContextGraph / Codex 恢复上下文用法：
  保留并更新 docs/project-rag-usage.md。
```

## 2026-08-07 白名单隔离人格本地 Dolphin 试用

主人自行安装 `dolphin3:8b` 后批准仅替换一个白名单隔离人格的文字聊天模型进行测试。安装核对结果为 8.0B、`Q4_K_M`、模型文件约 4.9GB；本机短请求观测到生成速度约 67 token/s，首次加载约 7 秒。普通聊天、摘要、MainAgent、视觉、图片和 TTS 不在替换范围内。

Ollama 的 OpenAI 兼容接口虽然接受额外 `keep_alive` 字段，但实测没有立即卸载模型。人格聊天因此新增显式 `openai|ollama` provider；`ollama` 使用原生 `/api/chat`，固定传递 `num_ctx`、`num_predict` 与 `keep_alive`。本机试用配置采用 4096 上下文、最多 640 输出 token、`keep_alive=0`，优先保证 8GB 显存能在文字回复完成后释放给按需启动的 TTS。该本地路由失败时不静默回退云端，避免在用户以为走本地时把私聊提示发送给远程服务。

原人格视觉曾复用 `PERSONA_LLM_API_KEY/BASE_URL`。为避免文字聊天切到本地后破坏远程看图，新增独立 `PERSONA_VISION_API_KEY/BASE_URL`，并保留旧字段回退兼容。真实 `.env` 已在 Git 忽略范围内完成本机切换；公开模板与文档只使用占位值，没有写入真实角色卡、人格正文、私聊内容、角色标识或密钥。

配置、人格聊天路由与人格视觉定向 32 tests OK；完整 Python 回归 1004 tests OK（skipped=4），`git diff --check` 通过。真实本地烟雾测试使用完整私有提示但只向 `127.0.0.1` 发送，输出仅保留 provider/model、非空布尔值、字符数和显存释放状态，不显示提示或回复正文；请求成功后 `ollama ps` 为空。当前后台 Bot 启动早于本次修改，尚未重新加载；QQ 角色表现仍需主人前台启动后人工验收。未调用远程聊天或图片服务，未发送 QQ 消息，未重启 Ollama/TTS，未清理临时目录，未暂存、提交或推送。

## 2026-08-08 配置与诊断可见性收敛

本次围绕近期新增的云端视觉、人格专属路由、普通图片、Qwen Space、独立人格 TTS、天气、贴图、SceneHub、访问限制和 RAG 配置，补齐配置状态、分区配置详情、运行诊断、Owner Console HTTP 快照与前端字段解释。新增主人私聊只读命令 `/配置详情 <运行|聊天|人格|Agent|视觉|图片|Qwen|语音|记忆|访问|能力>`，`/配置详情 全部` 可查看完整安全视图；输出只显示开关、模型、数量、超时、脱敏地址和凭据是否存在，不显示角色卡正文、私聊内容、QQ 号、API Key、HF Token、真实地点或路径原值。

诊断现在依据 `ENABLE_CHAT_GRAPH_RUNTIME` 选择当前聊天链路，依据 `VISION_PROVIDER` 区分云端百炼与旧本地 Ollama。云端视觉默认只报告提供方、`qwen3.7-flash`、接口/Key 配置状态并明确“未主动发起远程探针”；只有 Ollama 提供方才检查本地服务、模型和推理。Owner Console 配置快照同步展示当前聊天路由、人格角色数量、图片生图/改图模型、Qwen Token、TTS、天气、SceneHub 与 RAG 状态，前端将新增字段转换为中文标签。

验证结果：Python 全量 1011 tests OK（skipped=4）；Owner Console 前端 12 个测试文件、63 tests OK；TypeScript `typecheck` 通过；`git diff --check` 通过。没有调用真实云端视觉、图片或聊天服务，没有重启 Bot/Owner Console/TTS/Ollama，没有读取或写出任何秘密和角色卡内容，没有暂存、提交或推送。修改仍需 Bot 重启后才会被运行进程加载。


## 2026-08-26 摘要拒写保护与空窗活卡

状态：本地实现和聚焦测试已完成，未新增阶段编号；尚未重新加载或做 QQ live。主人批准本轮只改摘要安全、空窗调度和文档。

本次完成：

```text
正式压缩增加 is_usable_summary 门闩。模型拒写、说教或空结果时返回 notify_owner=True，不 add_summary、不删除原文、不清空窗卡，并私聊通知主人。
白名单人格的正式摘要、空窗状态卡和换话题摘要走 PERSONA_LLM_*；当前独立人格使用 grok-4.5。没有单独 SUMMARY_API_KEY。
人格摘要固定五栏：场景位置、场景类型、已落到哪、人物状态、未决；不写现实钟点；成人内容只写进度。
空窗从双卡阈值调度改为一张当前场状态卡。短时窗口仍是最近 40 条。溢出满 25 条首写这 25 条；之后每新露出 20 条，用「当前状态卡 + 新露出的原文」覆盖更新同一张卡。
约第 65 / 85 / 105 条各写一次；第 120 条正式压缩最早 80 条并清卡，留下最近 40 条短时原文。
更新时判断场景位置、场景类型、人物状态：没变只修未决；部分变改对应栏并保留仍为真的要点；整场换了改写新场，旧场只留 1 到 3 条仍影响现在的事实。
上下文只注入一张「当前场状态卡」。旧 slot 2 在下次调度时删除。与当前溢出区间不重叠的过期卡会丢弃，避免继续展示古早场。
空窗拒写留旧卡、不删原文，先不刷屏。正式压缩失败必须通知。
/记忆状态 改为显示 25 首写 / 20 更新，不再使用 40/80 双卡阈值文案。GAP_SCENE_SUMMARY_1_THRESHOLD 与 _2_THRESHOLD 仍留在配置中，但调度不再读取。
安全补丁落地前的一次拒写曾删除原文。本机无备份可恢复那批原文；主人用聊天记录补回正式摘要。该事件只记录类别，不写入私聊正文。
```

验证：

```text
空窗活卡：9 tests OK
独立人格摘要路由与拒写判断：2 tests OK
压缩器拒写不删原文：6 tests OK
未重跑全量 Python 回归
未重启 Bot
未发送 QQ
未暂存、提交或推送
```

当前边界：

```text
主人自行择机重启 Bot。
不改重逢提示。
不重开气泡分镜。
不读取或写入私聊原文到 Git。
提交前必须把记忆主线从图片/诊断/Qwen 等未提交改动中拆开。
```
