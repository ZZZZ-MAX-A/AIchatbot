from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from .sticker_library import StickerLimits
from .sticker_preview import StickerPreviewError, resolve_sticker_preview_asset


StickerAttachmentSender = Callable[[int, Path], Awaitable[None]]


@dataclass(frozen=True)
class StickerAttachmentResult:
    status: str
    sent: bool
    sticker_id: str = ""


async def send_selected_sticker_attachment(
    root: Path,
    sticker_id: str,
    user_id: int,
    *,
    limits: StickerLimits,
    sender: StickerAttachmentSender,
) -> StickerAttachmentResult:
    if type(user_id) is not int or user_id <= 0:
        return StickerAttachmentResult("invalid_recipient", False)
    try:
        asset = await asyncio.to_thread(
            resolve_sticker_preview_asset,
            root,
            sticker_id,
            limits=limits,
        )
    except StickerPreviewError as exc:
        return StickerAttachmentResult(f"asset_{exc.code}", False)
    try:
        await sender(user_id, asset.file_path)
    except Exception:
        return StickerAttachmentResult("send_failed", False, asset.sticker_id)
    return StickerAttachmentResult("sent", True, asset.sticker_id)
