"""`scripts/wiki/cycle.ps1` and `scripts/wiki/register-cycle-task.ps1`: the wiki's scheduled run.

EVERY CASE RUNS THE REAL SCRIPTS against throwaway git repositories: a bare korus remote and a
detached clone of it, and a bare record remote and a detached reader clone. Nothing reaches a real
clone, a real remote or a network.

THE WIKI SCRIPTS THE CYCLE CALLS ARE STUBS, committed to the throwaway korus remote at the paths
the real ones hold. Running the real compile would need `gh` and a record repository with a leak
scanner, and `test_wiki_compile.py` already pins compile itself. Each stub appends one JSON line
naming itself, its version and its arguments, then prints what its real twin prints with `-Json`.
An environment variable makes any stub fail with a chosen exit code.

THE STUBS ON THE REMOTE ARE A NEWER VERSION THAN THE CHECKOUT HOLDS. So a stub call that reports
the newer version shows the cycle ran the scripts at `origin/main`, not the checkout's stale copy.
The older version is the control: the checkout is asserted to hold it before the run.

THE REGISTRAR IS RUN ONLY WITH -WhatIf, under a decoy task name. On Windows the last case reads the
task store and finds no task of that name.

Run: python -m pytest tests/test_wiki_cycle.py
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _wikitest as w

CYCLE = w.WIKI / "cycle.ps1"
REGISTER = w.WIKI / "register-cycle-task.ps1"

# One stub per wiki script. `__NAME__` and `__VERSION__` are filled in per file. The lint stub writes
# the Totals table in the shape lint.ps1 writes it, so the cycle's parser is tested against that shape.
_STUB = r"""
$name = '__NAME__'
$version = '__VERSION__'
$calls = $env:WIKI_CYCLE_TEST_CALLS
if ($calls) {
    $rec = [ordered]@{ name = $name; version = $version; root = $PSScriptRoot; args = @($args) }
    [System.IO.File]::AppendAllText($calls, (ConvertTo-Json -InputObject $rec -Compress -Depth 4) + "`n")
}
$want = [Environment]::GetEnvironmentVariable('WIKI_CYCLE_TEST_' + $name.ToUpper() + '_EXIT')
$code = if ($want) { [int]$want } else { 0 }
if ($code -ne 0) { [Console]::Error.WriteLine("$name stub: failing on purpose with $code"); exit $code }
switch ($name) {
    'compile' { Write-Output '{"result":"compiled","deleted":0,"pending":2,"held":0,"added":2,"conflicts":0,"pr":"https://example.invalid/pull/7"}' }
    'import'  { Write-Output '{"what_if":false,"counts":{"imported":3,"merged":1,"refused":0}}' }
    'lint' {
        $i = [array]::IndexOf($args, '-Out')
        $out = $args[$i + 1]
        $text = "# Wiki lint report`n`n## conflict (1)`n`n- x`n`n## Totals`n`n| Class | Count |`n|---|---|`n" +
            "| conflict | 1 |`n| dead-evidence | 0 |`n| stale | 2 |`n| orphan-page | 0 |`n| promotion-candidate | 0 |`n| unchecked | 4 |`n`n## Inputs`n`n| not | 9 |`n"
        [System.IO.File]::WriteAllText($out, $text)
    }
}
exit 0
"""

STUB_NAMES = ("import", "compile", "lint")


def stub(name: str, version: str) -> str:
    return _STUB.replace("__NAME__", name).replace("__VERSION__", version)


def day_name(when: datetime) -> str:
    return when.strftime("%A")


class _CycleCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-cycle-")
        self.addCleanup(tmp.cleanup)
        # Resolved, so a short 8.3 temp path reads the same here as in the script's GetFullPath.
        self.root = Path(tmp.name).resolve()
        self.state = self.root / "state"
        self.state.mkdir()
        self.calls = self.root / "calls.jsonl"
        self.lint_out = self.root / "lint"
        self.stores = [self.root / "store-a", self.root / "store-b"]
        for s in self.stores:
            s.mkdir()
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()

        # korus: a remote, a seed that pushes to it, and a detached checkout one commit behind.
        self.korus_remote = self.root / "korus.git"
        w.git(self.root, "init", "--bare", "-b", "main", str(self.korus_remote))
        self.korus_seed = w.make_repo(self.root / "korus-seed", None)
        w.git(self.korus_seed, "remote", "add", "origin", str(self.korus_remote))
        self.push_stubs("v1")
        self.korus = self.root / "korus"
        w.git(self.root, "clone", "--quiet", str(self.korus_remote), str(self.korus))
        w.git(self.korus, "checkout", "--quiet", "--detach")
        self.korus_v1 = self.head(self.korus)
        self.push_stubs("v2")
        self.korus_v2 = self.remote_head(self.korus_remote)

        # The record repository's reader: a remote with no wiki/events yet, and a detached clone.
        self.vault_remote = self.root / "vault.git"
        w.git(self.root, "init", "--bare", "-b", "main", str(self.vault_remote))
        # Not make_repo: its commit has the same tree, author and message as the korus seed's, so
        # two made in one second get ONE root SHA, and a korus clone then passes as a reader. That
        # happened on the Linux runner, where setUp is fast enough.
        self.vault_seed = self.root / "vault-seed"
        self.vault_seed.mkdir()
        w.git(self.vault_seed, "init", "-b", "main")
        w.git(self.vault_seed, "config", "user.email", "t@example.com")
        w.git(self.vault_seed, "config", "user.name", "t")
        # a.txt, as make_repo writes, because the cases below edit it; only its content differs.
        (self.vault_seed / "a.txt").write_text("the record repository\n", encoding="ascii")
        w.git(self.vault_seed, "add", "a.txt")
        w.git(self.vault_seed, "commit", "-m", "the record repository's first commit")
        w.git(self.vault_seed, "remote", "add", "origin", str(self.vault_remote))
        w.git(self.vault_seed, "push", "--quiet", "origin", "main")
        self.reader = self.root / "reader"
        w.git(self.root, "clone", "--quiet", str(self.vault_remote), str(self.reader))
        w.git(self.reader, "checkout", "--quiet", "--detach")
        # The clone compile works from. The stub compile never touches it; the cycle checks that the
        # reader shares its root commit.
        self.record = self.root / "record"
        w.git(self.root, "clone", "--quiet", str(self.vault_remote), str(self.record))

    # -------------------------------------------------------------------------------- helpers
    def push_stubs(self, version: str):
        wiki = self.korus_seed / "scripts" / "wiki"
        wiki.mkdir(parents=True, exist_ok=True)
        for n in STUB_NAMES:
            (wiki / f"{n}.ps1").write_text(stub(n, version), encoding="ascii")
        w.git(self.korus_seed, "add", "scripts")
        w.git(self.korus_seed, "commit", "--quiet", "-m", f"stubs {version}")
        w.git(self.korus_seed, "push", "--quiet", "origin", "main")

    def push_events_dir(self):
        """What the first merged compile leaves behind: a wiki/events directory at the reader's origin/main."""
        path = self.vault_seed / "wiki" / "events" / "2026" / "09"
        path.mkdir(parents=True)
        (path / "planted.json").write_text("{}\n", encoding="ascii")
        w.git(self.vault_seed, "add", "wiki")
        w.git(self.vault_seed, "commit", "--quiet", "-m", "the first compile landed")
        w.git(self.vault_seed, "push", "--quiet", "origin", "main")

    def head(self, repo: Path) -> str:
        return w.git(repo, "rev-parse", "HEAD").stdout.strip()

    def root_commits(self, repo: Path) -> set[str]:
        return set(w.git(repo, "rev-list", "--max-parents=0", "HEAD").stdout.split())

    def remote_head(self, remote: Path) -> str:
        return w.git(self.root, f"--git-dir={remote}", "rev-parse", "refs/heads/main").stdout.strip()

    def args(self, *extra: str) -> list[str]:
        return ["-KorusCheckout", str(self.korus), "-StateRoot", str(self.state), "-RecordRepo", str(self.record),
                "-ReaderRepo", str(self.reader), "-Store", ",".join(str(s) for s in self.stores),
                "-EvidenceRepo", str(self.evidence), "-LintOut", str(self.lint_out), *extra]

    def cycle(self, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
        full = {"WIKI_CYCLE_TEST_CALLS": str(self.calls)}
        full.update(env or {})
        return w.run(self.pwsh, CYCLE, *self.args(*extra), env=full)

    def called(self) -> list[dict]:
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines() if line.strip()]

    def log_lines(self) -> list[dict]:
        """Every line of every monthly log, oldest file first. Not keyed on today's month, which moves."""
        lines = []
        for path in sorted((self.state / "wiki-cycle").glob("log-*.jsonl")):
            lines += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return lines

    def plant_log_line(self, when: datetime, imp: dict | None = None) -> dict:
        """A line as an earlier run would have logged it, in that run's monthly file."""
        line = {"start": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "exit": 0, "import": imp or {"skipped": "planted"}}
        path = self.state / "wiki-cycle" / f"log-{when.strftime('%Y-%m')}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(line) + "\n")
        return line

    def lock(self) -> Path:
        return self.state / "wiki-cycle" / "lock"

    def plant_lock(self, age_hours: float) -> bytes:
        lock = self.lock()
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("pid 1 on elsewhere, a planted holder", encoding="ascii")
        t = time.time() - age_hours * 3600
        os.utime(lock, (t, t))
        return lock.read_bytes()

    def assert_ran(self, r: subprocess.CompletedProcess, code: int = 0):
        self.assertEqual(code, r.returncode, f"cycle exited {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}")


