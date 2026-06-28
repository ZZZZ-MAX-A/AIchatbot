from __future__ import annotations

from dataclasses import dataclass

from .state import RuntimeState


@dataclass(frozen=True)
class RuntimeResponse:
    text: str
    should_reply: bool = True


class AgentRuntime:
    """Placeholder runtime boundary for future LangGraph integration.

    The current v1.3 skeleton intentionally does not route production QQ
    messages through LangGraph yet. This class defines the integration point
    that future graph implementations should satisfy.
    """

    async def run(self, state: RuntimeState) -> RuntimeResponse:
        if state.response:
            return RuntimeResponse(state.response)
        return RuntimeResponse("Agent Runtime 尚未启用。", should_reply=False)

