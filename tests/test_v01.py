#!/usr/bin/env python3
"""architect-run acceptance tests for R1 and preflight (v0.1 checklist, plus the
gaps Grok named in his round-3 review).

Run:  python3 tests/test_v01.py
Standard library only. No network. Every test works on a throwaway copy of
this directory, so the real work/, budget/ and log/ are never touched.
Each test names the line of Grok's round-2 checklist it answers.
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = "the cage holds"
GOOD = hashlib.sha256((CONTENT + "\n").encode()).hexdigest()
FORBIDDEN = ("claude", "grok", "curl", "docker", "ssh", "systemctl", "wget", "sudo")
CANARY_ENV = {"ANTHROPIC_API_KEY": "sk-ant-CANARY-1234", "XAI_API_KEY": "xai-CANARY-5678",
              "SIGNAL_NUMBER": "+15550001111", "META_PUBLISH_TOKEN": "EAAB-CANARY-9"}
ALLOWED_TOP = {"work", "outbox", "budget", "log"}


def read(path):
    with open(path) as fh:
        return fh.read()


def write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="arch-test-")
        self.root = os.path.join(self.tmp, "architect-run")
        shutil.copytree(HERE, self.root, ignore=shutil.ignore_patterns(
            ".git", "work", "outbox", "budget", "log", "keys", "rulings", "__pycache__"))
        self.shims = os.path.join(self.tmp, "shims")
        os.makedirs(self.shims)
        self.called = os.path.join(self.tmp, "called.txt")
        for name in FORBIDDEN:
            self.shim(name, 'echo "%s $*" >> "%s"\nexit 0' % (name, self.called))
        self.task(expect=GOOD)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def shim(self, name, body):
        path = os.path.join(self.shims, name)
        with open(path, "w") as fh:
            fh.write("#!/bin/bash\n" + body + "\n")
        os.chmod(path, 0o755)

    def task(self, name="r1.yaml", expect=GOOD, target="work/r1.txt", tid="r1-checksum"):
        body = ["id: " + tid, "kind: r1", "target: " + target, "content: " + CONTENT]
        if expect is not None:
            body.append("expect_sha256: " + expect)
        with open(os.path.join(self.root, "inbox", name), "w") as fh:
            fh.write("\n".join(body) + "\n")

    def run_sh(self, script, *args, cwd=None):
        env = dict(os.environ, **CANARY_ENV)
        env["PATH"] = self.shims + os.pathsep + env["PATH"]
        return subprocess.run(["bash", os.path.join(self.root, script)] + list(args),
                              cwd=cwd or self.root, env=env, capture_output=True, text=True, timeout=60)

    def tree(self):
        seen = {}
        for base, _dirs, files in os.walk(self.root):
            for f in files:
                p = os.path.join(base, f)
                seen[os.path.relpath(p, self.root)] = os.stat(p).st_mtime_ns
        return seen

    def log(self):
        p = os.path.join(self.root, "log", "run.log")
        return read(p) if os.path.exists(p) else ""

    def ledger(self):
        return json.loads(read(os.path.join(self.root, "budget", "ledger.json")))

    def edit(self, rel, old, new):
        p = os.path.join(self.root, rel)
        with open(p) as fh:
            text = fh.read()
        self.assertIn(old, text)
        with open(p, "w") as fh:
            fh.write(text.replace(old, new))

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, rel))


class R1(Base):
    def test_default_run_writes_file_and_prints_checksum(self):
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(GOOD, r.stdout)
        self.assertTrue(self.exists("work/r1.txt"))
        self.assertTrue(self.exists("work/r1-checksum.ok"))
        self.assertIn("OK r1-checksum", self.log())

    def test_second_run_does_not_count_a_second_success(self):
        self.assertEqual(self.run_sh("run.sh").returncode, 0)
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.ledger()["successes"]), 1)
        self.assertIn("already recorded", r.stdout)
        self.assertEqual(self.log().count("first success"), 1)

    def test_no_expect_line_no_run(self):
        self.task(expect=None)
        r = self.run_sh("run.sh")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.exists("work"))
        self.assertIn("No expect line, no run", r.stdout)

    def test_blank_expect_refuses(self):
        self.task(expect="")
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(self.exists("work"))

    def test_shipped_task_carries_the_hash_jeremy_ran(self):
        self.assertIn("expect_sha256: " + GOOD, read(os.path.join(HERE, "inbox", "r1.yaml")))

    def test_wrong_checksum_fails_and_leaves_no_success(self):
        self.task(expect="0" * 64)
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 4)
        self.assertFalse(self.exists("work/r1-checksum.ok"))
        self.assertFalse(self.exists("work/r1.txt"), "a file that failed its checksum must not be left behind")
        self.assertFalse(self.exists("budget/ledger.json"))
        self.assertIn("FAIL", self.log())

    def test_runs_from_another_directory(self):
        r = self.run_sh("run.sh", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "work")))


class Budget(Base):
    def test_halt_test_stops_with_HALT_and_no_success_file(self):
        r = self.run_sh("run.sh", "--halt-test")
        self.assertEqual(r.returncode, 10)
        self.assertIn("HALT", self.log())
        self.assertFalse(self.exists("work"))
        self.assertFalse(self.exists("budget/ledger.json"))

    def test_limits_env_is_really_read(self):
        self.edit("limits.env", "MONTH_USD=40", "MONTH_USD=0")
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("HALT", r.stdout)
        self.assertFalse(self.exists("work"))

    def test_task_ceiling_is_really_read(self):
        self.edit("limits.env", "TASK_USD=8", "TASK_USD=0")
        self.assertEqual(self.run_sh("run.sh").returncode, 10)

    def seed(self, spent, holds=()):
        os.makedirs(os.path.join(self.root, "budget"), exist_ok=True)
        import datetime
        month = datetime.datetime.now().strftime("%Y-%m")
        write(os.path.join(self.root, "budget", "ledger.json"), json.dumps(
            {"version": 1, "months": {month: {"spent_usd": spent}}, "successes": {}, "holds": list(holds)}))

    def test_halt_percentages_are_really_read(self):
        self.seed(35.0)                       # under the shipped line of 90% of $40 = $36
        self.assertEqual(self.run_sh("run.sh").returncode, 0)
        self.edit("limits.env", "MONTH_HALT_PCT=90", "MONTH_HALT_PCT=80")   # line moves to $32
        self.assertEqual(self.run_sh("run.sh").returncode, 10)
        self.edit("limits.env", "MONTH_HALT_PCT=80", "MONTH_HALT_PCT=90")
        self.edit("limits.env", "TASK_HALT_PCT=90", "TASK_HALT_PCT=0")      # task line moves to $0
        self.assertEqual(self.run_sh("run.sh").returncode, 10)

    def test_spend_at_the_halt_line_stops(self):
        self.seed(36.0)
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 10)
        self.assertFalse(self.exists("work"))

    def test_open_hold_stops_r1(self):
        self.seed(0.0, holds=[{"id": "r2-x", "usd": 2.0, "provider": "xai", "at": "t"}])
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 10)
        self.assertIn("hold", r.stdout)
        self.assertFalse(self.exists("work"))

    def test_wall_clock_alarm_fires(self):
        self.edit("limits.env", "WALL_CLOCK_S=1500", "WALL_CLOCK_S=1")
        p = os.path.join(self.root, "denylist.txt")
        os.remove(p)
        os.mkfifo(p)                          # opening it blocks, so only the alarm can end the run
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("HALT wall clock", r.stdout)
        self.assertFalse(self.exists("work"))

    def test_missing_limit_refuses(self):
        self.edit("limits.env", "WALL_CLOCK_S=1500", "")
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(self.exists("work"))

    def test_shipped_limits_are_the_ruled_values(self):
        want = {"TASK_USD": "8", "TASK_HALT_PCT": "90", "MONTH_USD": "40", "MONTH_HALT_PCT": "90",
                "ROUNDS": "2", "DIFF_MAX_LINES": "400", "DIFF_MAX_FILES": "8",
                "NEIGHBOR_MAX_FILES": "8", "NEIGHBOR_MAX_KB": "80", "WALL_CLOCK_S": "1500",
                "CONSOLE_CAP_ANTHROPIC_USD": "40", "CONSOLE_CAP_ANTHROPIC_IS_REAL": "yes",
                "ANTHROPIC_MONTH_USD": "0", "CONSOLE_CAP_XAI_USD": "",
                "CONSOLE_CAP_XAI_IS_REAL": "no"}
        got = dict(l.strip().split("=", 1) for l in read(os.path.join(HERE, "limits.env")).splitlines()
                   if "=" in l and not l.startswith("#"))
        self.assertEqual({k: got.get(k) for k in want}, want)
        self.assertEqual({k: got.get(k) for k in ("R2_TASK_USD", "XAI_MONTH_USD", "XAI_IN_PER_M",
                          "XAI_CACHED_IN_PER_M", "XAI_OUT_PER_M")},
                         {"R2_TASK_USD": "2", "XAI_MONTH_USD": "15", "XAI_IN_PER_M": "2",
                          "XAI_CACHED_IN_PER_M": "0.50", "XAI_OUT_PER_M": "6"})


class Denylist(Base):
    def refused(self, target):
        self.task(target=target)
        before = self.tree()
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 3, "%s -> %s" % (target, r.stdout))
        self.assertFalse(self.exists("work"), target)
        changed = {k.split(os.sep)[0] for k, v in self.tree().items() if before.get(k) != v}
        self.assertTrue(changed <= {"log", "outbox"}, changed)

    def test_listed_paths_are_refused_before_writing(self):
        for target in ("/forge/reverb/x.txt", "/forge/secrets.env", "/forge/forge-ads/a/b.txt",
                       "/forge/architect/main.py", "/forge/forge_shell/deploy/up.sh",
                       "/forge/oracle/x", "/forge/warp/forge_shell/x", "/forge/warp/app.py",
                       "/forge/signal-api/x", "/forge/backups/x"):
            self.refused(target)

    def test_orchestrator_itself_is_refused(self):
        for target in ("run.sh", "../architect-run/limits.env", "work/../denylist.txt",
                       "keys/anthropic", "budget/ledger.json", "inbox/r1.yaml"):
            self.refused(target)

    def test_dot_env_anywhere_is_refused(self):
        self.refused("work/.env")
        self.refused("work/sub/.env/x")

    def test_outside_work_is_refused(self):
        self.refused("/tmp/arch-escape.txt")
        self.refused("../escape.txt")

    def test_symlink_out_of_work_is_refused(self):
        os.makedirs(os.path.join(self.root, "work"))
        os.symlink(self.tmp, os.path.join(self.root, "work", "out"))
        self.task(target="work/out/escape.txt")
        r = self.run_sh("run.sh")
        self.assertEqual(r.returncode, 3)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escape.txt")))

    def test_missing_or_empty_denylist_fails_closed(self):
        p = os.path.join(self.root, "denylist.txt")
        write(p, "# nothing\n")
        self.assertEqual(self.run_sh("run.sh").returncode, 3)
        os.remove(p)
        self.assertEqual(self.run_sh("run.sh").returncode, 3)
        self.assertFalse(self.exists("work"))

    def test_shipped_denylist_has_every_ruled_entry(self):
        have = {l.strip() for l in read(os.path.join(HERE, "denylist.txt")).splitlines()}
        for e in ("/forge/secrets.env", "/forge/secrets.qa.env", "/forge/.env", "**/.env",
                  "/forge/forge-ads", "/forge/reverb", "/forge/beacon-ads", "/forge/beacon-seo",
                  "/forge/harvester", "/forge/watchtower", "/forge/oracle", "/forge/oracle-harvester",
                  "/forge/architect", "/forge/mission-control", "/forge/deploy", "/forge/forge_shell",
                  "/forge/reverb/forge_shell", "/forge/warp/forge_shell", "@self", "@self/keys"):
            self.assertIn(e, have)


class Rubric(Base):
    LEGAL = {"verdict": "pass", "notes": [], "mechanical_ok": True, "secrets_seen": False,
             "prod_paths": False, "tests_cover_clauses": True, "doctrine_touched": False}

    def verdict(self, **over):
        v = dict(self.LEGAL, **over)
        with open(os.path.join(self.root, "inbox", "v.json"), "w") as fh:
            json.dump(v, fh)
        return self.run_sh("run.sh", "--verdict", "inbox/v.json")

    def test_legal_pass_is_accepted(self):
        self.assertEqual(self.verdict().returncode, 0)

    def test_pass_cannot_override_a_failed_checksum(self):
        self.task(expect="0" * 64)
        r = self.verdict()
        self.assertEqual(r.returncode, 4)
        self.assertFalse(self.exists("work/r1-checksum.ok"))

    def test_pass_with_mechanical_false_is_not_a_pass(self):
        self.assertEqual(self.verdict(mechanical_ok=False).returncode, 4)

    def test_pass_with_any_note_is_not_a_pass(self):
        note = {"path": "a.py", "line": 3, "why": "also add caching", "spec_clause": "none"}
        self.assertEqual(self.verdict(notes=[note]).returncode, 4)

    def test_pass_with_a_danger_flag_is_not_a_pass(self):
        for flag in ("secrets_seen", "prod_paths", "doctrine_touched"):
            self.assertEqual(self.verdict(**{flag: True}).returncode, 4, flag)
        self.assertEqual(self.verdict(tests_cover_clauses=False).returncode, 4)

    def test_truthy_strings_do_not_count_as_booleans(self):
        self.assertEqual(self.verdict(mechanical_ok="true").returncode, 4)

    def test_revise_is_fail_and_halt_is_HALT(self):
        self.assertEqual(self.verdict(verdict="revise").returncode, 4)
        r = self.verdict(verdict="halt")
        self.assertEqual(r.returncode, 10)
        self.assertIn("HALT", r.stdout)
        self.assertFalse(self.exists("work/r1-checksum.ok"))

    def test_verdict_file_must_be_in_inbox(self):
        with open(os.path.join(self.tmp, "v.json"), "w") as fh:
            json.dump(self.LEGAL, fh)
        r = self.run_sh("run.sh", "--verdict", os.path.join(self.tmp, "v.json"))
        self.assertEqual(r.returncode, 2)

    def test_rubric_schema_lists_every_field(self):
        rub = json.loads(read(os.path.join(HERE, "rubric.json")))
        self.assertEqual(rub["properties"]["verdict"]["enum"], ["pass", "revise", "halt"])
        self.assertEqual(set(rub["properties"]["notes"]["items"]["required"]),
                         {"path", "line", "why", "spec_clause"})
        self.assertEqual(rub["x-pass-requires"], {"mechanical_ok": True, "secrets_seen": False,
                         "prod_paths": False, "doctrine_touched": False,
                         "tests_cover_clauses": True, "notes_max": 0})


class Hygiene(Base):
    def test_no_forbidden_command_is_ever_invoked(self):
        self.run_sh("run.sh")
        self.run_sh("run.sh")
        self.run_sh("run.sh", "--halt-test")
        self.assertFalse(os.path.exists(self.called), read(self.called) if os.path.exists(self.called) else "")

    def test_run_sh_source_has_no_network_or_process_calls(self):
        src = read(os.path.join(HERE, "run.sh"))
        for word in ("socket", "urllib", "http", "requests", "subprocess", "os.system", "popen",
                     "curl", "docker", "systemctl", "ssh ", "os.environ", "getenv", "secrets.env", "resend"):
            self.assertNotIn(word, src.lower().replace("no docker", "").replace("no network", ""), word)

    def test_writes_stay_inside_the_four_directories(self):
        changed = set()
        for expect, args in ((GOOD, []), (GOOD, ["--halt-test"]), ("0" * 64, [])):
            self.task(expect=expect)
            before = self.tree()
            self.run_sh("run.sh", *args)
            after = self.tree()
            changed |= {k.split(os.sep)[0] for k in after if before.get(k) != after[k]}
            changed |= {k.split(os.sep)[0] for k in before if k not in after}
        self.assertTrue(changed and changed <= ALLOWED_TOP, changed)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["architect-run", "shims"])

    def test_log_block_fits_one_screen_and_holds_no_secret(self):
        self.run_sh("run.sh")
        r = self.run_sh("run.sh", "--halt-test")
        blocks = [b for b in self.log().split("--- ") if b.strip()]
        self.assertEqual(len(blocks), 2)
        for b in blocks:
            self.assertLessEqual(len(b.splitlines()), 24)
            self.assertTrue(all(len(l) <= 120 for l in b.splitlines()))
        everything = self.log() + r.stdout + read(os.path.join(self.root, "outbox", "notify.txt"))
        for secret in list(CANARY_ENV.values()) + ["SIGNAL_NUMBER", "API_KEY", "TOKEN"]:
            self.assertNotIn(secret, everything)

    def test_notify_only_writes_the_outbox_file(self):
        self.run_sh("run.sh")
        self.assertEqual(os.listdir(os.path.join(self.root, "outbox")), ["notify.txt"])

    def test_modes_and_gitignore(self):
        for name in ("run.sh", "preflight.sh", "limits.env", "denylist.txt", "rubric.json"):
            mode = stat.S_IMODE(os.stat(os.path.join(HERE, name)).st_mode)
            self.assertEqual(mode & 0o022, 0, "%s is %o" % (name, mode))
        gi = os.path.join(HERE, ".gitignore")
        self.assertTrue(os.path.exists(gi), ".gitignore is missing: it was probably lost when the files were copied")
        ignored = {l.strip() for l in read(gi).splitlines()}
        for p in ("keys/", "budget/", "work/", "outbox/", "log/", ".env"):
            self.assertIn(p, ignored)
        keys = os.path.join(HERE, "keys")       # absent in a fresh copy; present once keys are placed
        if os.path.isdir(keys):
            self.assertEqual(stat.S_IMODE(os.stat(keys).st_mode), 0o700, "keys/ must be mode 700")
            for name in os.listdir(keys):
                self.assertEqual(stat.S_IMODE(os.stat(os.path.join(keys, name)).st_mode), 0o600, name)

    def test_only_the_agreed_files_exist(self):
        have = set()
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".git", "work", "outbox", "budget", "log", "__pycache__",
                                                    "keys", "rulings")]
            have |= {os.path.relpath(os.path.join(base, f), HERE) for f in files}
        have = {f for f in have if not (f.startswith("inbox/") and f not in ("inbox/r1.yaml", "inbox/r2-example.yaml"))}
        self.assertEqual(have, {
            "preflight.sh", "run.sh", "limits.env", "denylist.txt", "rubric.json", ".gitignore",
            "r2.sh", "r2.py", "r2_child.py", "rulings.schema.json",
            "inbox/r1.yaml", "inbox/r2-example.yaml",
            "setup/1-check-march-repo.sh", "setup/2-first-commit.sh", "setup/4-place-keys.sh",
            "setup/5a-make-user.sh", "setup/5b-prove-user.sh", "setup/6-prove-key.sh", "setup/clear-hold.sh",
            "setup/7-prove-anthropic-key.sh", "setup/7a-place-anthropic-key.sh",
            "cage/cage.sh", "cage/prove.sh", "cage/probe.py", "cage/inspect_check.py",
            "tests/test_v01.py", "tests/test_v02.py", "tests/test_v04_cage.py", "tests/test_v05_key.py",
            "tests/fixtures/ok.json", "tests/fixtures/dollar.json",
            "tests/fixtures/overspend.json", "tests/fixtures/no_usage.json", "tests/fixtures/bad_content.json",
            "tests/fixtures/ticks_high.json", "tests/fixtures/ticks_low.json", "tests/fixtures/ticks_only.json"})

    def test_no_units_timers_or_compose(self):
        for name in ("run.sh", "preflight.sh"):
            src = read(os.path.join(HERE, name))
            for word in ("docker compose", ".timer", "systemctl enable", "systemctl start", "cloudflared", "crontab"):
                self.assertNotIn(word, src)


class Preflight(Base):
    def setUp(self):
        super().setUp()
        self.shim("docker", 'echo "docker $*" >> "%s"; exit 0' % self.called)
        self.shim("systemctl", "echo inactive")

    def test_passes_on_the_no_model_path(self):
        r = self.run_sh("preflight.sh")
        self.assertEqual(r.returncode, 0, r.stdout)
        for word in ("uid", "groups", "docker info", "beacon-seo", "denylist"):
            self.assertIn(word, r.stdout)
        for secret in CANARY_ENV.values():
            self.assertNotIn(secret, r.stdout)

    def test_changes_nothing(self):
        before = self.tree()
        self.run_sh("preflight.sh")
        self.assertEqual(before, self.tree())

    def test_only_inactive_beacon_seo_passes(self):
        for state in ("activating", "active", "failed", "unknown", "deactivating"):
            self.shim("systemctl", "echo " + state)
            self.assertEqual(self.run_sh("preflight.sh").returncode, 1, state)
        self.shim("systemctl", "exit 4")      # prints nothing at all
        self.assertEqual(self.run_sh("preflight.sh").returncode, 1)

    def ready_for_model(self, uid="1500", groups="architect"):
        # The cap lines are left exactly as shipped: empty, with IS_REAL=no. Writing a
        # number in here would be the pretend cap this check exists to refuse.
        os.makedirs(os.path.join(self.root, "keys"), mode=0o700)
        write(os.path.join(self.root, "keys", "xai"), "xai-TESTKEY-not-real-0000000000\n")
        os.chmod(os.path.join(self.root, "keys", "xai"), 0o600)
        self.shim("id", 'if [ "${2:-}" = architect ]; then case "$1" in -u) echo %s;; -Gn) echo "%s";; esac; '
                        'else exec /usr/bin/id "$@"; fi' % (uid, groups))

    def test_model_path_can_pass(self):
        self.ready_for_model()
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("TESTKEY", r.stdout)
        self.assertIn("console cap: none; in-code xAI halt is 90% of $15", r.stdout)

    def model_fails(self, needle):
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(needle, r.stdout)

    def test_a_number_on_a_cap_line_with_no_real_cap_fails(self):
        self.ready_for_model()
        self.edit("limits.env", "CONSOLE_CAP_XAI_USD=\n", "CONSOLE_CAP_XAI_USD=15\n")
        self.model_fails("holds a number while CONSOLE_CAP_XAI_IS_REAL=no")

    def test_xai_month_above_15_with_no_real_cap_fails(self):
        self.ready_for_model()
        self.edit("limits.env", "XAI_MONTH_USD=15", "XAI_MONTH_USD=16")
        self.model_fails("no higher than 15")

    def test_anthropic_cap_needs_a_real_flag_and_a_zero_budget(self):
        self.ready_for_model()
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("console cap: $40 on the Anthropic console; in-code Anthropic budget is $0 (no builder)", r.stdout)
        self.edit("limits.env", "ANTHROPIC_MONTH_USD=0", "ANTHROPIC_MONTH_USD=1")
        self.model_fails("ANTHROPIC_MONTH_USD must be 0")
        self.edit("limits.env", "ANTHROPIC_MONTH_USD=1", "ANTHROPIC_MONTH_USD=0")
        self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_IS_REAL=yes", "CONSOLE_CAP_ANTHROPIC_IS_REAL=no")
        self.model_fails("holds a number while CONSOLE_CAP_ANTHROPIC_IS_REAL=no")
        self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_USD=40\n", "CONSOLE_CAP_ANTHROPIC_USD=\n")
        self.assertEqual(self.run_sh("preflight.sh", "--model").returncode, 0)     # no cap claimed, no key: fine
        self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_IS_REAL=no", "CONSOLE_CAP_ANTHROPIC_IS_REAL=yes")
        self.model_fails("needs a number above 0")
        self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_IS_REAL=yes", "CONSOLE_CAP_ANTHROPIC_IS_REAL=maybe")
        self.model_fails("CONSOLE_CAP_ANTHROPIC_IS_REAL must be yes or no")

    def test_is_real_must_be_yes_or_no(self):
        self.ready_for_model()
        self.edit("limits.env", "CONSOLE_CAP_XAI_IS_REAL=no", "CONSOLE_CAP_XAI_IS_REAL=maybe")
        self.model_fails("must be yes or no")
        self.edit("limits.env", "CONSOLE_CAP_XAI_IS_REAL=maybe\n", "")
        self.model_fails("must be yes or no")

    def test_a_real_cap_passes_only_when_the_in_code_limit_fits_under_it(self):
        self.ready_for_model()
        self.edit("limits.env", "CONSOLE_CAP_XAI_IS_REAL=no", "CONSOLE_CAP_XAI_IS_REAL=yes")
        self.model_fails("needs a number")                       # yes, but the line is empty
        self.edit("limits.env", "CONSOLE_CAP_XAI_USD=\n", "CONSOLE_CAP_XAI_USD=15\n")
        self.assertEqual(self.run_sh("preflight.sh", "--model").returncode, 0)
        self.edit("limits.env", "CONSOLE_CAP_XAI_USD=15\n", "CONSOLE_CAP_XAI_USD=9.5\n")
        self.model_fails("must not be higher than the xAI console cap")   # 15 > 9.5, compared as numbers

    def test_a_parked_anthropic_key_is_allowed_only_in_the_ruled_state(self):
        self.ready_for_model()
        kf = os.path.join(self.root, "keys", "anthropic")
        write(kf, "sk-ant-TESTKEY-not-real-00000000\n")
        os.chmod(kf, 0o600)
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("parked, mode 600, yours (R2 does not use it)", r.stdout)
        self.assertNotIn("TESTKEY", r.stdout)
        os.chmod(kf, 0o640)
        self.model_fails("keys/anthropic must be a plain file, mode 600, owned by you")
        os.chmod(kf, 0o600)
        self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_IS_REAL=yes", "CONSOLE_CAP_ANTHROPIC_IS_REAL=no")
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 1)
        self.assertIn("keys/anthropic exists while CONSOLE_CAP_ANTHROPIC_IS_REAL=no", r.stdout)
        self.assertNotIn("TESTKEY", r.stdout)

    def test_a_symlinked_anthropic_key_is_refused(self):
        self.ready_for_model()
        os.symlink(os.path.join(self.root, "keys", "xai"), os.path.join(self.root, "keys", "anthropic"))
        self.model_fails("keys/anthropic must be a plain file")

    def test_no_model_path_ignores_all_of_this(self):
        self.edit("limits.env", "CONSOLE_CAP_XAI_IS_REAL=no", "CONSOLE_CAP_XAI_IS_REAL=maybe")
        self.assertEqual(self.run_sh("preflight.sh").returncode, 0)

    def test_model_path_needs_the_architect_user(self):
        self.ready_for_model()
        self.shim("id", 'if [ "${2:-}" = architect ]; then exit 1; else exec /usr/bin/id "$@"; fi')
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not exist", r.stdout)

    def test_model_path_needs_the_key_file_at_mode_600(self):
        self.ready_for_model()
        os.chmod(os.path.join(self.root, "keys", "xai"), 0o644)
        self.assertEqual(self.run_sh("preflight.sh", "--model").returncode, 1)

    def test_docker_down_is_a_note_without_model_and_a_fail_with(self):
        self.shim("docker", "exit 1")
        self.assertEqual(self.run_sh("preflight.sh").returncode, 0)
        self.assertEqual(self.run_sh("preflight.sh", "--model").returncode, 1)

    def test_blank_cap_lines_alone_never_fail_the_model_path(self):
        self.ready_for_model()
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("CONSOLE_CAP", r.stdout)

    def test_model_flag_refuses_uid_1000_and_docker_group(self):
        self.ready_for_model(uid="1000", groups="jb sudo docker")
        r = self.run_sh("preflight.sh", "--model")
        self.assertEqual(r.returncode, 1)
        self.assertIn("uid 1000", r.stdout)
        self.assertIn("docker group", r.stdout)
        self.assertIn("sudo group", r.stdout)
        self.assertNotIn("CONSOLE_CAP", r.stdout)

    def test_fails_when_denylist_missing_or_world_writable(self):
        p = os.path.join(self.root, "denylist.txt")
        os.chmod(p, 0o666)
        self.assertEqual(self.run_sh("preflight.sh").returncode, 1)
        os.remove(p)
        self.assertEqual(self.run_sh("preflight.sh").returncode, 1)

    def test_fails_when_a_script_is_world_writable(self):
        os.chmod(os.path.join(self.root, "run.sh"), 0o777)
        self.assertEqual(self.run_sh("preflight.sh").returncode, 1)

    @unittest.skipUnless(os.path.isdir("/forge"), "/forge does not exist on this machine")
    def test_refuses_when_run_from_forge(self):
        self.assertEqual(self.run_sh("preflight.sh", cwd="/forge").returncode, 1)
        self.assertEqual(self.run_sh("run.sh", cwd="/forge").returncode, 5)


if __name__ == "__main__":
    unittest.main(verbosity=1)
