from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import threading
from typing import Any
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from .sticker_library import (
    ALLOWED_ACTIONS,
    ALLOWED_INTENSITIES,
    ALLOWED_MOODS,
    ALLOWED_PERSONA_KEYS,
    ALLOWED_SCOPES,
    ALLOWED_USAGE_TAGS,
    APPROVED_DIRECTORY_NAME,
    MANIFEST_FILE_NAME,
    MAX_LIBRARY_ENTRIES,
    MAX_MANIFEST_BYTES,
    STICKER_LIBRARY_SCHEMA_VERSION,
    StickerImageInfo,
    StickerLibraryError,
    StickerLimits,
    _is_link_or_junction,
    _webp_frame_durations,
    inspect_sticker_image,
    load_approved_sticker_library,
    resolve_sticker_candidate_file,
)


DRAFT_SCHEMA_VERSION = 1
DRAFT_FILE_NAME = "approval-drafts.json"
REPORTS_DIRECTORY_NAME = "reports"
MAX_DRAFT_BYTES = 1_048_576
MAX_DRAFT_REPORT_ITEMS = 50

_CANDIDATE_ID_PATTERN = re.compile(r"^candidate_([0-9a-f]{12})$")
_STICKER_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,62}[a-z0-9])?$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONFIRMATION_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_APPROVAL_LOCK = threading.Lock()
_CHINA_STANDARD_TIME = timezone(timedelta(hours=8), name="Asia/Shanghai")


class StickerApprovalError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StickerApprovalDraft:
    candidate_id: str
    source_sha256: str
    sticker_id: str
    persona_key: str
    moods: tuple[str, ...]
    intensity: str
    actions: tuple[str, ...]
    usage_tags: tuple[str, ...]
    scope: str
    owner_confirmed: bool


@dataclass(frozen=True)
class StickerApprovalDraftSet:
    schema_version: int
    draft_revision: int
    drafts: tuple[StickerApprovalDraft, ...]

    def by_candidate_id(self, candidate_id: str) -> StickerApprovalDraft | None:
        return next(
            (draft for draft in self.drafts if draft.candidate_id == candidate_id),
            None,
        )


@dataclass(frozen=True)
class StickerApprovalResult:
    sticker_id: str
    library_revision: int
    short_sha256: str
    animated: bool
    frame_count: int
    duration_ms: int


@dataclass(frozen=True)
class StickerRevocationResult:
    sticker_id: str
    library_revision: int


