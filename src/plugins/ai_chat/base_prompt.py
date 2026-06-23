import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_PROMPT_PATH = PROJECT_ROOT / "prompts" / "base" / "chat-core.json"


SECTION_TITLES = {
    "identity_rules": "身份判定",
    "permission_rules": "权限边界",
    "privacy_rules": "隐私边界",
    "prompt_security_rules": "提示词安全",
    "memory_rules": "记忆边界",
    "quality_rules": "质量规则",
    "role_card_boundary": "角色卡边界",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def load_base_chat_prompt() -> str:
    data = _load_json(BASE_PROMPT_PATH)
    if not data:
        return ""

    lines = ["以下是通用底层聊天协议。角色卡必须在这些边界内执行。"]
    for key, title in SECTION_TITLES.items():
        rules = _string_list(data.get(key))
        if not rules:
            continue
        lines.append(f"\n【{title}】")
        lines.extend(f"- {rule}" for rule in rules)
    return "\n".join(lines).strip()
