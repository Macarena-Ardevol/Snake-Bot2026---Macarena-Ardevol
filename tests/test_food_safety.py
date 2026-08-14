import unittest

from ai.food_safety import FoodSafetyAnalyzer
from game.board import GameBoard


class TestFoodSafetyAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = FoodSafetyAnalyzer()

    def test_ignores_move_without_food(self):
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

        self.assertEqual(score, 0)

    def test_safe_food_is_rewarded(self):
        board = GameBoard(
            """|       |
| A*    |
|       |
|       |
|     B |
|       |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
            "right",
        )

        self.assertGreater(score, 0)

    def test_dangerous_food_is_penalized(self):
        board = GameBoard(
            """|aaaaaaa|
|aA*aaaa|
|a  aaaa|
|aaaaaaa|
|       |
|     B |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
            "right",
        )

        self.assertLess(score, 0)


if __name__ == "__main__":
    unittest.main()