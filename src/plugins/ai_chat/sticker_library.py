from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import warnings

from PIL import Image, UnidentifiedImageError
from PIL import ImageChops, ImageOps


STICKER_LIBRARY_SCHEMA_VERSION = 2
SUPPORTED_STICKER_LIBRARY_SCHEMA_VERSIONS = frozenset({1, 2})
MAX_MANIFEST_BYTES = 1_048_576
MAX_LIBRARY_ENTRIES = 500
MAX_CANDIDATE_ENTRIES = 200
MAX_CANDIDATE_REPORT_ITEMS = 30
APPROVED_DIRECTORY_NAME = "approved"
INBOX_DIRECTORY_NAME = "inbox"
MANIFEST_FILE_NAME = "library.json"

STATIC_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})
DYNAMIC_IMAGE_FORMATS = frozenset({"GIF", "PNG", "WEBP"})
ALLOWED_IMAGE_FORMATS = STATIC_IMAGE_FORMATS | DYNAMIC_IMAGE_FORMATS
MEDIA_TYPE_BY_FORMAT = {
    "GIF": "image/gif",
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}
ALLOWED_PERSONA_KEYS = frozenset({"aike"})
ALLOWED_MOODS = frozenset(
    {
        "affection",
        "angry",
        "attentive",
        "comfort",
        "confused",
        "curious",
        "dizzy",
        "embarrassed",
        "excited",
        "expectant",
        "happy",
        "hurt",
        "mixed",
        "neutral",
        "playful",
        "pleading",
        "resigned",
        "sad",
        "shy",
        "surprised",
        "teasing",
        "tired",
    }
)
ALLOWED_INTENSITIES = frozenset({"soft", "medium", "strong"})
ALLOWED_ACTIONS = frozenset(
    {
        "act_cute",
        "blush",
        "cover_face",
        "cry",
        "dance",
        "drink_milk_tea",
        "drive",
        "exclamation_mark",
        "facepalm",
        "fidget",
        "get_hit",
        "hands_together",
        "hide",
        "hug",
        "jump",
        "kiss",
        "laugh",
        "lick",
        "lie_flat",
        "look_away",
        "look_around",
        "nod",
        "offer_cake",
        "offer_gift",
        "peek",
        "question_mark",
        "shake_head",
        "show_heart",
        "sleep",
        "smile",
        "soul_leave_body",
        "stare",
        "sway",
        "take_notes",
        "take_photo",
        "type_angrily",
        "wave",
        "yawn",
    }
)
ALLOWED_USAGE_TAGS = frozenset(
    {
        "acting_cute",
        "affection",
        "apology",
        "attention_seeking",
        "birthday",
        "celebration",
        "checking_reaction",
        "comfort",
        "continue_speaking",
        "departure",
        "embarrassed_response",
        "failure",
        "general_reaction",
        "giving_up",
        "goodnight",
        "greeting",
        "holding_grudge",
        "joining_chat",
        "listening",
        "morning",
        "pleasing",
        "praise",
        "praise_received",
        "questioning",
        "recording",
        "reaction",
        "remembering",
        "request",
        "setback",
        "sharing_snack",
        "success",
        "teasing",
        "unexpected_statement",
    }
)
ALLOWED_SCOPES = frozenset({"owner_private"})

_STICKER_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,62}[a-z0-9])?$")
_SAFE_FILE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_ID_PATTERN = re.compile(r"^candidate_([0-9a-f]{12})$")
_TEXT_METADATA_KEYS = frozenset(
    {
        "comment",
        "description",
        "exif",
        "parameters",
        "text",
        "xml",
        "xmp",
    }
)


