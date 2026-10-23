# B 站固定浏览器会话

同日新增 [自动浏览与分享启动入口](bilibili-autobrowse-runbook.md)，使用现有专用 Edge。
浏览器管理命令本身仍不启动自动循环；需要运行 `scripts/start-bilibili.ps1` 或独立 worker 的 run 命令。

2026-10-22 最新：固定会话已接入 `bilibili_browse.py preview`，包括候选、详情、网页原生字幕与显式私信提交。
真实单轮完成 6 条候选、2 条精选、1 条有效总结和 1 条私信，主人已确认收到，指出总结基本正确但文案过于报告化。
现已改为只发角色自然分享话语与规范视频链接；总结、字幕覆盖和引用保留在本机报告。新格式仅离线验证，未重发。
全部 B 站相关回归 130 项通过。以下登录保留和单片检查为此前独立验收记录：
19:57（Asia/Shanghai）主人扫码后账号检查为 `logged_in`，与既有默认人格绑定相符。
正常关闭后确认 `browser_running=false`，19:58 以同一资料目录新启动（`reused_process=false`），
再次检查为 HTTP 200/code=0、`logged_in`；真实登录及关闭重开保留验收通过，专用窗口保持打开。
20:03（Asia/Shanghai）对原错配样本完成一次网页原生字幕检查：player HTTP 200/code=0、CDN HTTP 200，
拿到 14 段/73 字自动字幕，aid/bvid/cid 与网页元数据及时间轴校验通过。
这是该样本在该固定会话下的读取成功，不表示所有视频或原接口线路风控已解除。

## 用途与实现

