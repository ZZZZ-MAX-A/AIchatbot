from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VisionNode(str, Enum):
    EXTRACT_IMAGE_URLS = "extract_image_urls"
    APPLY_IMAGE_CACHE_POLICY = "apply_image_cache_policy"
    CHECK_VISION_ACCESS = "check_vision_access"
    DESCRIBE_IMAGES = "describe_images"
    SANITIZE_IMAGE_CONTEXT = "sanitize_image_context"
    RETURN_IMAGE_ARTIFACT = "return_image_artifact"


VISION_NODE_SEQUENCE: tuple[VisionNode, ...] = (
    VisionNode.EXTRACT_IMAGE_URLS,
    VisionNode.APPLY_IMAGE_CACHE_POLICY,
    VisionNode.CHECK_VISION_ACCESS,
    VisionNode.DESCRIBE_IMAGES,
    VisionNode.SANITIZE_IMAGE_CONTEXT,
    VisionNode.RETURN_IMAGE_ARTIFACT,
)


@dataclass
class VisionContext:
    has_image: bool = False
    has_image_context: bool = False
    image_urls: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    context_text: str = ""
    error: str = ""


@dataclass(frozen=True)
class VisionArtifact:
    descriptions: tuple[str, ...]
    context_text: str
    has_image_context: bool


def vision_artifact_from_context(context: VisionContext) -> VisionArtifact:
    return VisionArtifact(
        descriptions=tuple(context.descriptions),
        context_text=context.context_text,
        has_image_context=context.has_image_context,
    )
