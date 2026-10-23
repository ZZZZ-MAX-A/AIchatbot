from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROLE_CARD_DIR = PROJECT_ROOT / "prompts" / "persona-cards"
PRIVATE_ROLE_CARD_DIR = ROLE_CARD_DIR / "private"
PUBLIC_ROLE_CARD_DIR = ROLE_CARD_DIR / "public"
ACTIVE_ROLE_CARD_PATH = PROJECT_ROOT / "data" / "active-role-card.json"
ROLE_CARD_EXCLUDED_FILENAMES = frozenset({"readme.md"})
ROLE_CARD_EXCLUDED_STEM_SUFFIXES = (".example",)


@dataclass(frozen=True)
class RoleCard:
    key: str
    title: str
    path: Path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _title_from_content(content: str, fallback: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def _is_selectable_role_card_file(path: Path) -> bool:
    name = path.name.lower()
    stem = path.stem.lower()
    if name in ROLE_CARD_EXCLUDED_FILENAMES:
        return False
    if any(stem.endswith(suffix) for suffix in ROLE_CARD_EXCLUDED_STEM_SUFFIXES):
        return False
    return True


def list_role_cards() -> list[RoleCard]:
    cards: list[RoleCard] = []
    seen: set[str] = set()
    for directory in (PRIVATE_ROLE_CARD_DIR, ROLE_CARD_DIR, PUBLIC_ROLE_CARD_DIR):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if not _is_selectable_role_card_file(path):
                continue
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


def active_role_card() -> RoleCard | None:
    """Compatibility default-card view; never consult the old selection file."""
    from .config import load_config

    return role_card_by_key(load_config().persona_routing.legacy_role_card_key)


def role_card_by_key(key: str) -> RoleCard | None:
    """Return one exact role card without changing the global active card."""

    target = key.strip()
    if not target:
        return None
    from .persona_scope import valid_role_card_key

    if not valid_role_card_key(target):
        return None
    for directory in (PRIVATE_ROLE_CARD_DIR, ROLE_CARD_DIR, PUBLIC_ROLE_CARD_DIR):
        path = directory / f"{target}.md"
        if not path.exists():
            continue
        # A broken private override must not borrow another copy's identity.
        if not _is_selectable_role_card_file(path):
            return None
        content = _read_text(path)
        return RoleCard(target, _title_from_content(content, target), path) if content else None
    return None


def load_role_card_prompt(key: str) -> str:
    card = role_card_by_key(key)
    if card is None:
        return ""
    return _read_text(card.path)


def load_active_role_card_prompt() -> str:
    card = active_role_card()
    if card is None:
        return ""
    return _read_text(card.path)


def select_role_card(value: str) -> RoleCard | None:
    raise RuntimeError("fixed_persona_binding: runtime role-card switching is disabled")
