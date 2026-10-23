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
            "aike_llm_api_key": "sk-aike-secret-value",
            "aike_llm_base_url": "https://aike.example.com/v1",
            "aike_llm_model": "aike-chat",
            "aike_llm_timeout_seconds": 60,
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
            "enable_topic_scene_switch": True,
            "topic_scene_switch_owner_only": True,
            "topic_scene_switch_private_only": True,
            "topic_scene_min_source_messages": 4,
            "topic_scene_hint_turns": 3,
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
            "enable_image_gen": True,
            "image_gen_api_key": "sk-image-secret-value",
            "image_gen_base_url": "https://name:password@image.example.com/v1?token=secret",
            "image_gen_model": "grok-imagine-image-quality",
            "image_edit_model": "grok-imagine-image-quality",
            "image_gen_timeout_seconds": 120,
            "image_gen_max_prompt_chars": 1000,
            "image_gen_max_input_bytes": 10485760,
            "image_gen_max_output_bytes": 10485760,
            "image_gen_pending_edit_seconds": 120,
            "image_gen_cooldown_seconds": 30,
            "image_gen_max_requests_per_hour": 10,
            "enable_qwen_space_edit": True,
            "qwen_space_base_url": "https://qwen-space.example/?token=secret",
            "qwen_space_hf_token": "hf-secret-value",
            "qwen_space_submit_timeout_seconds": 60,
            "qwen_space_infer_timeout_seconds": 180,
            "qwen_space_download_timeout_seconds": 300,
            "qwen_space_download_retries": 2,
            "qwen_space_result_ttl_seconds": 1800,
            "qwen_space_max_side": 1024,
            "qwen_space_jpeg_quality": 90,
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
            "图片生成：",
            "Qwen Space 改图：",
            "语音：",
            "MainAgent 高风险边界：",
        ):
            self.assertIn(heading, reply)
        self.assertIn("聊天运行链路：ChatGraph/RootGraph", reply)
        self.assertIn("模型：aike-chat", reply)
        self.assertIn("Main LLM 模型：main-current", reply)
        self.assertIn("MemoryRAG：开启", reply)
        self.assertIn("ProjectDocRAG：开启", reply)
        self.assertIn("单图上限：5 MiB", reply)
        self.assertIn("文生图模型：grok-imagine-image-quality", reply)
        self.assertIn("改图模型：grok-imagine-image-quality", reply)
        self.assertIn("接口：https://image.example.com/v1", reply)
        self.assertIn("地址范围：本机 loopback", reply)
        self.assertIn("主人管理写：审批门控", reply)
        self.assertIn("不代表服务在线、模型已加载或端到端功能已经验证", reply)
        self.assertIn("https://aike.example.com/v1", reply)
        self.assertIn("https://main.example.com/v1", reply)
        self.assertNotIn("legacy-chat", reply)
        for secret in (
            "sk-chat",
            "sk-main",
            "sk-image",
            "hf-secret",
            "password",
            "token=",
            "user:pass",
        ):
            self.assertNotIn(secret, reply)

    def test_format_config_status_uses_legacy_chat_fields_when_graph_is_disabled(self):
        reply = self.diagnostics.format_config_status(
            self.make_config_status_config(enable_chat_graph_runtime=False)
        )

        self.assertIn("聊天运行链路：兼容聊天链路", reply)
        self.assertIn("模型：aike-chat", reply)
        self.assertIn("接口：https://aike.example.com/v1", reply)
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

    def test_format_vision_status_uses_cloud_provider_without_ollama_probe(self):
        config = self.make_vision_config()
        config.vision_provider = "aliyun_bailian"
        config.vision_cloud_model = "qwen3.7-flash"
        config.aliyun_bailian_base_url = "https://name:password@bailian.example/v1?token=secret"
        config.aliyun_bailian_api_key = "TEST-CLOUD-CREDENTIAL"

        with patch.object(self.diagnostics, "check_ollama") as ollama_probe:
            with patch.object(self.diagnostics, "check_vision_inference") as inference_probe:
                reply = self.diagnostics.format_vision_status(
                    config,
                    {"total": 0, "private": 0, "group": 0},
                )

        ollama_probe.assert_not_called()
        inference_probe.assert_not_called()
        self.assertIn("当前提供方：aliyun_bailian", reply)
        self.assertIn("云端模型：qwen3.7-flash", reply)
        self.assertIn("云端 Key：已配置", reply)
        self.assertIn("云端视觉未主动发起远程推理探针", reply)
        self.assertNotIn("password", reply)
        self.assertNotIn("token=", reply)

    def test_format_config_detail_status_only_exposes_primary_models(self):
        reply = self.diagnostics.format_config_detail_status(
            self.make_config_status_config(
                vision_provider="aliyun_bailian",
                vision_cloud_model="qwen3.7-flash",
                aliyun_bailian_base_url="https://user:pass@bailian.example/v1?token=secret",
                aliyun_bailian_api_key="TEST-CLOUD-CREDENTIAL",
                enable_persona_llm_routing=True,
                persona_llm_role_card_keys=frozenset({"linyin", "ROLE-KEY-REDACTION-TEST"}),
                persona_llm_provider="openai",
                persona_llm_api_key="TEST-PERSONA-CREDENTIAL",
                persona_llm_base_url="https://persona.example/v1",
                persona_llm_model="grok-4.5",
                persona_llm_timeout_seconds=90,
                persona_vision_role_card_keys=frozenset({"ROLE-KEY-REDACTION-TEST"}),
                persona_vision_model="vision-model",
                persona_vision_base_url="https://vision.example/v1",
                persona_vision_api_key="TEST-VISION-CREDENTIAL",
                enable_linyin_tts=True,
                linyin_tts_voice="private-voice",
                linyin_tts_emotion="private-emotion",
            ),
            "模型",
        )

        for expected in (
            "配置详情（模型）：",
            "爱可 Chatbot",
            "模型：aike-chat",
            "凛音 Chatbot",
            "模型：grok-4.5",
            "MainAgent",
            "模型：main-current",
            "用途：项目上下文查询、系统状态与运行链路诊断、记忆与 RAG 查询、人格与访问状态查看、Web 公开资料检索、任务与审批工作流、生成并发送 TXT / Word / PPT",
        ):
            self.assertIn(expected, reply)
        for removed_section in (
            "视觉：",
            "人格：",
            "图片：",
            "Qwen：",
            "语音：",
            "记忆：",
            "访问：",
        ):
            self.assertNotIn(removed_section, reply)
        for secret in (
            "TEST-PERSONA-CREDENTIAL",
            "https://persona.example/v1",
            "上下文消息：",
            "ROLE-KEY-REDACTION-TEST",
        ):
            self.assertNotIn(secret, reply)

    def test_format_config_detail_status_compatibility_and_removed_sections(self):
        config = self.make_config_status_config()
        help_reply = self.diagnostics.format_config_detail_status(config)
        all_reply = self.diagnostics.format_config_detail_status(config, "全部")
        alias_reply = self.diagnostics.format_config_detail_status(config, "聊天")
        unknown_reply = self.diagnostics.format_config_detail_status(config, "访问")

        self.assertIn("/配置详情 <模型|TTS|视觉|图片|记忆>", help_reply)
        self.assertIn("当前可用区域：模型、TTS、视觉、图片、记忆", help_reply)
        self.assertIn("配置详情（模型、TTS、视觉、图片、记忆）：", all_reply)
        self.assertIn("【主要 LLM】", all_reply)
        self.assertIn("【语音输出】", all_reply)
        self.assertIn("【图片识别】", all_reply)
        self.assertIn("【图片生成与修改】", all_reply)
        self.assertIn("【会话记忆与摘要】", all_reply)
        self.assertEqual(alias_reply, self.diagnostics.format_config_detail_status(config, "模型"))
        self.assertIn("未知配置区域：访问", unknown_reply)
        self.assertIn("当前可用区域：模型、TTS、视觉、图片、记忆", unknown_reply)

    def test_format_config_detail_status_vision_shows_routes_without_secrets(self):
        config = self.make_config_status_config(
            vision_provider="aliyun_bailian",
            vision_cloud_model="qwen3.7-flash",
            aliyun_bailian_base_url="https://user:pass@bailian.example/v1?token=secret",
            aliyun_bailian_api_key="TEST-CLOUD-CREDENTIAL",
            vision_max_images=1,
            vision_max_image_bytes=5242880,
            enable_persona_vision_routing=True,
            persona_vision_role_card_keys=frozenset({"linyin"}),
            persona_vision_api_key="TEST-PERSONA-VISION-CREDENTIAL",
            persona_vision_base_url="https://persona-vision.example/v1",
            persona_vision_model="grok-4.5",
            persona_routing=types.SimpleNamespace(
                routing_v2_enabled=True,
                binding_errors=(),
                routing_v2_bot_ids=frozenset({"3000000001"}),
                bindings=(
                    types.SimpleNamespace(
                        role_card_key="linyin",
                        bot_self_id="3000000001",
                    ),
                ),
            ),
        )
        reply = self.diagnostics.format_config_detail_status(config, "视觉")

        for expected in (
            "配置详情（视觉）：",
            "说明：这里只展示图片识别的业务配置，不展示接口地址、Key、Token、上下文或角色卡内容。",
            "【图片识别】",
            "功能：已启用",
            "使用范围：聊天图片识别",
            "每轮最多图片：1 张",
            "单图大小上限：5 MiB",
            "爱可 Chatbot",
            "图片识别：已接入默认视觉线路",
            "模型：qwen3.7-flash",
            "凛音 Chatbot",
            "图片识别：已接入独立视觉线路",
            "模型：grok-4.5",
            "当前默认视觉使用云端线路；旧本地 Ollama 不作为当前主视觉线路。",
        ):
            self.assertIn(expected, reply)
        for secret in (
            "TEST-CLOUD-CREDENTIAL",
            "TEST-PERSONA-VISION-CREDENTIAL",
            "https://persona-vision.example/v1",
            "password",
            "token=",
        ):
            self.assertNotIn(secret, reply)

    def test_format_config_detail_status_vision_reports_disabled_and_incomplete_routes(self):
        disabled_reply = self.diagnostics.format_config_detail_status(
            self.make_config_status_config(enable_vision=False),
            "视觉",
        )
        incomplete_reply = self.diagnostics.format_config_detail_status(
            self.make_config_status_config(
                vision_provider="aliyun_bailian",
                vision_cloud_model="qwen3.7-flash",
                aliyun_bailian_base_url="",
                aliyun_bailian_api_key="",
                enable_persona_vision_routing=True,
                persona_vision_role_card_keys=frozenset({"linyin"}),
                persona_vision_model="grok-4.5",
                persona_vision_base_url="",
                persona_vision_api_key="",
            ),
            "视觉",
        )

        self.assertIn("功能：已关闭", disabled_reply)
        self.assertIn("图片识别：未启用", disabled_reply)
        self.assertIn("功能：已启用", incomplete_reply)
        self.assertIn("爱可 Chatbot", incomplete_reply)
        self.assertIn("图片识别：配置不完整", incomplete_reply)
        self.assertIn("凛音 Chatbot", incomplete_reply)
        self.assertNotIn("图片识别：已接入默认视觉线路", incomplete_reply)
        self.assertNotIn("图片识别：已接入独立视觉线路", incomplete_reply)

    def test_format_config_detail_status_image_shows_waiting_contract_without_secrets(self):
        config = self.make_config_status_config(
            enable_image_gen=True,
            image_gen_api_key="TEST-IMAGE-CREDENTIAL",
            image_gen_base_url="https://user:pass@image.example/v1?token=secret",
            image_gen_model="grok-imagine-image-quality",
            image_edit_model="grok-imagine-image-quality",
            image_gen_timeout_seconds=120,
            image_gen_max_prompt_chars=1000,
            image_gen_max_input_bytes=10485760,
            image_gen_max_output_bytes=10485760,
            image_gen_pending_edit_seconds=120,
            image_gen_cooldown_seconds=30,
            image_gen_max_requests_per_hour=10,
            enable_qwen_space_edit=True,
            qwen_space_base_url="https://qwen-space.example/?token=secret",
            qwen_space_hf_token="hf-secret-value",
            qwen_space_submit_timeout_seconds=60,
            qwen_space_infer_timeout_seconds=180,
            qwen_space_download_timeout_seconds=300,
            qwen_space_download_retries=2,
            qwen_space_result_ttl_seconds=1800,
            qwen_space_max_side=1024,
        )
        reply = self.diagnostics.format_config_detail_status(config, "图片")

        for expected in (
            "配置详情（图片）：",
            "说明：这里只展示图片生成与修改的业务配置，不展示接口地址、Key、Token 或内部请求参数。",
            "【图片生成与修改】",
            "使用范围：主人私聊",
            "图片提示词上限：1000 字",
            "普通图片输入上限：10 MiB",
            "普通图片输出上限：10 MiB",
            "单次操作冷却：30 秒",
            "每小时最多请求：10 次",
            "文生图",
            "状态：已接入图片生成线路",
            "接口等待上限：120 秒",
            "失败处理：不会自动重新生成",
            "普通改图",
            "状态：已接入图片修改线路",
            "等待发送待修改图片：120 秒",
            "模型处理等待上限：120 秒",
            "失败处理：不会自动重新修改",
            "Qwen Space 改图",
            "状态：已接入 Qwen Space 改图线路",
            "提交阶段等待上限：60 秒",
            "排队与推理等待上限：180 秒",
            "结果下载单次等待上限：300 秒",
            "结果下载失败重试：2 次",
            "下载最多尝试：3 次（首次下载 + 2 次重试）",
            "已生成结果可重新下载：30 分钟内有效",
            "上传图片最长边：1024 像素",
            "失败处理：下载失败时可以重新下载，不会重复调用模型",
        ):
            self.assertIn(expected, reply)
        for secret in (
            "TEST-IMAGE-CREDENTIAL",
            "hf-secret-value",
            "https://image.example/v1",
            "https://qwen-space.example",
            "password",
            "token=",
        ):
            self.assertNotIn(secret, reply)

    def test_format_config_detail_status_memory_shows_configuration_without_contents(self):
        config = self.make_config_status_config(
            enable_memory_compression=True,
            max_stored_messages_per_session=120,
            summary_keep_recent_messages=40,
            summary_min_source_messages=40,
            summary_batch_messages=80,
            max_session_summaries_in_context=3,
            enable_gap_scene_summaries=True,
            gap_scene_summary_1_threshold=40,
            gap_scene_summary_2_threshold=80,
            max_gap_scene_summaries_in_context=2,
            enable_topic_scene_switch=True,
            topic_scene_switch_owner_only=True,
            topic_scene_switch_private_only=True,
            topic_scene_min_source_messages=4,
            topic_scene_hint_turns=3,
            enable_long_term_memory_context=True,
            max_long_term_memories_in_context=4,
            enable_memory_rag=True,
            enable_project_doc_rag=False,
            memory_rag_embedding_model="bge-m3",
            memory_rag_top_k=5,
            memory_rag_min_score=0.50,
            memory_rag_max_context_chars=1600,
            project_doc_rag_top_k=4,
            project_doc_rag_min_score=0.50,
            project_doc_rag_max_context_chars=2000,
            memory_rag_include_manual_facts=True,
            memory_rag_include_manual_preferences=True,
            memory_rag_include_session_summaries=True,
            memory_rag_include_short_messages=False,
            memory_rag_include_gap_scene_summaries=False,
            memory_rag_inject_in_chat=True,
        )
        reply = self.diagnostics.format_config_detail_status(config, "记忆")

        for expected in (
            "配置详情（记忆）：",
            "【会话记忆与摘要】",
            "自动压缩：已启用",
            "每个会话最多保留原始消息：120 条",
            "保留最近原文：40 条",
            "触发摘要的最低消息数：40 条",
            "每次摘要处理消息数：80 条",
            "带入上下文的正式摘要：3 条",
            "【长期记忆】",
            "带入上下文的长期记忆：最多 4 条",
            "【空窗场景摘要】",
            "当前策略：无状态卡时累计 25 条新消息后首次写入；已有状态卡时每新增 20 条更新",
            "GAP_SCENE_SUMMARY_1_THRESHOLD / GAP_SCENE_SUMMARY_2_THRESHOLD：历史兼容配置，当前调度器不使用",
            "【MemoryRAG 记忆索引】",
            "功能：已启用",
            "聊天注入：已启用",
            "向量模型：bge-m3",
            "每次最多召回：5 条",
            "最低匹配分数：0.5",
            "注入上下文上限：1600 字",
            "- 长期事实记忆：启用",
            "- 短消息：关闭",
            "【ProjectDocRAG 项目文档索引】",
            "功能：已关闭",
            "聊天注入：未启用",
            "每次最多召回：4 条",
            "注入上下文上限：2000 字",
        ):
            self.assertIn(expected, reply)
        for removed_or_sensitive in (
            "作用：",
            "运行方式：",
            "向量维度：",
            "http://127.0.0.1:11434",
            "token=",
            "sk-",
        ):
            self.assertNotIn(removed_or_sensitive, reply)

    def test_format_config_detail_status_tts_shows_business_routes_without_secrets(self):
        config = self.make_config_status_config(
            enable_tts=True,
            tts_voice="default-voice",
            tts_emotion="neutral-emotion",
            tts_auto_start=True,
            tts_max_chars=260,
            tts_max_total_seconds=60,
            tts_cooldown_seconds=20,
            enable_linyin_tts=True,
            linyin_tts_voice="private-voice",
            linyin_tts_emotion="private-emotion",
        )
        reply = self.diagnostics.format_config_detail_status(config, "TTS")

        for expected in (
            "配置详情（TTS）：",
            "说明：这里只展示语音功能的业务配置，不展示服务地址、Key、Token 或内部路径。",
            "【语音输出】",
            "功能：已启用",
            "引擎：IndexTTS2",
            "语言：中文",
            "使用范围：主人私聊",
            "启动方式：按需自动冷启动",
            "文本上限：260 字",
            "单次总时长上限：60 秒",
            "生成冷却：20 秒",
            "爱可 Chatbot",
            "语音输出：已接入默认语音线路",
            "凛音 Chatbot",
            "语音输出：已接入独立语音线路",
            "音色：已配置",
            "情绪：已配置",
        ):
            self.assertIn(expected, reply)
        for secret in (
            "default-voice",
            "neutral-emotion",
            "private-voice",
            "private-emotion",
            "127.0.0.1",
            "token=secret",
        ):
            self.assertNotIn(secret, reply)

    def test_cloud_vision_warnings_use_cloud_contract_instead_of_old_model_field(self):
        config = self.make_config_status_config(
            vision_provider="aliyun_bailian",
            vision_model="",
            vision_cloud_model="qwen3.7-flash",
            aliyun_bailian_base_url="",
            aliyun_bailian_api_key="",
        )

        warnings = self.diagnostics.config_warnings(config)

        self.assertIn("云端视觉已启用，但 ALIYUN_BAILIAN_BASE_URL 未配置。", warnings)
        self.assertIn("云端视觉已启用，但 ALIYUN_BAILIAN_API_KEY 未配置。", warnings)
        self.assertNotIn("VISION_MODEL 为空", "\n".join(warnings))

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

    def test_format_vision_status_suggests_manual_runner_reload_for_low_quality_repeat(self):
        status = self.diagnostics.OllamaStatus(
            self.diagnostics.CheckResult(True, "正常"),
            True,
            ("qwen2.5vl:3b",),
        )
        probe = self.vision.VisionInferenceCheck(
            False,
            "失败：Ollama 返回低质量重复内容，用时 1.3 秒",
        )

        with patch.object(self.diagnostics, "check_ollama", return_value=status):
            with patch.object(self.diagnostics, "check_vision_inference", return_value=probe):
                reply = self.diagnostics.format_vision_status(
                    self.make_vision_config(),
                    {"total": 0, "private": 0, "group": 0},
                )

        self.assertIn("Runner 恢复建议：", reply)
        self.assertIn("当前视觉 runner 可能处于异常状态", reply)
        self.assertIn("ollama stop qwen2.5vl:3b", reply)
        self.assertIn("本次诊断未执行该命令，也未自动重试", reply)

    def test_format_vision_status_does_not_suggest_runner_reload_for_other_failures(self):
        status = self.diagnostics.OllamaStatus(
            self.diagnostics.CheckResult(True, "正常"),
            True,
            ("qwen2.5vl:3b",),
        )
        probe = self.vision.VisionInferenceCheck(False, "失败：Ollama 识别超时")

        with patch.object(self.diagnostics, "check_ollama", return_value=status):
            with patch.object(self.diagnostics, "check_vision_inference", return_value=probe):
                reply = self.diagnostics.format_vision_status(
                    self.make_vision_config(),
                    {"total": 0, "private": 0, "group": 0},
                )

        self.assertNotIn("Runner 恢复建议：", reply)
        self.assertNotIn("ollama stop", reply)

    def test_vision_troubleshoot_findings_accepts_chinese_normal_status(self):
        findings = self.diagnostics.vision_troubleshoot_findings(
            vision_lines=[
                "视觉识图：开启",
                "Ollama 服务：正常",
                "视觉模型：qwen2.5vl:3b",
                "模型存在：是",
                "推理自检：正常，用时 0.5 秒，返回 74 字",
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

    def test_vision_troubleshoot_findings_include_manual_runner_reload_for_repeat(self):
        findings = self.diagnostics.vision_troubleshoot_findings(
            vision_lines=[
                "视觉识图：开启",
                "Ollama 服务：正常",
                "视觉模型：qwen2.5vl:3b",
                "模型存在：是",
                "推理自检：失败：Ollama 返回低质量重复内容，用时 1.3 秒",
            ],
            recent_errors=[],
            root_lines=[],
        )

        joined = "\n".join(findings)
        self.assertIn("当前视觉 runner 可能处于异常状态", joined)
        self.assertIn("ollama stop qwen2.5vl:3b", joined)
        self.assertIn("本次诊断未执行该命令，也未自动重试", joined)

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
