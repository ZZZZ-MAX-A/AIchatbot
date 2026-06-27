from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "chatbot.db"

PATTERNS = (
    "%日语%",
    "%日文%",
    "%日本語%",
    "%中文释义%",
    "%中文翻译%",
    "%あ%",
    "%い%",
    "%う%",
    "%え%",
    "%お%",
    "%か%",
    "%き%",
    "%く%",
    "%け%",
    "%こ%",
    "%さ%",
    "%し%",
    "%す%",
    "%せ%",
    "%そ%",
    "%た%",
    "%ち%",
    "%つ%",
    "%て%",
    "%と%",
    "%な%",
    "%に%",
    "%ぬ%",
    "%ね%",
    "%の%",
    "%は%",
    "%ひ%",
    "%ふ%",
    "%へ%",
    "%ほ%",
    "%ま%",
    "%み%",
    "%む%",
    "%め%",
    "%も%",
    "%や%",
    "%ゆ%",
    "%よ%",
    "%ら%",
    "%り%",
    "%る%",
    "%れ%",
    "%ろ%",
    "%わ%",
    "%を%",
    "%ん%",
    "%ア%",
    "%イ%",
    "%ウ%",
    "%エ%",
    "%オ%",
)


TARGETS = (
    ("messages", "content"),
    ("session_summaries", "summary"),
    ("gap_scene_summaries", "summary"),
)


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def matching_ids(connection: sqlite3.Connection, table: str, column: str) -> list[int]:
    conditions = " OR ".join(f"{column} LIKE ?" for _ in PATTERNS)
    rows = connection.execute(
        f"SELECT id FROM {table} WHERE {conditions}",
        PATTERNS,
    ).fetchall()
    return [int(row[0]) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Find or delete old Japanese TTS test contamination from chatbot.db.")
    parser.add_argument("--db", type=Path, default=DATABASE_PATH, help="SQLite database path.")
    parser.add_argument("--apply", action="store_true", help="Delete matching rows. Without this flag, only report counts.")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"database not found: {args.db}")
        return 1

    try:
        with sqlite3.connect(args.db) as connection:
            total = 0
            for table, column in TARGETS:
                if not table_exists(connection, table):
                    continue
                ids = matching_ids(connection, table, column)
                total += len(ids)
                print(f"{table}: {len(ids)} matching rows")
                if args.apply and ids:
                    placeholders = ",".join("?" for _ in ids)
                    connection.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
            if args.apply:
                connection.commit()
                print(f"deleted matching rows: {total}")
            else:
                print("dry run only; rerun with --apply to delete matching rows")
    except sqlite3.Error as exc:
        print(f"database error: {exc}")
        print("close the running bot or any process using data/chatbot.db, then rerun this script")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
