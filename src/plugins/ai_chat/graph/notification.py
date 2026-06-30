from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class NotificationNode(str, Enum):
    CHECK_NOTIFICATION_POLICY = "check_notification_policy"
    VALIDATE_NOTIFICATION_CONTENT = "validate_notification_content"
    CHECK_NOTIFICATION_COOLDOWN = "check_notification_cooldown"
    FORMAT_OWNER_NOTIFICATION = "format_owner_notification"
    SEND_OWNER_PRIVATE_MESSAGE = "send_owner_private_message"
    RENDER_SOURCE_REPLY = "render_source_reply"


NOTIFICATION_NODE_SEQUENCE: tuple[NotificationNode, ...] = (
    NotificationNode.CHECK_NOTIFICATION_POLICY,
    NotificationNode.VALIDATE_NOTIFICATION_CONTENT,
    NotificationNode.CHECK_NOTIFICATION_COOLDOWN,
    NotificationNode.FORMAT_OWNER_NOTIFICATION,
    NotificationNode.SEND_OWNER_PRIVATE_MESSAGE,
    NotificationNode.RENDER_SOURCE_REPLY,
)


@dataclass
class NotificationState:
    content: str = ""
    requester_id: str = ""
    session_key: str = ""
    owner_user_id: str = ""
    group_id: str | None = None
    target_message: str = ""
    source_reply: str = ""
    sent: bool = False
    should_reply_source: bool = True
    error: str = ""
    deny_reason: str | None = None


@dataclass(frozen=True)
class NotificationGraphResult:
    sent: bool
    source_reply: str = ""
    should_reply_source: bool = True
    error: str = ""
    deny_reason: str | None = None
    target_message: str = ""


@dataclass(frozen=True)
class NotificationGraphExecution:
    state: NotificationState
    result: NotificationGraphResult
    node_trace: tuple[NotificationNode, ...]


NotificationStateHandler: TypeAlias = Callable[
    [NotificationState],
    NotificationState | Awaitable[NotificationState],
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class NotificationGraphRunner:
    """Executable owner-notification graph boundary with injected side effects."""

    def __init__(
        self,
        *,
        check_notification_policy: NotificationStateHandler | None = None,
        validate_notification_content: NotificationStateHandler | None = None,
        check_notification_cooldown: NotificationStateHandler | None = None,
        format_owner_notification: NotificationStateHandler | None = None,
        send_owner_private_message: NotificationStateHandler | None = None,
        render_source_reply: NotificationStateHandler | None = None,
    ) -> None:
        self.check_notification_policy = check_notification_policy
        self.validate_notification_content = validate_notification_content
        self.check_notification_cooldown = check_notification_cooldown
        self.format_owner_notification = format_owner_notification
        self.send_owner_private_message = send_owner_private_message
        self.render_source_reply = render_source_reply

    async def run(self, state: NotificationState) -> NotificationGraphExecution:
        node_trace: list[NotificationNode] = []
        current = state

        for node in NOTIFICATION_NODE_SEQUENCE:
            node_trace.append(node)
            if (
                node == NotificationNode.CHECK_NOTIFICATION_POLICY
                and self.check_notification_policy is not None
            ):
                current = await _maybe_await(self.check_notification_policy(current))
            elif (
                node == NotificationNode.VALIDATE_NOTIFICATION_CONTENT
                and self.validate_notification_content is not None
            ):
                current = await _maybe_await(self.validate_notification_content(current))
            elif (
                node == NotificationNode.CHECK_NOTIFICATION_COOLDOWN
                and self.check_notification_cooldown is not None
            ):
                current = await _maybe_await(self.check_notification_cooldown(current))
            elif (
                node == NotificationNode.FORMAT_OWNER_NOTIFICATION
                and self.format_owner_notification is not None
            ):
                current = await _maybe_await(self.format_owner_notification(current))
            elif (
                node == NotificationNode.SEND_OWNER_PRIVATE_MESSAGE
                and self.send_owner_private_message is not None
            ):
                current = await _maybe_await(self.send_owner_private_message(current))
            elif node == NotificationNode.RENDER_SOURCE_REPLY and self.render_source_reply is not None:
                current = await _maybe_await(self.render_source_reply(current))

            if current.error:
                break

        result = NotificationGraphResult(
            sent=current.sent,
            source_reply=current.source_reply,
            should_reply_source=current.should_reply_source,
            error=current.error,
            deny_reason=current.deny_reason,
            target_message=current.target_message,
        )
        return NotificationGraphExecution(current, result, tuple(node_trace))
