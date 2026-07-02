import unittest

from pure_ai_chat_loader import load_pure_graph_modules


class GraphAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.contracts = cls.modules["contracts"]
        cls.state = cls.modules["state"]
        cls.chat = cls.modules["chat"]
        cls.adapters = cls.modules["adapters"]
        cls.shadow = cls.modules["shadow"]

    def make_request(self):
        return self.contracts.ChatRequest(
            key="group:42",
            text="hello",
            image_context=self.contracts.ChatImageContext(
                urls=["https://example.test/image.png"],
                has_context=True,
            ),
        )

    def make_runtime(self, request):
        return self.adapters.runtime_state_from_chat_request(
            request,
            user_id="10001",
            actor_role=self.state.ActorRole.OWNER,
            session_type=self.state.SessionType.GROUP,
            group_id="42",
            message_id="9001",
            raw_text="@bot hello",
        )

    def make_prompt_context(self):
        return self.contracts.ChatPromptContext(
            history=[
                {"role": "system", "content": "policy"},
                {"role": "user", "content": "previous"},
            ],
            user_id="10001",
            group_id="42",
        )

    def test_runtime_state_from_chat_request_preserves_event_actor_and_session(self):
        request = self.make_request()

        runtime = self.make_runtime(request)

        self.assertEqual(runtime.event.message_id, "9001")
        self.assertEqual(runtime.event.raw_text, "@bot hello")
        self.assertEqual(runtime.event.plain_text, "hello")
        self.assertTrue(runtime.event.has_image)
        self.assertEqual(runtime.actor.user_id, "10001")
        self.assertEqual(runtime.actor.role, self.state.ActorRole.OWNER)
        self.assertEqual(runtime.session.session_type, self.state.SessionType.GROUP)
        self.assertEqual(runtime.session.session_key, "group:42")
        self.assertEqual(runtime.session.group_id, "42")
        self.assertEqual(runtime.intent, self.state.RuntimeIntent.CHAT)
        self.assertEqual(
            runtime.artifacts["legacy_chat_request"],
            {
                "image_urls": ("https://example.test/image.png",),
                "has_image_context": True,
            },
        )

    def test_parse_main_agent_command_text_accepts_agent_prefixes(self):
        self.assertEqual(
            self.adapters.parse_main_agent_command_text("/agent recover context"),
            "recover context",
        )
        self.assertEqual(
            self.adapters.parse_main_agent_command_text("  /main-agent\tstatus  "),
            "status",
        )
        self.assertEqual(self.adapters.parse_main_agent_command_text("/agent"), "")
        self.assertIsNone(self.adapters.parse_main_agent_command_text("/agentx recover"))
        self.assertIsNone(self.adapters.parse_main_agent_command_text("hello /agent recover"))

    def test_runtime_state_from_main_agent_command_builds_main_agent_intent(self):
        runtime = self.adapters.runtime_state_from_main_agent_command(
            "/agent recover project context",
            user_id="10001",
            actor_role=self.state.ActorRole.OWNER,
            session_type=self.state.SessionType.PRIVATE,
            session_key="private:10001",
            message_id="9002",
        )

        self.assertIsNotNone(runtime)
        assert runtime is not None
        self.assertEqual(runtime.event.message_id, "9002")
        self.assertEqual(runtime.event.raw_text, "/agent recover project context")
        self.assertEqual(runtime.event.plain_text, "recover project context")
        self.assertEqual(runtime.actor.role, self.state.ActorRole.OWNER)
        self.assertEqual(runtime.session.session_key, "private:10001")
        self.assertEqual(runtime.intent, self.state.RuntimeIntent.MAIN_AGENT)
        self.assertEqual(
            runtime.artifacts["main_agent_command"]["prefixes"],
            ("/agent", "/main-agent"),
        )

    def test_runtime_state_from_main_agent_command_ignores_non_command_text(self):
        runtime = self.adapters.runtime_state_from_main_agent_command(
            "ordinary chat",
            user_id="10001",
            actor_role=self.state.ActorRole.OWNER,
            session_type=self.state.SessionType.PRIVATE,
            session_key="private:10001",
        )

        self.assertIsNone(runtime)

    def test_chat_state_from_request_maps_semantic_voice_options(self):
        request = self.make_request()
        runtime = self.make_runtime(request)
        options = self.contracts.ChatOptions(
            semantic_voice=True,
            semantic_goal="read the answer aloud",
            preserve_original=True,
            tts_refresh_cache=True,
        )

        state = self.adapters.chat_state_from_chat_request(runtime, request, options)

        self.assertEqual(state.mode, self.chat.ChatMode.SEMANTIC_VOICE)
        self.assertEqual(state.text, "hello")
        self.assertEqual(state.semantic_goal, "read the answer aloud")
        self.assertTrue(state.preserve_original)
        self.assertTrue(state.tts_refresh_cache)
        self.assertTrue(state.vision.has_image)
        self.assertTrue(state.vision.has_image_context)
        self.assertEqual(state.vision.image_urls, ["https://example.test/image.png"])

    def test_prompt_context_and_runtime_result_produce_persistable_chat_state(self):
        request = self.make_request()
        runtime = self.make_runtime(request)
        options = self.contracts.ChatOptions()
        state = self.adapters.chat_state_from_chat_request(runtime, request, options)
        state.runtime.artifacts["shadow_chat"] = {
            "stage": "prompt",
            "production_route": "legacy_chat_runtime",
        }
        prompt_context = self.make_prompt_context()
        user_content = self.contracts.ChatUserContent(
            original="hello\n\n[image]",
            for_llm="hello with image context",
            stored="hello\n\n[image]",
        )

        prompted = self.adapters.chat_state_with_prompt_context(
            state,
            prompt_context,
            user_content,
            llm_user_content="wrapped llm user text",
        )
        visioned = self.adapters.chat_state_with_vision_result(
            prompted,
            descriptions=["a UI screenshot"],
            context_text="image context text",
        )
        turn = self.contracts.ChatTurn("stored user", "stored assistant")
        persisted = self.adapters.persisted_turn_from_chat_turn(
            request,
            prompt_context,
            turn,
            message_type="group",
        )
        result = self.contracts.ChatRuntimeResult(
            reply="assistant reply",
            stored_assistant="stored assistant",
        )
        completed = self.adapters.chat_state_with_runtime_result(
            visioned,
            result,
            options,
            persisted_turn=persisted,
        )

        self.assertEqual(prompted.history, prompt_context.history)
        self.assertIsNot(prompted.history, prompt_context.history)
        self.assertEqual(prompted.memory.history, prompt_context.history)
        self.assertEqual(prompted.original_user_content, "hello\n\n[image]")
        self.assertEqual(prompted.user_content, "hello with image context")
        self.assertEqual(prompted.llm_user_content, "wrapped llm user text")
        self.assertEqual(visioned.vision.descriptions, ["a UI screenshot"])
        self.assertEqual(visioned.vision.context_text, "image context text")
        self.assertEqual(persisted.session_key, "group:42")
        self.assertEqual(persisted.message_type, "group")
        self.assertEqual(persisted.user_id, "10001")
        self.assertEqual(persisted.group_id, "42")
        self.assertEqual(completed.reply, "assistant reply")
        self.assertEqual(completed.runtime.response, "assistant reply")
        self.assertTrue(completed.should_reply_text)
        self.assertIs(completed.persisted_turn, persisted)

    def test_semantic_voice_result_suppresses_text_reply_and_requires_voice_text(self):
        request = self.make_request()
        runtime = self.make_runtime(request)
        options = self.contracts.ChatOptions(semantic_voice=True)
        state = self.adapters.chat_state_from_chat_request(runtime, request, options)
        prompt_context = self.make_prompt_context()
        turn = self.contracts.ChatTurn("stored user", "spoken answer")
        persisted = self.adapters.persisted_turn_from_chat_turn(
            request,
            prompt_context,
            turn,
            message_type="group",
        )
        result = self.contracts.ChatRuntimeResult(
            reply="spoken answer",
            stored_assistant="spoken answer",
            voice_text="spoken answer",
        )

        graph_result = self.adapters.chat_graph_result_from_runtime_result(
            result,
            options,
            persisted_turn=persisted,
        )
        completed = self.adapters.chat_state_with_runtime_result(
            state,
            result,
            options,
            persisted_turn=persisted,
        )

        self.assertFalse(graph_result.should_reply_text)
        self.assertEqual(graph_result.voice_text, "spoken answer")
        self.assertIs(graph_result.persisted_turn, persisted)
        self.assertFalse(completed.should_reply_text)
        self.assertEqual(completed.voice_text, "spoken answer")


class ShadowSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.contracts = cls.modules["contracts"]
        cls.state = cls.modules["state"]
        cls.adapters = cls.modules["adapters"]
        cls.shadow = cls.modules["shadow"]

    def make_complete_state(self):
        request = self.contracts.ChatRequest(
            key="private:10001",
            text="hello",
            image_context=self.contracts.ChatImageContext(
                urls=["https://example.test/image.png"],
                has_context=True,
            ),
        )
        runtime = self.adapters.runtime_state_from_chat_request(
            request,
            user_id="10001",
            actor_role=self.state.ActorRole.USER,
            session_type=self.state.SessionType.PRIVATE,
            message_id="9001",
        )
        runtime.artifacts["shadow_chat"] = {
            "stage": "result",
            "production_route": "legacy_chat_runtime",
        }
        options = self.contracts.ChatOptions()
        state = self.adapters.chat_state_from_chat_request(runtime, request, options)
        state = self.adapters.chat_state_with_vision_result(
            state,
            descriptions=["image description"],
            context_text="image context text",
        )
        prompt_context = self.contracts.ChatPromptContext(
            history=[{"role": "system", "content": "ctx"}],
            user_id="10001",
            group_id=None,
        )
        user_content = self.contracts.ChatUserContent("hello", "hello", "hello")
        state = self.adapters.chat_state_with_prompt_context(
            state,
            prompt_context,
            user_content,
            llm_user_content="wrapped user text",
        )
        turn = self.contracts.ChatTurn("hello", "ok")
        persisted = self.adapters.persisted_turn_from_chat_turn(
            request,
            prompt_context,
            turn,
            message_type="private",
        )
        result = self.contracts.ChatRuntimeResult("ok", "ok")
        return self.adapters.chat_state_with_runtime_result(
            state,
            result,
            options,
            persisted_turn=persisted,
        )

    def make_snapshot(self, **overrides):
        values = {
            "stage": "result",
            "production_route": "legacy_chat_runtime",
            "session_key": "private:10001",
            "session_type": "private",
            "group_id": "",
            "user_id": "10001",
            "actor_role": "user",
            "intent": "chat",
            "mode": "text",
            "message_id": "9001",
            "has_image": False,
            "has_image_context": False,
            "image_url_count": 0,
            "image_description_count": 0,
            "history_count": 1,
            "system_context_count": 0,
            "has_user_content": True,
            "user_content_chars": 5,
            "llm_user_content_chars": 17,
            "has_reply": True,
            "reply_chars": 2,
            "should_reply_text": True,
            "has_voice_text": False,
            "has_persisted_turn": True,
            "has_error": False,
            "tool_event_count": 0,
        }
        values.update(overrides)
        return self.shadow.ShadowChatSnapshot(**values)

    def test_snapshot_from_state_records_summary_without_message_bodies(self):
        state = self.make_complete_state()

        snapshot = self.shadow.shadow_chat_snapshot_from_state(state)
        snapshot_dict = snapshot.as_dict()

        self.assertEqual(snapshot.stage, "result")
        self.assertEqual(snapshot.production_route, "legacy_chat_runtime")
        self.assertEqual(snapshot.session_key, "private:10001")
        self.assertEqual(snapshot.session_type, "private")
        self.assertEqual(snapshot.user_id, "10001")
        self.assertEqual(snapshot.intent, "chat")
        self.assertEqual(snapshot.mode, "text")
        self.assertTrue(snapshot.has_image)
        self.assertEqual(snapshot.image_url_count, 1)
        self.assertEqual(snapshot.image_description_count, 1)
        self.assertEqual(snapshot.history_count, 1)
        self.assertTrue(snapshot.has_user_content)
        self.assertEqual(snapshot.user_content_chars, 5)
        self.assertEqual(snapshot.llm_user_content_chars, 17)
        self.assertTrue(snapshot.has_reply)
        self.assertEqual(snapshot.reply_chars, 2)
        self.assertTrue(snapshot.has_persisted_turn)
        self.assertNotIn("reply", snapshot_dict)
        self.assertNotIn("user_content", snapshot_dict)
        self.assertNotIn("llm_user_content", snapshot_dict)

    def test_complete_result_snapshot_is_valid(self):
        snapshot = self.make_snapshot()

        validation = self.shadow.validate_shadow_chat_snapshot(snapshot)

        self.assertTrue(validation.is_valid)
        self.assertEqual(validation.errors, ())
        self.assertEqual(validation.warnings, ())

    def test_result_snapshot_requires_reply_and_persisted_turn(self):
        snapshot = self.make_snapshot(
            has_reply=False,
            reply_chars=0,
            has_persisted_turn=False,
        )

        validation = self.shadow.validate_shadow_chat_snapshot(snapshot)

        self.assertFalse(validation.is_valid)
        self.assertIn("result-ready stage has no reply", validation.errors)
        self.assertIn("result-ready stage has empty reply", validation.errors)
        self.assertIn("result-ready stage has no persisted turn", validation.errors)

    def test_non_text_result_requires_voice_text(self):
        snapshot = self.make_snapshot(
            should_reply_text=False,
            has_voice_text=False,
        )

        validation = self.shadow.validate_shadow_chat_snapshot(snapshot)

        self.assertFalse(validation.is_valid)
        self.assertIn("non-text result has no voice text", validation.errors)

    def test_prompt_ready_snapshot_requires_history_and_user_content(self):
        snapshot = self.make_snapshot(
            stage="prompt",
            history_count=0,
            has_user_content=False,
            llm_user_content_chars=0,
            has_reply=False,
            reply_chars=0,
            has_persisted_turn=False,
        )

        validation = self.shadow.validate_shadow_chat_snapshot(snapshot)

        self.assertFalse(validation.is_valid)
        self.assertIn("prompt-ready stage has no history", validation.errors)
        self.assertIn("prompt-ready stage has no user content", validation.errors)
        self.assertIn("prompt-ready stage has no llm user content", validation.errors)
        self.assertNotIn("result-ready stage has no reply", validation.errors)


if __name__ == "__main__":
    unittest.main()
