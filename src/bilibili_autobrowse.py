"""Durable random-interval browsing with bounded work and cooperative process control."""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import sqlite3
import time
import uuid

from .bilibili_browser import profile_lock
from .bilibili_connector import BilibiliConnectorError, _atomic_write


BEIJING = timezone(timedelta(hours=8))


def local_day(stamp: float) -> str:
    return datetime.fromtimestamp(stamp, BEIJING).date().isoformat()


@dataclass(frozen=True)
class BrowsePolicy:
    min_interval_minutes: int = 90
    max_interval_minutes: int = 180
    max_rounds_per_day: int = 6
    per_source: int = 3
    max_selected: int = 1
    quiet_start_hour: int = 0
    quiet_end_hour: int = 9
    error_backoff_minutes: int = 240

    def validate(self):
        if any(type(value) is not int for value in asdict(self).values()):
            raise ValueError("Browsing options must be integers")
        if not (15 <= self.min_interval_minutes <= self.max_interval_minutes <= 1440
                and 1 <= self.max_rounds_per_day <= 24 and 1 <= self.per_source <= 8
                and 1 <= self.max_selected <= 2 and 0 <= self.quiet_start_hour <= 23
                and 0 <= self.quiet_end_hour <= 23 and 60 <= self.error_backoff_minutes <= 1440):
            raise ValueError("Browsing options are outside the supported bounds")

    @classmethod
    def load(cls, path: Path):
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("Invalid browsing configuration")
        policy = cls(**data)
        policy.validate()
        return policy

    def quiet(self, now: float) -> bool:
        hour = datetime.fromtimestamp(now, BEIJING).hour
        start, end = self.quiet_start_hour, self.quiet_end_hour
        return (start <= hour < end if start < end else hour >= start or hour < end) if start != end else False

    def allowed_time(self, stamp: float, rng=None) -> float:
        if not self.quiet(stamp):
            return stamp
        rng = rng or random.SystemRandom()
        local = datetime.fromtimestamp(stamp, BEIJING)
        end = local.replace(hour=self.quiet_end_hour, minute=0, second=0, microsecond=0)
        if end <= local:
            end += timedelta(days=1)
        return end.timestamp() + rng.randint(0, 60) * 60

    def next_round(self, now: float, *, error=False, tomorrow=False, rng=None) -> float:
        rng = rng or random.SystemRandom()
        if tomorrow:
            local = datetime.fromtimestamp(now, BEIJING)
            stamp = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        else:
            delay = max(self.error_backoff_minutes, self.max_interval_minutes) if error else rng.randint(
                self.min_interval_minutes, self.max_interval_minutes)
            stamp = now + delay * 60
        return self.allowed_time(stamp, rng)


