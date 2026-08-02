from __future__ import annotations

import os
import json
import socket
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENSURE_OLLAMA_SCRIPT = PROJECT_ROOT / "scripts" / "ensure-ollama.ps1"


class EnsureOllamaStartupContractTests(unittest.TestCase):
    def test_cloud_vision_does_not_create_a_local_ollama_requirement(self):
        source = ENSURE_OLLAMA_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn('Get-BoolConfig "ENABLE_VISION"', source)
        self.assertNotIn('Get-ConfigValue "VISION_OLLAMA_BASE_URL"', source)
        self.assertNotIn('Get-ConfigValue "VISION_MODEL"', source)
        self.assertNotIn("qwen2.5vl:3b", source)
        self.assertIn('Get-BoolConfig "ENABLE_MEMORY_RAG"', source)
        self.assertIn('Get-BoolConfig "ENABLE_PROJECT_DOC_RAG"', source)
        self.assertIn('Get-ConfigValue "MEMORY_RAG_EMBEDDING_MODEL" "bge-m3"', source)
        self.assertIn("Required RAG model(s)", source)
        self.assertNotIn('"Ollama is ready. Models:', source)
        self.assertIn("Test-ConnectionRefusedException", source)
        self.assertIn("A healthy Ollama service will not be restarted", source)
        self.assertIn("-ModelDir $ModelDir -KeepExisting", source)
        self.assertNotIn("$needsRestart", source)

    def test_reachable_service_with_missing_model_fails_without_starting(self):
        class TagsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = json.dumps({"models": []}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), TagsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = os.environ.copy()
        environment.update(
            {
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "false",
                "MEMORY_RAG_EMBEDDING_PROVIDER": "ollama",
                "MEMORY_RAG_EMBEDDING_MODEL": "definitely-missing-model",
            }
        )
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ENSURE_OLLAMA_SCRIPT),
                    "-BaseUrl",
                    f"http://127.0.0.1:{server.server_port}",
                    "-NoStart",
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
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("required model(s) are missing", completed.stdout)
        self.assertIn("will not be restarted", completed.stdout)
        self.assertNotIn("Starting Ollama", completed.stdout)

    def test_connection_refused_is_the_only_offline_no_start_path(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])

        environment = os.environ.copy()
        environment.update(
            {
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "false",
                "MEMORY_RAG_EMBEDDING_PROVIDER": "ollama",
                "MEMORY_RAG_EMBEDDING_MODEL": "bge-m3",
            }
        )
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ENSURE_OLLAMA_SCRIPT),
                "-BaseUrl",
                f"http://127.0.0.1:{port}",
                "-NoStart",
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

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("explicitly offline (connection refused)", completed.stdout)
        self.assertIn("-NoStart was specified", completed.stdout)
        self.assertNotIn("readiness is ambiguous", completed.stdout)
        self.assertNotIn("Starting Ollama", completed.stdout)

    def test_vision_only_configuration_skips_ollama_without_network_or_start(self):
        environment = os.environ.copy()
        environment.update(
            {
                "ENABLE_VISION": "true",
                "ENABLE_MEMORY_RAG": "false",
                "ENABLE_PROJECT_DOC_RAG": "false",
                "MEMORY_RAG_EMBEDDING_PROVIDER": "ollama",
            }
        )

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ENSURE_OLLAMA_SCRIPT),
                "-NoStart",
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

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "Ollama ensure skipped: Ollama-backed RAG is disabled.",
            completed.stdout,
        )
        self.assertNotIn("Checking Ollama", completed.stdout)
        self.assertNotIn("Starting Ollama", completed.stdout)

    def test_non_ollama_rag_provider_also_skips_local_ollama(self):
        environment = os.environ.copy()
        environment.update(
            {
                "ENABLE_VISION": "true",
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "true",
                "MEMORY_RAG_EMBEDDING_PROVIDER": "openai_compatible",
            }
        )

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ENSURE_OLLAMA_SCRIPT),
                "-NoStart",
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

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "Ollama ensure skipped: Ollama-backed RAG is disabled.",
            completed.stdout,
        )
        self.assertNotIn("Checking Ollama", completed.stdout)


if __name__ == "__main__":
    unittest.main()
