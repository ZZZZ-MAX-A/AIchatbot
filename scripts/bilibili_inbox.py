"""Start, inspect and stop Aike's owner-only Bilibili private replies."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bilibili_autobrowse import BEIJING
from src.bilibili_connector import BindingStore, _atomic_write, connector_home
from src.bilibili_inbox import InboxPolicy, InboxStore, poll_inbox, run_inbox


def show(data):
    data = dict(data)
    for key in ("next_poll", "last_poll_at", "last_reply_at", "started_at", "stopped_at", "initialized_at"):
        if isinstance(data.get(key), (int, float)):
            data[key] = datetime.fromtimestamp(data[key], BEIJING).isoformat(timespec="seconds")
    # Cursor and process identity are local metadata, never message bodies or account IDs.
    print(json.dumps(data, ensure_ascii=False), flush=True)


def start_background(home: Path, command=None):
    home.mkdir(parents=True, exist_ok=True)
    command = command or [sys.executable, "-u", str(Path(__file__).resolve()), "run"]
    with (home / "inbox.stdout.log").open("wb") as output, (home / "inbox.stderr.log").open("wb") as errors:
        # Do not inherit a launcher's captured pipes into the long-lived worker.
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
            stdout=output, stderr=errors, close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    try:
        process.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        return {"status": "started", "pid": process.pid}
    raise RuntimeError("Private reply worker exited; inspect private logs")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "baseline", "start", "run", "status", "stop"))
    parser.add_argument("--once", action="store_true", help="run only: one receive check; not a forced reply")
    args = parser.parse_args(argv)
    if args.once and args.command != "run":
        parser.error("--once only applies to run")
    home = connector_home()
    path = home / "inbox-config.json"
    try:
        if args.command == "init":
            if not path.exists():
                _atomic_write(path, json.dumps(asdict(InboxPolicy()), indent=2) + "\n")
            show({"status": "configured", "policy": asdict(InboxPolicy.load(path))})
            return 0
        if args.command in {"status", "stop"}:
            session_path = home / "inbox-session.json"
            if not session_path.is_file():
                show({"status": "not_running", "running": False})
                return 0
            session = json.loads(session_path.read_text(encoding="utf-8"))
            if not isinstance(session, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(session.get("scope", ""))):
                raise ValueError("Invalid inbox session")
            store = InboxStore(home, session["scope"])
            if args.command == "stop":
                show(store.request_stop())
                return 0
            show({**store.state(), "running": store.is_running(), "counts": store.counts()})
            return 0
        from src.bilibili_persona import load_persona_configuration, persona_settings
        from src.bilibili_memory import open_pinned_history
        binding = BindingStore(home / "binding.json").load()
        config = load_persona_configuration()
        _, scope, _ = open_pinned_history(binding, config, home=home)
        store = InboxStore(home, scope.key)
        if store.is_running():
            show({"status": "already_running"})
            return 1
        if args.command == "baseline":
            if store.state().get("initialized"):
                show({"status": "already_initialized"})
                return 0
            from src.bilibili_browser import profile_lock
            with profile_lock(store.lock_path):
                show(poll_inbox(store, binding))
            return 0
        persona_settings(binding, config=config)
        if args.command == "start":
            InboxPolicy.load(path).validate()
            show(start_background(home))
            return 0
        show(run_inbox(store, binding, config, InboxPolicy.load(path), once=args.once, emit=show))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        print("私聊回复未启动或本次检查失败，请核对专用 Edge 登录、主人绑定和本地配置；未自动重复发送。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
