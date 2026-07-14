from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .sticker_library import (
    StickerLibraryError,
    StickerLimits,
    inspect_sticker_image,
    load_approved_sticker_library,
)


_STICKER_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,62}[a-z0-9])?$")


class StickerPreviewError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StickerPreviewAsset:
    sticker_id: str
    file_path: Path
    short_sha256: str
    media_type: str
    animated: bool
    frame_count: int
    duration_ms: int


def resolve_sticker_preview_asset(
    root: Path,
    sticker_id: str,
    *,
    limits: StickerLimits | None = None,
) -> StickerPreviewAsset:
    normalized_id = sticker_id.strip()
    if not _STICKER_ID_PATTERN.fullmatch(normalized_id):
        raise StickerPreviewError("invalid_sticker_id")
    selected_limits = limits or StickerLimits()
    try:
        selected_limits.validate()
        library = load_approved_sticker_library(root, limits=selected_limits)
    except StickerLibraryError:
        raise StickerPreviewError("library_validation_failed") from None
    if library.issues:
        raise StickerPreviewError("library_validation_failed")
    asset = next(
        (candidate for candidate in library.assets if candidate.sticker_id == normalized_id),
        None,
    )
    if asset is None:
        raise StickerPreviewError("sticker_not_found")
    if not asset.enabled:
        raise StickerPreviewError("sticker_disabled")
    try:
        current = inspect_sticker_image(
            asset.file_path,
            limits=selected_limits,
            reject_metadata=True,
            allow_animation=True,
        )
    except StickerLibraryError:
        raise StickerPreviewError("asset_validation_failed") from None
    if (
        current.sha256 != asset.sha256
        or current.media_type != asset.media_type
        or current.width != asset.width
        or current.height != asset.height
        or current.bytes != asset.bytes
        or current.animated != asset.animated
        or current.frame_count != asset.frame_count
        or current.duration_ms != asset.duration_ms
    ):
        raise StickerPreviewError("asset_validation_failed")
    return StickerPreviewAsset(
        sticker_id=asset.sticker_id,
        file_path=asset.file_path,
        short_sha256=asset.sha256[:12],
        media_type=asset.media_type,
        animated=asset.animated,
        frame_count=asset.frame_count,
        duration_ms=asset.duration_ms,
    )