def _required_string(entry: dict[str, object], name: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value.strip():
        raise StickerApprovalError(f"invalid_{name}")
    return value.strip()


def _enum_list(
    entry: dict[str, object],
    name: str,
    allowed: frozenset[str],
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    value = entry.get(name)
    if not isinstance(value, list) or (not allow_empty and not value):
        raise StickerApprovalError(f"invalid_{name}")
    normalized = tuple(value)
    if (
        any(not isinstance(item, str) or item not in allowed for item in normalized)
        or len(set(normalized)) != len(normalized)
    ):
        raise StickerApprovalError(f"invalid_{name}")
    return normalized


def _parse_draft(entry: object) -> StickerApprovalDraft:
    if not isinstance(entry, dict):
        raise StickerApprovalError("invalid_draft")
    candidate_id = _required_string(entry, "candidate_id")
    match = _CANDIDATE_ID_PATTERN.fullmatch(candidate_id)
    if not match:
        raise StickerApprovalError("invalid_candidate_id")
    source_sha256 = _required_string(entry, "source_sha256")
    if not _SHA256_PATTERN.fullmatch(source_sha256) or not source_sha256.startswith(
        match.group(1)
    ):
        raise StickerApprovalError("invalid_source_sha256")
    sticker_id = _required_string(entry, "sticker_id")
    if not _STICKER_ID_PATTERN.fullmatch(sticker_id):
        raise StickerApprovalError("invalid_sticker_id")
    persona_key = _required_string(entry, "persona_key")
    if persona_key not in ALLOWED_PERSONA_KEYS:
        raise StickerApprovalError("invalid_persona_key")
    intensity = _required_string(entry, "intensity")
    if intensity not in ALLOWED_INTENSITIES:
        raise StickerApprovalError("invalid_intensity")
    scope = _required_string(entry, "scope")
    if scope not in ALLOWED_SCOPES:
        raise StickerApprovalError("invalid_scope")
    owner_confirmed = entry.get("owner_confirmed")
    if owner_confirmed is not True:
        raise StickerApprovalError("owner_confirmation_required")
    return StickerApprovalDraft(
        candidate_id=candidate_id,
        source_sha256=source_sha256,
        sticker_id=sticker_id,
        persona_key=persona_key,
        moods=_enum_list(entry, "moods", ALLOWED_MOODS),
        intensity=intensity,
        actions=_enum_list(entry, "actions", ALLOWED_ACTIONS, allow_empty=True),
        usage_tags=_enum_list(entry, "usage_tags", ALLOWED_USAGE_TAGS),
        scope=scope,
        owner_confirmed=True,
    )


def load_sticker_approval_drafts(root: Path) -> StickerApprovalDraftSet:
    reports_root = root / REPORTS_DIRECTORY_NAME
    draft_path = reports_root / DRAFT_FILE_NAME
    if (
        _is_link_or_junction(root)
        or _is_link_or_junction(reports_root)
        or _is_link_or_junction(draft_path)
    ):
        raise StickerApprovalError("unsafe_draft_path")
    try:
        payload_bytes = draft_path.read_bytes()
    except OSError as exc:
        raise StickerApprovalError("draft_file_missing") from exc
    if not payload_bytes or len(payload_bytes) > MAX_DRAFT_BYTES:
        raise StickerApprovalError("draft_file_size_invalid")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StickerApprovalError("draft_file_invalid_json") from None
    if not isinstance(payload, dict) or payload.get("schema_version") != DRAFT_SCHEMA_VERSION:
        raise StickerApprovalError("draft_schema_unsupported")
    draft_revision = payload.get("draft_revision")
    if type(draft_revision) is not int or draft_revision <= 0:
        raise StickerApprovalError("invalid_draft_revision")
    entries = payload.get("drafts")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_LIBRARY_ENTRIES:
        raise StickerApprovalError("invalid_drafts")
    drafts = tuple(_parse_draft(entry) for entry in entries)
    candidate_ids = [draft.candidate_id for draft in drafts]
    source_hashes = [draft.source_sha256 for draft in drafts]
    sticker_ids = [draft.sticker_id for draft in drafts]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise StickerApprovalError("duplicate_draft_candidate")
    if len(set(source_hashes)) != len(source_hashes):
        raise StickerApprovalError("duplicate_draft_source")
    if len(set(sticker_ids)) != len(sticker_ids):
        raise StickerApprovalError("duplicate_draft_sticker_id")
    return StickerApprovalDraftSet(DRAFT_SCHEMA_VERSION, draft_revision, drafts)


def format_sticker_approval_drafts(draft_set: StickerApprovalDraftSet) -> str:
    lines = [
        "本地表情批准草稿：",
        f"草稿版本：{draft_set.draft_revision}",
        f"待逐项批准：{len(draft_set.drafts)}",
    ]
    for draft in draft_set.drafts[:MAX_DRAFT_REPORT_ITEMS]:
        lines.append(
            "- "
            f"{draft.candidate_id} -> {draft.sticker_id} | "
            f"{','.join(draft.moods)} | {draft.intensity} | "
            f"{','.join(draft.usage_tags)}"
        )
    omitted = len(draft_set.drafts) - MAX_DRAFT_REPORT_ITEMS
    if omitted > 0:
        lines.append(f"其余 {omitted} 项未展开。")
    lines.append("草稿不是正式批准；必须逐项执行精确批准命令。")
    return "\n".join(lines)


def _safe_root(root: Path) -> Path:
    if _is_link_or_junction(root) or not root.is_dir():
        raise StickerApprovalError("unsafe_sticker_root")
    try:
        return root.resolve(strict=True)
    except OSError:
        raise StickerApprovalError("unsafe_sticker_root") from None


def _ensure_local_directory(root: Path, name: str) -> Path:
    resolved_root = _safe_root(root)
    directory = root / name
    if _is_link_or_junction(directory):
        raise StickerApprovalError("unsafe_approval_directory")
    try:
        directory.mkdir(exist_ok=True)
        resolved = directory.resolve(strict=True)
    except OSError:
        raise StickerApprovalError("approval_directory_unavailable") from None
    if resolved.parent != resolved_root or not resolved.is_dir():
        raise StickerApprovalError("unsafe_approval_directory")
    return resolved


def _frame_durations(source: Path, info: StickerImageInfo) -> list[int]:
    if not info.animated:
        return []
    if info.media_type == "image/webp":
        return list(_webp_frame_durations(source))
    durations: list[int] = []
    try:
        with Image.open(source) as image:
            for frame_index in range(info.frame_count):
                image.seek(frame_index)
                raw_duration = image.info.get("duration", 0)
                if not isinstance(raw_duration, (int, float)):
                    raise StickerApprovalError("normalization_timing_unavailable")
                durations.append(int(raw_duration))
    except StickerApprovalError:
        raise
    except (UnidentifiedImageError, OSError, EOFError, ValueError):
        raise StickerApprovalError("normalization_decode_failed") from None
    return durations


def _normalized_extension(info: StickerImageInfo) -> str:
    if not info.animated:
        return ".png"
    return {
        "image/gif": ".gif",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(info.media_type, "")


def _normalize_candidate(source: Path, target: Path, source_info: StickerImageInfo) -> None:
    durations = _frame_durations(source, source_info)
    frames: list[Image.Image] = []
    try:
        with Image.open(source) as image:
            for frame_index in range(source_info.frame_count):
                image.seek(frame_index)
                frame = ImageOps.exif_transpose(image.convert("RGBA"))
                frames.append(frame.copy())
        if not frames:
            raise StickerApprovalError("normalization_decode_failed")
        if not source_info.animated:
            frames[0].save(target, format="PNG", optimize=True)
            return
        common: dict[str, Any] = {
            "save_all": True,
            "append_images": frames[1:],
            "duration": durations,
            "loop": source_info.loop_count or 0,
        }
        if source_info.media_type == "image/gif":
            frames[0].save(target, format="GIF", disposal=2, optimize=False, **common)
        elif source_info.media_type == "image/png":
            frames[0].save(target, format="PNG", disposal=2, optimize=True, **common)
        elif source_info.media_type == "image/webp":
            frames[0].save(
                target,
                format="WEBP",
                lossless=True,
                quality=100,
                method=6,
                **common,
            )
        else:
            raise StickerApprovalError("normalization_format_unsupported")
    except StickerApprovalError:
        raise
    except (UnidentifiedImageError, OSError, EOFError, ValueError):
        raise StickerApprovalError("normalization_failed") from None
    finally:
        for frame in frames:
            frame.close()


def _read_manifest_for_write(
    root: Path,
    *,
    limits: StickerLimits,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest_path = root / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        return (
            {
                "schema_version": STICKER_LIBRARY_SCHEMA_VERSION,
                "library_revision": 0,
                "stickers": [],
            },
            [],
        )
    if _is_link_or_junction(manifest_path):
        raise StickerApprovalError("unsafe_manifest_path")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise StickerApprovalError("manifest_unavailable") from None
    if not isinstance(payload, dict):
        raise StickerApprovalError("manifest_unavailable")
    if payload.get("schema_version") != STICKER_LIBRARY_SCHEMA_VERSION:
        raise StickerApprovalError("manifest_schema_upgrade_required")
    try:
        library = load_approved_sticker_library(root, limits=limits)
    except StickerLibraryError:
        raise StickerApprovalError("manifest_validation_failed") from None
    if library.issues:
        raise StickerApprovalError("manifest_validation_failed")
    entries = payload.get("stickers")
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise StickerApprovalError("manifest_validation_failed")
    return payload, [dict(entry) for entry in entries]


def _manifest_bytes(revision: int, entries: list[dict[str, object]]) -> bytes:
    payload = {
        "schema_version": STICKER_LIBRARY_SCHEMA_VERSION,
        "library_revision": revision,
        "stickers": entries,
    }
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise StickerApprovalError("manifest_size_out_of_range")
    return encoded


def _atomic_replace_bytes(path: Path, payload: bytes) -> None:
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise StickerApprovalError("atomic_manifest_write_failed") from None


def approve_sticker_candidate(
    root: Path,
    candidate_id: str,
    confirmation: str,
    *,
    limits: StickerLimits | None = None,
    now: datetime | None = None,
) -> StickerApprovalResult:
    selected_limits = limits or StickerLimits()
    try:
        selected_limits.validate()
    except StickerLibraryError:
        raise StickerApprovalError("invalid_limits") from None
    candidate_match = _CANDIDATE_ID_PATTERN.fullmatch(candidate_id.strip())
    normalized_confirmation = confirmation.strip().lower()
    if not candidate_match or not _CONFIRMATION_PATTERN.fullmatch(normalized_confirmation):
        raise StickerApprovalError("invalid_approval_confirmation")
    if normalized_confirmation != candidate_match.group(1):
        raise StickerApprovalError("approval_confirmation_mismatch")
    with _APPROVAL_LOCK:
        _safe_root(root)
        draft_set = load_sticker_approval_drafts(root)
        draft = draft_set.by_candidate_id(candidate_id.strip())
        if draft is None:
            raise StickerApprovalError("approval_draft_not_found")
        try:
            source = resolve_sticker_candidate_file(
                root,
                draft.candidate_id,
                limits=selected_limits,
            )
            source_info = inspect_sticker_image(
                source,
                limits=selected_limits,
                reject_metadata=False,
                allow_animation=True,
            )
        except StickerLibraryError:
            raise StickerApprovalError("candidate_validation_failed") from None
        if source_info.sha256 != draft.source_sha256:
            raise StickerApprovalError("candidate_source_changed")
        approved_root = _ensure_local_directory(root, APPROVED_DIRECTORY_NAME)
        manifest, entries = _read_manifest_for_write(root, limits=selected_limits)
        if len(entries) >= MAX_LIBRARY_ENTRIES:
            raise StickerApprovalError("library_entry_limit_reached")
        for entry in entries:
            if entry.get("sticker_id") == draft.sticker_id:
                raise StickerApprovalError("sticker_id_already_exists")
            if entry.get("source_sha256") == draft.source_sha256:
                raise StickerApprovalError("candidate_already_approved")
        extension = _normalized_extension(source_info)
        if not extension:
            raise StickerApprovalError("normalization_format_unsupported")
        final_path = approved_root / f"{draft.sticker_id}{extension}"
        if final_path.exists() or _is_link_or_junction(final_path):
            raise StickerApprovalError("approved_file_already_exists")
        temporary = approved_root / f".{draft.sticker_id}.{uuid4().hex}.tmp"
        final_created = False
        try:
            _normalize_candidate(source, temporary, source_info)
            try:
                normalized_info = inspect_sticker_image(
                    temporary,
                    limits=selected_limits,
                    reject_metadata=True,
                    allow_animation=True,
                )
            except StickerLibraryError:
                raise StickerApprovalError("normalized_candidate_invalid") from None
            if normalized_info.animated != source_info.animated:
                raise StickerApprovalError("normalized_animation_changed")
            os.replace(temporary, final_path)
            final_created = True
            approval_time = now or datetime.now(_CHINA_STANDARD_TIME)
            if approval_time.tzinfo is None or approval_time.utcoffset() is None:
                raise StickerApprovalError("approval_time_invalid")
            entry: dict[str, object] = {
                "sticker_id": draft.sticker_id,
                "relative_file": final_path.name,
                "sha256": normalized_info.sha256,
                "source_sha256": draft.source_sha256,
                "media_type": normalized_info.media_type,
                "width": normalized_info.width,
                "height": normalized_info.height,
                "bytes": normalized_info.bytes,
                "animated": normalized_info.animated,
                "frame_count": normalized_info.frame_count,
                "duration_ms": normalized_info.duration_ms,
                "persona_key": draft.persona_key,
                "moods": list(draft.moods),
                "intensity": draft.intensity,
                "actions": list(draft.actions),
                "usage_tags": list(draft.usage_tags),
                "scope": draft.scope,
                "enabled": True,
                "approved_at": approval_time.isoformat(timespec="seconds"),
                "approval_source": "owner_local_command",
            }
            revision = int(manifest["library_revision"]) + 1
            _atomic_replace_bytes(
                root / MANIFEST_FILE_NAME,
                _manifest_bytes(revision, [*entries, entry]),
            )
        except StickerApprovalError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if final_created:
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if final_created:
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise StickerApprovalError("approval_write_failed") from None
        return StickerApprovalResult(
            sticker_id=draft.sticker_id,
            library_revision=revision,
            short_sha256=normalized_info.sha256[:12],
            animated=normalized_info.animated,
            frame_count=normalized_info.frame_count,
            duration_ms=normalized_info.duration_ms,
        )


def revoke_sticker_approval(
    root: Path,
    sticker_id: str,
    confirmation: str,
    *,
    limits: StickerLimits | None = None,
) -> StickerRevocationResult:
    selected_limits = limits or StickerLimits()
    try:
        selected_limits.validate()
    except StickerLibraryError:
        raise StickerApprovalError("invalid_limits") from None
    normalized_id = sticker_id.strip()
    normalized_confirmation = confirmation.strip().lower()
    if (
        not _STICKER_ID_PATTERN.fullmatch(normalized_id)
        or not _CONFIRMATION_PATTERN.fullmatch(normalized_confirmation)
    ):
        raise StickerApprovalError("invalid_revocation_confirmation")
    with _APPROVAL_LOCK:
        _safe_root(root)
        manifest, entries = _read_manifest_for_write(root, limits=selected_limits)
        matched: dict[str, object] | None = None
        for entry in entries:
            if entry.get("sticker_id") == normalized_id:
                matched = entry
                break
        if matched is None:
            raise StickerApprovalError("approved_sticker_not_found")
        sha256 = str(matched.get("sha256") or "")
        if not sha256.startswith(normalized_confirmation):
            raise StickerApprovalError("revocation_confirmation_mismatch")
        if matched.get("enabled") is not True:
            raise StickerApprovalError("sticker_already_disabled")
        matched["enabled"] = False
        revision = int(manifest["library_revision"]) + 1
        _atomic_replace_bytes(
            root / MANIFEST_FILE_NAME,
            _manifest_bytes(revision, entries),
        )
        return StickerRevocationResult(normalized_id, revision)
