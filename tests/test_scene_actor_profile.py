from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class SceneActorProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.scene_actor_profile",
            AI_CHAT_ROOT / "scene_actor_profile.py",
        )

    def test_linyin_uses_legacy_route_and_loaded_private_examples(self):
        with TemporaryDirectory() as directory:
            style_path = Path(directory) / "linyin.md"
            style_path.write_text("风格示例内容", encoding="utf-8")

            profile = self.module.build_scene_actor_profile(
                "linyin",
                style_path=style_path,
            )

        self.assertEqual(profile.completion_route, "legacy")
        self.assertEqual(profile.reasoning_effort, "low")
        self.assertEqual(profile.style_examples.status, "loaded")
        self.assertEqual(profile.style_examples.content, "风格示例内容")
        self.assertEqual(profile.style_examples.char_count, 6)
        self.assertNotIn("风格示例内容", repr(profile.style_examples))

    def test_aike_route_is_unchanged_and_does_not_load_examples(self):
        profile = self.module.build_scene_actor_profile("aike")

        self.assertEqual(profile.completion_route, "auto")
        self.assertIsNone(profile.reasoning_effort)
        self.assertEqual(profile.style_examples.status, "not_applicable")
        self.assertEqual(profile.style_examples.content, "")

    def test_missing_examples_fail_open_without_content(self):
        with TemporaryDirectory() as directory:
            profile = self.module.build_scene_actor_profile(
                "linyin",
                style_path=Path(directory) / "missing.md",
            )

        self.assertEqual(profile.completion_route, "legacy")
        self.assertEqual(profile.reasoning_effort, "low")
        self.assertEqual(profile.style_examples.status, "missing")
        self.assertEqual(profile.style_examples.content, "")
        self.assertEqual(profile.style_examples.char_count, 0)

    def test_empty_and_oversized_examples_are_not_injected(self):
        with TemporaryDirectory() as directory:
            empty_path = Path(directory) / "empty.md"
            empty_path.write_text("  \n", encoding="utf-8")
            empty_result = self.module.load_linyin_deepseek_group_style_examples(
                empty_path
            )

            large_path = Path(directory) / "large.md"
            large_path.write_text(
                "x" * (self.module.MAX_STYLE_EXAMPLE_CHARS + 1),
                encoding="utf-8",
            )
            large_result = self.module.load_linyin_deepseek_group_style_examples(
                large_path
            )

        self.assertEqual(empty_result.status, "empty")
        self.assertEqual(large_result.status, "too_large")
        self.assertEqual(large_result.content, "")

    def test_log_fields_never_include_content_or_unbounded_values(self):
        fields = self.module.format_scene_style_example_log_fields(
            "loaded",
            999_999,
        )
        invalid = self.module.format_scene_style_example_log_fields(
            "private text",
            "not-a-number",
        )

        self.assertEqual(
            fields,
            f"style_examples=loaded style_example_chars={self.module.MAX_STYLE_EXAMPLE_CHARS}",
        )
        self.assertEqual(
            invalid,
            "style_examples=unreadable style_example_chars=0",
        )


if __name__ == "__main__":
    unittest.main()
