import json
import unittest

from ai.food_race import FoodRaceAnalyzer
from ai.evaluator import MoveEvaluator
from ai.strategy import SnakeStrategy
from game.board import GameBoard


BOARD = GameBoard("""|       |
| A *   |
|       |
|       |
|     B |
|       |
|       |""")


class TestDecisionTelemetry(unittest.TestCase):
    def test_compute_levels_and_enemy_prediction_are_captured(self):
        for level in ("normal", "busy", "critical"):
            strategy = SnakeStrategy()
            move = strategy.choose_move(BOARD, "A", 100, 0, 0, level)
            context = strategy.last_decision_context
            self.assertEqual(context["compute_level"], level)
            self.assertEqual(context["chosen_direction"], move)
            if level == "critical":
                self.assertIsNone(context["enemy_prediction"]["direction"])
            else:
                self.assertIn(
                    context["enemy_prediction"]["direction"],
                    BOARD.DIRECTIONS,
                )

    def test_known_target_reuses_canonical_bfs_path(self):
        strategy = SnakeStrategy()
        strategy.choose_move(BOARD, "A", 100, 0, 0)
        target = strategy.last_decision_context["target_food"]
        self.assertEqual(target["status"], "known")
        self.assertEqual(target["food"], [1, 3])
        self.assertEqual(target["path"], ["right", "right"])
        self.assertEqual(target["shortest_path_count"], "unknown")

    def test_ambiguous_target_is_not_arbitrarily_selected(self):
        board = GameBoard("""|       |
|       |
|*  A  *|
|       |
|       |
|     B |
|       |""")
        analysis = MoveEvaluator().analyze_move(board, "A", "down")
        contexts = [
            analysis["candidate_context"]["food_target"]
        ]
        self.assertTrue(any(context["status"] == "ambiguous" for context in contexts))
        for context in contexts:
            if context["status"] == "ambiguous":
                self.assertNotIn("food", context)

    def test_no_food_has_none_target(self):
        board = GameBoard("""|       |
| A     |
|       |
|       |
|     B |
|       |
|       |""")
        strategy = SnakeStrategy()
        strategy.choose_move(board, "A")
        self.assertEqual(strategy.last_decision_context["target_food"]["status"], "none")

    def test_food_race_known_and_ambiguous_targets(self):
        analyzer = FoodRaceAnalyzer()
        known = analyzer.analyze(BOARD, "A")
        self.assertEqual(known["target_status"], "known")
        self.assertEqual(known["food"], [1, 3])
        self.assertIn(known["result"], ("winning", "tied", "losing"))

        symmetric = GameBoard("""|       |
| *   * |
|   A   |
|       |
|   B   |
|       |
|       |""")
        ambiguous = analyzer.analyze(symmetric, "A")
        self.assertEqual(ambiguous["target_status"], "ambiguous")
        self.assertIsNone(ambiguous["food"])

    def test_context_is_json_serializable_and_reproducible(self):
        first = SnakeStrategy()
        second = SnakeStrategy()
        first.choose_move(BOARD, "A", 100, 0, 0)
        second.choose_move(BOARD, "A", 100, 0, 0)
        self.assertEqual(first.last_decision_context, second.last_decision_context)
        json.dumps(first.last_decision_context)

    def test_telemetry_helpers_preserve_existing_numeric_scores(self):
        evaluator = MoveEvaluator()
        for direction in BOARD.DIRECTIONS:
            simulated = evaluator.simulator.simulate_move(BOARD, "A", direction)
            if simulated is None:
                continue
            position = simulated.my_head("A")
            old_score = evaluator._food_score(simulated, position)
            contextual_score, _ = evaluator._food_score_with_context(
                simulated, position, direction
            )
            self.assertEqual(contextual_score, old_score)

        race = FoodRaceAnalyzer()
        self.assertEqual(race.score(BOARD, "A"), race.analyze(BOARD, "A")["score"])


if __name__ == "__main__":
    unittest.main()
