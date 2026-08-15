import json
import tempfile
import unittest
from pathlib import Path

from ai import weights
from ai.strategy import SnakeStrategy
from ai.weight_config import WeightConfig
from game.board import GameBoard
from learning.candidate_optimizer import CandidateOptimizer, generate_candidates


class TestWeightConfig(unittest.TestCase):

    def test_baseline_reflects_current_defaults(self):
        baseline = WeightConfig.from_current_defaults()

        self.assertEqual(baseline.SPACE_WEIGHT, weights.SPACE_WEIGHT)
        self.assertEqual(baseline.INVALID_MOVE_SCORE, weights.INVALID_MOVE_SCORE)

    def test_candidate_does_not_mutate_baseline(self):
        baseline = WeightConfig.from_current_defaults()
        candidate = baseline.with_changes(SPACE_WEIGHT=baseline.SPACE_WEIGHT * 1.05)

        self.assertNotEqual(candidate.SPACE_WEIGHT, baseline.SPACE_WEIGHT)
        self.assertEqual(baseline.SPACE_WEIGHT, weights.SPACE_WEIGHT)

    def test_fingerprint_is_reproducible_and_comparable(self):
        first = WeightConfig.from_current_defaults()
        second = WeightConfig.from_current_defaults()
        changed = first.with_changes(SPACE_WEIGHT=9)

        self.assertEqual(first, second)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_rejects_invalid_configuration(self):
        baseline = WeightConfig.from_current_defaults()

        with self.assertRaises(ValueError):
            baseline.with_changes(UNKNOWN_WEIGHT=1)
        with self.assertRaises(TypeError):
            baseline.with_changes(SPACE_WEIGHT="large")
        with self.assertRaises(ValueError):
            baseline.with_changes(SPACE_WEIGHT=-1)

    def test_generates_requested_variations_for_subset(self):
        baseline = WeightConfig.from_current_defaults()
        generated = generate_candidates(
            baseline,
            ["SPACE_WEIGHT"],
            (0.05, -0.05, 0.10, -0.10),
        )

        self.assertEqual([item["variation"] for item in generated], [0.05, -0.05, 0.10, -0.10])
        self.assertEqual(
            [item["config"].SPACE_WEIGHT for item in generated],
            [8.4, 7.6, 8.8, 7.2],
        )
        self.assertTrue(all(
            set(item["config"].differences_from(baseline)) == {"SPACE_WEIGHT"}
            for item in generated
        ))

    def test_candidate_limit_prevents_combinatorial_growth(self):
        generated = generate_candidates(
            WeightConfig.from_current_defaults(),
            ["SPACE_WEIGHT", "FOOD_DISTANCE_WEIGHT"],
            limit=3,
        )

        self.assertEqual(len(generated), 3)

    def test_structural_invalid_move_marker_is_not_optimizable(self):
        with self.assertRaises(ValueError):
            generate_candidates(
                WeightConfig.from_current_defaults(),
                ["INVALID_MOVE_SCORE"],
            )

    def test_advisor_only_prioritizes_with_explicit_mapping(self):
        baseline = WeightConfig.from_current_defaults()
        report = {"recommendations": [{"metric": "space"}]}

        generated = generate_candidates(
            baseline,
            ["FOOD_DISTANCE_WEIGHT", "SPACE_WEIGHT"],
            variations=(0.05,),
            advisor_report=report,
            metric_to_weight={"space": "SPACE_WEIGHT"},
        )

        self.assertEqual(generated[0]["parameter"], "SPACE_WEIGHT")
        self.assertEqual(generated[0]["reason"], "advisor_priority")

    def test_default_strategy_matches_explicit_baseline(self):
        board = GameBoard("""|       |
| A     |
| a   * |
| a     |
|     B |
|     b |
|       |""")

        implicit = SnakeStrategy().choose_move(board, "A", 100, 0, 0)
        explicit = SnakeStrategy(
            weight_config=WeightConfig.from_current_defaults()
        ).choose_move(board, "A", 100, 0, 0)

        self.assertEqual(implicit, explicit)


