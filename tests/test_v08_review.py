"""v0.8 R4: one review of a built slice. Dry runs only: no socket, $0.

The slice under review here is the toy r3-trio, built by hand inside the test copy.
"""
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import Base, HERE, read, write  # noqa: E402

XAI = "xai-TESTKEY-not-real-0000000000"
PARKED = "sk-ant-PARKED-not-real-000000000"
FILES = {"add.py": "def add(a, b):\n    return a + b\n", "neg.py": "def neg(a):\n    return -a\n",
         "twice.py": "def twice(a):\n    return a * 2\n"}
PARAS = ["add returns the **sum** of its two arguments.", "neg returns the negative of its argument.",
         "twice returns `double` its argument."]
TASK = "inbox/r3-trio-review.yaml"
FIX = os.path.join("budget", "ledger.r4.fixture.json")
REAL = os.path.join("budget", "ledger.json")


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class ReviewBase(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.root, "work", "r3-trio"))
        for name, text in FILES.items():
            write(os.path.join(self.root, "work", "r3-trio", name), text)
        write(os.path.join(self.root, "inbox", "trio.spec.md"),
              "# Toy spec\n\n" + "\n\n".join(PARAS) + "\n\nREST-OF-SPEC-MARKER: the roadmap nobody asked about.\n")
        excerpt = "# pasted word for word\n" + "\n".join(p.replace("*", "").replace("`", "") for p in PARAS) + "\n"
        write(os.path.join(self.root, "inbox", "trio.excerpt.txt"), excerpt)
        self.review_task(excerpt_sha=digest(excerpt))

    def review_task(self, excerpt_sha=None, hashes=None, extra=""):
        if excerpt_sha is None:
            excerpt_sha = digest(read(os.path.join(self.root, "inbox", "trio.excerpt.txt")))
        hashes = hashes or [digest(FILES[n]) for n in ("add.py", "neg.py", "twice.py")]
        write(os.path.join(self.root, TASK),
              "id: r3-trio-review\nkind: r4\nslice: inbox/r3-trio.yaml\nspec: inbox/trio.spec.md\n"
              "excerpt: inbox/trio.excerpt.txt\nexpect_excerpt_sha256: %s\nfiles_sha256: %s\n%s"
              % (excerpt_sha, " ".join(hashes), extra))

    def fixture(self, name, obj, usage=None):
        body = {"choices": [{"message": {"content": obj if isinstance(obj, str) else json.dumps(obj)}}]}
        if usage is not False:
            body["usage"] = usage or {"prompt_tokens": 3000, "completion_tokens": 300}
        write(os.path.join(self.root, "tests", "fixtures", name + ".json"), json.dumps(body))
        return name

    def r4(self, fixture="r4_clean", live=False, **extra):
        env = dict(os.environ, PATH=self.shims + os.pathsep + os.environ["PATH"])
        env.pop("ARCHITECT_LIVE", None)
        env.update(extra)
        args = ["bash", os.path.join(self.root, "r4.sh"), TASK]
        if live:
            env["ARCHITECT_LIVE"] = "1"
        else:
            args += ["--fixture", os.path.join("tests", "fixtures", fixture + ".json")]
        return subprocess.run(args, cwd=self.root, env=env, capture_output=True, text=True, timeout=120)

    def snapshot(self):
        out = {}
        for base, _d, files in os.walk(os.path.join(self.root, "work")):
            for f in files:
                p = os.path.join(base, f)
                out[os.path.relpath(p, self.root)] = (read(p), os.stat(p).st_mtime_ns)
        return out

    def reviews(self):
        d = os.path.join(self.root, "rulings")
        return [read(os.path.join(d, f)) for f in sorted(os.listdir(d))] if os.path.isdir(d) else []

    def no_call(self, r, code):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, FIX)), "a hold was placed")
        self.assertFalse(os.path.exists(os.path.join(self.root, REAL)))
        self.assertEqual(self.reviews(), [])


