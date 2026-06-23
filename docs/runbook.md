# 运行维护手册

这份文档用于记录 AIchatbot 的日常启动、停止、重启、权限管理和常见故障处理。

## 运行组件

机器人运行时需要两个组件同时在线：

```text
NoneBot2 后端
NapCatQQ / QQ 接入端
```

链路：

```text
QQ
  -> NapCatQQ
  -> OneBot v11 WebSocket
  -> NoneBot2
  -> DeepSeek
  -> QQ 回复
```

## 日常启动

### 1. 启动 NoneBot2 后端

打开第一个 PowerShell：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

看到以下内容表示后端启动成功：

```text
Uvicorn running on http://127.0.0.1:8080
```

这个窗口不要关闭。

### 2. 启动 NapCatQQ

打开第二个 PowerShell：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1 2700318954
```

如果需要扫码，使用手机 QQ 扫码授权。

这个窗口也不要关闭。

## 日常停止

在两个 PowerShell 窗口中分别按：

```text
Ctrl + C
```

或者直接关闭窗口。

关闭窗口后机器人会停止运行，但项目文件不会丢失。

## 日常重启

如果只是修改了机器人代码、`.env` 配置或提示词，一般只需要重启 NoneBot2 后端：

```text
关闭 .\scripts\start.ps1 窗口
重新运行 .\scripts\start.ps1
```

NapCatQQ 不一定需要重启。

如果 QQ 掉线、WebSocket 连接异常或 NapCat 状态异常，再重启 NapCatQQ：

```text
关闭 NapCat 窗口
重新运行 .\scripts\start-napcat-shell.ps1 2700318954
```

## 注意事项

启动机器人前，不建议先手动打开普通 QQ 登录机器人账号。

原因：

```text
普通 QQ 可能占用账号，导致 NapCatQQ 无法接管登录。
```

推荐习惯：

```text
不要先打开普通 QQ
直接使用 .\scripts\start-napcat-shell.ps1 2700318954 启动
```

## WebUI

NapCat WebUI 地址通常是：

```text
http://127.0.0.1:6099
```

正常日常使用不需要打开 WebUI。

只有以下情况需要进入 WebUI：

- OneBot WebSocket 连接失败
- 需要查看 NapCat 日志
- 需要修改网络配置
- 更换 QQ 账号
- NapCat 更新后配置异常

当前 OneBot v11 WebSocket 客户端配置：

```text
URL: ws://127.0.0.1:8080/onebot/v11/ws
Token: 留空
消息格式: Array
```

## 权限配置

权限来源有两部分：

```text
.env 静态配置
data/access.json 动态配置
```

最终权限是两者合并：

```text
最终权限 = .env 名单 + data/access.json 名单
```

### .env

`.env` 用于保存敏感配置和默认配置。

不要提交 `.env` 到 GitHub。

关键配置：

```env
BOT_OWNER_QQ=3313097998

PRIVATE_WHITELIST=
ALLOW_UNKNOWN_PRIVATE_CHAT=false
PRIVATE_TRIAL_MESSAGES=3
PRIVATE_RATE_LIMIT_SECONDS=10
MAX_PRIVATE_MESSAGE_LENGTH=150

GROUP_WHITELIST=
GROUP_RATE_LIMIT_SECONDS=5
MAX_GROUP_MESSAGE_LENGTH=300

USER_BLACKLIST=
```

### data/access.json

`data/access.json` 用于保存 QQ 内动态修改的白名单和黑名单。

不要提交 `data/access.json` 到 GitHub。

结构：

```json
{
  "private_whitelist": [],
  "group_whitelist": [],
  "user_blacklist": []
}
```

## QQ 管理命令

以下管理命令只有主人可以使用。

### 帮助

```text
/权限帮助
```

### 群白名单

把当前群加入白名单：

```text
/启用本群
```

把当前群移出白名单：

```text
/禁用本群
```

按群号加入：

```text
/加入群白名单 群号
```

按群号移出：

```text
/移出群白名单 群号
```

查看群白名单：

```text
/群白名单
```

### 私聊白名单

加入私聊白名单：

```text
/加入私聊白名单 QQ号
```

移出私聊白名单：

```text
/移出私聊白名单 QQ号
```

查看私聊白名单：

```text
/私聊白名单
```

### 黑名单

加入黑名单：

```text
/加入黑名单 QQ号
```

移出黑名单：

```text
/移出黑名单 QQ号
```

查看黑名单：

```text
/黑名单
```

## 普通命令

清空当前会话上下文：

```text
/重置
```

查看机器人状态：

```text
/状态
```

`/状态` 只有主人可以使用。

## 限制规则

私聊：

```text
主人可以私聊
私聊白名单用户可以私聊
普通用户默认不能私聊
私聊消息限制 150 字
普通用户私聊冷却 10 秒
主人不受冷却限制
```

群聊：

```text
只有群白名单中的群可以使用
白名单群内所有非黑名单成员可以 @机器人
群聊消息限制 300 字
普通用户群聊冷却 5 秒
主人不受冷却限制
非白名单群静默不回复
```

黑名单：

```text
私聊静默
群聊静默
管理命令不可用
```

## 常见问题

### 机器人不回复

按顺序检查：

1. `.\scripts\start.ps1` 窗口是否还在运行。
2. NapCatQQ 窗口是否还在运行。
3. QQ 是否掉线。
4. 当前群是否在群白名单中。
5. 是否真正 @ 到机器人账号。
6. 用户是否在黑名单中。
7. 消息是否超过长度限制。
8. 是否触发冷却。

### WebUI 显示无需重复登录

通常是普通 QQ 已经登录了同一个账号。

处理：

1. 关闭普通 QQ。
2. 关闭 NapCatQQ。
3. 重新运行：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1 2700318954
```

### AI 调用失败

先运行 DeepSeek 测试脚本：

```powershell
cd D:\AIchatbot
.\.venv\Scripts\python.exe scripts\test_deepseek.py
```

如果脚本返回 `OK`，说明 DeepSeek 配置可用。

如果机器人仍然失败，查看：

```text
logs/ai_chat_error.log
```

### 修改 .env 后不生效

`.env` 只在机器人启动时读取。

修改 `.env` 后需要重启 NoneBot2 后端：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

### 动态白名单不生效

确认命令是否由主人发送。

查看：

```text
/群白名单
/私聊白名单
/黑名单
```

如果 `data/access.json` 损坏，可以关闭机器人后手动修复或删除该文件，再重启机器人。

## Git 提交

查看状态：

```powershell
cd D:\AIchatbot
D:\AIchatbot\tools\PortableGit\cmd\git.exe status
```

提交：

```powershell
D:\AIchatbot\tools\PortableGit\cmd\git.exe add .
D:\AIchatbot\tools\PortableGit\cmd\git.exe commit -m "Update chatbot"
```

推送：

```powershell
D:\AIchatbot\tools\PortableGit\cmd\git.exe push
```

不要提交以下内容：

- `.env`
- `tools/`
- `.venv/`
- `data/access.json`
- `logs/`
- `__pycache__/`
- `*.egg-info/`

这些已在 `.gitignore` 中忽略。
