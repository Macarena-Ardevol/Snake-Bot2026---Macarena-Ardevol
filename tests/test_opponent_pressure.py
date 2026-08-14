import unittest

from ai.opponent_pressure import OpponentPressureAnalyzer
from game.board import GameBoard


class TestOpponentPressureAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = OpponentPressureAnalyzer()

    def test_open_enemy_has_low_pressure_score(self):
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

        self.assertLess(score, 800)

    def test_enemy_with_one_exit_is_rewarded(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|   bbb |
|   bB  |
|   bbb |
|   *   |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertGreater(score, 0)

    def test_trapped_enemy_receives_large_bonus(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|   bbb |
|   bBb |
|   bbb |
|   *   |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertGreaterEqual(score, 5_000)


if __name__ == "__main__":
    unittest.main()