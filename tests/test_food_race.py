import unittest

from ai.food_race import FoodRaceAnalyzer
from game.board import GameBoard


class TestFoodRaceAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = FoodRaceAnalyzer()

    def test_rewards_food_closer_to_us(self):
        board = GameBoard(
            """|       |
| A *   |
|       |
|       |
|      B|
|       |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertGreater(score, 0)

    def test_penalizes_food_closer_to_enemy(self):
        board = GameBoard(
            """|       |
|A      |
|       |
|       |
|   * B |
|       |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertLess(score, 0)

    def test_returns_zero_without_food(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|       |
|     B |
|       |
|       |"""
        )

        score = self.analyzer.score(
            board,
            "A",
        )

        self.assertEqual(score, 0)


if __name__ == "__main__":
    unittest.main()