"""Control Aike's independent Bilibili browsing worker. run --send enables private shares."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bilibili_autobrowse import AutoBrowseStore, BEIJING, BrowsePolicy, execute_browser_round, run_loop
from src.bilibili_connector import BindingStore, BilibiliConnectorError, DeliveryStore, _atomic_write, connector_home


def show(data):
    data = dict(data)
    for key in ("next_due", "last_round_at", "last_completed_at", "started_at", "stopped_at"):
        if isinstance(data.get(key), (int, float)):
            data[key] = datetime.fromtimestamp(data[key], BEIJING).isoformat(timespec="seconds")
    print(json.dumps(data, ensure_ascii=False), flush=True)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "run", "status", "stop"))
    parser.add_argument("--send", action="store_true", help="run only: enable real owner video shares, max 3/day")
    parser.add_argument("--once", action="store_true", help="run only: process at most one due round; obey quiet hours and persisted limits")
    args = parser.parse_args(argv)
    if (args.send or args.once) and args.command != "run":
        parser.error("--send / --once only apply to run")
    home = connector_home()
    policy_path = home / "autobrowse-config.json"
    try:
        if args.command == "init":
            if not policy_path.exists():
                _atomic_write(policy_path, json.dumps(asdict(BrowsePolicy()), indent=2) + "\n")
            policy = BrowsePolicy.load(policy_path)
            show({"status": "configured", "config_path": str(policy_path), "policy": asdict(policy), "daily_share_limit": 3})
            return 0
        session_path = home / "autobrowse-session.json"
        if args.command in {"status", "stop"}:
            if not session_path.is_file():
                show({"status": "not_running", "running": False, "config_path": str(policy_path)})
                return 0
            session = json.loads(session_path.read_text(encoding="utf-8"))
            if not isinstance(session, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(session.get("scope", ""))):
                raise ValueError("Invalid worker session")
            store = AutoBrowseStore(home, session["scope"])
            if args.command == "stop":
                show(store.request_stop())
                return 0
            state = store.state()
            running = store.is_running()
            show({"status": "running" if running else "not_running", "running": running,
                  **state, "today": store.today(time.time()), "config_path": str(policy_path),
                  "log_path": str(home / "autobrowse.stdout.log")})
            try:
                binding = BindingStore(home / "binding.json").load()
                show({"share_quota": DeliveryStore(home / "deliveries.sqlite3").quota_status(binding)})
            except Exception:
                show({"share_quota_status": "unavailable"})
            return 0
        from src.bilibili_memory import open_pinned_history
        from src.bilibili_persona import load_persona_configuration, persona_settings
        binding = BindingStore(home / "binding.json").load()
        config = load_persona_configuration()
        _, scope, _ = open_pinned_history(binding, config, home=home)
        policy = BrowsePolicy.load(policy_path)
        policy.validate()
        store = AutoBrowseStore(home, scope.key)
        if store.is_running():
            show({"status": "already_running"})
            return 1
        persona_settings(binding, config=config)
        DeliveryStore(home / "deliveries.sqlite3").register_reported_shares(binding, home / "previews")
        result = run_loop(store, policy, lambda fresh, seen, stop: execute_browser_round(
            binding, config, policy, send=args.send, refresh_index=fresh, seen_bvids=seen, should_stop=stop, home=home),
            send=args.send, once=args.once, emit=show)
        show(result)
        return int(result["status"] in {"error", "blocked", "delivery_failed_or_unknown"})
    except KeyboardInterrupt:
        show({"status": "interrupted"})
        return 130
    except BilibiliConnectorError as exc:
        print("自动浏览未启动或已停止：" + str(exc), file=sys.stderr)
        return 1
    except Exception:
        print("自动浏览不可用，请核对专用浏览器、绑定、角色配置与本地存储；未自动重试。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