class ACycleRunsEveryStepFromOriginMain(_CycleCase):
    def test_the_steps_run_in_order_from_the_moved_checkout_and_one_line_is_logged(self):
        self.assertEqual(self.korus_v1, self.head(self.korus), "control: the checkout starts one commit behind")
        r = self.cycle("-Import", "-Json")
        self.assert_ran(r)

        calls = self.called()
        self.assertEqual(["import", "compile", "lint"], [c["name"] for c in calls])
        self.assertEqual({"v2"}, {c["version"] for c in calls}, "every script must be origin/main's")
        for c in calls:
            self.assertEqual((self.korus / "scripts" / "wiki").resolve(), Path(c["root"]).resolve())
        self.assertEqual(self.korus_v2, self.head(self.korus))
        self.assertEqual("", w.git(self.korus, "status", "--porcelain").stdout.strip())

        compile_args = calls[1]["args"]
        self.assertEqual(["-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-Json"], compile_args)
        lint_args = calls[2]["args"]
        today = self.log_lines()[0]["start"][:10]
        self.assertEqual(str(self.reader), lint_args[lint_args.index("-RecordRepo") + 1])
        self.assertEqual(str(self.evidence), lint_args[lint_args.index("-EvidenceRepo") + 1])
        self.assertEqual(str(self.lint_out / f"lint-{today}.md"), lint_args[lint_args.index("-Out") + 1])
        self.assertTrue((self.lint_out / f"lint-{today}.md").is_file())
        import_args = calls[0]["args"]
        self.assertEqual(",".join(str(s) for s in self.stores), import_args[import_args.index("-Store") + 1])

        lines = self.log_lines()
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertEqual(line, json.loads(r.stdout), "-Json prints the line it logs")
        for field in ("start", "end", "exit", "outcome", "korus_sha", "reader_sha", "lock", "import", "compile", "lint"):
            self.assertIn(field, line)
        self.assertRegex(line["start"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertRegex(line["end"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertLessEqual(line["start"], line["end"])
        self.assertEqual(0, line["exit"])
        self.assertEqual("every step ran", line["outcome"])
        self.assertEqual(self.korus_v2, line["korus_sha"])
        self.assertEqual(self.remote_head(self.vault_remote), line["reader_sha"])
        self.assertEqual({"state": "taken"}, line["lock"])
        self.assertEqual(0, line["import"]["exit"])
        self.assertEqual({"imported": 3, "merged": 1, "refused": 0}, line["import"]["counts"])
        self.assertEqual(0, line["compile"]["exit"])
        self.assertEqual("compiled", line["compile"]["result"])
        self.assertEqual(2, line["compile"]["added"])
        self.assertEqual("https://example.invalid/pull/7", line["compile"]["pr"])
        self.assertEqual(0, line["lint"]["exit"])
        self.assertEqual({"conflict": 1, "dead-evidence": 0, "stale": 2, "orphan-page": 0,
                          "promotion-candidate": 0, "unchecked": 4}, line["lint"]["totals"],
                         "only the Totals table is read; the planted row under Inputs is not")
        self.assertFalse(self.lock().exists(), "the run releases its lock")

    def test_without_json_it_prints_one_summary_line(self):
        r = self.cycle("-NoImport")
        self.assert_ran(r)
        self.assertEqual(1, len(r.stdout.splitlines()), r.stdout)
        self.assertTrue(r.stdout.startswith(f"wiki cycle: korus at {self.korus_v2}; import skipped (-NoImport); compile exit 0, compiled;"), r.stdout)
        self.assertTrue(r.stdout.rstrip().endswith("exit 0."), r.stdout)
        r = self.cycle("-NoImport", "-WhatIf")
        self.assert_ran(r)
        self.assertIn("a run would exit 0", r.stdout)

    def test_a_second_run_appends_a_second_line(self):
        self.assert_ran(self.cycle("-NoImport"))
        self.assert_ran(self.cycle("-NoImport"))
        self.assertEqual(2, len(self.log_lines()))


class TheImportRunsOnItsDayOrWhenForced(_CycleCase):
    def test_a_non_import_day_skips_the_import(self):
        other = day_name(datetime.now() + timedelta(days=3))
        self.assert_ran(self.cycle("-ImportDay", other))
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])
        self.assertIn("not the import day", self.log_lines()[0]["import"]["skipped"])

    def test_import_forces_it_on_any_day(self):
        other = day_name(datetime.now() + timedelta(days=3))
        self.assert_ran(self.cycle("-ImportDay", other, "-Import"))
        self.assertEqual(["import", "compile", "lint"], [c["name"] for c in self.called()])
        self.assertEqual("-Import", self.log_lines()[0]["import"]["reason"])

    def test_the_import_day_runs_it(self):
        now = datetime.now()
        if now.hour == 23 and now.minute >= 58:
            self.skipTest("too close to midnight to name today's day reliably")
        self.assert_ran(self.cycle("-ImportDay", day_name(now)))
        self.assertEqual(["import", "compile", "lint"], [c["name"] for c in self.called()])

    def test_no_import_skips_it_on_its_day(self):
        self.assert_ran(self.cycle("-ImportDay", day_name(datetime.now()), "-NoImport"))
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])

    def test_import_and_no_import_together_is_refused(self):
        r = self.cycle("-Import", "-NoImport")
        self.assert_ran(r, 2)
        self.assertEqual([], self.called())

    def test_a_bad_import_day_is_refused(self):
        for bad in ("Someday", "3", "Friday,Saturday"):
            r = self.cycle("-ImportDay", bad)
            self.assert_ran(r, 2)
        self.assertEqual([], self.called())

    def test_a_due_import_with_no_store_fails_that_step_only(self):
        args = self.args("-Import")
        i = args.index("-Store")
        del args[i:i + 2]
        r = w.run(self.pwsh, CYCLE, *args, env={"WIKI_CYCLE_TEST_CALLS": str(self.calls)})
        self.assert_ran(r, 1)
        self.assertIn("no -Store", r.stderr)
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])
        self.assertIsNone(self.log_lines()[-1]["import"]["exit"])


