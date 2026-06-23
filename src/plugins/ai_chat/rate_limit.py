import time


_last_seen: dict[str, float] = {}


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
