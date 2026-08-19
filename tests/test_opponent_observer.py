import unittest

from ai.opponent_observer import OpponentObserver
from game.board import GameBoard


class TestOpponentObserver(unittest.TestCase):

    def setUp(self):
        self.observer = OpponentObserver()

    def test_infers_left_move(self):
        previous = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        current = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|    B  |
|       |
|       |"""
        )

        direction = self.observer.infer_direction(
            previous,
            current,
            "A",
        )

        self.assertEqual(
            direction,
            "left",
        )

    def test_detects_move_toward_food(self):
        previous = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        current = GameBoard(
            """|       |
| A     |
|       |
|   *B  |
|       |
|       |
|       |"""
        )

        result = self.observer.moved_toward_food(
            previous,
            current,
            "A",
        )

        self.assertTrue(result)

    def test_returns_none_without_normal_movement(self):
        previous = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        current = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        direction = self.observer.infer_direction(
            previous,
            current,
            "A",
        )

        self.assertIsNone(direction)

    def test_detects_move_toward_us(self):
        previous = GameBoard(
            """|       |
    | A     |
    |       |
    |       |
    |     B |
    |       |
    |   *   |"""
        )

        current = GameBoard(
            """|       |
    | A     |
    |       |
    |    B  |
    |       |
    |       |
    |   *   |"""
        )

        result = self.observer.moved_toward_us(
            previous,
            current,
            "A",
        )

        self.assertTrue(result)

    def test_food_observations_are_false_without_food(self):
        previous = GameBoard(
            """|       |
| A     |
|       |
|       |
|     B |
|       |
|       |"""
        )
        current = GameBoard(
            """|       |
| A     |
|       |
|    B  |
|       |
|       |
|       |"""
        )
        self.assertFalse(self.observer.moved_toward_food(previous, current, "A"))
        self.assertFalse(self.observer.contested_food(previous, current, "A"))

    def test_detects_contested_food_when_enemy_approaches_reachable_food(self):
        previous = GameBoard(
            """|       |
| A     |
|   *   |
|     B |
|       |
|       |
|       |"""
        )
        current = GameBoard(
            """|       |
| A     |
|   *B  |
|       |
|       |
|       |
|       |"""
        )
        self.assertTrue(self.observer.contested_food(previous, current, "A"))

    def test_food_is_not_contested_when_enemy_moves_away(self):
        previous = GameBoard(
            """|       |
| A     |
|   *   |
|    B  |
|       |
|       |
|       |"""
        )
        current = GameBoard(
            """|       |
| A     |
|   *   |
|     B |
|       |
|       |
|       |"""
        )
        self.assertFalse(self.observer.contested_food(previous, current, "A"))


if __name__ == "__main__":
    unittest.main()
