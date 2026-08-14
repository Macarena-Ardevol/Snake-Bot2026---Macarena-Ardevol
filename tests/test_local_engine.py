import unittest

from ai.baseline_strategy import BaselineStrategy
from local_game.engine import LocalSnakeGame


class TestLocalSnakeGame(unittest.TestCase):

    def test_board_uses_server_format(self):
        game = LocalSnakeGame(
            strategy_a=BaselineStrategy(),
            strategy_b=BaselineStrategy(),
            rows=7,
            cols=7,
            seed=1,
        )

        board = game.board_text()
        rows = board.splitlines()

        self.assertEqual(len(rows), 7)
        self.assertTrue(all(row.startswith("|") for row in rows))
        self.assertTrue(all(row.endswith("|") for row in rows))
        self.assertIn("A", board)
        self.assertIn("B", board)

    def test_match_finishes(self):
        game = LocalSnakeGame(
            strategy_a=BaselineStrategy(),
            strategy_b=BaselineStrategy(),
            max_moves=30,
            seed=1,
        )

        result = game.play()

        self.assertLessEqual(result.turns, 30)
        self.assertIn(result.winner, ("A", "B", None))

    def test_scores_are_integers(self):
        game = LocalSnakeGame(
            strategy_a=BaselineStrategy(),
            strategy_b=BaselineStrategy(),
            max_moves=20,
            seed=2,
        )

        result = game.play()

        self.assertIsInstance(result.score_a, int)
        self.assertIsInstance(result.score_b, int)


if __name__ == "__main__":
    unittest.main()