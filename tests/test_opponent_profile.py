import tempfile
import unittest
from pathlib import Path

from ai.opponent_memory import OpponentMemory
from ai.opponent_profile import OpponentProfile


class TestOpponentProfile(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        file_path = (
            Path(self.temp_dir.name)
            / "memory.json"
        )

        self.memory = OpponentMemory(
            str(file_path)
        )

        self.profile = OpponentProfile(
            self.memory
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_unknown_with_little_information(self):
        self.memory.record_move(
            "enemy",
            "left",
            moved_toward_food=True,
        )

        result = self.profile.classify(
            "enemy"
        )

        self.assertEqual(
            result,
            "unknown",
        )

    def test_detects_food_hunter(self):
        for _ in range(20):
            self.memory.record_move(
                "enemy",
                "left",
                moved_toward_food=True,
                contested_food=True,
            )

        result = self.profile.classify(
            "enemy"
        )

        self.assertEqual(
            result,
            "food_hunter",
        )

    def test_detects_aggressive_player(self):
        for _ in range(20):
            self.memory.record_move(
                "enemy",
                "left",
                moved_toward_us=True,
            )

        result = self.profile.classify(
            "enemy"
        )

        self.assertEqual(
            result,
            "aggressive",
        )

    def test_detects_defensive_player(self):
        for _ in range(20):
            self.memory.record_move(
                "enemy",
                "left",
                moved_toward_food=False,
                moved_toward_us=False,
                contested_food=False,
            )

        result = self.profile.classify(
            "enemy"
        )

        self.assertEqual(
            result,
            "defensive",
        )


if __name__ == "__main__":
    unittest.main()