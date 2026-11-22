"""The contract for the Hopper slice "seed plan": which lines of a seed file would be added, and which skipped.

Written by Jeremy and Claude before any build. The builder never sees this file and may not
write it. It is hash-pinned in the task. One module is under test. It is pure: it never reads
a file, opens a socket, starts a process or looks at the clock. It plans; it stores nothing.
The plan is the dry run, and the same plan is what a real run would then store.

  seed.py   plan_seed(lines, existing_hashes) -> {"add": [...], "skip": [...]}

lines             the idea texts from the seed file, in order, one str each
existing_hashes   a set of the text hashes of the seed ideas already stored
add               a list of {"text": ..., "text_hash": ...} in file order
skip              a list of {"text": ..., "reason": ...} in file order
The hash is the SHA-256 of the text's UTF-8 bytes as 64 lowercase hex characters, of the text
exactly as given. The reasons are empty_text, already_imported and repeated_in_file, and the
first that applies in that order is the one given.
"""
import hashlib
import unittest

from seed import plan_seed


def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


LINES = ["Wolf at the laundromat", "Moth to a porch light", "Raven with a paper crown"]


class Plan(unittest.TestCase):
    def test_a_first_run_adds_every_line_in_order(self):
        got = plan_seed(LINES, set())
        self.assertEqual(got, {"add": [{"text": t, "text_hash": h(t)} for t in LINES], "skip": []})

    def test_the_keys_are_add_then_skip_and_both_are_lists(self):
        got = plan_seed([], set())
        self.assertEqual(list(got), ["add", "skip"])
        self.assertEqual(got, {"add": [], "skip": []})

    def test_running_it_twice_adds_nothing_the_second_time(self):
        first = plan_seed(LINES, set())
        stored = {row["text_hash"] for row in first["add"]}
        second = plan_seed(LINES, stored)
        self.assertEqual(second["add"], [])
        self.assertEqual(second["skip"], [{"text": t, "reason": "already_imported"} for t in LINES])

    def test_only_the_new_lines_of_a_longer_file_are_added(self):
        got = plan_seed(LINES + ["Owl with a library card"], {h(LINES[0]), h(LINES[2])})
        self.assertEqual([row["text"] for row in got["add"]], ["Moth to a porch light", "Owl with a library card"])
        self.assertEqual(got["skip"], [{"text": LINES[0], "reason": "already_imported"},
                                       {"text": LINES[2], "reason": "already_imported"}])

    def test_a_line_repeated_in_the_file_is_added_once(self):
        got = plan_seed(["same", "other", "same", "same"], set())
        self.assertEqual([row["text"] for row in got["add"]], ["same", "other"])
        self.assertEqual(got["skip"], [{"text": "same", "reason": "repeated_in_file"},
                                       {"text": "same", "reason": "repeated_in_file"}])

    def test_a_line_already_stored_is_already_imported_every_time_it_appears(self):
        got = plan_seed(["same", "same"], {h("same")})
        self.assertEqual(got, {"add": [], "skip": [{"text": "same", "reason": "already_imported"},
                                                   {"text": "same", "reason": "already_imported"}]})

    def test_text_is_hashed_exactly_as_given(self):
        got = plan_seed(["Squatch", "squatch", "Squatch ", "Café ☕"], {h("squatch")})
        self.assertEqual([row["text"] for row in got["add"]], ["Squatch", "Squatch ", "Café ☕"])
        self.assertEqual(got["add"][2]["text_hash"], h("Café ☕"))
        self.assertEqual(got["skip"], [{"text": "squatch", "reason": "already_imported"}])

    def test_an_empty_line_is_skipped_and_never_hashed_into_the_plan(self):
        got = plan_seed(["", "   ", "\t", "real"], {h(""), h("   ")})
        self.assertEqual(got["add"], [{"text": "real", "text_hash": h("real")}])
        self.assertEqual(got["skip"], [{"text": "", "reason": "empty_text"}, {"text": "   ", "reason": "empty_text"},
                                       {"text": "\t", "reason": "empty_text"}])

    def test_nothing_passed_in_is_changed(self):
        lines, stored = list(LINES), {h(LINES[0])}
        plan_seed(lines, stored)
        self.assertEqual(lines, LINES)
        self.assertEqual(stored, {h(LINES[0])})

    def test_a_frozen_set_and_a_tuple_work_too(self):
        got = plan_seed(tuple(LINES), frozenset({h(LINES[1])}))
        self.assertEqual([row["text"] for row in got["add"]], [LINES[0], LINES[2]])


if __name__ == "__main__":
    unittest.main()
