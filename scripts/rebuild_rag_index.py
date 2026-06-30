from __future__ import annotations

import argparse
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


def load_ai_chat_modules() -> dict[str, object]:
    # Avoid importing src.plugins.ai_chat.__init__, which starts the bot runtime.
    ensure_package("src", REPO_ROOT / "src")
    ensure_package("src.plugins", REPO_ROOT / "src" / "plugins")
    ensure_package("src.plugins.ai_chat", AI_CHAT_ROOT)
    ensure_package("src.plugins.ai_chat.rag", AI_CHAT_ROOT / "rag")

    modules: dict[str, object] = {
        "config": load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py"),
        "database": load_module("src.plugins.ai_chat.database", AI_CHAT_ROOT / "database.py"),
        "schema": load_module("src.plugins.ai_chat.rag.schema", AI_CHAT_ROOT / "rag" / "schema.py"),
    }
    modules["documents"] = load_module(
        "src.plugins.ai_chat.rag.documents",
        AI_CHAT_ROOT / "rag" / "documents.py",
    )
    modules["embeddings"] = load_module(
        "src.plugins.ai_chat.rag.embeddings",
        AI_CHAT_ROOT / "rag" / "embeddings.py",
    )
    modules["providers"] = load_module(
        "src.plugins.ai_chat.rag.providers",
        AI_CHAT_ROOT / "rag" / "providers.py",
    )
    modules["search"] = load_module(
        "src.plugins.ai_chat.rag.search",
        AI_CHAT_ROOT / "rag" / "search.py",
    )
    modules["project_docs"] = load_module(
        "src.plugins.ai_chat.rag.project_docs",
        AI_CHAT_ROOT / "rag" / "project_docs.py",
    )
    modules["memory_sources"] = load_module(
        "src.plugins.ai_chat.rag.memory_sources",
        AI_CHAT_ROOT / "rag" / "memory_sources.py",
    )
    modules["memory_index"] = load_module(
        "src.plugins.ai_chat.rag.memory_index",
        AI_CHAT_ROOT / "rag" / "memory_index.py",
    )
    modules["project_index"] = load_module(
        "src.plugins.ai_chat.rag.project_index",
        AI_CHAT_ROOT / "rag" / "project_index.py",
    )
    return modules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild or query AIchatbot RAG indexes.")
    parser.add_argument("--project-docs", action="store_true", help="Rebuild ProjectDocRAG index.")
    parser.add_argument("--memory", action="store_true", help="Rebuild MemoryRAG index.")
    parser.add_argument("--query-project-docs", help="Query ProjectDocRAG with the provided text.")
    parser.add_argument("--query-memory", help="Query MemoryRAG with the provided text.")
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root to scan.")
    parser.add_argument("--max-chars", type=int, default=1800, help="Maximum characters per Markdown chunk.")
    parser.add_argument("--top-k", type=int, help="Retrieval top-k override.")
    parser.add_argument("--min-score", type=float, help="Retrieval minimum score override.")
    parser.add_argument("--max-context-chars", type=int, help="Retrieval context character cap override.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.project_docs and not args.memory and not args.query_project_docs and not args.query_memory:
        parser.error("choose --project-docs, --memory, --query-project-docs, or --query-memory")

    modules = load_ai_chat_modules()
    config = modules["config"].load_config()
    embedder = modules["providers"].build_embedding_provider(config)
    project_index = modules["project_index"]
    memory_index = modules["memory_index"]

    exit_code = 0
    if args.project_docs:
        stats = project_index.rebuild_project_doc_index(
            root=Path(args.root),
            embedder=embedder,
            max_chars=args.max_chars,
        )
        print("ProjectDocRAG rebuild stats:")
        for key, value in stats.as_dict().items():
            if key == "errors":
                continue
            print(f"  {key}: {value}")
        if stats.errors:
            exit_code = 1
            print("Errors:")
            for error in stats.errors:
                print(f"  - {error}")

    if args.memory:
        stats = memory_index.rebuild_memory_rag_index(
            embedder=embedder,
            include_manual_facts=config.memory_rag_include_manual_facts,
            include_manual_preferences=config.memory_rag_include_manual_preferences,
            include_session_summaries=config.memory_rag_include_session_summaries,
        )
        print("MemoryRAG rebuild stats:")
        for key, value in stats.as_dict().items():
            if key == "errors":
                continue
            print(f"  {key}: {value}")
        if stats.errors:
            exit_code = 1
            print("Errors:")
            for error in stats.errors:
                print(f"  - {error}")

    if args.query_project_docs:
        try:
            results = project_index.retrieve_project_docs(
                query=args.query_project_docs,
                embedder=embedder,
                is_owner=True,
                top_k=args.top_k or config.project_doc_rag_top_k,
                min_score=args.min_score if args.min_score is not None else config.project_doc_rag_min_score,
                max_context_chars=(
                    args.max_context_chars
                    if args.max_context_chars is not None
                    else config.project_doc_rag_max_context_chars
                ),
            )
        except modules["providers"].EmbeddingProviderError as exc:
            print(f"ProjectDocRAG query failed: {exc}")
            exit_code = 1
        else:
            print(project_index.format_project_doc_results(results))

    if args.query_memory:
        try:
            results = memory_index.retrieve_memory(
                query=args.query_memory,
                embedder=embedder,
                is_owner=True,
                top_k=args.top_k or config.memory_rag_top_k,
                min_score=args.min_score if args.min_score is not None else config.memory_rag_min_score,
                max_context_chars=(
                    args.max_context_chars
                    if args.max_context_chars is not None
                    else config.memory_rag_max_context_chars
                ),
            )
        except modules["providers"].EmbeddingProviderError as exc:
            print(f"MemoryRAG query failed: {exc}")
            exit_code = 1
        else:
            print(memory_index.format_memory_results(results))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