class AMissedImportDayIsCaughtUp(_CycleCase):
    def setUp(self):
        super().setUp()
        now = datetime.now()
        if now.hour == 23 and now.minute >= 58:
            self.skipTest("too close to midnight to name the days reliably")
        # The import day was two days ago, so today is never it.
        self.missed = day_name(now - timedelta(days=2))

    def test_the_next_run_imports_once(self):
        # The cycle ran before the missed day, and no import has run since.
        self.plant_log_line(datetime.now(timezone.utc) - timedelta(days=8))
        self.assert_ran(self.cycle("-ImportDay", self.missed))
        self.assertEqual(["import", "compile", "lint"], [c["name"] for c in self.called()])
        self.assertIn("catch-up", self.log_lines()[-1]["import"]["reason"])
        # Control: the catch-up is owed once. The line that run wrote covers it.
        self.calls.unlink()
        self.assert_ran(self.cycle("-ImportDay", self.missed))
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])

    def test_nothing_is_owed_when_the_cycle_did_not_run_before_the_import_day(self):
        self.plant_log_line(datetime.now(timezone.utc) - timedelta(hours=1))
        self.assert_ran(self.cycle("-ImportDay", self.missed))
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])

    def test_an_import_that_could_not_run_is_still_owed(self):
        self.plant_log_line(datetime.now(timezone.utc) - timedelta(days=8))
        self.plant_log_line(datetime.now(timezone.utc) - timedelta(hours=1), imp={"exit": 2})
        self.assert_ran(self.cycle("-ImportDay", self.missed))
        self.assertEqual("import", self.called()[0]["name"])

    def test_an_import_that_needed_a_look_counts_as_run(self):
        self.plant_log_line(datetime.now(timezone.utc) - timedelta(days=8))
        self.plant_log_line(datetime.now(timezone.utc) - timedelta(hours=1), imp={"exit": 1})
        self.assert_ran(self.cycle("-ImportDay", self.missed))
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])


