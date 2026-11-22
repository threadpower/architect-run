"""v0.13: slice.sh runs one slice from build to review. These tests make no call of any kind.

r3.sh, review_task.sh and r4.sh are each tested on their own elsewhere. Here they are swapped,
in the test's own copy, for stand-ins that record that they ran and exit as told, so what is
tested is the chain: the order, the stops, the commits, and what it refuses to do.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import HERE, Base, read, write  # noqa: E402

ID = "toy-one"


class SliceBase(Base):
    def setUp(self):
        super().setUp()
        self.ran = os.path.join(self.tmp, "ran.txt")
        write(os.path.join(self.root, "inbox", ID + ".yaml"), "id: %s\nkind: r3\n" % ID)
        write(os.path.join(self.root, "inbox", "spec.md"), "# spec\n")
        self.stand_in("r3.sh", 0, 'mkdir -p work/%s outbox && echo built > work/%s/a.py && echo BUILD-REPORT > outbox/2026-01-01-%s.md' % (ID, ID, ID))
        self.stand_in("review_task.sh", 0, 'echo "id: x" > inbox/%s-review.yaml' % ID)
        self.stand_in("r4.sh", 0, 'mkdir -p rulings && echo REVIEW-TEXT > rulings/2026-01-01-%s-review.md' % ID)
        self.shim("git", 'echo "git $*" >> "%s"\ncase "$1" in status) ;; log) echo "abc1234 a commit";; esac\nexit 0' % self.ran)

    def stand_in(self, name, code, body=":"):
        write(os.path.join(self.root, name),
              '#!/bin/bash\necho "%s $* live=${ARCHITECT_LIVE:-}" >> "%s"\n[ %d = 0 ] && { %s; }\nexit %d\n'
              % (name, self.ran, code, body, code))

    def slice(self, *args, live=True):
        env = dict(os.environ, PATH=self.shims + os.pathsep + os.environ["PATH"])
        env.pop("ARCHITECT_LIVE", None)
        if live:
            env["ARCHITECT_LIVE"] = "1"
        return subprocess.run(["bash", os.path.join(self.root, "slice.sh")] + list(args or (ID, "inbox/spec.md")),
                              cwd=self.root, env=env, capture_output=True, text=True)

    def steps(self):
        return [ln.split()[0] for ln in read(self.ran).splitlines() if not ln.startswith("git")] if os.path.exists(self.ran) else []

    def commits(self):
        return [ln for ln in read(self.ran).splitlines() if ln.startswith("git commit")] if os.path.exists(self.ran) else []


class Chain(SliceBase):
    def test_a_clean_slice_runs_the_three_steps_once_each_in_order_and_commits_two_things(self):
        r = self.slice()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.steps(), ["r3.sh", "review_task.sh", "r4.sh"])
        ran = read(self.ran)
        self.assertIn("r3.sh inbox/%s.yaml live=1" % ID, ran)
        self.assertIn("review_task.sh inbox/%s.yaml inbox/spec.md" % ID, ran)
        self.assertIn("r4.sh inbox/%s-review.yaml live=1" % ID, ran)
        self.assertEqual(self.commits(), ["git commit -q -m Review task for %s" % ID, "git commit -q -m Review of %s" % ID])
        self.assertIn("git add inbox/%s-review.yaml" % ID, ran)
        self.assertNotIn("git add -A", ran)
        for want in ("BUILD-REPORT", "REVIEW-TEXT", "RESULT: OK %s is built and reviewed" % ID, "The next slice waits"):
            self.assertIn(want, r.stdout)
        report = [f for f in os.listdir(os.path.join(self.root, "outbox")) if f.startswith("slice-%s-" % ID)]
        if report:                                           # on a machine with no C:\forge the report lands in outbox/
            self.assertIn("REVIEW-TEXT", read(os.path.join(self.root, "outbox", report[0])))

    def test_a_failed_build_stops_before_the_review_task_and_commits_nothing(self):
        self.stand_in("r3.sh", 4)
        r = self.slice()
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertEqual(self.steps(), ["r3.sh"])
        self.assertEqual(self.commits(), [])
        self.assertIn("STOPPED at the build, exit 4", r.stdout)
        self.assertIn("Do not run it again", r.stdout)

    def test_a_halt_or_a_refusal_at_the_build_stops_the_same_way(self):
        for code in (2, 3, 5, 10):
            self.tearDown()
            self.setUp()
            self.stand_in("r3.sh", code)
            r = self.slice()
            self.assertEqual(r.returncode, code, r.stdout)
            self.assertEqual(self.steps(), ["r3.sh"])
            self.assertEqual(self.commits(), [])

    def test_a_refused_review_task_stops_before_the_review_call(self):
        self.stand_in("review_task.sh", 2)
        r = self.slice()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(self.steps(), ["r3.sh", "review_task.sh"])
        self.assertEqual(self.commits(), [])
        self.assertIn("No review call was made", r.stdout)

    def test_a_blocking_review_is_committed_and_the_exit_says_stop(self):
        self.stand_in("r4.sh", 4, ":")
        write(os.path.join(self.root, "r4.sh"), read(os.path.join(self.root, "r4.sh")).replace(
            "[ 4 = 0 ]", "mkdir -p rulings && echo BLOCKING-REVIEW > rulings/2026-01-01-%s-review.md; [ 4 = 0 ]" % ID))
        r = self.slice()
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertEqual(self.steps(), ["r3.sh", "review_task.sh", "r4.sh"])
        self.assertEqual(len(self.commits()), 2)
        self.assertIn("BLOCKING-REVIEW", r.stdout)
        self.assertIn("STOPPED at the review, exit 4", r.stdout)

    def test_a_review_that_wrote_nothing_commits_no_review(self):
        self.stand_in("r4.sh", 10)
        r = self.slice()
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertEqual(self.commits(), ["git commit -q -m Review task for %s" % ID])


class Refuses(SliceBase):
    def nothing(self, r, needle):
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)
        self.assertEqual(self.steps(), [])
        self.assertEqual(self.commits(), [])

    def test_without_the_live_word(self):
        self.nothing(self.slice(live=False), "Set ARCHITECT_LIVE=1")

    def test_a_slice_that_was_already_built_or_already_has_a_review_task(self):
        os.makedirs(os.path.join(self.root, "work", ID))
        self.nothing(self.slice(), "never run twice")
        os.rmdir(os.path.join(self.root, "work", ID))
        write(os.path.join(self.root, "inbox", ID + "-review.yaml"), "id: x\n")
        self.nothing(self.slice(), "never run twice")

    def test_a_dirty_tree(self):
        self.shim("git", 'echo "git $*" >> "%s"\n[ "$1" = status ] && echo " M limits.env"\nexit 0' % self.ran)
        self.nothing(self.slice(), "not clean")

    def test_odd_arguments_and_missing_files(self):
        for args in ((ID,), (ID, "inbox/spec.md", "extra"), ("../x", "inbox/spec.md"), (ID, "/etc/passwd"),
                     (ID, "inbox/../limits.md"), ("Two Words", "inbox/spec.md")):
            self.nothing(self.slice(*args), "usage")
        self.nothing(self.slice("no-such-slice", "inbox/spec.md"), "is not there")
        self.nothing(self.slice(ID, "inbox/none.md"), "is not there")


class Source(Base):
    def test_one_slice_two_calls_and_no_hand_on_the_caps(self):
        src = read(os.path.join(HERE, "slice.sh"))
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
        self.assertEqual(code.count('bash "$ROOT/r3.sh"'), 1)
        self.assertEqual(code.count('bash "$ROOT/r4.sh"'), 1)
        self.assertEqual(code.count('bash "$ROOT/review_task.sh"'), 1)
        import re
        self.assertIsNone(re.search(r"(?m)^\s*(for|while|until)\b", code), "a loop")
        for word in ("limits.env", "R3_LIVE_MAX", "clear-hold", "land.sh", "landing",
                     "architect-out", "git add -A", "git add .", "rm ", "sudo", "--fixture", "chmod", "sed ", "keys",
                     "step.sh", "export ARCHITECT_LIVE", "ARCHITECT_LIVE=1 bash \"$ROOT"):
            self.assertNotIn(word, code, word)
        self.assertIn('git add "inbox/$ID-review.yaml"', code)
        self.assertIn("git add rulings/", code)
        self.assertEqual(code.count("git add"), 2)
        self.assertEqual(code.count("git commit"), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
