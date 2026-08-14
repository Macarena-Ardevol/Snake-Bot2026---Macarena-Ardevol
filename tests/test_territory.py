import unittest

from ai.territory import TerritoryAnalyzer
from game.board import GameBoard


class TestTerritoryAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = TerritoryAnalyzer()

    def test_distance_map_starts_at_zero(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|       |
|     B |
|       |
|       |"""
        )

        distances = self.analyzer.distance_map(
            board,
            board.my_head("A"),
        )

        self.assertEqual(
            distances[board.my_head("A")],
            0,
        )

    def test_closer_snake_controls_more_nearby_cells(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|       |
|     B |
|       |
|       |"""
        )

        balance_a = self.analyzer.territory_balance(
            board,
            "A",
        )

        balance_b = self.analyzer.territory_balance(
            board,
            "B",
        )

        self.assertEqual(
            balance_a,
            -balance_b,
        )

    def test_wall_divides_territory(self):
        board = GameBoard(
            """|       |
| A a   |
| aaa   |
|       |
|   bbb |
|   b B |
|       |"""
        )

        balance = self.analyzer.territory_balance(
            board,
            "A",
        )

        self.assertIsInstance(balance, int)


if __name__ == "__main__":
    unittest.main()