class TheRecordRepoReachesTheImportOnlyWhenItHasALog(_CycleCase):
    def test_no_events_dir_means_no_record_repo_and_a_landed_one_means_it_is_passed(self):
        self.assert_ran(self.cycle("-Import"))
        first = self.called()[0]
        self.assertEqual("import", first["name"])
        self.assertNotIn("-RecordRepo", first["args"])
        self.assertFalse(self.log_lines()[0]["import"]["record_repo_passed"])

        # The events directory lands on the remote only. The run must see it after moving the reader.
        self.push_events_dir()
        self.assertFalse((self.reader / "wiki" / "events").exists(), "control: the reader does not have it yet")
        self.calls.unlink()
        self.assert_ran(self.cycle("-Import"))
        second = self.called()[0]
        self.assertEqual(str(self.reader), second["args"][second["args"].index("-RecordRepo") + 1])
        self.assertTrue(self.log_lines()[1]["import"]["record_repo_passed"])


class ACheckoutWithLocalChangesIsNeverMoved(_CycleCase):
    def assert_refused_and_unmoved(self, r, needle: str):
        self.assert_ran(r, 2)
        self.assertIn(needle, r.stderr)
        self.assertEqual([], self.called(), "no step may run")
        self.assertEqual(self.korus_v1, self.head(self.korus))
        line = self.log_lines()[-1]
        self.assertEqual("could not run", line["outcome"])
        self.assertEqual(2, line["exit"])
        self.assertIn(needle, line["problem"])

    def test_a_modified_tracked_file_in_the_korus_checkout(self):
        target = self.korus / "scripts" / "wiki" / "lint.ps1"
        target.write_text("# a local edit\n", encoding="ascii")
        self.assert_refused_and_unmoved(self.cycle("-NoImport"), "local changes")
        self.assertEqual("# a local edit\n", target.read_text(encoding="ascii"))
        # Control: the same run goes through once the edit is gone.
        w.git(self.korus, "checkout", "--", ".")
        self.assert_ran(self.cycle("-NoImport"))

    def test_a_staged_change_in_the_reader_leaves_both_checkouts_where_they_were(self):
        reader_head = self.head(self.reader)
        (self.reader / "a.txt").write_text("edited\n", encoding="ascii")
        w.git(self.reader, "add", "a.txt")
        self.assert_refused_and_unmoved(self.cycle("-NoImport"), "local changes")
        self.assertEqual(reader_head, self.head(self.reader))

    def test_an_untracked_file_does_not_block_it(self):
        (self.korus / "scratch.txt").write_text("x\n", encoding="ascii")
        self.assert_ran(self.cycle("-NoImport"))
        self.assertTrue((self.korus / "scratch.txt").exists())

    def test_a_checkout_on_a_branch_is_refused(self):
        w.git(self.korus, "checkout", "--quiet", "-B", "somebodys-work")
        r = self.cycle("-NoImport")
        self.assert_ran(r, 2)
        self.assertIn("switch --detach", r.stderr)
        self.assertEqual([], self.called())
        self.assertEqual("somebodys-work", w.git(self.korus, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip())

    def test_a_local_commit_is_not_stranded(self):
        (self.korus / "a.txt").write_text("committed here\n", encoding="ascii")
        w.git(self.korus, "config", "user.email", "t@example.com")
        w.git(self.korus, "config", "user.name", "t")
        w.git(self.korus, "commit", "--quiet", "-am", "a local commit")
        local = self.head(self.korus)
        r = self.cycle("-NoImport")
        self.assert_ran(r, 2)
        self.assertIn("strand", r.stderr)
        self.assertEqual(local, self.head(self.korus))
        self.assertEqual([], self.called())

    def test_a_local_commit_in_the_reader_leaves_the_korus_checkout_unmoved(self):
        w.git(self.reader, "config", "user.email", "t@example.com")
        w.git(self.reader, "config", "user.name", "t")
        (self.reader / "a.txt").write_text("committed in the reader\n", encoding="ascii")
        w.git(self.reader, "commit", "--quiet", "-am", "a local commit")
        local = self.head(self.reader)
        r = self.cycle("-NoImport")
        self.assert_ran(r, 2)
        self.assertIn("strand", r.stderr)
        self.assertEqual(local, self.head(self.reader))
        self.assertEqual(self.korus_v1, self.head(self.korus), "nothing moves until both checkouts pass")
        self.assertEqual([], self.called())

    def test_a_head_another_ref_holds_is_moved_after_a_squash_merge(self):
        """A checkout left at a pull request's head: main lacks the commit, but a ref still holds it."""
        w.git(self.korus_seed, "checkout", "--quiet", "-b", "pr-branch")
        (self.korus_seed / "pr.txt").write_text("pr\n", encoding="ascii")
        w.git(self.korus_seed, "add", "pr.txt")
        w.git(self.korus_seed, "commit", "--quiet", "-m", "a pull request")
        w.git(self.korus_seed, "push", "--quiet", "origin", "pr-branch")
        w.git(self.korus_seed, "checkout", "--quiet", "main")
        w.git(self.korus, "fetch", "--quiet", "origin")
        w.git(self.korus, "checkout", "--quiet", "--detach", "origin/pr-branch")
        self.assert_ran(self.cycle("-NoImport"))
        self.assertEqual(self.korus_v2, self.head(self.korus))

    def test_a_reader_of_another_repository_is_refused(self):
        wrong = self.root / "wrong-reader"
        w.git(self.root, "clone", "--quiet", str(self.korus_remote), str(wrong))
        w.git(wrong, "checkout", "--quiet", "--detach")
        # The control. Were the two roots one SHA, the wrong reader WOULD share a root, and a
        # correct cycle would run rather than refuse.
        self.assertNotEqual(self.root_commits(wrong), self.root_commits(self.record),
                            "control: the wrong reader and the record must not share a root commit")
        args = self.args("-Import")
        args[args.index("-ReaderRepo") + 1] = str(wrong)
        r = w.run(self.pwsh, CYCLE, *args, env={"WIKI_CYCLE_TEST_CALLS": str(self.calls)})
        self.assert_ran(r, 2)
        self.assertIn("shares no root commit", r.stderr)
        self.assertEqual([], self.called())
        self.assertEqual(self.korus_v1, self.head(self.korus))

    def test_a_store_path_holding_a_comma_is_refused(self):
        odd = self.root / "store,c"
        odd.mkdir()
        args = self.args("-Import")
        args[args.index("-Store") + 1] = str(odd)
        r = w.run(self.pwsh, CYCLE, *args, env={"WIKI_CYCLE_TEST_CALLS": str(self.calls)})
        self.assert_ran(r, 2)
        self.assertIn("comma", r.stderr)
        self.assertEqual([], self.called())

    def test_a_subdirectory_of_a_checkout_is_refused(self):
        args = self.args("-NoImport")
        args[args.index("-KorusCheckout") + 1] = str(self.korus / "scripts")
        r = w.run(self.pwsh, CYCLE, *args, env={"WIKI_CYCLE_TEST_CALLS": str(self.calls)})
        self.assert_ran(r, 2)
        self.assertIn("not its top", r.stderr)

    def test_a_missing_path_is_refused(self):
        args = self.args("-NoImport")
        args[args.index("-RecordRepo") + 1] = str(self.root / "no-such-record")
        r = w.run(self.pwsh, CYCLE, *args, env={"WIKI_CYCLE_TEST_CALLS": str(self.calls)})
        self.assert_ran(r, 2)
        self.assertIn("does not exist", r.stderr)
        self.assertEqual([], self.called())


class TheLockKeepsTwoCyclesApart(_CycleCase):
    def test_a_live_lock_refuses_the_run_and_is_left_alone(self):
        before = self.plant_lock(age_hours=0.5)
        r = self.cycle("-NoImport")
        self.assert_ran(r, 2)
        self.assertIn("holds the lock", r.stderr)
        self.assertEqual([], self.called())
        self.assertEqual(before, self.lock().read_bytes(), "a refused run never removes a live holder's lock")
        self.assertEqual(self.korus_v1, self.head(self.korus))
        line = self.log_lines()[-1]
        self.assertEqual("held", line["lock"]["state"])
        self.assertEqual(2, line["exit"])

    def test_a_lock_older_than_two_hours_is_cleared_and_logged(self):
        self.plant_lock(age_hours=3)
        r = self.cycle("-NoImport")
        self.assert_ran(r)
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])
        self.assertIn("stale lock", r.stderr)
        lock = self.log_lines()[-1]["lock"]
        self.assertEqual("stale lock cleared", lock["state"])
        self.assertGreater(lock["age_hours"], 2.9)
        self.assertIn("planted holder", lock["holder"])
        self.assertFalse(self.lock().exists())


