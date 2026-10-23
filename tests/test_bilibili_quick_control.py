from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from scripts import bilibili_quick_control as controls


class CombinedControlsTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.stdout = redirect_stdout(self.output)
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        self.stderr = redirect_stderr(self.output)
        self.stderr.__enter__()
        self.addCleanup(self.stderr.__exit__, None, None, None)

    def test_default_status_reads_both_workers(self):
        with patch.object(controls, 'control', return_value={'running': False}) as control:
            self.assertEqual(controls.main(['status']), 0)
        self.assertEqual([c.kwargs['inbox'] for c in control.call_args_list], [False, True])

    def test_inbox_only_entry_still_controls_only_inbox(self):
        with patch.object(controls, 'control', return_value={'status': 'not_running'}) as control:
            self.assertEqual(controls.main(['stop', '--inbox']), 0)
        control.assert_called_once_with('stop', inbox=True)

    def test_stops_both_before_waiting_for_either(self):
        calls = []
        def control(command, *, inbox=False):
            calls.append((command, inbox))
            return {'status': 'stop_requested'} if command == 'stop' else {'running': False}
        with patch.object(controls, 'control', side_effect=control), patch.object(controls.time, 'sleep'):
            self.assertEqual(controls.main(['stop']), 0)
        self.assertEqual(calls, [('stop', False), ('stop', True), ('status', False), ('status', True)])

    def test_one_stop_failure_does_not_prevent_stopping_other_worker(self):
        def control(command, *, inbox=False):
            if not inbox:
                raise RuntimeError('synthetic failure')
            return {'status': 'not_running'}
        with patch.object(controls, 'control', side_effect=control) as call:
            self.assertEqual(controls.main(['stop']), 1)
        self.assertEqual([c.kwargs['inbox'] for c in call.call_args_list], [False, True])

    def test_start_does_not_report_success_if_inbox_is_missing(self):
        with patch.object(controls.subprocess, 'run', return_value=NS(returncode=0)), \
             patch.object(controls, 'control', side_effect=lambda command, inbox=False: {'running': not inbox}):
            self.assertEqual(controls.main(['start']), 1)

    def test_status_failure_does_not_hide_other_worker(self):
        with patch.object(controls, 'control', side_effect=[RuntimeError(), {'running': True}]) as call:
            self.assertEqual(controls.main(['status']), 1)
        self.assertEqual(call.call_count, 2)
        self.assertIn('私聊回复：运行中', self.output.getvalue())

    def test_combined_stop_reaches_two_real_isolated_workers(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, AIKE_BILIBILI_HOME=directory)
            common = (
                "import os,time;from pathlib import Path;from types import SimpleNamespace as NS;"
                "from src.bilibili_connector import BilibiliBinding;"
                "home=Path(os.environ['AIKE_BILIBILI_HOME']);"
            )
            browse = common + (
                "from src.bilibili_autobrowse import AutoBrowseStore,BrowsePolicy,run_loop;"
                "store=AutoBrowseStore(home,'a'*64);store.update_state(next_due=time.time()+3600);"
                "run_loop(store,BrowsePolicy(),lambda *args:dict(status='ok'),send=False)"
            )
            inbox = common + (
                "from unittest.mock import patch;from src.bilibili_inbox import InboxStore,InboxPolicy,run_inbox;"
                "p=patch('src.bilibili_inbox.poll_inbox',return_value=dict(status='ok',received=0));p.start();"
                "run_inbox(InboxStore(home,'a'*64),BilibiliBinding('aike','aike','101','202'),NS(),InboxPolicy())"
            )
            processes = []
            try:
                for code in (browse, inbox):
                    processes.append(subprocess.Popen([controls.sys.executable, '-u', '-c', code],
                        cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
                with patch.dict(os.environ, env):
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        if all(controls.control('status', inbox=target).get('running') for target in (False, True)):
                            break
                        time.sleep(0.05)
                    else:
                        self.fail('Synthetic workers did not become ready')
                    self.assertEqual(controls.main(['stop']), 0)
                    for process in processes:
                        _, errors = process.communicate(timeout=10)
                        self.assertEqual(process.returncode, 0, errors)
                    for target in (False, True):
                        self.assertFalse(controls.control('status', inbox=target)['running'])
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                        process.communicate(timeout=5)


@unittest.skipUnless(os.name == 'nt', 'Windows launcher behavior')
class CombinedPowerShellLauncherTests(unittest.TestCase):
    def launch(self, *, existing=False, inbox_fails=False, flags=()):
        source = (Path(__file__).resolve().parents[1] / 'scripts/start-bilibili.ps1').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            # Replace only the executable boundary; run the actual launcher logic.
            source = source.replace('$python = Join-Path $RepoRoot ".venv\\Scripts\\python.exe"', '$python = "Fake-Python"')
            (scripts / 'start-bilibili.ps1').write_text(source, encoding='utf-8-sig')
            (scripts / 'start-bilibili-inbox.ps1').write_text(
                "param([switch]$Background)\nAdd-Content -LiteralPath $env:TEST_EVENTS -Value 'inbox_start'\n"
                + ('exit 1\n' if inbox_fails else '$global:LASTEXITCODE = 0\n'), encoding='utf-8-sig')
            harness = r'''
param([switch]$Existing, [switch]$PreviewOnly, [switch]$Once)
$global:FakeWorkerRunning = [bool]$Existing
function Test-Path { param($LiteralPath) return $true }
function Fake-Python {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Items)
    $global:LASTEXITCODE = 0
    $name = [System.IO.Path]::GetFileName($Items[0])
    $command = $Items[1]
    Add-Content -LiteralPath $env:TEST_EVENTS -Value ($name + ':' + $command)
    if ($command -eq 'status') { @{running=$global:FakeWorkerRunning} | ConvertTo-Json -Compress }
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    Add-Content -LiteralPath $env:TEST_EVENTS -Value 'browse_start'
    $global:FakeWorkerRunning = $true
    $process = [PSCustomObject]@{}
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { param($Timeout) return $false }
    return $process
}
& (Join-Path $PSScriptRoot 'scripts/start-bilibili.ps1') -Background -PreviewOnly:$PreviewOnly -Once:$Once
exit $LASTEXITCODE
'''
            path = root / 'harness.ps1'
            path.write_text(harness, encoding='utf-8-sig')
            env = dict(os.environ, TEST_EVENTS=str(root / 'events.log'), AIKE_BILIBILI_HOME=str(root / 'private'))
            args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(path)]
            if existing:
                args.append('-Existing')
            result = subprocess.run([*args, *flags], env=env, capture_output=True, timeout=15)
            events = (root / 'events.log').read_text(encoding='utf-8-sig').splitlines()
            return result.returncode, events

    def test_default_start_enables_inbox_before_browsing(self):
        code, events = self.launch()
        self.assertEqual(code, 0)
        self.assertLess(events.index('inbox_start'), events.index('browse_start'))

    def test_existing_browser_worker_still_starts_missing_inbox(self):
        code, events = self.launch(existing=True)
        self.assertEqual(code, 0)
        self.assertIn('inbox_start', events)
        self.assertNotIn('browse_start', events)
        self.assertNotIn('bilibili_browser.py:open', events)

    def test_failed_inbox_prevents_new_browsing_worker(self):
        code, events = self.launch(inbox_fails=True)
        self.assertNotEqual(code, 0)
        self.assertNotIn('browse_start', events)

    def test_preview_does_not_enable_real_private_replies(self):
        code, events = self.launch(flags=('-PreviewOnly',))
        self.assertEqual(code, 0)
        self.assertNotIn('inbox_start', events)

    def test_single_round_does_not_leave_inbox_running(self):
        code, events = self.launch(flags=('-Once',))
        self.assertEqual(code, 0)
        self.assertNotIn('inbox_start', events)


if __name__ == '__main__':
    unittest.main()
