from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AI_CHAT_ROOT = REPO_ROOT / "src" / "plugins" / "ai_chat"


def ensure_package(name: str, path: Path) -> None:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__package__ = name
        sys.modules[name] = module
    module.__path__ = [str(path)]


def load_module(name: str, path: Path):
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__file__", None) == str(path):
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ensure_ai_chat_packages() -> None:
    install_dotenv_stub()
    # The plugin package __init__ starts NoneBot and SQLite setup, so tests load
    # only the pure contract/graph/policy modules needed for state validation.
    ensure_package("src", REPO_ROOT / "src")
    ensure_package("src.plugins", REPO_ROOT / "src" / "plugins")
    ensure_package("src.plugins.ai_chat", AI_CHAT_ROOT)


def install_dotenv_stub() -> None:
    if "dotenv" in sys.modules:
        return
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: False
    sys.modules["dotenv"] = dotenv_module


def install_openai_stub() -> None:
    if "openai" in sys.modules:
        return
    openai_module = types.ModuleType("openai")

    class AsyncOpenAI:
        pass

    openai_module.AsyncOpenAI = AsyncOpenAI
    sys.modules["openai"] = openai_module


def install_nonebot_event_stubs():
    existing = sys.modules.get("nonebot.adapters.onebot.v11")
    if (
        existing is not None
        and hasattr(existing, "MessageEvent")
        and hasattr(existing, "PrivateMessageEvent")
        and hasattr(existing, "GroupMessageEvent")
    ):
        return types.SimpleNamespace(
            MessageEvent=existing.MessageEvent,
            PrivateMessageEvent=existing.PrivateMessageEvent,
            GroupMessageEvent=existing.GroupMessageEvent,
        )

    class MessageEvent:
        def __init__(self, user_id: int | str = "", group_id: int | str | None = None):
            self.user_id = user_id
            if group_id is not None:
                self.group_id = group_id

    class PrivateMessageEvent(MessageEvent):
        pass

    class GroupMessageEvent(MessageEvent):
        pass

    nonebot_module = sys.modules.setdefault("nonebot", types.ModuleType("nonebot"))
    adapters_module = sys.modules.setdefault("nonebot.adapters", types.ModuleType("nonebot.adapters"))
    onebot_module = sys.modules.setdefault("nonebot.adapters.onebot", types.ModuleType("nonebot.adapters.onebot"))
    v11_module = types.ModuleType("nonebot.adapters.onebot.v11")
    v11_module.MessageEvent = MessageEvent
    v11_module.PrivateMessageEvent = PrivateMessageEvent
    v11_module.GroupMessageEvent = GroupMessageEvent
    sys.modules["nonebot.adapters.onebot.v11"] = v11_module
    nonebot_module.adapters = adapters_module
    adapters_module.onebot = onebot_module
    onebot_module.v11 = v11_module
    return types.SimpleNamespace(
        MessageEvent=MessageEvent,
        PrivateMessageEvent=PrivateMessageEvent,
        GroupMessageEvent=GroupMessageEvent,
    )


def load_pure_graph_modules():
    ensure_ai_chat_packages()
    ensure_package("src.plugins.ai_chat.graph", AI_CHAT_ROOT / "graph")

    modules = {
        "contracts": load_module(
            "src.plugins.ai_chat.chat_contracts",
            AI_CHAT_ROOT / "chat_contracts.py",
        ),
        "memory": load_module(
            "src.plugins.ai_chat.graph.memory",
            AI_CHAT_ROOT / "graph" / "memory.py",
        ),
        "state": load_module(
            "src.plugins.ai_chat.graph.state",
            AI_CHAT_ROOT / "graph" / "state.py",
        ),
        "vision": load_module(
            "src.plugins.ai_chat.graph.vision",
            AI_CHAT_ROOT / "graph" / "vision.py",
        ),
    }
    modules["chat"] = load_module(
        "src.plugins.ai_chat.graph.chat",
        AI_CHAT_ROOT / "graph" / "chat.py",
    )
    modules["adapters"] = load_module(
        "src.plugins.ai_chat.graph.adapters",
        AI_CHAT_ROOT / "graph" / "adapters.py",
    )
    modules["root"] = load_module(
        "src.plugins.ai_chat.graph.root",
        AI_CHAT_ROOT / "graph" / "root.py",
    )
    modules["runtime"] = load_module(
        "src.plugins.ai_chat.graph.runtime",
        AI_CHAT_ROOT / "graph" / "runtime.py",
    )
    modules["voice"] = load_module(
        "src.plugins.ai_chat.graph.voice",
        AI_CHAT_ROOT / "graph" / "voice.py",
    )
    modules["shadow"] = load_module(
        "src.plugins.ai_chat.graph.shadow",
        AI_CHAT_ROOT / "graph" / "shadow.py",
    )
    return modules


