import unittest

from ai.random_safe_strategy import RandomSafeStrategy
from ai.survival_strategy import SurvivalStrategy
from game.board import GameBoard


class TestOpponentStrategies(unittest.TestCase):

    def setUp(self):
        self.board = GameBoard(
            """|       |
|   A   |
|   a   |
|       |
|     B |
|     b |
|   *   |"""
        )

    def test_random_strategy_returns_valid_direction(self):
        strategy = RandomSafeStrategy(seed=1)

        move = strategy.choose_move(
            self.board,
            "A",
        )

        self.assertTrue(
            self.board.valid_moves("A")[move]
        )

    def test_survival_strategy_avoids_body(self):
        strategy = SurvivalStrategy()

        move = strategy.choose_move(
            self.board,
            "A",
        )

        self.assertNotEqual(move, "down")


if __name__ == "__main__":
    unittest.main()