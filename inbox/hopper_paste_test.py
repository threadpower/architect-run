"""The contract for the Hopper slice "pasted list": one pasted block of text becomes a list of idea texts.

Written by Jeremy and Claude before any build. The builder never sees this file and may not
write it. It is hash-pinned in the task. One module is under test. It is pure: it never reads
a file, opens a socket, starts a process or looks at the clock.

  paste.py   split_lines(text) -> list of str

Each line of the paste is one idea. A line ends at \\n, \\r\\n or \\r. Spaces and tabs at the two
ends of a line are dropped. A line with nothing left is dropped. Nothing else about a line is
changed, the order is kept, and a line that appears twice appears twice in the result.
"""
import unittest

from paste import split_lines


class Split(unittest.TestCase):
    def test_one_idea_a_line_in_order(self):
        self.assertEqual(split_lines("Wolf at the laundromat\nMoth to a porch light\nRaven with a paper crown"),
                         ["Wolf at the laundromat", "Moth to a porch light", "Raven with a paper crown"])

    def test_a_single_line_is_a_single_idea(self):
        self.assertEqual(split_lines("Wolf at the laundromat"), ["Wolf at the laundromat"])
        self.assertEqual(split_lines("Wolf at the laundromat\n"), ["Wolf at the laundromat"])

    def test_windows_and_old_mac_line_endings(self):
        self.assertEqual(split_lines("one\r\ntwo\rthree\nfour"), ["one", "two", "three", "four"])

    def test_blank_lines_and_lines_of_only_spaces_are_dropped(self):
        self.assertEqual(split_lines("\n\none\n   \n\t\ntwo\n\n"), ["one", "two"])

    def test_nothing_in_gives_nothing_out(self):
        for text in ("", "   ", "\n\n\n", " \r\n\t\r\n"):
            self.assertEqual(split_lines(text), [])

    def test_spaces_and_tabs_at_the_ends_of_a_line_are_dropped(self):
        self.assertEqual(split_lines("  one  \n\ttwo\t\n three"), ["one", "two", "three"])

    def test_nothing_inside_a_line_is_changed(self):
        self.assertEqual(split_lines("Squatch  on a\tskateboard"), ["Squatch  on a\tskateboard"])
        self.assertEqual(split_lines("- a bullet\n1. a number\n• a dot\n\"quoted\""),
                         ["- a bullet", "1. a number", "• a dot", "\"quoted\""])
        self.assertEqual(split_lines("SQUATCH\nsquatch\nCafé ☕"), ["SQUATCH", "squatch", "Café ☕"])

    def test_a_repeated_line_is_kept_both_times(self):
        self.assertEqual(split_lines("same\nother\nsame"), ["same", "other", "same"])

    def test_the_answer_is_always_a_list_of_str(self):
        got = split_lines("one\ntwo")
        self.assertIsInstance(got, list)
        self.assertTrue(all(isinstance(line, str) for line in got))


if __name__ == "__main__":
    unittest.main()
