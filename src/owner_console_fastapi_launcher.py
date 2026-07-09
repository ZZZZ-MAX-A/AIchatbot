from __future__ import annotations

"""Side-effect-free launcher for the Owner Console FastAPI smoke app.

Use this module as the Uvicorn target instead of importing the ai_chat plugin
package directly:

    python -m uvicorn src.owner_console_fastapi_launcher:app --host 127.0.0.1
"""

import importlib
import sys
import types
from pathlib import Path
from typing import Any

from fastapi import FastAPI


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PLUGINS_ROOT = SRC_ROOT / "plugins"
AI_CHAT_ROOT = PLUGINS_ROOT / "ai_chat"
OWNER_CONSOLE_FASTAPI_MODULE = "src.plugins.ai_chat.owner_console_fastapi_app"


def _ensure_package_stub(
    name: str,
    path: Path,
    *,
    forbid_initialized_file: bool = False,
) -> None:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__package__ = name
        module.__path__ = [str(path)]
        sys.modules[name] = module
    else:
        if forbid_initialized_file and getattr(module, "__file__", None):
            raise RuntimeError(
                f"{name} is already initialized; use this launcher before "
                "importing the QQ plugin package"
            )
        package_path = getattr(module, "__path__", None)
        if package_path is None:
            raise RuntimeError(f"{name} is not a package")
        if str(path) not in package_path:
            package_path.append(str(path))

    parent_name, _, child_name = name.rpartition(".")
    if parent_name:
        parent = sys.modules.get(parent_name)
        if parent is not None and not hasattr(parent, child_name):
            setattr(parent, child_name, module)


def ensure_owner_console_import_boundary() -> None:
    _ensure_package_stub("src", SRC_ROOT)
    _ensure_package_stub("src.plugins", PLUGINS_ROOT)
    _ensure_package_stub(
        "src.plugins.ai_chat",
        AI_CHAT_ROOT,
        forbid_initialized_file=True,
    )


def load_owner_console_fastapi_module() -> Any:
    ensure_owner_console_import_boundary()
    return importlib.import_module(OWNER_CONSOLE_FASTAPI_MODULE)


def create_app() -> FastAPI:
    module = load_owner_console_fastapi_module()
    return module.create_owner_console_fastapi_app()


app = create_app()
