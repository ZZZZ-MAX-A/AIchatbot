from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from PIL import features
from PIL.PngImagePlugin import PngInfo

from pure_ai_chat_loader import AI_CHAT_ROOT, load_sticker_library_module


class StickerLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_sticker_library_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "stickers"
        self.approved = self.root / "approved"
        self.approved.mkdir(parents=True)

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_png(
        self,
        name: str = "aike_happy_001.png",
        *,
        size: tuple[int, int] = (64, 64),
        pnginfo: PngInfo | None = None,
    ) -> Path:
        path = self.approved / name
        Image.new("RGBA", size, (255, 120, 160, 255)).save(
            path,
            format="PNG",
            pnginfo=pnginfo,
        )
        return path

    def entry(self, path: Path, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "sticker_id": "aike_happy_001",
            "relative_file": path.name,
            "sha256": self.sha256(path),
            "media_type": "image/png",
            "width": 64,
            "height": 64,
            "bytes": path.stat().st_size,
            "persona_key": "aike",
            "moods": ["happy"],
            "usage_tags": ["greeting", "affection"],
            "scope": "owner_private",
            "enabled": True,
            "approved_at": "2026-07-13T10:30:00+08:00",
            "approval_source": "owner_local_command",
        }
        payload.update(overrides)
        return payload

    def write_manifest(self, entries: list[object], **overrides: object) -> None:
        payload: dict[str, object] = {
            "schema_version": 1,
            "library_revision": 1,
            "stickers": entries,
        }
        payload.update(overrides)
        (self.root / "library.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def assert_error_code(self, expected: str, callback) -> None:
        with self.assertRaises(self.module.StickerLibraryError) as raised:
            callback()
        self.assertEqual(raised.exception.code, expected)

    def test_valid_approved_static_png_loads_as_immutable_asset(self):
        path = self.write_png()
        self.write_manifest([self.entry(path)])

        library = self.module.load_approved_sticker_library(self.root)

        self.assertEqual(library.schema_version, 1)
        self.assertEqual(library.library_revision, 1)
        self.assertEqual(library.approved_count, 1)
        self.assertEqual(library.disabled_count, 0)
        self.assertEqual(library.invalid_count, 0)
        asset = library.enabled_asset("aike_happy_001")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.file_path, path.resolve())
        self.assertEqual(asset.media_type, "image/png")
        self.assertEqual(asset.moods, ("happy",))

    def test_disabled_asset_is_loaded_but_not_selectable(self):
        path = self.write_png()
        self.write_manifest([self.entry(path, enabled=False)])

        library = self.module.load_approved_sticker_library(self.root)

        self.assertEqual(library.approved_count, 0)
        self.assertEqual(library.disabled_count, 1)
        self.assertIsNone(library.enabled_asset("aike_happy_001"))

    def test_path_traversal_and_absolute_paths_are_entry_issues(self):
        for relative_file in ("../outside.png", "sub/file.png", "C:/escape.png"):
            with self.subTest(relative_file=relative_file):
                self.write_manifest(
                    [
                        {
                            **self.entry(self.write_png()),
                            "relative_file": relative_file,
                        }
                    ]
                )
                library = self.module.load_approved_sticker_library(self.root)
                self.assertEqual(library.assets, ())
                self.assertEqual(library.issues[0].code, "unsafe_file_name")

    def test_hash_size_dimensions_and_media_type_are_rechecked(self):
        path = self.write_png()
        cases = (
            ({"sha256": "0" * 64}, "sha256_mismatch"),
            ({"bytes": path.stat().st_size + 1}, "bytes_mismatch"),
            ({"width": 65}, "dimensions_mismatch"),
            ({"media_type": "image/jpeg"}, "media_type_mismatch"),
        )
        for overrides, expected in cases:
            with self.subTest(expected=expected):
                self.write_manifest([self.entry(path, **overrides)])
                library = self.module.load_approved_sticker_library(self.root)
                self.assertEqual(library.issues[0].code, expected)

    def test_metadata_is_rejected_from_approved_file(self):
        metadata = PngInfo()
        metadata.add_text("Comment", "private review note")
        path = self.write_png(pnginfo=metadata)
        self.write_manifest([self.entry(path)])

        library = self.module.load_approved_sticker_library(self.root)

        self.assertEqual(library.issues[0].code, "metadata_present")

    def test_animated_png_is_rejected(self):
        path = self.approved / "aike_happy_001.png"
        frames = [
            Image.new("RGBA", (64, 64), (255, 0, 0, 255)),
            Image.new("RGBA", (64, 64), (0, 0, 255, 255)),
        ]
        frames[0].save(
            path,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            duration=100,
        )

        self.assert_error_code(
            "animated_image_rejected",
            lambda: self.module.inspect_static_sticker_image(path),
        )

    def test_corrupt_and_unsupported_files_are_rejected(self):
        corrupt = self.approved / "broken.png"
        corrupt.write_bytes(b"not an image")
        self.assert_error_code(
            "image_decode_failed",
            lambda: self.module.inspect_static_sticker_image(corrupt),
        )

        gif = self.approved / "animated.gif"
        Image.new("RGB", (64, 64), "red").save(gif, format="GIF")
        self.assert_error_code(
            "unsupported_image_format",
            lambda: self.module.inspect_static_sticker_image(gif),
        )

    def test_static_jpeg_and_webp_are_allowed_by_real_decoder(self):
        jpeg = self.approved / "aike_happy_001.jpg"
        Image.new("RGB", (64, 64), "red").save(jpeg, format="JPEG")
        jpeg_info = self.module.inspect_static_sticker_image(jpeg)
        self.assertEqual(jpeg_info.media_type, "image/jpeg")

        if not features.check("webp"):
            self.skipTest("Pillow WebP support is unavailable")
        webp = self.approved / "aike_happy_001.webp"
        Image.new("RGBA", (64, 64), (255, 0, 0, 128)).save(webp, format="WEBP")
        webp_info = self.module.inspect_static_sticker_image(webp)
        self.assertEqual(webp_info.media_type, "image/webp")

    def test_symbolic_link_inside_approved_directory_is_rejected(self):
        outside = Path(self.temp_dir.name) / "outside.png"
        Image.new("RGBA", (64, 64), "red").save(outside, format="PNG")
        linked = self.approved / "linked.png"
        try:
            linked.symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links are unavailable in this environment")
        self.write_manifest(
            [
                self.entry(
                    outside,
                    relative_file=linked.name,
                    sha256=self.sha256(outside),
                    bytes=outside.stat().st_size,
                )
            ]
        )

        library = self.module.load_approved_sticker_library(self.root)

        self.assertEqual(library.assets, ())
        self.assertEqual(library.issues[0].code, "unsafe_file_link")

    def test_byte_dimension_and_pixel_limits_fail_closed(self):
        path = self.write_png(size=(64, 64))
        cases = (
            (self.module.StickerLimits(max_file_bytes=1), "file_size_out_of_range"),
            (
                self.module.StickerLimits(max_dimension=63),
                "image_dimensions_out_of_range",
            ),
            (
                self.module.StickerLimits(max_pixels=4095),
                "image_dimensions_out_of_range",
            ),
        )
        for limits, expected in cases:
            with self.subTest(limits=limits):
                self.assert_error_code(
                    expected,
                    lambda limits=limits: self.module.inspect_static_sticker_image(
                        path,
                        limits=limits,
                    ),
                )
        self.assert_error_code(
            "invalid_limits",
            lambda: self.module.StickerLimits(max_file_bytes=0).validate(),
        )

    def test_invalid_entries_are_isolated_without_expanding_scope(self):
        first = self.write_png()
        second = self.write_png("aike_shy_001.png")
        valid = self.entry(first)
        invalid = self.entry(
            second,
            sticker_id="aike_shy_001",
            moods=["unknown"],
        )
        self.write_manifest([valid, invalid])

        library = self.module.load_approved_sticker_library(self.root)

        self.assertEqual([asset.sticker_id for asset in library.assets], ["aike_happy_001"])
        self.assertEqual(library.invalid_count, 1)
        self.assertEqual(library.issues[0].sticker_id, "aike_shy_001")
        self.assertEqual(library.issues[0].code, "invalid_moods")

    def test_duplicate_id_file_and_hash_are_rejected(self):
        first = self.write_png()
        second = self.write_png("aike_shy_001.png")
        second.write_bytes(first.read_bytes())
        cases = (
            (self.entry(second), "duplicate_sticker_id"),
            (
                self.entry(second, sticker_id="aike_shy_001"),
                "duplicate_sha256",
            ),
        )
        for duplicate, expected in cases:
            with self.subTest(expected=expected):
                self.write_manifest([self.entry(first), duplicate])
                library = self.module.load_approved_sticker_library(self.root)
                self.assertEqual(library.invalid_count, 1)
                self.assertEqual(library.issues[0].code, expected)

        different = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
        different.save(second, format="PNG")
        duplicate_file = self.entry(
            second,
            sticker_id="aike_shy_001",
            relative_file=first.name,
            sha256=self.sha256(first),
            bytes=first.stat().st_size,
        )
        self.write_manifest([self.entry(first), duplicate_file])
        library = self.module.load_approved_sticker_library(self.root)
        self.assertEqual(library.issues[0].code, "duplicate_relative_file")

    def test_manifest_schema_size_and_json_are_strict(self):
        path = self.write_png()
        self.write_manifest([self.entry(path)], schema_version=999)
        self.assert_error_code(
            "unsupported_schema_version",
            lambda: self.module.load_approved_sticker_library(self.root),
        )

        (self.root / "library.json").write_text("not-json", encoding="utf-8")
        self.assert_error_code(
            "manifest_invalid_json",
            lambda: self.module.load_approved_sticker_library(self.root),
        )

        (self.root / "library.json").write_bytes(
            b"x" * (self.module.MAX_MANIFEST_BYTES + 1)
        )
        self.assert_error_code(
            "manifest_size_out_of_range",
            lambda: self.module.load_approved_sticker_library(self.root),
        )

    def test_approval_time_must_be_timezone_aware_iso(self):
        path = self.write_png()
        for approved_at in ("not-a-time", "2026-07-13T10:30:00"):
            with self.subTest(approved_at=approved_at):
                self.write_manifest([self.entry(path, approved_at=approved_at)])
                library = self.module.load_approved_sticker_library(self.root)
                self.assertEqual(library.issues[0].code, "invalid_approved_at")

    def test_module_has_no_network_database_nonebot_or_send_dependency(self):
        source = (AI_CHAT_ROOT / "sticker_library.py").read_text(encoding="utf-8").lower()
        for forbidden in (
            "httpx",
            "tavily",
            "sqlite",
            "database",
            "nonebot",
            "messagesegment",
            "send_private_msg",
            "ask_llm",
            "mainagent",
        ):
            self.assertNotIn(forbidden, source)

    def test_missing_inbox_is_reported_without_creating_it(self):
        inbox = self.root / "inbox"

        report = self.module.inspect_sticker_candidates(self.root)

        self.assertEqual(report.status, "missing")
        self.assertFalse(inbox.exists())
        self.assertIn("未自动创建", self.module.format_sticker_candidate_report(report))

    def test_candidate_scan_reports_safe_id_and_no_path_or_file_name(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        file_name = "private-owner-file.png"
        path = inbox / file_name
        Image.new("RGBA", (64, 64), "red").save(path, format="PNG")
        full_hash = self.sha256(path)

        report = self.module.inspect_sticker_candidates(self.root)
        formatted = self.module.format_sticker_candidate_report(report)

        self.assertEqual(report.status, "ready")
        self.assertEqual(report.scanned_count, 1)
        self.assertEqual(report.eligible_count, 1)
        self.assertEqual(report.rejected_count, 0)
        candidate = report.candidates[0]
        self.assertEqual(candidate.candidate_id, f"candidate_{full_hash[:12]}")
        self.assertEqual(candidate.short_sha256, full_hash[:12])
        self.assertEqual(candidate.media_type, "image/png")
        self.assertNotIn(file_name, formatted)
        self.assertNotIn(str(inbox), formatted)
        self.assertNotIn(full_hash, formatted)
        self.assertIn("未移动、改写、批准或发送", formatted)
        self.assertFalse((self.root / "library.json").exists())

    def test_candidate_metadata_directory_and_oversize_are_rejected(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        metadata = PngInfo()
        metadata.add_text("Comment", "owner-only")
        Image.new("RGBA", (64, 64), "red").save(
            inbox / "metadata.png",
            format="PNG",
            pnginfo=metadata,
        )
        (inbox / "nested").mkdir()
        (inbox / "oversize.png").write_bytes(b"x" * 1025)

        report = self.module.inspect_sticker_candidates(
            self.root,
            limits=self.module.StickerLimits(
                max_file_bytes=1024,
                max_dynamic_file_bytes=1024,
            ),
        )

        self.assertEqual(report.scanned_count, 3)
        self.assertEqual(report.eligible_count, 0)
        self.assertEqual(report.rejected_count, 3)
        self.assertEqual(
            {candidate.issue_code for candidate in report.candidates},
            {"metadata_present", "non_regular_file", "file_size_out_of_range"},
        )

    def test_duplicate_candidate_content_is_rejected_after_first_file(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        first = inbox / "first.png"
        second = inbox / "second.png"
        Image.new("RGBA", (64, 64), "red").save(first, format="PNG")
        second.write_bytes(first.read_bytes())

        report = self.module.inspect_sticker_candidates(self.root)

        self.assertEqual(report.eligible_count, 1)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.candidates[1].issue_code, "duplicate_candidate_content")

    def test_candidate_scan_rejects_more_than_fixed_entry_budget(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        for index in range(self.module.MAX_CANDIDATE_ENTRIES + 1):
            (inbox / f"candidate-{index:03d}.png").touch()

        report = self.module.inspect_sticker_candidates(self.root)

        self.assertEqual(report.status, "too_many_entries")
        self.assertEqual(report.candidates, ())
        self.assertIn(
            str(self.module.MAX_CANDIDATE_ENTRIES),
            self.module.format_sticker_candidate_report(report),
        )

    def test_candidate_symbolic_link_is_rejected_when_supported(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        outside = Path(self.temp_dir.name) / "outside-candidate.png"
        Image.new("RGBA", (64, 64), "red").save(outside, format="PNG")
        link = inbox / "linked.png"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links are unavailable in this environment")

        report = self.module.inspect_sticker_candidates(self.root)

        self.assertEqual(report.eligible_count, 0)
        self.assertEqual(report.candidates[0].issue_code, "unsafe_file_link")

    def test_candidate_report_limits_expanded_items(self):
        candidates = tuple(
            self.module.StickerCandidate(
                candidate_id=f"candidate_{index:012d}",
                short_sha256=f"{index:012d}",
                eligible=False,
                issue_code="image_decode_failed",
            )
            for index in range(self.module.MAX_CANDIDATE_REPORT_ITEMS + 2)
        )
        report = self.module.StickerCandidateReport(
            status="ready",
            scanned_count=len(candidates),
            eligible_count=0,
            rejected_count=len(candidates),
            candidates=candidates,
        )

        formatted = self.module.format_sticker_candidate_report(report)

        self.assertIn("其余 2 项未展开", formatted)
        self.assertNotIn(candidates[-1].candidate_id, formatted)

    def test_qq_candidate_check_is_owner_private_read_only_and_lazy_loaded(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        declaration = source.index('sticker_check_cmd = on_command(')
        handler = source.index("@sticker_check_cmd.handle()")
        handler_end = source.index("@sticker_analyze_cmd.handle()", handler)
        block = source[handler:handler_end]

        self.assertIn('"表情检查"', source[declaration:handler])
        self.assertIn("await require_owner(event, matcher)", block)
        self.assertIn("isinstance(event, PrivateMessageEvent)", block)
        self.assertIn("if not config.enable_local_stickers", block)
        self.assertIn("from .sticker_library import", block)
        self.assertIn("inspect_sticker_candidates(", block)
        self.assertIn("format_sticker_candidate_report(report)", block)
        for forbidden in (
            "MessageSegment.image",
            "send_private_msg",
            "ask_llm",
            "run_main_agent",
            "Tavily",
            "library.json",
            "write_",
            "mkdir",
            "replace(",
            "unlink(",
        ):
            self.assertNotIn(forbidden, block)

    def test_candidate_file_resolver_uses_only_safe_short_hash_id(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        candidate = inbox / "private-name.gif"
        frames = [Image.new("RGBA", (64, 64), "red"), Image.new("RGBA", (64, 64), "blue")]
        frames[0].save(
            candidate,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )
        candidate_id = f"candidate_{self.sha256(candidate)[:12]}"

        resolved = self.module.resolve_sticker_candidate_file(self.root, candidate_id)

        self.assertEqual(resolved, candidate.resolve())
        self.assert_error_code(
            "invalid_candidate_id",
            lambda: self.module.resolve_sticker_candidate_file(
                self.root,
                "candidate_../../private-name.gif",
            ),
        )
        self.assert_error_code(
            "candidate_not_found",
            lambda: self.module.resolve_sticker_candidate_file(
                self.root,
                "candidate_000000000000",
            ),
        )

    def test_qq_candidate_analysis_is_exact_owner_private_and_no_write_or_send(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        declaration = source.index('sticker_analyze_cmd = on_command(')
        handler = source.index("@sticker_analyze_cmd.handle()")
        handler_end = source.index("def sticker_limits_from_config", handler)
        block = source[handler:handler_end]

        self.assertIn('"表情分析"', source[declaration:handler])
        self.assertIn("await require_owner(event, matcher)", block)
        self.assertIn("isinstance(event, PrivateMessageEvent)", block)
        self.assertIn("if not config.enable_local_stickers", block)
        self.assertIn("if not config.enable_vision", block)
        self.assertIn("resolve_sticker_candidate_file", block)
        self.assertIn("build_sticker_contact_sheet", block)
        self.assertIn("analyze_sticker_contact_sheet", block)
        self.assertIn("asyncio.to_thread", block)
        for forbidden in (
            "MessageSegment.image",
            "send_private_msg",
            "ask_llm",
            "run_main_agent",
            "Tavily",
            "library.json",
            "write_",
            "mkdir",
            "unlink(",
            "replace(",
        ):
            self.assertNotIn(forbidden, block)

    def test_dynamic_gif_is_inspected_and_reported_with_animation_metadata(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        gif = inbox / "animated.gif"
        frames = [
            Image.new("RGBA", (64, 64), color)
            for color in ("red", "green", "blue", "yellow")
        ]
        frames[0].save(
            gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )

        info = self.module.inspect_sticker_image(gif)
        report = self.module.inspect_sticker_candidates(self.root)
        formatted = self.module.format_sticker_candidate_report(report)

        self.assertTrue(info.animated)
        self.assertEqual(info.media_type, "image/gif")
        self.assertEqual(info.frame_count, 4)
        self.assertEqual(info.duration_ms, 400)
        self.assertEqual(info.loop_count, 0)
        self.assertEqual(info.total_decoded_pixels, 64 * 64 * 4)
        self.assertEqual(report.eligible_count, 1)
        self.assertTrue(report.candidates[0].animated)
        self.assertIn("动态 4 帧/400ms", formatted)

    def test_dynamic_animation_budgets_are_enforced(self):
        gif = self.approved / "budget.gif"
        frames = [Image.new("RGBA", (64, 64), (index, 0, 0, 255)) for index in range(4)]
        frames[0].save(
            gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )
        cases = (
            (
                self.module.StickerLimits(max_animation_frames=3),
                "animation_frame_budget_exceeded",
            ),
            (
                self.module.StickerLimits(max_animation_duration_ms=300),
                "animation_duration_budget_exceeded",
            ),
            (
                self.module.StickerLimits(max_animation_decoded_pixels=16_000),
                "animation_pixel_budget_exceeded",
            ),
        )
        for limits, expected in cases:
            with self.subTest(expected=expected):
                self.assert_error_code(
                    expected,
                    lambda limits=limits: self.module.inspect_sticker_image(
                        gif,
                        limits=limits,
                    ),
                )

        fast = self.approved / "fast.gif"
        frames[0].save(
            fast,
            format="GIF",
            save_all=True,
            append_images=frames[1:2],
            duration=10,
            loop=0,
        )
        self.assert_error_code(
            "invalid_frame_duration",
            lambda: self.module.inspect_sticker_image(fast),
        )

    def test_dynamic_apng_and_webp_are_detected_when_supported(self):
        frames = [
            Image.new("RGBA", (64, 64), "red"),
            Image.new("RGBA", (64, 64), "blue"),
        ]
        apng = self.approved / "animated.png"
        frames[0].save(
            apng,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )
        apng_info = self.module.inspect_sticker_image(apng)
        self.assertTrue(apng_info.animated)
        self.assertEqual(apng_info.media_type, "image/png")

        webp = self.approved / "animated.webp"
        try:
            frames[0].save(
                webp,
                format="WEBP",
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0,
            )
        except OSError:
            self.skipTest("Pillow animated WebP support is unavailable")
        webp_info = self.module.inspect_sticker_image(webp)
        self.assertTrue(webp_info.animated)
        self.assertEqual(webp_info.media_type, "image/webp")

    def test_contact_sheet_samples_animation_in_memory(self):
        gif = self.approved / "contact.gif"
        frames = [
            Image.new("RGBA", (80, 64), (index * 20, 0, 255 - index * 20, 255))
            for index in range(10)
        ]
        frames[0].save(
            gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )

        sheet = self.module.build_sticker_contact_sheet(gif, max_frames=6, cell_size=128)

        self.assertTrue(sheet.png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(sheet.source_frame_count, 10)
        self.assertLessEqual(len(sheet.frame_indices), 6)
        self.assertIn(0, sheet.frame_indices)
        self.assertIn(9, sheet.frame_indices)
        self.assertGreater(sheet.width, 0)
        self.assertGreater(sheet.height, 0)


if __name__ == "__main__":
    unittest.main()
