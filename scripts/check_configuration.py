"""Validate a fresh process configuration without importing the Bot plugin."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_configuration_modules():
    # The normal plugin __init__ registers matchers and initializes SQLite.
    # Create package shells, as the existing offline RAG tooling does, so only
    # the configuration and pure report modules execute in this CLI process.
    for name, path in (
        ("src", PROJECT_ROOT / "src"),
        ("src.plugins", PROJECT_ROOT / "src" / "plugins"),
        ("src.plugins.ai_chat", PROJECT_ROOT / "src" / "plugins" / "ai_chat"),
    ):
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            module.__package__ = name
            sys.modules[name] = module
        module.__path__ = [str(path)]
    return (
        importlib.import_module("src.plugins.ai_chat.config"),
        importlib.import_module("src.plugins.ai_chat.configuration_report"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-chat", action="store_true", help="also reject an incomplete default chat route")
    args = parser.parse_args()
    config_module, reports = load_configuration_modules()
    try:
        config = config_module.load_config()
        report = reports.build_configuration_report(config)
        code = int(args.require_chat and (
            not report["default_chat"]["configured"] or not report["persona_bindings"]["ready"]
        ))
    except config_module.ConfigValidationError as exc:
        report = {
            "parse_ok": False,
            "issues": [vars(issue) for issue in exc.issues],
            "external_probes_executed": False,
            "database_opened": False,
        }
        code = 1
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print("Configuration syntax: " + ("OK" if report["parse_ok"] else "INVALID"))
        if report["parse_ok"]:
            print("Default chat: " + ("configured" if report["default_chat"]["configured"] else "incomplete"))
            print("Fixed persona bindings: " + ("ready" if report["persona_bindings"]["ready"] else "invalid"))
            print("Ollama required: " + str(report["ollama_required"]).lower())
        for issue in report["issues"]:
            print(f"[{issue['severity']}] {issue['key']}: {issue['message']}")
        print("No services started, network probes or database access.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
