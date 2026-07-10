from __future__ import annotations

import json
import types
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_module


class DevelopmentContextReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = load_module(
            "src.plugins.ai_chat.development_context_report",
            AI_CHAT_ROOT / "development_context_report.py",
        )

    @staticmethod
    def result(*, title: str, content: str, source_id: str = "private/path.md"):
        return types.SimpleNamespace(
            score=0.99,
            document=types.SimpleNamespace(
                title=title,
                content=content,
                source_id=source_id,
                session_key="private:10001",
            ),
        )

    def test_report_source_is_bounded_and_removes_retrieval_metadata_and_secrets(self):
        source = self.report.build_development_context_report_source(
            project_docs=[
                self.result(
                    title="docs/version-runlog.md#P2.43 current state",
                    content=(
                        "P2.43 is complete.\n"
                        "Next: design P2.44.\n"
                        "PRIVATE_TOKEN=do-not-send\n"
                        "owner@example.com 13800138000\n"
                        "D:\\AIchatbot\\data\\chatbot.db"
                    ),
                )
            ],
            memories=[
                self.result(
                    title="memory",
                    content="Keep Owner Console read-only.",
                    source_id="memory:77",
                )
            ],
        )

        self.assertIn("章节：P2.43 current state", source)
        self.assertIn("Keep Owner Console read-only", source)
        self.assertNotIn("docs/version-runlog.md", source)
        self.assertNotIn("private/path.md", source)
        self.assertNotIn("private:10001", source)
        self.assertNotIn("do-not-send", source)
        self.assertNotIn("owner@example.com", source)
        self.assertNotIn("13800138000", source)
        self.assertNotIn("D:\\AIchatbot", source)
        self.assertLessEqual(
            len(source),
            self.report.DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT,
        )

    def test_fixed_json_contract_parses_and_formats_structured_report(self):
        raw = json.dumps(
            {
                "current_stage": "P2.43 已完成。",
                "completed_items": ["显式主人私聊任务已接入。"],
                "pending_items": ["P2.40b 仍未批准。"],
                "safety_boundaries": ["Owner Console 保持只读。"],
                "recommended_next_steps": ["先观察正式任务使用频率。"],
                "evidence_limits": ["召回材料未提供 Git 远端状态。"],
            },
            ensure_ascii=False,
        )

        sections = self.report.parse_development_context_report_json(raw)
        formatted = self.report.format_development_context_report_sections(sections)

        self.assertEqual(sections.current_stage, "P2.43 已完成。")
        self.assertIn("当前阶段：", formatted)
        self.assertIn("未完成事项：", formatted)
        self.assertIn("P2.40b 仍未批准", formatted)
        self.assertIn("推荐下一步：", formatted)

    def test_contract_rejects_markdown_or_missing_fields(self):
        with self.assertRaisesRegex(
            self.report.DevelopmentContextReportFormatError,
            "must be JSON",
        ):
            self.report.parse_development_context_report_json("```json\n{}\n```")

        with self.assertRaisesRegex(
            self.report.DevelopmentContextReportFormatError,
            "fields do not match",
        ):
            self.report.parse_development_context_report_json(
                '{"current_stage":"only one field"}'
            )

    def test_deterministic_fallback_never_claims_specific_pending_work(self):
        sections = self.report.fallback_development_context_report_sections(
            project_result_count=3,
            memory_result_count=1,
            relevant_sections=("P2.43", "安全边界"),
        )
        formatted = self.report.format_development_context_report_sections(sections)

        self.assertIn("受限结构化总结未启用或不可用", formatted)
        self.assertIn("不从原始片段推断具体未完成事项", formatted)
        self.assertIn("相关章节：P2.43、安全边界", formatted)
        self.assertNotIn("a0d945e", formatted)


if __name__ == "__main__":
    unittest.main()
