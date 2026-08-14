import unittest

from ai.flood_fill import FloodFill
from ai.pathfinding import PathFinder
from game.board import GameBoard
from ai.territory import TerritoryAnalyzer


class TestAICache(unittest.TestCase):

    def setUp(self):
        PathFinder.clear_cache()
        FloodFill.clear_cache()
        TerritoryAnalyzer.clear_cache()

        self.board = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

    def test_pathfinder_cache_keeps_same_result(self):
        finder = PathFinder()

        start = self.board.my_head("A")
        goal = self.board.food[0]

        first = finder.shortest_path(
            self.board,
            start,
            goal,
        )

        second = finder.shortest_path(
            self.board,
            start,
            goal,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_flood_fill_cache_keeps_same_result(self):
        flood = FloodFill()

        first = flood.reachable_area(
            self.board,
            (0, 0),
        )

        second = flood.reachable_area(
            self.board,
            (0, 0),
        )

        self.assertEqual(
            first,
            second,
        )

    def test_different_board_does_not_reuse_wrong_result(self):
        flood = FloodFill()

        open_area = flood.reachable_area(
            self.board,
            (0, 0),
        )

        blocked_board = GameBoard(
            """|       |
| Aaaaa |
| aaaaa |
| aaaaa |
|     B |
|       |
|   *   |"""
        )

        blocked_area = flood.reachable_area(
            blocked_board,
            (0, 0),
        )

        self.assertNotEqual(
            open_area,
            blocked_area,
        )


    def test_territory_cache_keeps_same_result(self):
        territory = TerritoryAnalyzer()

        first = territory.territory_balance(
            self.board,
            "A",
        )

        second = territory.territory_balance(
            self.board,
            "A",
        )

        self.assertEqual(
            first,
            second,
        )

if __name__ == "__main__":
    unittest.main()