class AFailingStepIsRecordedAndTheOthersStillRun(_CycleCase):
    def test_compile_exit_2_gives_exit_1_and_lint_still_runs(self):
        r = self.cycle("-NoImport", env={"WIKI_CYCLE_TEST_COMPILE_EXIT": "2"})
        self.assert_ran(r, 1)
        self.assertEqual(["compile", "lint"], [c["name"] for c in self.called()])
        line = self.log_lines()[-1]
        self.assertEqual(1, line["exit"])
        self.assertEqual("a step returned an error", line["outcome"])
        self.assertEqual(2, line["compile"]["exit"])
        self.assertNotIn("result", line["compile"], "a compile that stopped early printed no result")
        self.assertIn("failing on purpose with 2", line["compile"]["stderr_tail"])
        self.assertEqual(0, line["lint"]["exit"])

    def test_compile_exit_1_is_recorded_as_returned(self):
        self.assert_ran(self.cycle("-NoImport", env={"WIKI_CYCLE_TEST_COMPILE_EXIT": "1"}), 1)
        self.assertEqual(1, self.log_lines()[-1]["compile"]["exit"])

    def test_an_import_that_needs_a_look_gives_exit_1(self):
        self.assert_ran(self.cycle("-Import", env={"WIKI_CYCLE_TEST_IMPORT_EXIT": "1"}), 1)
        line = self.log_lines()[-1]
        self.assertEqual(1, line["import"]["exit"])
        self.assertEqual(0, line["compile"]["exit"])
        self.assertEqual(0, line["lint"]["exit"])

    def test_a_failed_lint_has_no_totals(self):
        self.assert_ran(self.cycle("-NoImport", env={"WIKI_CYCLE_TEST_LINT_EXIT": "2"}), 1)
        line = self.log_lines()[-1]
        self.assertEqual(2, line["lint"]["exit"])
        self.assertNotIn("totals", line["lint"])


