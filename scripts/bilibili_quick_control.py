"""Readable controls for the double-click Bilibili launchers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "bilibili_autobrowse.py"


def control(command: str, *, inbox=False) -> dict:
    entry = ROOT / "scripts" / "bilibili_inbox.py" if inbox else ENTRY
    result = subprocess.run(
        [sys.executable, str(entry), command], cwd=ROOT,
        capture_output=True, encoding="utf-8", errors="replace", timeout=15,
    )
    if result.returncode:
        raise RuntimeError("control_failed")
    records = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    if not records or not all(isinstance(record, dict) for record in records):
        raise RuntimeError("invalid_status")
    return {key: value for record in records for key, value in record.items()}


def show_status(state: dict, *, inbox=False) -> None:
    if inbox:
        print("私聊回复：" + ("运行中" if state.get("running") else "已停止"))
        if state.get("running"):
            print("当前阶段：" + {"waiting": "等待新消息", "replying": "正在回复", "backoff": "连接异常，等待下次尝试"}.get(state.get("phase"), "初始化"))
            if state.get("next_poll"):
                print("下次收件检查：" + str(state["next_poll"]))
        counts = state.get("counts", {})
        print(f"待处理消息：{counts.get('pending_messages', 0)}；已回复：{counts.get('sent', 0)}；发送结果不明：{counts.get('unknown', 0)}")
        print("关闭本窗口不会停止私聊回复；双击“停止B站私聊回复.cmd”可停止。")
        return
    print("自动浏览：" + ("运行中" if state.get("running") else "已停止"))
    if state.get("running"):
        print("主动私信分享：" + ("已开启" if state.get("send_enabled") else "未开启（仅浏览）"))
        phases = {"waiting": "等待下一轮", "browsing": "正在浏览", "quiet_hours": "休息时段"}
        phase = state.get("phase")
        if phase:
            print("当前阶段：" + phases.get(phase, phase))
        if state.get("next_due"):
            print("下次计划时间：" + str(state["next_due"]))
    if state.get("today"):
        print("今天已占用浏览轮次：" + str(state["today"].get("rounds", 0)))
    quota = state.get("share_quota")
    if quota:
        print(f"今天分享额度：已占用 {quota['used_today']} / {quota['daily_limit']}，剩余 {quota['remaining_today']}")
    print("关闭本窗口不会停止后台；双击“停止B站自动浏览.cmd”可一起停止浏览和私聊回复。")


def stop(*, inbox=False) -> int:
    targets = (True,) if inbox else (False, True)
    pending = {}
    failed = False
    # Request both stops before waiting for either worker to finish.
    for target in targets:
        name = "私聊回复" if target else "自动浏览"
        try:
            result = control("stop", inbox=target)
            if result.get("status") == "not_running":
                print(name + "已经停止，无需重复操作。")
            elif result.get("status") in {"stop_requested", "starting_retry_stop"}:
                pending[target] = result["status"]
                print("正在停止" + name + "，当前请求可能需要先完成……", flush=True)
            else:
                raise RuntimeError("unexpected_stop_status")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            failed = True
            print(name + "停止请求未完成，请查看对应状态和日志。", file=sys.stderr)
    deadline = time.monotonic() + 15
    while pending and time.monotonic() < deadline:
        time.sleep(1)
        for target, stop_status in list(pending.items()):
            name = "私聊回复" if target else "自动浏览"
            try:
                state = control("status", inbox=target)
                if not state.get("running"):
                    print(name + "已停止。")
                    del pending[target]
                elif stop_status == "starting_retry_stop":
                    result = control("stop", inbox=target)
                    if result.get("status") == "not_running":
                        print(name + "已停止。")
                        del pending[target]
                    elif result.get("status") in {"stop_requested", "starting_retry_stop"}:
                        pending[target] = result["status"]
                    else:
                        raise RuntimeError("unexpected_stop_status")
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                failed = True
                del pending[target]
                print(name + "状态未能确认，请稍后查看。", file=sys.stderr)
    for target, stop_status in pending.items():
        name = "私聊回复" if target else "自动浏览"
        if stop_status == "starting_retry_stop":
            failed = True
            print(name + "仍在初始化，停止请求尚未提交；请稍后再次双击停止入口。")
        else:
            print(name + "停止请求已提交，正在等待当前请求收尾。")
    print("停止操作不会关闭专用 Edge 或 QQ。")
    return int(failed)


def show_workers(*, inbox=False, require_running=False) -> int:
    failed = False
    for target in ((True,) if inbox else (False, True)):
        try:
            state = control("status", inbox=target)
            show_status(state, inbox=target)
            if require_running and not state.get("running"):
                failed = True
                print(("私聊回复" if target else "自动浏览") + "后台未启动，请检查后重试。", file=sys.stderr)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            failed = True
            print(("私聊回复" if target else "自动浏览") + "状态读取失败，请查看对应日志。", file=sys.stderr)
    return int(failed)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "status", "stop"))
    parser.add_argument("--inbox", action="store_true", help="control private replies instead of browsing")
    args = parser.parse_args(argv)
    try:
        if args.command == "stop":
            return stop(inbox=args.inbox)
        if args.command == "start":
            print("正在启动爱可" + ("私聊回复" if args.inbox else "自动浏览和私聊回复") + "，请稍候……", flush=True)
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(ROOT / "scripts" / ("start-bilibili-inbox.ps1" if args.inbox else "start-bilibili.ps1")), "-Background"], cwd=ROOT,
            )
            if result.returncode:
                print("启动未完成。若提示未登录，请在爱可专用 Edge 中登录后再次双击启动入口。")
                show_workers(inbox=args.inbox)
                return result.returncode
            # A launcher returning is insufficient: both requested workers must be alive.
            return show_workers(inbox=args.inbox, require_running=True)
        return show_workers(inbox=args.inbox)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        print("操作未能完成，请查看对应的浏览/私聊日志，或使用说明中的原始控制命令。", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已关闭控制操作；已提交的后台任务和停止请求不受影响。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
