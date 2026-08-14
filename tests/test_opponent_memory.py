import tempfile
import unittest
from pathlib import Path

from ai.opponent_memory import OpponentMemory


class TestOpponentMemory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        file_path = (
            Path(self.temp_dir.name)
            / "opponents.json"
        )

        self.memory = OpponentMemory(
            str(file_path)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_opponent_has_neutral_direction_probability(self):
        probability = (
            self.memory.direction_probability(
                "enemy",
                "left",
            )
        )

        self.assertEqual(
            probability,
            0.25,
        )

    def test_records_direction(self):
        self.memory.record_move(
            "enemy",
            "left",
        )

        probability = (
            self.memory.direction_probability(
                "enemy",
                "left",
            )
        )

        self.assertEqual(
            probability,
            1.0,
        )

    def test_records_food_aggression(self):
        self.memory.record_move(
            "enemy",
            "right",
            moved_toward_food=True,
        )

        aggression = (
            self.memory.food_aggression(
                "enemy"
            )
        )

        self.assertEqual(
            aggression,
            1.0,
        )

    def test_records_game_result(self):
        self.memory.record_game(
            "enemy",
            won=True,
        )

        stats = self.memory.get_stats(
            "enemy"
        )

        self.assertEqual(
            stats["games"],
            1,
        )

        self.assertEqual(
            stats["wins_against"],
            1,
        )

    def test_memory_persists(self):
        self.memory.record_move(
            "enemy",
            "down",
        )

        second_memory = OpponentMemory(
            str(self.memory.file_path)
        )

        stats = second_memory.get_stats(
            "enemy"
        )

        self.assertEqual(
            stats["directions"]["down"],
            1,
        )

    def test_records_head_aggression(self):
        self.memory.record_move(
            "enemy",
            "left",
            moved_toward_us=True,
        )

        self.assertEqual(
            self.memory.head_aggression("enemy"),
            1.0,
        )


    def test_records_food_contest(self):
        self.memory.record_move(
            "enemy",
            "right",
            contested_food=True,
        )

        self.assertEqual(
            self.memory.contest_aggression("enemy"),
            1.0,
        )

    def test_confidence_starts_at_zero(self):
        confidence = self.memory.confidence(
            "enemy"
        )

        self.assertEqual(
            confidence,
            0.0,
        )


    def test_confidence_increases_with_observations(self):
        for _ in range(10):
            self.memory.record_move(
                "enemy",
                "left",
            )

        confidence = self.memory.confidence(
            "enemy"
        )

        self.assertEqual(
            confidence,
            0.5,
        )


    def test_confidence_is_capped_at_one(self):
        for _ in range(30):
            self.memory.record_move(
                "enemy",
                "left",
            )

        confidence = self.memory.confidence(
            "enemy"
        )

        self.assertEqual(
            confidence,
            1.0,
        )

    def test_records_correct_prediction(self):
        self.memory.record_prediction(
            opponent="enemy",
            predicted_direction="left",
            actual_direction="left",
        )

        accuracy = (
            self.memory.prediction_accuracy(
                "enemy"
            )
        )

        self.assertEqual(
            accuracy,
            1.0,
        )


    def test_records_wrong_prediction(self):
        self.memory.record_prediction(
            opponent="enemy",
            predicted_direction="left",
            actual_direction="right",
        )

        accuracy = (
            self.memory.prediction_accuracy(
                "enemy"
            )
        )

        self.assertEqual(
            accuracy,
            0.0,
        )


    def test_prediction_accuracy_without_data(self):
        accuracy = (
            self.memory.prediction_accuracy(
                "enemy"
            )
        )

        self.assertIsNone(
            accuracy
        )


if __name__ == "__main__":
    unittest.main()