"""The contract for the Hopper slice "the Board": which ideas the Board shows, and in what order.

Written by Jeremy and Claude before any build. The builder never sees this file and may not
write it. It is hash-pinned in the task. One module is under test. It is pure: it never reads
a file, opens a socket, starts a process or looks at the clock.

  board.py   board_rows(ideas, lane=None, source=None) -> list of the idea dicts to show

ideas    a list of dicts, each with id, state, lane, source and created (a timezone-aware
         datetime), plus whatever else the page needs (text, score and so on)
lane     None for every lane, or one lane to show
source   None for every source, or one source to show
The Board shows the ideas whose state is Submitted, Shortlisted, Generated or Reviewed, newest
first. Two ideas created at the same moment go higher id first. The dicts come back as they
were given, the same objects, in a new list.
"""
import unittest
from datetime import datetime, timedelta, timezone

from board import board_rows

T0 = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)


def idea(ident, state="Submitted", lane="apparel", source="team", minutes=0, **more):
    row = {"id": ident, "state": state, "lane": lane, "source": source, "created": T0 + timedelta(minutes=minutes),
           "text": "idea %d" % ident, "score": 0.0}
    row.update(more)
    return row


def ids(rows):
    return [row["id"] for row in rows]


class States(unittest.TestCase):
    def test_the_four_open_states_are_shown(self):
        rows = [idea(1, "Submitted", minutes=1), idea(2, "Shortlisted", minutes=2), idea(3, "Generated", minutes=3),
                idea(4, "Reviewed", minutes=4)]
        self.assertEqual(ids(board_rows(rows)), [4, 3, 2, 1])

    def test_parked_and_promoted_are_not_on_the_board(self):
        rows = [idea(1, minutes=1), idea(2, "Parked", minutes=2), idea(3, "Promoted", minutes=3), idea(4, minutes=4)]
        self.assertEqual(ids(board_rows(rows)), [4, 1])

    def test_a_state_in_any_other_spelling_is_not_shown(self):
        rows = [idea(1, "submitted"), idea(2, "SUBMITTED"), idea(3, "Draft"), idea(4, None)]
        self.assertEqual(board_rows(rows), [])

    def test_an_empty_bank_is_an_empty_board(self):
        self.assertEqual(board_rows([]), [])


class Order(unittest.TestCase):
    def test_newest_first(self):
        rows = [idea(1, minutes=5), idea(2, minutes=50), idea(3, minutes=-10), idea(4, minutes=20)]
        self.assertEqual(ids(board_rows(rows)), [2, 4, 1, 3])

    def test_ideas_created_at_the_same_moment_go_higher_id_first(self):
        rows = [idea(7), idea(9), idea(8), idea(3, minutes=1)]
        self.assertEqual(ids(board_rows(rows)), [3, 9, 8, 7])

    def test_score_does_not_change_the_order(self):
        rows = [idea(1, minutes=1, score=9.5), idea(2, minutes=2, score=0.0)]
        self.assertEqual(ids(board_rows(rows)), [2, 1])

    def test_the_same_moment_in_another_time_zone_is_the_same_moment(self):
        central = timezone(timedelta(hours=-6))
        rows = [idea(1, created=T0.astimezone(central)), idea(2, created=T0), idea(3, created=T0 + timedelta(seconds=1))]
        self.assertEqual(ids(board_rows(rows)), [3, 2, 1])


class Filters(unittest.TestCase):
    ROWS = [idea(1, lane="apparel", source="team", minutes=1), idea(2, lane="content", source="team", minutes=2),
            idea(3, lane="story", source="scout", minutes=3), idea(4, lane=None, source="warp", minutes=4),
            idea(5, lane="apparel", source="scout", minutes=5), idea(6, "Parked", lane="apparel", source="team", minutes=6)]

    def test_no_filter_shows_every_lane_and_source_and_ideas_with_no_lane(self):
        self.assertEqual(ids(board_rows(self.ROWS)), [5, 4, 3, 2, 1])
        self.assertEqual(ids(board_rows(self.ROWS, None, None)), [5, 4, 3, 2, 1])

    def test_filter_by_lane(self):
        self.assertEqual(ids(board_rows(self.ROWS, lane="apparel")), [5, 1])
        self.assertEqual(ids(board_rows(self.ROWS, lane="story")), [3])

    def test_filter_by_source(self):
        self.assertEqual(ids(board_rows(self.ROWS, source="team")), [2, 1])
        self.assertEqual(ids(board_rows(self.ROWS, source="warp")), [4])

    def test_both_filters_together(self):
        self.assertEqual(ids(board_rows(self.ROWS, lane="apparel", source="scout")), [5])
        self.assertEqual(board_rows(self.ROWS, lane="content", source="scout"), [])

    def test_a_filter_matches_exactly_and_an_unknown_value_shows_nothing(self):
        self.assertEqual(board_rows(self.ROWS, lane="Apparel"), [])
        self.assertEqual(board_rows(self.ROWS, lane="labs"), [])
        self.assertEqual(board_rows(self.ROWS, source="website"), [])


class Untouched(unittest.TestCase):
    def test_the_rows_come_back_as_the_same_dicts_with_everything_on_them(self):
        a, b = idea(1, minutes=1, score=1.5, extra="kept"), idea(2, minutes=2)
        got = board_rows([a, b])
        self.assertIs(got[0], b)
        self.assertIs(got[1], a)
        self.assertEqual(got[1]["extra"], "kept")

    def test_the_list_passed_in_is_not_reordered_or_changed(self):
        rows = [idea(1, minutes=1), idea(2, "Parked", minutes=2), idea(3, minutes=3)]
        before = list(rows)
        got = board_rows(rows)
        self.assertEqual(rows, before)
        self.assertIsNot(got, rows)


if __name__ == "__main__":
    unittest.main()