class WhatIfPlansAndWritesNothing(_CycleCase):
    def test_the_plan_names_each_step_and_nothing_moves(self):
        r = self.cycle("-Import", "-WhatIf", "-Json")
        self.assert_ran(r)
        plan = json.loads(r.stdout)
        self.assertTrue(plan["what_if"])
        self.assertEqual(0, plan["would_exit"])
        self.assertEqual([], plan["problems"])
        self.assertEqual(["import", "compile", "lint"], [s["name"] for s in plan["steps"]])
        compile_step = plan["steps"][1]
        self.assertEqual(str(self.korus / "scripts" / "wiki" / "compile.ps1"), compile_step["script"])
        self.assertEqual(["-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-Json"], compile_step["arguments"])
        self.assertFalse(plan["steps"][0]["record_repo_passed"])
        self.assertTrue(plan["import"]["due"])
        self.assertEqual("free", plan["lock"])
        self.assertEqual([], self.called())
        self.assertFalse((self.state / "wiki-cycle").exists(), "no log line, no lock")
        self.assertFalse(self.lint_out.exists())
        self.assertEqual(self.korus_v1, self.head(self.korus))
        self.assertEqual(self.korus_v1, w.git(self.korus, "rev-parse", "origin/main").stdout.strip(), "nothing was fetched")

    def test_the_plan_reports_a_refusal_with_exit_2(self):
        (self.korus / "scripts" / "wiki" / "lint.ps1").write_text("# edit\n", encoding="ascii")
        self.plant_lock(age_hours=0.1)
        r = self.cycle("-NoImport", "-WhatIf", "-Json")
        self.assert_ran(r, 2)
        plan = json.loads(r.stdout)
        self.assertEqual(2, plan["would_exit"])
        self.assertEqual(2, len(plan["problems"]))
        self.assertEqual(["compile", "lint"], [s["name"] for s in plan["steps"]])

    def test_a_missing_argument_still_prints_a_plan(self):
        r = w.run(self.pwsh, CYCLE, "-WhatIf", "-Json")
        self.assert_ran(r, 2)
        plan = json.loads(r.stdout)
        self.assertEqual(2, plan["would_exit"])
        self.assertIn("-KorusCheckout is required.", plan["problems"])


