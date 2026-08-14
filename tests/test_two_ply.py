import unittest

from ai.two_ply import TwoPlyAnalyzer
from game.board import GameBoard


class TestTwoPlyAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = TwoPlyAnalyzer()

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
            "right",
        )

        self.assertIsInstance(
            score,
            (int, float),
        )

    def test_invalid_move_has_minimum_score(self):
        board = GameBoard(
            """|       |
|   A   |
|   a   |
|   *   |
|     B |
|       |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
            "down",
        )

        self.assertEqual(
            score,
            -1_000_000,
        )


if __name__ == "__main__":
    unittest.main()