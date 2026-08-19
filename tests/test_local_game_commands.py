import io
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import run
from local_game import benchmark, mirror_benchmark, profile_strategy, run_matches


def result(winner=None, score_a=0, score_b=0, turns=10, crashed_side=None):
    return SimpleNamespace(
        winner=winner,
        score_a=score_a,
        score_b=score_b,
        turns=turns,
        crashed_side=crashed_side,
    )


class TestRunCommand(unittest.TestCase):
    @patch("run.BotClient")
    def test_main_uses_command_line_token_and_starts_client(self, client_class):
        with patch.object(sys, "argv", ["run.py", "argument-token"]), patch.object(
            run, "BOT_TOKEN", "environment-token"
        ):
            run.main()

        client_class.assert_called_once_with("argument-token")
        client_class.return_value.start.assert_called_once_with()

    @patch("run.BotClient")
    def test_main_uses_environment_token_when_argument_is_absent(self, client_class):
        with patch.object(sys, "argv", ["run.py"]), patch.object(
            run, "BOT_TOKEN", "environment-token"
        ):
            run.main()

        client_class.assert_called_once_with("environment-token")
        client_class.return_value.start.assert_called_once_with()

    @patch("run.BotClient")
    def test_main_rejects_missing_token_before_creating_client(self, client_class):
        with patch.object(sys, "argv", ["run.py"]), patch.object(run, "BOT_TOKEN", None):
            with self.assertRaisesRegex(SystemExit, "Falta el token"):
                run.main()
        client_class.assert_not_called()


