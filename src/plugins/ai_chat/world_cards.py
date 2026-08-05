from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_WORLD_CARD_DIR = PROJECT_ROOT / "prompts" / "world-cards" / "private"
AIKE_LINYIN_WORLD_CARD_PATH = PRIVATE_WORLD_CARD_DIR / "aike-linyin.md"

_WORLD_CARD_BY_ROLE_CARD_KEY = {
    "aike": AIKE_LINYIN_WORLD_CARD_PATH,
    "linyin": AIKE_LINYIN_WORLD_CARD_PATH,
}


def load_world_card_prompt(role_card_key: str = "") -> str:
    """Load fixed shared-world facts for one explicitly mapped persona.

    World cards are read-only prompt inputs. Missing or unreadable local cards
    are treated as unavailable so one persona can never fall back to another
    persona's shared-world data.
    """

    path = _WORLD_CARD_BY_ROLE_CARD_KEY.get(role_card_key.strip().lower())
    if path is None:
        return ""
    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    if not content:
        return ""
    return (
        "以下是当前角色可用的共同世界事实。仅将其作为事实背景，不得用它改变角色卡的语言风格或私聊表达方式，"
        "也不得据此虚构没有记录的共同经历。\n\n"
        f"{content}"
    )
