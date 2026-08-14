import json
import tempfile
import unittest
from pathlib import Path

from learning.match_analyzer import MatchAnalyzer


class TestMatchAnalyzer(unittest.TestCase):

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.games_directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_game(self, name: str, data: dict) -> None:
        (self.games_directory / name).write_text(
            json.dumps(data),
            encoding="utf-8",
        )

    def match(
        self,
        winner: str | None,
        score_1: int,
        score_2: int,
        remaining_moves: int = 0,
        turns: list | None = None,
    ) -> dict:
        return {
            "game_id": "game_test",
            "player_1": "my_bot",
            "player_2": "rival",
            "bot_side": "A",
            "score_1": score_1,
            "score_2": score_2,
            "winner": winner,
            "remaining_moves": remaining_moves,
            "turns": [] if turns is None else turns,
        }

    def analyze(self) -> dict:
        return MatchAnalyzer(self.games_directory).analyze()

    def test_empty_directory(self):
        summary = self.analyze()

        self.assertEqual(summary["files"]["matches_analyzed"], 0)
        self.assertEqual(summary["outcomes"]["wins"], 0)
        self.assertEqual(summary["outcomes"]["win_rate"], 0.0)
        self.assertEqual(summary["scores"]["own_average"], 0.0)

    def test_counts_a_victory(self):
        self.write_game("win.json", self.match("my_bot", 200, 100))

        summary = self.analyze()

        self.assertEqual(summary["outcomes"]["wins"], 1)
        self.assertEqual(summary["outcomes"]["win_rate"], 1.0)

    def test_counts_a_defeat(self):
        self.write_game("loss.json", self.match("rival", 100, 200))

        self.assertEqual(self.analyze()["outcomes"]["losses"], 1)

    def test_counts_a_draw(self):
        self.write_game("draw.json", self.match(None, 100, 100))

        self.assertEqual(self.analyze()["outcomes"]["draws"], 1)

    def test_calculates_aggregates_across_matches(self):
        self.write_game("one.json", self.match("my_bot", 300, 100))
        second = self.match("rival", 100, 200)
        second["game_id"] = "game_second"
        self.write_game("two.json", second)

        summary = self.analyze()

        self.assertEqual(summary["files"]["matches_analyzed"], 2)
        self.assertEqual(summary["outcomes"]["wins"], 1)
        self.assertEqual(summary["outcomes"]["losses"], 1)
        self.assertEqual(summary["outcomes"]["win_rate"], 0.5)
        self.assertEqual(summary["scores"]["own_average"], 200.0)
        self.assertEqual(summary["scores"]["opponent_average"], 150.0)

    def test_tolerates_incomplete_json_object(self):
        self.write_game("incomplete.json", {"game_id": "old_game"})

        summary = self.analyze()

        self.assertEqual(summary["files"]["matches_analyzed"], 1)
        self.assertEqual(summary["files"]["incomplete_matches"], 1)
        self.assertEqual(summary["outcomes"]["unknown"], 1)

    def test_missing_winner_is_not_confused_with_missing_player_name(self):
        self.write_game("incomplete.json", {
            "game_id": "old_game",
            "bot_side": "A",
            "player_2": "rival",
        })

        self.assertEqual(self.analyze()["outcomes"]["unknown"], 1)

    def test_skips_invalid_json_file(self):
        (self.games_directory / "broken.json").write_text(
            "{not valid json",
            encoding="utf-8",
        )

        summary = self.analyze()

        self.assertEqual(summary["files"]["invalid_files"], 1)
        self.assertEqual(summary["files"]["matches_analyzed"], 0)
        self.assertEqual(summary["files"]["skipped"][0]["file"], "broken.json")

    def test_match_without_turns_is_supported(self):
        self.write_game("no_turns.json", self.match("my_bot", 10, 0))

        summary = self.analyze()

        self.assertEqual(summary["turns"]["total"], 0)
        self.assertEqual(summary["turns"]["matches_without_turns"], 1)

    def test_analyzes_turn_modes_components_and_loss_tail(self):
        turns = [
            {
                "side": "A",
                "chosen_direction": "right",
                "mode": "balanced",
                "remaining_moves": 10,
                "analysis": {
                    "right": {"space": 20, "food": 4, "total": 24},
                    "up": {"space": 10, "food": 2, "total": 12},
                },
            },
            {
                "side": "A",
                "chosen_direction": "down",
                "mode": "aggressive",
                "remaining_moves": 8,
                "analysis": {
                    "down": {"space": 8, "lookahead": -5, "total": 3},
                },
            },
        ]
        self.write_game(
            "loss.json",
            self.match("rival", 100, 200, remaining_moves=0, turns=turns),
        )

        summary = MatchAnalyzer(
            self.games_directory,
            recent_loss_moves=2,
        ).analyze()

        self.assertEqual(summary["turns"]["total"], 2)
        self.assertEqual(summary["strategy_modes"]["balanced"], 1)
        self.assertEqual(summary["strategy_modes"]["aggressive"], 1)
        self.assertEqual(
            summary["evaluation_components"]["chosen_moves"]["space"]["average"],
            14.0,
        )
        self.assertEqual(
            summary["evaluation_components"]["all_candidates"]["food"]["count"],
            2,
        )
        tail = summary["recent_moves_before_losses"][0]["moves"]
        self.assertEqual([move["direction"] for move in tail], ["right", "down"])

    def test_negative_remaining_moves_alone_is_not_a_timeout(self):
        self.write_game(
            "timeout.json",
            self.match("rival", -3000, 5, remaining_moves=-1),
        )

        summary = self.analyze()

        self.assertEqual(summary["outcomes"]["loss_causes"]["timeout"], 0)
        self.assertEqual(summary["outcomes"]["loss_causes"]["unknown"], 1)
        self.assertEqual(summary["terminations"]["timeouts"]["own"], 0)

    def test_classifies_explicit_timeout(self):
        match = self.match("rival", -500, 5, remaining_moves=-1)
        match["timeout_side"] = "A"
        self.write_game("timeout.json", match)

        summary = self.analyze()

        self.assertEqual(summary["outcomes"]["loss_causes"]["timeout"], 1)
        self.assertEqual(summary["terminations"]["timeouts"]["own"], 1)

    def test_classifies_collision_from_reliable_score_delta(self):
        turns = [{
            "side": "A",
            "score_1": 100,
            "score_2": 50,
            "chosen_direction": "left",
            "analysis": {},
        }]
        self.write_game(
            "collision.json",
            self.match("rival", -400, 1050, remaining_moves=20, turns=turns),
        )

        summary = self.analyze()

        self.assertEqual(summary["outcomes"]["loss_causes"]["collision"], 1)
        self.assertEqual(summary["terminations"]["collisions"]["own"], 1)

    def test_classifies_score_loss_at_move_limit(self):
        self.write_game(
            "score.json",
            self.match("rival", 100, 200, remaining_moves=0),
        )

        self.assertEqual(
            self.analyze()["outcomes"]["loss_causes"]["score"],
            1,
        )

    def test_move_limit_without_lower_score_is_not_a_score_loss(self):
        inconsistent = self.match("rival", 200, 100, remaining_moves=0)
        self.write_game("ambiguous.json", inconsistent)

        self.assertEqual(
            self.analyze()["outcomes"]["loss_causes"]["unknown"],
            1,
        )

    def test_absent_collision_field_does_not_match_absent_player(self):
        ambiguous = {
            "game_id": "ambiguous",
            "bot_side": "A",
            "player_2": "rival",
            "winner": "rival",
            "score_1": 0,
            "score_2": 100,
            "remaining_moves": 10,
            "turns": [],
        }
        self.write_game("ambiguous.json", ambiguous)

        summary = self.analyze()

        self.assertEqual(summary["outcomes"]["loss_causes"]["collision"], 0)
        self.assertEqual(summary["outcomes"]["loss_causes"]["unknown"], 1)

    def test_unrecognized_winner_is_not_replaced_by_score_inference(self):
        ambiguous = self.match("external_player", 500, 0, remaining_moves=0)
        self.write_game("ambiguous.json", ambiguous)

        self.assertEqual(self.analyze()["outcomes"]["unknown"], 1)

    def test_configured_player_missing_from_match_keeps_perspective_unknown(self):
        self.write_game("other_bot.json", self.match("my_bot", 10, 0))

        summary = MatchAnalyzer(
            self.games_directory,
            player_name="different_bot",
        ).analyze()

        self.assertEqual(summary["outcomes"]["unknown"], 1)

    def test_can_infer_bot_side_from_turns_in_old_record(self):
        old_match = self.match("my_bot", 10, 0, turns=[{"side": "A"}])
        old_match.pop("bot_side")
        self.write_game("old.json", old_match)

        self.assertEqual(self.analyze()["outcomes"]["wins"], 1)

    def test_player_name_resolves_old_match_without_turns(self):
        old_match = self.match("my_bot", 10, 0)
        old_match.pop("bot_side")
        self.write_game("old.json", old_match)

        summary = MatchAnalyzer(
            self.games_directory,
            player_name="my_bot",
        ).analyze()

        self.assertEqual(summary["outcomes"]["wins"], 1)

    def test_summary_persistence_is_explicit_and_separate(self):
        summary = self.analyze()
        output_path = self.games_directory / "learning" / "global_stats.json"

        saved_path = MatchAnalyzer.save_summary(summary, output_path)

        self.assertEqual(saved_path, output_path)
        self.assertEqual(
            json.loads(saved_path.read_text(encoding="utf-8")),
            summary,
        )


if __name__ == "__main__":
    unittest.main()