class StickerLibraryError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StickerLimits:
    max_file_bytes: int = 2_097_152
    max_dynamic_file_bytes: int = 5_242_880
    min_dimension: int = 32
    max_dimension: int = 2048
    max_pixels: int = 4_194_304
    max_animation_frames: int = 120
    max_animation_duration_ms: int = 10_000
    min_frame_duration_ms: int = 20
    max_animation_decoded_pixels: int = 60_000_000

    def validate(self) -> None:
        values = (
            self.max_file_bytes,
            self.max_dynamic_file_bytes,
            self.min_dimension,
            self.max_dimension,
            self.max_pixels,
            self.max_animation_frames,
            self.max_animation_duration_ms,
            self.min_frame_duration_ms,
            self.max_animation_decoded_pixels,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise StickerLibraryError("invalid_limits")
        if self.min_dimension > self.max_dimension:
            raise StickerLibraryError("invalid_limits")


@dataclass(frozen=True)
class StickerImageInfo:
    media_type: str
    width: int
    height: int
    bytes: int
    sha256: str
    metadata_present: bool
    animated: bool
    frame_count: int
    duration_ms: int
    loop_count: int | None
    total_decoded_pixels: int


@dataclass(frozen=True)
class StickerAsset:
    sticker_id: str
    file_path: Path
    relative_file: str
    sha256: str
    source_sha256: str
    media_type: str
    width: int
    height: int
    bytes: int
    animated: bool
    frame_count: int
    duration_ms: int
    persona_key: str
    moods: tuple[str, ...]
    intensity: str
    actions: tuple[str, ...]
    usage_tags: tuple[str, ...]
    scope: str
    enabled: bool
    approved_at: str
    approval_source: str


@dataclass(frozen=True)
class StickerIssue:
    entry_index: int
    sticker_id: str
    code: str


@dataclass(frozen=True)
class StickerLibrary:
    schema_version: int
    library_revision: int
    assets: tuple[StickerAsset, ...]
    issues: tuple[StickerIssue, ...]

    @property
    def approved_count(self) -> int:
        return sum(1 for asset in self.assets if asset.enabled)

    @property
    def disabled_count(self) -> int:
        return sum(1 for asset in self.assets if not asset.enabled)

    @property
    def invalid_count(self) -> int:
        return len(self.issues)

    def enabled_asset(self, sticker_id: str) -> StickerAsset | None:
        return next(
            (
                asset
                for asset in self.assets
                if asset.enabled and asset.sticker_id == sticker_id
            ),
            None,
        )


@dataclass(frozen=True)
class StickerCandidate:
    candidate_id: str
    short_sha256: str
    eligible: bool
    issue_code: str
    media_type: str = ""
    width: int = 0
    height: int = 0
    bytes: int = 0
    animated: bool = False
    frame_count: int = 1
    duration_ms: int = 0
    loop_count: int | None = None
    total_decoded_pixels: int = 0


@dataclass(frozen=True)
class StickerContactSheet:
    png_bytes: bytes
    frame_indices: tuple[int, ...]
    source_frame_count: int
    width: int
    height: int


@dataclass(frozen=True)
class StickerCandidateReport:
    status: str
    scanned_count: int
    eligible_count: int
    rejected_count: int
    candidates: tuple[StickerCandidate, ...]


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _safe_regular_file(root: Path, file_name: str) -> Path:
    if (
        not isinstance(file_name, str)
        or not _SAFE_FILE_NAME_PATTERN.fullmatch(file_name)
        or Path(file_name).name != file_name
        or "/" in file_name
        or "\\" in file_name
    ):
        raise StickerLibraryError("unsafe_file_name")
    resolved_root = root.resolve(strict=True)
    if _is_link_or_junction(root):
        raise StickerLibraryError("unsafe_approved_root")
    candidate = root / file_name
    if _is_link_or_junction(candidate):
        raise StickerLibraryError("unsafe_file_link")
    try:
        resolved_file = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise StickerLibraryError("file_missing") from exc
    if resolved_file.parent != resolved_root or not resolved_file.is_file():
        raise StickerLibraryError("file_outside_approved_root")
    return resolved_file


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65_536), b""):
                digest.update(chunk)
    except OSError as exc:
        raise StickerLibraryError("file_read_failed") from exc
    return digest.hexdigest()


def _has_disallowed_metadata(image: Image.Image) -> bool:
    if image.getexif():
        return True
    info_keys = {str(key).strip().lower() for key in image.info}
    if info_keys & _TEXT_METADATA_KEYS:
        return True
    text = getattr(image, "text", None)
    return bool(text)


def _webp_frame_durations(path: Path) -> tuple[int, ...]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise StickerLibraryError("file_read_failed") from exc
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise StickerLibraryError("animation_timing_unavailable")
    durations: list[int] = []
    offset = 12
    while offset + 8 <= len(payload):
        chunk_type = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        data_end = data_start + chunk_size
        if data_end > len(payload):
            raise StickerLibraryError("animation_timing_unavailable")
        if chunk_type == b"ANMF":
            if chunk_size < 16:
                raise StickerLibraryError("animation_timing_unavailable")
            durations.append(int.from_bytes(payload[data_start + 12 : data_start + 15], "little"))
        offset = data_end + (chunk_size % 2)
    if not durations:
        raise StickerLibraryError("animation_timing_unavailable")
    return tuple(durations)