入口为 `scripts/bilibili_browser.py`，实现为 `src/bilibili_browser.py`。
程序使用独立且固定的 Edge 用户资料目录，直接保留浏览器自行维护的 Cookie、站点存储和登录状态。
正常显示窗口，由主人用默认人格独立账号扫码；后续命令通过本机 CDP 连接同一实例。
这是普通默认浏览器上下文；不创建临时隐身上下文，也不从旧接口凭据注入或导出 Cookie。
Edge 的独立资料目录及调试连接依据为 [Microsoft Edge DevTools Protocol 官方文档](https://learn.microsoft.com/en-us/microsoft-edge/devtools/protocol/)。

会话管理和 `subtitle-check` 分开执行；后者只检查指定视频，不运行候选发现或模型总结。
`bilibili_browse.py preview` 默认复用此会话；`inspect/diagnose` 仍走原接口，未迁移。
固定会话不会自动启动 QQ Bot、后台刷视频或私信分享。账号检查不读取角色卡、QQ 记忆或视频字幕。
预览需保持专用 Edge 运行，可最小化，无需手动停在某个视频页；命令只关闭自己创建的临时标签页。
接口传输在浏览器内执行带登录态的限定 fetch，Cookie 不导出到 Python，CSRF 也只在浏览器内使用。
默认只保存本机报告，只有 `preview --send-one` 才提交首条通过校验的结果，沿用主人绑定、互关检查和持久去重。

## 命令

在项目根目录执行：

```powershell
# 打开可见的默认人格专用 Edge；如果该实例已运行则复用
.\.venv\Scripts\python.exe scripts\bilibili_browser.py open

# 完成扫码后，只读请求一次 nav，核对当前登录账号与既有默认人格绑定
.\.venv\Scripts\python.exe scripts\bilibili_browser.py check

# 只查本机连接和历史检查状态，不向 B 站发账号请求
.\.venv\Scripts\python.exe scripts\bilibili_browser.py status

# 正常关闭专用实例；保留资料目录
.\.venv\Scripts\python.exe scripts\bilibili_browser.py close

# 用当前固定会话打开一个视频，检查网页原生字幕；替换为实际 BVID
.\.venv\Scripts\python.exe scripts\bilibili_browser.py subtitle-check --bvid <BVID> --page 1
```

`open` 启动命令完成后浏览器继续运行，窗口可最小化。关闭浏览器会结束本次控制连接；下次 `open` 使用同一目录。
无需一直停在登录页，但需要使用这一个专用实例。日常其他 Edge 窗口不提供本模块的登录状态。

检查状态：

| 状态 | 含义与处理 |
|---|---|
| `logged_in` | 本次账号检查与既有默认人格绑定相符；`check` 退出码为 0 |
| `login_required` | 尚未登录或登录失效；在专用窗口扫码后再检查 |
| `account_mismatch` | 登录了其他账号；切换到默认人格账号，本程序不会自动修改绑定 |
| `account_request_blocked` | 本次账号请求被拒绝；停止重复尝试，按页面提示处理 |
| `account_response_invalid` | 账号响应不符合预期；不作为登录成功 |
| `browser_unreachable` | 浏览器不可达；检查专用窗口是否关闭，必要时重开 |

除 `logged_in` 外，`check` 均返回非零退出码。`status` 的 `last_check_status` 只是历史，
`live_account_check=false`，不能当作当前在线认证。`open` 本身也不会宣布已验证身份。

## 登录保留验收

1. `open` 后由主人扫码，执行一次 `check`，要求 `logged_in`。
2. `close` 正常关闭专用实例，等本机 `status` 显示 `browser_running=false`。
3. 重新 `open`，输出应为 `reused_process=false`，随后 `check` 再次为 `logged_in`。
4. 第二次核对成功才记录真实重开保留通过；只复用同一运行实例不算重开验收。

平台可能使登录过期；若第二次要求登录，应如实记录，不能承诺永久免扫码。
登录成功不能替代字幕来源验收；单片网页字幕检查的范围见下节。

## 单片网页字幕检查

`subtitle-check` 先核对默认人格账号，再在同一持久上下文创建临时视频标签页。
网页自行生成 WBI 签名并请求 `/x/player/wbi/v2`，程序捕获这条原生响应，
不自己重签、不回退旧 player 接口。请求拦截在导航前启用，导航异步发送，避免等待被拦截的文档请求时死锁。
单次最多放行一个 player GET；拦截后续重复请求、其他 BVID、媒体下载、播放地址、历史上报及非读取方法。
注入禁止播放脚本，完成或异常后只关闭本次创建的标签页，保留专用浏览器。

网页公开元数据仅取指定视频和分 P；player 的 aid/bvid/cid 必须相符。
字幕 CDN 沿用独立无 Cookie 客户端、HTTPS 白名单、禁止重定向、2 MiB 上限及全轨时间轴校验。
只读取一个分 P、一个优先中文轨、最多 12000 字符，拒绝部分解析失败的轨，不根据标题补全字幕。
自动字幕、覆盖范围、末段时间、指纹和正文保存在仓库外私人报告中；终端只输出状态与数量。

`ok` 表示来源和既有结构校验通过；`unavailable` 表示未拿到字幕；`source_error` 表示来源或校验失败。
`ok` 不表示完成内容理解或分享审核，报告固定 `content_reviewed=false`、`share_eligible=false`。
本次 508 秒视频只有 14 段/73 字台词型自动字幕，末段到 426.7 秒；整轨读取成功不代表覆盖全部画面或战斗过程。
没有调用模型、读取 QQ 记忆或生成分享草稿。

## 资料、日志与边界

默认位于 `%LOCALAPPDATA%\AIchatbot\bilibili`，沿用仓库外的 `AIKE_BILIBILI_HOME` 设置：

- `browser-profile/`：仅默认人格使用的浏览器资料，应视为含登录凭据的私人数据，不提交或分享。
- `browser-profile-binding.json`：现有人格、角色卡键和双方账号绑定的摘要，不保存明文 UID。
- `browser-session.json`：安全检查状态；不保存昵称、响应原文或 Cookie。
- `browser-controller.lock`：操作系统文件锁，阻止多个控制命令同时操作；进程退出后释放。
- `logs/browse-*.jsonl`：复用有界脱敏日志，只记录状态、指纹及账号匹配布尔值等白名单字段。
- `diagnostics/browser-subtitle-<trace>.json`：单片字幕检查的私人元数据、校验结果及有效字幕；不保留签名 URL 或原始 player 响应。

若绑定变化，程序拒绝复用资料而不覆盖原会话；非空且未绑定的资料目录也拒绝自动接管。
浏览器资料不能放在仓库内或重定向到其他位置。调试连接限定 `127.0.0.1`，随机端口只供本机使用。
会话管理与单片检查命令不删除资料、不更改原连接器凭据、不发私信，也没有模型调用。
独立 `preview` 会调用现有默认人格模型并默认读取 QQ 记忆；其用量和显式发送范围见 [浏览说明](bilibili-browsing-runbook.md)。

## 验证范围

专项覆盖固定资料、绑定变化、损坏状态、锁冲突、调试端点限制、默认上下文、响应大小、
登录分类、日志脱敏、实例复用、关闭保留和 CLI 独立加载。
网页字幕另覆盖导航前拦截、异步导航、一次 player 限制、写入/媒体阻断、412 不重试、
身份不符先拒绝 CDN、时间轴失败清空证据、正文仅留私人报告和分享资格始终关闭。
离线测试使用合成账号与协议响应；真实扫码和重开保留结果以本节开头及版本运行日志的最新记录为准。
