from __future__ import annotations

import asyncio
import unittest

from pure_ai_chat_loader import load_pure_graph_modules, load_pure_policy_modules


class PolicyEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_policy_modules()
        cls.risk = cls.modules["risk"]
        cls.engine = cls.modules["engine"]

    def decide(
        self,
        risk_level,
        *,
        is_owner: bool = True,
        is_group: bool = False,
        enable_external_read: bool = False,
        enable_local_write: bool = False,
        enable_external_write: bool = False,
    ):
        return self.engine.decide_tool_policy(
            self.engine.ToolPolicyInput(
                risk_level=risk_level,
                is_owner=is_owner,
                is_group=is_group,
                enable_external_read=enable_external_read,
                enable_local_write=enable_local_write,
                enable_external_write=enable_external_write,
            )
        )

    def test_internal_and_local_read_tools_are_allowed_for_owner_private_chat(self):
        for risk_level in (self.risk.RiskLevel.INTERNAL, self.risk.RiskLevel.READ_LOCAL):
            with self.subTest(risk_level=risk_level):
                decision = self.decide(risk_level)

                self.assertEqual(decision.type, self.engine.PolicyDecisionType.ALLOW)
                self.assertTrue(decision.allowed)
                self.assertEqual(decision.reason, "")

    def test_tools_are_denied_for_non_owner_even_when_low_risk(self):
        decision = self.decide(self.risk.RiskLevel.INTERNAL, is_owner=False)

        self.assertEqual(decision.type, self.engine.PolicyDecisionType.DENY)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "main agent tools require owner access")

    def test_tools_are_private_only_by_default(self):
        decision = self.decide(self.risk.RiskLevel.INTERNAL, is_group=True)

        self.assertEqual(decision.type, self.engine.PolicyDecisionType.DENY)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "main agent tools are private-only by default")

    def test_external_read_requires_explicit_enable_flag(self):
        disabled = self.decide(self.risk.RiskLevel.READ_EXTERNAL)
        enabled = self.decide(self.risk.RiskLevel.READ_EXTERNAL, enable_external_read=True)

        self.assertEqual(disabled.type, self.engine.PolicyDecisionType.DENY)
        self.assertEqual(disabled.reason, "external reads are disabled")
        self.assertEqual(enabled.type, self.engine.PolicyDecisionType.ALLOW)
        self.assertTrue(enabled.allowed)

    def test_local_and_external_writes_require_approval_when_enabled(self):
        local_disabled = self.decide(self.risk.RiskLevel.WRITE_LOCAL)
        local_enabled = self.decide(self.risk.RiskLevel.WRITE_LOCAL, enable_local_write=True)
        external_disabled = self.decide(self.risk.RiskLevel.WRITE_EXTERNAL)
        external_enabled = self.decide(
            self.risk.RiskLevel.WRITE_EXTERNAL,
            enable_external_write=True,
        )

        self.assertEqual(local_disabled.type, self.engine.PolicyDecisionType.DENY)
        self.assertEqual(local_disabled.reason, "local writes are disabled")
        self.assertEqual(local_enabled.type, self.engine.PolicyDecisionType.REQUIRE_APPROVAL)
        self.assertFalse(local_enabled.allowed)
        self.assertEqual(local_enabled.reason, "local writes require approval")
        self.assertEqual(external_disabled.type, self.engine.PolicyDecisionType.DENY)
        self.assertEqual(external_disabled.reason, "external writes are disabled")
        self.assertEqual(external_enabled.type, self.engine.PolicyDecisionType.REQUIRE_APPROVAL)
        self.assertFalse(external_enabled.allowed)
        self.assertEqual(external_enabled.reason, "external writes require approval")

    def test_dangerous_tools_are_always_denied(self):
        decision = self.decide(
            self.risk.RiskLevel.DANGEROUS,
            is_owner=True,
            is_group=False,
            enable_external_read=True,
            enable_local_write=True,
            enable_external_write=True,
        )

        self.assertEqual(decision.type, self.engine.PolicyDecisionType.DENY)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "dangerous tools are disabled")


class RootRuntimeTests(unittest.TestCase):
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

    def test_route_from_explicit_intent_returns_ignore_when_intent_is_missing(self):
        state = self.make_runtime_state(intent=None)

        decision = self.root.route_from_explicit_intent(state)

        self.assertEqual(decision.intent, self.state.RuntimeIntent.IGNORE)
        self.assertEqual(decision.reason, "intent is not set")

    def test_route_from_explicit_intent_preserves_set_intent(self):
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        decision = self.root.route_from_explicit_intent(state)

        self.assertEqual(decision.intent, self.state.RuntimeIntent.CHAT)
        self.assertEqual(decision.reason, "explicit runtime intent")

    def test_placeholder_runtime_returns_existing_response(self):
        state = self.make_runtime_state(
            intent=self.state.RuntimeIntent.CHAT,
            response="ready",
        )

        response = asyncio.run(self.runtime.AgentRuntime().run(state))

        self.assertEqual(response.text, "ready")
        self.assertTrue(response.should_reply)

    def test_placeholder_runtime_does_not_reply_when_no_response_is_set(self):
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        response = asyncio.run(self.runtime.AgentRuntime().run(state))

        self.assertFalse(response.should_reply)
        self.assertTrue(response.text)


if __name__ == "__main__":
    unittest.main()
