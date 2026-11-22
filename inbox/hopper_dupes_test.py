"""The contract for the Hopper slice "duplicates": is a team submission a copy of a team idea.

Written by Jeremy and Claude before any build. The builder never sees this file and may not
write it. It is hash-pinned in the task. One module is under test. It is pure: it never reads
a file, opens a socket, starts a process or looks at the clock.

  dupes.py   text_hash(text) -> str
             find_duplicate(text, source, ideas) -> an idea id, or None

text_hash   the SHA-256 of the text's UTF-8 bytes as 64 lowercase hex characters. The text is
            hashed exactly as given: no trimming, no change of case, no other clean-up.
ideas       the ideas already stored, each a dict with id, text_hash and source
Returns the id of the stored team idea a new team submission copies, or None when the
submission is accepted. Only a team submission against a team idea is ever a duplicate.
"""
import hashlib
import unittest

from dupes import find_duplicate, text_hash


def stored(ident, text, source="team"):
    return {"id": ident, "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(), "source": source}


IDEAS = [stored(11, "Squatch on a skateboard"), stored(12, "Moth to a porch light", "scout"),
         stored(13, "Raven with a paper crown", "public"), stored(14, "Wolf at the laundromat")]


class Hash(unittest.TestCase):
    def test_it_is_sha256_of_the_utf8_bytes_in_lowercase_hex(self):
        self.assertEqual(text_hash("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(text_hash(""), hashlib.sha256(b"").hexdigest())
        self.assertEqual(text_hash("Café ☕"), hashlib.sha256("Café ☕".encode("utf-8")).hexdigest())

    def test_the_text_is_hashed_exactly_as_given(self):
        base = text_hash("Squatch on a skateboard")
        for other in ("squatch on a skateboard", "Squatch on a skateboard ", " Squatch on a skateboard",
                      "Squatch  on a skateboard", "Squatch on a skateboard\n", "Squatch on a skateboard."):
            self.assertNotEqual(text_hash(other), base)


class Duplicate(unittest.TestCase):
    def test_a_team_submission_that_exactly_matches_a_team_idea_gets_that_ideas_id(self):
        self.assertEqual(find_duplicate("Squatch on a skateboard", "team", IDEAS), 11)
        self.assertEqual(find_duplicate("Wolf at the laundromat", "team", IDEAS), 14)

    def test_the_answer_is_an_id_not_a_link(self):
        self.assertIsInstance(find_duplicate("Squatch on a skateboard", "team", IDEAS), int)

    def test_a_near_match_is_not_a_duplicate(self):
        for text in ("squatch on a skateboard", "Squatch on a skateboard ", "Squatch on a skateboard!"):
            self.assertIsNone(find_duplicate(text, "team", IDEAS))

    def test_a_new_idea_is_not_a_duplicate(self):
        self.assertIsNone(find_duplicate("Owl with a library card", "team", IDEAS))
        self.assertIsNone(find_duplicate("Squatch on a skateboard", "team", []))

    def test_a_scout_or_public_twin_of_a_team_idea_is_accepted(self):
        for source in ("scout", "public", "seed", "warp", "transcript", "luma"):
            self.assertIsNone(find_duplicate("Squatch on a skateboard", source, IDEAS))

    def test_a_team_twin_of_a_scout_or_public_idea_is_accepted(self):
        self.assertIsNone(find_duplicate("Moth to a porch light", "team", IDEAS))
        self.assertIsNone(find_duplicate("Raven with a paper crown", "team", IDEAS))

    def test_when_the_same_text_is_stored_twice_the_lowest_id_is_given(self):
        twice = [stored(31, "Same"), stored(7, "Same"), stored(19, "Same", "scout")]
        self.assertEqual(find_duplicate("Same", "team", twice), 7)

    def test_the_list_passed_in_is_not_changed(self):
        before = [dict(i) for i in IDEAS]
        find_duplicate("Squatch on a skateboard", "team", IDEAS)
        self.assertEqual(IDEAS, before)


if __name__ == "__main__":
    unittest.main()
