# NapCatQQ 接入 NoneBot2

## 是否需要自己下载

可以自己下载，也可以让我帮你下载到本机目录。

但 QQ 登录、扫码、账号验证必须由你自己完成，不能把 QQ 密码、短信验证码或登录二维码发给别人。

当前本机已经解压到：

```text
D:\AIchatbot\tools\NapCatQQ
```

## 推荐方式

Windows 上建议优先使用 NapCat 官方 Releases 里的 Windows 包：

- `NapCat.Shell.zip`：需要本机已安装 QQ，解压后运行 `launcher.bat`。
- `NapCat.Shell.Windows.OneKey.zip`：一键包，官方说明为 Windows AMD64 使用，内置 QQ 和 NapCat。
- 当前查到的最新 Release：`v4.18.7`。
- Release 页面提示推荐 QQ `40768+` 版本，默认 WebUI 密钥是随机密码，需要从控制台查看。

官方文档：

- https://napneko.github.io/guide/boot/Shell
- https://github.com/NapNeko/NapCatQQ/releases

## 和本项目的连接方式

本项目第一版使用 OneBot v11 反向 WebSocket。

先启动 NoneBot2：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

如果 OneKey 安装器下载 QQ 失败，例如出现 `InternetOpenUrl 调用失败，错误码: 12057`，改用 Shell 版：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1
```

Shell 版会读取本机已安装 QQ 的路径。当前检测到的 QQ 路径：

```text
C:\Program Files\Tencent\QQNT\QQ.exe
```

如果本机记录了多个 QQ 账号，可以在 `.env` 中设置：

```env
NAPCAT_QQ=你的QQ号
```

也可以启动时直接指定：

```powershell
.\scripts\start-napcat-shell.ps1 你的QQ号
```

如果你已经完成 OneKey 初始化，也可以启动 OneKey 版：

第一次使用 OneKey 包时，先运行安装器：

```powershell
cd D:\AIchatbot
.\scripts\install-napcat.ps1
```

完成初始化和 QQ 登录后，再运行快速启动脚本：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat.ps1
```

然后在 NapCatQQ WebUI 中新增网络配置：

```text
类型：WebSocket 客户端 / 反向 WebSocket / ws-reverse
URL：ws://127.0.0.1:8080/onebot/v11/ws
Token：先留空
```

如果你在 NapCatQQ 中设置了 Token，则 `.env` 里也必须填相同值：

```env
ONEBOT_ACCESS_TOKEN=你的token
```

否则会出现连接失败或 403。

## 验证

连接成功后：

- 私聊机器人 QQ：应该自动回复。
- 群聊中 @ 机器人：应该触发 AI 回复。
- 发送 `/status`：查看机器人状态。
- 发送 `/reset`：清空当前会话上下文。
