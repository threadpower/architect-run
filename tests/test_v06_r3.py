"""v0.6 R3: one caged run. Everything here is a dry run: no socket, no real container, $0.

The fake `docker` below stands in for the cage: it records the flags it was given and
runs the test module in the run directory, so a good fixture passes and a wrong one
fails. That is a test double for fixture code written in this repo. r3.py itself never
loads or runs the file it writes.
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import Base, HERE, read, write  # noqa: E402

KEY = "sk-ant-BUILDERKEY-not-real-00000000"
RUN = os.path.join("work", "r3-toy-FIXTURE")
FIX = os.path.join("budget", "ledger.r3.fixture.json")
REAL = os.path.join("budget", "ledger.json")
DOCKER = r'''case "$1" in
 version) exit 0;;
 image) echo "python:3.13-slim"; exit 0;;
 kill) exit 0;;
 run) echo "$@" >> "$SHIM_DOCKER_LOG"
      src="$(echo "$@" | sed -n 's/.*source=\([^,]*\),target.*/\1/p')"
      mod="${@: -1}"
      cd "$src" && exec python3 -B -m unittest "$mod";;
esac
exit 0'''


class R3Base(Base):
    def setUp(self):
        super().setUp()
        self.docker_log = os.path.join(self.tmp, "docker.log")
        self.shim("docker", DOCKER)
        self.test_sha = self.sha(os.path.join("inbox", "r3_toy_test.py"))

    def sha(self, rel):
        with open(os.path.join(self.root, rel), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def r3(self, fixture="r3_ok", live=False, task="inbox/r3-toy.yaml", **extra):
        env = dict(os.environ, PATH=self.shims + os.pathsep + os.environ["PATH"], SHIM_DOCKER_LOG=self.docker_log)
        env.pop("ARCHITECT_LIVE", None)
        env.update(extra)
        args = ["bash", os.path.join(self.root, "r3.sh"), task]
        if live:
            env["ARCHITECT_LIVE"] = "1"
        else:
            args += ["--fixture", os.path.join("tests", "fixtures", fixture + ".json")]
        return subprocess.run(args, cwd=self.root, env=env, capture_output=True, text=True, timeout=120)

    def exists(self, rel):
        return os.path.lexists(os.path.join(self.root, rel))

    def fix_month(self):
        return json.loads(read(os.path.join(self.root, FIX)))["months"][datetime.datetime.now().strftime("%Y-%m")]

    def wrote_nothing(self, r, code):
        self.assertIn(r.returncode, code if isinstance(code, tuple) else (code,), r.stdout + r.stderr)
        self.assertFalse(self.exists(RUN), "a run directory was created")
        self.assertFalse(self.exists(os.path.join("work", "r3-toy")))
        self.assertFalse(os.path.exists(self.docker_log), "the cage was started")
        self.assertFalse(self.exists(REAL), "the real ledger was touched")


class GoodRun(R3Base):
    def test_good_fixture_writes_one_file_and_passes_in_the_cage(self):
        r = self.r3()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, RUN))), ["r3_toy_test.py", "slug.py"])
        self.assertEqual(os.listdir(os.path.join(self.root, "work")), ["r3-toy-FIXTURE"])
        for name in ("inbox/r3_toy_test.py", RUN + "/r3_toy_test.py"):      # the contract, before and after
            self.assertEqual(self.sha(name), self.test_sha)
        self.assertEqual(os.stat(os.path.join(self.root, RUN)).st_mode & 0o777, 0o755)
        self.assertFalse(self.exists(REAL))
        m = self.fix_month()
        self.assertAlmostEqual(m["anthropic_usd"], (260 * 0.10 + 70 * 0.50) / 1e6, places=4)
        self.assertEqual(json.loads(read(os.path.join(self.root, FIX)))["holds"], [])
        report = [f for f in os.listdir(os.path.join(self.root, "outbox")) if f.endswith("-r3-toy-FIXTURE.md")]
        self.assertEqual(len(report), 1)
        text = read(os.path.join(self.root, "outbox", report[0]))
        for want in ("**PASS**", "FIXTURE", "claude-haiku-5-5", "max_tokens 1024", self.test_sha, "Never run on the host"):
            self.assertIn(want, text)

    def test_the_test_command_is_the_cage_with_its_own_flags_and_nothing_added(self):
        self.r3()
        ran = read(self.docker_log).strip().splitlines()
        self.assertEqual(len(ran), 1, "exactly one container")
        run_dir = os.path.join(self.root, RUN)
        flags = ("--rm", "--network none", "--ipc none", "--cgroupns private", "--cap-drop ALL",
                 "--security-opt no-new-privileges", "--user 65534:65534", "--pids-limit 256", "--memory 2g",
                 "--mount type=bind,source=%s,target=/work" % run_dir, "--workdir /work", "--entrypoint /usr/bin/env")
        rest = ran[0]
        for flag in flags:
            self.assertIn(flag, rest)
            rest = rest.replace(flag, "", 1)
        self.assertRegex(" ".join(rest.split()),
                         r"^run --name architect-r3-\S+ python:3\.13-slim -i PATH=/usr/local/bin:/usr/bin:/bin "
                         r"HOME=/work python3 -B -m unittest r3_toy_test$")
        cage = read(os.path.join(HERE, "r3_cage.sh"))
        self.assertIn('. "$ROOT/cage/cage.sh"', cage)
        self.assertIn('docker run "${CAGE_ARGS[@]}" "$IMAGE" "${CAGE_ENV[@]}" python3 -B -m unittest "$MOD"', cage)
        for word in ("-v ", "--volume", "--mount", "--network", "--env", "-e ", "--privileged", "docker.sock", "docker pull"):
            self.assertNotIn(word, cage.replace("no network", ""), word)

    def test_r3_never_loads_or_runs_the_file_on_the_host(self):
        src = read(os.path.join(HERE, "r3.py"))
        for word in ("importlib", "__import__", "exec(", "eval(", "compile(", "runpy", "os.system", "shell=True", "popen"):
            self.assertNotIn(word, src.lower(), word)
        self.assertEqual(src.count("subprocess.run("), 4,
                         "preflight, can-architect-read-the-child, the one child call, the cage; nothing else")
        self.assertIn('["sudo", "runuser", "-u", "architect", "--", "test", "-r", CHILD]', src)
        self.assertIn('subprocess.run(["bash", CAGE, run_dir, test_name[:-3], str(wall)]', src)
        self.assertNotIn("https://", src)
        self.assertNotIn("xai", src.lower())

    def test_the_test_file_is_never_put_in_the_request(self):
        src = read(os.path.join(HERE, "r3.py"))
        build = src[src.index("# ---------------------------------------------------------------- build the request"):
                    src.index("# ---------------------------------------------------------------- live only")]
        self.assertNotIn("test_", build)
        self.assertIn('"messages": [{"role": "user", "content": prose}]', build)
        self.assertNotIn('"tools":', src)

    def test_a_wrong_implementation_is_fail_with_no_second_call(self):
        r = self.r3("r3_wrong")
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("FAIL the tests did not pass inside the cage", r.stdout)
        self.assertIn("No second call", r.stdout)
        self.assertEqual(len(read(self.docker_log).strip().splitlines()), 1)
        report = [f for f in os.listdir(os.path.join(self.root, "outbox")) if f.endswith(".md")]
        self.assertIn("**FAIL**", read(os.path.join(self.root, "outbox", report[0])))

    def test_one_code_fence_around_the_object_is_tolerated(self):
        self.assertEqual(self.r3("r3_fenced").returncode, 0)

    def test_a_dry_run_can_be_repeated_only_after_its_ledger_is_removed(self):
        self.assertEqual(self.r3().returncode, 0)
        r = self.r3()                                        # one run fills the month
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("would pass the month's $2.00", r.stdout)
        os.remove(os.path.join(self.root, FIX))
        self.assertEqual(self.r3().returncode, 0)            # and clears only its own two files first


class WritesNothing(R3Base):
    def test_each_bad_reply_writes_nothing(self):
        cases = (("r3_two_files", 4, "a second file is refused"), ("r3_extra_key", 4, "a second file is refused"),
                 ("r3_test_path", 3, "names the test file"), ("r3_abs", 3, "absolute path"),
                 ("r3_dotdot", 3, "contains '..'"), ("r3_deny", 3, "on the denylist"),
                 ("r3_other_name", 3, "is not slug.py"), ("r3_long", 4, "over 40 lines"))
        for fixture, code, needle in cases:
            self.tearDown()
            self.setUp()
            r = self.r3(fixture)
            self.wrote_nothing(r, code)
            self.assertIn(needle, r.stdout, fixture)
            self.assertIn("Nothing written", r.stdout, fixture)

    def test_a_test_file_that_does_not_match_its_hash_stops_before_any_call(self):
        with open(os.path.join(self.root, "inbox", "r3_toy_test.py"), "a") as fh:
            fh.write("# one byte more\n")
        r = self.r3()
        self.wrote_nothing(r, 4)
        self.assertIn("does not match its expect_sha256", r.stdout)
        self.assertFalse(self.exists(FIX), "a hold was placed")

    def test_a_task_cannot_choose_the_model_or_add_tools_and_needs_its_lines(self):
        base = read(os.path.join(self.root, "inbox", "r3-toy.yaml"))
        for line in ("model: claude-opus-5-5", "tools: bash", "max_tokens: 9000", "host: example.com", "retries: 3"):
            write(os.path.join(self.root, "inbox", "r3-toy.yaml"), base + line + "\n")
            self.wrote_nothing(self.r3(), 2)
        for drop in ("expect_sha256:", "impl:", "test:", "prose:"):
            write(os.path.join(self.root, "inbox", "r3-toy.yaml"),
                  "\n".join(l for l in base.splitlines() if not l.startswith(drop)) + "\n")
            self.wrote_nothing(self.r3(), 2)
        for bad in ("impl: ../slug.py", "impl: /tmp/slug.py", "impl: r3_toy_test.py", "impl: .env", "impl: a/b.py"):
            write(os.path.join(self.root, "inbox", "r3-toy.yaml"), base.replace("impl: slug.py", bad))
            self.wrote_nothing(self.r3(), 2)

    def test_an_existing_live_run_directory_is_never_overwritten(self):
        os.makedirs(os.path.join(self.root, RUN, "something-else"))
        r = self.r3()
        self.assertEqual(r.returncode, 2)
        self.assertIn("already exists", r.stdout)


class Money(R3Base):
    def test_live_is_refused_before_a_hold_while_the_month_is_zero(self):
        self.edit("limits.env", "ANTHROPIC_MONTH_USD=2", "ANTHROPIC_MONTH_USD=0")
        r = self.r3(live=True)
        self.wrote_nothing(r, 2)
        self.assertIn("no builder call is authorized: ANTHROPIC_MONTH_USD is $0.00", r.stdout)
        self.assertIn("No hold placed, no call made", r.stdout)
        self.assertFalse(self.exists("budget"))
        self.assertFalse(os.path.exists(self.called), "sudo or another forbidden command was started")

    def test_no_usage_leaves_the_fixture_hold_and_blocks_nothing_real(self):
        r = self.r3("r3_no_usage")
        self.wrote_nothing(r, 10)
        self.assertIn("hold stays open", r.stdout)
        self.assertEqual(len(json.loads(read(os.path.join(self.root, FIX)))["holds"]), 1)
        self.assertEqual(self.run_sh("run.sh").returncode, 0)               # R1 still runs
        self.assertFalse(self.exists(os.path.join("budget", "ledger.fixture.json")))   # R2's dry-run ledger untouched
        r = self.r3()
        self.assertEqual(r.returncode, 10)
        self.assertIn("unreconciled spending hold", r.stdout)

    def test_a_cost_over_the_task_cap_is_halt_and_is_recorded(self):
        r = self.r3("r3_overspend")
        self.wrote_nothing(r, 10)
        self.assertIn("over this task's $2.00. Recorded", r.stdout)
        self.assertAlmostEqual(self.fix_month()["anthropic_usd"], 2.4, places=4)

    def test_cache_tokens_are_counted_and_a_dollar_figure_wins_when_it_is_greater(self):
        self.assertEqual(self.r3("r3_cache").returncode, 0)
        self.assertAlmostEqual(self.fix_month()["anthropic_usd"], (100 * 0.10 + 100 * 0.50 + 1e6 * 0.20 + 1e6 * 0.01) / 1e6, places=4)
        self.tearDown()
        self.setUp()
        self.assertEqual(self.r3("r3_dollars").returncode, 0)
        self.assertAlmostEqual(self.fix_month()["anthropic_usd"], 0.5, places=4)

    def test_no_percentage_line_for_anthropic_and_the_cap_is_at_most_2(self):
        src = read(os.path.join(HERE, "r3.py"))
        self.assertIn("if a_spent + r3max > a_month:", src)
        self.edit("limits.env", "R3_TASK_USD=2", "R3_TASK_USD=3")
        self.wrote_nothing(self.r3(), 2)

    def test_shipped_numbers_are_the_ruled_ones(self):
        text = read(os.path.join(HERE, "limits.env"))
        for line in ("ANTHROPIC_MONTH_USD=2", "R3_TASK_USD=2", "ANTHROPIC_IN_PER_M=0.10", "ANTHROPIC_OUT_PER_M=0.50",
                     "CONSOLE_CAP_ANTHROPIC_USD=40", "XAI_MONTH_USD=15", "CONSOLE_CAP_XAI_IS_REAL=no"):
            self.assertIn("\n" + line + "\n", text)
        src = read(os.path.join(HERE, "r3.py"))
        self.assertIn('BUILDER_MODEL = "claude-haiku-5-5"', src)
        self.assertIn("MAX_TOKENS = 1024", src)
        self.assertIn("MAX_LINES = 40", src)


class LivePathWithoutANetwork(R3Base):
    """`sudo` is a fake that answers with a fixture body. This proves how the key
    travels at the shipped month of 2. It opens no socket."""

    def setUp(self):
        super().setUp()
        self.assertIn("\nANTHROPIC_MONTH_USD=2\n", read(os.path.join(self.root, "limits.env")))
        os.makedirs(os.path.join(self.root, "keys"), mode=0o700)
        for name, value in (("anthropic", KEY), ("xai", "xai-TESTKEY-not-real-0000000000")):
            write(os.path.join(self.root, "keys", name), value + "\n")
            os.chmod(os.path.join(self.root, "keys", name), 0o600)
        self.shim("systemctl", "echo inactive")
        self.shim("id", 'if [ "${2:-}" = architect ]; then case "$1" in -u) echo 1500;; -Gn) echo architect;; esac; '
                        'else exec /usr/bin/id "$@"; fi')
        self.argv = os.path.join(self.tmp, "sudo.argv")
        self.stdin = os.path.join(self.tmp, "sudo.stdin")
        body = read(os.path.join(HERE, "tests", "fixtures", "r3_ok.json"))
        # `sudo ... test -r FILE` answers for architect; anything else is the one call, recorded and answered.
        self.shim("sudo", 'for a; do last="$a"; done\n'
                          'if [ "$5" = test ]; then exit ${SHIM_READABLE:-0}; fi\n'
                          'echo "$@" > "%s"\ncat > "%s"\n[ -n "${SHIM_CRASH:-}" ] && { echo "python3: can\'t open file: Permission denied" >&2; exit 2; }\n'
                          'cat <<\'J\'\n{"ok": true, "status": 200, "error": null, "body": %s}\nJ'
                  % (self.argv, self.stdin, body))

    def test_key_goes_on_stdin_only_and_appears_nowhere_else(self):
        r = self.r3(live=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(read(self.argv).strip(), "runuser -u architect -- env -i PATH=/usr/bin:/bin python3 %s --live"
                         % os.path.join(self.root, "r3_child.py"))
        packet = json.loads(read(self.stdin))
        self.assertEqual(packet["key"], KEY)
        self.assertEqual(set(packet["request"]), {"model", "max_tokens", "system", "messages"})
        self.assertEqual((packet["request"]["model"], packet["request"]["max_tokens"]), ("claude-haiku-5-5", 1024))
        self.assertNotIn(KEY, json.dumps(packet["request"]))
        self.assertNotIn("assertEqual", json.dumps(packet["request"]))        # nothing from the test file
        self.assertNotIn("xai-TESTKEY", read(self.stdin))                      # and never the xAI key
        seen = r.stdout + r.stderr
        for top in ("log", "outbox", "work", "budget"):          # everything a run can write
            for base, _d, files in os.walk(os.path.join(self.root, top)):
                for f in files:
                    with open(os.path.join(base, f), errors="replace") as fh:
                        seen += fh.read()
        self.assertNotIn(KEY, seen)
        self.assertNotIn("BUILDERKEY", seen)
        self.assertTrue(self.exists(os.path.join("work", "r3-toy", "slug.py")))
        self.assertEqual(json.loads(read(os.path.join(self.root, REAL)))["holds"], [])

    def test_an_unreadable_child_is_refused_before_any_hold(self):
        r = self.r3(live=True, SHIM_READABLE="1")
        self.assertEqual(r.returncode, 5, r.stdout)
        self.assertIn("user architect cannot read r3_child.py", r.stdout)
        self.assertIn("No hold placed, no call made", r.stdout)
        self.assertFalse(self.exists("budget"), "a hold was placed")
        self.assertFalse(os.path.exists(self.argv), "the call was started")
        os.chmod(os.path.join(self.root, "r3_child.py"), 0o600)          # and preflight says so by itself
        r = self.r3(live=True)
        self.assertEqual(r.returncode, 5, r.stdout)
        self.assertIn("r3_child.py must be mode 644", r.stdout)
        self.assertFalse(self.exists("budget"))

    def test_a_child_that_dies_leaves_its_reason_in_the_log_and_the_hold_open(self):
        r = self.r3(live=True, SHIM_CRASH="1")
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("child said: python3: can't open file: Permission denied", r.stdout)
        self.assertNotIn(KEY, r.stdout + read(os.path.join(self.root, "log", "run.log")))
        self.assertEqual(len(json.loads(read(os.path.join(self.root, REAL)))["holds"]), 1)

    def test_a_second_live_run_halts_because_one_hold_fills_the_month(self):
        self.assertEqual(self.r3(live=True).returncode, 0)
        os.rename(os.path.join(self.root, "work", "r3-toy"), os.path.join(self.root, "work", "moved"))
        r = self.r3(live=True)
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("would pass the month's $2.00", r.stdout)


class Child(R3Base):
    CHILD = os.path.join(HERE, "r3_child.py")

    def child(self, args, packet, env=None):
        return subprocess.run(["env", "-i", "PATH=/usr/bin:/bin"] + ["%s=%s" % kv for kv in (env or {}).items()]
                              + ["python3", self.CHILD] + args, input=json.dumps(packet),
                              capture_output=True, text=True, timeout=30)

    REQ = {"model": "claude-haiku-5-5", "max_tokens": 1024, "system": "s", "messages": []}

    def test_one_host_one_path_and_no_other_tool(self):
        src = read(self.CHILD)
        self.assertIn('HOST = "api.anthropic.com"', src)
        self.assertIn('URL = "https://" + HOST + "/v1/messages"', src)
        self.assertEqual(src.count("https://"), 1)
        for word in ("api.x.ai", "subprocess", "os.system", "Bearer", "chat/completions", "xai"):
            self.assertNotIn(word, src, word)
        self.assertIn('"x-api-key": key', src)
        self.assertIn('groups & {"docker", "sudo", "adm"}', src)
        self.assertIn("uid == 0 or uid == 1000 or uid == owner", src)

    def test_live_is_refused_for_this_user_before_any_network(self):
        r = self.child(["--live"], {"key": KEY, "request": self.REQ})      # run here as the owner, or root
        res = json.loads(r.stdout)
        self.assertFalse(res["ok"])
        self.assertIn("identity refused", res["error"])
        self.assertNotIn(KEY, r.stdout + r.stderr)

    def test_a_dirty_environment_tools_or_a_key_on_a_fixture_run_are_refused(self):
        fx = os.path.join(HERE, "tests", "fixtures", "r3_ok.json")
        self.assertFalse(json.loads(self.child(["--fixture", fx], {"request": self.REQ},
                                               env={"ANTHROPIC_API_KEY": "sk-ant-CANARY"}).stdout)["ok"])
        self.assertFalse(json.loads(self.child(["--fixture", fx], {"request": dict(self.REQ, tools=[])}).stdout)["ok"])
        self.assertFalse(json.loads(self.child(["--fixture", fx], {"key": KEY, "request": self.REQ}).stdout)["ok"])
        self.assertTrue(json.loads(self.child(["--fixture", fx], {"request": self.REQ}).stdout)["ok"])


if __name__ == "__main__":
    import unittest
    unittest.main()
