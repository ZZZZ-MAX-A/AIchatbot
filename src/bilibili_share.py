"""Submit at most one validated preview result to the pinned Bilibili owner."""
from __future__ import annotations

from .bilibili_browse import BV, share_draft, validate_summary
from .bilibili_connector import BilibiliConnectorError, BilibiliDuplicateDelivery, BilibiliShareLimit


def share_one(account, binding, report: dict, *, dry_run: bool = True, history_writer=None) -> dict:
    binding.validate()
    if report.get("status") not in {"ok", "partial"} or report.get("withdrawal_reason"):
        raise BilibiliConnectorError("本轮预览异常或已撤回，停止私信提交")
    candidates = {c["bvid"]: c for c in report.get("candidates", []) if c.get("detail_status") == "ok"}
    for result in report.get("results", []):
        if result.get("status") != "summarized" or result.get("eligible_to_share") is not True:
            continue
        try:
            bvid = result["bvid"]
            if not isinstance(bvid, str) or not BV.fullmatch(bvid) or bvid not in candidates:
                raise ValueError()
            url = f"https://www.bilibili.com/video/{bvid}"
            if result["url"] != url or candidates[bvid]["url"] != url:
                raise ValueError()
            evidence = result["evidence"]
            verified_pages = {p["page"] for p in evidence["pages"]
                              if p["status"] == "available" and p.get("identity_verified") is True}
            if (evidence["basis"] != "subtitles" or not evidence["segments"] or not evidence["pages"] or
                    not verified_pages or any(s["page"] not in verified_pages for s in evidence["segments"]) or
                    any(p["status"] == "error" for p in evidence["pages"]) or
                    any(p.get("identity_verified") is not True for p in evidence["pages"] if p["status"] == "available")):
                raise ValueError()
            summary = validate_summary(result["summary"], evidence)
            if summary["content_alignment"] != "consistent" or summary["worth_sharing"] is not True:
                raise ValueError()
            draft = share_draft({"url": url}, summary, evidence)
            if result["draft"] != draft or not draft or len(draft) > 300:
                raise ValueError()
        except (KeyError, TypeError, ValueError, BilibiliConnectorError):
            raise BilibiliConnectorError("分享结果、字幕引用或规范链接复核失败，未发送私信") from None
        # Stable across rounds and wording changes; the connector hashes the owner pair as well.
        try:
            sent = account.send_private_message(binding, draft, dry_run=dry_run, delivery_key="video-share-v1:" + bvid)
        except BilibiliDuplicateDelivery:
            continue
        except BilibiliShareLimit as exc:
            return {"status": exc.reason, "platform_accepted": False, "owner_received_confirmed": False}
        history_status = {"status": "not_configured"}
        if dry_run or sent.dry_run or not sent.sent:
            history_status = {"status": "not_sent"}
        elif history_writer is not None:
            try:
                history_status = history_writer.record_share(
                    binding, request_id=sent.request_id, text=draft, bvid=bvid,
                    video_title=candidates[bvid].get("title", ""),
                )
            except Exception:
                # Never report an accepted delivery as failed or retry it for a storage error.
                history_status = {"status": "save_failed"}
        return {"status": "dry_run" if sent.dry_run else "sent", "request_id": sent.request_id, "bvid": bvid,
                "platform_accepted": sent.sent, "owner_received_confirmed": False,
                "http_status": sent.http_status, "business_code": sent.code, "history": history_status}
    return {"status": "no_eligible_video", "platform_accepted": False, "owner_received_confirmed": False}
