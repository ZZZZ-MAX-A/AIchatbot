from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_diagnostics_modules


class DiagnosticsPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_diagnostics_modules()
        cls.diagnostics = cls.modules["diagnostics"]
        cls.vision = cls.modules["vision"]

    def make_vision_config(self, *, enable_vision: bool = True):
        return types.SimpleNamespace(
            enable_vision=enable_vision,
            vision_ollama_base_url="http://127.0.0.1:11434",
            vision_model="qwen2.5vl:3b",
            vision_num_ctx=16384,
            vision_image_cache_ttl_seconds=120,
            vision_private_image_wait_seconds=5,
            vision_max_images=1,
            vision_max_image_bytes=5242880,
        )

    def test_format_vision_status_includes_inference_check_result(self):
        status = self.diagnostics.OllamaStatus(
            self.diagnostics.CheckResult(True, "service-ok"),
            True,
            ("qwen2.5vl:3b",),
        )
        probe = self.vision.VisionInferenceCheck(True, "probe-ok")

        with patch.object(self.diagnostics, "check_ollama", return_value=status):
            with patch.object(self.diagnostics, "check_vision_inference", return_value=probe):
                reply = self.diagnostics.format_vision_status(
                    self.make_vision_config(),
                    {"total": 0, "private": 0, "group": 0},
                )

        self.assertIn("service-ok", reply)
        self.assertIn("probe-ok", reply)

    def test_format_vision_status_skips_inference_when_ollama_is_down(self):
        status = self.diagnostics.OllamaStatus(
            self.diagnostics.CheckResult(False, "service-down"),
            None,
            (),
        )

        with patch.object(self.diagnostics, "check_ollama", return_value=status):
            with patch.object(self.diagnostics, "check_vision_inference") as probe:
                reply = self.diagnostics.format_vision_status(
                    self.make_vision_config(),
                    {"total": 0, "private": 0, "group": 0},
                )

        probe.assert_not_called()
        self.assertIn("service-down", reply)

    def test_vision_troubleshoot_findings_accepts_chinese_normal_status(self):
        findings = self.diagnostics.vision_troubleshoot_findings(
            vision_lines=[
                "视觉识图：开启",
                "Ollama 服务：正常",
                "视觉模型：qwen2.5vl:3b",
                "模型存在：是",
                "推理自检：成功，用时 0.5 秒",
            ],
            recent_errors=[],
            root_lines=[
                "Vision detail：context=是 urls=1 continue=否 descriptions=1 errors=0 low_quality=0 num_ctx=16384",
            ],
        )

        joined = "\n".join(findings)
        self.assertIn("未发现明确的视觉链路硬错误", joined)
        self.assertNotIn("Ollama 服务需要关注", joined)
        self.assertNotIn("视觉推理自检需要关注", joined)

    def test_vision_troubleshoot_findings_reports_positive_root_metrics(self):
        findings = self.diagnostics.vision_troubleshoot_findings(
            vision_lines=[
                "视觉识图：开启",
                "Ollama 服务：正常",
                "模型存在：是",
                "推理自检：成功",
            ],
            recent_errors=[],
            root_lines=[
                "Vision detail：context=是 urls=1 continue=否 descriptions=1 errors=0 low_quality=0 num_ctx=16384",
                "Vision detail：context=是 urls=1 continue=否 descriptions=1 errors=2 low_quality=1 num_ctx=16384",
            ],
        )

        joined = "\n".join(findings)
        self.assertIn("识图错误计数", joined)
        self.assertIn("低质量识图输出", joined)
        self.assertNotIn("未发现明确", joined)

    def test_vision_troubleshoot_findings_suppresses_secondary_checks_when_disabled(self):
        findings = self.diagnostics.vision_troubleshoot_findings(
            vision_lines=[
                "视觉识图：关闭",
                "Ollama 服务：视觉未开启",
                "推理自检：视觉未开启，未执行",
            ],
            recent_errors=[],
            root_lines=[],
        )

        joined = "\n".join(findings)
        self.assertIn("视觉功能当前关闭", joined)
        self.assertNotIn("Ollama 服务需要关注", joined)
        self.assertNotIn("视觉推理自检需要关注", joined)

    def test_memory_rag_troubleshoot_findings_accepts_normal_status(self):
        findings = self.diagnostics.memory_rag_troubleshoot_findings(
            status_lines=[
                "RAG 开关：开启",
                "聊天注入：开启",
                "Embedding 自检：正常，用时 0.2 秒，维度 1024",
                "索引文档数量：3",
                "向量记录数量：3",
                "待索引数量：0",
            ],
            index_lines=[
                "RAG 索引详情：",
                "MemoryRAG：开启",
                "- semantic_memory/manual_fact：documents=1，active=1，embeddings=1",
            ],
            recent_errors=[],
            root_lines=[
                "MemoryRAG：enabled=是 inject=是 attempted=是 results=1 query_chars=12 context_chars=80 error=否",
                "MemoryRAG hits：事实:1@0.820",
            ],
        )

        joined = "\n".join(findings)
        self.assertIn("未发现明确的 MemoryRAG 硬错误", joined)
        self.assertNotIn("Embedding 自检需要关注", joined)

    def test_memory_rag_troubleshoot_findings_reports_index_and_runtime_issues(self):
        findings = self.diagnostics.memory_rag_troubleshoot_findings(
            status_lines=[
                "RAG 开关：开启",
                "聊天注入：开启",
                "Embedding 自检：失败：connection refused",
                "索引文档数量：0",
                "向量记录数量：0",
                "待索引数量：2",
            ],
            index_lines=["RAG 索引详情：", "- 暂无 RAG 索引记录。"],
            recent_errors=["EmbeddingProviderError: connection refused"],
            root_lines=[
                "MemoryRAG：enabled=是 inject=是 attempted=是 results=0 query_chars=12 context_chars=0 error=是",
                "MemoryRAG error：EmbeddingProviderError",
            ],
        )

        joined = "\n".join(findings)
        self.assertIn("Embedding 自检需要关注", joined)
        self.assertIn("索引文档数量为 0", joined)
        self.assertIn("向量记录数量为 0", joined)
        self.assertIn("还有 2 条待索引内容", joined)
        self.assertIn("MemoryRAG 观测记录了错误", joined)
        self.assertIn("结果数为 0", joined)
        self.assertIn("最近错误日志非空", joined)

    def test_memory_rag_troubleshoot_findings_suppresses_embedding_warning_when_disabled(self):
        findings = self.diagnostics.memory_rag_troubleshoot_findings(
            status_lines=[
                "RAG 开关：关闭",
                "聊天注入：关闭",
                "Embedding 自检：RAG 未开启，未执行",
                "索引文档数量：0",
                "向量记录数量：0",
                "待索引数量：0",
            ],
            index_lines=[],
            recent_errors=[],
            root_lines=[],
        )

        joined = "\n".join(findings)
        self.assertIn("MemoryRAG 当前关闭", joined)
        self.assertIn("聊天注入当前关闭", joined)
        self.assertNotIn("Embedding 自检需要关注", joined)
        self.assertNotIn("索引文档数量为 0", joined)


if __name__ == "__main__":
    unittest.main()
