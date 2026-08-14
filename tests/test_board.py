import unittest

from game.board import GameBoard


class TestBoard(unittest.TestCase):

    def setUp(self):
        board = """|       |
|   A   |
|   a*  |
|       |
|     B |
|     b |
|       |"""

        self.board = GameBoard(board)

    def test_valid_moves(self):
        moves = self.board.valid_moves("A")

        self.assertTrue(moves["up"])
        self.assertTrue(moves["left"])
        self.assertTrue(moves["right"])
        self.assertFalse(moves["down"])

    def test_food_is_free(self):
        self.assertTrue(self.board.is_free(2, 4))

    def test_snake_body_is_not_free(self):
        self.assertFalse(self.board.is_free(2, 3))

    def test_position_outside_is_not_free(self):
        self.assertFalse(self.board.is_free(-1, 0))

    def test_next_position(self):
        position = self.board.next_position((1, 3), "right")

        self.assertEqual(position, (1, 4))

    def test_invalid_direction(self):
        with self.assertRaises(ValueError):
            self.board.next_position((1, 3), "diagonal")


if __name__ == "__main__":
    unittest.main()