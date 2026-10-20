"""Exercise Windows installers using local Git and a fake Ollama, never live models."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt" and shutil.which("git"), "Windows + Git required")
class DeploymentInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aichatbot-install-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.marker = self.work / "installed"
        self.cli_log = self.work / "cli.json"
        self.dimension = 1024
        self.requests = []
        self.invalid_api = False
        test = self

        class Handler(BaseHTTPRequestHandler):
            def respond(self, payload, status=200):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if test.invalid_api:
                    self.respond({"error": "not Ollama"}, 503)
                    return
                self.respond({"models": [{"name": "bge-m3:latest"}] if test.marker.exists() else []})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.requests.append((self.path, body))
                self.respond({"embeddings": [[0.25] * test.dimension]})

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        fake_bin = self.work / "bin"
        fake_bin.mkdir()
        helper = fake_bin / "fake_ollama.py"
        helper.write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "Path(os.environ['INSTALL_TEST_LOG']).write_text(json.dumps({'args':sys.argv[1:], 'host':os.environ.get('OLLAMA_HOST')}))\n"
            "if os.environ.get('INSTALL_TEST_FAIL') == '1': sys.exit(7)\n"
            "assert sys.argv[1:] == ['pull', 'bge-m3'], sys.argv\n"
            "Path(os.environ['INSTALL_TEST_MARKER']).touch()\n",
            encoding="utf-8",
        )
        (fake_bin / "ollama.cmd").write_text(
            f'@echo off\n"{sys.executable}" "{helper}" %*\nexit /b %errorlevel%\n',
            encoding="utf-8",
        )
        self.environment = os.environ.copy()
        self.environment.update({
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "INSTALL_TEST_LOG": str(self.cli_log),
            "INSTALL_TEST_MARKER": str(self.marker),
            "OLLAMA_HOST": "http://127.0.0.1:9",
        })

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def run_script(self, name, *arguments):
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "scripts" / name), *map(str, arguments)],
            cwd=self.work, env=self.environment, capture_output=True,
            encoding="utf-8", errors="replace", timeout=30,
        )

    def make_repository(self):
        repo = self.work / "source"
        repo.mkdir()
        for folder in ("config", "docs", "prompts", "scripts", "src", "tests", "web/owner-console"):
            target = repo / folder
            target.mkdir(parents=True, exist_ok=True)
            (target / "fixture.txt").write_text("fixture", encoding="utf-8")
        (repo / "web/owner-console/package.json").write_text("{}", encoding="utf-8")
        shutil.copyfile(ROOT / ".env.example", repo / ".env.example")
        source = (ROOT / "scripts/install-vector-model.ps1").read_text(encoding="utf-8-sig")
        # Redirect only the fixture's default endpoint to the isolated fake service.
        (repo / "scripts/install-vector-model.ps1").write_text(
            source.replace("http://127.0.0.1:11434", self.url), encoding="utf-8"
        )
        for args in (("init", "-b", "main"), ("add", "."),
                     ("-c", "user.name=Installer Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")):
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
        return repo

    def test_pull_uses_requested_endpoint_and_checks_cpu_embedding(self):
        result = self.run_script("install-vector-model.ps1", "-BaseUrl", self.url)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.cli_log.read_text()), {"args": ["pull", "bge-m3"], "host": self.url})
        self.assertEqual(self.requests, [("/api/embed", {
            "model": "bge-m3", "input": "MemoryRAG installation check", "options": {"num_gpu": 0}
        })])

    def test_existing_model_is_verified_without_pulling(self):
        self.marker.touch()
        result = self.run_script("install-vector-model.ps1", "-BaseUrl", self.url)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.cli_log.exists())
        self.assertEqual(len(self.requests), 1)

    def test_wrong_embedding_dimension_fails(self):
        self.marker.touch()
        self.dimension = 8
        result = self.run_script("install-vector-model.ps1", "-BaseUrl", self.url)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1024-dimensional", result.stderr)

    def test_pull_failure_fails_core_install_without_reporting_success(self):
        repo = self.make_repository()
        self.environment["INSTALL_TEST_FAIL"] = "1"
        result = self.run_script("install-core.ps1", "-RepositoryUrl", repo, "-Destination", "core")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to download", result.stderr)
        self.assertNotIn("Core source and bge-m3 are ready", result.stdout)

    def test_core_excludes_frontend_creates_env_and_requires_vector(self):
        repo = self.make_repository()
        result = self.run_script("install-core.ps1", "-RepositoryUrl", repo, "-Destination", "core")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        core = self.work / "core"
        self.assertFalse((core / "web").exists())
        self.assertTrue((core / "src/fixture.txt").exists())
        self.assertEqual((core / ".env").read_bytes(), (ROOT / ".env.example").read_bytes())
        self.assertTrue(self.marker.exists())
        self.assertIn("Core source and bge-m3 are ready", result.stdout)

    def test_frontend_download_excludes_backend_and_models(self):
        repo = self.make_repository()
        result = self.run_script("install-owner-console.ps1", "-RepositoryUrl", repo, "-Destination", "frontend")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        frontend = self.work / "frontend"
        self.assertTrue((frontend / "web/owner-console/package.json").exists())
        self.assertFalse((frontend / "src").exists())
        self.assertFalse(self.cli_log.exists())

    def test_existing_destination_is_not_modified(self):
        target = self.work / "existing"
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_text("keep me")
        for installer in ("install-core.ps1", "install-owner-console.ps1"):
            result = self.run_script(installer, "-Destination", target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite", result.stderr)
        self.assertEqual(sentinel.read_text(), "keep me")

    def test_invalid_service_is_not_restarted(self):
        self.invalid_api = True
        result = self.run_script("install-vector-model.ps1", "-BaseUrl", self.url)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace or restart", result.stderr)
        self.assertFalse(self.cli_log.exists())

    def test_host_override_is_restored_after_vector_check(self):
        self.marker.touch()
        script = str(ROOT / "scripts/install-vector-model.ps1").replace("'", "''")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             f"& '{script}' -BaseUrl '{self.url}'; if ($env:OLLAMA_HOST -ne 'http://127.0.0.1:9') {{ throw 'Host was not restored' }}"],
            cwd=self.work, env=self.environment, capture_output=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_setup_does_not_report_success_after_dependency_failure(self):
        project = self.work / "setup-project"
        scripts = project / "scripts"
        scripts.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/setup.ps1", scripts / "setup.ps1")
        # Fake Python only in this subprocess. No real environment is created.
        (self.work / "bin/python.cmd").write_text(
            '@echo off\nif "%1"=="--version" exit /b 0\n'
            'if "%1"=="-c" exit /b 0\n'
            'if "%2"=="venv" exit /b 3\nexit /b 9\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(scripts / "setup.ps1")],
            cwd=self.work, env=self.environment, capture_output=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Virtual environment creation failed", result.stderr)
        self.assertNotIn("Setup complete", result.stdout)


if __name__ == "__main__":
    unittest.main()
