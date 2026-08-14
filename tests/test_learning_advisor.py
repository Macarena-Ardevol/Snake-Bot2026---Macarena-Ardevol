import json
import tempfile
import unittest
from pathlib import Path

from ai import weights
from ai.strategy import SnakeStrategy
from learning.learning_advisor import LearningAdvisor
from learning.match_analyzer import MatchAnalyzer


class TestLearningAdvisor(unittest.TestCase):

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        empty_games = Path(self.temporary_directory.name) / "games"
        empty_games.mkdir()
        self.empty_summary = MatchAnalyzer(empty_games).analyze()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def summary(self, wins: int, losses: int, draws: int = 0) -> dict:
        summary = json.loads(json.dumps(self.empty_summary))
        total = wins + losses + draws
        summary["files"]["matches_analyzed"] = total
        summary["outcomes"].update({
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": wins / total if total else 0.0,
        })
        return summary

    @staticmethod
    def component(average: object, count: object, matches: object = 10) -> dict:
        return {
            "average": average,
            "count": count,
            "matches": matches,
            "minimum": average,
            "maximum": average,
        }

    @staticmethod
    def recommendation(report: dict, kind: str, metric: str | None = None) -> dict:
        for recommendation in report["recommendations"]:
            if recommendation["kind"] != kind:
                continue
            if metric is None or recommendation["metric"] == metric:
                return recommendation
        raise AssertionError(f"No se encontró recomendación {kind}/{metric}")

    def test_empty_summary(self):
        report = LearningAdvisor().analyze(self.empty_summary)

        self.assertEqual(report["status"], "insufficient_data")
        recommendation = self.recommendation(report, "insufficient_data")
        self.assertEqual(recommendation["direction"], "collect_more_data")
        self.assertEqual(report["evidence"]["matches_analyzed"], 0)

    def test_insufficient_sample_has_low_confidence(self):
        report = LearningAdvisor().analyze(self.summary(1, 1))

        recommendation = self.recommendation(report, "insufficient_data")
        self.assertLess(recommendation["confidence"], 0.5)
        self.assertNotEqual(recommendation["priority"], "high")

    def test_predominantly_winning_history_suggests_maintaining(self):
        report = LearningAdvisor().analyze(self.summary(16, 4))

        recommendation = self.recommendation(report, "performance")
        self.assertEqual(recommendation["direction"], "maintain")
        self.assertEqual(recommendation["evidence"]["win_rate"], 0.8)

    def test_predominantly_losing_history_suggests_review(self):
        report = LearningAdvisor().analyze(self.summary(4, 16))

        recommendation = self.recommendation(report, "performance")
        self.assertEqual(recommendation["direction"], "review")
        self.assertEqual(recommendation["sample_size"], 20)

    def test_compares_dynamic_component_between_wins_and_losses(self):
        summary = self.summary(10, 10)
        segmented = summary["evaluation_components_by_outcome"]
        segmented["wins"]["chosen_moves"]["future_metric"] = self.component(100, 30)
        segmented["losses"]["chosen_moves"]["future_metric"] = self.component(50, 30)

        report = LearningAdvisor().analyze(summary)

        recommendation = self.recommendation(
            report,
            "component_correlation",
            "future_metric",
        )
        self.assertEqual(recommendation["direction"], "review")
        self.assertEqual(recommendation["evidence"]["win_average"], 100.0)
        self.assertEqual(recommendation["evidence"]["loss_average"], 50.0)
        self.assertIn("correlación", recommendation["explanation"].lower())

    def test_detects_mode_performance_difference(self):
        summary = self.summary(10, 10)
        summary["mode_performance"]["balanced"].update({
            "matches": 10, "wins": 8, "losses": 2, "win_rate": 0.8,
        })
        summary["mode_performance"]["aggressive"].update({
            "matches": 10, "wins": 2, "losses": 8, "win_rate": 0.2,
        })

        report = LearningAdvisor().analyze(summary)

        weak_mode = self.recommendation(report, "mode_performance", "aggressive")
        self.assertEqual(weak_mode["direction"], "review")
        self.assertEqual(weak_mode["evidence"]["mode_win_rate"], 0.2)

    def test_detects_collision_increase_in_mode(self):
        summary = self.summary(8, 12)
        summary["outcomes"]["loss_causes"]["collision"] = 4
        aggressive = summary["mode_performance"]["aggressive"]
        aggressive.update({"matches": 10, "wins": 2, "losses": 8})
        aggressive["loss_causes"]["collision"] = 4

        report = LearningAdvisor().analyze(summary)

        recommendation = self.recommendation(report, "mode_risk", "aggressive")
        self.assertEqual(recommendation["evidence"]["cause"], "collision")
        self.assertEqual(recommendation["evidence"]["cause_count"], 4)
        self.assertEqual(recommendation["direction"], "review")

    def test_detects_score_loss_increase_in_mode(self):
        summary = self.summary(8, 12)
        summary["outcomes"]["loss_causes"]["score"] = 4
        defensive = summary["mode_performance"]["defensive"]
        defensive.update({"matches": 10, "wins": 2, "losses": 8})
        defensive["loss_causes"]["score"] = 4

        report = LearningAdvisor().analyze(summary)

        recommendation = self.recommendation(report, "mode_risk", "defensive")
        self.assertEqual(recommendation["evidence"]["cause"], "score")

    def test_detects_repeated_score_losses(self):
        summary = self.summary(8, 12)
        summary["outcomes"]["loss_causes"]["score"] = 6

        report = LearningAdvisor().analyze(summary)

        recommendation = self.recommendation(report, "loss_cause", "score")
        self.assertEqual(recommendation["evidence"]["count"], 6)

    def test_detects_confirmed_timeouts(self):
        summary = self.summary(10, 10)
        summary["outcomes"]["loss_causes"]["timeout"] = 3

        report = LearningAdvisor().analyze(summary)

        recommendation = self.recommendation(report, "loss_cause", "timeout")
        self.assertEqual(recommendation["evidence"]["count"], 3)

    def test_compares_chosen_move_with_candidates_for_dynamic_metric(self):
        summary = self.summary(10, 10)
        summary["evaluation_components"]["valid_chosen_moves"]["novel"] = (
            self.component(40, 40)
        )
        summary["evaluation_components"]["valid_candidates"]["novel"] = (
            self.component(100, 120)
        )
        summary["evaluation_components"]["selection_context"].update({
            "turns_with_multiple_valid_candidates": 40,
            "matches_with_multiple_valid_candidates": 10,
        })

        report = LearningAdvisor().analyze(summary)

        recommendation = self.recommendation(report, "selection_gap", "novel")
        self.assertEqual(recommendation["direction"], "review")

    def test_chosen_metric_above_candidate_average_is_not_a_problem_signal(self):
        summary = self.summary(10, 10)
        summary["evaluation_components"]["valid_chosen_moves"]["novel"] = (
            self.component(100, 40)
        )
        summary["evaluation_components"]["valid_candidates"]["novel"] = (
            self.component(40, 120)
        )
        summary["evaluation_components"]["selection_context"].update({
            "turns_with_multiple_valid_candidates": 40,
            "matches_with_multiple_valid_candidates": 10,
        })

        report = LearningAdvisor().analyze(summary)

        self.assertFalse(any(
            item["kind"] == "selection_gap" and item["metric"] == "novel"
            for item in report["recommendations"]
        ))

    def test_single_valid_candidate_does_not_create_selection_signal(self):
        summary = self.summary(10, 10)
        summary["evaluation_components"]["valid_chosen_moves"]["novel"] = (
            self.component(10, 30)
        )
        summary["evaluation_components"]["valid_candidates"]["novel"] = (
            self.component(100, 30)
        )

        report = LearningAdvisor().analyze(summary)

        self.assertFalse(any(
            item["kind"] == "selection_gap"
            for item in report["recommendations"]
        ))

    def test_old_candidate_format_is_handled_conservatively(self):
        summary = self.summary(10, 10)
        components = summary["evaluation_components"]
        components.pop("valid_chosen_moves")
        components.pop("valid_candidates")
        components.pop("selection_context")
        components["chosen_moves"]["novel"] = self.component(10, 40)
        components["all_candidates"]["novel"] = self.component(100, 120)

        report = LearningAdvisor().analyze(summary)

        self.assertFalse(any(
            item["kind"] == "selection_gap"
            for item in report["recommendations"]
        ))
        self.assertTrue(any(
            warning["code"] == "insufficient_valid_candidate_data"
            for warning in report["warnings"]
        ))

    def test_missing_metrics_are_tolerated(self):
        report = LearningAdvisor().analyze(self.summary(10, 10))

        self.assertFalse(any(
            item["kind"] == "component_correlation"
            for item in report["recommendations"]
        ))
        self.assertTrue(any(
            warning["code"] == "missing_segmented_components"
            for warning in report["warnings"]
        ))

    def test_non_numeric_component_values_are_ignored(self):
        summary = self.summary(10, 10)
        segmented = summary["evaluation_components_by_outcome"]
        segmented["wins"]["chosen_moves"]["broken"] = self.component("high", 30)
        segmented["losses"]["chosen_moves"]["broken"] = self.component(None, 30)

        report = LearningAdvisor().analyze(summary)

        self.assertFalse(any(item["metric"] == "broken" for item in report["recommendations"]))

    def test_many_turns_from_one_loss_do_not_create_component_recommendation(self):
        summary = self.summary(10, 10)
        segmented = summary["evaluation_components_by_outcome"]
        segmented["wins"]["chosen_moves"]["space"] = self.component(
            100,
            500,
            matches=10,
        )
        segmented["losses"]["chosen_moves"]["space"] = self.component(
            10,
            500,
            matches=1,
        )

        report = LearningAdvisor().analyze(summary)

        self.assertFalse(any(
            item["kind"] == "component_correlation" and item["metric"] == "space"
            for item in report["recommendations"]
        ))

    def test_incomplete_summary_is_tolerated(self):
        report = LearningAdvisor().analyze({"outcomes": {"wins": 2}})

        self.assertEqual(report["status"], "insufficient_data")
        self.assertTrue(any(
            warning["code"] == "incomplete_summary"
            for warning in report["warnings"]
        ))

    def test_contradictory_evidence_produces_no_directional_claim(self):
        summary = self.summary(10, 10)
        segmented = summary["evaluation_components_by_outcome"]
        segmented["wins"]["chosen_moves"]["space"] = self.component(100, 30)
        segmented["losses"]["chosen_moves"]["space"] = self.component(100, 30)

        report = LearningAdvisor().analyze(summary)

        self.assertEqual(report["status"], "no_clear_signal")
        self.assertFalse(any(item["metric"] == "space" for item in report["recommendations"]))

    def test_confidence_increases_with_sample_size(self):
        small = LearningAdvisor().analyze(self.summary(3, 7))
        large = LearningAdvisor().analyze(self.summary(30, 70))

        small_confidence = self.recommendation(small, "performance")["confidence"]
        large_confidence = self.recommendation(large, "performance")["confidence"]

        self.assertGreater(large_confidence, small_confidence)
        self.assertLessEqual(large_confidence, 0.95)

    def test_report_is_json_serializable_and_saved_only_explicitly(self):
        report = LearningAdvisor().analyze(self.summary(8, 12))
        output = Path(self.temporary_directory.name) / "learning" / "advisor.json"

        encoded = json.dumps(report)
        saved = LearningAdvisor.save_report(report, output)

        self.assertTrue(encoded)
        self.assertEqual(saved, output)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)

    def test_does_not_modify_weights_or_strategy(self):
        weight_values = {
            name: value
            for name, value in vars(weights).items()
            if name.isupper()
        }
        strategy_method = SnakeStrategy.choose_move

        LearningAdvisor().analyze(self.summary(2, 18))

        self.assertEqual(
            weight_values,
            {
                name: value
                for name, value in vars(weights).items()
                if name.isupper()
            },
        )
        self.assertIs(SnakeStrategy.choose_move, strategy_method)


if __name__ == "__main__":
    unittest.main()
