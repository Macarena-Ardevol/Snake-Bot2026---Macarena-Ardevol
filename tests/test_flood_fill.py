import unittest

from ai.flood_fill import FloodFill
from game.board import GameBoard


class TestFloodFill(unittest.TestCase):

    def setUp(self):

        board = """|       |
|   A   |
|       |
|   *   |
|       |
|     B |
|       |"""

        self.board = GameBoard(board)
        self.flood = FloodFill()

    def test_reachable_area(self):

        area = self.flood.reachable_area(
            self.board,
            (0, 0)
        )

        self.assertGreater(area, 20)


if __name__ == "__main__":
    unittest.main()