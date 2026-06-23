import time


_last_seen: dict[str, float] = {}
_private_trial_counts: dict[str, int] = {}


def check_rate_limit(key: str, interval_seconds: int) -> tuple[bool, int]:
    if interval_seconds <= 0:
        return True, 0

    now = time.monotonic()
    last = _last_seen.get(key)
    if last is not None:
        elapsed = now - last
        if elapsed < interval_seconds:
            return False, max(1, int(interval_seconds - elapsed))

    _last_seen[key] = now
    return True, 0


def private_trial_used(user_id: str) -> int:
    return _private_trial_counts.get(user_id, 0)


def can_use_private_trial(user_id: str, max_messages: int) -> bool:
    if max_messages <= 0:
        return False
    return private_trial_used(user_id) < max_messages


def increment_private_trial(user_id: str) -> None:
    _private_trial_counts[user_id] = private_trial_used(user_id) + 1
