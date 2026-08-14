import unittest

from ai.evaluator import MoveEvaluator
from game.board import GameBoard


class TestMoveEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = MoveEvaluator()

    def test_invalid_move_receives_minimum_score(self):
        board = GameBoard(
            """|       |
|   A   |
|   a   |
|       |
|     B |
|       |
|       |"""
        )

        score = self.evaluator.score_move(
            board,
            "A",
            "down",
        )

        self.assertEqual(
            score,
            MoveEvaluator.INVALID_MOVE_SCORE,
        )

    def test_eating_food_is_rewarded(self):
        board = GameBoard(
            """|       |
|   A*  |
|       |
|       |
|     B |
|       |
|       |"""
        )

        right_score = self.evaluator.score_move(
            board,
            "A",
            "right",
        )

        left_score = self.evaluator.score_move(
            board,
            "A",
            "left",
        )

        self.assertGreater(
            right_score,
            left_score,
        )

    def test_enemy_proximity_is_penalized(self):
        board = GameBoard(
            """|       |
|       |
|  A B  |
|       |
|   *   |
|       |
|       |"""
        )

        right_score = self.evaluator.score_move(
            board,
            "A",
            "right",
        )

        left_score = self.evaluator.score_move(
            board,
            "A",
            "left",
        )

        self.assertLess(
            right_score,
            left_score,
        )

    def test_analysis_total_matches_score(self):
        board = GameBoard(
            """|       |
|   A*  |
|       |
|       |
|     B |
|       |
|       |"""
        )

        analysis = self.evaluator.analyze_move(
            board,
            "A",
            "right",
        )

        score = self.evaluator.score_move(
            board,
            "A",
            "right",
        )

        self.assertEqual(
            analysis["total"],
            score,
        )

        self.assertIn("space", analysis)
        self.assertIn("food", analysis)
        self.assertIn("territory", analysis)


if __name__ == "__main__":
    unittest.main()