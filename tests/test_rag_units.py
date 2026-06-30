from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pure_ai_chat_loader import load_rag_modules


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

        self.assertEqual(same_embedding_id, embedding_id)
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
