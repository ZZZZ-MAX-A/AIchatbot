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


def read_env_flags(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def configured(values: dict[str, str], key: str) -> bool:
    return bool(values.get(key, "").strip())


def enabled(values: dict[str, str], key: str, *, default: bool = False) -> bool:
    value = values.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    values = read_env_flags(env_path)
    issues: list[str] = []
    config_lines = [f".env：{'存在' if env_path.is_file() else '缺失'}。"]
    if not env_path.is_file():
        issues.append("配置文件缺失")

    chat_ready = configured(values, "OPENAI_API_KEY") and configured(values, "OPENAI_MODEL")
    config_lines.append(f"聊天模型必填项：{'已配置' if chat_ready else '不完整'}。")
    if not chat_ready:
        issues.append("聊天模型配置不完整")

    if enabled(values, "ENABLE_MAIN_AGENT"):
        main_ready = configured(values, "MAIN_LLM_API_KEY") and configured(values, "MAIN_LLM_MODEL")
        config_lines.append(f"MainAgent 模型必填项：{'已配置' if main_ready else '不完整'}。")
        if not main_ready:
            issues.append("MainAgent 模型配置不完整")
    else:
        config_lines.append("MainAgent：按配置关闭或未显式开启。")

    bot_port_ok = tcp_reachable("127.0.0.1", 8080)
    database_ok = database_readable(PROJECT_ROOT / "data" / "chatbot.db")
    runtime_lines = [
        f"NoneBot 端口 8080：{'可达' if bot_port_ok else '不可达'}。",
        f"SQLite 只读检查：{'通过' if database_ok else '失败'}。",
        f"虚拟环境：{'存在' if (PROJECT_ROOT / '.venv' / 'Scripts' / 'python.exe').is_file() else '缺失'}。",
    ]
    if not bot_port_ok:
        issues.append("NoneBot 本地端口不可达")
    if not database_ok:
        issues.append("SQLite 只读检查失败")

    if enabled(values, "ENABLE_VISION"):
        ollama_ok = tcp_reachable("127.0.0.1", 11434)
        runtime_lines.append(f"Ollama 端口 11434：{'可达' if ollama_ok else '不可达'}。")
        if not ollama_ok:
            issues.append("视觉已开启但 Ollama 不可达")
    else:
        runtime_lines.append("视觉：按配置关闭，不检查 Ollama。")

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
