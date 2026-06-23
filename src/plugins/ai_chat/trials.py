from .database import connect, ensure_database, utc_now


def private_trial_used(user_id: str) -> int:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT used_count FROM private_trials WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["used_count"]) if row else 0


def can_use_private_trial(user_id: str, max_messages: int) -> bool:
    if max_messages <= 0:
        return False
    return private_trial_used(user_id) < max_messages


def increment_private_trial(user_id: str) -> None:
    ensure_database()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO private_trials (user_id, used_count, updated_at)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                used_count = used_count + 1,
                updated_at = excluded.updated_at
            """,
            (user_id, utc_now()),
        )


def trial_stats() -> dict[str, int]:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS trial_user_count,
                COALESCE(SUM(used_count), 0) AS trial_message_count
            FROM private_trials
            """
        ).fetchone()
    return {
        "trial_user_count": int(row["trial_user_count"]),
        "trial_message_count": int(row["trial_message_count"]),
    }
