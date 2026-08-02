from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = PROJECT_ROOT / "scripts" / "start.ps1"


class StartScriptContractTests(unittest.TestCase):
    def test_port_ownership_preflight_precedes_ollama_and_bot_start(self):
        source = START_SCRIPT.read_text(encoding="utf-8")

        listener_check = source.index("Get-PortListener -LocalPort $botPort")
        ollama_ensure = source.index("& .\\scripts\\ensure-ollama.ps1")
        bot_start = source.index("& $python $botEntry")

        self.assertIn("function Get-BotPort", source)
        self.assertIn("function Test-ChatbotProcess", source)
        self.assertIn("QQ Chatbot is already running", source)
        self.assertIn("Port $botPort is already in use by another process", source)
        self.assertLess(listener_check, ollama_ensure)
        self.assertLess(ollama_ensure, bot_start)

    def test_existing_project_bot_listener_exits_without_starting_again(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])

        listener_code = (
            "import socket,sys,time; "
            "s=socket.socket(); "
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
            "s.bind(('127.0.0.1',int(sys.argv[1]))); "
            "s.listen(); print('ready',flush=True); time.sleep(20)"
        )
        listener = subprocess.Popen(
            [sys.executable, "-c", listener_code, str(port), str(PROJECT_ROOT / "bot.py")],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(listener.stdout.readline().strip(), "ready")
            listener_observed = False
            listener_probe = (
                f"netstat.exe -ano -p tcp | Select-String -Pattern ':({port})\\s+.*LISTENING'"
            )
            for _ in range(20):
                observed = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", listener_probe],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if observed.returncode == 0 and observed.stdout.strip():
                    listener_observed = True
                    break
                time.sleep(0.05)
            self.assertTrue(
                listener_observed,
                (
                    "temporary listener was not visible to netstat; "
                    f"stdout={observed.stdout!r} stderr={observed.stderr!r}"
                ),
            )
            environment = os.environ.copy()
            environment["PORT"] = str(port)
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(START_SCRIPT),
                    "-SkipOllamaEnsure",
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
        finally:
            listener.terminate()
            listener.wait(timeout=5)
            if listener.stdout is not None:
                listener.stdout.close()
            if listener.stderr is not None:
                listener.stderr.close()

        self.assertIn(
            completed.returncode,
            {0, 1},
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}",
        )
        self.assertTrue(
            "QQ Chatbot is already running" in completed.stdout
            or "is already in use by another process" in completed.stdout,
            completed.stdout,
        )
        self.assertNotIn("NoneBot is initializing", completed.stdout)


if __name__ == "__main__":
    unittest.main()
