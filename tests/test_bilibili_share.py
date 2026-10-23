from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

from src.bilibili_browse import share_draft
from src.bilibili_connector import BilibiliBinding, BilibiliConnectorError, PrivateMessageResult
from src.bilibili_share import share_one

BV = "BV1xx411c7mD"
BINDING = BilibiliBinding("aike", "aike", "101", "202")


class ShareTests(unittest.TestCase):
    def setUp(self):
        self.account = MagicMock()
        self.account.send_private_message.return_value = PrivateMessageResult(False, True)
        url = "https://www.bilibili.com/video/" + BV
        summary = {"content_alignment": "consistent", "alignment_reason": "合成字幕主题相符", "worth_sharing": True,
                   "why_share": "这个主题很有意思", "claims": [{"text": "视频解释了测试主题", "quote": "测试主题", "segment_id": "S1"}]}
        evidence = {"basis": "subtitles", "partial": False,
                    "pages": [{"page": 1, "status": "available", "identity_verified": True, "automatic": False}],
                    "segments": [{"id": "S1", "page": 1, "text": "这段解释了测试主题"}]}
        result = {"bvid": BV, "url": url, "status": "summarized", "eligible_to_share": True,
                  "evidence": evidence, "summary": summary, "draft": share_draft({"url": url}, summary, evidence)}
        self.report = {"status": "ok", "results": [result], "candidates": [{"bvid": BV, "url": url, "detail_status": "ok"}]}

    def test_default_is_dry_run_and_pinned_owner_binding(self):
        result = share_one(self.account, BINDING, self.report)
        self.assertEqual(result["status"], "dry_run")
        args, kwargs = self.account.send_private_message.call_args
        self.assertIs(args[0], BINDING)
        self.assertTrue(kwargs["dry_run"])
        self.assertEqual(kwargs["delivery_key"], "video-share-v1:" + BV)

    def test_explicit_send_submits_at_most_one_result(self):
        self.report["results"].append(copy.deepcopy(self.report["results"][0]))
        self.account.send_private_message.return_value = PrivateMessageResult(True, False, 200, 0, "", "fixture-request")
        result = share_one(self.account, BINDING, self.report, dry_run=False)
        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["platform_accepted"])
        self.assertFalse(result["owner_received_confirmed"])
        self.account.send_private_message.assert_called_once()
        self.assertFalse(self.account.send_private_message.call_args.kwargs["dry_run"])
        self.assertEqual(self.account.send_private_message.call_args.args[1],
                         "这个主题很有意思\nhttps://www.bilibili.com/video/" + BV)

    def test_persona_message_is_not_truncated_or_wrapped_in_a_report(self):
        result = self.report["results"][0]
        message = "这段讲解让我想到一个很有意思的细节。" * 5
        self.assertGreater(len(message), 85)
        self.assertLessEqual(len(message), 100)
        result["summary"]["why_share"] = "  " + message + "  "
        result["evidence"]["partial"] = True
        result["evidence"]["pages"][0]["automatic"] = True
        result["draft"] = share_draft({"url": result["url"]}, result["summary"], result["evidence"])
        share_one(self.account, BINDING, self.report, dry_run=False)
        self.assertEqual(self.account.send_private_message.call_args.args[1], message + "\n" + result["url"])

    def test_error_or_withdrawn_report_never_sends(self):
        for report in ({**self.report, "status": "error"}, {**self.report, "withdrawal_reason": "fixture"}):
            with self.assertRaises(BilibiliConnectorError):
                share_one(self.account, BINDING, report, dry_run=False)
        self.account.send_private_message.assert_not_called()

    def test_no_eligible_video_does_not_force_share(self):
        self.report["results"][0]["eligible_to_share"] = False
        result = share_one(self.account, BINDING, self.report, dry_run=False)
        self.assertEqual(result["status"], "no_eligible_video")
        self.account.send_private_message.assert_not_called()

    def test_tampered_link_draft_or_summary_are_rejected(self):
        mutations = (
            lambda r: r.update(url="https://outside.test/"),
            lambda r: r.update(draft="unverified replacement"),
            lambda r: r["summary"].update(worth_sharing=False),
            lambda r: r["summary"].update(content_alignment="mismatch"),
            lambda r: r["summary"]["claims"][0].update(quote="没有出现的引用"),
        )
        for mutation in mutations:
            report = copy.deepcopy(self.report)
            mutation(report["results"][0])
            with self.subTest(mutation=mutation), self.assertRaises(BilibiliConnectorError):
                share_one(self.account, BINDING, report, dry_run=False)
        self.account.send_private_message.assert_not_called()

    def test_missing_or_wrong_page_identity_blocks_send(self):
        for key, value in (("identity_verified", False), ("status", "error"), ("page", 2)):
            report = copy.deepcopy(self.report)
            report["results"][0]["evidence"]["pages"][0][key] = value
            with self.subTest(key=key), self.assertRaises(BilibiliConnectorError):
                share_one(self.account, BINDING, report, dry_run=False)
        self.account.send_private_message.assert_not_called()

    def test_different_wording_keeps_same_video_deduplication_key(self):
        share_one(self.account, BINDING, self.report, dry_run=False)
        first = self.account.send_private_message.call_args.kwargs["delivery_key"]
        result = self.report["results"][0]
        result["summary"]["why_share"] = "新的分享措辞"
        result["draft"] = share_draft({"url": result["url"]}, result["summary"], result["evidence"])
        share_one(self.account, BINDING, self.report, dry_run=False)
        self.assertEqual(self.account.send_private_message.call_args.kwargs["delivery_key"], first)

    def test_network_or_platform_error_is_not_retried(self):
        self.account.send_private_message.side_effect = BilibiliConnectorError("unknown")
        with self.assertRaises(BilibiliConnectorError):
            share_one(self.account, BINDING, self.report, dry_run=False)
        self.account.send_private_message.assert_called_once()

    def test_only_accepted_send_is_archived_with_actual_sent_text(self):
        writer = MagicMock()
        writer.record_share.return_value = {"status": "saved"}
        self.account.send_private_message.return_value = PrivateMessageResult(True, False, 200, 0, "", "fixture-request")
        result = share_one(self.account, BINDING, self.report, dry_run=False, history_writer=writer)
        writer.record_share.assert_called_once()
        self.assertEqual(writer.record_share.call_args.kwargs["text"], self.report["results"][0]["draft"])
        self.assertEqual(result["history"]["status"], "saved")

    def test_preview_and_failed_send_never_enter_history(self):
        writer = MagicMock()
        share_one(self.account, BINDING, self.report, history_writer=writer)
        writer.record_share.assert_not_called()
        self.account.send_private_message.side_effect = BilibiliConnectorError("unknown")
        with self.assertRaises(BilibiliConnectorError):
            share_one(self.account, BINDING, self.report, dry_run=False, history_writer=writer)
        writer.record_share.assert_not_called()

    def test_history_failure_does_not_retry_or_change_successful_delivery(self):
        writer = MagicMock()
        writer.record_share.side_effect = RuntimeError("PRIVATE_STORAGE_DETAILS")
        self.account.send_private_message.return_value = PrivateMessageResult(True, False, 200, 0, "", "fixture-request")
        result = share_one(self.account, BINDING, self.report, dry_run=False, history_writer=writer)
        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["platform_accepted"])
        self.assertEqual(result["history"]["status"], "save_failed")
        self.assertNotIn("PRIVATE_STORAGE_DETAILS", str(result))
        self.account.send_private_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