class TestCandidateOptimizer(unittest.TestCase):

    def setUp(self):
        self.baseline = WeightConfig.from_current_defaults()
        self.candidate = self.baseline.with_changes(SPACE_WEIGHT=8.4)

    @staticmethod
    def runner(outcome="win", crash=False, score_diff=100):
        def run(candidate, baseline, rival, seed, side):
            own_score = 100 + score_diff
            return {
                "seed": seed,
                "side": side,
                "outcome": outcome,
                "own_score": own_score,
                "opponent_score": 100,
                "own_crash": crash,
                "opponent_crash": False,
                "turns": 4,
            }
        return run

    def optimizer(self, runner, matches=4, min_matches=4, rivals=()):
        return CandidateOptimizer(
            matches_per_rival=matches,
            base_seed=10,
            rivals=rivals,
            min_matches=min_matches,
            match_runner=runner,
        )

    def test_alternates_sides_and_pairs_seeds(self):
        calls = []

        def runner(candidate, baseline, rival, seed, side):
            calls.append((rival, seed, side))
            return self.runner("draw", False, 0)(candidate, baseline, rival, seed, side)

        self.optimizer(runner).evaluate(self.baseline, [self.candidate])

        self.assertEqual(calls, [
            ("stable", 10, "A"), ("stable", 10, "B"),
            ("stable", 11, "A"), ("stable", 11, "B"),
        ])

    def test_clearly_worse_candidate_is_rejected(self):
        report = self.optimizer(self.runner("loss", False, -200)).evaluate(
            self.baseline, [self.candidate]
        )

        self.assertEqual(report["candidates"][0]["status"], "rejected")

    def test_small_sample_is_inconclusive(self):
        report = self.optimizer(self.runner(), matches=2, min_matches=4).evaluate(
            self.baseline, [self.candidate]
        )

        self.assertEqual(report["candidates"][0]["status"], "inconclusive")

    def test_better_candidate_without_crashes_is_promising(self):
        report = self.optimizer(self.runner("win", False, 100)).evaluate(
            self.baseline, [self.candidate]
        )

        self.assertEqual(report["candidates"][0]["status"], "promising")

    def test_crash_increase_prevents_promotion(self):
        report = self.optimizer(self.runner("win", True, 100)).evaluate(
            self.baseline, [self.candidate]
        )

        self.assertEqual(report["candidates"][0]["status"], "rejected")
        self.assertLess(report["candidates"][0]["results"]["composite_score"], 100)

    def test_results_include_local_rivals_and_sides(self):
        report = self.optimizer(
            self.runner("draw", False, 0), rivals=("baseline", "survival")
        ).evaluate(self.baseline, [self.candidate])
        result = report["candidates"][0]

        self.assertEqual(set(result["results_by_rival"]), {"stable", "baseline", "survival"})
        self.assertEqual(result["results_by_side"]["A"]["matches"], 6)
        self.assertEqual(result["results_by_side"]["B"]["matches"], 6)

    def test_same_seed_produces_same_ranking(self):
        candidates = [
            self.candidate,
            self.baseline.with_changes(FOOD_DISTANCE_WEIGHT=36.75),
        ]
        first = self.optimizer(self.runner()).evaluate(self.baseline, candidates)
        second = self.optimizer(self.runner()).evaluate(self.baseline, candidates)

        self.assertEqual(first, second)

    def test_report_is_json_serializable_and_save_is_explicit(self):
        report = self.optimizer(self.runner()).evaluate(self.baseline, [self.candidate])
        encoded = json.dumps(report)

        self.assertIn(self.candidate.fingerprint, encoded)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            self.assertFalse(output.exists())
            CandidateOptimizer.save_report(report, output)
            self.assertEqual(json.loads(output.read_text()), report)

    def test_experiment_keeps_baseline_and_weights_file_intact(self):
        weights_path = Path(__file__).parents[1] / "ai" / "weights.py"
        before_file = weights_path.read_bytes()
        before_config = self.baseline.as_dict()

        self.optimizer(self.runner()).evaluate(self.baseline, [self.candidate])

        self.assertEqual(weights_path.read_bytes(), before_file)
        self.assertEqual(self.baseline.as_dict(), before_config)
        self.assertEqual(weights.SPACE_WEIGHT, 8)

    def test_optimizer_is_not_imported_by_competitive_entrypoints(self):
        root = Path(__file__).parents[1]

        self.assertNotIn("candidate_optimizer", (root / "run.py").read_text().lower())
        self.assertNotIn("candidate_optimizer", (root / "bot" / "client.py").read_text().lower())


if __name__ == "__main__":
    unittest.main()
