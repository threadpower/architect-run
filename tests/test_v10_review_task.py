"""v0.10: review_task.py writes the R4 review task for a built slice. No model, no network, $0."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import HERE, read, write  # noqa: E402
from test_v08_review import PARAS, TASK, ReviewBase, digest  # noqa: E402

SLICE, SPEC, EXCERPT = "inbox/r3-trio.yaml", "inbox/trio.spec.md", "inbox/r3-trio.spec.txt"


class WriterBase(ReviewBase):
    def setUp(self):
        super().setUp()
        os.remove(os.path.join(self.root, TASK))            # the base class wrote one by hand; start without it
        write(os.path.join(self.root, EXCERPT),
              "# pasted word for word\n" + "\n".join(p.replace("*", "").replace("`", "") for p in PARAS) + "\n")

    def make(self, *args):
        env = dict(os.environ, ARCHITECT_LIVE="1")          # the wrapper must drop this
        return subprocess.run(["bash", os.path.join(self.root, "review_task.sh")] + list(args or (SLICE, SPEC)),
                              cwd=self.root, env=env, capture_output=True, text=True)

    def tree(self):
        seen = {}
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in files:
                p = os.path.join(base, f)
                seen[os.path.relpath(p, self.root)] = digest(read(p)) if not os.path.islink(p) else "link"
        return seen


class Writes(WriterBase):
    def test_it_writes_one_file_and_the_review_dry_run_accepts_it(self):
        before = self.tree()
        r = self.make()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = self.tree()
        self.assertEqual(set(after) - set(before), {TASK})
        self.assertEqual({k: v for k, v in after.items() if k != TASK}, before, "something else changed")
        task = read(os.path.join(self.root, TASK))
        for line in ("id: r3-trio-review", "kind: r4", "slice: " + SLICE, "spec: " + SPEC, "excerpt: " + EXCERPT):
            self.assertIn("\n%s\n" % line, task)
        self.assertIn("Nothing was run", r.stdout)
        self.assertIn("ARCHITECT_LIVE=1 bash r4.sh " + TASK, r.stdout)
        review = self.r4()                                   # the fixture review reads the task this wrote
        self.assertEqual(review.returncode, 0, review.stdout + review.stderr)
        self.assertIn("hashes match", review.stdout)

    def test_it_never_overwrites(self):
        self.assertEqual(self.make().returncode, 0)
        first = read(os.path.join(self.root, TASK))
        r = self.make()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("never overwritten", r.stdout)
        self.assertEqual(read(os.path.join(self.root, TASK)), first)


class Refuses(WriterBase):
    def nothing(self, r, code, needle):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, TASK)), "a task was written")

    def test_a_slice_that_has_not_been_built(self):
        task = read(os.path.join(self.root, SLICE)).replace("id: r3-trio", "id: never-built")
        write(os.path.join(self.root, "inbox", "never-built.yaml"), task)
        self.nothing(self.make("inbox/never-built.yaml", SPEC), 2, "has not been built")

    def test_a_missing_built_file(self):
        os.remove(os.path.join(self.root, "work", "r3-trio", "neg.py"))
        self.nothing(self.make(), 2, "neg.py is missing")

    def test_a_built_file_that_is_a_symlink(self):
        os.remove(os.path.join(self.root, "work", "r3-trio", "neg.py"))
        os.symlink(os.path.join(self.root, "work", "r3-trio", "add.py"), os.path.join(self.root, "work", "r3-trio", "neg.py"))
        self.nothing(self.make(), 2, "not a plain file")

    def test_an_excerpt_line_that_is_not_in_the_spec(self):
        with open(os.path.join(self.root, EXCERPT), "a") as fh:
            fh.write("A sentence the spec never said.\n")
        self.nothing(self.make(), 2, "not in inbox/trio.spec.md word for word")

    def test_an_altered_test_file(self):
        with open(os.path.join(self.root, "inbox", "r3_trio_test.py"), "a") as fh:
            fh.write("# changed\n")
        self.nothing(self.make(), 4, "does not match the slice's expect_sha256")

    def test_files_outside_inbox_and_the_wrong_kind_of_task(self):
        self.nothing(self.make("limits.env", SPEC), 2, "directly inside inbox/")
        self.nothing(self.make(SLICE, "../etc/passwd"), 2, "directly inside inbox/")
        self.nothing(self.make("inbox/r1.yaml", SPEC), 2, "must be an R3 task")
        self.nothing(self.make(SLICE), 2, "usage")


class Source(WriterBase):
    def test_it_calls_nothing_and_writes_one_file(self):
        src = read(os.path.join(HERE, "review_task.py"))
        for word in ("subprocess", "socket", "urllib", "http", "requests", "os.system", "os.remove", "os.rename",
                     "shutil", "chmod", "ledger", "keys", "sudo", "ARCHITECT_LIVE=1 bash r3", "r3.sh", "limits", "LIVE_MAX",
                     "hold", "rmtree", "unlink"):
            self.assertNotIn(word, src, word)
        self.assertEqual(src.count("open("), 6)              # five reads, one write
        self.assertEqual(src.count('"x")'), 1)               # and the write refuses to replace a file
        sh = read(os.path.join(HERE, "review_task.sh"))
        self.assertIn("unset ARCHITECT_LIVE", sh)
        code = [ln for ln in sh.splitlines() if ln.strip() and not ln.startswith("#")]
        self.assertEqual(code, ["set -u", "unset ARCHITECT_LIVE", 'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"',
                                'exec python3 "$ROOT/review_task.py" "$@"'])

if __name__ == "__main__":
    import unittest
    unittest.main()