class TheRegistrarPlansExactlyWhatItWouldRegister(_CycleCase):
    def setUp(self):
        super().setUp()
        # The checkout the task runs from must hold the real cycle.ps1, beside the stubs.
        target = self.korus_seed / "scripts" / "wiki" / "cycle.ps1"
        target.write_bytes(CYCLE.read_bytes())
        w.git(self.korus_seed, "add", "scripts")
        w.git(self.korus_seed, "commit", "--quiet", "-m", "the real cycle")
        w.git(self.korus_seed, "push", "--quiet", "origin", "main")
        w.git(self.korus, "fetch", "--quiet", "origin")
        w.git(self.korus, "checkout", "--quiet", "--detach", "origin/main")
        self.task = "KORUS-Wiki-Cycle-test-" + uuid.uuid4().hex[:8]

    def register(self, *extra: str, full: bool = True) -> subprocess.CompletedProcess:
        base = self.args()[:] if full else []
        return w.run(self.pwsh, REGISTER, *base, "-TaskName", self.task, *extra)

    def test_whatif_json_names_every_setting(self):
        r = self.register("-At", "07:15", "-WhatIf", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        plan = json.loads(r.stdout)
        self.assertTrue(plan["whatIf"])
        self.assertEqual(self.task, plan["taskName"])
        self.assertEqual("Interactive", plan["logonType"])
        self.assertEqual("Limited", plan["runLevel"])
        self.assertTrue(plan["startWhenAvailable"])
        self.assertTrue(plan["allowStartIfOnBatteries"])
        self.assertTrue(plan["dontStopIfGoingOnBatteries"])
        self.assertEqual(1, plan["executionTimeLimitHours"])
        self.assertEqual("IgnoreNew", plan["multipleInstances"])
        self.assertEqual({"kind": "daily", "at": "07:15"}, plan["trigger"])
        self.assertEqual("Sunday", plan["importDay"])
        self.assertTrue(plan["cycleExists"])
        self.assertEqual([], plan["missing"])
        self.assertEqual(str(self.korus), plan["workingDirectory"])
        arg = plan["argument"]
        cycle = self.korus / "scripts" / "wiki" / "cycle.ps1"
        window = "-WindowStyle Hidden " if sys.platform == "win32" else ""
        self.assertIn(f'{window}-ExecutionPolicy Bypass -File "{cycle}"', arg)
        self.assertIn(f'-KorusCheckout "{self.korus}"', arg)
        self.assertIn(f'-StateRoot "{self.state}"', arg)
        self.assertIn(f'-RecordRepo "{self.record}"', arg)
        self.assertIn(f'-ReaderRepo "{self.reader}"', arg)
        self.assertIn('-Store "' + ",".join(str(s) for s in self.stores) + '"', arg)
        self.assertIn(f'-EvidenceRepo "{self.evidence}"', arg)
        self.assertIn(f'-LintOut "{self.lint_out}"', arg)
        self.assertTrue(arg.endswith("-ImportDay Sunday"))

    def test_the_registered_command_line_runs_the_cycle(self):
        """The argument string, run as Task Scheduler would run it, parses into a cycle that plans exit 0."""
        plan = json.loads(self.register("-WhatIf", "-Json").stdout)
        tail = " -WhatIf -Json"
        if sys.platform == "win32":
            # Without the hidden window: a child sharing this console would hide the runner's own.
            argument = plan["argument"].replace("-WindowStyle Hidden ", "")
            self.assertNotEqual(plan["argument"], argument, "control: the registered line does hide its window")
            r = subprocess.run(f'"{plan["executable"]}" {argument}{tail}', capture_output=True, text=True,
                               timeout=w.TIMEOUT_SECONDS)
        else:
            r = subprocess.run([plan["executable"], *shlex.split(plan["argument"] + tail)], capture_output=True,
                               text=True, timeout=w.TIMEOUT_SECONDS)
        self.assertEqual(0, r.returncode, r.stderr)
        cycle_plan = json.loads(r.stdout)
        self.assertEqual(0, cycle_plan["would_exit"], cycle_plan["problems"])
        self.assertEqual(str(self.state), cycle_plan["steps"][-1]["arguments"][1])
        self.assertFalse((self.state / "wiki-cycle").exists())

    def test_a_missing_directory_shows_in_the_plan(self):
        args = self.args()
        args[args.index("-EvidenceRepo") + 1] = str(self.root / "no-such-evidence")
        r = w.run(self.pwsh, REGISTER, *args, "-TaskName", self.task, "-WhatIf", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([str(self.root / "no-such-evidence")], json.loads(r.stdout)["missing"])

    @unittest.skipUnless(sys.platform == "win32", "a drive root with a backslash is a Windows path")
    def test_a_trailing_backslash_does_not_escape_its_closing_quote(self):
        drive = str(self.root)[:3]
        args = self.args()
        args[args.index("-LintOut") + 1] = drive
        r = w.run(self.pwsh, REGISTER, *args, "-TaskName", self.task, "-WhatIf", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        arg = json.loads(r.stdout)["argument"]
        self.assertIn(f'-LintOut "{drive}\\" -ImportDay Sunday', arg)

    def test_a_store_path_holding_a_comma_is_refused(self):
        odd = self.root / "store,c"
        odd.mkdir()
        args = self.args()
        args[args.index("-Store") + 1] = str(odd)
        r = w.run(self.pwsh, REGISTER, *args, "-TaskName", self.task, "-WhatIf", "-Json")
        self.assertEqual(2, r.returncode, r.stdout)
        self.assertIn("comma", r.stderr)

    def test_bad_arguments_are_refused(self):
        args = self.args()
        i = args.index("-Store")
        no_store = args[:i] + args[i + 2:]
        cases = [
            no_store + ["-WhatIf"],
            self.args("-At", "7pm", "-WhatIf"),
            self.args("-ImportDay", "Funday", "-WhatIf"),
            self.args("-ImportDay", "Friday,Saturday", "-WhatIf"),
            self.args("-ImportDay", "3", "-WhatIf"),
            ["-StateRoot", str(self.state), "-WhatIf"],
        ]
        for case in cases:
            r = w.run(self.pwsh, REGISTER, *case, "-TaskName", self.task)
            self.assertEqual(2, r.returncode, f"{case}: {r.stdout} {r.stderr}")

    def test_uninstall_whatif_removes_nothing(self):
        r = w.run(self.pwsh, REGISTER, "-Uninstall", "-TaskName", self.task, "-WhatIf", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        result = json.loads(r.stdout)
        self.assertTrue(result["whatIf"])
        self.assertFalse(result["removed"])

    @unittest.skipUnless(sys.platform == "win32", "the task store exists only on Windows")
    def test_no_task_of_the_decoy_name_was_registered(self):
        self.register("-WhatIf", "-Json")
        probe = "if (Get-ScheduledTask -TaskName '{0}' -ErrorAction SilentlyContinue) {{ 'FOUND' }} else {{ 'NONE' }}"
        # Control: the same probe finds a task that does exist, so NONE below is a reading.
        first = subprocess.run([self.pwsh, "-NoProfile", "-Command",
                                "(Get-ScheduledTask | Where-Object { $_.TaskName -notmatch \"'\" } | Select-Object -First 1).TaskName"],
                               capture_output=True, text=True, timeout=w.TIMEOUT_SECONDS).stdout.strip()
        self.assertTrue(first, "control: this machine lists no scheduled task at all")
        found = subprocess.run([self.pwsh, "-NoProfile", "-Command", probe.format(first)],
                               capture_output=True, text=True, timeout=w.TIMEOUT_SECONDS)
        self.assertEqual("FOUND", found.stdout.strip(), found.stderr)
        r = subprocess.run([self.pwsh, "-NoProfile", "-Command", probe.format(self.task)],
                           capture_output=True, text=True, timeout=w.TIMEOUT_SECONDS)
        self.assertEqual("NONE", r.stdout.strip(), r.stderr)

    @unittest.skipUnless(sys.platform == "win32", "-Status reads the Windows task store")
    def test_status_of_an_unregistered_task_prints_two_lines(self):
        r = w.run(self.pwsh, REGISTER, "-Status", "-StateRoot", str(self.state), "-TaskName", self.task)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([f"No scheduled task '{self.task}'.", "  last log line: (none)"], r.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