class TestPairedBenchmark(unittest.TestCase):
    @patch("local_game.benchmark.LocalSnakeGame")
    def test_play_pair_alternates_sides_and_aggregates_results(self, game_class):
        game_class.return_value.play.side_effect = [
            result("A", 250, 100, crashed_side="B"),
            result("A", 300, 180, crashed_side="B"),
        ]
        opponent_factory = MagicMock(side_effect=lambda: object())

        totals = benchmark.play_pair(7, opponent_factory)

        self.assertEqual(totals["advanced_wins"], 1)
        self.assertEqual(totals["opponent_wins"], 1)
        self.assertEqual(totals["opponent_crashes"], 1)
        self.assertEqual(totals["advanced_crashes"], 1)
        self.assertEqual(totals["advanced_score"], 430)
        self.assertEqual(totals["opponent_score"], 400)
        self.assertEqual(game_class.call_count, 2)
        self.assertTrue(all(item.kwargs["seed"] == 7 for item in game_class.call_args_list))

    @patch("local_game.benchmark.play_pair")
    def test_benchmark_opponent_prints_accumulated_summary(self, play_pair):
        play_pair.side_effect = [
            {
                "advanced_wins": 1, "opponent_wins": 0, "draws": 1,
                "advanced_crashes": 0, "opponent_crashes": 0,
                "advanced_score": 300, "opponent_score": 200,
            },
            {
                "advanced_wins": 0, "opponent_wins": 1, "draws": 1,
                "advanced_crashes": 1, "opponent_crashes": 0,
                "advanced_score": 100, "opponent_score": 250,
            },
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            benchmark.benchmark_opponent("prueba", object, number_of_pairs=2)

        text = output.getvalue()
        self.assertIn("Partidas: 4", text)
        self.assertIn("Victorias avanzadas: 1", text)
        self.assertIn("Tasa de victoria: 25.00%", text)
        self.assertEqual(play_pair.call_args_list, [call(0, object), call(1, object)])

    @patch("local_game.benchmark.benchmark_opponent")
    def test_run_benchmark_executes_each_supported_opponent(self, run_opponent):
        benchmark.run_benchmark()
        self.assertEqual(run_opponent.call_count, 3)
        self.assertEqual(
            [args.args[0] for args in run_opponent.call_args_list],
            ["BFS básico", "supervivencia", "aleatorio seguro"],
        )


class TestRunMatches(unittest.TestCase):
    @patch("local_game.run_matches.LocalSnakeGame")
    def test_run_single_match_places_advanced_strategy_on_requested_side(self, game_class):
        expected = result("A")
        game_class.return_value.play.return_value = expected

        self.assertIs(run_matches.run_single_match(3, "A"), expected)
        first = game_class.call_args
        self.assertEqual(first.kwargs["seed"], 3)
        self.assertEqual(first.kwargs["strategy_a"].__class__.__name__, "SnakeStrategy")
        self.assertEqual(first.kwargs["strategy_b"].__class__.__name__, "BaselineStrategy")

        run_matches.run_single_match(4, "B")
        second = game_class.call_args
        self.assertEqual(second.kwargs["strategy_a"].__class__.__name__, "BaselineStrategy")
        self.assertEqual(second.kwargs["strategy_b"].__class__.__name__, "SnakeStrategy")

    @patch("local_game.run_matches.run_single_match")
    def test_run_matches_accumulates_score_crashes_sides_and_draws(self, single_match):
        single_match.side_effect = [
            result("A", 300, 100, turns=20),
            result(None, 150, 150, turns=30),
            result("B", 100, 1200, turns=12, crashed_side="A"),
            result("A", 1300, 100, turns=13, crashed_side="B"),
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            run_matches.run_matches(number_of_pairs=2)

        text = output.getvalue()
        self.assertIn("Partidas: 4", text)
        self.assertIn("Bot avanzado: 1", text)
        self.assertIn("Bot básico: 2", text)
        self.assertIn("Empates: 1", text)
        self.assertIn("Avanzado como A: 1 (50.00%)", text)
        self.assertIn("Avanzado como B: 0 (0.00%)", text)
        self.assertIn("Tasa de victoria avanzada: 25.00%", text)
        self.assertEqual(single_match.call_count, 4)


class TestMirrorBenchmark(unittest.TestCase):
    @patch("local_game.mirror_benchmark.LocalSnakeGame")
    def test_mirror_benchmark_aggregates_wins_draws_crashes_and_scores(self, game_class):
        game_class.return_value.play.side_effect = [
            result("A", 300, 100, 20, "B"),
            result("B", 120, 320, 30, "A"),
            result(None, 200, 200, 40, None),
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            mirror_benchmark.run_mirror_benchmark(3)

        text = output.getvalue()
        self.assertIn("Partidas: 3", text)
        self.assertIn("A: 1", text)
        self.assertIn("B: 1", text)
        self.assertIn("Empates: 1", text)
        self.assertIn("Puntaje A: 206.67", text)
        self.assertIn("Turnos: 30.00", text)
        self.assertEqual([c.kwargs["seed"] for c in game_class.call_args_list], [0, 1, 2])


class TestProfileStrategy(unittest.TestCase):
    def test_percentile_handles_empty_and_orders_values(self):
        self.assertEqual(profile_strategy.percentile([], 0.95), 0.0)
        self.assertEqual(profile_strategy.percentile([0.3, 0.1, 0.2], 0.5), 0.2)

    @patch("local_game.profile_strategy.LocalSnakeGame")
    @patch("local_game.profile_strategy.TimedStrategy")
    def test_profile_prints_average_p95_and_maximum(self, timed_class, game_class):
        timed_class.side_effect = [
            SimpleNamespace(decision_times=[0.001, 0.003]),
            SimpleNamespace(decision_times=[0.002, 0.004]),
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            profile_strategy.profile_strategy(2)

        text = output.getvalue()
        self.assertIn("Decisiones medidas: 4", text)
        self.assertIn("Promedio: 2.50 ms", text)
        self.assertIn("Percentil 95: 3.00 ms", text)
        self.assertIn("Máximo: 4.00 ms", text)
        self.assertEqual(game_class.return_value.play.call_count, 2)

    @patch("local_game.profile_strategy.LocalSnakeGame")
    @patch("local_game.profile_strategy.TimedStrategy")
    def test_profile_reports_when_no_decisions_were_measured(self, timed_class, game_class):
        timed_class.return_value.decision_times = []
        output = io.StringIO()
        with redirect_stdout(output):
            profile_strategy.profile_strategy(1)
        self.assertEqual(output.getvalue().strip(), "No se registraron movimientos.")
        game_class.return_value.play.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
