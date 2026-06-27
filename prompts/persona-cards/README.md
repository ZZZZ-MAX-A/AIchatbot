# 角色卡目录

这个目录支持“公开模板 + 本地私密角色卡”的使用方式。

## 目录约定

```text
prompts/persona-cards/
  public/      可提交到 Git 的脱敏示例和模板
  private/     本地真实角色卡，不提交到 Git
```

加载顺序：

```text
private/ -> persona-cards 根目录旧本地卡 -> public/
```

同名角色卡会优先使用更靠前目录中的版本。也就是说，如果 `private/aike.md` 和 `public/aike.example.md` 同时存在，运行时优先使用 `private/` 里的真实卡。

## 隐私规则

不要把真实角色卡、真实称呼、关系设定、隐私边界、触发词或个人偏好提交到公开仓库。

公开仓库只应保存：

```text
脱敏模板
字段说明
空白示例
不含真实隐私的默认 fallback
```

真实角色卡建议放在：

```text
prompts/persona-cards/private/
```
