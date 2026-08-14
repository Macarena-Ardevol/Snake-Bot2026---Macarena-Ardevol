import json
import tempfile
import unittest
from pathlib import Path

from bot.game_recorder import GameRecorder


class TestGameRecorder(unittest.TestCase):

    def test_records_and_saves_game(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = GameRecorder(directory)

            recorder.record_turn(
                game_id="game_test",
                data={
                    "board": "| A* |",
                    "side": "A",
                    "remaining_moves": 10,
                    "score_1": 0,
                    "score_2": 0,
                },
                direction="right",
                analysis={
                    "right": {
                        "total": 100,
                    }
                },
                mode="balanced",
            )

            file_path = recorder.finish_game(
                "game_test",
                {
                    "game_id": "game_test",
                    "player_1": "bot_a",
                    "player_2": "bot_b",
                    "score_1": 101,
                    "score_2": 0,
                    "winner": "bot_a",
                    "board": "|  A |",
                    "remaining_moves": 0,
                },
            )

            self.assertTrue(file_path.exists())

            saved_data = json.loads(
                Path(file_path).read_text(
                    encoding="utf-8",
                )
            )

            self.assertEqual(
                saved_data["winner"],
                "bot_a",
            )

            self.assertEqual(
                len(saved_data["turns"]),
                1,
            )

            self.assertEqual(
                saved_data["turns"][0]["chosen_direction"],
                "right",
            )

            self.assertEqual(
                saved_data["turns"][0]["mode"],
                "balanced",
            )

            self.assertEqual(
                saved_data["bot_side"],
                "A",
            )


if __name__ == "__main__":
    unittest.main()
