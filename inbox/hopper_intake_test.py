"""The contract for the Hopper slice "intake rules": is one submission accepted, and if not, why.

Written by Jeremy and Claude before any build. The builder never sees this file and may not
write it. It is hash-pinned in the task. One module is under test. It is pure: it never reads
a file, opens a socket, starts a process or looks at the clock.

  intake.py   check_submission(submission, caller, roster) -> None or a reason string

submission  a dict with text, lane, source and submitter (other keys may be present)
caller      {"kind": "person", "email": ...} or {"kind": "service", "name": ...}
roster      a set of the sign-in emails of the people who are allowed in
Returns None when the submission is accepted. Otherwise one of these reasons, the first that
applies in this order: not_on_roster, wrong_submitter, empty_text, bad_lane, bad_source.
"""
import unittest

from intake import check_submission

ROSTER = {"jeremy@threadpower.com", "josh@threadpower.com", "steph@threadpower.com"}
JOSH = {"kind": "person", "email": "josh@threadpower.com"}
WARP = {"kind": "service", "name": "warp"}


def sub(**changes):
    base = {"text": "A wolf howling at a disco ball", "lane": "apparel", "source": "team",
            "submitter": "josh@threadpower.com"}
    base.update(changes)
    return base


class Accepted(unittest.TestCase):
    def test_a_roster_member_submitting_as_themself(self):
        self.assertIsNone(check_submission(sub(), JOSH, ROSTER))

    def test_every_lane_and_no_lane_at_all(self):
        for lane in ("apparel", "content", "story", None):
            self.assertIsNone(check_submission(sub(lane=lane), JOSH, ROSTER))
        without = sub()
        del without["lane"]
        self.assertIsNone(check_submission(without, JOSH, ROSTER))

    def test_every_source_in_the_spec(self):
        for source in ("team", "seed", "warp", "scout", "transcript", "luma", "public"):
            self.assertIsNone(check_submission(sub(source=source), JOSH, ROSTER))

    def test_a_service_submitting_under_its_own_system_name(self):
        self.assertIsNone(check_submission(sub(source="warp", submitter="warp"), WARP, ROSTER))

    def test_a_service_submitting_as_itself_may_use_any_source(self):
        self.assertIsNone(check_submission(sub(source="team", submitter="warp"), WARP, ROSTER))
        self.assertIsNone(check_submission(sub(source="scout", submitter="warp"), WARP, ROSTER))

    def test_optional_fields_do_not_matter(self):
        extra = sub(source_ref="meeting 2026-12-01", scout_motive=None, image="ref.jpg")
        self.assertIsNone(check_submission(extra, JOSH, ROSTER))


class Refused(unittest.TestCase):
    def test_a_person_who_is_not_on_the_roster(self):
        stranger = {"kind": "person", "email": "someone@example.com"}
        self.assertEqual(check_submission(sub(submitter="someone@example.com"), stranger, ROSTER), "not_on_roster")

    def test_a_service_key_submitting_as_a_person(self):
        self.assertEqual(check_submission(sub(source="warp"), WARP, ROSTER), "wrong_submitter")

    def test_a_service_submitting_under_another_name(self):
        self.assertEqual(check_submission(sub(source="warp", submitter="scout"), WARP, ROSTER), "wrong_submitter")

    def test_a_person_submitting_as_someone_else(self):
        self.assertEqual(check_submission(sub(submitter="steph@threadpower.com"), JOSH, ROSTER), "wrong_submitter")

    def test_text_with_nothing_in_it(self):
        for text in ("", "   ", "\n\t "):
            self.assertEqual(check_submission(sub(text=text), JOSH, ROSTER), "empty_text")

    def test_a_lane_that_is_not_one_of_the_three_in_lowercase(self):
        for lane in ("Apparel", "APPAREL", "labs", "", " apparel"):
            self.assertEqual(check_submission(sub(lane=lane), JOSH, ROSTER), "bad_lane")

    def test_a_source_that_is_not_in_the_spec(self):
        for source in ("Team", "website", "", None):
            self.assertEqual(check_submission(sub(source=source), JOSH, ROSTER), "bad_source")


class Order(unittest.TestCase):
    def test_the_closed_door_comes_before_everything_else(self):
        stranger = {"kind": "person", "email": "someone@example.com"}
        bad = sub(text="", lane="Labs", source="website", submitter="josh@threadpower.com")
        self.assertEqual(check_submission(bad, stranger, ROSTER), "not_on_roster")

    def test_then_the_submitter_then_text_then_lane_then_source(self):
        self.assertEqual(check_submission(sub(text="", lane="Labs", source="x", submitter="warp"), JOSH, ROSTER), "wrong_submitter")
        self.assertEqual(check_submission(sub(text="", lane="Labs", source="x"), JOSH, ROSTER), "empty_text")
        self.assertEqual(check_submission(sub(lane="Labs", source="x"), JOSH, ROSTER), "bad_lane")
        self.assertEqual(check_submission(sub(source="x"), JOSH, ROSTER), "bad_source")

    def test_nothing_passed_in_is_changed(self):
        submission, roster = sub(), set(ROSTER)
        check_submission(submission, JOSH, roster)
        self.assertEqual(submission, sub())
        self.assertEqual(roster, ROSTER)


if __name__ == "__main__":
    unittest.main()
