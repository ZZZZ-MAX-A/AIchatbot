from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from pure_ai_chat_loader import load_pure_graph_modules


class RootGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.state = cls.modules["state"]
        cls.root = cls.modules["root"]
        cls.runtime = cls.modules["runtime"]

    def make_runtime_state(self, *, intent=None, response: str | None = None):
        return self.state.RuntimeState(
            event=self.state.EventContext(
                message_id="9001",
                raw_text="hello",
                plain_text="hello",
            ),
            actor=self.state.ActorContext(
                user_id="10001",
                role=self.state.ActorRole.OWNER,
            ),
            session=self.state.SessionContext(
                session_type=self.state.SessionType.PRIVATE,
                session_key="private:10001",
            ),
            intent=intent,
            response=response,
        )

    def test_root_graph_runner_dispatches_chat_intent_to_registered_handler(self):
        calls = []
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        async def chat_handler(runtime_state):
            calls.append(runtime_state)
            return self.runtime.RuntimeResponse("chat reply")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertEqual(response.text, "chat reply")
        self.assertTrue(response.should_reply)
        self.assertEqual(calls, [state])
        self.assertEqual(
            state.artifacts["root_graph"]["node_trace"],
            tuple(node.value for node in self.root.ROOT_NODE_SEQUENCE),
        )
        self.assertEqual(state.artifacts["root_graph"]["route"], "chat")
        self.assertTrue(state.artifacts["root_graph"]["dispatched"])
        self.assertEqual(state.artifacts["policy"]["decision"], "allow")
        self.assertEqual(state.artifacts["context"]["context_level"], "chat_context")
        self.assertTrue(state.artifacts["context"]["memory_rag_enabled"])
        self.assertTrue(state.artifacts["commit"]["handler_dispatched"])

    def test_root_graph_runner_ignores_missing_intent_without_dispatching(self):
        state = self.make_runtime_state(intent=None)
        runner = self.runtime.RootGraphRunner(
            handlers={
                self.state.RuntimeIntent.CHAT: lambda _: self.runtime.RuntimeResponse("unused")
            }
        )

        response = asyncio.run(runner.run(state))

        self.assertFalse(response.should_reply)
        self.assertEqual(response.text, "")
        self.assertEqual(state.artifacts["root_graph"]["route"], "ignore")
        self.assertFalse(state.artifacts["root_graph"]["dispatched"])
        self.assertEqual(state.artifacts["policy"]["decision"], "ignore")
        self.assertFalse(state.artifacts["policy"]["allow_dispatch"])

    def test_root_graph_runner_dispatches_main_agent_for_owner_private(self):
        calls = []
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.MAIN_AGENT)

        async def main_agent_handler(runtime_state):
            calls.append(runtime_state)
            return self.runtime.RuntimeResponse("main agent reply")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.MAIN_AGENT: main_agent_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertEqual(response.text, "main agent reply")
        self.assertTrue(response.should_reply)
        self.assertEqual(calls, [state])
        self.assertEqual(state.artifacts["root_graph"]["route"], "main_agent")
        self.assertTrue(state.artifacts["root_graph"]["dispatched"])
        self.assertEqual(state.artifacts["context"]["context_level"], "minimal_context")
        self.assertEqual(
            state.artifacts["context"]["project_doc_rag_scope"],
            "dev_context_tool_only",
        )

    def test_root_graph_runner_denies_non_owner_main_agent_before_handler(self):
        calls = []
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.MAIN_AGENT)
        state.actor = self.state.ActorContext(
            user_id="20002",
            role=self.state.ActorRole.USER,
        )

        async def main_agent_handler(_runtime_state):
            calls.append("called")
            return self.runtime.RuntimeResponse("unused")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.MAIN_AGENT: main_agent_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertTrue(response.should_reply)
        self.assertIn("owner access is required", response.text)
        self.assertEqual(calls, [])
        self.assertEqual(state.error, "permission_denied")
        self.assertEqual(state.artifacts["policy"]["decision"], "denied")
        self.assertEqual(state.artifacts["root_graph"]["route"], "ignore")
        self.assertFalse(state.artifacts["root_graph"]["dispatched"])

    def test_root_graph_runner_denies_chat_from_access_policy_before_handler(self):
        calls = []
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)
        state.artifacts["chat_access_policy"] = {
            "allow_dispatch": False,
            "decision": "rate_limited",
            "reason": "chat rate limit is active",
            "should_reply": True,
            "response_text": "slow down",
            "error": "rate_limited",
        }

        async def chat_handler(_runtime_state):
            calls.append("called")
            return self.runtime.RuntimeResponse("unused")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertEqual(response.text, "slow down")
        self.assertTrue(response.should_reply)
        self.assertEqual(calls, [])
        self.assertEqual(state.error, "rate_limited")
        self.assertEqual(state.artifacts["policy"]["decision"], "rate_limited")
        self.assertEqual(state.artifacts["root_graph"]["route"], "ignore")
        self.assertFalse(state.artifacts["root_graph"]["dispatched"])

    def test_root_graph_runner_silently_denies_chat_from_access_policy(self):
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)
        state.artifacts["chat_access_policy"] = {
            "allow_dispatch": False,
            "decision": "group_denied",
            "reason": "group chat is not allowed",
            "should_reply": False,
            "response_text": "",
            "error": "permission_denied",
        }

        runner = self.runtime.RootGraphRunner(
            handlers={
                self.state.RuntimeIntent.CHAT: lambda _: self.runtime.RuntimeResponse("unused")
            }
        )

        response = asyncio.run(runner.run(state))

        self.assertEqual(response.text, "")
        self.assertFalse(response.should_reply)
        self.assertEqual(state.error, "permission_denied")
        self.assertEqual(state.artifacts["policy"]["decision"], "group_denied")
        self.assertFalse(state.artifacts["policy"]["allow_dispatch"])
        self.assertFalse(state.artifacts["root_graph"]["dispatched"])

    def test_root_graph_runner_catches_handler_error_and_records_artifact(self):
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        async def chat_handler(_runtime_state):
            raise RuntimeError("boom")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertTrue(response.should_reply)
        self.assertIn("RuntimeError: boom", response.text)
        self.assertEqual(state.error, "RuntimeError: boom")
        self.assertEqual(state.artifacts["root_graph"]["error"], "RuntimeError: boom")
        self.assertFalse(state.artifacts["root_graph"]["dispatched"])

    def test_root_graph_runner_can_passthrough_control_exceptions(self):
        class ControlException(Exception):
            pass

        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        async def chat_handler(_runtime_state):
            raise ControlException("finish")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler},
            passthrough_exceptions=(ControlException,),
        )

        with self.assertRaises(ControlException):
            asyncio.run(runner.run(state))

    def test_root_graph_runner_keeps_side_effectful_chat_response_non_rendering(self):
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        async def chat_handler(runtime_state):
            runtime_state.response = "already sent"
            runtime_state.artifacts["chat_graph"] = {"status": "complete"}
            runtime_state.artifacts["chat_commit"] = {
                "qq_reply_sent": True,
                "persisted_turn_saved": True,
                "trial_updated": True,
                "compression_scheduled": True,
                "tts_candidate_updated": True,
            }
            runtime_state.artifacts["chat_runtime"] = {"stage": "dispatched"}
            return self.runtime.RuntimeResponse("already sent", should_reply=False)

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertEqual(response.text, "already sent")
        self.assertFalse(response.should_reply)
        self.assertEqual(state.response, "already sent")
        self.assertTrue(state.artifacts["root_graph"]["dispatched"])
        self.assertTrue(state.artifacts["commit"]["chat_graph_completed"])
        self.assertFalse(state.artifacts["commit"]["should_reply"])
        self.assertTrue(state.artifacts["commit"]["chat_reply_sent"])
        self.assertTrue(state.artifacts["commit"]["chat_persisted"])
        self.assertTrue(state.artifacts["commit"]["chat_trial_updated"])
        self.assertTrue(state.artifacts["commit"]["chat_compression_scheduled"])
        self.assertTrue(state.artifacts["commit"]["chat_tts_candidate_updated"])
        self.assertEqual(state.artifacts["commit"]["chat_runtime_stage"], "dispatched")

    def test_root_graph_commit_marks_deferred_chat_image_context(self):
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        async def chat_handler(runtime_state):
            runtime_state.artifacts["chat_runtime"] = {
                "stage": "image_context_deferred"
            }
            runtime_state.artifacts["chat_commit"] = {
                "image_context_deferred": True
            }
            return self.runtime.RuntimeResponse("", should_reply=False)

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertFalse(response.should_reply)
        self.assertTrue(state.artifacts["commit"]["chat_image_context_deferred"])
        self.assertEqual(
            state.artifacts["commit"]["chat_runtime_stage"],
            "image_context_deferred",
        )

    def test_agent_runtime_uses_root_runner_and_preserves_existing_response_fallback(self):
        state = self.make_runtime_state(
            intent=self.state.RuntimeIntent.CHAT,
            response="already rendered",
        )

        response = asyncio.run(self.runtime.AgentRuntime().run(state))

        self.assertEqual(response.text, "already rendered")
        self.assertTrue(response.should_reply)
        self.assertEqual(state.artifacts["root_graph"]["route"], "chat")


class ChatGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.contracts = cls.modules["contracts"]
        cls.state = cls.modules["state"]
        cls.chat = cls.modules["chat"]
        cls.adapters = cls.modules["adapters"]

    def make_chat_state(self, *, semantic_voice: bool = False, text: str = "hello"):
        request = self.contracts.ChatRequest(
            key="private:10001",
            text=text,
            image_context=self.contracts.ChatImageContext(urls=[], has_context=False),
        )
        runtime = self.adapters.runtime_state_from_chat_request(
            request,
            user_id="10001",
            actor_role=self.state.ActorRole.OWNER,
            session_type=self.state.SessionType.PRIVATE,
            message_id="9001",
        )
        options = self.contracts.ChatOptions(
            semantic_voice=semantic_voice,
            semantic_goal="say it aloud" if semantic_voice else "",
            tts_refresh_cache=semantic_voice,
        )
        return self.adapters.chat_state_from_chat_request(runtime, request, options)

    def test_chat_graph_runner_calls_agent_persists_turn_and_renders_result(self):
        state = self.make_chat_state()
        persisted = self.modules["memory"].PersistedTurn(
            session_key="private:10001",
            user_content="hello",
            assistant_content="reply",
            message_type="private",
            user_id="10001",
            group_id=None,
        )
        agent_calls = []
        persist_calls = []

        async def call_chat_agent(chat_state):
            agent_calls.append(chat_state)
            return self.contracts.ChatRuntimeResult(
                reply="reply",
                stored_assistant="reply",
            )

        async def persist_turn(chat_state, runtime_result):
            persist_calls.append((chat_state, runtime_result))
            return persisted

        runner = self.chat.ChatGraphRunner(
            call_chat_agent,
            persist_turn=persist_turn,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(agent_calls, [state])
        self.assertEqual(len(persist_calls), 1)
        self.assertEqual(execution.node_trace, self.chat.CHAT_NODE_SEQUENCE)
        self.assertEqual(execution.result.reply, "reply")
        self.assertTrue(execution.result.should_reply_text)
        self.assertIs(execution.result.persisted_turn, persisted)
        self.assertEqual(execution.state.runtime.response, "reply")
        self.assertEqual(execution.state.runtime.artifacts["chat_graph"]["status"], "complete")
        self.assertEqual(
            execution.state.runtime.artifacts["chat_graph"]["node_trace"],
            tuple(node.value for node in self.chat.CHAT_NODE_SEQUENCE),
        )

    def test_chat_graph_runner_suppresses_text_reply_for_semantic_voice_mode(self):
        state = self.make_chat_state(semantic_voice=True)

        async def call_chat_agent(_):
            return self.contracts.ChatRuntimeResult(
                reply="spoken reply",
                stored_assistant="spoken reply",
                voice_text="spoken reply",
            )

        execution = asyncio.run(self.chat.ChatGraphRunner(call_chat_agent).run(state))

        self.assertFalse(execution.result.should_reply_text)
        self.assertEqual(execution.result.voice_text, "spoken reply")
        self.assertEqual(execution.state.voice_text, "spoken reply")

    def test_chat_graph_runner_allows_voice_node_to_add_voice_text(self):
        state = self.make_chat_state(semantic_voice=True)
        calls = []

        async def call_chat_agent(chat_state):
            calls.append(("agent", chat_state.text))
            return self.contracts.ChatRuntimeResult(
                reply="spoken reply",
                stored_assistant="spoken reply",
            )

        async def maybe_voice_response(chat_state, runtime_result):
            calls.append(("voice", chat_state.text, runtime_result.reply))
            return self.contracts.ChatRuntimeResult(
                reply=runtime_result.reply,
                stored_assistant=runtime_result.stored_assistant,
                voice_text=runtime_result.reply,
            )

        execution = asyncio.run(
            self.chat.ChatGraphRunner(
                call_chat_agent,
                maybe_voice_response=maybe_voice_response,
            ).run(state)
        )

        self.assertEqual(calls, [("agent", "hello"), ("voice", "hello", "spoken reply")])
        self.assertFalse(execution.result.should_reply_text)
        self.assertEqual(execution.result.voice_text, "spoken reply")
        self.assertEqual(execution.state.voice_text, "spoken reply")

    def test_chat_graph_runner_runs_image_and_prompt_hooks_before_agent(self):
        state = self.make_chat_state()
        calls = []

        async def resolve_image_context(chat_state):
            calls.append(("resolve", chat_state.text))
            return self.adapters.chat_state_with_vision_result(
                chat_state,
                descriptions=["image description"],
                context_text="image context",
            )

        async def build_prompt_context(chat_state):
            calls.append(("prompt", tuple(chat_state.vision.descriptions)))
            prompt_context = self.contracts.ChatPromptContext(
                history=[{"role": "system", "content": "ctx"}],
                user_id="10001",
                group_id=None,
            )
            user_content = self.contracts.ChatUserContent(
                original="hello",
                for_llm="hello for llm",
                stored="hello",
            )
            return self.adapters.chat_state_with_prompt_context(
                chat_state,
                prompt_context,
                user_content,
                llm_user_content="wrapped",
            )

        async def call_chat_agent(chat_state):
            calls.append(("agent", chat_state.llm_user_content))
            return self.contracts.ChatRuntimeResult(
                reply="reply",
                stored_assistant="reply",
            )

        execution = asyncio.run(
            self.chat.ChatGraphRunner(
                call_chat_agent,
                resolve_image_context=resolve_image_context,
                build_prompt_context=build_prompt_context,
            ).run(state)
        )

        self.assertEqual(
            calls,
            [
                ("resolve", "hello"),
                ("prompt", ("image description",)),
                ("agent", "wrapped"),
            ],
        )
        self.assertEqual(execution.state.vision.context_text, "image context")
        self.assertEqual(execution.state.history, [{"role": "system", "content": "ctx"}])

    def test_chat_graph_runner_runs_postprocess_hooks_after_agent(self):
        state = self.make_chat_state()
        calls = []
        persisted = self.modules["memory"].PersistedTurn(
            session_key="private:10001",
            user_content="hello",
            assistant_content="reply",
            message_type="private",
            user_id="10001",
            group_id=None,
        )

        async def call_chat_agent(chat_state):
            calls.append(("agent", chat_state.text))
            return self.contracts.ChatRuntimeResult(
                reply="reply",
                stored_assistant="reply",
            )

        async def persist_turn(chat_state, runtime_result):
            calls.append(("persist", chat_state.text, runtime_result.reply))
            return persisted

        async def update_trial_accounting(chat_state, runtime_result):
            calls.append(("trial", chat_state.text, runtime_result.reply))
            return chat_state

        async def update_tts_candidate(chat_state, runtime_result):
            calls.append(("tts", chat_state.text, runtime_result.reply))
            return chat_state

        async def schedule_compression(chat_state, runtime_result):
            calls.append(("compression", chat_state.text, runtime_result.reply))
            return chat_state

        execution = asyncio.run(
            self.chat.ChatGraphRunner(
                call_chat_agent,
                persist_turn=persist_turn,
                update_trial_accounting=update_trial_accounting,
                update_tts_candidate=update_tts_candidate,
                schedule_compression=schedule_compression,
            ).run(state)
        )

        self.assertEqual(
            calls,
            [
                ("agent", "hello"),
                ("persist", "hello", "reply"),
                ("trial", "hello", "reply"),
                ("tts", "hello", "reply"),
                ("compression", "hello", "reply"),
            ],
        )
        self.assertIs(execution.result.persisted_turn, persisted)

    def test_chat_graph_runner_rejects_empty_input_before_agent_call(self):
        state = self.make_chat_state(text="")

        async def call_chat_agent(_):
            raise AssertionError("agent should not be called")

        execution = asyncio.run(self.chat.ChatGraphRunner(call_chat_agent).run(state))

        self.assertFalse(execution.result.should_reply_text)
        self.assertEqual(execution.result.reply, "")
        self.assertEqual(execution.node_trace, (self.chat.ChatNode.VALIDATE_INPUT,))
        self.assertEqual(execution.state.runtime.error, "chat input is empty")
        self.assertEqual(execution.state.runtime.artifacts["chat_graph"]["status"], "invalid")


class MemoryGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.memory = cls.modules["memory"]

    def test_memory_context_graph_runner_builds_manual_context_before_history(self):
        state = self.memory.MemoryContext(
            session_key="private:10001",
            system_contexts=["base"],
        )
        calls = []

        async def ensure_gap(memory_state):
            calls.append(("gap", memory_state.session_key))
            return memory_state

        async def build_manual(memory_state):
            calls.append(("manual", tuple(memory_state.system_contexts)))
            memory_state.manual_long_term_context = "manual memory"
            memory_state.system_contexts.append(memory_state.manual_long_term_context)
            return memory_state

        async def retrieve_semantic(memory_state):
            calls.append(("semantic", tuple(memory_state.system_contexts), memory_state.query))
            memory_state.semantic_memory_context = "semantic memory"
            memory_state.semantic_memory_result_count = 1
            memory_state.system_contexts.append(memory_state.semantic_memory_context)
            return memory_state

        async def build_history(memory_state):
            calls.append(("history", tuple(memory_state.system_contexts)))
            memory_state.rule_reminder_context = "rule reminder"
            memory_state.history = [
                {"role": "system", "content": context}
                for context in memory_state.system_contexts
            ]
            memory_state.history.append(
                {"role": "system", "content": memory_state.rule_reminder_context}
            )
            return memory_state

        runner = self.memory.MemoryContextGraphRunner(
            ensure_gap_scene=ensure_gap,
            build_manual_memory_context=build_manual,
            retrieve_semantic_memory=retrieve_semantic,
            build_history=build_history,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.memory.MEMORY_CONTEXT_NODE_SEQUENCE)
        self.assertEqual(execution.result.manual_long_term_context, "manual memory")
        self.assertEqual(execution.result.semantic_memory_context, "semantic memory")
        self.assertEqual(execution.result.semantic_memory_result_count, 1)
        self.assertEqual(execution.result.rule_reminder_context, "rule reminder")
        self.assertEqual(
            [item["content"] for item in execution.result.history],
            ["base", "manual memory", "semantic memory", "rule reminder"],
        )
        self.assertEqual(
            calls,
            [
                ("gap", "private:10001"),
                ("manual", ("base",)),
                ("semantic", ("base", "manual memory"), ""),
                ("history", ("base", "manual memory", "semantic memory")),
            ],
        )

    def test_memory_context_graph_runner_continues_when_gap_node_records_recoverable_error(self):
        state = self.memory.MemoryContext(session_key="private:10001")

        async def ensure_gap(memory_state):
            memory_state.gap_scene_error = "timeout"
            return memory_state

        async def build_manual(memory_state):
            memory_state.manual_long_term_context = "manual"
            return memory_state

        runner = self.memory.MemoryContextGraphRunner(
            ensure_gap_scene=ensure_gap,
            build_manual_memory_context=build_manual,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.gap_scene_error, "timeout")
        self.assertEqual(execution.result.manual_long_term_context, "manual")
        self.assertEqual(execution.node_trace, self.memory.MEMORY_CONTEXT_NODE_SEQUENCE)

    def test_memory_persist_graph_runner_saves_turn_and_schedules_compression(self):
        state = self.memory.MemoryPersistState(
            session_key="private:10001",
            user_content="hello",
            assistant_content="reply",
            message_type="private",
            user_id="10001",
        )
        calls = []

        async def save_user(memory_state):
            calls.append(("user", memory_state.session_key, memory_state.user_content))
            memory_state.user_saved = True
            return memory_state

        async def save_assistant(memory_state):
            calls.append(("assistant", memory_state.session_key, memory_state.assistant_content))
            memory_state.assistant_saved = True
            return memory_state

        async def schedule(memory_state):
            calls.append(("schedule", memory_state.session_key))
            memory_state.compression_scheduled = True
            return memory_state

        runner = self.memory.MemoryPersistGraphRunner(
            save_user_message=save_user,
            save_assistant_message=save_assistant,
            schedule_compression=schedule,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.memory.MEMORY_PERSIST_NODE_SEQUENCE)
        self.assertTrue(execution.result.user_saved)
        self.assertTrue(execution.result.assistant_saved)
        self.assertTrue(execution.result.compression_scheduled)
        self.assertEqual(
            calls,
            [
                ("user", "private:10001", "hello"),
                ("assistant", "private:10001", "reply"),
                ("schedule", "private:10001"),
            ],
        )

    def test_memory_persist_graph_runner_stops_on_save_error(self):
        state = self.memory.MemoryPersistState(
            session_key="private:10001",
            user_content="hello",
        )

        async def save_user(memory_state):
            memory_state.error = "write_failed"
            return memory_state

        async def save_assistant(_):
            raise AssertionError("assistant save should not run after error")

        runner = self.memory.MemoryPersistGraphRunner(
            save_user_message=save_user,
            save_assistant_message=save_assistant,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "write_failed")
        self.assertEqual(
            execution.node_trace,
            (self.memory.MemoryNode.SAVE_USER_MESSAGE,),
        )

    def test_memory_admin_graph_runner_executes_and_renders_reply(self):
        state = self.memory.MemoryAdminState(
            action=self.memory.MemoryAdminAction.ADD_FACT_MEMORY,
            session_key="private:10001",
            content="project fact",
        )
        calls = []

        async def validate(memory_state):
            calls.append(("validate", memory_state.action))
            return memory_state

        async def execute(memory_state):
            calls.append(("execute", memory_state.content))
            memory_state.metadata["memory_id"] = 7
            return memory_state

        async def render(memory_state):
            calls.append(("render", memory_state.metadata["memory_id"]))
            memory_state.reply_text = "已添加事实摘要记忆：ID 7。"
            return memory_state

        runner = self.memory.MemoryAdminGraphRunner(
            validate_admin_request=validate,
            execute_admin_operation=execute,
            render_admin_reply=render,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.memory.MEMORY_ADMIN_NODE_SEQUENCE)
        self.assertEqual(execution.result.reply_text, "已添加事实摘要记忆：ID 7。")
        self.assertEqual(execution.result.metadata["memory_id"], 7)
        self.assertEqual(
            calls,
            [
                ("validate", self.memory.MemoryAdminAction.ADD_FACT_MEMORY),
                ("execute", "project fact"),
                ("render", 7),
            ],
        )

    def test_memory_admin_graph_runner_stops_on_validation_error(self):
        state = self.memory.MemoryAdminState(
            action=self.memory.MemoryAdminAction.DELETE_SUMMARY,
            target_id="not-a-number",
        )

        async def validate(memory_state):
            memory_state.reply_text = "用法：/删除摘要 摘要ID"
            memory_state.error = "validation_failed"
            return memory_state

        async def execute(_):
            raise AssertionError("execute should not run after validation failure")

        runner = self.memory.MemoryAdminGraphRunner(
            validate_admin_request=validate,
            execute_admin_operation=execute,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "validation_failed")
        self.assertEqual(execution.result.reply_text, "用法：/删除摘要 摘要ID")
        self.assertEqual(
            execution.node_trace,
            (self.memory.MemoryAdminNode.VALIDATE_ADMIN_REQUEST,),
        )



class MemoryRetrievalGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.retrieval = cls.modules["retrieval"]

    def test_memory_retrieval_graph_runner_executes_sync_and_async_nodes(self):
        state = self.retrieval.MemoryRetrievalState(
            action=self.retrieval.MemoryRetrievalAction.QUERY,
            query="MemoryRAG",
            is_owner=True,
        )
        calls = []

        def validate(retrieval_state):
            calls.append(("validate", retrieval_state.query))
            return retrieval_state

        async def execute(retrieval_state):
            calls.append(("execute", retrieval_state.is_owner))
            retrieval_state.metadata["result_count"] = 2
            return retrieval_state

        def render(retrieval_state):
            calls.append(("render", retrieval_state.metadata["result_count"]))
            retrieval_state.reply_text = "found 2 memories"
            return retrieval_state

        runner = self.retrieval.MemoryRetrievalGraphRunner(
            validate_retrieval_request=validate,
            execute_retrieval_operation=execute,
            render_retrieval_reply=render,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.retrieval.MEMORY_RETRIEVAL_NODE_SEQUENCE)
        self.assertEqual(execution.result.reply_text, "found 2 memories")
        self.assertEqual(execution.result.metadata["result_count"], 2)
        self.assertEqual(
            calls,
            [
                ("validate", "MemoryRAG"),
                ("execute", True),
                ("render", 2),
            ],
        )

    def test_memory_retrieval_graph_runner_stops_on_validation_error(self):
        state = self.retrieval.MemoryRetrievalState(
            action=self.retrieval.MemoryRetrievalAction.QUERY,
            query="",
        )

        async def validate(retrieval_state):
            retrieval_state.reply_text = "用法：/记忆检索 查询内容"
            retrieval_state.error = "validation_failed"
            return retrieval_state

        async def execute(_):
            raise AssertionError("execute should not run after validation failure")

        runner = self.retrieval.MemoryRetrievalGraphRunner(
            validate_retrieval_request=validate,
            execute_retrieval_operation=execute,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "validation_failed")
        self.assertEqual(execution.result.reply_text, "用法：/记忆检索 查询内容")
        self.assertEqual(
            execution.node_trace,
            (self.retrieval.MemoryRetrievalNode.VALIDATE_RETRIEVAL_REQUEST,),
        )


class DevContextGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.dev_context = cls.modules["dev_context"]

    def test_dev_context_graph_runner_executes_sync_and_async_nodes(self):
        state = self.dev_context.DevContextState(
            query="CombinedRAG",
            is_owner=True,
        )
        calls = []

        def validate(context_state):
            calls.append(("validate", context_state.query))
            return context_state

        async def retrieve(context_state):
            calls.append(("retrieve", context_state.is_owner))
            context_state.project_result_count = 2
            context_state.memory_result_count = 1
            context_state.metadata["query"] = context_state.query
            return context_state

        def render(context_state):
            calls.append(("render", context_state.project_result_count, context_state.memory_result_count))
            context_state.context_text = "dev context ready"
            return context_state

        runner = self.dev_context.DevContextGraphRunner(
            validate_context_request=validate,
            retrieve_combined_context=retrieve,
            render_context_artifact=render,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.dev_context.DEV_CONTEXT_NODE_SEQUENCE)
        self.assertEqual(execution.result.context_text, "dev context ready")
        self.assertEqual(execution.result.project_result_count, 2)
        self.assertEqual(execution.result.memory_result_count, 1)
        self.assertEqual(execution.result.metadata["query"], "CombinedRAG")
        self.assertEqual(
            calls,
            [
                ("validate", "CombinedRAG"),
                ("retrieve", True),
                ("render", 2, 1),
            ],
        )

    def test_dev_context_graph_runner_stops_on_validation_error(self):
        state = self.dev_context.DevContextState(query="")

        async def validate(context_state):
            context_state.context_text = "请输入开发侧上下文查询。"
            context_state.error = "validation_failed"
            return context_state

        async def retrieve(_):
            raise AssertionError("retrieve should not run after validation failure")

        runner = self.dev_context.DevContextGraphRunner(
            validate_context_request=validate,
            retrieve_combined_context=retrieve,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "validation_failed")
        self.assertEqual(execution.result.context_text, "请输入开发侧上下文查询。")
        self.assertEqual(
            execution.node_trace,
            (self.dev_context.DevContextNode.VALIDATE_CONTEXT_REQUEST,),
        )


class MainAgentGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.main_agent = cls.modules["main_agent"]

    def test_main_agent_graph_runner_executes_read_only_dev_context_tool(self):
        state = self.main_agent.MainAgentState(
            query="恢复项目上下文",
            is_owner=True,
            is_group=False,
        )
        calls = []

        def validate(agent_state):
            calls.append(("validate", agent_state.query))
            return agent_state

        def build_context(agent_state):
            calls.append(("context", agent_state.is_owner, agent_state.is_group))
            agent_state.metadata["mode"] = "read_only"
            return agent_state

        def call_agent(agent_state):
            calls.append(("agent", agent_state.query))
            agent_state.raw_action_request = self.main_agent.dev_context_tool_action_json(
                agent_state.query,
                reason="需要恢复项目上下文",
            )
            return agent_state

        def validate_action(agent_state):
            action_request = self.main_agent.parse_main_agent_action_request(agent_state.raw_action_request)
            self.main_agent.apply_action_request_to_state(agent_state, action_request)
            calls.append(("action", agent_state.action, agent_state.requested_tool))
            return agent_state

        def check_policy(agent_state):
            calls.append(("policy", agent_state.requested_tool))
            agent_state.policy_decision = "allow"
            return agent_state

        async def execute_tool(agent_state):
            calls.append(("execute", agent_state.tool_query))
            agent_state.tool_result = "DevContextGraph result"
            return agent_state

        def render(agent_state):
            calls.append(("render", agent_state.policy_decision))
            agent_state.response_text = f"MainAgentGraph 只读结果：\n{agent_state.tool_result}"
            return agent_state

        runner = self.main_agent.MainAgentGraphRunner(
            validate_agent_request=validate,
            build_agent_context=build_context,
            call_main_agent=call_agent,
            validate_action_request=validate_action,
            check_tool_policy=check_policy,
            execute_tool=execute_tool,
            render_agent_response=render,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.main_agent.MAIN_AGENT_NODE_SEQUENCE)
        self.assertEqual(execution.result.action, self.main_agent.MainAgentAction.TOOL_REQUEST.value)
        self.assertEqual(execution.result.requested_tool, self.main_agent.MainAgentToolName.DEV_CONTEXT.value)
        self.assertEqual(execution.result.policy_decision, "allow")
        self.assertEqual(execution.result.tool_result, "DevContextGraph result")
        self.assertIn("MainAgentGraph 只读结果", execution.result.response_text)
        self.assertEqual(
            calls,
            [
                ("validate", "恢复项目上下文"),
                ("context", True, False),
                ("agent", "恢复项目上下文"),
                ("action", "tool_request", "dev_context"),
                ("policy", "dev_context"),
                ("execute", "恢复项目上下文"),
                ("render", "allow"),
            ],
        )

    def test_main_agent_graph_runner_stops_when_policy_denies_tool(self):
        state = self.main_agent.MainAgentState(
            query="恢复项目上下文",
            is_owner=False,
            is_group=False,
        )

        def call_agent(agent_state):
            agent_state.raw_action_request = self.main_agent.dev_context_tool_action_json(agent_state.query)
            return agent_state

        def validate_action(agent_state):
            action_request = self.main_agent.parse_main_agent_action_request(agent_state.raw_action_request)
            self.main_agent.apply_action_request_to_state(agent_state, action_request)
            return agent_state

        def check_policy(agent_state):
            agent_state.policy_decision = "deny"
            agent_state.policy_reason = "main agent tools require owner access"
            agent_state.response_text = "MainAgentGraph 拒绝执行：main agent tools require owner access"
            agent_state.error = "policy_denied"
            return agent_state

        async def execute_tool(_):
            raise AssertionError("execute_tool should not run after policy denial")

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=call_agent,
            validate_action_request=validate_action,
            check_tool_policy=check_policy,
            execute_tool=execute_tool,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "policy_denied")
        self.assertEqual(execution.result.policy_decision, "deny")
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
                self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST,
                self.main_agent.MainAgentNode.CHECK_TOOL_POLICY,
            ),
        )

    def test_main_agent_dev_context_action_json_builds_valid_tool_request(self):
        raw = self.main_agent.dev_context_tool_action_json("恢复上下文", reason="单元测试")
        action_request = self.main_agent.parse_main_agent_action_request(raw)

        self.assertEqual(action_request.action, self.main_agent.MainAgentAction.TOOL_REQUEST)
        self.assertEqual(action_request.tool_name, self.main_agent.MainAgentToolName.DEV_CONTEXT.value)
        self.assertEqual(action_request.arguments["query"], "恢复上下文")
        self.assertEqual(action_request.reason, "单元测试")

    def test_main_agent_action_parser_accepts_supported_actions(self):
        final_answer = self.main_agent.parse_main_agent_action_request(
            {"action": "final_answer", "content": "完成。"}
        )
        tool_request = self.main_agent.parse_main_agent_action_request(
            {
                "action": "tool_request",
                "tool_name": "dev_context",
                "arguments": {"query": "恢复上下文"},
                "reason": "需要读取项目状态",
            }
        )
        ask_owner = self.main_agent.parse_main_agent_action_request(
            {"action": "ask_owner", "content": "需要确认下一步方向。"}
        )
        stop = self.main_agent.parse_main_agent_action_request(
            {"action": "stop", "reason": "无需继续。"}
        )

        self.assertEqual(final_answer.action, self.main_agent.MainAgentAction.FINAL_ANSWER)
        self.assertEqual(final_answer.content, "完成。")
        self.assertEqual(tool_request.action, self.main_agent.MainAgentAction.TOOL_REQUEST)
        self.assertEqual(tool_request.tool_name, "dev_context")
        self.assertEqual(tool_request.arguments["query"], "恢复上下文")
        self.assertEqual(ask_owner.action, self.main_agent.MainAgentAction.ASK_OWNER)
        self.assertEqual(stop.action, self.main_agent.MainAgentAction.STOP)

    def test_main_agent_action_parser_rejects_malformed_or_unsafe_actions(self):
        invalid_payloads = [
            "not json",
            [],
            {"action": ""},
            {"action": "run_shell", "arguments": {"command": "dir"}},
            {"action": "final_answer"},
            {"action": "ask_owner"},
            {"action": "tool_request", "tool_name": "shell", "arguments": {"query": "x"}},
            {"action": "tool_request", "tool_name": "dev_context", "arguments": {}},
            {"action": "stop", "tool_name": "dev_context"},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(self.main_agent.MainAgentActionRequestError):
                    self.main_agent.parse_main_agent_action_request(payload)

    def test_main_agent_graph_runner_stops_when_action_request_is_malformed(self):
        state = self.main_agent.MainAgentState(
            query="恢复项目上下文",
            is_owner=True,
            is_group=False,
        )

        def call_agent(agent_state):
            agent_state.raw_action_request = {"action": "tool_request", "tool_name": "shell"}
            return agent_state

        def validate_action(agent_state):
            try:
                action_request = self.main_agent.parse_main_agent_action_request(agent_state.raw_action_request)
            except self.main_agent.MainAgentActionRequestError as exc:
                agent_state.response_text = f"MainAgentGraph 拒绝执行：{exc}"
                agent_state.error = "invalid_action_request"
                return agent_state
            self.main_agent.apply_action_request_to_state(agent_state, action_request)
            return agent_state

        async def check_policy(_):
            raise AssertionError("policy should not run after malformed action")

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=call_agent,
            validate_action_request=validate_action,
            check_tool_policy=check_policy,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "invalid_action_request")
        self.assertIn("unsupported tool", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
                self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST,
            ),
        )
class VisionGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.vision = cls.modules["vision"]

    def test_vision_graph_runner_resolves_describes_and_returns_artifact(self):
        state = self.vision.VisionContext(
            text="what is this",
            has_image=True,
        )
        calls = []

        async def extract_urls(vision_state):
            calls.append(("extract", vision_state.has_image))
            vision_state.image_urls = ["https://example.test/a.png"]
            vision_state.has_image_context = True
            return vision_state

        async def cache_policy(vision_state):
            calls.append(("cache", tuple(vision_state.image_urls)))
            return vision_state

        async def access(vision_state):
            calls.append(("access", vision_state.has_image_context))
            return vision_state

        async def describe(vision_state):
            calls.append(("describe", tuple(vision_state.image_urls)))
            vision_state.descriptions = ["raw image description"]
            return vision_state

        async def sanitize(vision_state):
            calls.append(("sanitize", tuple(vision_state.descriptions)))
            vision_state.descriptions = [description.upper() for description in vision_state.descriptions]
            vision_state.context_text = "\n".join(vision_state.descriptions)
            return vision_state

        async def return_artifact(vision_state):
            calls.append(("return", vision_state.context_text))
            return vision_state

        runner = self.vision.VisionGraphRunner(
            extract_image_urls=extract_urls,
            apply_image_cache_policy=cache_policy,
            check_vision_access=access,
            describe_images=describe,
            sanitize_image_context=sanitize,
            return_image_artifact=return_artifact,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.vision.VISION_NODE_SEQUENCE)
        self.assertEqual(execution.result.image_urls, ("https://example.test/a.png",))
        self.assertTrue(execution.result.has_image_context)
        self.assertTrue(execution.result.should_continue)
        self.assertEqual(execution.result.artifact.descriptions, ("RAW IMAGE DESCRIPTION",))
        self.assertEqual(execution.result.artifact.context_text, "RAW IMAGE DESCRIPTION")
        self.assertEqual(
            calls,
            [
                ("extract", True),
                ("cache", ("https://example.test/a.png",)),
                ("access", True),
                ("describe", ("https://example.test/a.png",)),
                ("sanitize", ("raw image description",)),
                ("return", "RAW IMAGE DESCRIPTION"),
            ],
        )

    def test_vision_graph_runner_stops_when_cache_policy_defers_message(self):
        state = self.vision.VisionContext(
            text="",
            has_image=True,
            image_urls=["https://example.test/a.png"],
            has_image_context=True,
        )

        async def cache_policy(vision_state):
            vision_state.should_continue = False
            vision_state.image_urls = []
            vision_state.has_image_context = False
            return vision_state

        async def access(_):
            raise AssertionError("vision access should not run after cache policy stops")

        runner = self.vision.VisionGraphRunner(
            apply_image_cache_policy=cache_policy,
            check_vision_access=access,
        )

        execution = asyncio.run(runner.run(state))

        self.assertFalse(execution.result.should_continue)
        self.assertFalse(execution.result.has_image_context)
        self.assertEqual(execution.result.image_urls, ())
        self.assertEqual(
            execution.node_trace,
            (
                self.vision.VisionNode.EXTRACT_IMAGE_URLS,
                self.vision.VisionNode.APPLY_IMAGE_CACHE_POLICY,
            ),
        )

    def test_vision_graph_runner_stops_on_error(self):
        state = self.vision.VisionContext(has_image=True)

        async def access(vision_state):
            vision_state.error = "vision_disabled"
            return vision_state

        async def describe(_):
            raise AssertionError("describe should not run after vision error")

        runner = self.vision.VisionGraphRunner(
            check_vision_access=access,
            describe_images=describe,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "vision_disabled")
        self.assertEqual(
            execution.node_trace,
            (
                self.vision.VisionNode.EXTRACT_IMAGE_URLS,
                self.vision.VisionNode.APPLY_IMAGE_CACHE_POLICY,
                self.vision.VisionNode.CHECK_VISION_ACCESS,
            ),
        )


class VoiceGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.voice = cls.modules["voice"]

    def test_voice_graph_runner_generates_and_sends_direct_text(self):
        state = self.voice.VoiceState(
            mode=self.voice.VoiceMode.DIRECT_TEXT,
            source_text="hello",
        )
        calls = []

        async def check_policy(voice_state):
            calls.append(("policy", voice_state.source_text))
            return voice_state

        async def select_text(voice_state):
            calls.append(("select", voice_state.source_text))
            return voice_state

        async def maybe_agent(voice_state):
            calls.append(("agent", voice_state.mode.value))
            return voice_state

        async def adapt(voice_state):
            calls.append(("adapt", voice_state.source_text))
            voice_state.adapted_text = voice_state.source_text.upper()
            voice_state.voice_text = voice_state.adapted_text
            return voice_state

        async def health(voice_state):
            calls.append(("health", voice_state.voice_text))
            return voice_state

        async def generate(voice_state):
            calls.append(("generate", voice_state.voice_text))
            voice_state.audio_path = Path("voice.wav")
            voice_state.duration_seconds = 1.25
            return voice_state

        async def send(voice_state):
            calls.append(("send", str(voice_state.audio_path)))
            voice_state.sent = True
            return voice_state

        runner = self.voice.VoiceGraphRunner(
            check_voice_policy=check_policy,
            select_text_source=select_text,
            maybe_call_chat_agent=maybe_agent,
            adapt_speech_text=adapt,
            check_tts_health=health,
            generate_tts=generate,
            send_private_record=send,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.voice.VOICE_NODE_SEQUENCE)
        self.assertTrue(execution.result.sent)
        self.assertEqual(execution.result.voice_text, "HELLO")
        self.assertEqual(execution.result.duration_seconds, 1.25)
        self.assertEqual(
            calls,
            [
                ("policy", "hello"),
                ("select", "hello"),
                ("agent", "direct_text"),
                ("adapt", "hello"),
                ("health", "HELLO"),
                ("generate", "HELLO"),
                ("send", "voice.wav"),
            ],
        )

    def test_voice_graph_runner_lets_semantic_agent_fill_source_text(self):
        state = self.voice.VoiceState(
            mode=self.voice.VoiceMode.SEMANTIC_REPLY,
            semantic_goal="say good night",
        )

        async def maybe_agent(voice_state):
            voice_state.source_text = "good night"
            return voice_state

        async def adapt(voice_state):
            voice_state.adapted_text = voice_state.source_text
            voice_state.voice_text = voice_state.source_text
            return voice_state

        runner = self.voice.VoiceGraphRunner(
            maybe_call_chat_agent=maybe_agent,
            adapt_speech_text=adapt,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.voice_text, "good night")
        self.assertEqual(execution.node_trace, self.voice.VOICE_NODE_SEQUENCE)

    def test_voice_graph_runner_stops_when_policy_sets_error(self):
        state = self.voice.VoiceState(
            mode=self.voice.VoiceMode.LAST_REPLY,
        )

        async def check_policy(voice_state):
            voice_state.error = "not_owner"
            return voice_state

        async def select_text(_):
            raise AssertionError("select_text should not run after policy error")

        runner = self.voice.VoiceGraphRunner(
            check_voice_policy=check_policy,
            select_text_source=select_text,
        )

        execution = asyncio.run(runner.run(state))

        self.assertFalse(execution.result.sent)
        self.assertEqual(execution.result.error, "not_owner")
        self.assertEqual(
            execution.node_trace,
            (
                self.voice.VoiceNode.PARSE_VOICE_INTENT,
                self.voice.VoiceNode.CHECK_VOICE_POLICY,
            ),
        )


class DiagnosticsGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.diagnostics = cls.modules["diagnostics"]

    def test_diagnostics_graph_runner_collects_snapshots_and_renders_reply(self):
        state = self.diagnostics.DiagnosticsState(
            view=self.diagnostics.DiagnosticsView.FULL,
            requester_id="10001",
            session_key="private:10001",
        )
        calls = []

        async def read_config(diag_state):
            calls.append("config")
            diag_state.config_snapshot = {"bot_name": "AI"}
            return diag_state

        async def read_runtime(diag_state):
            calls.append("runtime")
            diag_state.runtime_flags = {"enable_chat_graph_runtime": True}
            return diag_state

        async def check_tts(diag_state):
            calls.append("tts")
            diag_state.tts_health = {"ok": True, "loaded": True}
            return diag_state

        async def read_errors(diag_state):
            calls.append("errors")
            diag_state.recent_errors = ("error one",)
            return diag_state

        async def read_memory(diag_state):
            calls.append("memory")
            diag_state.memory_stats = {"message_count": 12}
            return diag_state

        async def read_images(diag_state):
            calls.append("images")
            diag_state.image_cache_stats = {"total": 2}
            return diag_state

        async def render(diag_state):
            calls.append("render")
            diag_state.reply_text = (
                f"{diag_state.config_snapshot['bot_name']} "
                f"{diag_state.memory_stats['message_count']} "
                f"{diag_state.image_cache_stats['total']}"
            )
            return diag_state

        runner = self.diagnostics.DiagnosticsGraphRunner(
            read_config_snapshot=read_config,
            read_runtime_flags=read_runtime,
            check_tts_health=check_tts,
            read_recent_errors=read_errors,
            read_memory_stats=read_memory,
            read_image_cache_stats=read_images,
            render_diagnostic_reply=render,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.diagnostics.DIAGNOSTICS_NODE_SEQUENCE)
        self.assertEqual(execution.state.view, self.diagnostics.DiagnosticsView.FULL)
        self.assertEqual(calls, ["config", "runtime", "tts", "errors", "memory", "images", "render"])
        self.assertEqual(execution.result.reply_text, "AI 12 2")
        self.assertTrue(execution.result.should_reply)

    def test_diagnostics_graph_runner_stops_when_node_sets_error(self):
        state = self.diagnostics.DiagnosticsState()

        async def read_config(diag_state):
            diag_state.error = "config failed"
            return diag_state

        async def read_runtime(_):
            raise AssertionError("runtime node should not run after error")

        runner = self.diagnostics.DiagnosticsGraphRunner(
            read_config_snapshot=read_config,
            read_runtime_flags=read_runtime,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "config failed")
        self.assertFalse(execution.result.should_reply)
        self.assertEqual(
            execution.node_trace,
            (self.diagnostics.DiagnosticsNode.READ_CONFIG_SNAPSHOT,),
        )


class NotificationGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.notification = cls.modules["notification"]

    def test_notification_graph_runner_sends_and_renders_source_reply(self):
        state = self.notification.NotificationState(
            content="hello owner",
            requester_id="20002",
            session_key="private:20002",
            owner_user_id="10001",
        )
        calls = []

        async def check_policy(notification_state):
            calls.append(("policy", notification_state.requester_id))
            return notification_state

        async def validate_content(notification_state):
            calls.append(("validate", notification_state.content))
            return notification_state

        async def check_cooldown(notification_state):
            calls.append(("cooldown", notification_state.session_key))
            return notification_state

        async def format_message(notification_state):
            calls.append(("format", notification_state.content))
            notification_state.target_message = "target message"
            return notification_state

        async def send_message(notification_state):
            calls.append(("send", notification_state.owner_user_id, notification_state.target_message))
            notification_state.sent = True
            return notification_state

        async def render_reply(notification_state):
            calls.append(("render", notification_state.sent))
            notification_state.source_reply = "sent"
            return notification_state

        runner = self.notification.NotificationGraphRunner(
            check_notification_policy=check_policy,
            validate_notification_content=validate_content,
            check_notification_cooldown=check_cooldown,
            format_owner_notification=format_message,
            send_owner_private_message=send_message,
            render_source_reply=render_reply,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.notification.NOTIFICATION_NODE_SEQUENCE)
        self.assertTrue(execution.result.sent)
        self.assertEqual(execution.result.source_reply, "sent")
        self.assertEqual(execution.result.target_message, "target message")
        self.assertEqual(
            calls,
            [
                ("policy", "20002"),
                ("validate", "hello owner"),
                ("cooldown", "private:20002"),
                ("format", "hello owner"),
                ("send", "10001", "target message"),
                ("render", True),
            ],
        )

    def test_notification_graph_runner_stops_on_silent_policy_denial(self):
        state = self.notification.NotificationState(content="hello owner")

        async def check_policy(notification_state):
            notification_state.error = "policy_denied"
            notification_state.should_reply_source = False
            notification_state.deny_reason = None
            return notification_state

        async def validate_content(_):
            raise AssertionError("validation should not run after policy error")

        runner = self.notification.NotificationGraphRunner(
            check_notification_policy=check_policy,
            validate_notification_content=validate_content,
        )

        execution = asyncio.run(runner.run(state))

        self.assertFalse(execution.result.sent)
        self.assertFalse(execution.result.should_reply_source)
        self.assertEqual(execution.result.error, "policy_denied")
        self.assertIsNone(execution.result.deny_reason)
        self.assertEqual(
            execution.node_trace,
            (self.notification.NotificationNode.CHECK_NOTIFICATION_POLICY,),
        )

    def test_notification_graph_runner_stops_on_send_error_before_render(self):
        state = self.notification.NotificationState(
            content="hello owner",
            target_message="target message",
        )

        async def send_message(notification_state):
            notification_state.error = "send_failed"
            notification_state.source_reply = "send failed"
            return notification_state

        async def render_reply(_):
            raise AssertionError("render should not run after send error")

        runner = self.notification.NotificationGraphRunner(
            send_owner_private_message=send_message,
            render_source_reply=render_reply,
        )

        execution = asyncio.run(runner.run(state))

        self.assertFalse(execution.result.sent)
        self.assertEqual(execution.result.error, "send_failed")
        self.assertEqual(execution.result.source_reply, "send failed")
        self.assertEqual(
            execution.node_trace,
            (
                self.notification.NotificationNode.CHECK_NOTIFICATION_POLICY,
                self.notification.NotificationNode.VALIDATE_NOTIFICATION_CONTENT,
                self.notification.NotificationNode.CHECK_NOTIFICATION_COOLDOWN,
                self.notification.NotificationNode.FORMAT_OWNER_NOTIFICATION,
                self.notification.NotificationNode.SEND_OWNER_PRIVATE_MESSAGE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
