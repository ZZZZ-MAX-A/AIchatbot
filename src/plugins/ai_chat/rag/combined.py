from __future__ import annotations

from dataclasses import dataclass

from .memory_index import MEMORY_SOURCE_TYPES, memory_document_visible, trim_results_to_context_chars as trim_memory_results
from .project_index import project_doc_visible, trim_results_to_context_chars as trim_project_results
from .providers import EmbeddingProvider
from .schema import (
    NAMESPACE_PROJECT_DOCS,
    NAMESPACE_SEMANTIC_MEMORY,
    SOURCE_PROJECT_DOC,
    RagSearchResult,
)
from .search import search_rag_documents


@dataclass(frozen=True)
class CombinedRagResults:
    project_docs: list[RagSearchResult]
    memories: list[RagSearchResult]

    @property
    def has_results(self) -> bool:
        return bool(self.project_docs or self.memories)


def retrieve_combined_rag(
    *,
    query: str,
    embedder: EmbeddingProvider,
    is_owner: bool,
    project_top_k: int = 4,
    project_min_score: float = 0.50,
    project_max_context_chars: int = 2000,
    memory_top_k: int = 5,
    memory_min_score: float = 0.55,
    memory_max_context_chars: int = 1600,
) -> CombinedRagResults:
    if not is_owner or not query.strip():
        return CombinedRagResults(project_docs=[], memories=[])

    query_embedding = embedder.embed(query)
    project_results: list[RagSearchResult] = []
    memory_results: list[RagSearchResult] = []

    if project_top_k > 0 and project_max_context_chars > 0:
        raw_project_results = search_rag_documents(
            query_embedding=query_embedding,
            namespace=NAMESPACE_PROJECT_DOCS,
            provider=embedder.provider,
            model=embedder.model,
            source_types={SOURCE_PROJECT_DOC},
            min_score=project_min_score,
            top_k=project_top_k,
        )
        visible_project_results = [
            result for result in raw_project_results if project_doc_visible(result.document, is_owner=is_owner)
        ]
        project_results = trim_project_results(visible_project_results, project_max_context_chars)

    if memory_top_k > 0 and memory_max_context_chars > 0:
        raw_memory_results = search_rag_documents(
            query_embedding=query_embedding,
            namespace=NAMESPACE_SEMANTIC_MEMORY,
            provider=embedder.provider,
            model=embedder.model,
            source_types=MEMORY_SOURCE_TYPES,
            min_score=memory_min_score,
            top_k=memory_top_k,
        )
        visible_memory_results = [
            result for result in raw_memory_results if memory_document_visible(result.document, is_owner=is_owner)
        ]
        memory_results = trim_memory_results(visible_memory_results, memory_max_context_chars)

    return CombinedRagResults(project_docs=project_results, memories=memory_results)


def format_combined_rag_results(results: CombinedRagResults) -> str:
    if not results.has_results:
        return "CombinedRAG 暂无匹配结果。"

    lines: list[str] = ["CombinedRAG 开发侧召回："]
    lines.append("")
    lines.append("项目文档召回：")
    if results.project_docs:
        for index, result in enumerate(results.project_docs, start=1):
            document = result.document
            lines.append(f"{index}. {document.title}")
            lines.append(f"   路径：{document.source_id}")
            lines.append(f"   相似度：{result.score:.3f}，片段：{document.chunk_index}")
            lines.append(document.content)
            lines.append("")
    else:
        lines.append("暂无匹配项目文档。")
        lines.append("")

    lines.append("记忆召回：")
    if results.memories:
        for index, result in enumerate(results.memories, start=1):
            document = result.document
            lines.append(f"{index}. {document.title}")
            lines.append(f"   来源：{document.source_type}:{document.source_id}")
            if document.session_key:
                lines.append(f"   会话：{document.session_key}")
            lines.append(f"   相似度：{result.score:.3f}")
            lines.append(document.content)
            lines.append("")
    else:
        lines.append("暂无匹配记忆。")

    return "\n".join(lines).strip()
