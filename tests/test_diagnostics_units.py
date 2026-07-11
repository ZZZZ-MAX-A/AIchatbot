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

    def make_config_status_config(self, **overrides):
        values = {
            "bot_name": "AI助手",
            "bot_owner_qq": "10001",
            "bot_owner_public_name": "主人",
            "enable_private_chat": True,
            "enable_group_chat": True,
            "enable_group_auto_reply": True,
            "enable_owner_notifications": True,
            "enable_chat_graph_runtime": True,
            "chat_llm_api_key": "sk-chat-secret-value",
            "chat_llm_base_url": "https://user:pass@chat.example.com/v1/?token=secret",
            "chat_llm_model": "chat-current",
            "chat_llm_timeout_seconds": 45,
            "openai_api_key": "sk-legacy-secret-value",
            "openai_base_url": "https://legacy.example.com/v1",
            "openai_model": "legacy-chat",
            "ai_timeout_seconds": 60,
            "ai_temperature": 0.7,
            "enable_main_agent": True,
            "main_agent_owner_only": True,
            "main_agent_allow_group": False,
            "main_agent_use_llm": True,
            "main_llm_api_key": "sk-main-secret-value",
            "main_llm_base_url": "https://name:password@main.example.com/v1?token=secret",
            "main_llm_model": "main-current",
            "main_llm_timeout_seconds": 60,
            "main_agent_max_steps": 5,
            "main_agent_require_approval_for_writes": True,
            "enable_memory_compression": True,
            "max_context_messages": 40,
            "max_stored_messages_per_session": 120,
            "summary_keep_recent_messages": 40,
            "summary_batch_messages": 80,
            "max_session_summaries_in_context": 1,
            "enable_gap_scene_summaries": True,
            "gap_scene_summary_1_threshold": 40,
            "gap_scene_summary_2_threshold": 80,
            "max_gap_scene_summaries_in_context": 2,
            "enable_long_term_memory_context": True,
            "max_long_term_memories_in_context": 4,
            "enable_memory_rag": True,
            "memory_rag_inject_in_chat": True,
            "enable_project_doc_rag": True,
            "memory_rag_embedding_provider": "ollama",
            "memory_rag_embedding_model": "bge-m3",
            "memory_rag_embedding_base_url": "http://127.0.0.1:11434/?token=secret",
            "memory_rag_embedding_dimension": 1024,
            "memory_rag_top_k": 5,
            "memory_rag_min_score": 0.35,
            "memory_rag_max_context_chars": 2400,
            "project_doc_rag_top_k": 5,
            "project_doc_rag_min_score": 0.35,
            "project_doc_rag_max_context_chars": 2400,
            "enable_vision": True,
            "vision_ollama_base_url": "http://127.0.0.1:11434/?token=secret",
            "vision_model": "qwen2.5vl:3b",
            "vision_timeout_seconds": 180,
            "vision_num_ctx": 16384,
            "vision_max_images": 1,
            "vision_max_image_bytes": 5242880,
            "vision_image_cache_ttl_seconds": 120,
            "vision_private_image_wait_seconds": 5,
            "enable_tts": True,
            "tts_service_url": "http://127.0.0.1:9880/?token=secret",
            "tts_auto_start": True,
            "tts_voice": "default",
            "tts_emotion": "neutral",
            "tts_timeout_seconds": 180,
            "tts_max_chars": 500,
            "tts_max_total_seconds": 120,
            "tts_cooldown_seconds": 5,
            "enable_agent_web": False,
            "enable_agent_shell": False,
            "enable_agent_local_write": False,
            "enable_agent_external_write": False,
            "group_auto_reply_threshold": 80,
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def test_format_config_status_uses_current_runtime_sections_and_redacts_urls(self):
        reply = self.diagnostics.format_config_status(self.make_config_status_config())

        for heading in (
            "基础与入口：",
            "聊天模型：",
            "MainAgent：",
            "记忆与 RAG：",
            "视觉：",
            "语音：",
            "MainAgent 高风险边界：",
        ):
            self.assertIn(heading, reply)
        self.assertIn("聊天运行链路：ChatGraph/RootGraph", reply)
        self.assertIn("模型：chat-current", reply)
        self.assertIn("Main LLM 模型：main-current", reply)
        self.assertIn("MemoryRAG：开启", reply)
        self.assertIn("ProjectDocRAG：开启", reply)
        self.assertIn("单图上限：5 MiB", reply)
        self.assertIn("地址范围：本机 loopback", reply)
        self.assertIn("主人管理写：审批门控", reply)
        self.assertIn("不代表服务在线、模型已加载或端到端功能已经验证", reply)
        self.assertIn("https://chat.example.com/v1", reply)
        self.assertIn("https://main.example.com/v1", reply)
        self.assertNotIn("legacy-chat", reply)
        for secret in ("sk-chat", "sk-main", "password", "token=", "user:pass"):
            self.assertNotIn(secret, reply)

    def test_format_config_status_uses_legacy_chat_fields_when_graph_is_disabled(self):
        reply = self.diagnostics.format_config_status(
            self.make_config_status_config(enable_chat_graph_runtime=False)
        )

        self.assertIn("聊天运行链路：兼容聊天链路", reply)
        self.assertIn("模型：legacy-chat", reply)
        self.assertIn("接口：https://legacy.example.com/v1", reply)
        self.assertNotIn("模型：chat-current", reply)

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
