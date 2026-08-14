import unittest

from ai.lookahead import LookaheadAnalyzer
from game.board import GameBoard


class TestLookaheadAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = LookaheadAnalyzer()

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

    def test_rewards_trapped_enemy(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|    bbb|
|    bBb|
|    bbb|
|   *   |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertEqual(
            score,
            3_000,
        )

    def test_enemy_food_response_is_considered(self):
        board_with_food = GameBoard(
            """|       |
| A     |
|       |
|    *B |
|       |
|       |
|       |"""
        )

        board_without_food = GameBoard(
            """|       |
| A     |
|       |
|     B |
|       |
|       |
|       |"""
        )

        score_with_food = self.analyzer.score(
            board_with_food,
            "A",
        )

        score_without_food = self.analyzer.score(
            board_without_food,
            "A",
        )

        self.assertLessEqual(
            score_with_food,
            score_without_food,
        )

    def test_prediction_keeps_numeric_result(self):
        board = GameBoard(
            """|       |
    | A     |
    |       |
    |   * B |
    |       |
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


    def test_trapped_enemy_still_receives_bonus(self):
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

        self.assertEqual(
            score,
            3_000,
        )


if __name__ == "__main__":
    unittest.main()