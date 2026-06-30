from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias


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
    text: str = ""
    has_image: bool = False
    has_image_context: bool = False
    image_urls: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    context_text: str = ""
    should_continue: bool = True
    error: str = ""


@dataclass(frozen=True)
class VisionArtifact:
    descriptions: tuple[str, ...]
    context_text: str
    has_image_context: bool


@dataclass(frozen=True)
class VisionGraphResult:
    artifact: VisionArtifact
    image_urls: tuple[str, ...]
    has_image: bool
    has_image_context: bool
    should_continue: bool = True
    error: str = ""


@dataclass(frozen=True)
class VisionGraphExecution:
    state: VisionContext
    result: VisionGraphResult
    node_trace: tuple[VisionNode, ...]


VisionStateHandler: TypeAlias = Callable[[VisionContext], VisionContext | Awaitable[VisionContext]]


def vision_artifact_from_context(context: VisionContext) -> VisionArtifact:
    return VisionArtifact(
        descriptions=tuple(context.descriptions),
        context_text=context.context_text,
        has_image_context=context.has_image_context,
    )


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class VisionGraphRunner:
    """Executable vision graph boundary with injected cache and model handlers."""

    def __init__(
        self,
        *,
        extract_image_urls: VisionStateHandler | None = None,
        apply_image_cache_policy: VisionStateHandler | None = None,
        check_vision_access: VisionStateHandler | None = None,
        describe_images: VisionStateHandler | None = None,
        sanitize_image_context: VisionStateHandler | None = None,
        return_image_artifact: VisionStateHandler | None = None,
    ) -> None:
        self.extract_image_urls = extract_image_urls
        self.apply_image_cache_policy = apply_image_cache_policy
        self.check_vision_access = check_vision_access
        self.describe_images = describe_images
        self.sanitize_image_context = sanitize_image_context
        self.return_image_artifact = return_image_artifact

    async def run(self, state: VisionContext) -> VisionGraphExecution:
        node_trace: list[VisionNode] = []
        current = state

        for node in VISION_NODE_SEQUENCE:
            node_trace.append(node)
            if node == VisionNode.EXTRACT_IMAGE_URLS and self.extract_image_urls is not None:
                current = await _maybe_await(self.extract_image_urls(current))
            elif (
                node == VisionNode.APPLY_IMAGE_CACHE_POLICY
                and self.apply_image_cache_policy is not None
            ):
                current = await _maybe_await(self.apply_image_cache_policy(current))
            elif node == VisionNode.CHECK_VISION_ACCESS and self.check_vision_access is not None:
                current = await _maybe_await(self.check_vision_access(current))
            elif node == VisionNode.DESCRIBE_IMAGES and self.describe_images is not None:
                current = await _maybe_await(self.describe_images(current))
            elif (
                node == VisionNode.SANITIZE_IMAGE_CONTEXT
                and self.sanitize_image_context is not None
            ):
                current = await _maybe_await(self.sanitize_image_context(current))
            elif (
                node == VisionNode.RETURN_IMAGE_ARTIFACT
                and self.return_image_artifact is not None
            ):
                current = await _maybe_await(self.return_image_artifact(current))

            if current.error or not current.should_continue:
                break

        artifact = vision_artifact_from_context(current)
        result = VisionGraphResult(
            artifact=artifact,
            image_urls=tuple(current.image_urls),
            has_image=current.has_image,
            has_image_context=current.has_image_context,
            should_continue=current.should_continue,
            error=current.error,
        )
        return VisionGraphExecution(current, result, tuple(node_trace))
