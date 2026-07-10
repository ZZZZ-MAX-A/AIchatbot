from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_memory_modules, load_rag_modules


class FakeEmbeddingProvider:
    provider = "unit"
    model = "toy"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        normalized = text.lower()
        if "deploy" in normalized or "readme" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]


class TempDatabaseMixin:
    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, patcher


class RagDocumentStorageUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.database = cls.modules["database"]
        cls.documents = cls.modules["documents"]
        cls.schema = cls.modules["schema"]

    def test_upsert_update_soft_delete_and_reactivate_document(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            document_id = self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="memory-1",
                title="fact 1",
                content="first content",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
                subject_type="private",
                subject_id="10001",
            )
            same_document_id = self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="memory-1",
                title="fact 1 updated",
                content="updated content",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
                subject_type="private",
                subject_id="10001",
            )
            updated = self.documents.get_rag_document(document_id)
            deleted_count = self.documents.soft_delete_rag_documents(source_id="memory-1")
            hidden = self.documents.get_rag_document(document_id)
            deleted = self.documents.get_rag_document(document_id, include_deleted=True)
            reactivated_document_id = self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="memory-1",
                title="fact 1 reactivated",
                content="reactivated content",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
                subject_type="private",
                subject_id="10001",
            )
            reactivated = self.documents.get_rag_document(document_id)
            stats = self.documents.rag_document_stats()

        self.assertEqual(same_document_id, document_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.title, "fact 1 updated")
        self.assertEqual(updated.content_hash, self.documents.stable_content_hash("updated content"))
        self.assertEqual(deleted_count, 1)
        self.assertIsNone(hidden)
        self.assertIsNotNone(deleted)
        self.assertTrue(deleted.deleted_at)
        self.assertEqual(reactivated_document_id, document_id)
        self.assertIsNotNone(reactivated)
        self.assertEqual(reactivated.deleted_at, "")
        self.assertEqual(reactivated.content, "reactivated content")
        self.assertEqual(
            stats,
            {"document_count": 1, "active_document_count": 1, "embedding_count": 0},
        )

    def test_soft_delete_requires_filter_and_list_hides_deleted_documents(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="fact-1",
                title="fact 1",
                content="fact content",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
            )
            self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                source_id="README.md",
                title="README.md",
                content="project content",
                visibility=self.schema.VISIBILITY_PROJECT_OWNER,
            )

            with self.assertRaises(ValueError):
                self.documents.soft_delete_rag_documents()

            deleted = self.documents.soft_delete_rag_documents(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY
            )
            active = self.documents.list_rag_documents()
            all_documents = self.documents.list_rag_documents(include_deleted=True)

        self.assertEqual(deleted, 1)
        self.assertEqual([document.source_id for document in active], ["README.md"])
        self.assertEqual({document.source_id for document in all_documents}, {"fact-1", "README.md"})


class RagEmbeddingAndSearchUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.database = cls.modules["database"]
        cls.documents = cls.modules["documents"]
        cls.embeddings = cls.modules["embeddings"]
        cls.search = cls.modules["search"]
        cls.schema = cls.modules["schema"]

    def add_document_with_embedding(
        self,
        *,
        namespace: str,
        source_type: str,
        source_id: str,
        content: str,
        embedding: list[float],
        visibility: str | None = None,
    ) -> int:
        document_id = self.documents.upsert_rag_document(
            namespace=namespace,
            source_type=source_type,
            source_id=source_id,
            title=source_id,
            content=content,
            visibility=visibility or self.schema.VISIBILITY_OWNER_ONLY,
        )
        document = self.documents.get_rag_document(document_id)
        self.assertIsNotNone(document)
        self.embeddings.upsert_rag_embedding(
            document_id=document_id,
            provider="unit",
            model="toy",
            embedding=embedding,
            content_hash=document.content_hash,
        )
        return document_id

    def test_embedding_serialization_and_upsert_validation(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            document_id = self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="fact-1",
                title="fact 1",
                content="fact content",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
            )
            document = self.documents.get_rag_document(document_id)
            self.assertIsNotNone(document)
            embedding_id = self.embeddings.upsert_rag_embedding(
                document_id=document_id,
                provider="unit",
                model="toy",
                embedding=[1, 2, 3],
                content_hash=document.content_hash,
            )
            same_embedding_id = self.embeddings.upsert_rag_embedding(
                document_id=document_id,
                provider="unit",
                model="toy",
                embedding=[3, 2, 1],
                content_hash=document.content_hash,
            )
            with self.database.connect() as connection:
                row = connection.execute(
                    """
                    SELECT embedding_dimension, embedding
                    FROM rag_embeddings
                    WHERE id = ?
                    """,
                    (embedding_id,),
                ).fetchone()

            with self.assertRaises(ValueError):
                self.embeddings.upsert_rag_embedding(
                    document_id=document_id,
                    provider="unit",
                    model="empty",
                    embedding=[],
                    content_hash=document.content_hash,
                )
            with self.assertRaises(ValueError):
                self.embeddings.deserialize_embedding('{"not":"a list"}')
            record = self.embeddings.get_rag_embedding(
                document_id=document_id,
                provider="unit",
                model="toy",
            )
            matches_content = self.embeddings.rag_embedding_matches_content(
                document_id=document_id,
                provider="unit",
                model="toy",
                content_hash=document.content_hash,
            )

        self.assertEqual(same_embedding_id, embedding_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.document_id, document_id)
        self.assertEqual(record.provider, "unit")
        self.assertEqual(record.model, "toy")
        self.assertEqual(record.dimension, 3)
        self.assertEqual(record.embedding, [3.0, 2.0, 1.0])
        self.assertTrue(matches_content)
        self.assertEqual(row["embedding_dimension"], 3)
        self.assertEqual(self.embeddings.deserialize_embedding(row["embedding"]), [3.0, 2.0, 1.0])

    def test_search_sorts_filters_and_excludes_deleted_or_stale_embeddings(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="fact-1",
                content="aligned fact",
                embedding=[1.0, 0.0],
            )
            self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_SESSION_SUMMARY,
                source_id="summary-1",
                content="nearby summary",
                embedding=[0.8, 0.2],
            )
            self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                source_id="README.md",
                content="project docs",
                embedding=[0.0, 1.0],
                visibility=self.schema.VISIBILITY_PROJECT_OWNER,
            )
            deleted_id = self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_PREFERENCE,
                source_id="deleted-pref",
                content="deleted preference",
                embedding=[1.0, 0.0],
            )
            self.documents.soft_delete_rag_documents(source_id="deleted-pref")
            stale_id = self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="stale-fact",
                content="old content",
                embedding=[1.0, 0.0],
            )
            self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="stale-fact",
                title="stale-fact",
                content="new content without refreshed embedding",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
            )

            results = self.search.search_rag_documents(
                query_embedding=[1.0, 0.0],
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                provider="unit",
                model="toy",
                top_k=5,
                min_score=0.1,
            )
            fact_results = self.search.search_rag_documents(
                query_embedding=[1.0, 0.0],
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                provider="unit",
                model="toy",
                source_types={self.schema.SOURCE_MANUAL_FACT},
                top_k=5,
            )
            project_results = self.search.search_rag_documents(
                query_embedding=[0.0, 1.0],
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                provider="unit",
                model="toy",
                top_k=5,
            )

        self.assertEqual(round(self.search.cosine_similarity([1, 0], [1, 0]), 4), 1.0)
        self.assertEqual(self.search.cosine_similarity([1, 0], [0, 0]), 0.0)
        self.assertEqual(self.search.cosine_similarity([1, 0], [1]), 0.0)
        self.assertEqual([result.document.source_id for result in results], ["fact-1", "summary-1"])
        self.assertEqual([result.document.source_id for result in fact_results], ["fact-1"])
        self.assertEqual([result.document.source_id for result in project_results], ["README.md"])
        self.assertNotIn(deleted_id, [result.document.id for result in results])
        self.assertNotIn(stale_id, [result.document.id for result in results])


class RagProjectDocUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.project_docs = cls.modules["project_docs"]

    def test_markdown_scanner_and_chunker_keep_path_source_id_and_titles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            readme = root / "README.md"
            design = docs_dir / "design.md"
            readme.write_text("# README\nintro\n\n## Usage\nstep one\nstep two\n", encoding="utf-8")
            design.write_text("# Design\nalpha\nbeta\n", encoding="utf-8")

            files = self.project_docs.iter_project_markdown_files(root)
            chunks = self.project_docs.chunk_markdown_document(
                path=readme,
                text=readme.read_text(encoding="utf-8"),
                root=root,
                max_chars=25,
            )
            relative_files = [path.relative_to(root).as_posix() for path in files]

        self.assertEqual(relative_files, ["README.md", "docs/design.md"])
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual({chunk.source_id for chunk in chunks}, {"README.md"})
        self.assertEqual([chunk.chunk_index for chunk in chunks], list(range(len(chunks))))
        self.assertEqual(chunks[0].title, "README.md#README")
        self.assertTrue(any(chunk.title == "README.md#Usage" for chunk in chunks))
        self.assertTrue(all(chunk.source_version for chunk in chunks))

    def test_project_doc_scanner_includes_safe_docs_and_excludes_private_runtime_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = [
                root / "README.md",
                root / "docs" / "design.md",
                root / "docs" / "nested" / "runbook.md",
                root / "docs-archive" / "old.md",
                root / "prompts" / "base" / "chat-core.json",
                root / "prompts" / "persona-cards" / "public" / "default.md",
                root / "prompts" / "persona-cards" / "private" / "secret.md",
                root / "data" / "chatbot.db",
                root / "logs" / "ai_chat_error.log",
                root / ".env",
            ]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("content", encoding="utf-8")

            files = self.project_docs.iter_project_document_files(root)
            relative_files = [path.relative_to(root).as_posix() for path in files]

        self.assertEqual(
            relative_files,
            [
                "README.md",
                "docs/design.md",
                "docs/nested/runbook.md",
                "prompts/base/chat-core.json",
                "prompts/persona-cards/public/default.md",
            ],
        )

    def test_current_development_status_source_id_is_fixed_and_single_chunk_indexable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot = root / self.project_docs.CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(
                "# AIchatbot 当前开发状态\n\n当前阶段：P2.45a。\n推荐下一步：P2.45b。\n",
                encoding="utf-8",
            )

            chunks = self.project_docs.chunk_markdown_document(
                path=snapshot,
                text=snapshot.read_text(encoding="utf-8"),
                root=root,
            )

        self.assertEqual(
            self.project_docs.CURRENT_DEVELOPMENT_STATUS_SOURCE_ID,
            "docs/current-development-status.md",
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].source_id, "docs/current-development-status.md")
        self.assertEqual(chunks[0].chunk_index, 0)


class RagProjectIndexUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.database = cls.modules["database"]
        cls.documents = cls.modules["documents"]
        cls.project_index = cls.modules["project_index"]
        cls.schema = cls.modules["schema"]

    def write_project_docs(self, root: Path) -> tuple[Path, Path]:
        docs_dir = root / "docs"
        docs_dir.mkdir()
        readme = root / "README.md"
        design = docs_dir / "vision.md"
        readme.write_text("# README\nDeploy the bot with scripts/start.ps1.\n", encoding="utf-8")
        design.write_text("# Vision\nOllama handles image descriptions.\n", encoding="utf-8")
        return readme, design

    def test_rebuild_project_docs_indexes_skips_and_soft_deletes_stale_chunks(self):
        temp_db_dir, patcher = self.temp_database()
        with tempfile.TemporaryDirectory() as project_dir, temp_db_dir, patcher:
            root = Path(project_dir)
            _, design = self.write_project_docs(root)
            embedder = FakeEmbeddingProvider()

            first = self.project_index.rebuild_project_doc_index(root=root, embedder=embedder)
            first_call_count = len(embedder.calls)
            second = self.project_index.rebuild_project_doc_index(root=root, embedder=embedder)
            design.unlink()
            third = self.project_index.rebuild_project_doc_index(root=root, embedder=embedder)
            active_documents = self.documents.list_rag_documents(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                limit=None,
            )

        self.assertFalse(first.has_errors)
        self.assertEqual(first.scanned_files, 2)
        self.assertEqual(first.created_documents, first.chunks_seen)
        self.assertEqual(first.embeddings_created, first.chunks_seen)
        self.assertEqual(first_call_count, first.chunks_seen)
        self.assertFalse(second.has_errors)
        self.assertEqual(second.unchanged_documents, second.chunks_seen)
        self.assertEqual(second.embeddings_skipped, second.chunks_seen)
        self.assertEqual(len(embedder.calls), first_call_count)
        self.assertFalse(third.has_errors)
        self.assertGreaterEqual(third.soft_deleted_documents, 1)
        self.assertEqual({document.source_id for document in active_documents}, {"README.md"})

    def test_retrieve_project_docs_uses_owner_visibility_and_context_limit(self):
        temp_db_dir, patcher = self.temp_database()
        with tempfile.TemporaryDirectory() as project_dir, temp_db_dir, patcher:
            root = Path(project_dir)
            self.write_project_docs(root)
            embedder = FakeEmbeddingProvider()
            self.project_index.rebuild_project_doc_index(root=root, embedder=embedder)

            owner_results = self.project_index.retrieve_project_docs(
                query="deploy",
                embedder=embedder,
                is_owner=True,
                top_k=2,
                min_score=0.1,
                max_context_chars=20,
            )
            non_owner_results = self.project_index.retrieve_project_docs(
                query="deploy",
                embedder=embedder,
                is_owner=False,
                top_k=2,
                min_score=0.1,
                max_context_chars=200,
            )
            formatted = self.project_index.format_project_doc_results(owner_results)

        self.assertEqual([result.document.source_id for result in owner_results], ["README.md"])
        self.assertLessEqual(len(owner_results[0].document.content), 20)
        self.assertEqual(non_owner_results, [])
        self.assertIn("README.md#README", formatted)

    def test_current_status_anchor_uses_only_fixed_source_owner_scope_and_budget(self):
        temp_db_dir, patcher = self.temp_database()
        anchor_source = self.project_index.CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
        with temp_db_dir, patcher:
            second_id = self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                source_id=anchor_source,
                title=f"{anchor_source}#Second",
                content="second anchor chunk",
                visibility=self.schema.VISIBILITY_PROJECT_OWNER,
                chunk_index=1,
            )
            current_id = self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                source_id=anchor_source,
                title=f"{anchor_source}#Current",
                content="current anchor chunk",
                visibility=self.schema.VISIBILITY_PROJECT_OWNER,
                chunk_index=0,
            )
            self.documents.upsert_rag_document(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                source_id="docs/current-development-status-copy.md",
                title="lookalike",
                content="must not be selected",
                visibility=self.schema.VISIBILITY_PROJECT_OWNER,
                chunk_index=0,
            )

            owner_documents = self.project_index.retrieve_current_development_status(
                is_owner=True,
                max_context_chars=25,
            )
            non_owner_documents = self.project_index.retrieve_current_development_status(
                is_owner=False,
                max_context_chars=200,
            )
            self.documents.soft_delete_rag_document(current_id)
            self.documents.soft_delete_rag_document(second_id)
            deleted_documents = self.project_index.retrieve_current_development_status(
                is_owner=True,
                max_context_chars=200,
            )

        self.assertEqual(
            [document.chunk_index for document in owner_documents],
            [0, 1],
        )
        self.assertEqual(
            {document.source_id for document in owner_documents},
            {anchor_source},
        )
        self.assertLessEqual(
            sum(len(document.content) for document in owner_documents),
            25,
        )
        self.assertEqual(non_owner_documents, [])
        self.assertEqual(deleted_documents, [])
        self.assertEqual(
            tuple(inspect.signature(self.project_index.retrieve_current_development_status).parameters),
            ("is_owner", "max_context_chars"),
        )


class RagCombinedRetrievalUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.database = cls.modules["database"]
        cls.documents = cls.modules["documents"]
        cls.embeddings = cls.modules["embeddings"]
        cls.combined = cls.modules["combined"]
        cls.schema = cls.modules["schema"]

    def add_document_with_embedding(
        self,
        *,
        namespace: str,
        source_type: str,
        source_id: str,
        title: str,
        content: str,
        visibility: str,
        embedding: list[float],
    ) -> None:
        document_id = self.documents.upsert_rag_document(
            namespace=namespace,
            source_type=source_type,
            source_id=source_id,
            title=title,
            content=content,
            visibility=visibility,
        )
        document = self.documents.get_rag_document(document_id)
        self.assertIsNotNone(document)
        self.embeddings.upsert_rag_embedding(
            document_id=document_id,
            provider="unit",
            model="toy",
            embedding=embedding,
            content_hash=document.content_hash,
        )

    def test_combined_retrieval_keeps_project_docs_and_memories_separated(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_PROJECT_DOCS,
                source_type=self.schema.SOURCE_PROJECT_DOC,
                source_id="docs/runbook.md",
                title="docs/runbook.md#Deploy",
                content="Deploy the bot with scripts/start.ps1.",
                visibility=self.schema.VISIBILITY_PROJECT_OWNER,
                embedding=[1.0, 0.0],
            )
            self.add_document_with_embedding(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                source_type=self.schema.SOURCE_MANUAL_FACT,
                source_id="42",
                title="长期事实记忆 42",
                content="主人确认 MemoryRAG 已经接入普通聊天。",
                visibility=self.schema.VISIBILITY_OWNER_ONLY,
                embedding=[1.0, 0.0],
            )
            embedder = FakeEmbeddingProvider()

            owner_results = self.combined.retrieve_combined_rag(
                query="deploy memoryrag readme",
                embedder=embedder,
                is_owner=True,
                project_top_k=3,
                project_min_score=0.1,
                project_max_context_chars=200,
                memory_top_k=3,
                memory_min_score=0.1,
                memory_max_context_chars=200,
            )
            non_owner_results = self.combined.retrieve_combined_rag(
                query="deploy memoryrag readme",
                embedder=embedder,
                is_owner=False,
            )
            formatted = self.combined.format_combined_rag_results(owner_results)
            anchor_only = self.combined.CombinedRagResults(
                project_docs=[],
                memories=[],
                current_status_docs=[owner_results.project_docs[0].document],
            )
            anchor_formatted = self.combined.format_combined_rag_results(anchor_only)

        self.assertEqual([result.document.source_id for result in owner_results.project_docs], ["docs/runbook.md"])
        self.assertEqual([result.document.source_id for result in owner_results.memories], ["42"])
        self.assertEqual(non_owner_results.project_docs, [])
        self.assertEqual(non_owner_results.memories, [])
        self.assertEqual(owner_results.current_status_docs, [])
        self.assertEqual(non_owner_results.current_status_docs, [])
        self.assertEqual(len(embedder.calls), 1)
        self.assertIn("CombinedRAG 开发侧召回：", formatted)
        self.assertNotIn("当前状态锚点：", formatted)
        self.assertIn("项目文档召回：", formatted)
        self.assertIn("记忆召回：", formatted)
        self.assertTrue(anchor_only.has_results)
        self.assertIn("当前状态锚点：", anchor_formatted)
        self.assertIn("docs/runbook.md#Deploy", anchor_formatted)
        self.assertNotIn("相似度：", anchor_formatted)


class RagProviderUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.providers = cls.modules["providers"]

    def test_parse_ollama_embedding_response_accepts_current_and_legacy_shapes(self):
        self.assertEqual(
            self.providers.parse_ollama_embedding_response({"embeddings": [[1, "2", 3.5]]}),
            [1.0, 2.0, 3.5],
        )
        self.assertEqual(
            self.providers.parse_ollama_embedding_response({"embedding": [4, 5]}),
            [4.0, 5.0],
        )
        with self.assertRaises(self.providers.EmbeddingProviderError):
            self.providers.parse_ollama_embedding_response({"embeddings": []})

    def test_check_embedding_provider_uses_capped_timeout_and_reports_dimension(self):
        captured = {}

        class ProbeEmbedder:
            provider = "unit"
            model = "toy"

            def embed(self, text: str) -> list[float]:
                captured["text"] = text
                return [0.1, 0.2, 0.3]

        def fake_builder(config):
            captured["timeout"] = config.memory_rag_embedding_timeout_seconds
            captured["dimension"] = config.memory_rag_embedding_dimension
            return ProbeEmbedder()

        config = SimpleNamespace(
            memory_rag_embedding_provider="ollama",
            memory_rag_embedding_model="bge-m3",
            memory_rag_embedding_base_url="http://127.0.0.1:11434",
            memory_rag_embedding_timeout_seconds=60,
            memory_rag_embedding_dimension=1024,
        )

        with patch.object(self.providers, "build_embedding_provider", fake_builder):
            result = self.providers.check_embedding_provider(config)

        self.assertTrue(result.ok)
        self.assertEqual(result.dimension, 3)
        self.assertEqual(captured["timeout"], self.providers.EMBEDDING_HEALTH_CHECK_TIMEOUT_SECONDS)
        self.assertEqual(captured["dimension"], 1024)
        self.assertEqual(captured["text"], self.providers.EMBEDDING_HEALTH_CHECK_TEXT)
        self.assertIn("维度 3", result.detail)
        self.assertNotIn(self.providers.EMBEDDING_HEALTH_CHECK_TEXT, result.detail)

    def test_check_embedding_provider_reports_failure_without_vector_content(self):
        error_cls = self.providers.EmbeddingProviderError

        class FailingEmbedder:
            provider = "unit"
            model = "toy"

            def embed(self, text: str) -> list[float]:
                raise error_cls("Cannot connect to Ollama: refused")

        config = SimpleNamespace(
            memory_rag_embedding_provider="ollama",
            memory_rag_embedding_model="bge-m3",
            memory_rag_embedding_base_url="http://127.0.0.1:11434",
            memory_rag_embedding_timeout_seconds=60,
            memory_rag_embedding_dimension=1024,
        )

        with patch.object(self.providers, "build_embedding_provider", lambda _: FailingEmbedder()):
            result = self.providers.check_embedding_provider(config)

        self.assertFalse(result.ok)
        self.assertEqual(result.dimension, 0)
        self.assertIn("Cannot connect to Ollama", result.detail)
        self.assertNotIn(self.providers.EMBEDDING_HEALTH_CHECK_TEXT, result.detail)

    def test_check_embedding_provider_skips_when_rag_is_disabled(self):
        result = self.providers.check_embedding_provider(SimpleNamespace(), enabled=False)

        self.assertFalse(result.ok)
        self.assertIn("未执行", result.detail)


class RagMemoryIndexUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.legacy_modules = load_legacy_memory_modules()
        cls.database = cls.modules["database"]
        cls.documents = cls.modules["documents"]
        cls.memory_index = cls.modules["memory_index"]
        cls.schema = cls.modules["schema"]
        cls.manual_memory = cls.legacy_modules["manual_memory"]
        cls.summaries = cls.legacy_modules["summaries"]

    def add_summary(self, session_key: str, text: str) -> int:
        return self.summaries.add_summary(
            session_key=session_key,
            message_type="private",
            user_id="10001",
            group_id=None,
            summary=text,
            message_start_id=1,
            message_end_id=2,
            source_message_count=2,
        )

    def test_rebuild_memory_rag_indexes_and_skips_unchanged_embeddings(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict("os.environ", {"ENABLE_MEMORY_RAG": "false"}):
            self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "fact memory",
                memory_type="fact",
            )
            self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "preference memory",
                memory_type="preference",
            )
            self.add_summary("private:10001", "summary memory")
            embedder = FakeEmbeddingProvider()

            first = self.memory_index.rebuild_memory_rag_index(embedder=embedder)
            first_call_count = len(embedder.calls)
            second = self.memory_index.rebuild_memory_rag_index(embedder=embedder)
            active_documents = self.documents.list_rag_documents(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                include_deleted=False,
                limit=None,
            )

        self.assertFalse(first.has_errors)
        self.assertEqual(first.scanned_manual_memories, 2)
        self.assertEqual(first.scanned_session_summaries, 1)
        self.assertEqual(first.created_documents, 3)
        self.assertEqual(first.embeddings_created, 3)
        self.assertEqual(first_call_count, 3)
        self.assertFalse(second.has_errors)
        self.assertEqual(second.unchanged_documents, 3)
        self.assertEqual(second.embeddings_skipped, 3)
        self.assertEqual(len(embedder.calls), first_call_count)
        self.assertEqual(
            {document.source_type for document in active_documents},
            {
                self.schema.SOURCE_MANUAL_FACT,
                self.schema.SOURCE_MANUAL_PREFERENCE,
                self.schema.SOURCE_SESSION_SUMMARY,
            },
        )

    def test_memory_delete_hooks_soft_delete_index_documents(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict("os.environ", {"ENABLE_MEMORY_RAG": "false"}):
            memory_id = self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "preference memory",
                memory_type="preference",
            )
            summary_id = self.add_summary("private:10001", "summary memory")
            embedder = FakeEmbeddingProvider()
            self.memory_index.rebuild_memory_rag_index(embedder=embedder)

            memory_deleted = self.manual_memory.delete_manual_memory(memory_id)
            summary_deleted = self.summaries.delete_session_summary("private:10001", summary_id)
            active_documents = self.documents.list_rag_documents(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                include_deleted=False,
                limit=None,
            )
            all_documents = self.documents.list_rag_documents(
                namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                include_deleted=True,
                limit=None,
            )

        self.assertTrue(memory_deleted)
        self.assertTrue(summary_deleted)
        self.assertEqual(active_documents, [])
        self.assertEqual(len(all_documents), 2)
        self.assertTrue(all(document.deleted_at for document in all_documents))

    def test_retrieve_memory_uses_owner_visibility_and_context_limit(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict("os.environ", {"ENABLE_MEMORY_RAG": "false"}):
            self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "fact memory with a long enough body",
                memory_type="fact",
            )
            embedder = FakeEmbeddingProvider()
            self.memory_index.rebuild_memory_rag_index(embedder=embedder)

            owner_results = self.memory_index.retrieve_memory(
                query="memory",
                embedder=embedder,
                is_owner=True,
                top_k=3,
                min_score=0.1,
                max_context_chars=12,
            )
            non_owner_results = self.memory_index.retrieve_memory(
                query="memory",
                embedder=embedder,
                is_owner=False,
                top_k=3,
                min_score=0.1,
                max_context_chars=120,
            )
            formatted = self.memory_index.format_memory_results(owner_results)

        self.assertEqual([result.document.source_type for result in owner_results], [self.schema.SOURCE_MANUAL_FACT])
        self.assertLessEqual(len(owner_results[0].document.content), 12)
        self.assertEqual(non_owner_results, [])
        self.assertIn("manual_fact", formatted)


class RagMemorySourceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.memory_sources = cls.modules["memory_sources"]
        cls.schema = cls.modules["schema"]

    def test_manual_memory_and_session_summary_document_fields(self):
        fact = SimpleNamespace(
            id=1,
            subject_type="private",
            subject_id="10001",
            memory_type="fact_summary",
            content="fact content",
            updated_at="2026-06-30T00:00:00+00:00",
        )
        preference = SimpleNamespace(
            id=2,
            subject_type="private",
            subject_id="10001",
            memory_type="preference_summary",
            content="preference content",
            updated_at="2026-06-30T00:00:01+00:00",
        )
        summary = SimpleNamespace(
            id=3,
            session_key="private:10001",
            summary="session summary content",
            created_at="2026-06-30T00:00:02+00:00",
        )

        fact_fields = self.memory_sources.manual_memory_document_fields(fact)
        preference_fields = self.memory_sources.manual_memory_document_fields(preference)
        summary_fields = self.memory_sources.session_summary_document_fields(summary)

        self.assertEqual(fact_fields["namespace"], self.schema.NAMESPACE_SEMANTIC_MEMORY)
        self.assertEqual(fact_fields["source_type"], self.schema.SOURCE_MANUAL_FACT)
        self.assertEqual(fact_fields["source_id"], "1")
        self.assertEqual(fact_fields["subject_type"], "private")
        self.assertEqual(fact_fields["subject_id"], "10001")
        self.assertEqual(fact_fields["visibility"], self.schema.VISIBILITY_OWNER_ONLY)
        self.assertEqual(preference_fields["source_type"], self.schema.SOURCE_MANUAL_PREFERENCE)
        self.assertEqual(preference_fields["content"], "preference content")
        self.assertEqual(summary_fields["source_type"], self.schema.SOURCE_SESSION_SUMMARY)
        self.assertEqual(summary_fields["source_id"], "3")
        self.assertEqual(summary_fields["session_key"], "private:10001")
        self.assertEqual(summary_fields["content"], "session summary content")


if __name__ == "__main__":
    unittest.main()
