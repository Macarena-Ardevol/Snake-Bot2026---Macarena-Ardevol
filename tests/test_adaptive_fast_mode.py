import asyncio
import contextlib
import io
import json
import time
import unittest
from collections import Counter

from ai.strategy import SnakeStrategy
from bot.client import BotClient
from bot.load_controller import AdaptiveLoadController
from game.board import GameBoard
from local_game.engine import LocalSnakeGame


SAFE_BOARD = """|Aa     |
|       |
|   *   |
|       |
|     B |
|     b |
|       |"""


class TestAdaptiveLoadController(unittest.TestCase):

    def test_levels_and_hysteresis_follow_executor_capacity(self):
        controller = AdaptiveLoadController(decision_workers=2)

        levels = [controller.decision_started().level for _ in range(33)]

        self.assertEqual(levels[:2], ["normal", "normal"])
        self.assertEqual(levels[2:32], ["busy"] * 30)
        self.assertEqual(levels[32], "critical")

        while controller.pending_decisions > 16:
            controller.decision_finished()
        self.assertEqual(controller.level, "busy")

        while controller.pending_decisions > 1:
            controller.decision_finished()
        self.assertEqual(controller.level, "normal")


class TestAdaptiveSnakeStrategy(unittest.TestCase):

    def test_default_is_exactly_explicit_normal_on_multiple_local_boards(self):
        for seed in range(5):
            game = LocalSnakeGame(
                strategy_a=SnakeStrategy(),
                strategy_b=SnakeStrategy(),
                seed=seed,
                max_moves=10,
            )
            board = GameBoard(game.board_text())
            implicit = SnakeStrategy()
            explicit = SnakeStrategy()

            implicit_move = implicit.choose_move(board, "A", 200, 0, 0)
            explicit_move = explicit.choose_move(
                board, "A", 200, 0, 0, compute_level="normal"
            )

            self.assertEqual(implicit_move, explicit_move)
            self.assertEqual(implicit.current_mode, explicit.current_mode)
            self.assertEqual(implicit.last_analysis, explicit.last_analysis)

    def test_busy_and_critical_keep_legal_safe_evaluation(self):
        board = GameBoard(SAFE_BOARD)

        for level in ("normal", "busy", "critical"):
            strategy = SnakeStrategy()
            move = strategy.choose_move(
                board, "A", 100, 0, 0, compute_level=level
            )

            self.assertEqual(move, "down")
            self.assertTrue(board.valid_moves("A")[move])
            self.assertEqual(strategy.last_compute_level, level)

        busy = SnakeStrategy()
        busy.choose_move(board, "A", 100, 0, 0, compute_level="busy")
        self.assertTrue(all(a["two_ply"] == 0 for a in busy.last_analysis.values()))

        critical = SnakeStrategy()
        critical.choose_move(board, "A", 100, 0, 0, compute_level="critical")
        for analysis in critical.last_analysis.values():
            if analysis["total"] == critical.evaluator.INVALID_MOVE_SCORE:
                continue
            self.assertEqual(analysis["lookahead"], 0)
            self.assertEqual(analysis["territory"], 0)
            self.assertEqual(analysis["bottleneck"], 0)
            self.assertNotEqual(analysis["space"], 0)

    def test_compute_level_is_per_call_and_does_not_stick(self):
        board = GameBoard(SAFE_BOARD)
        strategy = SnakeStrategy()

        strategy.choose_move(board, "A", compute_level="critical")
        restored_move = strategy.choose_move(board, "A")
        fresh = SnakeStrategy()
        fresh_move = fresh.choose_move(board, "A", compute_level="normal")

        self.assertEqual(strategy.last_compute_level, "normal")
        self.assertEqual(restored_move, fresh_move)
        self.assertEqual(strategy.last_analysis, fresh.last_analysis)


class TestAdaptiveClient(unittest.IsolatedAsyncioTestCase):

    @staticmethod
    def turn(index: int) -> dict:
        return {
            "board": SAFE_BOARD,
            "side": "A",
            "game_id": f"game_{index}",
            "turn_token": f"token_{index}",
            "remaining_moves": 100,
            "player_1": "bot",
            "player_2": f"rival_{index}",
            "score_1": 0,
            "score_2": 0,
        }

    async def test_burst_levels_are_per_turn_and_return_to_normal(self):
        chosen_levels = []

        class Strategy:
            current_mode = "balanced"
            last_enemy_prediction = None
            last_analysis = {"down": {"total": 1}}

            def set_opponent(self, opponent):
                pass

            def choose_move(self, *args, compute_level="normal"):
                chosen_levels.append(compute_level)
                time.sleep(0.01)
                return "down"

            def print_analysis(self):
                pass

        class WebSocket:
            def __init__(self):
                self.messages = []

            async def send(self, raw):
                self.messages.append(json.loads(raw))

        class Recorder:
            def record_turn(self, **kwargs):
                pass

        class Visualizer:
            def publish(self, state):
                pass

        client = BotClient("test", decision_workers=2)
        self.addCleanup(client.decision_executor.shutdown)
        self.addCleanup(client.background_executor.shutdown)
        client.recorder = Recorder()
        client.visualizer = Visualizer()
        client.strategies = {f"game_{i}": Strategy() for i in range(100)}
        websocket = WebSocket()

        with contextlib.redirect_stdout(io.StringIO()):
            await asyncio.gather(*(
                client.process_turn(websocket, self.turn(i))
                for i in range(100)
            ))

        counts = Counter(metric["compute_level"] for metric in client.decision_metrics)
        self.assertEqual(len(websocket.messages), 100)
        self.assertGreater(counts["critical"], 0)
        self.assertGreater(counts["busy"], 0)
        self.assertEqual(client.load_controller.level, "normal")
        self.assertEqual(client.load_controller.pending_decisions, 0)

        client.strategies["game_100"] = Strategy()
        with contextlib.redirect_stdout(io.StringIO()):
            await client.process_turn(websocket, self.turn(100))

        self.assertEqual(client.decision_metrics[-1]["compute_level"], "normal")
        self.assertEqual(client.decision_metrics[-1]["pending_decisions"], 1)
        self.assertEqual(len(client.event_tasks), 0)


if __name__ == "__main__":
    unittest.main()
