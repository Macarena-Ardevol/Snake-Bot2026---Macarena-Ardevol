import unittest

from ai.baseline_strategy import BaselineStrategy
from game.board import GameBoard
from local_game.timed_strategy import TimedStrategy


class TestTimedStrategy(unittest.TestCase):

    def test_records_decision_time(self):
        board = GameBoard(
            """|       |
|   A   |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        strategy = TimedStrategy(
            BaselineStrategy()
        )

        move = strategy.choose_move(
            board,
            "A",
        )

        self.assertIn(
            move,
            board.DIRECTIONS,
        )

        self.assertEqual(
            len(strategy.decision_times),
            1,
        )

        self.assertGreaterEqual(
            strategy.decision_times[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()