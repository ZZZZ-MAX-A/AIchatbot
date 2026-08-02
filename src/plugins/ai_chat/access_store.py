import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ACCESS_STORE_PATH = PROJECT_ROOT / "data" / "access.json"
ListName = Literal["private_whitelist", "group_whitelist", "user_blacklist"]


@dataclass(frozen=True)
class AccessStore:
    private_whitelist: frozenset[str]
    group_whitelist: frozenset[str]
    user_blacklist: frozenset[str]
    revision: int = 0


EMPTY_STORE = AccessStore(
    private_whitelist=frozenset(),
    group_whitelist=frozenset(),
    user_blacklist=frozenset(),
)

_ACCESS_STORE_LOCK = RLock()


class AccessStoreError(RuntimeError):
    pass


class AccessStoreCorruptError(AccessStoreError):
    pass


class AccessStoreRevisionConflict(AccessStoreError):
    pass


def _normalize_items(value: object) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(str(item).strip() for item in value if str(item).strip())


def _store_path(path: Path | None = None) -> Path:
    return Path(path) if path is not None else ACCESS_STORE_PATH


def _parse_access_store(data: object, *, strict: bool) -> AccessStore:
    if not isinstance(data, dict):
        if strict:
            raise AccessStoreCorruptError("access store root must be an object")
        return EMPTY_STORE
    revision = data.get("revision", 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        if strict:
            raise AccessStoreCorruptError("access store revision is invalid")
        revision = 0
    if strict:
        for field_name in (
            "private_whitelist",
            "group_whitelist",
            "user_blacklist",
        ):
            field_value = data.get(field_name)
            if field_value is not None and not isinstance(field_value, list):
                raise AccessStoreCorruptError(
                    f"access store field {field_name} must be a list"
                )
    return AccessStore(
        private_whitelist=_normalize_items(data.get("private_whitelist")),
        group_whitelist=_normalize_items(data.get("group_whitelist")),
        user_blacklist=_normalize_items(data.get("user_blacklist")),
        revision=revision,
    )


def load_access_store(
    *,
    strict: bool = False,
    path: Path | None = None,
) -> AccessStore:
    store_path = _store_path(path)
    if not store_path.exists():
        return EMPTY_STORE

    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise AccessStoreCorruptError("access store cannot be read safely") from exc
        return EMPTY_STORE

    return _parse_access_store(data, strict=strict)


def save_access_store(store: AccessStore, *, path: Path | None = None) -> None:
    with _ACCESS_STORE_LOCK:
        store_path = _store_path(path)
        store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "revision": store.revision,
            "private_whitelist": sorted(store.private_whitelist),
            "group_whitelist": sorted(store.group_whitelist),
            "user_blacklist": sorted(store.user_blacklist),
        }
        temporary_path = store_path.with_name(
            f".{store_path.name}.{uuid4().hex}.tmp"
        )
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, store_path)
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def ensure_access_store() -> AccessStore:
    with _ACCESS_STORE_LOCK:
        store = load_access_store(strict=True)
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
        revision=store.revision,
    )


def _replace_list(store: AccessStore, list_name: ListName, items: frozenset[str]) -> AccessStore:
    values = {
        "private_whitelist": store.private_whitelist,
        "group_whitelist": store.group_whitelist,
        "user_blacklist": store.user_blacklist,
    }
    values[list_name] = items
    return AccessStore(**values, revision=store.revision)


def update_item(
    list_name: ListName,
    item: str,
    *,
    add: bool,
    expected_revision: int,
    path: Path | None = None,
) -> tuple[AccessStore, bool]:
    normalized = item.strip()
    if not normalized:
        raise ValueError("access item must be non-empty")
    if isinstance(expected_revision, bool) or expected_revision < 0:
        raise ValueError("access store revision must be a non-negative integer")

    with _ACCESS_STORE_LOCK:
        store = load_access_store(strict=True, path=path)
        if store.revision != expected_revision:
            raise AccessStoreRevisionConflict("access store revision changed")
        current = getattr(store, list_name)
        changed = normalized not in current if add else normalized in current
        if not changed:
            return store, False
        updated_items = current | {normalized} if add else current - {normalized}
        updated = _replace_list(store, list_name, frozenset(updated_items))
        updated = AccessStore(
            private_whitelist=updated.private_whitelist,
            group_whitelist=updated.group_whitelist,
            user_blacklist=updated.user_blacklist,
            revision=store.revision + 1,
        )
        save_access_store(updated, path=path)
        return updated, True


def add_item(list_name: ListName, item: str) -> bool:
    item = item.strip()
    if not item:
        return False
    with _ACCESS_STORE_LOCK:
        store = ensure_access_store()
        _, changed = update_item(
            list_name,
            item,
            add=True,
            expected_revision=store.revision,
        )
        return changed


def remove_item(list_name: ListName, item: str) -> bool:
    item = item.strip()
    if not item:
        return False
    with _ACCESS_STORE_LOCK:
        store = ensure_access_store()
        _, changed = update_item(
            list_name,
            item,
            add=False,
            expected_revision=store.revision,
        )
        return changed