class AutoBrowseStore:
    def __init__(self, home: Path, scope: str):
        self.home, self.scope = Path(home), scope
        self.path = self.home / "autobrowse.sqlite3"
        self.lock_path = self.home / "autobrowse.lock"
        self.stop_path = self.home / "autobrowse-stop.json"
        self.session_path = self.home / "autobrowse-session.json"

    @contextmanager
    def connect(self, *, write=False):
        if write:
            self.home.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(self.path, timeout=3)
            c.executescript("""
                CREATE TABLE IF NOT EXISTS job_state(scope TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS browse_rounds(
                    id TEXT PRIMARY KEY,scope TEXT NOT NULL,day TEXT NOT NULL,started REAL NOT NULL,
                    completed REAL,status TEXT NOT NULL,model_calls INTEGER NOT NULL DEFAULT 0,
                    known_tokens INTEGER NOT NULL DEFAULT 0,unknown_usage INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS browse_day ON browse_rounds(scope,day);
                CREATE TABLE IF NOT EXISTS seen(scope TEXT NOT NULL,bvid TEXT NOT NULL,seen_at REAL NOT NULL,
                    PRIMARY KEY(scope,bvid));
            """)
        else:
            c = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
            c.execute("PRAGMA query_only=ON")
        try:
            yield c
            if write:
                c.commit()
        except BaseException:
            if write:
                c.rollback()
            raise
        finally:
            c.close()

    def state(self) -> dict:
        if not self.path.is_file():
            return {}
        with self.connect() as c:
            row = c.execute("SELECT payload FROM job_state WHERE scope=?", (self.scope,)).fetchone()
        return json.loads(row[0]) if row else {}

    def update_state(self, **values):
        with self.connect(write=True) as c:
            c.execute("BEGIN IMMEDIATE")
            self._update(c, values)

    def _update(self, c, values):
        row = c.execute("SELECT payload FROM job_state WHERE scope=?", (self.scope,)).fetchone()
        state = json.loads(row[0]) if row else {}
        state.update(values)
        c.execute("INSERT INTO job_state VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET payload=excluded.payload",
                  (self.scope, json.dumps(state, separators=(",", ":"))))

    def begin_round(self, now: float, policy: BrowsePolicy, next_due: float) -> tuple[str, int] | None:
        with self.connect(write=True) as c:
            c.execute("BEGIN IMMEDIATE")
            count = c.execute("SELECT COUNT(*) FROM browse_rounds WHERE scope=? AND day=?",
                              (self.scope, local_day(now))).fetchone()[0]
            if count >= policy.max_rounds_per_day:
                return None
            state = c.execute("SELECT payload FROM job_state WHERE scope=?", (self.scope,)).fetchone()
            fresh = int(json.loads(state[0]).get("refresh_index", 0)) + 1 if state else 1
            fresh = (fresh - 1) % 1000000 + 1
            key = uuid.uuid4().hex
            c.execute("INSERT INTO browse_rounds(id,scope,day,started,status) VALUES(?,?,?,?,'in_progress')",
                      (key, self.scope, local_day(now), now))
            self._update(c, {"phase": "browsing", "last_round_at": now, "next_due": next_due,
                             "refresh_index": fresh, "last_round_id": key})
        return key, fresh

    def finish_round(self, key: str, now: float, outcome: dict):
        usage = outcome.get("usage", [])
        known = sum(u["total_tokens"] for u in usage if type(u.get("total_tokens")) is int)
        unknown = sum(type(u.get("total_tokens")) is not int for u in usage) + int(outcome.get("cost_unknown", False))
        with self.connect(write=True) as c:
            c.execute("UPDATE browse_rounds SET completed=?,status=?,model_calls=?,known_tokens=?,unknown_usage=? WHERE id=? AND scope=?",
                      (now, outcome["status"], len(usage), known, unknown, key, self.scope))
            for bvid in outcome.get("seen_bvids", []):
                c.execute("INSERT INTO seen VALUES(?,?,?) ON CONFLICT(scope,bvid) DO UPDATE SET seen_at=excluded.seen_at",
                          (self.scope, bvid, now))
            c.execute("DELETE FROM seen WHERE scope=? AND seen_at<?", (self.scope, now - 7 * 86400))
            c.execute("DELETE FROM browse_rounds WHERE scope=? AND started<?", (self.scope, now - 30 * 86400))

    def seen(self, now: float) -> set[str]:
        if not self.path.is_file():
            return set()
        with self.connect() as c:
            return {r[0] for r in c.execute("SELECT bvid FROM seen WHERE scope=? AND seen_at>=?", (self.scope, now - 7 * 86400))}

    def today(self, now: float) -> dict:
        if not self.path.is_file():
            return {"rounds": 0, "model_calls": 0, "known_tokens": 0, "unknown_usage": 0, "unfinished_rounds": 0}
        with self.connect() as c:
            row = c.execute("SELECT COUNT(*),COALESCE(SUM(model_calls),0),COALESCE(SUM(known_tokens),0),COALESCE(SUM(unknown_usage),0),COALESCE(SUM(status='in_progress'),0) FROM browse_rounds WHERE scope=? AND day=?",
                            (self.scope, local_day(now))).fetchone()
        result = dict(zip(("rounds", "model_calls", "known_tokens", "unknown_usage", "unfinished_rounds"), row))
        result["unknown_usage"] += result["unfinished_rounds"]
        return result

    def is_running(self) -> bool:
        if not self.lock_path.is_file():
            return False
        try:
            with profile_lock(self.lock_path):
                return False
        except BilibiliConnectorError:
            return True

    def should_stop(self, run_id: str) -> bool:
        try:
            return json.loads(self.stop_path.read_text(encoding="utf-8")).get("run_id") == run_id
        except FileNotFoundError:
            return False

    def request_stop(self) -> dict:
        if not self.is_running():
            return {"status": "not_running"}
        state = self.state()
        if not state.get("run_id"):
            return {"status": "starting_retry_stop"}
        _atomic_write(self.stop_path, json.dumps({"run_id": state["run_id"]}))
        return {"status": "stop_requested", "in_flight_request_may_finish": True}


