# B 站账号接入操作说明

状态：账号接入已实现并通过离线测试，主人已在 B 站私信确认收到测试回复，完成本机首次送达验收。
本文件介绍原接口凭据、主人 UID 绑定和私信入口；[单轮浏览预览](bilibili-browsing-runbook.md) 现默认使用固定浏览器登录态。
2026-10-22 固定会话已完成一次真实视频分享提交，主人确认收到；分享格式随后按主人反馈改为自然话语加链接，未重发。
固定浏览器的 [打开、扫码与账号检查入口](bilibili-browser-runbook.md) 不替换本文件 `bilibili_connect.py` 的原凭据命令。

## 当前能力与承载方式

入口为 `scripts/bilibili_connect.py`，独立模块为 `src/bilibili_connector.py`。它使用项目已有的 httpx，不启动 NoneBot、QQ 插件或聊天数据库，不需要安装 DSH。

本文件原接口线路由浏览器首次登录后手动更新 Cookie，导入成功后无需保持浏览器打开。
新的 `bilibili_browse.py preview` 默认线路在专用 Edge 内使用登录态发起限定请求，需要专用浏览器运行，可最小化。
Cookie 不导出到 Python，私信 CSRF 也仅在浏览器内读取和使用；沿用同一绑定、互关检查和持久发送库。
两种工具均按命令完成即退出，没有常驻刷视频或自动轮询。

已实现：

- 在本机终端隐藏输入 `SESSDATA`、`bili_jct` 和可选 `buvid3`，在线验证登录身份，经用户核对账号后保存。
- 固定绑定默认人格账号 UID 与主人 UID；发送前再次验证当前账号，且只允许发送给绑定主人。
- 检查互关；默认预览正文并进行只读预检，显式 `--go` 才提交私信。
- 发送文本及正文中的视频链接。当前是文本私信，不是原生视频卡片。
- 本地持久化发送状态，默认按双方 UID 和相同正文阻止重复提交。

账号连接器不负责视频处理。独立浏览入口已支持候选读取、角色卡筛选、字幕总结和本地草稿，
使用 `persona_id` / `role_card_key` 精确读取现有默认人格角色卡；账号入口本身不读取角色卡。
浏览入口已进一步支持 [QQ 主人私聊记忆与上下文组装](bilibili-memory-runbook.md)，按固定身份映射只读加载。
仍未接入：收取或自动回复主人 B 站私信、画面理解和后台自动分享。

## 首次配置

使用现有 Windows 虚拟环境，在项目根目录的本机 PowerShell 执行以下命令。不要把 Cookie 放进命令参数、聊天或截图中。

1. 在浏览器登录默认人格的独立 B 站账号，确认没有误用主人账号。让两个账号互相关注。
2. 按 F12 打开开发者工具，进入 Application（应用）→ Storage（存储）→ Cookies → `https://www.bilibili.com`。Firefox 对应“存储”工具。分别复制 Cookie 对应的 **Value 值**，不要复制整行或整个 Cookie 头。`SESSDATA` 是 HttpOnly，不能靠 `document.cookie` 读取。
3. 运行登录命令，按提示逐项粘贴。终端不显示输入内容；`buvid3` 可回车跳过。程序请求账号接口，显示昵称和 UID，核对后在本机输入 `yes` 保存。

```powershell
.\.venv\Scripts\python.exe scripts\bilibili_connect.py login
```

4. 查看默认人格 UID，再绑定双方 UID。以下尖括号是占位说明，需要替换为数字，不能原样执行。主人 UID 可从主人 B 站个人空间网址 `space.bilibili.com/<UID>` 核对；昵称不作为身份证明。

```powershell
.\.venv\Scripts\python.exe scripts\bilibili_connect.py account
.\.venv\Scripts\python.exe scripts\bilibili_connect.py bind-owner --aike-uid <默认人格UID> --owner-uid <主人UID>
.\.venv\Scripts\python.exe scripts\bilibili_connect.py status
```

绑定时会验证登录 UID 必须等于 `--aike-uid`；尚未互关时允许保存绑定，但发送入口拒绝提交。`status` 仅在身份匹配且确认互关时退出码为 0；未配置、登录失效、绑定不匹配或未互关为 2。其他错误同样为 2，中止为 130。

## 私信预检与实际发送

