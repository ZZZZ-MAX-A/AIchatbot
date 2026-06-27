import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROLE_CARD_DIR = PROJECT_ROOT / "prompts" / "persona-cards"
PRIVATE_ROLE_CARD_DIR = ROLE_CARD_DIR / "private"
PUBLIC_ROLE_CARD_DIR = ROLE_CARD_DIR / "public"
ACTIVE_ROLE_CARD_PATH = PROJECT_ROOT / "data" / "active-role-card.json"


@dataclass(frozen=True)
class RoleCard:
    key: str
    title: str
    path: Path


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _title_from_content(content: str, fallback: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def list_role_cards() -> list[RoleCard]:
    cards: list[RoleCard] = []
    seen: set[str] = set()
    for directory in (PRIVATE_ROLE_CARD_DIR, ROLE_CARD_DIR, PUBLIC_ROLE_CARD_DIR):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            content = _read_text(path)
            if not content or path.stem in seen:
                continue
            seen.add(path.stem)
            cards.append(
                RoleCard(
                    key=path.stem,
                    title=_title_from_content(content, path.stem),
                    path=path,
                )
            )
    return cards


def _load_active_key() -> str:
    if not ACTIVE_ROLE_CARD_PATH.exists():
        return ""
    try:
        data = json.loads(ACTIVE_ROLE_CARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("active", "")).strip()


def active_role_card() -> RoleCard | None:
    cards = list_role_cards()
    if not cards:
        return None

    active_key = _load_active_key()
    if active_key:
        for card in cards:
            if active_key in {card.key, card.title, str(card.path)}:
                return card

    return cards[0]


def load_active_role_card_prompt() -> str:
    card = active_role_card()
    if card is None:
        return ""
    return _read_text(card.path)


def select_role_card(value: str) -> RoleCard | None:
    target = value.strip().lower()
    if not target:
        return None

    for card in list_role_cards():
        candidates = {
            card.key.lower(),
            card.title.lower(),
            card.path.name.lower(),
            str(card.path).lower(),
        }
        if target in candidates:
            ACTIVE_ROLE_CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
            ACTIVE_ROLE_CARD_PATH.write_text(
                json.dumps({"active": card.key}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return card
    return None
