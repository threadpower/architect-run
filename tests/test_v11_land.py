"""v0.11: land.py copies one reviewed slice to the landing place. No model, no network, $0.

The real landing place is /forge/architect-out. Each test here works on a copy of land.py whose
one OUT_ROOT line points into the test's own temp directory, so no test can touch the real one.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import HERE, Base, read, write  # noqa: E402
from test_v08_review import FILES, digest  # noqa: E402

ID = "r3-trio"
REAL_LINE = 'OUT_ROOT = "/forge/architect-out"'


class LandBase(Base):
    def setUp(self):
        super().setUp()
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.join(self.out, "toy"))
        src = read(os.path.join(self.root, "land.py"))
        assert src.count(REAL_LINE) == 1
        write(os.path.join(self.root, "land.py"), src.replace(REAL_LINE, 'OUT_ROOT = "%s"' % self.out))
        os.makedirs(os.path.join(self.root, "work", ID))
        for name, text in FILES.items():
            write(os.path.join(self.root, "work", ID, name), text)
        self.test_sha = digest(read(os.path.join(self.root, "inbox", "r3_trio_test.py")))
        self.name_it()
        self.review()

    def name_it(self, line="%s toy" % ID):
        with open(os.path.join(self.root, "landing.txt"), "a") as fh:
            fh.write(line + "\n")

    def review(self, name="2026-11-22-%s-review.md" % ID, live=True, blocking="- none", files=None, test_sha=None):
        files = files or FILES
        lines = ["# Review: %s-review" % ID, "",
                 "- Reviewer: grok-4.7, one call, %s" % ("live" if live else "FIXTURE, not a real review")]
        lines += ["- Read, not changed: `work/%s/%s` sha256 `%s`" % (ID, n, digest(t)) for n, t in files.items()]
        lines += ["- Frozen test: `inbox/r3_trio_test.py` sha256 `%s`" % (test_sha or self.test_sha), "",
                  "## Blocking", "", blocking, "", "---", ""]
        os.makedirs(os.path.join(self.root, "rulings"), exist_ok=True)
        write(os.path.join(self.root, "rulings", name), "\n".join(lines))

    def land(self, *args):
        env = dict(os.environ, ARCHITECT_LIVE="1")
        return subprocess.run(["bash", os.path.join(self.root, "land.sh")] + list(args or (ID,)), cwd=self.root,
                              env=env, capture_output=True, text=True)

    def dest(self, *more):
        return os.path.join(self.out, "toy", ID, *more)

    def nothing(self, r, code, needle):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)
        self.assertIn("Nothing copied", r.stdout)
        self.assertFalse(os.path.lexists(self.dest()), "something was copied")


class Lands(LandBase):
    def test_a_named_reviewed_slice_is_copied_and_work_is_left_alone(self):
        before = {n: os.stat(os.path.join(self.root, "work", ID, n)).st_mtime_ns for n in FILES}
        r = self.land()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(os.listdir(self.dest())), ["LANDED.txt", "add.py", "neg.py", "twice.py"])
        for name, text in FILES.items():
            self.assertEqual(read(self.dest(name)), text)
            self.assertEqual(os.stat(os.path.join(self.root, "work", ID, name)).st_mtime_ns, before[name])
            self.assertIn("file: %s sha256 %s" % (name, digest(text)), read(self.dest("LANDED.txt")))
        self.assertIn("review: rulings/2026-11-22-%s-review.md" % ID, read(self.dest("LANDED.txt")))
        self.assertEqual(sorted(os.listdir(self.out)), ["toy"])
        self.assertIn("Nothing was run", r.stdout)

    def test_it_never_overwrites(self):
        self.assertEqual(self.land().returncode, 0)
        r = self.land()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("never overwritten", r.stdout)


class Refuses(LandBase):
    def test_a_slice_that_is_not_named(self):
        write(os.path.join(self.root, "landing.txt"), "# nothing named\n")
        self.nothing(self.land(), 2, "not named in landing.txt")

    def test_a_landing_list_with_a_bad_line(self):
        self.name_it("r3-trio toy extra")
        self.nothing(self.land(), 2, "not '<slice id> <project>'")

    def test_a_built_file_changed_after_the_review(self):
        write(os.path.join(self.root, "work", ID, "neg.py"), "def neg(a):\n    return a\n")
        self.nothing(self.land(), 4, "neg.py is not the file the review read")

    def test_a_test_changed_after_the_contract(self):
        with open(os.path.join(self.root, "inbox", "r3_trio_test.py"), "a") as fh:
            fh.write("# changed\n")
        self.nothing(self.land(), 4, "no longer matches the slice's expect_sha256")

    def test_a_review_written_against_another_test(self):
        self.review(test_sha="0" * 64)
        self.nothing(self.land(), 4, "against a different test")

    def test_no_review_a_dry_run_review_and_a_blocking_review(self):
        os.remove(os.path.join(self.root, "rulings", "2026-11-22-%s-review.md" % ID))
        self.nothing(self.land(), 2, "exactly one live review")
        self.review(name="2026-11-22-%s-review-FIXTURE.md" % ID, live=False)
        self.nothing(self.land(), 2, "exactly one live review")
        self.review(live=False)
        self.nothing(self.land(), 2, "not a live review with nothing blocking")
        self.review(blocking="- neg.py: returns the wrong sign")
        self.nothing(self.land(), 2, "not a live review with nothing blocking")

    def test_two_reviews_of_the_same_slice(self):
        self.review(name="2026-11-23-%s-review.md" % ID)
        self.nothing(self.land(), 2, "has 2")

    def test_a_project_directory_that_is_missing_or_a_symlink_or_inside_the_repo(self):
        os.rmdir(os.path.join(self.out, "toy"))
        r = self.land()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("Jeremy creates it by hand", r.stdout)
        self.assertEqual(os.listdir(self.out), [])
        os.symlink(os.path.join(self.root, "inbox"), os.path.join(self.out, "toy"))
        r = self.land()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, "inbox", ID)))

    def test_a_missing_built_file_and_odd_arguments(self):
        os.remove(os.path.join(self.root, "work", ID, "add.py"))
        self.nothing(self.land(), 2, "add.py is missing")
        for args in (("../etc",), ("r3-trio", "toy"), ("R3-TRIO",), ("-x",)):
            r = self.land(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("usage", r.stdout)


class Source(Base):
    def test_it_calls_nothing_and_the_path_is_fixed_in_one_place(self):
        src = read(os.path.join(HERE, "land.py"))
        self.assertEqual(src.count(REAL_LINE), 1)
        self.assertEqual(src.count("architect-out"), 1)
        for word in ("subprocess", "socket", "urllib", "http", "requests", "os.system", "os.remove", "os.rename",
                     "shutil", "chmod", "ledger", "keys", "sudo", "r3.sh", "r4.sh", "limits", "environ", "getenv",
                     "rmtree", "unlink", "git"):
            self.assertNotIn(word, src, word)
        self.assertEqual(src.count("os.mkdir("), 1)
        self.assertEqual(src.count('"xb")') + src.count('"x")'), 2)      # the only two writes refuse to replace
        sh = read(os.path.join(HERE, "land.sh"))
        code = [ln for ln in sh.splitlines() if ln.strip() and not ln.startswith("#")]
        self.assertEqual(code, ["set -u", "unset ARCHITECT_LIVE", 'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"',
                                'exec python3 "$ROOT/land.py" "$@"'])

    def test_no_model_is_given_the_path_and_nothing_is_named_by_a_patch(self):
        for name in ("r2.py", "r2_child.py", "r3.py", "r3_child.py", "r3_cage.sh", "r4.py", "review_task.py",
                     "cage/cage.sh", "review.schema.json", "rulings.schema.json"):
            self.assertNotIn("architect-out", read(os.path.join(HERE, name)), name)
        for name in os.listdir(os.path.join(HERE, "inbox")):
            if name.endswith((".yaml", ".txt")):
                self.assertNotIn("architect-out", read(os.path.join(HERE, "inbox", name)), name)


if __name__ == "__main__":
    import unittest
    unittest.main()
