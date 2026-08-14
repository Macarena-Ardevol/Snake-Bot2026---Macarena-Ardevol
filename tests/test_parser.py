import unittest

from game.parser import BoardParser


class TestBoardParser(unittest.TestCase):

    def test_ignores_server_trailing_newline(self):
        parser = BoardParser(
            "| A |\n| * |\n| B |\n"
        )

        self.assertEqual(parser.grid, [" A ", " * ", " B "])

    def test_rejects_non_rectangular_board(self):
        with self.assertRaises(ValueError):
            BoardParser("| A |\n| B  |")

    def setUp(self):
        self.board = """|       |
|   A   |
|   a   |
| *     |
|     B |
|     b |
|       |"""

        self.parser = BoardParser(self.board)

    def test_find_food(self):
        food = self.parser.find_food()

        self.assertEqual(food, [(3, 1)])

    def test_find_snakes(self):
        snakes = self.parser.find_snakes()

        self.assertEqual(snakes["A"]["head"], (1, 3))
        self.assertEqual(snakes["A"]["body"], [(2, 3)])

        self.assertEqual(snakes["B"]["head"], (4, 5))
        self.assertEqual(snakes["B"]["body"], [(5, 5)])

    def test_grid_dimensions(self):
        self.assertEqual(len(self.parser.grid), 7)
        self.assertEqual(len(self.parser.grid[0]), 7)


if __name__ == "__main__":
    unittest.main()
