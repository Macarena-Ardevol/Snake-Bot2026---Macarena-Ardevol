import unittest

from game.board import GameBoard


class TestClone(unittest.TestCase):

    def test_clone(self):

        board = """|       |
|   A   |
|       |
|   *   |
|       |
|     B |
|       |"""

        original = GameBoard(board)

        copy = original.clone()

        self.assertIsNot(original, copy)

        self.assertEqual(original.grid, copy.grid)

        self.assertEqual(original.food, copy.food)

        self.assertEqual(original.snakes, copy.snakes)


if __name__ == "__main__":
    unittest.main()