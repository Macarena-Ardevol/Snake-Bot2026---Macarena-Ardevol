import json
import tempfile
import threading
import unittest
from pathlib import Path

from bot.game_recorder import GameRecorder


class TestGameRecorder(unittest.TestCase):

    def test_concurrent_games_keep_turns_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = GameRecorder(directory)
            threads = []
            for game_index in range(10):
                for turn_index in range(3):
                    thread = threading.Thread(target=recorder.record_turn, kwargs={
                        "game_id": f"game_{game_index}",
                        "data": {"side": "A", "remaining_moves": 10 - turn_index},
                        "direction": "right",
                        "analysis": {"right": {"total": game_index}},
                    })
                    threads.append(thread)
                    thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(set(recorder.games), {f"game_{i}" for i in range(10)})
            self.assertTrue(all(len(turns) == 3 for turns in recorder.games.values()))

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
                compute_level="busy",
                decision_metrics={
                    "decision_ms": 12.5,
                    "receive_to_send_ms": 14.0,
                    "pending_decisions": 4,
                },
                decision_context={
                    "target_food": {"status": "known", "food": [0, 3]},
                },
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
            self.assertEqual(saved_data["schema_version"], 2)
            self.assertEqual(saved_data["turns"][0]["schema_version"], 2)
            self.assertEqual(saved_data["turns"][0]["compute_level"], "busy")
            self.assertEqual(saved_data["turns"][0]["decision_metrics"]["pending_decisions"], 4)


if __name__ == "__main__":
    unittest.main()
