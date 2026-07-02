# 从 0 搭一个 QQ AI 机器人：NoneBot2 + NapCatQQ + DeepSeek 实践

> 本文基于项目 v0.4 及以前的实现记录整理，重点介绍 QQ AI 机器人的基础接入、消息链路、权限控制和本地运行维护。后续的长期记忆、人格表达、视觉识图、语音输出等能力不在本文展开。

## 摘要 / 导语

这个项目不是从零自研一个 QQ 机器人框架，而是选择了更稳妥的组合：用 NoneBot2 负责机器人框架和事件分发，用 NapCatQQ 负责 QQ 登录与 OneBot v11 协议接入，再通过 DeepSeek / OpenAI 兼容接口完成 AI 回复。项目自己的代码主要集中在业务插件里，包括私聊和群聊触发、权限控制、白名单、黑名单、冷却、消息长度限制、上下文保存和错误日志等能力。

如果你也想做一个能在 QQ 私聊和群聊里使用的 AI 机器人，这篇文章可以作为第一阶段的架构参考。

## 建议标签

`NoneBot2`、`QQ机器人`、`OneBot`、`NapCatQQ`、`Python`、`AI应用开发`、`DeepSeek`

## 为什么选择这条技术路线

QQ 机器人项目最容易踩坑的地方不是调用大模型，而是“怎么稳定收到 QQ 消息、怎么把回复发回去、怎么管理权限和故障”。所以第一版没有选择自研完整框架，而是把职责拆开：

```text
QQ
  -> NapCatQQ
  -> OneBot v11 反向 WebSocket
  -> NoneBot2
  -> 自研 ai_chat 插件
  -> DeepSeek / OpenAI-compatible API
  -> QQ 回复
```

这条链路的好处是边界清楚：

- NapCatQQ 只负责 QQ 登录、收消息、发消息。
- OneBot v11 提供机器人协议层。
- NoneBot2 负责事件分发、适配器、命令和插件机制。
- 自研插件只处理“这个项目真正关心的业务逻辑”。
- 大模型服务通过 OpenAI 兼容接口接入，后续切换模型成本较低。

## 项目入口

项目入口非常薄，核心就是初始化 NoneBot2、注册 OneBot v11 适配器、加载插件并启动：

```python
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
```

这也说明项目的底层框架是 NoneBot2，不是自研框架。自研部分主要在 `src/plugins/ai_chat` 这个插件包里。

依赖也保持得很克制：

```toml
dependencies = [
    "nonebot2[fastapi,httpx,websockets]>=2.4.0",
    "nonebot-adapter-onebot>=2.4.0",
    "openai>=1.0.0",
    "python-dotenv>=1.0.0",
]
```

## 接入 NapCatQQ

第一阶段使用 OneBot v11 反向 WebSocket。运行时先启动 NoneBot2 后端：

```powershell
cd D:\AIchatbot
.\scripts\start.ps1
```

后端启动后，NapCatQQ 侧配置 WebSocket 客户端：

```text
URL: ws://127.0.0.1:8080/onebot/v11/ws
Token: 留空，或与项目 .env 中 ONEBOT_ACCESS_TOKEN 保持一致
消息格式: Array
```

然后启动 NapCatQQ：

```powershell
cd D:\AIchatbot
.\scripts\start-napcat-shell.ps1 <机器人QQ号>
```

这里建议把 NoneBot2 后端和 NapCatQQ 分成两个 PowerShell 窗口运行。这样排查问题时可以快速判断是哪一层异常：后端没启动、QQ 掉线、WebSocket 断开，还是 AI 接口调用失败。

## 插件层负责什么

`ai_chat` 插件并不只是简单地把消息转发给大模型。它至少要完成这些工作：

```text
收到 QQ 消息
  -> 判断私聊还是群聊
  -> 判断是否应该触发 AI
  -> 检查主人、白名单、黑名单
  -> 检查消息长度和冷却
  -> 组装系统提示词和上下文
  -> 调用 DeepSeek / OpenAI 兼容接口
  -> 发送回复
  -> 写入上下文和错误日志
```

也就是说，AI 回复只是链路里的一个节点。真正决定机器人能不能长期稳定运行的，是 AI 调用前后的治理逻辑。

## v0.2：权限和安全先行

第一版跑通后，v0.2 的重点不是增加花哨能力，而是让机器人“可控”。QQ 机器人一旦进入群聊，如果没有权限边界，很容易出现误回复、刷屏、被陌生人滥用等问题。

