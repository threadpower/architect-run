"""v0.7 R3, the three-file shape. Dry runs only: no socket, no real container, $0.

The dry runs use a toy task (r3-trio) on purpose. The first Hopper slice (hopper-votes) has
no solution anywhere in this repository, and one test here keeps it that way.
"""
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import HERE, read, write  # noqa: E402
from test_v06_r3 import FIX, KEY, REAL, R3Base  # noqa: E402

TRIO = "inbox/r3-trio.yaml"
RUN = os.path.join("work", "r3-trio-FIXTURE")
GROK_HASH = "19f599c97c0d49c5ab8db6b417b390218f5777b8eb8490208208b87165ca97f6"


class ThreeBase(R3Base):
    def trio(self, fixture="r3t_ok", **kw):
        return self.r3(fixture, task=TRIO, **kw)

    def nothing(self, r, code):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertFalse(self.exists(RUN), "a run directory was created")
        self.assertFalse(os.path.exists(self.docker_log), "the cage was started")
        self.assertFalse(self.exists(REAL), "the real ledger was touched")


class GoodRun(ThreeBase):
    def test_three_files_are_written_and_pass_in_the_cage(self):
        r = self.trio()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, RUN))), ["add.py", "neg.py", "r3_trio_test.py", "twice.py"])
        self.assertEqual(os.listdir(os.path.join(self.root, "work")), ["r3-trio-FIXTURE"])
        self.assertIn("hold: $0.0050 placed before the call", r.stdout)
        self.assertIn("max_tokens 4096", r.stdout)
        self.assertEqual(len(read(self.docker_log).strip().splitlines()), 1, "exactly one container")
        self.assertIn("python3 -B -m unittest r3_trio_test", read(self.docker_log))
        report = [f for f in os.listdir(os.path.join(self.root, "outbox")) if f.endswith("-r3-trio-FIXTURE.md")]
        text = read(os.path.join(self.root, "outbox", report[0]))
        for want in ("**PASS**", "max_tokens 4096", "## add.py", "## neg.py", "## twice.py", "FIXTURE"):
            self.assertIn(want, text)
        self.assertEqual(json.loads(read(os.path.join(self.root, FIX)))["holds"], [])

    def test_wrong_code_is_fail_in_the_cage_with_no_second_call(self):
        r = self.trio("r3t_wrong")
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("FAIL the tests did not pass inside the cage", r.stdout)
        self.assertEqual(len(read(self.docker_log).strip().splitlines()), 1)

    def test_the_one_file_shape_is_untouched(self):
        r = self.r3("r3_ok")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("max_tokens 1024", r.stdout)
        self.assertIn("hold: $2.00 placed", r.stdout)             # R3Base pins the one-file hold at 2
        src = read(os.path.join(HERE, "r3.py"))
        for want in ("MAX_TOKENS = 1024", "MAX_LINES = 40", "THREE_MAX_TOKENS = 4096", "THREE_TOTAL_LINES = 120",
                     "THREE_FILE_LINES = 80", "THREE_HOLD_CEILING = 0.005",
                     "max_tokens = THREE_MAX_TOKENS if three else MAX_TOKENS"):
            self.assertIn(want, src)


class WritesNothing(ThreeBase):
    def test_each_bad_reply_writes_nothing_and_is_kept_as_evidence(self):
        cases = (("r3t_missing", 4, "exactly these three keys"), ("r3t_extra", 3, "not one of the three"),
                 ("r3t_wrapped", 3, "not one of the three"), ("r3t_array", 4, "exactly one JSON object"),
                 ("r3t_pathshape", 3, "not one of the three"), ("r3t_empty", 4, "a file is empty"),
                 ("r3t_not_text", 4, "one string holding the whole file"),
                 ("r3t_long_file", 4, "one is over 80"), ("r3t_long_total", 4, "over 120 lines in all"),
                 ("r3t_test_key", 3, "names the test file"), ("r3t_dotdot", 3, "contains '..'"),
                 ("r3t_abs", 3, "absolute path"), ("r3t_deny", 3, "on the denylist"))
        for fixture, code, needle in cases:
            self.tearDown()
            self.setUp()
            r = self.trio(fixture)
            self.nothing(r, code)
            self.assertIn(needle, r.stdout, fixture)
            self.assertIn("Nothing written", r.stdout, fixture)
            kept = [f for f in os.listdir(os.path.join(self.root, "outbox")) if "REJECTED" in f]
            self.assertEqual(len(kept), 1, fixture)

    def test_impl_must_be_one_name_or_exactly_three_different_ones(self):
        base = read(os.path.join(self.root, TRIO))
        for bad in ("impl: add.py neg.py", "impl: add.py neg.py twice.py more.py", "impl: add.py add.py twice.py",
                    "impl: add.py ../neg.py twice.py", "impl: add.py r3_trio_test.py twice.py", "impl: add.py neg.py .env"):
            write(os.path.join(self.root, TRIO), base.replace("impl: add.py neg.py twice.py", bad))
            self.nothing(self.trio(), 2)
            self.assertFalse(self.exists(FIX), "a hold was placed")


