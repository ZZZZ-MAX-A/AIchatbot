# 推送到 GitHub

远程仓库地址：

```text
https://github.com/ZZZZ-MAX-A/AIchatbot.git
```

## 前提

本机需要先安装 Git，并完成 GitHub 登录或令牌配置。

当前项目目录：

```powershell
D:\AIchatbot
```

## 首次推送

在 PowerShell 中进入项目目录：

```powershell
cd D:\AIchatbot
```

初始化 Git 仓库：

```powershell
git init
```

添加远程仓库：

```powershell
git remote add origin https://github.com/ZZZZ-MAX-A/AIchatbot.git
```

提交当前文件：

```powershell
git add .
git commit -m "Initial QQ AI chatbot workspace"
```

推送到 GitHub：

```powershell
git branch -M main
git push -u origin main
```

## 如果 origin 已经存在

如果添加远程仓库时报错，可以改用：

```powershell
git remote set-url origin https://github.com/ZZZZ-MAX-A/AIchatbot.git
```

然后重新执行：

```powershell
git push -u origin main
```

## 安全提醒

推送前确认不要提交以下内容：

- `.env`
- API Key
- QQ Token
- 真实聊天记录
- 私密日志

这些内容已经在 `.gitignore` 中默认忽略。
