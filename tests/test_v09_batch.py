"""v0.9: the December batch of three Hopper slices, on paper. Dry runs only: no socket, no real container, $0.

Three contracts Grok accepted on Nov 22, in the order they will be built: intake, duplicates, the
package. There is no solution to any of them in this repository, and one test here keeps it that way.
Nothing in this file runs a builder or a reviewer.
"""
import hashlib
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import HERE, read  # noqa: E402
from test_v07_three import ThreeBase  # noqa: E402

ACCEPTED = {   # name: (the hash Grok accepted, the impl line)
    "intake": ("f1a6223ff5f97b8e52bfb035aa533f3cc38d3f801669528531c094b63937d12f", "intake.py"),
    "dupes": ("7a152ee9833d220e6bc9f2332d4ff2070697f5fbaad648138abc67f27de63d86", "dupes.py"),
    "package": ("3c6c5c4ed9ffc3a13b57b660ae1ec2349ea2d2d3041bb1f2902fd367688107fe", "package.py filenames.py confirm.py"),
}
SPEC = os.path.join(HERE, "inbox", "hopper-h1.md")


def inbox(name):
    return os.path.join(HERE, "inbox", name)


def prose_of(name):
    return [ln for ln in read(inbox("hopper-%s.yaml" % name)).splitlines() if ln.startswith("prose: ")][0]


def sent(name):
    """The excerpt lines a reviewer would be sent: everything that is not a comment."""
    return [ln.strip() for ln in read(inbox("hopper-%s.spec.txt" % name)).splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def plain(text):            # the same rule r4.py uses
    return " ".join(re.sub(r"[*`\\_]", "", text).split())


class Contracts(unittest.TestCase):
    def test_each_contract_is_the_file_grok_accepted(self):
        for name, (want, impl) in ACCEPTED.items():
            with open(inbox("hopper_%s_test.py" % name), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), want, name)
            task = read(inbox("hopper-%s.yaml" % name))
            for line in ("id: hopper-%s" % name, "kind: r3", "impl: %s" % impl,
                         "test: inbox/hopper_%s_test.py" % name, "expect_sha256: %s" % want):
                self.assertIn("\n%s\n" % line, task, "%s: %s" % (name, line))
            for forbidden in ("model:", "max_tokens:", "tools:", "retries:", "rounds:", "reviewer:"):
                self.assertNotIn("\n" + forbidden, task, name)

    def test_no_solution_to_any_of_the_three_is_on_the_box(self):
        names = ("intake.py", "dupes.py", "package.py", "filenames.py", "confirm.py")
        markers = ("def check_submission", "def text_hash", "def find_duplicate", "def build_package",
                   "def numbered", "def confirm_text")
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".git", "work", "outbox", "budget", "log", "keys", "__pycache__")]
            for f in files:
                self.assertNotIn(f, names, os.path.join(base, f))
                if f.endswith((".py", ".json", ".yaml", ".md", ".sh", ".txt")) and f != "test_v09_batch.py":
                    text = read(os.path.join(base, f))
                    for marker in markers:
                        self.assertNotIn(marker, text, "%s in %s" % (marker, f))

    def test_the_prose_tells_the_builder_the_rules_without_the_tests(self):
        wants = {
            "intake": ("check_submission(submission, caller, roster)", "not_on_roster", "wrong_submitter", "empty_text",
                       "bad_lane", "bad_source", "the first that applies in this order",
                       "a service's source does not have to match its name"),
            "dupes": ("text_hash(text)", "find_duplicate(text, source, ideas)", "exactly as given", "the lowest id",
                      "not a link"),
            "package": ("build_package(promotion, idea, concepts, reference_images, names)", "numbered(prefix, paths)",
                        "confirm_text(concept_count)", "No concepts attached.", "raise ValueError",
                        "whether or not it is in names", "evidence_url is always None", "whatever the concepts are"),
        }
        for name, needed in wants.items():
            prose = prose_of(name)
            self.assertLess(len(prose), 4000, name)
            for want in needed:
                self.assertIn(want, prose, "%s: %s" % (name, want))
            for absent in ("assertEqual", "assertRaises", "unittest", "_test", "threadpower.com", "laundromat",
                           "Squatch", "ghost@"):
                self.assertNotIn(absent, prose, "%s: %s" % (name, absent))

    def test_the_sentences_grok_cut_reach_neither_the_builder_nor_the_reviewer(self):
        cut = {
            "intake": ("pasted list", "split by line", "exact duplicate", "duplicate of a team idea"),
            "dupes": ("One vote per person", "second tap"),
            "package": ("package_path", "warp_ref", "warp_outcome", "posts the package", "HTTP post", "retries",
                        "reaches Warp"),
        }
        for name, phrases in cut.items():
            seen = prose_of(name) + "\n" + "\n".join(sent(name))
            for phrase in phrases:
                self.assertNotIn(phrase, seen, "%s: %s" % (name, phrase))

    def test_each_excerpt_carries_the_rules_jeremy_set(self):
        for name, opening in (("intake", "Rules for intake, set by Jeremy on Nov 21."),
                              ("dupes", "Rules for duplicates, set by Jeremy on Nov 21."),
                              ("package", "Rules for the package, set by Jeremy on Nov 21.")):
            self.assertEqual(len([ln for ln in sent(name) if ln.startswith(opening)]), 1, name)
        self.assertIn("A submitter or promoter with an @ in it is a person", "\n".join(sent("package")))
        self.assertNotIn("never contain", "\n".join(sent("package")))

    @unittest.skipUnless(os.path.exists(SPEC), "the Hopper spec is not in this copy")
    def test_every_excerpt_line_is_in_the_hopper_spec_word_for_word(self):
        spec = plain(read(SPEC))
        for name in ACCEPTED:
            for n, para in enumerate(sent(name), 1):
                self.assertIn(plain(para), spec, "hopper-%s.spec.txt line %d: %s..." % (name, n, para[:50]))


class DryRuns(ThreeBase):
    """One dry run a test: each test starts from its own copy and its own fixture ledger."""

    def wrong_reply(self, name, fixture):
        r = self.r3(fixture, task="inbox/hopper-%s.yaml" % name)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("Nothing written", r.stdout)
        self.assertFalse(self.exists(os.path.join("work", "hopper-%s-FIXTURE" % name)))
        self.assertFalse(os.path.exists(self.docker_log), "the cage was started")
        return r

    def altered(self, name):
        with open(os.path.join(self.root, "inbox", "hopper_%s_test.py" % name), "a") as fh:
            fh.write("# changed\n")
        r = self.r3("r3_ok", task="inbox/hopper-%s.yaml" % name)
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("does not match its expect_sha256", r.stdout)

    def test_intake_a_reply_meant_for_another_task_writes_nothing(self):
        self.assertIn("max_tokens 1024", self.wrong_reply("intake", "r3_ok").stdout)

    def test_duplicates_a_reply_meant_for_another_task_writes_nothing(self):
        self.assertIn("max_tokens 1024", self.wrong_reply("dupes", "r3_ok").stdout)

    def test_package_a_reply_meant_for_another_task_writes_nothing(self):
        self.assertIn("max_tokens 4096", self.wrong_reply("package", "r3t_ok").stdout)

    def test_intake_an_altered_contract_is_refused_before_any_call(self):
        self.altered("intake")

    def test_duplicates_an_altered_contract_is_refused_before_any_call(self):
        self.altered("dupes")

    def test_package_an_altered_contract_is_refused_before_any_call(self):
        self.altered("package")


if __name__ == "__main__":
    unittest.main()
