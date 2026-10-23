from __future__ import annotations

import argparse
import os
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AI_CHAT_ROOT = PROJECT_ROOT / "src" / "plugins" / "ai_chat"
if str(AI_CHAT_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_CHAT_ROOT))

from failure_diagnostics import format_failure_inspection, inspect_failure_lines  # noqa: E402
from check_configuration import load_configuration_modules  # noqa: E402


DEFAULT_LOGS = (
    PROJECT_ROOT / "logs" / "ai_chat_error.log",
    PROJECT_ROOT / "logs" / "nonebot.err.log",
    PROJECT_ROOT / "logs" / "owner-console.err.log",
    PROJECT_ROOT / "logs" / "tts-service.err.log",
)
MAX_LINES_PER_LOG = 2000


def read_log_tail(path: Path, *, limit: int = MAX_LINES_PER_LOG) -> list[str]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fallback_timestamp = datetime.fromtimestamp(path.stat().st_mtime).isoformat(
        timespec="seconds"
    )
    output: list[str] = []
    for line in lines[-limit:]:
        if line[:4].isdigit() and len(line) >= 19 and "T" in line[:19]:
            output.append(line)
        else:
            output.append(f"{fallback_timestamp} source={path.name} {line}")
    return output


def tcp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def database_readable(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        connection = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
            timeout=1,
        )
        try:
            connection.execute("PRAGMA schema_version").fetchone()
        finally:
            connection.close()
        return True
    except sqlite3.Error:
        return False


def build_local_state_report() -> str:
    env_path = PROJECT_ROOT / ".env"
    issues: list[str] = []
    config_lines = [f".env：{'存在' if env_path.is_file() else '缺失'}。"]
    if not env_path.is_file():
        issues.append("配置文件缺失")

    config_module, reports = load_configuration_modules()
    try:
        config = config_module.load_config()
        evidence = reports.build_configuration_report(config)
    except config_module.ConfigValidationError as exc:
        return "\n".join([
            "本地状态巡检：需要关注", "配置校验失败：",
            *(f"- {item.key}: {item.message}" for item in exc.issues),
            "配置无效，未执行端口或数据库检查。",
        ])
    for item in evidence["issues"]:
        config_lines.append(f"配置提示：{item['key']}：{item['message']}。")
    chat_ready = evidence["default_chat"]["configured"]
    config_lines.append(f"聊天模型必填项：{'已配置' if chat_ready else '不完整'}。")
    if not chat_ready:
        issues.append("聊天模型配置不完整")

    if evidence["main_agent"]["llm_enabled"]:
        main_ready = evidence["main_agent"]["configured"]
        config_lines.append(f"MainAgent 模型必填项：{'已配置' if main_ready else '不完整'}。")
        if not main_ready:
            issues.append("MainAgent 模型配置不完整")
    else:
        config_lines.append("MainAgent：按配置关闭或未显式开启。")

    bot_port = evidence["nonebot_port"]
    bot_port_ok = tcp_reachable("127.0.0.1", bot_port)
    database_ok = database_readable(PROJECT_ROOT / "data" / "chatbot.db")
    runtime_lines = [
        f"NoneBot 配置端口 {bot_port}：{'可达' if bot_port_ok else '不可达'}。",
        f"SQLite 只读检查：{'通过' if database_ok else '失败'}。",
        f"虚拟环境：{'存在' if (PROJECT_ROOT / '.venv' / 'Scripts' / 'python.exe').is_file() else '缺失'}。",
    ]
    if not bot_port_ok:
        issues.append("NoneBot 本地端口不可达")
    if not database_ok:
        issues.append("SQLite 只读检查失败")

    for purpose, url in reports.local_ollama_dependencies(config):
        endpoint = reports.loopback_endpoint(url)
        if endpoint is None:
            runtime_lines.append(f"Ollama 依赖 {purpose}：非本机或地址无效，未连接。")
            continue
        dependency_ok = tcp_reachable(*endpoint)
        runtime_lines.append(f"Ollama 依赖 {purpose}：{'可达' if dependency_ok else '不可达'}。")
        if not dependency_ok:
            issues.append(f"Ollama 依赖 {purpose} 不可达")
    if evidence["vision"]["enabled"]:
        runtime_lines.append(f"视觉提供方：{evidence['vision']['provider']}；未执行远程探针。")
        if not evidence["vision"]["configured"]:
            issues.append("视觉配置不完整")
    if not evidence["ollama_required"]:
        runtime_lines.append("没有启用依赖 Ollama 的能力，不检查 Ollama。")

    status = "需要关注" if issues else "正常"
    lines = [f"本地状态巡检：{status}", "配置状态：", *config_lines, "", "核心服务：", *runtime_lines]
    if issues:
        lines.extend(["", "需关注：", *(f"- {issue}。" for issue in issues)])
    lines.append("边界：只读取配置是否存在，不输出配置值；只连接本机端口，不启动服务。")
    return "\n".join(lines)


def build_report(*, hours: int) -> str:
    lines: list[str] = []
    present_logs = 0
    for path in DEFAULT_LOGS:
        if path.is_file():
            present_logs += 1
        lines.extend(read_log_tail(path))
    inspection = inspect_failure_lines(lines, now=datetime.now(), window_hours=hours)
    return "\n".join(
        [
            build_local_state_report(),
            "",
            format_failure_inspection(inspection),
            "",
            f"日志源：已找到 {present_logs}/{len(DEFAULT_LOGS)} 个固定日志文件。",
            "建议频率：每 30 分钟执行一次；出现失败时保留报告并再运行 scripts/diagnose.ps1。",
        ]
    )


def write_latest_report(report: str) -> Path:
    report_directory = PROJECT_ROOT / "output" / "reliability-inspections"
    report_directory.mkdir(parents=True, exist_ok=True)
    report_path = report_directory / "latest.txt"
    temporary_path = report_directory / "latest.tmp"
    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write(report.rstrip() + "\n")
        file.flush()
        os.fsync(file.fileno())
    temporary_path.replace(report_path)
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only AIchatbot reliability inspection."
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.hours <= 24 * 30:
        parser.error("--hours must be between 1 and 720")
    report = build_report(hours=args.hours)
    print(report)
    if args.write_report:
        write_latest_report(report)
        print("Report written: output/reliability-inspections/latest.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
