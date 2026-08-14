import unittest

from ai.strategy import SnakeStrategy
from game.board import GameBoard


class TestStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = SnakeStrategy()

    def test_strategy_moves_toward_adjacent_food(self):
        board = GameBoard(
            """|       |
|   A*  |
|       |
|       |
|     B |
|       |
|       |"""
        )

        move = self.strategy.choose_move(
            board,
            "A",
        )

        self.assertEqual(move, "right")

    def test_strategy_avoids_occupied_cell(self):
        board = GameBoard(
            """|       |
|   A   |
|   a   |
|       |
|     B |
|       |
|   *   |"""
        )

        move = self.strategy.choose_move(
            board,
            "A",
        )

        self.assertNotEqual(move, "down")

    def test_uses_defensive_mode_when_winning_near_end(self):
        board = GameBoard(
            """|       |
|   A   |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        self.strategy.choose_move(
            board=board,
            side="A",
            remaining_moves=20,
            my_score=500,
            enemy_score=100,
        )

        self.assertEqual(
            self.strategy.current_mode,
            "defensive",
        )

    def test_uses_aggressive_mode_when_losing_near_end(self):
        board = GameBoard(
            """|       |
|   A   |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        self.strategy.choose_move(
            board=board,
            side="A",
            remaining_moves=20,
            my_score=100,
            enemy_score=500,
        )

        self.assertEqual(
            self.strategy.current_mode,
            "aggressive",
        )

    def test_uses_balanced_mode_normally(self):
        board = GameBoard(
            """|       |
|   A   |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        self.strategy.choose_move(
            board=board,
            side="A",
            remaining_moves=200,
            my_score=100,
            enemy_score=100,
        )

        self.assertEqual(
            self.strategy.current_mode,
            "balanced",
        )

    def test_uses_defensive_mode_when_winning_near_end(self):
        mode = self.strategy._choose_mode(
            remaining_moves=20,
            my_score=500,
            enemy_score=300,
        )

        self.assertEqual(
            mode,
            "defensive",
        )


    def test_uses_aggressive_mode_when_losing_near_end(self):
            mode = self.strategy._choose_mode(
                remaining_moves=20,
                my_score=200,
                enemy_score=500,
            )

            self.assertEqual(
                mode,
                "aggressive",
            )


    def test_uses_aggressive_mode_when_tied_near_end(self):
            mode = self.strategy._choose_mode(
                remaining_moves=20,
                my_score=500,
                enemy_score=500,
            )

            self.assertEqual(
                mode,
                "aggressive",
            )


    def test_uses_balanced_mode_during_normal_game(self):
            mode = self.strategy._choose_mode(
                remaining_moves=200,
                my_score=500,
                enemy_score=450,
            )

            self.assertEqual(
                mode,
                "balanced",
            )


    def test_protects_large_lead(self):
            mode = self.strategy._choose_mode(
                remaining_moves=150,
                my_score=1200,
                enemy_score=500,
            )

            self.assertEqual(
                mode,
                "defensive",
            )

    def test_strategy_still_returns_valid_move_with_selective_search(self):
        board = GameBoard(
            """|       |
    |   A   |
    |       |
    |   *   |
    |       |
    |     B |
    |       |"""
        )

        move = self.strategy.choose_move(
            board=board,
            side="A",
            remaining_moves=200,
            my_score=0,
            enemy_score=0,
        )

        self.assertIn(
            move,
            board.DIRECTIONS,
        )

        self.assertTrue(
            board.valid_moves("A")[move]
        )

    def test_forced_safe_move_is_selected(self):
        board = GameBoard(
            """|Aa     |
    |       |
    |   *   |
    |       |
    |     B |
    |     b |
    |       |"""
        )

        move = self.strategy.choose_move(
            board=board,
            side="A",
            remaining_moves=100,
            my_score=0,
            enemy_score=0,
        )

        self.assertEqual(
            move,
            "down",
        )

        self.assertTrue(
            board.valid_moves("A")[move]
        )

    def test_detects_critical_position_when_losing(self):
        board = GameBoard(
            """|       |
    | A     |
    |       |
    |   *   |
    |     B |
    |       |
    |       |"""
        )

        candidates = [
            ("right", 1000),
            ("down", 700),
        ]

        result = self.strategy._is_critical_position(
            board=board,
            side="A",
            remaining_moves=150,
            my_score=100,
            enemy_score=500,
            candidates=candidates,
        )

        self.assertTrue(result)


    def test_detects_critical_position_near_end(self):
        board = GameBoard(
            """|       |
    | A     |
    |       |
    |   *   |
    |     B |
    |       |
    |       |"""
        )

        candidates = [
            ("right", 1000),
            ("down", 0),
        ]

        result = self.strategy._is_critical_position(
            board=board,
            side="A",
            remaining_moves=20,
            my_score=500,
            enemy_score=400,
            candidates=candidates,
        )

        self.assertTrue(result)
        