当前权限模型分成几类：

```text
主人：BOT_OWNER_QQ
私聊白名单：PRIVATE_WHITELIST
群白名单：GROUP_WHITELIST
用户黑名单：USER_BLACKLIST
普通用户：默认受限
```

私聊规则：

```text
黑名单用户：静默
主人：允许
私聊白名单用户：允许
陌生人：默认拒绝，可配置试用次数
```

群聊规则：

```text
必须 @ 机器人
群必须在 GROUP_WHITELIST 中
黑名单用户静默
通过冷却和长度检查后才调用 AI
```

这套规则看起来朴素，但很关键。因为它把“是否调用大模型”放在权限检查之后，避免不必要的 API 消耗，也减少安全风险。

## 冷却和长度限制

v0.2 还加入了两个非常实用的保护：

```env
PRIVATE_RATE_LIMIT_SECONDS=10
GROUP_RATE_LIMIT_SECONDS=5
MAX_PRIVATE_MESSAGE_LENGTH=150
MAX_GROUP_MESSAGE_LENGTH=300
```

设计时没有选择自动截断超长消息，而是直接拒绝。原因是自动截断可能改变用户原意，尤其是把一段复杂问题截成半截后再交给 AI，很容易生成误导性回复。

冷却则按用户维度计算。这样可以限制同一个用户短时间连续触发 AI，但不会让一个人的行为影响整个群里其他人的正常使用。

## 动态名单和静态配置

权限来源分成两部分：

```text
.env 静态配置
data/access.json 动态配置
```

最终权限是两者合并：

```text
最终权限 = .env 名单 + data/access.json 名单
```

`.env` 适合保存初始配置和敏感配置，`data/access.json` 适合保存运行时通过 QQ 命令修改的白名单和黑名单。

主人可以在 QQ 内执行管理命令，例如：

```text
/启用本群
/禁用本群
/加入群白名单 群号
/移出群白名单 群号
/加入私聊白名单 QQ号
/移出私聊白名单 QQ号
/加入黑名单 QQ号
/移出黑名单 QQ号
/群白名单
/私聊白名单
/黑名单
```

这样做的好处是：日常运维不需要每次都登录服务器改 `.env`，但基础配置仍然可以通过 `.env` 固化。

## 错误日志不要泄露敏感信息

AI 调用失败时，项目会把错误追加到：

```text
logs/ai_chat_error.log
```

日志记录时间、会话类型、用户 QQ、群号、异常类型和异常消息，但不记录 API Key、Token 和完整敏感配置。

这个边界很重要。聊天机器人通常要接触真实用户消息，如果日志随意记录完整请求体、完整环境变量或密钥，后续排障会变成新的安全风险。

## 本地运行维护经验

日常运行时需要两个组件在线：

```text
NoneBot2 后端
NapCatQQ / QQ 接入端
```

如果机器人不回复，可以按这个顺序排查：

1. `.\scripts\start.ps1` 窗口是否还在运行。
2. NapCatQQ 窗口是否还在运行。
3. QQ 是否掉线。
4. 当前群是否在群白名单中。
5. 是否真正 @ 到机器人账号。
6. 用户是否在黑名单中。
7. 消息是否超过长度限制。
8. 是否触发冷却。
9. AI 接口配置是否可用。
10. `logs/ai_chat_error.log` 是否有异常。

这个排查顺序的核心思想是：先看链路，再看权限，最后看 AI。很多“机器人不回复”的问题其实和大模型无关，而是接入端断线、未进白名单或没有真正 @ 到机器人。

## 阶段总结

到 v0.2 为止，这个 QQ AI 机器人已经具备了可用的基础骨架：

- NoneBot2 负责机器人框架。
- NapCatQQ 负责 QQ 接入。
- OneBot v11 负责消息协议。
- DeepSeek / OpenAI 兼容接口负责生成回复。
- 自研插件负责业务逻辑。
- 权限、白名单、黑名单、冷却和长度限制保证基础可控。

这个阶段最重要的经验是：不要一开始就追求复杂人格、长期记忆或多模态能力。先把接入链路、权限边界、运行方式和故障排查做好，机器人后续才有稳定迭代的基础。

下一篇会继续介绍 v0.3 和 v0.4：如何用 SQLite 保存短期上下文，以及如何通过会话摘要压缩解决“越聊越长”的问题。
