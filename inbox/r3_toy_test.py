"""The contract for task r3-toy. Written by Jeremy and Claude before the run.
The builder never sees this file and may not write it. It is hash-pinned in r3-toy.yaml."""
import unittest

from slug import slugify


class Slugify(unittest.TestCase):
    def test_plain_words(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_runs_of_other_characters_become_one_hyphen(self):
        self.assertEqual(slugify("The Forge:  Amp & Reverb!"), "the-forge-amp-reverb")

    def test_no_hyphen_at_either_end(self):
        self.assertEqual(slugify("  --Wolf #4--  "), "wolf-4")

    def test_digits_are_kept(self):
        self.assertEqual(slugify("H1 then S1, 2026"), "h1-then-s1-2026")

    def test_nothing_usable_gives_an_empty_string(self):
        self.assertEqual(slugify(""), "")
        self.assertEqual(slugify("!!! ??? ..."), "")

    def test_non_ascii_letters_are_separators(self):
        self.assertEqual(slugify("Café Olé"), "caf-ol")

    def test_returns_text(self):
        self.assertIsInstance(slugify("a"), str)


if __name__ == "__main__":
    unittest.main()
