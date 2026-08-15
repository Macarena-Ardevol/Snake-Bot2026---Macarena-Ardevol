import json
import tempfile
import unittest
from pathlib import Path

from ai.strategy import SnakeStrategy
from game.board import GameBoard
from learning.learning_advisor import LearningAdvisor
from learning.match_analyzer import MatchAnalyzer
from learning.selfplay_dataset import SelfPlayDatasetGenerator


class TestSelfPlayDatasetGenerator(unittest.TestCase):

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def generator(self, opponents=("baseline",)) -> SelfPlayDatasetGenerator:
        return SelfPlayDatasetGenerator(
            output_root=self.root / "selfplay",
            opponents=opponents,
            rows=7,
            cols=7,
            max_moves=4,
            food_count=1,
        )

    @staticmethod
    def records(summary: dict) -> list[dict]:
        directory = Path(summary["dataset_path"])
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]

    def test_generates_zero_matches(self):
        summary = self.generator().generate(0, base_seed=7)

        self.assertEqual(summary["matches"], 0)
        self.assertEqual(summary["seeds"], [])
        self.assertTrue(Path(summary["dataset_path"]).is_dir())
        self.assertEqual(self.records(summary), [])

    def test_generates_one_complete_match(self):
        summary = self.generator().generate(1, base_seed=7)
        record = self.records(summary)[0]

        self.assertEqual(summary["matches"], 1)
        self.assertEqual(record["source"], "selfplay")
        self.assertEqual(record["bot_side"], "A")
        self.assertIn(record["winner"], ("advanced", "local:baseline", None))
        self.assertIsInstance(record["turns"], list)
        self.assertIsInstance(record["turn_count"], int)
        self.assertIn(record["end_reason"], ("collision", "score", "draw"))

    def test_generates_multiple_matches_and_alternates_sides_in_pairs(self):
        summary = self.generator().generate(4, base_seed=20)
        records = self.records(summary)

        self.assertEqual([record["bot_side"] for record in records], ["A", "B", "A", "B"])
        self.assertEqual(summary["seeds"], [20, 20, 21, 21])
        self.assertEqual(records[0]["selfplay"]["pair_id"], records[1]["selfplay"]["pair_id"])
        self.assertEqual(records[2]["selfplay"]["pair_id"], records[3]["selfplay"]["pair_id"])

    def test_same_configuration_and_seed_are_byte_reproducible(self):
        first = self.generator(("random_safe",)).generate(2, base_seed=31)
        first_bytes = [path.read_bytes() for path in sorted(Path(first["dataset_path"]).glob("*.json"))]

        second = self.generator(("random_safe",)).generate(2, base_seed=31)
        second_bytes = [path.read_bytes() for path in sorted(Path(second["dataset_path"]).glob("*.json"))]

        self.assertEqual(first["dataset_path"], second["dataset_path"])
        self.assertEqual(first_bytes, second_bytes)

    def test_different_seeds_produce_distinct_datasets(self):
        first = self.generator(("random_safe",)).generate(1, base_seed=1)
        second = self.generator(("random_safe",)).generate(1, base_seed=2)

        self.assertNotEqual(first["dataset_path"], second["dataset_path"])
        self.assertNotEqual(self.records(first)[0], self.records(second)[0])

    def test_cycles_configured_opponent_mix_by_pair(self):
        summary = self.generator(("baseline", "survival", "random_safe", "mirror")).generate(8, 5)
        records = self.records(summary)

        self.assertEqual(summary["by_opponent"], {
            "baseline": 2,
            "mirror": 2,
            "random_safe": 2,
            "survival": 2,
        })
        self.assertEqual(
            [records[index]["selfplay"]["opponent_strategy"] for index in range(0, 8, 2)],
            ["baseline", "survival", "random_safe", "mirror"],
        )

    def test_records_traceable_metadata_and_move_analysis(self):
        record = self.records(self.generator().generate(1, 3))[0]
        metadata = record["selfplay"]

        self.assertEqual(metadata["seed"], 3)
        self.assertEqual(metadata["opponent_strategy"], "baseline")
        self.assertEqual(metadata["bot"]["strategy"], "ai.strategy.SnakeStrategy")
        self.assertEqual(len(metadata["bot"]["weights_fingerprint"]), 64)
        if record["turns"]:
            turn = record["turns"][0]
            self.assertIn(turn["mode"], ("balanced", "aggressive", "defensive"))
            self.assertIn(turn["chosen_direction"], turn["analysis"])

    def test_dataset_is_separate_from_real_games(self):
        real_directory = self.root / "games"
        real_directory.mkdir()
        summary = self.generator().generate(1, 4)

        self.assertTrue(Path(summary["dataset_path"]).is_relative_to(self.root / "selfplay"))
        self.assertEqual(list(real_directory.iterdir()), [])

    def test_generated_dataset_is_compatible_with_match_analyzer(self):
        generated = self.generator().generate(2, 9)

        summary = MatchAnalyzer(generated["dataset_path"]).analyze()

        self.assertEqual(summary["files"]["matches_analyzed"], 2)
        self.assertEqual(sum(summary["outcomes"][key] for key in ("wins", "losses", "draws")), 2)
        self.assertGreater(summary["turns"]["with_analysis"], 0)
        self.assertEqual(summary["data_sources"]["selfplay"], 2)

    def test_real_and_selfplay_datasets_are_combined_only_when_requested(self):
        generated = self.generator().generate(1, 10)
        real_directory = self.root / "games"
        real_directory.mkdir()
        (real_directory / "real.json").write_text(json.dumps({
            "game_id": "real",
            "player_1": "advanced",
            "player_2": "rival",
            "bot_side": "A",
            "score_1": 1,
            "score_2": 0,
            "winner": "advanced",
            "remaining_moves": 0,
            "turns": [],
        }), encoding="utf-8")

        synthetic_only = MatchAnalyzer(generated["dataset_path"]).analyze()
        combined = MatchAnalyzer([
            real_directory,
            generated["dataset_path"],
        ]).analyze()

        self.assertEqual(synthetic_only["files"]["matches_analyzed"], 1)
        self.assertEqual(combined["files"]["matches_analyzed"], 2)
        self.assertEqual(combined["data_sources"], {"real": 1, "selfplay": 1})

    def test_generated_dataset_is_compatible_with_learning_advisor(self):
        generated = self.generator().generate(2, 11)
        summary = MatchAnalyzer(generated["dataset_path"]).analyze()

        report = LearningAdvisor(min_matches=2).analyze(summary)

        self.assertIn(report["status"], ("ready", "no_clear_signal", "insufficient_data"))
        self.assertEqual(report["evidence"]["matches_analyzed"], 2)

    def test_invalid_and_incomplete_files_remain_tolerated(self):
        generated = self.generator().generate(1, 13)
        directory = Path(generated["dataset_path"])
        (directory / "broken.json").write_text("{broken", encoding="utf-8")
        (directory / "incomplete.json").write_text('{"source":"selfplay"}', encoding="utf-8")

        summary = MatchAnalyzer(directory).analyze()

        self.assertEqual(summary["files"]["invalid_files"], 1)
        self.assertEqual(summary["files"]["matches_analyzed"], 2)
        self.assertGreaterEqual(summary["files"]["incomplete_matches"], 1)

    def test_generation_does_not_modify_weights_file(self):
        weights_path = Path(__file__).parents[1] / "ai" / "weights.py"
        before = weights_path.read_bytes()

        self.generator().generate(1, 15)

        self.assertEqual(weights_path.read_bytes(), before)

    def test_generation_does_not_change_strategy_behavior(self):
        board = GameBoard("""|       |
| A     |
| a   * |
| a     |
|     B |
|     b |
|       |""")
        before = SnakeStrategy().choose_move(board, "A", 100, 0, 0)

        self.generator().generate(1, 17)
        after = SnakeStrategy().choose_move(board, "A", 100, 0, 0)

        self.assertEqual(after, before)

    def test_bot_client_has_no_selfplay_integration(self):
        client_path = Path(__file__).parents[1] / "bot" / "client.py"

        self.assertNotIn("selfplay", client_path.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
