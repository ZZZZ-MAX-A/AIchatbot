"""Manage Aike's dedicated persistent Edge session without starting the bot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bilibili_browser import PersistentBrowser
from src.bilibili_connector import BindingStore, BilibiliConnectorError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("open", "check", "status", "close", "subtitle-check"),
                        help="open 扫码登录；check 核对账号；status 本地状态；close 保留资料并关闭；subtitle-check 单片网页字幕检查")
    parser.add_argument("--bvid", help="subtitle-check 指定视频 BVID，只打开一个视频页面")
    parser.add_argument("--page", type=int, default=1, help="subtitle-check 检查的分 P，默认1")
    args = parser.parse_args(argv)
    if args.command == "subtitle-check" and not args.bvid:
        parser.error("subtitle-check 需要 --bvid")
    try:
        browser = PersistentBrowser(BindingStore().load())
        if args.command == "subtitle-check":
            from src.bilibili_browser_probe import probe
            result = probe(browser, args.bvid, page=args.page)
        else:
            result = getattr(browser, args.command)()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "open":
            print("已打开爱可专用 Edge。请用爱可的独立 B 站账号扫码登录，随后运行 check；资料会保留。")
        return int((args.command == "check" and result["status"] != "logged_in") or
                   (args.command == "subtitle-check" and (result["status"] not in {"ok", "unavailable"} or
                                                           result["diagnostics"]["write_failures"])))
    except BilibiliConnectorError as exc:
        print(f"未完成：{exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, ImportError):
        print("未完成：专用浏览器文件或依赖不可用，请检查目录权限与项目依赖。", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已中止；专用浏览器资料保留。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
