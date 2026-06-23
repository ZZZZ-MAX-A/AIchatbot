import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ACCESS_STORE_PATH = PROJECT_ROOT / "data" / "access.json"
ListName = Literal["private_whitelist", "group_whitelist", "user_blacklist"]


@dataclass(frozen=True)
class AccessStore:
    private_whitelist: frozenset[str]
    group_whitelist: frozenset[str]
    user_blacklist: frozenset[str]


EMPTY_STORE = AccessStore(
    private_whitelist=frozenset(),
    group_whitelist=frozenset(),
    user_blacklist=frozenset(),
)


def _normalize_items(value: object) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(str(item).strip() for item in value if str(item).strip())


def load_access_store() -> AccessStore:
    if not ACCESS_STORE_PATH.exists():
        return EMPTY_STORE

    try:
        data = json.loads(ACCESS_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EMPTY_STORE

    if not isinstance(data, dict):
        return EMPTY_STORE

    return AccessStore(
        private_whitelist=_normalize_items(data.get("private_whitelist")),
        group_whitelist=_normalize_items(data.get("group_whitelist")),
        user_blacklist=_normalize_items(data.get("user_blacklist")),
    )


def save_access_store(store: AccessStore) -> None:
    ACCESS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "private_whitelist": sorted(store.private_whitelist),
        "group_whitelist": sorted(store.group_whitelist),
        "user_blacklist": sorted(store.user_blacklist),
    }
    ACCESS_STORE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_access_store() -> AccessStore:
    store = load_access_store()
    if not ACCESS_STORE_PATH.exists():
        save_access_store(store)
    return store


def merged_access(
    env_private_whitelist: frozenset[str],
    env_group_whitelist: frozenset[str],
    env_user_blacklist: frozenset[str],
) -> AccessStore:
    store = load_access_store()
    return AccessStore(
        private_whitelist=env_private_whitelist | store.private_whitelist,
        group_whitelist=env_group_whitelist | store.group_whitelist,
        user_blacklist=env_user_blacklist | store.user_blacklist,
    )


def _replace_list(store: AccessStore, list_name: ListName, items: frozenset[str]) -> AccessStore:
    values = {
        "private_whitelist": store.private_whitelist,
        "group_whitelist": store.group_whitelist,
        "user_blacklist": store.user_blacklist,
    }
    values[list_name] = items
    return AccessStore(**values)


def add_item(list_name: ListName, item: str) -> bool:
    item = item.strip()
    if not item:
        return False
    store = ensure_access_store()
    current = getattr(store, list_name)
    existed = item in current
    save_access_store(_replace_list(store, list_name, current | {item}))
    return not existed


def remove_item(list_name: ListName, item: str) -> bool:
    item = item.strip()
    if not item:
        return False
    store = ensure_access_store()
    current = getattr(store, list_name)
    existed = item in current
    save_access_store(_replace_list(store, list_name, current - {item}))
    return existed