class Money(ThreeBase):
    def test_the_hold_is_capped_at_half_a_cent_and_must_cover_the_worst_case(self):
        self.limit("R3_HOLD_THREE_USD", "0.006")
        r = self.trio()
        self.nothing(r, 2)
        self.assertIn("R3_HOLD_THREE_USD must be above 0 and no higher than 0.005", r.stdout)
        self.limit("R3_HOLD_THREE_USD", "0.001")                     # 4096 tokens out cost about $0.002
        r = self.trio()
        self.nothing(r, 2)
        self.assertIn("worst-case cost", r.stdout)
        self.assertIn("No hold placed", r.stdout)
        self.assertFalse(self.exists(FIX))

    def test_shipped_numbers_for_this_shape(self):
        text = read(os.path.join(HERE, "limits.env"))
        for line in ("R3_HOLD_THREE_USD=0.005", "ANTHROPIC_MONTH_USD=2", "R3_TASK_USD=2"):
            self.assertIn("\n" + line + "\n", text)

    def test_one_dry_run_fills_its_play_month(self):
        self.assertEqual(self.trio().returncode, 0)
        r = self.trio()
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("would pass the month's $0.0050", r.stdout)


class LiveShapeWithoutANetwork(ThreeBase):
    """`sudo` is a fake that records what the child would be handed and answers with a fixture body."""

    def setUp(self):
        super().setUp()
        self.limit("ANTHROPIC_MONTH_USD", "2")
        os.makedirs(os.path.join(self.root, "keys"), mode=0o700)
        for name, value in (("anthropic", KEY), ("xai", "xai-TESTKEY-not-real-0000000000")):
            write(os.path.join(self.root, "keys", name), value + "\n")
            os.chmod(os.path.join(self.root, "keys", name), 0o600)
        self.shim("systemctl", "echo inactive")
        self.shim("id", 'if [ "${2:-}" = architect ]; then case "$1" in -u) echo 1500;; -Gn) echo architect;; esac; '
                        'else exec /usr/bin/id "$@"; fi')
        self.stdin = os.path.join(self.tmp, "sudo.stdin")
        body = read(os.path.join(HERE, "tests", "fixtures", "r3t_ok.json"))
        self.shim("sudo", 'if [ "$5" = test ]; then exit 0; fi\ncat > "%s"\n'
                          'cat <<\'J\'\n{"ok": true, "status": 200, "error": null, "body": %s}\nJ' % (self.stdin, body))

    def test_the_request_for_three_files(self):
        r = self.trio(live=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        req = json.loads(read(self.stdin))["request"]
        self.assertEqual(set(req), {"model", "max_tokens", "system", "messages", "thinking"})
        self.assertEqual((req["model"], req["max_tokens"], req["thinking"]), ("claude-haiku-5-5", 4096, {"type": "disabled"}))
        for name in ("add.py", "neg.py", "twice.py"):
            self.assertIn('"%s"' % name, req["system"])
        self.assertIn("at most 120 lines", req["system"])
        self.assertNotIn("assertEqual", json.dumps(req))            # nothing from the test file
        self.assertNotIn("r3_trio_test", json.dumps(req))
        self.assertIn("hold: $0.0050 placed before the call", r.stdout)
        self.assertIn("live call 1 of 1 this month", r.stdout)


class HopperVotesContract(ThreeBase):
    def test_the_contract_is_the_file_grok_ruled_on(self):
        with open(os.path.join(HERE, "inbox", "hopper_votes_test.py"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), GROK_HASH)
        task = read(os.path.join(HERE, "inbox", "hopper-votes.yaml"))
        self.assertIn("\nexpect_sha256: %s\n" % GROK_HASH, task)
        self.assertIn("\nimpl: votes.py scores.py shortlist.py\n", task)
        self.assertIn("\nkind: r3\n", task)

    def test_no_solution_to_the_slice_is_on_the_box(self):
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".git", "work", "outbox", "budget", "log", "keys", "__pycache__")]
            for f in files:
                self.assertNotIn(f, ("votes.py", "scores.py", "shortlist.py"), os.path.join(base, f))
                if f.endswith((".py", ".json", ".yaml", ".md", ".sh")) and f != "test_v07_three.py":
                    text = read(os.path.join(base, f))
                    for marker in ("def apply_tap", "def vote_score", "def next_state", "def pick_for_night"):
                        self.assertNotIn(marker, text, "%s in %s" % (marker, f))

    def test_the_prose_tells_the_builder_the_rules_without_the_tests(self):
        task = read(os.path.join(HERE, "inbox", "hopper-votes.yaml"))
        prose = [l for l in task.splitlines() if l.startswith("prose: ")][0]
        self.assertLess(len(prose), 4000)
        for want in ("apply_tap(votes, idea_id, user, at)", "vote_score(times, now, half_life_days=14)",
                     "next_state(state, score, bar)", "pick_for_night(ideas, n=5)", "at or above bar",
                     "stays Shortlisted", "oldest created first", "second tap"):
            self.assertIn(want, prose)
        for absent in ("assertEqual", "unittest", "days_ago", "hopper_votes_test"):
            self.assertNotIn(absent, prose)

    def test_the_slice_is_refused_cleanly_when_the_contract_is_altered(self):
        with open(os.path.join(self.root, "inbox", "hopper_votes_test.py"), "a") as fh:
            fh.write("# changed\n")
        r = self.r3("r3t_ok", task="inbox/hopper-votes.yaml")
        self.assertEqual(r.returncode, 4)
        self.assertIn("does not match its expect_sha256", r.stdout)
        self.assertFalse(self.exists(FIX))

    def test_a_reply_meant_for_another_task_writes_nothing_here(self):
        r = self.r3("r3t_ok", task="inbox/hopper-votes.yaml")       # names add.py, neg.py, twice.py
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("not one of the three", r.stdout)
        self.assertFalse(self.exists(os.path.join("work", "hopper-votes-FIXTURE")))


