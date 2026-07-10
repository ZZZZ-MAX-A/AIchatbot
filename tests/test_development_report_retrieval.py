from __future__ import annotations

import unittest

from pure_ai_chat_loader import load_rag_modules


class DevelopmentReportRetrievalPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_rag_modules()
        cls.policy = cls.modules["development_report"]
        cls.schema = cls.modules["schema"]

    def document(
        self,
        *,
        document_id: int,
        source_id: str,
        content: str,
        source_type: str | None = None,
        chunk_index: int = 0,
    ):
        return self.schema.RagDocument(
            id=document_id,
            namespace=self.schema.NAMESPACE_PROJECT_DOCS,
            source_type=source_type or self.schema.SOURCE_PROJECT_DOC,
            source_id=source_id,
            source_version="1",
            subject_type="",
            subject_id="",
            session_key="",
            message_type="",
            user_id="",
            group_id="",
            visibility=self.schema.VISIBILITY_PROJECT_OWNER,
            title=f"{source_id}#Section {chunk_index}",
            content=content,
            content_hash=f"hash-{document_id}",
            chunk_index=chunk_index,
            created_at="2026-07-11T00:00:00+00:00",
            updated_at="2026-07-11T00:00:00+00:00",
            deleted_at="",
        )

    def result(self, *, document_id: int, source_id: str, content: str, score: float):
        return self.schema.RagSearchResult(
            document=self.document(
                document_id=document_id,
                source_id=source_id,
                content=content,
            ),
            score=score,
        )

    def test_candidate_expansion_and_partition_budgets_match_fixed_contract(self):
        self.assertEqual(self.policy.development_report_candidate_top_k(0), 0)
        self.assertEqual(self.policy.development_report_candidate_top_k(1), 12)
        self.assertEqual(self.policy.development_report_candidate_top_k(3), 12)
        self.assertEqual(self.policy.development_report_candidate_top_k(5), 20)
        self.assertEqual(self.policy.development_report_candidate_top_k(99), 32)
        self.assertEqual(self.policy.DEVELOPMENT_REPORT_PROJECT_RESULT_LIMIT, 3)
        self.assertEqual(self.policy.DEVELOPMENT_REPORT_PROJECT_MAX_PER_SOURCE, 1)
        self.assertEqual(self.policy.CURRENT_STATUS_ANCHOR_MAX_CHARS, 1200)
        self.assertEqual(self.policy.DEVELOPMENT_REPORT_PROJECT_MAX_CHARS, 1800)
        self.assertEqual(self.policy.DEVELOPMENT_REPORT_MEMORY_MAX_CHARS, 800)
        self.assertEqual(self.policy.DEVELOPMENT_REPORT_FORMAT_RESERVE_CHARS, 400)
        self.assertEqual(self.policy.DEVELOPMENT_REPORT_EVIDENCE_MAX_CHARS, 3800)
        self.assertEqual(
            self.policy.DEVELOPMENT_REPORT_EVIDENCE_MAX_CHARS
            + self.policy.DEVELOPMENT_REPORT_FORMAT_RESERVE_CHARS,
            self.policy.DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT,
        )

    def test_source_diversity_excludes_anchor_and_prevents_single_source_monopoly(self):
        anchor_source = self.policy.CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
        candidates = [
            self.result(document_id=1, source_id=anchor_source, content="anchor duplicate", score=0.99),
            self.result(document_id=2, source_id="docs/version-runlog.md", content="old one", score=0.98),
            self.result(document_id=3, source_id="docs/version-runlog.md", content="old two", score=0.97),
            self.result(document_id=4, source_id="docs/version-runlog.md", content="old three", score=0.96),
            self.result(document_id=5, source_id="docs/design.md", content="design", score=0.95),
            self.result(document_id=6, source_id="docs/runbook.md", content="runbook", score=0.94),
            self.result(document_id=7, source_id="docs/extra.md", content="extra", score=0.93),
        ]

        selected = self.policy.select_development_report_project_results(candidates)

        self.assertEqual(
            [result.document.source_id for result in selected],
            ["docs/version-runlog.md", "docs/design.md", "docs/runbook.md"],
        )
        self.assertEqual([result.score for result in selected], [0.98, 0.95, 0.94])
        self.assertNotIn(anchor_source, [result.document.source_id for result in selected])

    def test_partition_builder_preserves_inputs_and_enforces_each_budget(self):
        anchor_source = self.policy.CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
        anchors = [
            self.document(
                document_id=10,
                source_id=anchor_source,
                content="a" * 1000,
                chunk_index=0,
            ),
            self.document(
                document_id=11,
                source_id=anchor_source,
                content="b" * 500,
                chunk_index=1,
            ),
        ]
        projects = [
            self.result(document_id=20, source_id=anchor_source, content="x" * 500, score=0.99),
            self.result(document_id=21, source_id="docs/version-runlog.md", content="v" * 1000, score=0.98),
            self.result(document_id=22, source_id="docs/version-runlog.md", content="w" * 1000, score=0.97),
            self.result(document_id=23, source_id="docs/design.md", content="d" * 1000, score=0.96),
            self.result(document_id=24, source_id="docs/runbook.md", content="r" * 1000, score=0.95),
        ]
        memories = [
            self.result(document_id=30, source_id="memory-1", content="m" * 600, score=0.90),
            self.result(document_id=31, source_id="memory-2", content="n" * 600, score=0.89),
        ]

        evidence = self.policy.build_development_report_evidence(
            current_status_docs=anchors,
            project_candidates=projects,
            memories=memories,
        )

        anchor_chars = sum(len(document.content) for document in evidence.current_status_docs)
        project_chars = sum(len(result.document.content) for result in evidence.project_docs)
        memory_chars = sum(len(result.document.content) for result in evidence.memories)
        self.assertEqual(anchor_chars, 1200)
        self.assertEqual(project_chars, 1800)
        self.assertEqual(memory_chars, 800)
        self.assertEqual(
            self.policy.development_report_evidence_content_chars(evidence),
            3800,
        )
        self.assertEqual(
            [result.document.source_id for result in evidence.project_docs],
            ["docs/version-runlog.md", "docs/design.md"],
        )
        self.assertEqual(len(anchors[1].content), 500)
        self.assertEqual(len(projects[3].document.content), 1000)
        self.assertEqual(len(memories[1].document.content), 600)

    def test_missing_anchor_still_excludes_registered_anchor_from_semantic_results(self):
        anchor_source = self.policy.CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
        evidence = self.policy.build_development_report_evidence(
            current_status_docs=[],
            project_candidates=[
                self.result(document_id=40, source_id=anchor_source, content="duplicate", score=0.99),
                self.result(document_id=41, source_id="docs/a.md", content="a", score=0.98),
                self.result(document_id=42, source_id="", content="missing source", score=0.97),
                self.result(document_id=43, source_id="docs/b.md", content="b", score=0.96),
            ],
            memories=[],
        )

        self.assertEqual(evidence.current_status_docs, [])
        self.assertEqual(
            [result.document.source_id for result in evidence.project_docs],
            ["docs/a.md", "docs/b.md"],
        )


if __name__ == "__main__":
    unittest.main()
