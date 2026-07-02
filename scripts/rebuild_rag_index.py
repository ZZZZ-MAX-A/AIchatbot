from __future__ import annotations

import argparse
import asyncio
import base64
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
    ensure_package("src.plugins.ai_chat.graph", AI_CHAT_ROOT / "graph")
    ensure_package("src.plugins.ai_chat.policy", AI_CHAT_ROOT / "policy")
    ensure_package("src.plugins.ai_chat.lc", AI_CHAT_ROOT / "lc")

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
    modules["combined"] = load_module(
        "src.plugins.ai_chat.rag.combined",
        AI_CHAT_ROOT / "rag" / "combined.py",
    )
    modules["dev_context"] = load_module(
        "src.plugins.ai_chat.graph.dev_context",
        AI_CHAT_ROOT / "graph" / "dev_context.py",
    )
    modules["main_agent"] = load_module(
        "src.plugins.ai_chat.graph.main_agent",
        AI_CHAT_ROOT / "graph" / "main_agent.py",
    )
    modules["risk"] = load_module(
        "src.plugins.ai_chat.policy.risk",
        AI_CHAT_ROOT / "policy" / "risk.py",
    )
    modules["policy_engine"] = load_module(
        "src.plugins.ai_chat.policy.engine",
        AI_CHAT_ROOT / "policy" / "engine.py",
    )
    modules["main_agent_llm"] = load_module(
        "src.plugins.ai_chat.graph.main_agent_llm",
        AI_CHAT_ROOT / "graph" / "main_agent_llm.py",
    )
    modules["main_agent_bridge"] = load_module(
        "src.plugins.ai_chat.graph.main_agent_bridge",
        AI_CHAT_ROOT / "graph" / "main_agent_bridge.py",
    )
    modules["lc_models"] = load_module(
        "src.plugins.ai_chat.lc.models",
        AI_CHAT_ROOT / "lc" / "models.py",
    )
    modules["lc_main_agent"] = load_module(
        "src.plugins.ai_chat.lc.main_agent",
        AI_CHAT_ROOT / "lc" / "main_agent.py",
    )
    return modules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild or query AIchatbot RAG indexes.")
    parser.add_argument("--project-docs", action="store_true", help="Rebuild ProjectDocRAG index.")
    parser.add_argument("--memory", action="store_true", help="Rebuild MemoryRAG index.")
    parser.add_argument("--query-project-docs", help="Query ProjectDocRAG with the provided text.")
    parser.add_argument("--query-memory", help="Query MemoryRAG with the provided text.")
    parser.add_argument("--query-combined", help="Query ProjectDocRAG and MemoryRAG together for dev-side context.")
    parser.add_argument("--query-dev-context", help="Build dev-side context through the DevContextGraph boundary.")
    parser.add_argument("--query-main-agent", help="Run MainAgentGraph with the read-only dev_context tool.")
    parser.add_argument(
        "--main-agent-use-llm",
        action="store_true",
        help="Use the configured Main LLM for --query-main-agent instead of the safe dev_context stub.",
    )
    parser.add_argument(
        "--main-agent-action-json",
        help="Inject raw ActionRequest JSON for --query-main-agent local testing.",
    )
    parser.add_argument(
        "--main-agent-action-json-base64",
        help="Inject base64-encoded ActionRequest JSON for shell-safe local testing.",
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root to scan.")
    parser.add_argument("--max-chars", type=int, default=1800, help="Maximum characters per Markdown chunk.")
    parser.add_argument("--top-k", type=int, help="Retrieval top-k override.")
    parser.add_argument("--min-score", type=float, help="Retrieval minimum score override.")
    parser.add_argument("--max-context-chars", type=int, help="Retrieval context character cap override.")
    return parser


PROJECT_DOC_REBUILD_LABELS = {
    "scanned_files": "扫描文件",
    "chunks_seen": "扫描片段",
    "created_documents": "新增文档",
    "updated_documents": "更新文档",
    "reactivated_documents": "恢复文档",
    "unchanged_documents": "未变化文档",
    "embeddings_created": "新增向量",
    "embeddings_updated": "更新向量",
    "embeddings_skipped": "跳过向量",
    "soft_deleted_documents": "软删除过期文档",
}
MEMORY_REBUILD_LABELS = {
    "scanned_manual_memories": "扫描长期记忆",
    "scanned_session_summaries": "扫描会话摘要",
    "created_documents": "新增文档",
    "updated_documents": "更新文档",
    "reactivated_documents": "恢复文档",
    "unchanged_documents": "未变化文档",
    "embeddings_created": "新增向量",
    "embeddings_updated": "更新向量",
    "embeddings_skipped": "跳过向量",
    "soft_deleted_documents": "软删除过期文档",
}


def print_stats(title: str, stats: object, labels: dict[str, str]) -> int:
    data = stats.as_dict()
    print(title)
    for key, label in labels.items():
        print(f"  {label}: {data.get(key, 0)}")
    errors = data.get("errors") or []
    if errors:
        print("错误:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("错误: 无")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if (
        not args.project_docs
        and not args.memory
        and not args.query_project_docs
        and not args.query_memory
        and not args.query_combined
        and not args.query_dev_context
        and not args.query_main_agent
    ):
        parser.error(
            "choose --project-docs, --memory, --query-project-docs, "
            "--query-memory, --query-combined, --query-dev-context, or --query-main-agent"
        )
    injected_action_count = sum(
        1
        for value in (
            args.main_agent_use_llm,
            bool(args.main_agent_action_json),
            bool(args.main_agent_action_json_base64),
        )
        if value
    )
    if injected_action_count > 1:
        parser.error(
            "--main-agent-use-llm, --main-agent-action-json, and "
            "--main-agent-action-json-base64 are mutually exclusive"
        )
    if injected_action_count and not args.query_main_agent:
        parser.error(
            "--main-agent-use-llm, --main-agent-action-json, and "
            "--main-agent-action-json-base64 require --query-main-agent"
        )

    modules = load_ai_chat_modules()
    config = modules["config"].load_config()
    embedder = modules["providers"].build_embedding_provider(config)
    project_index = modules["project_index"]
    memory_index = modules["memory_index"]
    combined = modules["combined"]
    dev_context = modules["dev_context"]
    main_agent = modules["main_agent"]
    risk = modules["risk"]
    policy_engine = modules["policy_engine"]
    main_agent_bridge = modules["main_agent_bridge"]
    lc_main_agent = modules["lc_main_agent"]

    async def run_dev_context_query(query: str, *, is_owner: bool = True):
        state = dev_context.DevContextState(query=query, is_owner=is_owner)

        def validate_context_request(current):
            if not current.is_owner:
                current.context_text = "只有主人可以使用开发侧上下文恢复。"
                current.error = "permission_denied"
            elif not current.query.strip():
                current.context_text = "请输入开发侧上下文查询。"
                current.error = "validation_failed"
            return current

        def retrieve_combined_context(current):
            results = combined.retrieve_combined_rag(
                query=current.query,
                embedder=embedder,
                is_owner=current.is_owner,
                project_top_k=args.top_k or config.project_doc_rag_top_k,
                project_min_score=(
                    args.min_score if args.min_score is not None else config.project_doc_rag_min_score
                ),
                project_max_context_chars=(
                    args.max_context_chars
                    if args.max_context_chars is not None
                    else config.project_doc_rag_max_context_chars
                ),
                memory_top_k=args.top_k or config.memory_rag_top_k,
                memory_min_score=args.min_score if args.min_score is not None else config.memory_rag_min_score,
                memory_max_context_chars=(
                    args.max_context_chars
                    if args.max_context_chars is not None
                    else config.memory_rag_max_context_chars
                ),
            )
            current.project_result_count = len(results.project_docs)
            current.memory_result_count = len(results.memories)
            current.metadata["combined_results"] = results
            return current

        def render_context_artifact(current):
            results = current.metadata.get("combined_results")
            if results is None:
                return current
            current.context_text = "\n".join(
                [
                    "DevContextGraph 开发侧上下文恢复：",
                    f"查询：{current.query}",
                    f"项目文档命中：{current.project_result_count}",
                    f"记忆命中：{current.memory_result_count}",
                    "",
                    combined.format_combined_rag_results(results),
                ]
            ).strip()
            return current

        runner = dev_context.DevContextGraphRunner(
            validate_context_request=validate_context_request,
            retrieve_combined_context=retrieve_combined_context,
            render_context_artifact=render_context_artifact,
        )
        return await runner.run(state)

    exit_code = 0
    if args.project_docs:
        stats = project_index.rebuild_project_doc_index(
            root=Path(args.root),
            embedder=embedder,
            max_chars=args.max_chars,
        )
        exit_code = max(exit_code, print_stats("ProjectDocRAG 项目文档索引重建完成：", stats, PROJECT_DOC_REBUILD_LABELS))

    if args.memory:
        stats = memory_index.rebuild_memory_rag_index(
            embedder=embedder,
            include_manual_facts=config.memory_rag_include_manual_facts,
            include_manual_preferences=config.memory_rag_include_manual_preferences,
            include_session_summaries=config.memory_rag_include_session_summaries,
        )
        exit_code = max(exit_code, print_stats("MemoryRAG 记忆索引重建完成：", stats, MEMORY_REBUILD_LABELS))

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
            print(f"ProjectDocRAG 查询失败：{exc}")
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
            print(f"MemoryRAG 查询失败：{exc}")
            exit_code = 1
        else:
            print(memory_index.format_memory_results(results))

    if args.query_combined:
        try:
            results = combined.retrieve_combined_rag(
                query=args.query_combined,
                embedder=embedder,
                is_owner=True,
                project_top_k=args.top_k or config.project_doc_rag_top_k,
                project_min_score=(
                    args.min_score if args.min_score is not None else config.project_doc_rag_min_score
                ),
                project_max_context_chars=(
                    args.max_context_chars
                    if args.max_context_chars is not None
                    else config.project_doc_rag_max_context_chars
                ),
                memory_top_k=args.top_k or config.memory_rag_top_k,
                memory_min_score=args.min_score if args.min_score is not None else config.memory_rag_min_score,
                memory_max_context_chars=(
                    args.max_context_chars
                    if args.max_context_chars is not None
                    else config.memory_rag_max_context_chars
                ),
            )
        except modules["providers"].EmbeddingProviderError as exc:
            print(f"CombinedRAG 查询失败：{exc}")
            exit_code = 1
        else:
            print(combined.format_combined_rag_results(results))

    if args.query_dev_context:
        try:
            execution = asyncio.run(run_dev_context_query(args.query_dev_context, is_owner=True))
        except modules["providers"].EmbeddingProviderError as exc:
            print(f"DevContextGraph 查询失败：{exc}")
            exit_code = 1
        else:
            print(execution.result.context_text)
            if execution.result.error:
                exit_code = 1

    if args.query_main_agent:
        try:
            state = main_agent.MainAgentState(
                query=args.query_main_agent,
                is_owner=True,
                is_group=False,
            )

            def validate_agent_request(current):
                if not current.is_owner:
                    current.response_text = "MainAgentGraph 拒绝执行：只有主人可以使用。"
                    current.error = "permission_denied"
                elif current.is_group:
                    current.response_text = "MainAgentGraph 拒绝执行：第一版只允许主人私聊使用。"
                    current.error = "group_denied"
                elif not current.query.strip():
                    current.response_text = "请输入 MainAgentGraph 查询内容。"
                    current.error = "validation_failed"
                return current

            def build_agent_context(current):
                current.metadata["mode"] = "read_only"
                current.metadata["allowed_tools"] = [main_agent.MainAgentToolName.DEV_CONTEXT.value]
                return current

            def call_main_agent(current):
                current.raw_action_request = main_agent.dev_context_tool_action_json(
                    current.query,
                    reason="恢复开发侧项目上下文",
                )
                return current

            def validate_action_request(current):
                try:
                    action_request = main_agent.parse_main_agent_action_request(current.raw_action_request)
                except main_agent.MainAgentActionRequestError as exc:
                    current.response_text = f"MainAgentGraph 拒绝执行：{exc}"
                    current.error = "invalid_action_request"
                    return current
                main_agent.apply_action_request_to_state(current, action_request)
                return current

            def check_tool_policy(current):
                if current.action != main_agent.MainAgentAction.TOOL_REQUEST.value:
                    return current
                decision = policy_engine.decide_tool_policy(
                    policy_engine.ToolPolicyInput(
                        risk_level=risk.RiskLevel.INTERNAL,
                        is_owner=current.is_owner,
                        is_group=current.is_group,
                    )
                )
                current.policy_decision = decision.type.value
                current.policy_reason = decision.reason
                if not decision.allowed:
                    current.response_text = f"MainAgentGraph 拒绝执行：{decision.reason}"
                    current.error = "policy_denied"
                return current

            async def execute_tool(current):
                if current.action != main_agent.MainAgentAction.TOOL_REQUEST.value:
                    return current
                if current.requested_tool != main_agent.MainAgentToolName.DEV_CONTEXT.value:
                    current.response_text = f"MainAgentGraph 拒绝执行：未注册工具 {current.requested_tool}"
                    current.error = "unknown_tool"
                    return current
                execution = await run_dev_context_query(current.tool_query, is_owner=current.is_owner)
                current.tool_result = execution.result.context_text
                current.metadata["dev_context_node_trace"] = tuple(node.value for node in execution.node_trace)
                return current

            def render_agent_response(current):
                if current.action != main_agent.MainAgentAction.TOOL_REQUEST.value:
                    return current
                current.response_text = "\n".join(
                    [
                        "MainAgentGraph 只读工具执行结果：",
                        f"工具：{current.requested_tool}",
                        f"策略：{current.policy_decision}",
                        "",
                        current.tool_result,
                    ]
                ).strip()
                return current

            async def retrieve_dev_context(query: str, is_owner: bool) -> str:
                execution = await run_dev_context_query(query, is_owner=is_owner)
                if execution.result.error:
                    raise RuntimeError(execution.result.context_text or execution.result.error)
                return execution.result.context_text

            call_main_agent_handler = None
            if args.main_agent_action_json:
                def call_main_agent_from_action_json(current):
                    current.raw_action_request = args.main_agent_action_json
                    return current

                call_main_agent_handler = call_main_agent_from_action_json
            elif args.main_agent_action_json_base64:
                raw_action_request = base64.b64decode(
                    args.main_agent_action_json_base64,
                    validate=True,
                ).decode("utf-8")

                def call_main_agent_from_action_json_base64(current):
                    current.raw_action_request = raw_action_request
                    return current

                call_main_agent_handler = call_main_agent_from_action_json_base64
            elif args.main_agent_use_llm:
                call_main_agent_handler = lc_main_agent.create_main_agent_lc_call_handler(config)

            runner = main_agent_bridge.create_read_only_main_agent_runner(
                retrieve_dev_context=retrieve_dev_context,
                call_main_agent=call_main_agent_handler,
            )
            execution = asyncio.run(runner.run(state))
        except modules["providers"].EmbeddingProviderError as exc:
            print(f"MainAgentGraph 查询失败：{exc}")
            exit_code = 1
        else:
            print(execution.result.response_text)
            if execution.result.error:
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
