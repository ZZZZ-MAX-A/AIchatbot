"""Connect the separate Bilibili account without starting the QQ bot.

Run login, bind-owner, status, then send (preview by default).
Cookie values are entered locally with hidden prompts, never as CLI arguments.
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sqlite3
import sys
import warnings

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bilibili_connector import (
    BilibiliBinding, BilibiliClient, BilibiliConnectorError,
    BilibiliCredentials, BindingStore, CredentialStore, DeliveryStore,
    connector_home, redact_uid,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="隐藏输入 Cookie，在线验证账号后加密保存（Windows）")
    sub.add_parser("account", help="只读检查登录账号，显示完整 UID 供本地核对")
    bind = sub.add_parser("bind-owner", help="在线确认当前账号后，绑定主人 UID")
    bind.add_argument("--owner-uid", required=True)
    bind.add_argument("--aike-uid", required=True, help="应与当前登录账号 UID 一致")
    bind.add_argument("--owner-name", default="")
    bind.add_argument("--persona-id", default="aike")
    bind.add_argument("--role-card-key", default="aike", help="仅保存映射标签，本阶段不读取角色卡")
    sub.add_parser("status", help="检查当前账号、身份绑定和互关状态")
    sub.add_parser("deliveries", help="查看最近 20 条本地发送状态，不显示正文")
    send = sub.add_parser("send", help="预览和预检私信；只有 --go 才发送")
    body = send.add_mutually_exclusive_group(required=True)
    body.add_argument("--text", help="私信正文，可包含视频链接")
    body.add_argument("--text-file", type=Path, help="从本地 UTF-8 文件读取正文")
    send.add_argument("--go", action="store_true", help="实际提交到 B 站")
    send.add_argument("--delivery-key", help="显式发送任务 ID；默认按双方 UID 和正文去重")
    return root


def _hidden_input(prompt: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt).strip()
        except getpass.GetPassWarning as exc:
            raise BilibiliConnectorError("当前终端不支持隐藏输入，请在本机 PowerShell 中运行 login") from exc


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "login":
            if sys.platform != "win32":
                raise BilibiliConnectorError("当前凭据存储仅支持 Windows DPAPI")
            print("请在浏览器登录爱可的独立 B 站账号，再从开发者工具 Application → Cookies 复制对应值。")
            print("输入不回显。SESSDATA / bili_jct 必填；buvid3 可回车跳过。不要把 Cookie 发到聊天中。")
            credentials = BilibiliCredentials(_hidden_input("SESSDATA: "), _hidden_input("bili_jct: "), _hidden_input("buvid3（可选）: "))
            with BilibiliClient(credentials) as client:
                account = client.account()
            print(f"验证账号：{account.uname}（UID {account.mid}）")
            if input("确认这是爱可的独立账号？输入 yes 保存：").strip().lower() != "yes":
                print("已取消，未保存新凭据。")
                return 0
            CredentialStore().save(credentials)
            print(f"已验证并使用当前 Windows 用户的 DPAPI 加密保存：{CredentialStore().path}")
            print("可关闭浏览器；登录态失效时重新执行 login。")
            return 0
        if args.command == "deliveries":
            rows = DeliveryStore().recent()
            if not rows:
                print("暂无发送记录。")
            for request_id, state, created_at, code in rows:
                print(f"request_id={request_id} state={state} timestamp={created_at} code={code}")
            return 0
        credentials = CredentialStore().load()
        with BilibiliClient(credentials) as client:
            if args.command == "send":
                binding = BindingStore().load()
                text = args.text if args.text is not None else args.text_file.read_text(encoding="utf-8-sig")
                print(f"{'发送' if args.go else '预览'}目标：主人 UID {redact_uid(binding.owner_mid)}")
                print(f"正文：\n{text.strip()}")
                result = client.send_private_message(binding, text, dry_run=not args.go, delivery_key=args.delivery_key)
                if result.dry_run:
                    print("账号与互关预检通过，未发送私信。加 --go 才会实际提交。")
                else:
                    print(f"B 站接口返回成功（request_id={result.request_id}），请在主人 B 站会话确认收到。")
                return 0
            account = client.account()
            if args.command == "account":
                print(f"已登录：{account.uname}（UID {account.mid}，请仅在本机核对）")
                return 0
            if args.command == "bind-owner":
                binding = BilibiliBinding(args.persona_id, args.role_card_key, args.aike_uid, args.owner_uid, args.owner_name)
                binding.validate()
                if account.mid != binding.aike_mid:
                    raise BilibiliConnectorError("当前登录账号与 --aike-uid 不一致，未保存绑定")
                relation = client.relation(binding.owner_mid)
                BindingStore().save(binding)
                print(f"已绑定爱可 {redact_uid(binding.aike_mid)} → 主人 {redact_uid(binding.owner_mid)}")
                print(f"互关：{'是' if relation.mutual else '否；请在 B 站完成互关后再运行 status'}")
                return 0
            if args.command == "status":
                print(f"存储目录：{connector_home()}")
                print(f"登录状态：已登录；当前账号 UID {redact_uid(account.mid)}")
                if not BindingStore().path.exists():
                    print("主人尚未绑定，请运行 bind-owner。")
                    return 2
                binding = BindingStore().load()
                matched = account.mid == binding.aike_mid
                print(f"身份绑定：{'匹配' if matched else '不匹配，停止私信'}")
                print(f"角色映射标签：{binding.persona_id} / {binding.role_card_key}（尚未读取角色卡）")
                print(f"主人 UID：{redact_uid(binding.owner_mid)}")
                if not matched:
                    return 2
                relation = client.relation(binding.owner_mid)
                print(f"互关：{'是' if relation.mutual else '否，停止私信'}")
                return 0 if relation.mutual else 2
        raise BilibiliConnectorError("未知命令")
    except BilibiliConnectorError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, sqlite3.Error):
        print("错误：本地凭据、绑定、正文或发送记录无法读写，请检查目录权限和文件状态。若刚提交过私信，请先检查 B 站会话，勿直接重发。", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\n已中止。如中止前已提交私信，请先检查会话和 deliveries，勿直接重发。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