class Review(ReviewBase):
    def test_a_clean_review_writes_one_file_in_rulings_and_nothing_under_work(self):
        before = self.snapshot()
        r = self.r4()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK r3-trio-review: nothing blocking", r.stdout)
        self.assertEqual(self.snapshot(), before)                       # same files, same bytes, same mtimes
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "rulings"))),
                         [f for f in sorted(os.listdir(os.path.join(self.root, "rulings"))) if "-FIXTURE" in f])
        text = self.reviews()[0]
        for want in ("FIXTURE, not a real review", "grok-4.7", "## Blocking\n\n- none", "returned no code",
                     "cannot un-accept the files", digest(FILES["add.py"]), "Spec paragraphs sent: 3"):
            self.assertIn(want, text)
        self.assertFalse(os.path.exists(os.path.join(self.root, REAL)))
        self.assertEqual(json.loads(read(os.path.join(self.root, FIX)))["holds"], [])
        self.assertEqual(self.run_sh("run.sh").returncode, 0)            # R1 is not disturbed

    def test_a_contradiction_or_a_forbidden_act_blocks_and_a_note_never_does(self):
        before = self.snapshot()
        r = self.r4("r4_blocking")
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("BLOCKING 1 finding(s). The slice stops here. The files stay where they are", r.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("| 1 | twice.py | CONTRADICTION |", self.reviews()[0])
        self.assertIn("| 2 | add.py | NOTE |", self.reviews()[0])
        self.tearDown()
        self.setUp()
        self.fixture("forb", {"summary": "s", "findings": [{"file": "neg.py", "kind": "forbidden", "detail": "It reads the clock."}]})
        self.assertEqual(self.r4("forb").returncode, 4)
        self.tearDown()
        self.setUp()
        self.fixture("notes", {"summary": "s", "findings": [{"file": "add.py", "kind": "note", "detail": "Could be shorter."},
                                                             {"file": "", "kind": "note", "detail": "Missing a feature."}]})
        r = self.r4("notes")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("## Blocking\n\n- none", self.reviews()[0])

    def test_a_reply_with_code_a_new_field_or_another_file_writes_no_review(self):
        bad = (
            {"summary": "s", "findings": [{"file": "add.py", "kind": "note", "detail": "Use this:\n```python\ndef add(a, b): return a+b\n```"}]},
            {"summary": "s", "findings": [{"file": "add.py", "kind": "note", "detail": "Better:\ndef add(a, b):\n    return b + a"}]},
            {"summary": "s", "findings": [{"file": "add.py", "kind": "note", "detail": "x" * 900}]},
            {"summary": "s", "findings": [], "replacement": {"add.py": "x"}},
            {"summary": "s", "findings": [{"file": "add.py", "kind": "note", "detail": "d", "fix": "x"}]},
            {"summary": "s", "findings": [{"file": "add.py", "kind": "amend_test", "detail": "d"}]},
            {"summary": "s", "findings": [{"file": "other.py", "kind": "note", "detail": "d"}]},
            "not json at all",
        )
        for n, obj in enumerate(bad):
            self.tearDown()
            self.setUp()
            before = self.snapshot()
            r = self.r4(self.fixture("bad%d" % n, obj))
            self.assertEqual(r.returncode, 4, "%d %s" % (n, r.stdout))
            self.assertIn("No review written", r.stdout, n)
            self.assertEqual(self.reviews(), [], n)
            self.assertEqual(self.snapshot(), before, n)

    def test_money_no_usage_holds_and_overspend_halts_on_the_dry_run_ledger_only(self):
        r = self.r4(self.fixture("nousage", {"summary": "s", "findings": []}, usage=False))
        self.assertEqual(r.returncode, 10)
        self.assertEqual(len(json.loads(read(os.path.join(self.root, FIX)))["holds"]), 1)
        self.assertFalse(os.path.exists(os.path.join(self.root, REAL)))
        self.assertEqual(self.r4().returncode, 10)                      # blocked by its own open hold
        self.assertEqual(self.run_sh("run.sh").returncode, 0)
        self.tearDown()
        self.setUp()
        r = self.r4(self.fixture("big", {"summary": "s", "findings": []},
                                 usage={"prompt_tokens": 2000000, "completion_tokens": 10, "cost_in_usd_ticks": 30000000000}))
        self.assertEqual(r.returncode, 10)
        self.assertIn("over this task's $2.00. Recorded", r.stdout)
        self.assertEqual(self.reviews(), [])


class RefusedBeforeAnyCall(ReviewBase):
    def test_a_built_file_that_changed_or_is_missing_or_is_a_link(self):
        write(os.path.join(self.root, "work", "r3-trio", "neg.py"), "def neg(a):\n    return a\n")
        r = self.r4()
        self.no_call(r, 4)
        self.assertIn("neg.py does not match its files_sha256 hash", r.stdout)
        os.remove(os.path.join(self.root, "work", "r3-trio", "neg.py"))
        self.no_call(self.r4(), 2)
        os.symlink(os.path.join(self.root, "work", "r3-trio", "add.py"), os.path.join(self.root, "work", "r3-trio", "neg.py"))
        self.no_call(self.r4(), 3)

    def test_an_excerpt_line_that_is_not_in_the_spec_word_for_word(self):
        path = os.path.join(self.root, "inbox", "trio.excerpt.txt")
        write(path, read(path) + "twice may also return triple on Sundays.\n")
        self.review_task()
        r = self.r4()
        self.no_call(r, 2)
        self.assertIn("excerpt paragraph 4 is not in inbox/trio.spec.md word for word", r.stdout)

    def test_hashes_and_task_lines(self):
        self.review_task(excerpt_sha="0" * 64)
        self.no_call(self.r4(), 4)
        self.review_task(hashes=[digest(FILES["add.py"])] * 2)
        self.no_call(self.r4(), 2)
        for line in ("model: grok-9", "reviewer: someone", "questions: is it pretty", "tools: bash"):
            self.review_task(extra=line + "\n")
            self.no_call(self.r4(), 2)
        with open(os.path.join(self.root, "inbox", "r3_trio_test.py"), "a") as fh:
            fh.write("# changed\n")
        self.review_task()
        r = self.r4()
        self.no_call(r, 4)
        self.assertIn("test file does not match the slice's expect_sha256", r.stdout)


class WhatIsSent(ReviewBase):
    """`sudo` is a fake that records what the child would be handed and answers with a fixture body."""

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.root, "keys"), mode=0o700)
        for name, value in (("xai", XAI), ("anthropic", PARKED)):
            write(os.path.join(self.root, "keys", name), value + "\n")
            os.chmod(os.path.join(self.root, "keys", name), 0o600)
        self.shim("systemctl", "echo inactive")
        self.shim("docker", "exit 0")
        self.shim("id", 'if [ "${2:-}" = architect ]; then case "$1" in -u) echo 1500;; -Gn) echo architect;; esac; '
                        'else exec /usr/bin/id "$@"; fi')
        self.argv, self.stdin = os.path.join(self.tmp, "sudo.argv"), os.path.join(self.tmp, "sudo.stdin")
        body = read(os.path.join(HERE, "tests", "fixtures", "r4_clean.json"))
        self.shim("sudo", 'echo "$@" > "%s"\ncat > "%s"\ncat <<\'J\'\n{"ok": true, "status": 200, "error": null, "body": %s}\nJ'
                  % (self.argv, self.stdin, body))

    def test_four_things_are_sent_and_the_rest_of_the_spec_is_not(self):
        before = self.snapshot()
        r = self.r4(live=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(read(self.argv).strip(), "runuser -u architect -- env -i PATH=/usr/bin:/bin python3 %s --live"
                         % os.path.join(self.root, "r2_child.py"))
        packet = json.loads(read(self.stdin))
        self.assertEqual(packet["key"], XAI)                                # the xAI key, on stdin, and only that key
        req = packet["request"]
        self.assertEqual((req["model"], req["max_completion_tokens"]), ("grok-4.7", 4000))
        self.assertEqual(req["response_format"]["json_schema"]["schema"]["required"], ["summary", "findings"])
        sent = json.dumps(req)
        for text in list(FILES.values()) + ["Write three Python modules.", "self.assertEqual(twice(21), 42)",
                                              "twice returns double its argument."]:
            self.assertIn(json.dumps(text)[1:-1], sent)
        self.assertNotIn("REST-OF-SPEC-MARKER", sent)
        self.assertNotIn("sk-ant-", read(self.stdin))
        self.assertNotIn(XAI, sent)
        system = req["messages"][0]["content"]
        for want in ("contradict any of those paragraphs", "read a file, open a socket, start a process, read the clock",
                     "never blocks", "do not return code", "do not amend the test"):
            self.assertIn(want, system)
        self.assertEqual(self.snapshot(), before)                           # nothing under work/ written, live either
        seen = r.stdout + r.stderr
        for top in ("log", "outbox", "rulings", "budget", "work"):
            for base, _d, files in os.walk(os.path.join(self.root, top)):
                for f in files:
                    seen += read(os.path.join(base, f))
        self.assertNotIn(XAI, seen)
        self.assertNotIn(PARKED, seen)
        self.assertEqual(len(self.reviews()), 1)
        self.assertNotIn("FIXTURE", self.reviews()[0])
        self.assertEqual(json.loads(read(os.path.join(self.root, REAL)))["holds"], [])


class Static(ReviewBase):
    def test_r4_writes_only_ledger_log_notice_and_rulings_and_knows_one_host_through_the_r2_child(self):
        src = read(os.path.join(HERE, "r4.py"))
        self.assertIn('CHILD = os.path.join(ROOT, "r2_child.py")', src)
        writes = [ln.strip() for ln in src.splitlines() if 'open(' in ln and ('"w"' in ln or '"a"' in ln)]
        self.assertEqual(len(writes), 4, writes)                          # ledger tmp, run.log, notify.txt, the review
        for word in ("anthropic", "https://", "urllib", "os.remove", "os.rename", "shutil", "chmod", "mkdir(built",
                     "importlib", "exec(", "eval("):
            self.assertNotIn(word, src.lower() if word == "anthropic" else src, word)
        self.assertEqual(src.count("subprocess.run("), 2, "preflight and the one child call")
        self.assertIn('REVIEWER_MODEL = "grok-4.7"', src)
        self.assertIn("MAX_OUTPUT_TOKENS = 4000", src)

    def test_the_votes_excerpt_is_in_the_repo_and_the_step_runner_leaves_readable_children_alone(self):
        text = read(os.path.join(HERE, "inbox", "hopper-votes.spec.txt"))
        for want in ("a second tap removes it", "at or above it", "stays Shortlisted", "the older one goes first",
                     "14-day half-life", "The runner ignores them"):
            self.assertIn(want, text)
        step = read(os.path.join(HERE, "step.sh"))
        self.assertIn('[ -z "$(find "$c" -perm -004)" ] && chmod o+r "$c"', step)
        self.assertNotIn("chmod 644", step)
        self.assertNotIn("keys", step)


if __name__ == "__main__":
    import unittest
    unittest.main()
