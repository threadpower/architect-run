"""v0.12: Hopper batch 2 on paper: pasted list, seed plan, the Board. Dry runs only: no socket, $0.

Three contracts Grok accepted on Nov 22. There is no solution to any of them in this repository,
and one test here keeps it that way. Nothing in this file runs a builder or a reviewer.
"""
import hashlib
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import HERE, read  # noqa: E402
from test_v07_three import ThreeBase  # noqa: E402

ACCEPTED = {
    "paste": "76a9152885f204a4feb0579f19f5680c1424035e7e208b3da0ac3f9e302847ae",
    "seed": "5b5535f194187856905d2ffc0464d68a4ba5236c549ba006d203294ceb0c9b01",
    "board": "8ff382f261db97f482ce85d68c3c8b557397f6160e39c05d927028b214d3a74b",
}
SPEC = os.path.join(HERE, "inbox", "hopper-h1.md")


def inbox(name):
    return os.path.join(HERE, "inbox", name)


def prose_of(name):
    return [ln for ln in read(inbox("hopper-%s.yaml" % name)).splitlines() if ln.startswith("prose: ")][0]


def sent(name):
    return [ln.strip() for ln in read(inbox("hopper-%s.spec.txt" % name)).splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def plain(text):            # the same rule r4.py uses
    return " ".join(re.sub(r"[*`\\_]", "", text).split())


class Contracts(unittest.TestCase):
    def test_each_contract_is_the_file_grok_accepted(self):
        for name, want in ACCEPTED.items():
            with open(inbox("hopper_%s_test.py" % name), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), want, name)
            task = read(inbox("hopper-%s.yaml" % name))
            for line in ("id: hopper-%s" % name, "kind: r3", "impl: %s.py" % name,
                         "test: inbox/hopper_%s_test.py" % name, "expect_sha256: %s" % want):
                self.assertIn("\n%s\n" % line, task, "%s: %s" % (name, line))
            for forbidden in ("model:", "max_tokens:", "tools:", "retries:", "rounds:", "reviewer:"):
                self.assertNotIn("\n" + forbidden, task, name)

    def test_no_solution_to_any_of_the_three_is_on_the_box(self):
        names = ("paste.py", "seed.py", "board.py")
        markers = ("def split_lines", "def plan_seed", "def board_rows")
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".git", "work", "outbox", "budget", "log", "keys", "__pycache__")]
            for f in files:
                self.assertNotIn(f, names, os.path.join(base, f))
                if f.endswith((".py", ".json", ".yaml", ".md", ".sh", ".txt")) and f != "test_v12_batch2.py":
                    text = read(os.path.join(base, f))
                    for marker in markers:
                        self.assertNotIn(marker, text, "%s in %s" % (marker, f))

    def test_the_prose_tells_the_builder_the_rules_without_the_tests(self):
        wants = {
            "paste": ("split_lines(text)", "carriage return", "spaces and tabs at its two ends", "returned twice"),
            "seed": ("plan_seed(lines, existing_hashes)", "empty_text", "already_imported", "repeated_in_file",
                     "exactly as given", "the first rule that applies"),
            "board": ("board_rows(ideas, lane=None, source=None)", "Submitted, Shortlisted, Generated, Reviewed",
                      "the higher id first", "is not an error", "the same dict objects"),
        }
        for name, needed in wants.items():
            prose = prose_of(name)
            self.assertLess(len(prose), 4000, name)
            for want in needed:
                self.assertIn(want, prose, "%s: %s" % (name, want))
            for absent in ("assertEqual", "unittest", "_test", "laundromat", "Squatch", "porch light", "Raven"):
                self.assertNotIn(absent, prose, "%s: %s" % (name, absent))

    def test_the_cut_sentences_reach_neither_the_builder_nor_the_reviewer(self):
        cut = {
            "seed": ("team, seed, warp", "transcript", "luma, public"),
            "board": ("One tap to vote", "take it back"),
            "paste": ("exact duplicate",),
        }
        for name, phrases in cut.items():
            seen = prose_of(name) + "\n" + "\n".join(sent(name))
            for phrase in phrases:
                self.assertNotIn(phrase, seen, "%s: %s" % (name, phrase))

    def test_each_excerpt_carries_the_rules_jeremy_set(self):
        for name, opening in (("paste", "Rules for a pasted list, set by Jeremy on Nov 22."),
                              ("seed", "Rules for the seed import, set by Jeremy on Nov 22."),
                              ("board", "Rules for the Board, set by Jeremy on Nov 22.")):
            self.assertEqual(len([ln for ln in sent(name) if ln.startswith(opening)]), 1, name)

    @unittest.skipUnless(os.path.exists(SPEC), "the Hopper spec is not in this copy")
    def test_every_excerpt_line_is_in_the_hopper_spec_word_for_word(self):
        spec = plain(read(SPEC))
        for name in ACCEPTED:
            for n, para in enumerate(sent(name), 1):
                self.assertIn(plain(para), spec, "hopper-%s.spec.txt line %d: %s..." % (name, n, para[:50]))


class DryRuns(ThreeBase):
    """One dry run a test: each starts from its own copy and its own fixture ledger."""

    def wrong_reply(self, name):
        r = self.r3("r3_ok", task="inbox/hopper-%s.yaml" % name)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("Nothing written", r.stdout)
        self.assertIn("max_tokens 1024", r.stdout)
        self.assertFalse(self.exists(os.path.join("work", "hopper-%s-FIXTURE" % name)))
        self.assertFalse(os.path.exists(self.docker_log), "the cage was started")

    def altered(self, name):
        with open(os.path.join(self.root, "inbox", "hopper_%s_test.py" % name), "a") as fh:
            fh.write("# changed\n")
        r = self.r3("r3_ok", task="inbox/hopper-%s.yaml" % name)
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("does not match its expect_sha256", r.stdout)

    def test_paste_a_reply_meant_for_another_task_writes_nothing(self):
        self.wrong_reply("paste")

    def test_seed_a_reply_meant_for_another_task_writes_nothing(self):
        self.wrong_reply("seed")

    def test_board_a_reply_meant_for_another_task_writes_nothing(self):
        self.wrong_reply("board")

    def test_paste_an_altered_contract_is_refused_before_any_call(self):
        self.altered("paste")

    def test_seed_an_altered_contract_is_refused_before_any_call(self):
        self.altered("seed")

    def test_board_an_altered_contract_is_refused_before_any_call(self):
        self.altered("board")


if __name__ == "__main__":
    unittest.main()
