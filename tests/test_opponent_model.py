import unittest

from ai.opponent_model import OpponentModel
from game.board import GameBoard


class TestOpponentModel(unittest.TestCase):

    def setUp(self):
        self.model = OpponentModel()

    def test_returns_ranked_legal_moves(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|   *   |
|     B |
|       |
|       |"""
        )

        moves = self.model.ranked_moves(
            board,
            "B",
        )

        self.assertGreater(
            len(moves),
            0,
        )

        for direction, score in moves:
            self.assertIn(
                direction,
                board.DIRECTIONS,
            )

            self.assertIsInstance(
                score,
                (int, float),
            )

    def test_predicts_adjacent_food_when_safe(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|    *B |
|       |
|       |
|       |"""
        )

        move = self.model.predicted_move(
            board,
            "B",
        )

        self.assertEqual(
            move,
            "left",
        )

    def test_returns_none_when_enemy_is_trapped(self):
        board = GameBoard(
            """|       |
| A     |
|       |
|   bbb |
|   bBb |
|   bbb |
|   *   |"""
        )

        move = self.model.predicted_move(
            board,
            "B",
        )

        self.assertIsNone(move)

    def test_memory_changes_food_aggression(self):
        import tempfile
        from pathlib import Path

        from ai.opponent_memory import OpponentMemory

        with tempfile.TemporaryDirectory() as directory:
            memory = OpponentMemory(
                str(
                    Path(directory)
                    / "memory.json"
                )
            )

            for _ in range(10):
                memory.record_move(
                    "aggressive_enemy",
                    "left",
                    moved_toward_food=True,
                )

            for _ in range(10):
                memory.record_move(
                    "defensive_enemy",
                    "left",
                    moved_toward_food=False,
                )

            aggressive_model = OpponentModel(
                memory=memory
            )

            aggressive_model.set_opponent(
                "aggressive_enemy"
            )

            defensive_model = OpponentModel(
                memory=memory
            )

            defensive_model.set_opponent(
                "defensive_enemy"
            )

            self.assertGreater(
                aggressive_model._food_aggression(),
                defensive_model._food_aggression(),
            )

    def test_head_aggression_changes_prediction_score(self):
        import tempfile
        from pathlib import Path

        from ai.opponent_memory import OpponentMemory

        with tempfile.TemporaryDirectory() as directory:
            memory = OpponentMemory(
                str(
                    Path(directory)
                    / "memory.json"
                )
            )

            for _ in range(10):
                memory.record_move(
                    "aggressive_enemy",
                    "left",
                    moved_toward_us=True,
                )

            for _ in range(10):
                memory.record_move(
                    "calm_enemy",
                    "left",
                    moved_toward_us=False,
                )

            aggressive_model = OpponentModel(
                memory=memory
            )
            aggressive_model.set_opponent(
                "aggressive_enemy"
            )

            calm_model = OpponentModel(
                memory=memory
            )
            calm_model.set_opponent(
                "calm_enemy"
            )

        self.assertGreater(
            aggressive_model._head_aggression(),
            calm_model._head_aggression(),
        )


    def test_contest_aggression_is_loaded(self):
        import tempfile
        from pathlib import Path

        from ai.opponent_memory import OpponentMemory

        with tempfile.TemporaryDirectory() as directory:
            memory = OpponentMemory(
                str(
                    Path(directory)
                    / "memory.json"
                )
            )

            for _ in range(8):
                memory.record_move(
                    "enemy",
                    "right",
                    contested_food=True,
                )

            model = OpponentModel(
                memory=memory
            )
            model.set_opponent(
                "enemy"
            )

            self.assertGreater(
                model._contest_aggression(),
                0.5,
            )

    def test_low_sample_keeps_model_close_to_neutral(self):
        import tempfile
        from pathlib import Path

        from ai.opponent_memory import OpponentMemory

        with tempfile.TemporaryDirectory() as directory:
            memory = OpponentMemory(
                str(
                    Path(directory)
                    / "memory.json"
                )
            )

            memory.record_move(
                "enemy",
                "left",
                moved_toward_food=True,
            )

            model = OpponentModel(
                memory=memory
            )

            model.set_opponent(
                "enemy"
            )

            aggression = model._food_aggression()

            self.assertGreater(
                aggression,
                0.5,
            )

            self.assertLess(
                aggression,
                0.6,
            )

    def test_prediction_confidence_starts_at_zero(self):
        model = OpponentModel()

        self.assertEqual(
            model.prediction_confidence(),
            0.0,
        )

    def test_prediction_confidence_grows_with_success(self):
        import tempfile
        from pathlib import Path

        from ai.opponent_memory import OpponentMemory

        with tempfile.TemporaryDirectory() as directory:
            memory = OpponentMemory(
                str(
                    Path(directory)
                    / "memory.json"
                )
            )

            for _ in range(20):
                memory.record_prediction(
                    opponent="enemy",
                    predicted_direction="left",
                    actual_direction="left",
                )

            model = OpponentModel(
                memory=memory
            )

            model.set_opponent(
                "enemy"
            )

            confidence = (
                model.prediction_confidence()
            )

            self.assertEqual(
                confidence,
                1.0,
            )


if __name__ == "__main__":
    unittest.main()