def inspect_sticker_image(
    path: Path,
    *,
    limits: StickerLimits | None = None,
    reject_metadata: bool = True,
    allow_animation: bool = True,
) -> StickerImageInfo:
    selected_limits = limits or StickerLimits()
    selected_limits.validate()
    try:
        file_bytes = path.stat().st_size
    except OSError as exc:
        raise StickerLibraryError("file_missing") from exc
    if file_bytes <= 0 or file_bytes > max(
        selected_limits.max_file_bytes,
        selected_limits.max_dynamic_file_bytes,
    ):
        raise StickerLibraryError("file_size_out_of_range")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image_format = str(image.format or "").upper()
                if image_format not in ALLOWED_IMAGE_FORMATS:
                    raise StickerLibraryError("unsupported_image_format")
                frame_count = int(getattr(image, "n_frames", 1))
                animated = frame_count > 1 or bool(getattr(image, "is_animated", False))
                if animated and image_format not in DYNAMIC_IMAGE_FORMATS:
                    raise StickerLibraryError("animated_image_rejected")
                if animated and not allow_animation:
                    raise StickerLibraryError("animated_image_rejected")
                file_limit = (
                    selected_limits.max_dynamic_file_bytes
                    if animated
                    else selected_limits.max_file_bytes
                )
                if file_bytes > file_limit:
                    raise StickerLibraryError("file_size_out_of_range")
                if animated and frame_count > selected_limits.max_animation_frames:
                    raise StickerLibraryError("animation_frame_budget_exceeded")
                webp_durations = (
                    _webp_frame_durations(path)
                    if animated and image_format == "WEBP"
                    else ()
                )
                if webp_durations and len(webp_durations) != frame_count:
                    raise StickerLibraryError("animation_timing_unavailable")
                metadata_present = _has_disallowed_metadata(image)
                if reject_metadata and metadata_present:
                    raise StickerLibraryError("metadata_present")
                loop_raw = image.info.get("loop") if animated else None
                loop_count = int(loop_raw) if isinstance(loop_raw, (int, float)) else None
                total_decoded_pixels = 0
                duration_ms = 0
                width, height = image.size
                for frame_index in range(frame_count):
                    image.seek(frame_index)
                    frame_width, frame_height = image.size
                    if (
                        frame_width < selected_limits.min_dimension
                        or frame_height < selected_limits.min_dimension
                        or frame_width > selected_limits.max_dimension
                        or frame_height > selected_limits.max_dimension
                        or frame_width * frame_height > selected_limits.max_pixels
                    ):
                        raise StickerLibraryError("image_dimensions_out_of_range")
                    total_decoded_pixels += frame_width * frame_height
                    if (
                        animated
                        and total_decoded_pixels
                        > selected_limits.max_animation_decoded_pixels
                    ):
                        raise StickerLibraryError("animation_pixel_budget_exceeded")
                    if animated:
                        raw_duration = (
                            webp_durations[frame_index]
                            if webp_durations
                            else image.info.get("duration", 0)
                        )
                        if not isinstance(raw_duration, (int, float)):
                            raise StickerLibraryError("invalid_frame_duration")
                        frame_duration = int(raw_duration)
                        if frame_duration < selected_limits.min_frame_duration_ms:
                            raise StickerLibraryError("invalid_frame_duration")
                        duration_ms += frame_duration
                        if duration_ms > selected_limits.max_animation_duration_ms:
                            raise StickerLibraryError("animation_duration_budget_exceeded")
                    image.load()
    except StickerLibraryError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise StickerLibraryError("image_pixel_budget_exceeded") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise StickerLibraryError("image_decode_failed") from None

    return StickerImageInfo(
        media_type=MEDIA_TYPE_BY_FORMAT[image_format],
        width=width,
        height=height,
        bytes=file_bytes,
        sha256=_sha256_file(path),
        metadata_present=metadata_present,
        animated=animated,
        frame_count=frame_count,
        duration_ms=duration_ms,
        loop_count=loop_count,
        total_decoded_pixels=total_decoded_pixels,
    )


def inspect_static_sticker_image(
    path: Path,
    *,
    limits: StickerLimits | None = None,
    reject_metadata: bool = True,
) -> StickerImageInfo:
    info = inspect_sticker_image(
        path,
        limits=limits,
        reject_metadata=reject_metadata,
        allow_animation=False,
    )
    if info.media_type not in {
        MEDIA_TYPE_BY_FORMAT[image_format]
        for image_format in STATIC_IMAGE_FORMATS
    }:
        raise StickerLibraryError("unsupported_image_format")
    return info


