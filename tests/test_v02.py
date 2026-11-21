#!/usr/bin/env python3
"""architect-run v0.2 acceptance tests: the R2 spec round.

Run:  python3 tests/test_v02.py
Standard library only. No socket is ever opened: every run here uses a fixture
response, and the one live-path test replaces sudo with a recorder that never
starts the child. Each test names the line of Grok's round-3 fail list it answers.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_v01 as v1  # noqa: E402  (Base, helpers; its own tests are not re-run from here)
import unittest  # noqa: E402

HERE = v1.HERE
read, write = v1.read, v1.write
SPEC = "# Hopper H1 (test spec)\n\n1. The widget stores ideas.\n2. Votes decide promotion.\nMARKER-SPEC-TEXT\n"
SPEC_SHA = hashlib.sha256(SPEC.encode()).hexdigest()
KEY_CANARY = "xai-CANARY-KEYFILE-000000000000"
OK_COST = (15000 * 2 + 5000 * 0.5 + (3000 + 1000) * 6) / 1e6   # ok.json usage at the limits.env prices


class R2Base(v1.Base):
    def setUp(self):
        super().setUp()
        write(os.path.join(self.root, "inbox", "spec.md"), SPEC)
        self.r2task()

    def r2task(self, expect=SPEC_SHA, extra=""):
        body = "id: r2-test\nkind: r2\nspec: inbox/spec.md\n"
        if expect is not None:
            body += "expect_sha256: %s\n" % expect
        write(os.path.join(self.root, "inbox", "r2.yaml"), body + extra)

    def r2(self, fixture="ok", live=False, task="inbox/r2.yaml"):
        env = dict(os.environ, **v1.CANARY_ENV)
        env["PATH"] = self.shims + os.pathsep + env["PATH"]
        env.pop("ARCHITECT_LIVE", None)
        args = ["bash", os.path.join(self.root, "r2.sh"), task]
        if live:
            env["ARCHITECT_LIVE"] = "1"
        elif fixture:
            args += ["--fixture", "tests/fixtures/%s.json" % fixture]
        return subprocess.run(args, cwd=self.root, env=env, capture_output=True, text=True, timeout=60)

    FIX = "budget/ledger.fixture.json"      # what a fixture run reads and writes
    REAL = "budget/ledger.json"             # what run.sh and a live call read and write

    def ledger(self, which=None):
        return json.loads(read(os.path.join(self.root, which or self.FIX)))

    def no_ledger(self):
        return not self.exists(self.FIX) and not self.exists(self.REAL)

    def month(self):
        return self.ledger()["months"][datetime.datetime.now().strftime("%Y-%m")]

    def seed(self, spent, xai=0.0, holds=()):
        os.makedirs(os.path.join(self.root, "budget"), exist_ok=True)
        month = datetime.datetime.now().strftime("%Y-%m")
        write(os.path.join(self.root, self.FIX), json.dumps(
            {"version": 1, "months": {month: {"spent_usd": spent, "xai_usd": xai}},
             "successes": {}, "holds": list(holds)}))

    def rulings(self):
        d = os.path.join(self.root, "rulings")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []


class SpecRound(R2Base):
    def test_fixture_round_writes_rulings_and_leaves_the_spec_alone(self):
        r = self.r2()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = self.rulings()
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], r"^\d{4}-\d\d-\d\d-r2-test-FIXTURE\.md$")
        self.assertIn("rulings/*-FIXTURE*", read(os.path.join(HERE, ".gitignore")).splitlines())
        text = read(os.path.join(self.root, "rulings", files[0]))
        for want in ("Votes decide promotion", "AMEND", SPEC_SHA, "Promotion needs three votes", "FIXTURE"):
            self.assertIn(want, text)
        self.assertIn("so no test can be written", text.replace("\\|", ""))
        self.assertEqual(read(os.path.join(self.root, "inbox", "spec.md")), SPEC)

    def test_rulings_go_to_rulings_not_to_an_ignored_directory(self):
        self.r2()
        self.assertEqual(self.rulings().__len__(), 1)
        self.assertEqual(os.listdir(os.path.join(self.root, "outbox")), ["notify.txt"])
        self.assertEqual(os.listdir(os.path.join(self.root, "log")), ["run.log"])
        ignored = {l.strip().rstrip("/") for l in read(os.path.join(HERE, ".gitignore")).splitlines()}
        self.assertNotIn("rulings", ignored)

    def test_a_second_round_never_overwrites_the_first(self):
        self.r2()
        self.r2()
        self.assertEqual(len(self.rulings()), 2)

    def test_no_expect_line_no_run(self):
        self.r2task(expect=None)
        r = self.r2()
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.rulings(), [])
        self.assertTrue(self.no_ledger())

    def test_expect_must_match_the_spec(self):
        self.r2task(expect="0" * 64)
        r = self.r2()
        self.assertEqual(r.returncode, 4)
        self.assertTrue(self.no_ledger(), "no hold may be placed")
        self.assertEqual(self.rulings(), [])

    def test_spec_must_live_in_inbox(self):
        write(os.path.join(self.tmp, "outside.md"), SPEC)
        self.r2task(extra="")
        write(os.path.join(self.root, "inbox", "r2.yaml"),
              "id: r2-test\nkind: r2\nspec: %s\nexpect_sha256: %s\n" % (os.path.join(self.tmp, "outside.md"), SPEC_SHA))
        self.assertEqual(self.r2().returncode, 2)

    def test_spec_changed_during_the_call_is_HALT_with_no_rulings(self):
        spec = os.path.join(self.root, "inbox", "spec.md")
        self.shim("env", 'echo "tampered" >> "%s"\nexec /usr/bin/env "$@"' % spec)
        r = self.r2()
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("spec file changed", r.stdout)
        self.assertEqual(self.rulings(), [])

    def test_a_task_cannot_choose_its_reviewer_or_host(self):
        for line in ("reviewer: claude\n", "model: grok-build-0.1\n", "host: evil.example\n"):
            self.r2task(extra=line)
            self.assertEqual(self.r2().returncode, 2, line)
        self.assertEqual(self.rulings(), [])

    def test_answer_that_breaks_the_schema_writes_no_rulings_but_is_paid_for(self):
        r = self.r2("bad_content")
        self.assertEqual(r.returncode, 4)
        self.assertEqual(self.rulings(), [])
        self.assertAlmostEqual(self.month()["spent_usd"], OK_COST, places=4)

    def test_r1_still_means_what_it_meant(self):
        self.assertEqual(self.run_sh("run.sh").returncode, 0)
        self.assertEqual(self.run_sh("run.sh", "inbox/r2.yaml").returncode, 2)
        self.assertEqual(self.r2(task="inbox/r1.yaml").returncode, 2)


class Money(R2Base):
    def test_ledger_moves_by_token_usage_times_the_prices(self):
        self.assertEqual(self.r2().returncode, 0)
        self.assertAlmostEqual(self.month()["spent_usd"], OK_COST, places=4)
        self.assertAlmostEqual(self.month()["xai_usd"], OK_COST, places=4)
        self.assertEqual(self.ledger()["holds"], [])
        self.assertIn("$%.4f" % OK_COST, self.log())

    def test_prices_are_read_from_limits_env(self):
        self.edit("limits.env", "XAI_OUT_PER_M=6", "XAI_OUT_PER_M=60")
        self.r2()
        self.assertAlmostEqual(self.month()["spent_usd"], (15000 * 2 + 5000 * 0.5 + 4000 * 60) / 1e6, places=4)

    def test_halt_at_ninety_percent_after_a_real_cost(self):
        self.seed(33.50)                                   # 33.50 + 2.00 hold = 35.50, under the $36 line
        r = self.r2("dollar")                              # fixture costs exactly $1.00
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertAlmostEqual(self.month()["spent_usd"], 34.50, places=4)
        before = self.rulings()
        r = self.r2("dollar")                              # 34.50 + 2.00 = 36.50, over the line
        self.assertEqual(r.returncode, 10)
        self.assertIn("HALT", r.stdout)
        self.assertEqual(self.rulings(), before)
        self.assertAlmostEqual(self.month()["spent_usd"], 34.50, places=4)

    def test_xai_monthly_ceiling_halts_on_its_own(self):
        self.seed(12.0, xai=12.0)                          # 12 + 2 = 14, over 90% of $15 = $13.50
        r = self.r2()
        self.assertEqual(r.returncode, 10)
        self.assertIn("xAI", r.stdout)

    def test_no_usage_leaves_the_hold_and_the_next_run_halts(self):
        r = self.r2("no_usage")
        self.assertEqual(r.returncode, 10)
        self.assertEqual(self.rulings(), [])
        holds = self.ledger()["holds"]
        self.assertEqual([(h["id"], h["usd"]) for h in holds], [("r2-test", 2.0)])
        stamp = os.stat(os.path.join(self.root, "work", "r2-test.request.json")).st_mtime_ns
        r = self.r2()                                      # a good fixture, but the hold is open
        self.assertEqual(r.returncode, 10)
        self.assertIn("hold", r.stdout)
        self.assertEqual(stamp, os.stat(os.path.join(self.root, "work", "r2-test.request.json")).st_mtime_ns)

    def test_a_fixture_run_never_touches_the_real_ledger(self):
        self.assertEqual(self.r2("no_usage").returncode, 10)       # opens a hold, in the fixture ledger
        self.assertEqual(len(self.ledger(self.FIX)["holds"]), 1)
        self.assertFalse(self.exists(self.REAL), "a dry run must not create budget/ledger.json")
        self.assertEqual(self.run_sh("run.sh").returncode, 0, "a fixture hold must not block R1")
        self.assertEqual(self.ledger(self.REAL).get("holds", []), [])

    def test_run_sh_only_reads_the_real_ledger(self):
        src = read(os.path.join(HERE, "run.sh"))
        self.assertIn('"ledger.json"', src)
        self.assertNotIn("ledger.fixture", src)

    def test_provider_cost_figure_wins_when_it_is_higher(self):
        self.assertEqual(self.r2("ticks_high").returncode, 0)
        self.assertAlmostEqual(self.month()["spent_usd"], 0.25, places=4)

    def test_token_formula_wins_when_the_provider_figure_is_lower(self):
        self.assertEqual(self.r2("ticks_low").returncode, 0)
        self.assertAlmostEqual(self.month()["spent_usd"], OK_COST, places=4)

    def test_provider_figure_alone_is_enough_to_reconcile(self):
        self.assertEqual(self.r2("ticks_only").returncode, 0)
        self.assertAlmostEqual(self.month()["spent_usd"], 0.50, places=4)
        self.assertEqual(self.ledger()["holds"], [])

    def test_one_task_cannot_be_allowed_more_than_two_dollars(self):
        self.assertIn("R2_TASK_USD=2\n", read(os.path.join(HERE, "limits.env")))
        self.edit("limits.env", "R2_TASK_USD=2", "R2_TASK_USD=9")      # above the $8 global task cap
        self.assertEqual(self.r2().returncode, 2)
        self.assertTrue(self.no_ledger())

    def test_worst_case_over_the_task_max_is_refused_before_the_call(self):
        self.edit("limits.env", "R2_MAX_OUTPUT_TOKENS=16000", "R2_MAX_OUTPUT_TOKENS=900000")   # $5.40 of output
        r = self.r2()
        self.assertEqual(r.returncode, 2)
        self.assertIn("worst-case", r.stdout)
        self.assertTrue(self.no_ledger())

    def test_actual_cost_over_the_task_max_is_HALT(self):
        r = self.r2("overspend")                           # fixture costs $3.00
        self.assertEqual(r.returncode, 10)
        self.assertAlmostEqual(self.month()["spent_usd"], 3.0, places=4)
        self.assertEqual(len(self.rulings()), 1, "what was paid for is still kept")


class Isolation(R2Base):
    def test_no_live_call_without_the_flag(self):
        r = self.r2(fixture=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ARCHITECT_LIVE=1", r.stdout)
        self.assertTrue(self.no_ledger())

    def test_request_holds_spec_and_rubric_and_no_key(self):
        self.r2()
        req = read(os.path.join(self.root, "work", "r2-test.request.json"))
        self.assertIn("MARKER-SPEC-TEXT", req)
        self.assertIn("x-pass-requires", req)
        self.assertIn('"model": "grok-4.7"', req)
        body = json.loads(req)
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertEqual(body["max_completion_tokens"], 16000)
        self.assertNotIn("max_tokens", body)
        for secret in list(v1.CANARY_ENV.values()) + [KEY_CANARY, "Bearer"]:
            self.assertNotIn(secret, req)

    def test_nothing_secret_reaches_the_log_or_the_rulings(self):
        r = self.r2()
        everything = r.stdout + r.stderr + self.log() + read(os.path.join(self.root, "rulings", self.rulings()[0]))
        for secret in list(v1.CANARY_ENV.values()) + ["SIGNAL_NUMBER", "API_KEY"]:
            self.assertNotIn(secret, everything)
        for block in [b for b in self.log().split("--- ") if b.strip()]:
            self.assertLessEqual(len(block.splitlines()), 24)

    def test_no_forbidden_command_on_a_fixture_run(self):
        self.r2()
        self.r2("no_usage")
        self.assertFalse(os.path.exists(self.called), read(self.called) if os.path.exists(self.called) else "")

    def live_ready(self):
        self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_USD=", "CONSOLE_CAP_ANTHROPIC_USD=40")
        self.edit("limits.env", "CONSOLE_CAP_XAI_USD=", "CONSOLE_CAP_XAI_USD=15")
        os.makedirs(os.path.join(self.root, "keys"), mode=0o700)
        write(os.path.join(self.root, "keys", "xai"), KEY_CANARY + "\n")
        os.chmod(os.path.join(self.root, "keys", "xai"), 0o600)
        self.shim("systemctl", "echo inactive")
        self.shim("docker", "exit 0")
        self.shim("id", 'if [ "${2:-}" = architect ]; then case "$1" in -u) echo 1500;; -Gn) echo architect;; esac; '
                        'else exec /usr/bin/id "$@"; fi')
        self.sudo_log = os.path.join(self.tmp, "sudo.txt")
        # Records how it was called and what it could see. Never starts the child, never reads stdin.
        self.shim("sudo", 'printf "%%s\\n" "$*" > "%s"\nenv >> "%s"\nexit 0' % (self.sudo_log, self.sudo_log))

    def test_live_call_is_handed_to_architect_through_runuser_and_env_i(self):
        self.live_ready()
        r = self.r2(live=True)
        self.assertEqual(r.returncode, 10, r.stdout)       # the recorder returns nothing, so the hold stays
        rec = read(self.sudo_log)
        self.assertEqual(rec.splitlines()[0], "runuser -u architect -- env -i PATH=/usr/bin:/bin python3 %s --live"
                         % os.path.join(self.root, "r2_child.py"))
        self.assertNotIn(KEY_CANARY, rec.splitlines()[0], "the key must never be on a command line")
        self.assertEqual(len(self.ledger(self.REAL)["holds"]), 1, "a live call holds in the real ledger")
        self.assertFalse(self.exists(self.FIX))
        self.assertEqual(self.rulings(), [])
        for text in (r.stdout, r.stderr, self.log(), read(os.path.join(self.root, "work", "r2-test.request.json"))):
            self.assertNotIn(KEY_CANARY, text)

    def test_live_call_is_refused_when_preflight_model_fails(self):
        self.live_ready()
        self.shim("id", 'if [ "${2:-}" = architect ]; then exit 1; else exec /usr/bin/id "$@"; fi')
        r = self.r2(live=True)
        self.assertEqual(r.returncode, 5, r.stdout)
        self.assertFalse(os.path.exists(self.sudo_log), "sudo must not be reached")
        self.assertTrue(self.no_ledger(), "no hold may be placed")

    def test_live_call_is_refused_while_beacon_seo_is_failed(self):
        self.live_ready()
        self.shim("systemctl", "echo failed")
        self.assertEqual(self.r2(live=True).returncode, 5)
        self.assertFalse(os.path.exists(self.sudo_log))

    def test_live_and_fixture_together_are_refused(self):
        env = dict(os.environ, ARCHITECT_LIVE="1")
        r = subprocess.run(["bash", os.path.join(self.root, "r2.sh"), "inbox/r2.yaml", "--fixture",
                            "tests/fixtures/ok.json"], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class Child(R2Base):
    CHILD = os.path.join(HERE, "r2_child.py")

    def child(self, argv, packet, env=None, guard_socket=False):
        code = "import runpy,sys\n"
        if guard_socket:
            code += ("import socket\n"
                     "def boom(*a, **k): raise SystemExit('SOCKET OPENED')\n"
                     "socket.socket = boom; socket.create_connection = boom\n")
        code += "sys.argv=%r\nrunpy.run_path(%r, run_name='__main__')\n" % (["r2_child.py"] + argv, self.CHILD)
        return subprocess.run(["/usr/bin/env", "-i", "PATH=/usr/bin:/bin"] + ["%s=%s" % kv for kv in (env or {}).items()]
                              + [sys.executable, "-c", code], input=json.dumps(packet),
                              capture_output=True, text=True, timeout=30)

    def test_live_refuses_the_operator_before_touching_the_network(self):
        # Whoever runs this suite owns the files (or is uid 1000, or root): never the architect user.
        r = self.child(["--live"], {"key": KEY_CANARY, "request": {}}, guard_socket=True)
        self.assertNotIn("SOCKET OPENED", r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("identity refused", out["error"])
        self.assertNotIn(KEY_CANARY, r.stdout + r.stderr)

    def test_fixture_mode_never_opens_a_socket(self):
        r = self.child(["--fixture", os.path.join(HERE, "tests", "fixtures", "ok.json")], {"request": {}},
                       guard_socket=True)
        self.assertNotIn("SOCKET OPENED", r.stdout + r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])

    def test_child_refuses_a_dirty_environment(self):
        r = self.child(["--fixture", os.path.join(HERE, "tests", "fixtures", "ok.json")], {"request": {}},
                       env={"ANTHROPIC_API_KEY": "sk-ant-CANARY"})
        out = json.loads(r.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("not clean", out["error"])
        self.assertNotIn("CANARY", r.stdout)

    def test_fixture_mode_refuses_a_key(self):
        r = self.child(["--fixture", os.path.join(HERE, "tests", "fixtures", "ok.json")],
                       {"key": KEY_CANARY, "request": {}})
        self.assertFalse(json.loads(r.stdout)["ok"])

    def test_only_one_host_and_no_other_tools_in_the_source(self):
        child, orch = read(self.CHILD), read(os.path.join(HERE, "r2.py"))
        self.assertIn('HOST = "api.x.ai"', child)
        for text in (child, orch, read(os.path.join(HERE, "r2.sh"))):
            for word in ("anthropic.com", "openai.com", "openrouter", "http://", "os.system", "shell=True",
                         "ssh ", "claude", "curl", "wget", "/bin/sh", "bash -c"):
                self.assertNotIn(word, text, word)
            # "docker" may appear only as a group name to refuse, never as a command
            self.assertIsNone(re.search(r"docker\s+(info|run|exec|compose|ps|build)|[\[(]\s*\"docker\"\s*,", text))
        self.assertEqual(child.count("https://"), 1)
        self.assertNotIn("subprocess", child)
        self.assertNotIn("https://", orch)
        self.assertEqual(orch.count("subprocess.run("), 2, "one preflight call and one child call, nothing else")
        self.assertIn('REVIEWER_MODEL = "grok-4.7"', orch)


class Shipped(unittest.TestCase):
    def test_committed_console_caps_are_empty_until_jeremy_fills_them(self):
        text = read(os.path.join(HERE, "limits.env"))
        self.assertIn("CONSOLE_CAP_ANTHROPIC_USD=\n", text)
        self.assertIn("CONSOLE_CAP_XAI_USD=\n", text)

    def test_no_key_directory_is_shipped_and_keys_stay_ignored(self):
        self.assertIn("keys/", read(os.path.join(HERE, ".gitignore")).splitlines())

    def test_setup_scripts_do_not_print_keys_or_touch_live_apps(self):
        place = read(os.path.join(HERE, "setup", "4-place-keys.sh"))
        self.assertIn("read -rs", place)
        self.assertNotIn('echo "$k"', place)
        for name in os.listdir(os.path.join(HERE, "setup")):
            text = read(os.path.join(HERE, "setup", name))
            self.assertIsNone(re.search(r"docker\s+(info|run|exec|compose|ps|stop|rm|build)", text), name)
            for word in ("/forge/reverb", "/forge/forge-ads", "/forge/warp", "systemctl", "git push"):
                if word == "git push" and name == "2-first-commit.sh":
                    self.assertNotIn("\ngit push", text)      # it only prints the push command for Jeremy
                    continue
                self.assertNotIn(word, text, "%s in %s" % (word, name))

    def test_fixture_prices_match_the_ruled_rates(self):
        self.assertAlmostEqual(OK_COST, 0.0565, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=1)