def load_pure_policy_modules():
    ensure_ai_chat_packages()
    ensure_package("src.plugins.ai_chat.policy", AI_CHAT_ROOT / "policy")

    modules = {
        "risk": load_module(
            "src.plugins.ai_chat.policy.risk",
            AI_CHAT_ROOT / "policy" / "risk.py",
        )
    }
    modules["engine"] = load_module(
        "src.plugins.ai_chat.policy.engine",
        AI_CHAT_ROOT / "policy" / "engine.py",
    )
    return modules


def load_pure_lc_modules():
    ensure_ai_chat_packages()
    ensure_package("src.plugins.ai_chat.lc", AI_CHAT_ROOT / "lc")

    modules = {
        "config": load_module(
            "src.plugins.ai_chat.config",
            AI_CHAT_ROOT / "config.py",
        )
    }
    modules["models"] = load_module(
        "src.plugins.ai_chat.lc.models",
        AI_CHAT_ROOT / "lc" / "models.py",
    )
    return modules


def load_legacy_business_modules():
    events = install_nonebot_event_stubs()
    ensure_ai_chat_packages()

    modules = {
        "config": load_module(
            "src.plugins.ai_chat.config",
            AI_CHAT_ROOT / "config.py",
        ),
        "access_store": load_module(
            "src.plugins.ai_chat.access_store",
            AI_CHAT_ROOT / "access_store.py",
        ),
        "rate_limit": load_module(
            "src.plugins.ai_chat.rate_limit",
            AI_CHAT_ROOT / "rate_limit.py",
        ),
        "reply_decider": load_module(
            "src.plugins.ai_chat.reply_decider",
            AI_CHAT_ROOT / "reply_decider.py",
        ),
        "owner_notify": load_module(
            "src.plugins.ai_chat.owner_notify",
            AI_CHAT_ROOT / "owner_notify.py",
        ),
    }
    modules["access"] = load_module(
        "src.plugins.ai_chat.access",
        AI_CHAT_ROOT / "access.py",
    )
    modules["events"] = events
    return modules


def load_legacy_media_modules():
    events = install_nonebot_event_stubs()
    ensure_ai_chat_packages()

    modules = {
        "config": load_module(
            "src.plugins.ai_chat.config",
            AI_CHAT_ROOT / "config.py",
        ),
        "vision": load_module(
            "src.plugins.ai_chat.vision",
            AI_CHAT_ROOT / "vision.py",
        ),
        "voice": load_module(
            "src.plugins.ai_chat.voice",
            AI_CHAT_ROOT / "voice.py",
        ),
        "events": events,
    }
    return modules


def load_legacy_memory_modules():
    install_openai_stub()
    ensure_ai_chat_packages()

    modules = {
        "database": load_module(
            "src.plugins.ai_chat.database",
            AI_CHAT_ROOT / "database.py",
        ),
        "summaries": load_module(
            "src.plugins.ai_chat.summaries",
            AI_CHAT_ROOT / "summaries.py",
        ),
        "manual_memory": load_module(
            "src.plugins.ai_chat.manual_memory",
            AI_CHAT_ROOT / "manual_memory.py",
        ),
        "gap_scene_summaries": load_module(
            "src.plugins.ai_chat.gap_scene_summaries",
            AI_CHAT_ROOT / "gap_scene_summaries.py",
        ),
    }
    modules["memory"] = load_module(
        "src.plugins.ai_chat.memory",
        AI_CHAT_ROOT / "memory.py",
    )
    return modules


def load_legacy_operation_modules():
    install_openai_stub()
    ensure_ai_chat_packages()

    modules = {
        "base_prompt": load_module(
            "src.plugins.ai_chat.base_prompt",
            AI_CHAT_ROOT / "base_prompt.py",
        ),
        "role_cards": load_module(
            "src.plugins.ai_chat.role_cards",
            AI_CHAT_ROOT / "role_cards.py",
        ),
        "trials": load_module(
            "src.plugins.ai_chat.trials",
            AI_CHAT_ROOT / "trials.py",
        ),
        "summaries": load_module(
            "src.plugins.ai_chat.summaries",
            AI_CHAT_ROOT / "summaries.py",
        ),
        "gap_scene_summaries": load_module(
            "src.plugins.ai_chat.gap_scene_summaries",
            AI_CHAT_ROOT / "gap_scene_summaries.py",
        ),
    }
    modules["llm"] = load_module(
        "src.plugins.ai_chat.llm",
        AI_CHAT_ROOT / "llm.py",
    )
    modules["compressor"] = load_module(
        "src.plugins.ai_chat.compressor",
        AI_CHAT_ROOT / "compressor.py",
    )
    return modules
