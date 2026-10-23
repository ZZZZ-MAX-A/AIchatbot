"""Local Bilibili history maintenance. Never sends messages or opens Bilibili."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "context-status", "import-sent", "index"))
    parser.add_argument("--query", default="", help="context-status only; empty by default, no semantic query")
    args = parser.parse_args(argv)
    try:
        from src.bilibili_connector import BindingStore, connector_home
        from src.bilibili_persona import load_persona_configuration
        from src.bilibili_history_bridge import BilibiliHistoryWriter, import_sent_reports
        config = load_persona_configuration()
        home = connector_home()
        writer = BilibiliHistoryWriter(BindingStore().load(), config)
        if args.command == "import-sent":
            result = import_sent_reports(writer, home / "previews", home / "deliveries.sqlite3")
        elif args.command == "index":
            from src.plugins.ai_chat.rag.providers import build_embedding_provider
            result = writer.store.index_pending(writer.scope, build_embedding_provider(config))
        elif args.command == "context-status":
            from types import SimpleNamespace
            from src.bilibili_memory import resolve_memory_scope, read_snapshot
            from src.plugins.ai_chat.bilibili_context import qq_bilibili_background
            qq_scope = resolve_memory_scope(writer.binding, config, ROOT)
            original = read_snapshot(qq_scope, config).records.history()
            conversation = SimpleNamespace(
                chat_type="private", configuration_error="", bot_self_id=qq_scope.qq_bot,
                persona_id=writer.binding.persona_id, role_card_key=writer.binding.role_card_key,
                runtime_session_key=qq_scope.session,
            )
            _, result = qq_bilibili_background(config, conversation=conversation, owner_id=qq_scope.qq_owner,
                                              history=original, query=args.query)
        else:
            snapshot = writer.store.snapshot(writer.scope, provider=config.memory_rag_embedding_provider,
                                             model=config.memory_rag_embedding_model)
            result = {"status": snapshot.status, "recent_rounds": len({m.round_key for m in snapshot.recent}),
                      "recent_messages": len(snapshot.recent), "indexed_messages": len(snapshot.candidates),
                      "unindexed_messages": snapshot.unindexed_messages, "recent_round_limit": 3,
                      "recall_message_limit": 5, "qq_database_written": False}
            from src.bilibili_daily_note import BilibiliDailyNoteStore
            try:
                note = BilibiliDailyNoteStore(home / "daily-note.sqlite3").read_today(writer.scope)
                result["daily_note"] = ({"status": "ready", "day": note["day"],
                                         "verified_videos": note["verified_videos"], "characters": len(note["text"])}
                                        if note else {"status": "missing_or_expired"})
            except Exception:
                result["daily_note"] = {"status": "unavailable"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result.get("failed", 0) > 0)
    except Exception:
        print("Bilibili history unavailable; verify local binding and storage. No message was sent.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