```powershell
# 展示目标和正文，在线检查账号及互关，不提交私信
.\.venv\Scripts\python.exe scripts\bilibili_connect.py send --text "这是一条接入测试私信"

# 确定要发送时，加 --go 实际提交
.\.venv\Scripts\python.exe scripts\bilibili_connect.py send --text "这是一条接入测试私信" --go

# 查看本地发送状态，无需访问 B 站
.\.venv\Scripts\python.exe scripts\bilibili_connect.py deliveries
```

私信可以包含视频网址；第一版保守限制正文去除首尾空白后不超过 300 字符，并要求互关。这是本程序的策略，不代表 B 站对所有账号统一采用这些限制。正文也可通过 `--text-file <本地UTF-8文件路径>` 读取，避免将私人内容放入终端命令历史；正文仍会在本机预览。

`--go` 不弹第二次确认，因为它本身就是明确的发送指令。程序不自动重试。平台 `code=0` 只表示接口报告成功，主人仍应在自己的 B 站私信会话确认实际收到。

## 发送记录与重复保护

每次实际 POST 前先在独立的本地 SQLite 记录中提交一次发送占位。该库不使用聊天数据库，不保存 Cookie、UID 原值或私信正文；保存去重摘要、请求 ID、时间戳、状态和平台业务码。

| 状态 | 含义 | 处理 |
|---|---|---|
| `pending` | 已占位，尚未记录结果；进程中断也可能停在这里 | 核对 B 站会话，不直接重发 |
| `sent` | 接口返回 `code=0` | 在主人账号确认送达 |
| `failed` | 接口明确返回非零业务码 | 修复登录或平台错误，再人工决定是否新建任务 |
| `unknown` | 超时、HTTP 异常、非 JSON 或缺少有效业务码 | 可能已经提交，核对 B 站会话 |

相同双方 UID 和正文默认只允许提交一次，以上任何状态都不会因重跑命令而自动重发。并发运行同一任务也只能有一个拿到发送占位；这不等于平台提供了严格的“恰好送达一次”保证。

如果已人工确认需要重新发送，或确实需要发送相同正文的新消息，可显式给新任务加 `--delivery-key <新的任务ID>`。相同双方 UID 与同一个任务 ID 始终去重，即使正文变化。不要在不确定是否送达时换任务 ID 反复尝试；不要删除发送库来绕过去重。未来后台分享器应为同一次分享提供稳定任务 ID。

## 存储与登录失效

默认目录是 `%LOCALAPPDATA%\AIchatbot\bilibili`，独立于仓库：

- `credentials.json`：当前 Windows 用户的 DPAPI 加密凭据，本版不提供明文回退。其他 Windows 用户或主机通常无法直接解密；同一用户下运行的程序仍可能访问凭据。
- `binding.json`：账号 UID 和人格映射标签，不包含角色卡正文。
- `device-id`：本地生成的持久设备标识。
- `deliveries.sqlite3`：上述发送状态记录。

可通过环境变量 `AIKE_BILIBILI_HOME` 改变目录；应选择仓库外的私人目录。凭据存储当前仅支持 Windows，不能把加密文件直接搬到 Linux 使用。程序不会自动导出浏览器所有 Cookie。

登录态失效时，程序报错并停止。重新在浏览器登录，再执行 `login` 和 `status`；如果账号 UID 改变，旧主人绑定不会跟着自动改写，需重新核对。退出浏览器账号、改密码或平台风控可能让 Cookie 提前失效。本程序不绕过验证，也不承诺自动续期。

## 接口依据与验证范围

账号接口为 `api.bilibili.com/x/web-interface/nav`，关系接口为 `api.bilibili.com/x/relation`，私信提交为 `api.vc.bilibili.com/web_im/v1/web_im/send_msg`。Cookie 登录、UID 绑定和文本私信的字段参考 [dsh-bili-whale](https://github.com/Alterssss/dsh-bili-whale) 的账号与私信实现；本程序独立实现，没有复用其视频浏览线路。它不是 B 站官方 OAuth 集成，接口行为及账号可用性需要实际验收。

本地测试覆盖 DPAPI 往返、Cookie 输入约束、绑定校验、默认预检无 POST、发送目标及表单、超时/格式异常、重复保护及 CLI。
单元测试的 B 站请求使用 httpx MockTransport；与单测分开的本机账号配置和测试私信已由主人实际执行并确认收到。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_bilibili_connector.py -v
```

真实验收顺序：`login` 确认身份 → `bind-owner` 绑定 → `status` 检查互关 → `send` 预检 → 由用户执行 `send --go` → 主人 B 站确认收到。
当前账号已完成上述首次验收；Cookie 失效或更换账号后需重新验证。
