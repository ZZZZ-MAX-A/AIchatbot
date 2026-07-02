# 给 QQ AI 机器人加记忆：SQLite 上下文与会话摘要压缩设计

> 本文基于项目 v0.3 和 v0.4 的实现记录整理，重点介绍 QQ AI 机器人的短期记忆、SQLite 持久化和会话摘要压缩。这里的“记忆”不是让机器人无限保存一切，而是在可控范围内保留对当前对话有帮助的信息。

## 摘要 / 导语

一个 AI 机器人刚跑通时，最容易想到的上下文方案是把最近几轮对话存在内存里。但只靠内存有两个问题：机器人重启后上下文丢失，陌生人试用次数也会被重置。v0.3 先把短期上下文和私聊试用次数迁移到 SQLite；v0.4 再增加会话摘要压缩，把旧消息压成摘要，避免数据库和模型上下文无限增长。

这篇文章介绍一个适合本地 QQ AI 机器人的轻量记忆架构：短期原文用于接住最近对话，会话摘要用于保留较早内容的大意，长期记忆和语义索引先预留结构，后续再逐步启用。

## 建议标签

`SQLite`、`AI应用开发`、`QQ机器人`、`NoneBot2`、`上下文管理`、`大模型应用`、`Python`

## 为什么不能只用内存上下文

第一版机器人只要能接住最近几轮对话，看起来就已经够用。但实际运行后会遇到几个问题：

- 重启 NoneBot2 后端后，刚才的上下文全部消失。
- 陌生人私聊试用次数如果存在内存里，重启后会被清零。
- 群聊和私聊同时使用时，需要稳定区分不同会话。
- 聊天越久，直接把所有历史都塞给模型会越来越贵，也越来越容易干扰当前回复。

所以 v0.3 的目标很明确：先把轻量但关键的状态落到本地数据库里。

## 为什么选择 SQLite

数据库文件放在：

```text
data/chatbot.db
```

选择 SQLite 的原因很实际：

- 不需要额外安装数据库服务。
- Python 标准库自带 `sqlite3`。
- 对单机 QQ 机器人这种轻量场景足够稳定。
- 数据库文件可以放在 `data/` 目录，并通过 `.gitignore` 忽略。
- 本地排障和备份都比较简单。

这个阶段没有选择 MySQL、MongoDB 或向量数据库。不是它们不好，而是当前问题还没有复杂到需要引入独立服务。对本地机器人来说，少一个运行组件就少一类故障。

## v0.3：分层记忆架构

v0.3 设计了三层记忆：

```text
第一层：短期对话缓存
第二层：长期记忆归档
第三层：语义索引
```

第一层在 v0.3 启用，用来保存最近若干条 user / assistant 消息。

第二层和第三层先预留表结构，暂不自动启用。这样做的目的是让数据库结构从一开始就能支撑后续升级，但不会影响当前版本的稳定性。

短期上下文的会话标识设计得很简单：

```text
私聊：private:QQ号
群聊：group:群号
```

这样可以保证每个私聊用户、每个群聊都有独立上下文。

## messages 表：保存短期原文

核心表是 `messages`：

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT NOT NULL,
    message_type TEXT NOT NULL,
    user_id TEXT NOT NULL,
    group_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

几个关键字段：

- `session_key`：当前会话标识。
- `message_type`：`private` 或 `group`。
- `user_id`：发送消息的 QQ 号。
- `group_id`：群聊时保存群号。
- `role`：`user` 或 `assistant`。
- `content`：消息正文。
- `created_at`：写入时间。

调用 AI 时不会读取全部消息，而是只读取当前会话最近的若干条：

```sql
SELECT role, content
FROM messages
WHERE session_key = ?
ORDER BY id DESC
LIMIT ?
```

读取后再按旧到新顺序交给模型。这样既能保存较多历史，也能控制每次请求的上下文长度。

## private_trials 表：保存陌生人试用次数

