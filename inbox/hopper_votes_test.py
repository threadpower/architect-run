"""The contract for the first Hopper slice: from votes to tonight's list.

Written by Jeremy and Claude before any build. The builder never sees this file and may
not write it. It is hash-pinned in the task. Three modules are under test, and none of
them may read a file, open a socket, start a process or look at the clock: every time
is passed in.

  votes.py      apply_tap(votes, idea_id, user, at) -> dict
  scores.py     vote_score(times, now, half_life_days=14) -> float
  shortlist.py  next_state(state, score, bar) -> str
                pick_for_night(ideas, n=5) -> list of idea ids
"""
import unittest
from datetime import datetime, timedelta, timezone

from scores import vote_score
from shortlist import next_state, pick_for_night
from votes import apply_tap

NOW = datetime(2026, 12, 8, 22, 0, tzinfo=timezone.utc)


def days_ago(n):
    return NOW - timedelta(days=n)


class Taps(unittest.TestCase):
    """Spec: one vote per person per idea; a second tap removes it."""

    def test_a_tap_adds_one_vote_with_its_time(self):
        self.assertEqual(apply_tap({}, 7, "josh", NOW), {(7, "josh"): NOW})

    def test_a_second_tap_by_the_same_person_removes_it_and_never_adds(self):
        once = apply_tap({}, 7, "josh", days_ago(1))
        self.assertEqual(apply_tap(once, 7, "josh", NOW), {})

    def test_a_third_tap_votes_again_with_the_new_time(self):
        votes = {}
        for when in (days_ago(2), days_ago(1), NOW):
            votes = apply_tap(votes, 7, "josh", when)
        self.assertEqual(votes, {(7, "josh"): NOW})

    def test_people_and_ideas_do_not_disturb_each_other(self):
        votes = apply_tap({}, 7, "josh", NOW)
        votes = apply_tap(votes, 7, "steph", NOW)
        votes = apply_tap(votes, 8, "josh", NOW)
        votes = apply_tap(votes, 7, "steph", NOW)
        self.assertEqual(votes, {(7, "josh"): NOW, (8, "josh"): NOW})

    def test_the_votes_passed_in_are_not_changed(self):
        before = {(7, "josh"): days_ago(1)}
        apply_tap(before, 7, "josh", NOW)
        apply_tap(before, 9, "steph", NOW)
        self.assertEqual(before, {(7, "josh"): days_ago(1)})


class Score(unittest.TestCase):
    """Spec: vote score is the sum of votes, each decayed with a 14-day half-life."""

    def test_no_votes_is_zero(self):
        self.assertEqual(vote_score([], NOW), 0.0)

    def test_a_vote_cast_now_counts_one(self):
        self.assertAlmostEqual(vote_score([NOW], NOW), 1.0)

    def test_a_vote_one_half_life_old_counts_half(self):
        self.assertAlmostEqual(vote_score([days_ago(14)], NOW), 0.5)
        self.assertAlmostEqual(vote_score([days_ago(28)], NOW), 0.25)

    def test_votes_add_up(self):
        self.assertAlmostEqual(vote_score([NOW, days_ago(14), days_ago(28)], NOW), 1.75)

    def test_two_votes_from_one_day_ago_fall_just_short_of_two(self):
        score = vote_score([days_ago(1), days_ago(1)], NOW)
        self.assertLess(score, 2.0)
        self.assertAlmostEqual(score, 2 * 0.5 ** (1 / 14), places=9)

    def test_the_half_life_is_a_number_passed_in(self):
        self.assertAlmostEqual(vote_score([days_ago(7)], NOW, half_life_days=7), 0.5)

    def test_decay_is_continuous_not_stepped_by_day(self):
        self.assertAlmostEqual(vote_score([NOW - timedelta(hours=12)], NOW), 0.5 ** (0.5 / 14), places=9)


class Shortlisted(unittest.TestCase):
    """Spec: an idea is Shortlisted when its vote score clears the bar. The bar is a config number."""

    def test_submitted_becomes_shortlisted_at_or_above_the_bar(self):
        self.assertEqual(next_state("Submitted", 2.0, 2.0), "Shortlisted")
        self.assertEqual(next_state("Submitted", 2.3, 2.0), "Shortlisted")

    def test_submitted_stays_submitted_below_the_bar(self):
        self.assertEqual(next_state("Submitted", 1.95, 2.0), "Submitted")

    def test_shortlisted_stays_shortlisted_when_its_score_decays(self):
        self.assertEqual(next_state("Shortlisted", 0.4, 2.0), "Shortlisted")

    def test_a_score_never_moves_any_other_state(self):
        for state in ("Generated", "Reviewed", "Promoted", "Parked"):
            self.assertEqual(next_state(state, 99.0, 2.0), state)
            self.assertEqual(next_state(state, 0.0, 2.0), state)


class Tonight(unittest.TestCase):
    """Spec: the runner takes the top N shortlisted ideas by score. It ignores parked ideas."""

    def idea(self, ident, state, score, age_days):
        return {"id": ident, "state": state, "score": score, "created": days_ago(age_days)}

    def test_only_shortlisted_ideas_are_picked(self):
        ideas = [self.idea(1, "Submitted", 9.0, 1), self.idea(2, "Shortlisted", 2.1, 1),
                 self.idea(3, "Parked", 9.0, 1), self.idea(4, "Promoted", 9.0, 1),
                 self.idea(5, "Generated", 9.0, 1), self.idea(6, "Reviewed", 9.0, 1)]
        self.assertEqual(pick_for_night(ideas), [2])

    def test_highest_score_first_and_at_most_n(self):
        ideas = [self.idea(i, "Shortlisted", float(i), 1) for i in range(1, 9)]
        self.assertEqual(pick_for_night(ideas), [8, 7, 6, 5, 4])
        self.assertEqual(pick_for_night(ideas, n=2), [8, 7])

    def test_a_tie_goes_to_the_older_idea_then_the_lower_id(self):
        ideas = [self.idea(10, "Shortlisted", 3.0, 2), self.idea(11, "Shortlisted", 3.0, 5),
                 self.idea(13, "Shortlisted", 3.0, 2), self.idea(12, "Shortlisted", 4.0, 1)]
        self.assertEqual(pick_for_night(ideas), [12, 11, 10, 13])

    def test_nothing_shortlisted_is_an_empty_night(self):
        self.assertEqual(pick_for_night([]), [])
        self.assertEqual(pick_for_night([self.idea(1, "Submitted", 5.0, 1)]), [])

    def test_the_list_passed_in_is_not_reordered(self):
        ideas = [self.idea(1, "Shortlisted", 1.0, 1), self.idea(2, "Shortlisted", 2.0, 1)]
        pick_for_night(ideas)
        self.assertEqual([i["id"] for i in ideas], [1, 2])


if __name__ == "__main__":
    unittest.main()