def run_loop(store: AutoBrowseStore, policy: BrowsePolicy, execute_round, *, send=False,
             once=False, clock=time.time, sleep=time.sleep, rng=None, emit=None):
    """No catch-up replay: persist work reservation and the next time before expensive work."""
    policy.validate()
    emit = emit or (lambda event: None)
    rng = rng or random.SystemRandom()
    with profile_lock(store.lock_path):
        run_id = uuid.uuid4().hex
        now = clock()
        previous = store.state()
        due = max(now, float(previous.get("next_due", now)))
        due = policy.allowed_time(due, rng)
        store.update_state(run_id=run_id, pid=os.getpid(), started_at=now, phase="waiting", send_enabled=send, next_due=due)
        _atomic_write(store.session_path, json.dumps({"scope": store.scope, "run_id": run_id, "pid": os.getpid()}))
        emit({"event": "started", "send_enabled": send, "next_due": due})
        try:
            while not store.should_stop(run_id):
                now = clock()
                state = store.state()
                due = float(state["next_due"])
                if policy.quiet(now):
                    if policy.quiet(due) or due <= now:
                        due = policy.allowed_time(max(now, due), rng)
                    if state.get("phase") != "quiet_hours" or due != state["next_due"]:
                        store.update_state(phase="quiet_hours", next_due=due)
                if now < due:
                    if once:
                        return {"status": "waiting", "next_due": due}
                    sleep(min(5, due - now))
                    continue
                reservation = store.begin_round(now, policy, policy.next_round(now, rng=rng))
                if reservation is None:
                    due = policy.next_round(now, tomorrow=True, rng=rng)
                    store.update_state(phase="daily_round_limit", next_due=due)
                    emit({"event": "daily_round_limit", "next_due": due})
                    if once:
                        return {"status": "daily_round_limit", "next_due": due}
                    continue
                key, fresh = reservation
                emit({"event": "round_started", "refresh_index": fresh})
                try:
                    result = execute_round(fresh, store.seen(now), lambda: store.should_stop(run_id))
                except Exception:
                    result = {"status": "error", "usage": [], "cost_unknown": True}
                completed = clock()
                store.finish_round(key, completed, result)
                due = policy.next_round(completed, error=result["status"] in {"error", "blocked", "delivery_failed_or_unknown"}, rng=rng)
                store.update_state(phase="waiting", last_result=result["status"], last_delivery=result.get("delivery_status", "not_sent"),
                                   last_completed_at=completed, next_due=due)
                emit({"event": "round_finished", "status": result["status"], "delivery_status": result.get("delivery_status", "not_sent"),
                      "model_calls": len(result.get("usage", [])), "next_due": due})
                if once:
                    return {"status": result["status"], "next_due": due}
        except KeyboardInterrupt:
            emit({"event": "interrupted"})
        finally:
            store.update_state(phase="stopped", stopped_at=clock())
            emit({"event": "stopped"})
    return {"status": "stopped"}


def execute_browser_round(binding, config, policy: BrowsePolicy, *, send: bool, refresh_index: int,
                          seen_bvids: set[str], should_stop, home: Path):
    """Use the established browser, persona, QQ memory, journal and delivery routes."""
    from .bilibili_browser import PersistentBrowser
    from .bilibili_browser_browse import browser_browse_client
    from .bilibili_browse import preview, save_report
    from .bilibili_connector import BindingStore
    from .bilibili_daily_note import BilibiliDailyNoteWriter
    from .bilibili_history_bridge import BilibiliHistoryWriter
    from .bilibili_memory import load_owner_memory
    from .bilibili_persona import PersonaModel, persona_settings
    from .bilibili_share import share_one
    if BindingStore(home / "binding.json").load() != binding:
        raise BilibiliConnectorError("自动浏览绑定发生变化，请停止后核对配置")
    if should_stop():
        return {"status": "cancelled", "delivery_status": "cancelled", "usage": []}
    manager = PersistentBrowser(binding, home=home)
    try:
        manager.open(wait_for_controller=True)
    except Exception:
        return {"status": "error", "delivery_status": "not_confirmed", "usage": []}
    if should_stop():
        return {"status": "cancelled", "delivery_status": "cancelled", "usage": []}
    settings = persona_settings(binding, config=config)
    memory = load_owner_memory(binding, config)
    journal = BilibiliDailyNoteWriter(binding, config, home=home)
    history = BilibiliHistoryWriter(binding, config, home=home)
    model = PersonaModel(*settings, memory=memory)
    try:
        with browser_browse_client(None, binding, manager=manager, short_locks=True) as browser:
            report = preview(browser, binding, model, per_source=policy.per_source, max_selected=policy.max_selected,
                             refresh_index=refresh_index, seen_bvids=seen_bvids)
            try:
                report["daily_note"] = journal.update(report)
            except Exception:
                report["daily_note"] = {"status": "unavailable"}
            save_report(report)
            delivery = "disabled" if not send else "no_eligible_video"
            if should_stop():
                delivery = "cancelled"
            elif policy.quiet(time.time()):
                delivery = "quiet_hours"
            elif send and report["status"] in {"ok", "partial"}:
                try:
                    report["delivery"] = share_one(browser.account_client, binding, report, dry_run=False, history_writer=history)
                    report["messages_sent"] = int(report["delivery"].get("platform_accepted") is True)
                    delivery = report["delivery"]["status"]
                except Exception:
                    report["delivery"] = {"status": "failed_or_unknown", "platform_accepted": False,
                                          "owner_received_confirmed": False}
                    delivery = "failed_or_unknown"
            save_report(report)
            blocked = any(e.get("http_status") in {412, 429} or e.get("business_code") in {-412, -352}
                          for e in browser.diagnostics.events)
            status = "blocked" if blocked else "delivery_failed_or_unknown" if delivery == "failed_or_unknown" else report["status"]
            seen = [c["bvid"] for c in report["candidates"] if c.get("decision") and (
                c["decision"]["select"] is False or any(r["bvid"] == c["bvid"] and r["status"] in {"summarized", "not_recommended"}
                                                     for r in report["results"]))]
            return {"status": status, "delivery_status": delivery, "usage": list(model.usage), "seen_bvids": seen}
    except Exception:
        return {"status": "error", "delivery_status": "not_confirmed", "usage": list(model.usage)}
    finally:
        model.close()