v0.2 已经引入了陌生人私聊试用，但如果试用次数只放在内存里，重启后就会失效。v0.3 把它迁移到 SQLite：

```sql
CREATE TABLE private_trials (
    user_id TEXT PRIMARY KEY,
    used_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
```

这张表很小，但对权限系统很关键。它让“陌生人最多试用几次”这个规则不会因为重启而被绕过。

## 先预留长期记忆和语义索引

v0.3 还预留了 `long_term_memories` 和 `memory_embeddings`：

```sql
CREATE TABLE long_term_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_session_key TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

```sql
CREATE TABLE memory_embeddings (
    memory_id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES long_term_memories(id)
        ON DELETE CASCADE
);
```

不过在 v0.4 及以前，重点仍然是短期上下文和会话摘要。长期记忆和语义检索只是提前留好升级空间。

## v0.4：为什么需要会话摘要压缩

有了 SQLite 之后，新的问题出现了：原始消息会不断增长。

如果完全不处理，会带来三个影响：

- `messages` 表越来越大。
- 旧消息过多会干扰当前回复。
- 后续如果要提取长期记忆，不能把大量寒暄、重复和无效内容都带进去。

所以 v0.4 在短期记忆之上增加一层“会话摘要”：

```text
第一层：短期原文
第二层：会话摘要
第三层：长期记忆
第四层：语义索引
```

短期原文负责“接住刚刚说的话”，会话摘要负责“记住较早一段聊天的大意”。

## session_summaries 表

v0.4 新增 `session_summaries` 表：

```sql
CREATE TABLE session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT NOT NULL,
    message_type TEXT NOT NULL,
    user_id TEXT,
    group_id TEXT,
    summary TEXT NOT NULL,
    message_start_id INTEGER NOT NULL,
    message_end_id INTEGER NOT NULL,
    source_message_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

这张表记录一段旧消息被压缩后的摘要，以及摘要覆盖的消息范围：

- `summary`：压缩后的中文摘要。
- `message_start_id`：被摘要的第一条消息 ID。
- `message_end_id`：被摘要的最后一条消息 ID。
- `source_message_count`：这条摘要覆盖了多少条原始消息。

这样后续排查时可以知道某条摘要从哪里来，而不是凭空出现的一段文本。

## 压缩配置

v0.4 使用几项配置控制压缩行为：

```env
MAX_CONTEXT_MESSAGES=20
MAX_STORED_MESSAGES_PER_SESSION=200
SUMMARY_KEEP_RECENT_MESSAGES=80
SUMMARY_BATCH_MESSAGES=120
MAX_SESSION_SUMMARIES_IN_CONTEXT=3
ENABLE_MEMORY_COMPRESSION=true
```

推荐理解方式：

```text
每次回复只带最近 20 条原文
每个会话最多保留 200 条原文
压缩时保留最近 80 条原文不动
每次把较旧的 120 条压成 1 条摘要
每次最多带入最近 3 条摘要
```

压缩不是每次都发生。只有 AI 成功回复并写入数据库后，系统才检查当前会话的消息数量。如果超过阈值，再压缩最旧的一批消息。

## 压缩示例

假设当前配置是：

```text
MAX_STORED_MESSAGES_PER_SESSION=200
SUMMARY_KEEP_RECENT_MESSAGES=80
SUMMARY_BATCH_MESSAGES=120
```

某个会话现在有 230 条原文。处理方式是：

```text
取最旧的 120 条消息
生成 1 条摘要
写入 session_summaries
删除这 120 条原文
保留最近 110 条原文
```

这样数据库不会无限积累原文，同时当前对话的近期内容仍然完整保留。

## 摘要不是复述

摘要生成最重要的边界是：它不是把旧聊天换一种方式复述一遍。

摘要应该保留：

- 已确认的事实。
- 正在进行的任务。
- 未完成事项。
- 重要决定。
- 群聊主题。
- 对后续对话有帮助的信息。

摘要不应该保留：