def _representative_frame_indices(frame_count: int, max_frames: int) -> list[int]:
    if frame_count <= max_frames:
        return list(range(frame_count))
    positions = {
        0,
        frame_count - 1,
        round((frame_count - 1) * 0.25),
        round((frame_count - 1) * 0.50),
        round((frame_count - 1) * 0.75),
    }
    return sorted(positions)[:max_frames]


def build_sticker_contact_sheet(
    path: Path,
    *,
    limits: StickerLimits | None = None,
    max_frames: int = 6,
    cell_size: int = 256,
) -> StickerContactSheet:
    if type(max_frames) is not int or max_frames <= 0 or max_frames > 12:
        raise StickerLibraryError("invalid_contact_sheet_budget")
    if type(cell_size) is not int or cell_size < 64 or cell_size > 512:
        raise StickerLibraryError("invalid_contact_sheet_budget")
    info = inspect_sticker_image(
        path,
        limits=limits,
        reject_metadata=False,
        allow_animation=True,
    )
    base_indices = _representative_frame_indices(info.frame_count, max_frames)
    sampled_frames: dict[int, Image.Image] = {}
    max_change_index = 0
    max_change_score = -1.0
    previous_small: Image.Image | None = None
    try:
        with Image.open(path) as image:
            for frame_index in range(info.frame_count):
                image.seek(frame_index)
                frame = image.convert("RGBA")
                small = ImageOps.contain(frame.convert("RGB"), (64, 64)).convert("L")
                if previous_small is not None:
                    difference = ImageChops.difference(previous_small, small)
                    score = sum(difference.histogram()[value] * value for value in range(256))
                    if score > max_change_score:
                        max_change_score = float(score)
                        max_change_index = frame_index
                previous_small = small
                if frame_index in base_indices:
                    sampled_frames[frame_index] = frame.copy()
            if info.frame_count > len(base_indices) and max_change_index not in base_indices:
                if len(base_indices) >= max_frames:
                    replaceable = [
                        index
                        for index in base_indices
                        if index not in {0, info.frame_count - 1}
                    ]
                    if replaceable:
                        base_indices.remove(replaceable[len(replaceable) // 2])
                base_indices.append(max_change_index)
                base_indices = sorted(set(base_indices))[:max_frames]
                if max_change_index not in sampled_frames:
                    image.seek(max_change_index)
                    sampled_frames[max_change_index] = image.convert("RGBA").copy()
    except (UnidentifiedImageError, OSError, EOFError, ValueError):
        raise StickerLibraryError("contact_sheet_failed") from None

    columns = min(3, len(base_indices))
    rows = (len(base_indices) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * cell_size, rows * cell_size), (245, 245, 245, 255))
    for offset, frame_index in enumerate(base_indices):
        frame = sampled_frames.get(frame_index)
        if frame is None:
            raise StickerLibraryError("contact_sheet_failed")
        contained = ImageOps.contain(frame, (cell_size, cell_size))
        x = (offset % columns) * cell_size + (cell_size - contained.width) // 2
        y = (offset // columns) * cell_size + (cell_size - contained.height) // 2
        sheet.alpha_composite(contained, (x, y))
    from io import BytesIO

    output = BytesIO()
    sheet.convert("RGB").save(output, format="PNG", optimize=True)
    png_bytes = output.getvalue()
    return StickerContactSheet(
        png_bytes=png_bytes,
        frame_indices=tuple(base_indices),
        source_frame_count=info.frame_count,
        width=sheet.width,
        height=sheet.height,
    )


def _rejected_candidate(index: int, code: str, *, bytes: int = 0) -> StickerCandidate:
    return StickerCandidate(
        candidate_id=f"rejected_{index + 1:03d}",
        short_sha256="",
        eligible=False,
        issue_code=code,
        bytes=max(bytes, 0),
    )


def inspect_sticker_candidates(
    root: Path,
    *,
    limits: StickerLimits | None = None,
) -> StickerCandidateReport:
    selected_limits = limits or StickerLimits()
    selected_limits.validate()
    inbox = root / INBOX_DIRECTORY_NAME
    if _is_link_or_junction(root) or _is_link_or_junction(inbox):
        return StickerCandidateReport("unsafe", 0, 0, 0, ())
    if not inbox.exists():
        return StickerCandidateReport("missing", 0, 0, 0, ())
    if not inbox.is_dir():
        return StickerCandidateReport("unsafe", 0, 0, 0, ())

    entries: list[Path] = []
    try:
        for entry in inbox.iterdir():
            entries.append(entry)
            if len(entries) > MAX_CANDIDATE_ENTRIES:
                return StickerCandidateReport("too_many_entries", 0, 0, 0, ())
    except OSError:
        return StickerCandidateReport("unavailable", 0, 0, 0, ())
    entries.sort(key=lambda path: path.name.casefold())

    candidates: list[StickerCandidate] = []
    seen_hashes: set[str] = set()
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if _is_link_or_junction(entry):
            candidates.append(_rejected_candidate(index, "unsafe_file_link"))
            continue
        if not entry.is_file():
            candidates.append(_rejected_candidate(index, "non_regular_file"))
            continue
        try:
            if entry.resolve(strict=True).parent != inbox.resolve(strict=True):
                candidates.append(_rejected_candidate(index, "file_outside_inbox"))
                continue
        except OSError:
            candidates.append(_rejected_candidate(index, "file_read_failed"))
            continue
        try:
            file_bytes = entry.stat().st_size
        except OSError:
            candidates.append(_rejected_candidate(index, "file_read_failed"))
            continue
        if file_bytes <= 0 or file_bytes > max(
            selected_limits.max_file_bytes,
            selected_limits.max_dynamic_file_bytes,
        ):
            candidates.append(
                _rejected_candidate(
                    index,
                    "file_size_out_of_range",
                    bytes=file_bytes,
                )
            )
            continue
        try:
            sha256 = _sha256_file(entry)
        except StickerLibraryError as exc:
            candidates.append(_rejected_candidate(index, exc.code, bytes=file_bytes))
            continue
        short_sha256 = sha256[:12]
        candidate_id = f"candidate_{short_sha256}"
        if sha256 in seen_hashes:
            candidates.append(
                StickerCandidate(
                    candidate_id=candidate_id,
                    short_sha256=short_sha256,
                    eligible=False,
                    issue_code="duplicate_candidate_content",
                    bytes=file_bytes,
                )
            )
            continue
        if candidate_id in seen_ids:
            candidates.append(
                StickerCandidate(
                    candidate_id=candidate_id,
                    short_sha256=short_sha256,
                    eligible=False,
                    issue_code="candidate_id_collision",
                    bytes=file_bytes,
                )
            )
            continue
        seen_hashes.add(sha256)
        seen_ids.add(candidate_id)
        try:
            image = inspect_sticker_image(
                entry,
                limits=selected_limits,
                reject_metadata=False,
                allow_animation=True,
            )
        except StickerLibraryError as exc:
            candidates.append(
                StickerCandidate(
                    candidate_id=candidate_id,
                    short_sha256=short_sha256,
                    eligible=False,
                    issue_code=exc.code,
                    bytes=file_bytes,
                )
            )
            continue
        candidates.append(
            StickerCandidate(
                candidate_id=candidate_id,
                short_sha256=short_sha256,
                eligible=not image.metadata_present,
                issue_code="" if not image.metadata_present else "metadata_present",
                media_type=image.media_type,
                width=image.width,
                height=image.height,
                bytes=image.bytes,
                animated=image.animated,
                frame_count=image.frame_count,
                duration_ms=image.duration_ms,
                loop_count=image.loop_count,
                total_decoded_pixels=image.total_decoded_pixels,
            )
        )

    eligible_count = sum(1 for candidate in candidates if candidate.eligible)
    return StickerCandidateReport(
        status="ready",
        scanned_count=len(entries),
        eligible_count=eligible_count,
        rejected_count=len(candidates) - eligible_count,
        candidates=tuple(candidates),
    )


def resolve_sticker_candidate_file(
    root: Path,
    candidate_id: str,
    *,
    limits: StickerLimits | None = None,
) -> Path:
    match = _CANDIDATE_ID_PATTERN.fullmatch(candidate_id.strip())
    if not match:
        raise StickerLibraryError("invalid_candidate_id")
    selected_limits = limits or StickerLimits()
    selected_limits.validate()
    inbox = root / INBOX_DIRECTORY_NAME
    if (
        _is_link_or_junction(root)
        or _is_link_or_junction(inbox)
        or not inbox.is_dir()
    ):
        raise StickerLibraryError("inbox_unavailable")
    entries: list[Path] = []
    try:
        for entry in inbox.iterdir():
            entries.append(entry)
            if len(entries) > MAX_CANDIDATE_ENTRIES:
                raise StickerLibraryError("too_many_candidate_entries")
    except StickerLibraryError:
        raise
    except OSError:
        raise StickerLibraryError("inbox_unavailable") from None

    short_hash = match.group(1)
    matches: list[tuple[Path, str]] = []
    resolved_inbox = inbox.resolve(strict=True)
    for entry in entries:
        if _is_link_or_junction(entry) or not entry.is_file():
            continue
        try:
            resolved = entry.resolve(strict=True)
            if resolved.parent != resolved_inbox:
                continue
            file_bytes = resolved.stat().st_size
        except OSError:
            continue
        if file_bytes <= 0 or file_bytes > max(
            selected_limits.max_file_bytes,
            selected_limits.max_dynamic_file_bytes,
        ):
            continue
        sha256 = _sha256_file(resolved)
        if sha256.startswith(short_hash):
            matches.append((resolved, sha256))
    if not matches:
        raise StickerLibraryError("candidate_not_found")
    if len(matches) != 1:
        raise StickerLibraryError("candidate_id_collision")
    resolved, _sha256 = matches[0]
    inspect_sticker_image(
        resolved,
        limits=selected_limits,
        reject_metadata=False,
        allow_animation=True,
    )
    return resolved


_CANDIDATE_ISSUE_LABELS = {
    "animated_image_rejected": "动画图片不允许",
    "animation_duration_budget_exceeded": "动画时长超出预算",
    "animation_frame_budget_exceeded": "动画帧数超出预算",
    "animation_pixel_budget_exceeded": "动画总解码像素超出预算",
    "animation_timing_unavailable": "动画帧时长无法安全读取",
    "candidate_id_collision": "候选短标识冲突",
    "duplicate_candidate_content": "候选内容重复",
    "file_read_failed": "文件不可读",
    "file_outside_inbox": "文件超出候选目录",
    "file_size_out_of_range": "文件大小超出预算",
    "image_decode_failed": "图片无法解码",
    "image_dimensions_out_of_range": "图片尺寸超出预算",
    "image_pixel_budget_exceeded": "图片像素预算超限",
    "invalid_frame_duration": "动画帧间隔无效或过短",
    "metadata_present": "包含待清理 metadata",
    "non_regular_file": "不是普通文件",
    "unsafe_file_link": "文件链接不允许",
    "unsupported_image_format": "图片格式不允许",
}


def format_sticker_candidate_report(report: StickerCandidateReport) -> str:
    if report.status == "missing":
        return "本地表情候选检查：候选目录不存在，未自动创建任何目录或文件。"
    if report.status == "unsafe":
        return "本地表情候选检查：候选目录边界不安全，已拒绝扫描。"
    if report.status == "unavailable":
        return "本地表情候选检查：候选目录当前不可读取。"
    if report.status == "too_many_entries":
        return f"本地表情候选检查：直接子项超过 {MAX_CANDIDATE_ENTRIES} 个，已拒绝扫描。"
    if report.status != "ready":
        return "本地表情候选检查：状态不可用。"

    lines = [
        "本地表情候选检查：",
        f"扫描：{report.scanned_count}",
        f"可进入审核：{report.eligible_count}",
        f"拒绝：{report.rejected_count}",
    ]
    if not report.candidates:
        lines.append("候选目录为空。")
        return "\n".join(lines)
    lines.append("候选：")
    visible = report.candidates[:MAX_CANDIDATE_REPORT_ITEMS]
    for candidate in visible:
        if candidate.eligible:
            animation = (
                f" | 动态 {candidate.frame_count} 帧/{candidate.duration_ms}ms"
                if candidate.animated
                else " | 静态"
            )
            lines.append(
                "- "
                f"{candidate.candidate_id} | 可审核 | {candidate.media_type} | "
                f"{candidate.width}x{candidate.height}{animation} | "
                f"{candidate.bytes} bytes | "
                f"sha256:{candidate.short_sha256}"
            )
            continue
        issue = _CANDIDATE_ISSUE_LABELS.get(candidate.issue_code, "安全校验未通过")
        label = candidate.candidate_id or "rejected"
        lines.append(f"- {label} | 拒绝 | {issue}")
    omitted = len(report.candidates) - len(visible)
    if omitted > 0:
        lines.append(f"其余 {omitted} 项未展开。")
    lines.append("本次仅检查，未移动、改写、批准或发送任何图片。")
    return "\n".join(lines)


def _required_string(entry: dict[str, object], name: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value.strip():
        raise StickerLibraryError(f"invalid_{name}")
    return value.strip()


def _required_positive_int(entry: dict[str, object], name: str) -> int:
    value = entry.get(name)
    if type(value) is not int or value <= 0:
        raise StickerLibraryError(f"invalid_{name}")
    return value


def _enum_list(
    entry: dict[str, object],
    name: str,
    allowed: frozenset[str],
) -> tuple[str, ...]:
    value = entry.get(name)
    if not isinstance(value, list) or not value:
        raise StickerLibraryError(f"invalid_{name}")
    normalized = tuple(value)
    if (
        any(not isinstance(item, str) or item not in allowed for item in normalized)
        or len(set(normalized)) != len(normalized)
    ):
        raise StickerLibraryError(f"invalid_{name}")
    return normalized


def _optional_enum_list(
    entry: dict[str, object],
    name: str,
    allowed: frozenset[str],
) -> tuple[str, ...]:
    value = entry.get(name)
    if not isinstance(value, list):
        raise StickerLibraryError(f"invalid_{name}")
    normalized = tuple(value)
    if (
        any(not isinstance(item, str) or item not in allowed for item in normalized)
        or len(set(normalized)) != len(normalized)
    ):
        raise StickerLibraryError(f"invalid_{name}")
    return normalized


def _approved_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise StickerLibraryError("invalid_approved_at") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StickerLibraryError("invalid_approved_at")
    return value


def _parse_asset(
    entry: object,
    *,
    schema_version: int,
    approved_root: Path,
    limits: StickerLimits,
) -> StickerAsset:
    if not isinstance(entry, dict):
        raise StickerLibraryError("invalid_entry")
    sticker_id = _required_string(entry, "sticker_id")
    if not _STICKER_ID_PATTERN.fullmatch(sticker_id):
        raise StickerLibraryError("invalid_sticker_id")
    relative_file = _required_string(entry, "relative_file")
    expected_sha256 = _required_string(entry, "sha256")
    if not _SHA256_PATTERN.fullmatch(expected_sha256):
        raise StickerLibraryError("invalid_sha256")
    source_sha256 = (
        _required_string(entry, "source_sha256")
        if schema_version >= 2
        else expected_sha256
    )
    if not _SHA256_PATTERN.fullmatch(source_sha256):
        raise StickerLibraryError("invalid_source_sha256")
    media_type = _required_string(entry, "media_type")
    if media_type not in MEDIA_TYPE_BY_FORMAT.values():
        raise StickerLibraryError("invalid_media_type")
    persona_key = _required_string(entry, "persona_key")
    if persona_key not in ALLOWED_PERSONA_KEYS:
        raise StickerLibraryError("invalid_persona_key")
    scope = _required_string(entry, "scope")
    if scope not in ALLOWED_SCOPES:
        raise StickerLibraryError("invalid_scope")
    enabled = entry.get("enabled")
    if type(enabled) is not bool:
        raise StickerLibraryError("invalid_enabled")
    approval_source = _required_string(entry, "approval_source")
    if approval_source != "owner_local_command":
        raise StickerLibraryError("invalid_approval_source")
    approved_at = _approved_at(_required_string(entry, "approved_at"))
    moods = _enum_list(entry, "moods", ALLOWED_MOODS)
    intensity = (
        _required_string(entry, "intensity")
        if schema_version >= 2
        else "medium"
    )
    if intensity not in ALLOWED_INTENSITIES:
        raise StickerLibraryError("invalid_intensity")
    actions = (
        _optional_enum_list(entry, "actions", ALLOWED_ACTIONS)
        if schema_version >= 2
        else ()
    )
    usage_tags = _enum_list(entry, "usage_tags", ALLOWED_USAGE_TAGS)
    expected_width = _required_positive_int(entry, "width")
    expected_height = _required_positive_int(entry, "height")
    expected_bytes = _required_positive_int(entry, "bytes")
    expected_animated = entry.get("animated") if schema_version >= 2 else False
    if type(expected_animated) is not bool:
        raise StickerLibraryError("invalid_animated")
    expected_frame_count = (
        _required_positive_int(entry, "frame_count")
        if schema_version >= 2
        else 1
    )
    expected_duration_ms = entry.get("duration_ms") if schema_version >= 2 else 0
    if type(expected_duration_ms) is not int or expected_duration_ms < 0:
        raise StickerLibraryError("invalid_duration_ms")
    if (not expected_animated and expected_frame_count != 1) or (
        not expected_animated and expected_duration_ms != 0
    ):
        raise StickerLibraryError("animation_metadata_mismatch")
    if expected_animated and (expected_frame_count <= 1 or expected_duration_ms <= 0):
        raise StickerLibraryError("animation_metadata_mismatch")

    file_path = _safe_regular_file(approved_root, relative_file)
    image = (
        inspect_sticker_image(file_path, limits=limits)
        if schema_version >= 2
        else inspect_static_sticker_image(file_path, limits=limits)
    )
    if image.sha256 != expected_sha256:
        raise StickerLibraryError("sha256_mismatch")
    if image.media_type != media_type:
        raise StickerLibraryError("media_type_mismatch")
    if (image.width, image.height) != (expected_width, expected_height):
        raise StickerLibraryError("dimensions_mismatch")
    if image.bytes != expected_bytes:
        raise StickerLibraryError("bytes_mismatch")
    if (
        image.animated != expected_animated
        or image.frame_count != expected_frame_count
        or image.duration_ms != expected_duration_ms
    ):
        raise StickerLibraryError("animation_metadata_mismatch")

    return StickerAsset(
        sticker_id=sticker_id,
        file_path=file_path,
        relative_file=relative_file,
        sha256=expected_sha256,
        source_sha256=source_sha256,
        media_type=media_type,
        width=expected_width,
        height=expected_height,
        bytes=expected_bytes,
        animated=expected_animated,
        frame_count=expected_frame_count,
        duration_ms=expected_duration_ms,
        persona_key=persona_key,
        moods=moods,
        intensity=intensity,
        actions=actions,
        usage_tags=usage_tags,
        scope=scope,
        enabled=enabled,
        approved_at=approved_at,
        approval_source=approval_source,
    )


def load_approved_sticker_library(
    root: Path,
    *,
    limits: StickerLimits | None = None,
) -> StickerLibrary:
    selected_limits = limits or StickerLimits()
    selected_limits.validate()
    manifest_path = root / MANIFEST_FILE_NAME
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise StickerLibraryError("manifest_missing") from exc
    if not manifest_bytes or len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise StickerLibraryError("manifest_size_out_of_range")
    try:
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StickerLibraryError("manifest_invalid_json") from None
    if not isinstance(payload, dict):
        raise StickerLibraryError("manifest_invalid_root")
    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_STICKER_LIBRARY_SCHEMA_VERSIONS:
        raise StickerLibraryError("unsupported_schema_version")
    library_revision = payload.get("library_revision")
    if type(library_revision) is not int or library_revision <= 0:
        raise StickerLibraryError("invalid_library_revision")
    entries = payload.get("stickers")
    if not isinstance(entries, list) or len(entries) > MAX_LIBRARY_ENTRIES:
        raise StickerLibraryError("invalid_sticker_entries")

    approved_root = root / APPROVED_DIRECTORY_NAME
    try:
        approved_root.resolve(strict=True)
    except OSError as exc:
        raise StickerLibraryError("approved_root_missing") from exc
    if not approved_root.is_dir() or approved_root.is_symlink():
        raise StickerLibraryError("unsafe_approved_root")

    assets: list[StickerAsset] = []
    issues: list[StickerIssue] = []
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    seen_hashes: set[str] = set()
    seen_source_hashes: set[str] = set()
    for index, entry in enumerate(entries):
        safe_id = ""
        if isinstance(entry, dict) and isinstance(entry.get("sticker_id"), str):
            candidate_id = str(entry["sticker_id"])
            safe_id = candidate_id if _STICKER_ID_PATTERN.fullmatch(candidate_id) else ""
        try:
            asset = _parse_asset(
                entry,
                schema_version=schema_version,
                approved_root=approved_root,
                limits=selected_limits,
            )
            if asset.sticker_id in seen_ids:
                raise StickerLibraryError("duplicate_sticker_id")
            if asset.relative_file in seen_files:
                raise StickerLibraryError("duplicate_relative_file")
            if asset.sha256 in seen_hashes:
                raise StickerLibraryError("duplicate_sha256")
            if asset.source_sha256 in seen_source_hashes:
                raise StickerLibraryError("duplicate_source_sha256")
        except StickerLibraryError as exc:
            issues.append(StickerIssue(index, safe_id, exc.code))
            continue
        seen_ids.add(asset.sticker_id)
        seen_files.add(asset.relative_file)
        seen_hashes.add(asset.sha256)
        seen_source_hashes.add(asset.source_sha256)
        assets.append(asset)

    return StickerLibrary(
        schema_version=schema_version,
        library_revision=library_revision,
        assets=tuple(assets),
        issues=tuple(issues),
    )
