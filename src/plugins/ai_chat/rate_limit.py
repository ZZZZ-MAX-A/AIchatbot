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


def check_rate_limits(limits: list[tuple[str, int]]) -> tuple[bool, int]:
    now = time.monotonic()
    max_wait = 0
    effective_limits = [(key, interval) for key, interval in limits if interval > 0]

    for key, interval_seconds in effective_limits:
        last = _last_seen.get(key)
        if last is None:
            continue
        elapsed = now - last
        if elapsed < interval_seconds:
            max_wait = max(max_wait, int(interval_seconds - elapsed), 1)

    if max_wait:
        return False, max_wait

    for key, _ in effective_limits:
        _last_seen[key] = now
    return True, 0
