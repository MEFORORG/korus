"""`install-git-hooks.ps1 -Status` names the interpreter the shims will run, by its exit code.

THE FAILURE THIS EXISTS FOR. `Resolve-Python` asked each candidate for `--version` and piped the
answer into `Select-Object -First 1`, then tested `$LASTEXITCODE -eq 0`. Stopping a pipeline early
stops the native command before pwsh records its exit code, so `$LASTEXITCODE` kept whatever the
previous native command left.

Measured 2026-10-09 on pwsh 7.6.6, Windows: the piped form gave `rc=[]`, the unpiped form `rc=[0]`,
for a real interpreter and for the WindowsApps alias alike. With nothing run before it, the value is
null, so every candidate was rejected. `-Status` printed "NONE FOUND -- BOTH GATES ARE OFF" and
exited 1 on a box whose gates were on, including with CCX_PYTHON naming a real interpreter.

The same hole has a second face. A stale 0 left by an earlier `git` call would pass a candidate that
printed something and then failed, which is what an execution-alias stub does. That is the case the
probe exists to reject.

HOW. Each case parses the installer, dot-sources ONLY the `Resolve-Python` function, and calls it.
The installer itself never runs, which `_ccxtest.find_pwsh` asks of every test here. Each case
pre-sets `$LASTEXITCODE` to the value that would hide the bug, so a probe that never reads a fresh
exit code fails rather than passing by luck. PATH points at an empty directory, so CCX_PYTHON is
the only candidate and the answer cannot come from somewhere else on the box.

Run: cd tests && python -m unittest test_the_status_report_finds_a_python_that_runs -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120

# Dot-source the one function, preset the exit code, call it, print what it returned. The function
# runs under the installer's own preference, so a behaviour that depends on it is the one under test.
HARNESS = r"""
param([string]$Installer, [int]$Preset)
$ErrorActionPreference = 'Stop'
$errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Installer, [ref]$null, [ref]$errs)
if ($errs) { Write-Output "PARSE-ERRORS: $($errs.Count)"; exit 3 }
$fn = $ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Resolve-Python'
}, $true) | Select-Object -First 1
if (-not $fn) { Write-Output 'NO-FUNCTION'; exit 4 }
. ([scriptblock]::Create($fn.Extent.Text))
$global:LASTEXITCODE = $Preset
$r = Resolve-Python
if ($r) { Write-Output "FOUND|$($r.How)|$($r.Path)|$($r.Version)" } else { Write-Output 'NONE' }
"""


@unittest.skipUnless(t.find_pwsh(), "pwsh is not on PATH")
class ResolvePythonReadsAFreshExitCode(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.empty_path = self.tmp / "empty-path"
        self.empty_path.mkdir()
        self.harness = self.tmp / "harness.ps1"
        self.harness.write_text(HARNESS, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def resolve(self, ccx_python: str, preset: int) -> str:
        env = dict(os.environ)
        env["CCX_PYTHON"] = ccx_python
        # An empty directory rather than an empty string: pwsh treats an empty PATH as unset on some
        # hosts, and then a python on the real PATH would answer for CCX_PYTHON.
        env["PATH"] = str(self.empty_path)
        r = subprocess.run(
            [t.find_pwsh(), "-NoProfile", "-NonInteractive", "-File", str(self.harness),
             "-Installer", str(t.GIT_HOOK_INSTALLER), "-Preset", str(preset)],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS, env=env,
        )
        out = r.stdout.strip()
        self.assertEqual(r.returncode, 0, f"harness failed\nstdout: {out}\nstderr: {r.stderr}")
        return out.splitlines()[-1] if out else ""

    def fake_interpreter(self, exit_code: int) -> Path:
        """A program that prints a version line and exits with `exit_code`."""
        if os.name == "nt":
            p = self.tmp / f"fake-python-{exit_code}.cmd"
            p.write_text(f"@echo Python 9.9.9\r\n@exit /b {exit_code}\r\n", encoding="ascii")
        else:
            p = self.tmp / f"fake-python-{exit_code}"
            p.write_text(f"#!/bin/sh\necho 'Python 9.9.9'\nexit {exit_code}\n", encoding="ascii")
            p.chmod(0o755)
        return p

    def test_a_real_interpreter_is_found_after_a_failed_command(self) -> None:
        """The reported bug: a working CCX_PYTHON was rejected, so -Status said both gates were off."""
        line = self.resolve(sys.executable, preset=1)
        self.assertTrue(line.startswith("FOUND|CCX_PYTHON|"), line)
        self.assertIn(Path(sys.executable).name, line)
        self.assertIn("Python 3", line)

    def test_a_candidate_that_exits_non_zero_is_rejected_after_a_success(self) -> None:
        """The probe's purpose: output alone is not evidence the interpreter runs."""
        line = self.resolve(str(self.fake_interpreter(9009)), preset=0)
        self.assertEqual(line, "NONE")

    def test_the_fake_is_accepted_when_it_exits_zero(self) -> None:
        """Control for the case above: the rejection is about the exit code, not about the fake."""
        line = self.resolve(str(self.fake_interpreter(0)), preset=1)
        self.assertTrue(line.startswith("FOUND|CCX_PYTHON|"), line)
        self.assertTrue(line.endswith("|Python 9.9.9"), line)


if __name__ == "__main__":
    unittest.main()