class StepRunner(ThreeBase):
    STEP = os.path.join(HERE, "step.sh")

    def step(self, *args):
        env = dict(os.environ, STEP_REPORT_DIR=os.path.join(self.tmp, "reports"))
        return subprocess.run(["bash", os.path.join(self.root, "step.sh")] + list(args), cwd=self.root, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_it_never_starts_a_live_run_or_calls_a_model(self):
        src = read(self.STEP)
        self.assertIn("unset ARCHITECT_LIVE", src)
        for word in ("ARCHITECT_LIVE=1", "r3.sh", "r2.sh", "run.sh", "curl", "sudo", "keys/", "secrets"):
            self.assertNotIn(word, src, word)

    def test_it_refuses_bad_input_and_a_dirty_tree_and_changes_nothing(self):
        self.assertEqual(self.step().returncode, 2)
        self.assertEqual(self.step(os.path.join(self.tmp, "missing.patch"), "msg").returncode, 2)
        inside = os.path.join(self.root, "x.patch")
        write(inside, "")
        r = self.step(inside, "msg")
        self.assertEqual(r.returncode, 2)
        self.assertIn("inside this repo", r.stdout)
        os.remove(inside)
        subprocess.run(["git", "init", "-q", self.root], check=True)            # everything is untracked: a dirty tree
        outside = os.path.join(self.tmp, "y.patch")
        write(outside, "")
        r = self.step(outside, "msg")
        self.assertEqual(r.returncode, 2)
        self.assertIn("changes that are not committed", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "reports")))


if __name__ == "__main__":
    import unittest
    unittest.main()
