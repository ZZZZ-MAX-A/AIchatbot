"""One replaceable day of subtitle-based experiences, separate from sent messages."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from .bilibili_browse import BV, validate_summary
from .bilibili_history import HistoryScope


BEIJING = timezone(timedelta(hours=8))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Daily note time must include a timezone")
    return value


def _day(now: datetime) -> str:
    return _aware(now).astimezone(BEIJING).date().isoformat()


def render_note(note: dict) -> tuple[str, int]:
    """A short reading journal assembled from already generated content and feelings."""
    def excerpt(value, limit):
        return value if len(value) <= limit else value[:limit] + "…"

    paragraphs = []
    for item in reversed(note["items"]):
        paragraph = f"了解了《{excerpt(item['title'], 40)}》（{item['bvid']}）：{excerpt(item['content'], 64)}。"
        if item["impression"]:
            paragraph += "我的感想：" + excerpt(item["impression"], 48) + "。"
        paragraph += "觉得值得分享。" if item["worth_sharing"] else "这次没有推荐分享。"
        if item["partial"]:
            paragraph += "本次字幕读取有未覆盖部分。"
        if paragraphs and len("\n".join([paragraph, *paragraphs])) > 600:
            break
        paragraphs.append(paragraph)
    return "\n".join(paragraphs), len(paragraphs)


class BilibiliDailyNoteStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def update(self, scope: HistoryScope, report: dict, *, now: datetime | None = None) -> dict:
        """Merge only verified results from today; never infer a delivery from a draft."""
        now = _aware(now or datetime.now(timezone.utc))
        day = _day(now)
        if report.get("mode") != "preview" or report.get("withdrawal_reason"):
            return {"status": "ignored", "verified_videos": 0}
        additions = {}
        for result in report.get("results", []):
            try:
                if result.get("status") not in {"summarized", "not_recommended"}:
                    continue
                bvid = result["bvid"]
                if not isinstance(bvid, str) or not BV.fullmatch(bvid):
                    continue
                reviewed = datetime.fromisoformat(result["reviewed_at"].replace("Z", "+00:00"))
                if _day(reviewed) != day or reviewed > now:
                    continue
                evidence = result["evidence"]
                pages = evidence["pages"]
                verified = {p["page"] for p in pages if p["status"] == "available" and p.get("identity_verified") is True}
                if (evidence["basis"] != "subtitles" or not evidence["segments"] or not verified
                        or any(p["status"] == "error" for p in pages)
                        or any(p.get("identity_verified") is not True for p in pages if p["status"] == "available")
                        or any(s["page"] not in verified for s in evidence["segments"])):
                    continue
                summary = validate_summary(result["summary"], evidence)
                if summary["content_alignment"] != "consistent":
                    continue
                title = result["title"]
                if not isinstance(title, str) or not title.strip():
                    continue
                additions[bvid] = {
                    "bvid": bvid, "title": title.strip()[:80],
                    "reviewed_at": reviewed.astimezone(timezone.utc).isoformat(),
                    "content": "；".join(c["text"].strip() for c in summary["claims"])[:160],
                    "impression": summary.get("viewing_impression", ""),
                    "worth_sharing": summary["worth_sharing"], "partial": evidence.get("partial") is True,
                    "basis": "verified_subtitles",
                }
            except (KeyError, TypeError, ValueError, AttributeError, RuntimeError):
                continue
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=3)) as c, c:
            c.execute("""CREATE TABLE IF NOT EXISTS daily_note (
                scope TEXT PRIMARY KEY, day TEXT NOT NULL, updated_at TEXT NOT NULL, items TEXT NOT NULL)""")
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT day,items FROM daily_note WHERE scope=?", (scope.key,)).fetchone()
            items = json.loads(row[1]) if row and row[0] == day else {}
            for bvid, item in additions.items():
                if bvid not in items or items[bvid]["reviewed_at"] <= item["reviewed_at"]:
                    items[bvid] = item
            c.execute("""INSERT INTO daily_note VALUES(?,?,?,?) ON CONFLICT(scope) DO UPDATE SET
                day=excluded.day,updated_at=excluded.updated_at,items=excluded.items""",
                (scope.key, day, now.isoformat(), json.dumps(items, ensure_ascii=False, separators=(",", ":"))))
        return {"status": "updated", "verified_videos": len(items), "accepted_results": len(additions)}

    def read_today(self, scope: HistoryScope, *, now: datetime | None = None) -> dict | None:
        """Read-only; yesterday is invisible even before the next writer replaces it."""
        if not self.path.is_file():
            return None
        now = _aware(now or datetime.now(timezone.utc))
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
            c.execute("PRAGMA query_only=ON")
            row = c.execute("SELECT day,updated_at,items FROM daily_note WHERE scope=? AND day=?",
                            (scope.key, _day(now))).fetchone()
        if not row:
            return None
        items = list(json.loads(row[2]).values())
        items.sort(key=lambda item: (item["reviewed_at"], item["bvid"]))
        note = {"day": row[0], "updated_at": row[1], "verified_videos": len(items), "items": items}
        note["text"], note["shown_videos"] = render_note(note)
        return note


class BilibiliDailyNoteWriter:
    def __init__(self, binding, config, *, root=None, home=None):
        from .bilibili_memory import open_pinned_history
        history, self.scope, _ = open_pinned_history(binding, config, root=root, home=home)
        self.store = BilibiliDailyNoteStore(history.path.with_name("daily-note.sqlite3"))

    def update(self, report: dict, *, now: datetime | None = None) -> dict:
        return self.store.update(self.scope, report, now=now)
