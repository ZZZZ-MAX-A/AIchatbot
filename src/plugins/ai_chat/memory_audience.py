from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .rag.schema import RagDocument


@dataclass(frozen=True)
class MemoryAudience:
    """Limit ordinary memory reads to the conversation receiving the reply.

    The selected database already provides persona isolation. SceneHub reads
    owner-private continuity separately, after validating its restricted group.
    """

    message_type: str
    user_id: str
    group_id: str = ""
    session_key: str = ""

    def manual_subjects(self) -> list[tuple[str, str]]:
        if self.message_type == "group" and self.group_id:
            return [("group", self.group_id)]
        if self.message_type == "private" and self.user_id:
            return [("user", self.user_id)]
        return []

    def allows_document(self, document: RagDocument) -> bool:
        if not self.session_key or not self.manual_subjects():
            return False
        if document.source_type == "session_summary":
            if document.session_key != self.session_key:
                return False
            if self.message_type == "group":
                return (
                    document.message_type == "group"
                    and document.group_id == self.group_id
                )
            # Legacy private summaries can lack message_type metadata, but
            # their exact private session key still identifies the audience.
            return document.message_type in {"", "private"}
        if document.source_type in {"manual_fact", "manual_preference"}:
            if self.message_type == "group":
                return (
                    document.subject_type == "group"
                    and document.subject_id == self.group_id
                )
            return (
                document.subject_type in {"user", "private"}
                and document.subject_id == self.user_id
            )
        return False
