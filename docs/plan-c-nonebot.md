# 方案 C：NoneBot2 自研 QQ AI 机器人

## 技术路线

```text
NapCatQQ / OneBot v11
        ↓
NoneBot2
        ↓
src/plugins/ai_chat
        ↓
DeepSeek OpenAI-compatible API
```

## 你需要补的三样东西

### 1. Python 环境

当前机器暂时没有检测到 Python、pip 或 uv。

建议安装 Python 3.12 或更新版本。装好后打开新的 PowerShell，确认：

```powershell
python --version
pip --version
```

后续安装依赖：

```powershell
cd D:\AIchatbot
.\scripts\setup.ps1
```

### 2. DeepSeek API Key

不要把真实 API Key 提交到 GitHub。

在项目根目录复制 `.env.example` 为 `.env`：

```powershell
copy .env.example .env
```

然后把 `.env` 里的这一行改成你的真实 Key：

```text
OPENAI_API_KEY=你的 DeepSeek API Key
```

默认 DeepSeek 配置：

```text
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
```

### 3. NapCatQQ

NapCatQQ 负责登录 QQ，并把 QQ 消息通过 OneBot v11 转发给 NoneBot2。

详细步骤见 `docs/napcatqq-setup.md`。

第一版建议使用反向 WebSocket：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

NoneBot2 启动命令：

```powershell
python bot.py
```

NapCatQQ 中开启 OneBot v11 后，把反向 WebSocket 地址填为上面的地址。

## 第一版能力

- 私聊自动回复
- 群聊 @ 机器人触发回复
- DeepSeek / OpenAI 兼容 API
- 读取 `prompts/system.md` 作为系统提示词
- 内存短期上下文
- `/reset` 清空当前会话上下文
- `/status` 查看机器人状态
