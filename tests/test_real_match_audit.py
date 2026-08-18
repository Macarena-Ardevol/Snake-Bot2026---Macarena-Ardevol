import json
import tempfile
import unittest
from pathlib import Path

from learning.real_match_audit import RealMatchAuditor


OPEN_ADJACENT = """|       |
|       |
|       |
|   A*  |
|       |
|      B|
|       |"""


def candidate(total=1000, **changes):
    values = {
        "space": 500, "survival": 0, "food": 100,
        "food_race": 0, "food_safety": 100, "mobility": 60,
        "territory": 0, "enemy_risk": 0, "lookahead": 0,
        "bottleneck": 0, "two_ply": 0, "total": total,
    }
    values.update(changes)
    return values


class TestRealMatchAudit(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_game(
        self,
        game_id="g1",
        board=OPEN_ADJACENT,
        chosen="right",
        analysis=None,
        winner="bot",
        side="A",
    ):
        payload = {
            "game_id": game_id,
            "player_1": "bot",
            "player_2": "rival",
            "winner": winner,
            "bot_side": side,
            "turns": [{
                "board": board, "side": side, "remaining_moves": 50,
                "score_1": 100, "score_2": 50,
                "chosen_direction": chosen, "mode": "balanced",
                "analysis": analysis if analysis is not None else {
                    "right": candidate(1200), "left": candidate(1000),
                    "up": candidate(900), "down": candidate(800),
                },
            }],
        }
        path = self.directory / f"game_{game_id}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def report(self, **filters):
        return RealMatchAuditor(self.directory).analyze(**filters)

    def test_adjacent_food_taken(self):
        self.write_game()
        report = self.report()
        adjacent = report["decisions"][0]["foods"][0]["adjacent_analysis"]
        self.assertTrue(adjacent["taken"])
        self.assertEqual(adjacent["reason"], "taken")

    def test_adjacent_food_ignored_with_real_enemy_risk(self):
        analysis = {
            "right": candidate(700, enemy_risk=-1500),
            "left": candidate(1200),
        }
        self.write_game(chosen="left", analysis=analysis)
        adjacent = self.report()["decisions"][0]["foods"][0]["adjacent_analysis"]
        self.assertEqual(adjacent["reason"], "immediate_enemy_risk")
        self.assertFalse(adjacent["suspicious"])

    def test_adjacent_ignored_without_analysis_is_insufficient(self):
        self.write_game(chosen="left", analysis={})
        adjacent = self.report()["decisions"][0]["foods"][0]["adjacent_analysis"]
        self.assertEqual(adjacent["reason"], "insufficient_recorded_data")

    def test_adjacent_ignored_with_ambiguous_evidence_is_unknown(self):
        self.write_game(
            chosen="left",
            analysis={"right": candidate(900), "left": candidate(1400)},
        )
        adjacent = self.report()["decisions"][0]["foods"][0]["adjacent_analysis"]
        self.assertEqual(adjacent["reason"], "unknown")

    def test_two_equivalent_shortest_first_steps(self):
        board = """|       |
|       |
|    *  |
|   A   |
|       |
|      B|
|       |"""
        self.write_game(board=board, chosen="up")
        food = self.report()["decisions"][0]["foods"][0]
        self.assertEqual(set(food["shortest_first_directions"]), {"up", "right"})
        self.assertEqual(len(food["shortest_routes"]), 2)
        self.assertEqual(food["chosen_path_classification"], "equivalent_shortest_path")

    def test_route_really_longer_is_off_shortest_path(self):
        board = """|       |
|       |
|     * |
|   A   |
|       |
|      B|
|       |"""
        self.write_game(board=board, chosen="left")
        food = self.report()["decisions"][0]["foods"][0]
        self.assertEqual(food["distance"], 3)
        self.assertEqual(food["chosen_path_classification"], "off_shortest_path")

    def test_multiple_foods_are_kept_separate(self):
        board = """|*      |
|       |
|       |
|   A*  |
|       |
|      B|
|       |"""
        self.write_game(board=board)
        foods = self.report()["decisions"][0]["foods"]
        self.assertEqual(len(foods), 2)
        self.assertEqual(sorted(food["distance"] for food in foods), [1, 6])

    def test_geometrically_close_food_blocked_by_body(self):
        board = """|       |
|       |
|       |
| Aa*  B|
|       |
|       |
|       |"""
        self.write_game(board=board, chosen="up")
        food = self.report()["decisions"][0]["foods"][0]
        self.assertGreater(food["distance"], 3)
        self.assertTrue(food["blocked_apparently_close"])

    def test_old_incomplete_record_is_tolerated(self):
        path = self.directory / "game_old.json"
        path.write_text(json.dumps({"game_id": "old", "turns": [{}]}), encoding="utf-8")
        report = self.report()
        self.assertEqual(report["summary"]["game_files_found"], 1)
        self.assertEqual(report["summary"]["turns_analyzed"], 0)

    def test_game_id_and_losses_only_filters(self):
        self.write_game(game_id="win")
        self.write_game(game_id="loss", winner="rival")
        losses = self.report(losses_only=True)
        specific = self.report(game_id="win")
        self.assertEqual(losses["summary"]["games_selected"], 1)
        self.assertEqual(losses["decisions"][0]["game_id"], "loss")
        self.assertEqual(specific["decisions"][0]["game_id"], "win")

    def test_explicit_output_does_not_modify_inputs_and_is_reproducible(self):
        original = self.write_game()
        before = original.read_bytes()
        auditor = RealMatchAuditor(self.directory)
        first = auditor.analyze()
        second = auditor.analyze()
        output = self.directory / "learning" / "audit.json"
        auditor.save(first, output)
        self.assertEqual(first, second)
        self.assertEqual(original.read_bytes(), before)
        exported = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exported["summary"], first["summary"])
        self.assertIn("candidate_cases", exported)
        self.assertNotIn("decisions", exported)

    def test_small_safe_gap_is_marked_suspicious(self):
        analysis = {
            "right": candidate(1000),
            "left": candidate(1110, two_ply=110),
        }
        self.write_game(chosen="left", analysis=analysis)
        report = self.report()
        self.assertEqual(len(report["suspicious_decisions"]), 1)
        self.assertEqual(
            report["decisions"][0]["foods"][0]["adjacent_analysis"]["reason"],
            "alternative_move_higher_two_ply",
        )


if __name__ == "__main__":
    unittest.main()
