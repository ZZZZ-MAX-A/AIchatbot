"""Run one bounded Bilibili preview; private messages require --send-one."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bilibili_connector import BilibiliClient, BilibiliConnectorError, BindingStore, CredentialStore
from src.bilibili_browse import BrowseClient, diagnose, preview, save_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "preview", "memory-status", "diagnose"), help="inspect 只读候选；preview 角色和 QQ 记忆预览；memory-status 只检查记忆范围；diagnose 脱敏诊断单片来源")
    parser.add_argument("--bvid", help="diagnose 需要的视频 BVID")
    parser.add_argument("--page", type=int, default=1, help="diagnose 检查的分 P（默认1）")
    parser.add_argument("--per-source", type=int, choices=range(1, 9), default=6, help="每来源候选上限（默认6，最多8）")
    parser.add_argument("--max-selected", type=int, choices=(1, 2), default=2, help="精选上限（默认2）")
    parser.add_argument("--without-qq-memory", action="store_true", help="仅角色卡预览，不读取 QQ 记忆，用于对照")
    parser.add_argument("--subtitle-transport", choices=("browser", "api"), default="browser",
                        help="preview 字幕默认使用固定浏览器；api 为原接口对照，不自动回退")
    parser.add_argument("--send-one", action="store_true", help="preview 通过校验后，实际私信提交第一条可分享视频，默认不发送")
    args = parser.parse_args(argv)
    if args.command == "diagnose" and not args.bvid:
        parser.error("diagnose 需要 --bvid")
    if args.send_one and args.command != "preview":
        parser.error("--send-one 仅适用于 preview")
    model = browser = None
    try:
        binding = BindingStore().load()
        if args.command in {"preview", "memory-status"}:
            from src.bilibili_persona import PersonaModel, persona_settings, load_persona_configuration
            from src.bilibili_memory import load_owner_memory
            config = load_persona_configuration()
            settings = persona_settings(binding, config=config)
            memory = None if args.without_qq_memory else load_owner_memory(binding, config)
            if args.command == "memory-status":
                print(json.dumps(memory.public_status() if memory else {"enabled": False, "status": "disabled"}, ensure_ascii=False, indent=2))
                return 0
            model = PersonaModel(*settings, memory=memory)
            print("QQ 记忆：" + (memory.public_status()["status"] if memory else "disabled") + "（仅显示状态，不打印正文）。", flush=True)
        with ExitStack() as stack:
            if model and args.subtitle_transport == "browser":
                from src.bilibili_browser_browse import browser_browse_client
                browser = stack.enter_context(browser_browse_client(None, binding))
                account = browser.account_client
            else:
                account = stack.enter_context(BilibiliClient(CredentialStore().load()))
                browser = BrowseClient(account)
            if args.command == "diagnose":
                browser = BrowseClient(account)
                report = diagnose(browser, binding, args.bvid, page=args.page)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return int(report["status"] not in {"ok", "unavailable"} or report["diagnostics"]["write_failures"] > 0)
            print("正在读取两个候选来源和详情；报告保存在本机。", flush=True)
            if model:
                print("随后进行角色初筛、字幕读取与有依据的总结（最多3次模型请求）；字幕线路=" + args.subtitle_transport, flush=True)
            report = preview(browser, binding, model, per_source=args.per_source, max_selected=args.max_selected)
            if model:
                try:
                    from src.bilibili_daily_note import BilibiliDailyNoteWriter
                    report["daily_note"] = BilibiliDailyNoteWriter(binding, config).update(report)
                except Exception:
                    # A private local journal failure must not trigger another model call or a resend.
                    report["daily_note"] = {"status": "unavailable"}
            json_path, md_path = save_report(report)
            if args.send_one:
                from src.bilibili_share import share_one
                from src.bilibili_history_bridge import BilibiliHistoryWriter
                history_writer = BilibiliHistoryWriter(binding, config)
                try:
                    report["delivery"] = share_one(account, binding, report, dry_run=False, history_writer=history_writer)
                    report["messages_sent"] = int(report["delivery"].get("platform_accepted") is True)
                except BilibiliConnectorError:
                    report["delivery"] = {"status": "failed_or_unknown", "owner_received_confirmed": False}
                    save_report(report)
                    raise
                json_path, md_path = save_report(report)
        for name, source in report["sources"].items():
            print(f"{name}: {source['status']}；接受候选={source.get('accepted', 0)}")
        print(f"去重候选={len(report['candidates'])}；精选={len(report['results'])}；总结={sum(r['status'] == 'summarized' for r in report['results'])}")
        print(f"模型调用={len(report['usage'])}；返回总token={sum(u['total_tokens'] or 0 for u in report['usage'])}")
        if "daily_note" in report:
            print("今日观影小记=" + report["daily_note"]["status"] + "；复用本轮结果，不额外调用模型。")
        if any("qq_memory" in usage for usage in report["usage"]):
            print(f"QQ 记忆注入字符合计={sum(u.get('qq_memory', {}).get('characters', 0) for u in report['usage'])}；供应商返回用量已包含记忆输入。")
        print(f"状态={report['status']}；平台报告发送成功={report['messages_sent']}。\n预览：{md_path}\n结构化记录：{json_path}")
        if args.send_one:
            print("私信状态=" + report["delivery"]["status"] + "；接口成功仍需主人确认实际收到。")
        print(f"脱敏诊断日志：{browser.diagnostics.path}；日志写入失败={browser.diagnostics.write_failures}")
        return int(report["status"] == "error" or (args.send_one and report["delivery"]["status"] != "sent"))
    except BilibiliConnectorError as exc:
        print(f"未完成：{exc}", file=sys.stderr)
        if browser:
            print(f"脱敏诊断日志：{browser.diagnostics.path}；日志写入失败={browser.diagnostics.write_failures}", file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("未完成：本地文件或配置读写失败。", file=sys.stderr)
        return 1
    finally:
        if browser:
            browser.close()
        if model:
            model.close()


if __name__ == "__main__":
    raise SystemExit(main())
