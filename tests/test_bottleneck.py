import unittest

from ai.bottleneck import BottleneckAnalyzer
from game.board import GameBoard


class TestBottleneckAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = BottleneckAnalyzer()

    def test_returns_numeric_score(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertIsInstance(
            score,
            (int, float),
        )

    def test_small_trapped_region_is_penalized(self):
        board = GameBoard(
            """|aaaaaaa|
|aA    a|
|aaaaa a|
|      a|
|  *   a|
|    B a|
|aaaaaaa|"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertLess(score, 0)


if __name__ == "__main__":
    unittest.main()