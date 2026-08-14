import unittest

from game.board import GameBoard
from game.simulator import BoardSimulator


class TestBoardSimulator(unittest.TestCase):

    def setUp(self):
        self.simulator = BoardSimulator()

    def test_moves_head_to_empty_cell(self):
        board = GameBoard(
            """|       |
|   A   |
|   a   |
|       |
|     B |
|       |
|       |"""
        )

        simulated = self.simulator.simulate_move(
            board,
            "A",
            "right",
        )

        self.assertIsNotNone(simulated)
        self.assertEqual(
            simulated.my_head("A"),
            (1, 4),
        )

        # El tablero original no debe modificarse.
        self.assertEqual(
            board.my_head("A"),
            (1, 3),
        )

    def test_eating_food_keeps_growth(self):
        board = GameBoard(
            """|       |
|   A*  |
|   a   |
|       |
|     B |
|       |
|       |"""
        )

        simulated = self.simulator.simulate_move(
            board,
            "A",
            "right",
        )

        self.assertIsNotNone(simulated)
        self.assertNotIn(
            (1, 4),
            simulated.food,
        )
        self.assertIn(
            (1, 3),
            simulated.snakes["A"]["body"],
        )

    def test_invalid_move_returns_none(self):
        board = GameBoard(
            """|       |
|   A   |
|   a   |
|       |
|     B |
|       |
|       |"""
        )

        simulated = self.simulator.simulate_move(
            board,
            "A",
            "down",
        )

        self.assertIsNone(simulated)


if __name__ == "__main__":
    unittest.main()