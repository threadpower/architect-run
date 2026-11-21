"""The contract for the toy task r3-trio. It exists so the three-file shape can be dry-run.
It has nothing to do with Hopper. The builder never sees this file."""
import unittest

from add import add
from neg import neg
from twice import twice


class Trio(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_neg(self):
        self.assertEqual(neg(4), -4)

    def test_twice(self):
        self.assertEqual(twice(21), 42)


if __name__ == "__main__":
    unittest.main()