- 无意义寒暄。
- 重复催促。
- 临时情绪。
- API Key、Token、二维码、密码。
- 过长原文复述。
- 用户没有明确表达过的动机和想法。

项目中建议的摘要提示词大致是：

```text
你是聊天记录压缩器。请把下面一段 QQ 聊天压缩成简洁摘要，只保留对后续对话有帮助的信息。
不要编造，不要记录无意义寒暄，不要保存隐私敏感内容。
重点保留：已确认的事实、正在进行的任务、未完成事项、重要决定、群聊主题。
输出 200 字以内中文摘要。
```

这个提示词的重点不是“写得像人”，而是“客观、短、可用、不编造”。

## 上下文如何组装

v0.4 后，调用 AI 时的上下文可以按这个顺序组装：

```text
系统提示词
  + 当前会话最近的会话摘要
  + 最近 MAX_CONTEXT_MESSAGES 条短期原文
  + 用户本次消息
```

摘要最多带入最近几条，而不是全部带入。因为摘要也是上下文，也会占用模型输入空间。如果摘要过多，同样会干扰当前对话。

这里也要注意：会话摘要不等于长期记忆。

```text
会话摘要回答：这段聊天之前说了什么？
长期记忆回答：这个人、这个群有什么稳定特点？
```

在 v0.4 阶段，摘要只是压缩聊天记录，不负责给用户贴标签，也不负责推断用户性格。

## QQ 内管理命令

为了方便运行中观察和干预，v0.4 增加了摘要相关命令：

```text
/摘要状态
/查看摘要
/压缩当前会话
/清空当前摘要
/清空全部摘要
```

这些命令只允许主人使用。

这样设计是因为摘要会影响后续上下文。如果普通用户可以清空或触发压缩，就可能影响机器人在当前会话中的记忆行为。

## 隐私和数据边界

SQLite 数据库会保存真实聊天内容和摘要，所以必须确保：

```text
data/chatbot.db
```

不会被提交到 GitHub。

摘要虽然比原文短，但仍然可能包含真实聊天信息，因此也要按敏感数据处理。项目中继续把 `data/` 加入 `.gitignore`，并在摘要生成时要求过滤 API Key、Token、二维码、账号密码、身份证、手机号等敏感信息。

## 测试重点

v0.3 和 v0.4 的测试不应该只测“能不能回复”，还要覆盖记忆边界：

1. 私聊连续对话，确认上下文正常。
2. 群聊 @ 机器人连续对话，确认上下文正常。
3. 重启 NoneBot2 后端，确认近期上下文仍然存在。
4. 使用 `/重置`，确认只清空当前会话原文。
5. 陌生人试用次数达到上限后，重启仍然保持上限。
6. 人工构造超过阈值的消息，确认能生成摘要。
7. 压缩后旧原文被删除，最近原文被保留。
8. `/查看摘要` 能看到当前会话摘要。
9. 摘要能参与后续 AI 回复。
10. 非主人执行摘要管理命令会被拒绝。

这些测试能验证一个核心结论：记忆功能不仅要“能保存”，还要“保存得有边界、可清理、可观察”。

## 阶段总结

到 v0.4 为止，这个 QQ AI 机器人的记忆系统已经形成了一个轻量但可扩展的基础：

- v0.3 用 SQLite 保存短期上下文和陌生人私聊试用次数。
- 每个私聊用户和每个群聊都有独立 `session_key`。
- 调用 AI 时只读取最近若干条原文，避免无限上下文。
- v0.4 用 `session_summaries` 压缩旧消息。
- 摘要参与上下文组装，但不替代短期原文。
- 长期记忆和语义索引先预留结构，后续再逐步启用。

这套方案的关键取舍是：不要让机器人“什么都记住”。对一个本地 QQ AI 机器人来说，更可靠的做法是只保存必要上下文，定期压缩旧内容，并把权限、隐私和清理能力放在设计里。

记忆不是越多越好。可控、可解释、可删除，才是聊天机器人能长期运行的前提。
