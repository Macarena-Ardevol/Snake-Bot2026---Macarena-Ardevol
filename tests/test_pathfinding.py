import unittest

from ai.pathfinding import PathFinder
from game.board import GameBoard


class TestPathFinding(unittest.TestCase):

    def setUp(self):

        board = """|       |
|   A   |
|       |
|   *   |
|       |
|     B |
|       |"""

        self.board = GameBoard(board)

        self.pathfinder = PathFinder()

    def test_shortest_path(self):

        start = self.board.my_head("A")

        goal = self.board.food[0]

        path = self.pathfinder.shortest_path(
            self.board,
            start,
            goal
        )

        self.assertEqual(path[0], start)

        self.assertEqual(path[-1], goal)

        self.assertGreater(len(path), 0)


if __name__ == "__main__":
    unittest.main()