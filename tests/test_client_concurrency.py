import asyncio
import json
import time
import unittest

from bot.client import BotClient


BOARD = """|       |
| aaA   |
|       |
|   *   |
|       |
|   Bbb |
|       |"""


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send(self, raw_message: str) -> None:
        self.messages.append(json.loads(raw_message))


class FakeRecorder:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events
        self.last_turn = None
        self.turns = {}

    def record_turn(self, **kwargs) -> None:
        self.last_turn = kwargs
        self.turns[kwargs["game_id"]] = kwargs
        if self.events is not None:
            self.events.append(f"record:{kwargs.get('mode')}")

    def finish_game(self, game_id, data):
        if self.events is not None:
            self.events.append(f"finish:{game_id}")
        return f"game_{game_id}.json"


class FakeVisualizer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def publish(self, state: dict) -> None:
        self.events.append("visualize")


class SlowStrategy:
    def __init__(self, events: list[str] | None = None) -> None:
        self.last_enemy_prediction = None
        self.last_analysis = {"down": {"total": 1}}
        self.opponent = None
        self.current_mode = "balanced"
        self.last_decision_context = {}
        self.events = events

    def set_opponent(self, opponent: str | None) -> None:
        self.opponent = opponent

    def choose_move(self, *args, **kwargs) -> str:
        if self.events is not None:
            self.events.append("decide")
        time.sleep(0.15)
        return "down"

    def print_analysis(self) -> None:
        if self.events is not None:
            self.events.append("print")


class TestClientConcurrency(unittest.IsolatedAsyncioTestCase):

    @staticmethod
    def turn(game_id: str, opponent: str) -> dict:
        return {
            "board": BOARD,
            "side": "A",
            "game_id": game_id,
            "turn_token": f"token_{game_id}",
            "remaining_moves": 100,
            "player_1": "my_bot",
            "player_2": opponent,
            "score_1": 0,
            "score_2": 0,
        }

    async def test_two_games_calculate_moves_concurrently(self):
        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies = {
            "game_1": SlowStrategy(),
            "game_2": SlowStrategy(),
        }
        websocket = FakeWebSocket()

        started = time.perf_counter()
        await asyncio.gather(
            client.process_turn(websocket, self.turn("game_1", "rival_1")),
            client.process_turn(websocket, self.turn("game_2", "rival_2")),
        )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.27)
        self.assertEqual(len(websocket.messages), 2)
        self.assertEqual(
            {message["data"]["game_id"] for message in websocket.messages},
            {"game_1", "game_2"},
        )
        self.assertIsNot(client.strategies["game_1"], client.strategies["game_2"])

    async def test_sends_move_before_observation_recording_and_printing(self):
        events = []
        client = BotClient("test-token")
        recorder = FakeRecorder(events)
        strategy = SlowStrategy(events)
        client.recorder = recorder
        client.visualizer = FakeVisualizer(events)
        client.strategies = {"game_order": strategy}
        client.previous_boards["game_order"] = object()
        client._observe_opponent = lambda **kwargs: events.append("observe")

        class OrderedWebSocket(FakeWebSocket):
            async def send(inner_self, raw_message: str) -> None:
                events.append("send")
                await super().send(raw_message)

        websocket = OrderedWebSocket()
        await client.process_turn(
            websocket,
            self.turn("game_order", "rival"),
        )

        self.assertEqual(
            events,
            [
                "decide",
                "send",
                "visualize",
                "observe",
                "record:balanced",
                "print",
            ],
        )
        self.assertEqual(websocket.messages[0]["data"]["direction"], "down")
        self.assertEqual(recorder.last_turn["mode"], "balanced")

    async def test_visualizer_failure_happens_after_send_and_does_not_skip_recording(self):
        events = []
        client = BotClient("test-token")
        client.recorder = FakeRecorder(events)
        client.strategies = {"visual_failure": SlowStrategy(events)}

        class FailingVisualizer:
            def publish(self, state):
                events.append("visualize")
                raise RuntimeError("browser unavailable")

        class OrderedWebSocket(FakeWebSocket):
            async def send(inner_self, raw_message):
                events.append("send")
                await super().send(raw_message)

        client.visualizer = FailingVisualizer()
        websocket = OrderedWebSocket()
        await client.process_turn(
            websocket,
            self.turn("visual_failure", "rival"),
        )

        self.assertEqual(events[:3], ["decide", "send", "visualize"])
        self.assertIn("record:balanced", events)
        self.assertEqual(len(websocket.messages), 1)

    async def test_many_games_send_correct_identifiers_and_isolated_state(self):
        class FastStrategy(SlowStrategy):
            def choose_move(self, *args, **kwargs) -> str:
                return "down"

        for game_count in (2, 10, 50, 70, 100):
            client = BotClient("test-token")
            client.recorder = FakeRecorder()
            client.strategies = {
                f"game_{index}": FastStrategy()
                for index in range(game_count)
            }
            for index, strategy in enumerate(client.strategies.values()):
                strategy.last_enemy_prediction = f"prediction_{index}"
                strategy.last_analysis = {"down": {"total": index}}
                strategy.current_mode = f"mode_{index}"
                strategy.last_decision_context = {
                    "marker": f"context_{index}"
                }
            websocket = FakeWebSocket()

            await asyncio.gather(*(
                client.process_turn(
                    websocket,
                    self.turn(f"game_{index}", f"rival_{index}"),
                )
                for index in range(game_count)
            ))

            self.assertEqual(len(websocket.messages), game_count)
            for message in websocket.messages:
                game_id = message["data"]["game_id"]
                self.assertEqual(message["data"]["turn_token"], f"token_{game_id}")
                self.assertEqual(message["data"]["direction"], "down")
            self.assertEqual(len({id(value) for value in client.strategies.values()}), game_count)
            self.assertEqual(len(client.enemy_predictions), game_count)
            for index in range(game_count):
                recorded = client.recorder.turns[f"game_{index}"]
                self.assertEqual(recorded["analysis"]["down"]["total"], index)
                self.assertEqual(recorded["mode"], f"mode_{index}")
                self.assertEqual(
                    recorded["decision_context"]["marker"],
                    f"context_{index}",
                )
                self.assertIn(recorded["compute_level"], ("normal", "busy", "critical"))
                self.assertGreaterEqual(recorded["decision_metrics"]["pending_decisions"], 1)
                self.assertGreaterEqual(recorded["decision_metrics"]["decision_ms"], 0)
                self.assertGreaterEqual(recorded["decision_metrics"]["receive_to_send_ms"], 0)
                self.assertEqual(
                    client.enemy_predictions[f"game_{index}"],
                    f"prediction_{index}",
                )

    async def test_turns_of_same_game_are_strictly_ordered(self):
        events = []

        class OrderedStrategy(SlowStrategy):
            def choose_move(
                inner_self, board, side, remaining, own, enemy, **kwargs
            ):
                events.append(f"start:{remaining}")
                time.sleep(0.02)
                events.append(f"end:{remaining}")
                return "down"

        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies = {"same": OrderedStrategy()}
        websocket = FakeWebSocket()
        first = self.turn("same", "rival")
        second = self.turn("same", "rival")
        first["remaining_moves"] = 10
        second["remaining_moves"] = 9
        second["turn_token"] = "token_second"

        await asyncio.gather(
            client.process_turn(websocket, first),
            client.process_turn(websocket, second),
        )

        self.assertEqual(events, ["start:10", "end:10", "start:9", "end:9"])
        self.assertEqual(
            [message["data"]["turn_token"] for message in websocket.messages],
            ["token_same", "token_second"],
        )

    async def test_game_over_cleans_only_its_session(self):
        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies = {"one": SlowStrategy(), "two": SlowStrategy()}
        client.previous_boards = {"one": object(), "two": object()}
        client.opponents = {"two": "r2"}
        client.game_locks = {"one": asyncio.Lock(), "two": asyncio.Lock()}
        client.bot_sides = {"one": "B", "two": "A"}

        await client.process_game_over({
            "game_id": "one", "player_1": "me", "player_2": "r1",
            "winner": "me", "score_1": 1, "score_2": 0,
        })

        self.assertNotIn("one", client.strategies)
        self.assertIn("two", client.strategies)
        self.assertIn("two", client.previous_boards)
        self.assertIn("two", client.game_locks)
        self.assertNotIn("one", client.bot_sides)
        self.assertEqual(client.bot_sides["two"], "A")

    async def test_game_over_publishes_established_side_not_contradictory_side(self):
        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies["real-game"] = SlowStrategy()
        turn = self.turn("real-game", "macarenaardevol")
        turn.update({
            "side": "B", "player_1": "arielcohen",
            "player_2": "macarenaardevol", "score_1": 1635,
            "score_2": 1139,
        })
        await client.process_turn(FakeWebSocket(), turn)
        self.assertEqual(client.bot_sides["real-game"], "B")

        await client.process_game_over({
            "game_id": "real-game", "side": "A",
            "player_1": "arielcohen", "player_2": "macarenaardevol",
            "score_1": 1635, "score_2": 1140, "winner": "arielcohen",
        })

        final_state = client.visualizer.hub._games["real-game"]
        self.assertEqual(final_state["side"], "B")
        self.assertEqual(final_state["status"], "finished")

    async def test_strategy_exception_does_not_cancel_other_games(self):
        class BrokenStrategy(SlowStrategy):
            def choose_move(self, *args, **kwargs):
                raise RuntimeError("broken")

        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies = {"broken": BrokenStrategy(), "healthy": SlowStrategy()}
        websocket = FakeWebSocket()

        await asyncio.gather(
            client.process_turn(websocket, self.turn("broken", "r1")),
            client.process_turn(websocket, self.turn("healthy", "r2")),
        )

        self.assertEqual({m["data"]["game_id"] for m in websocket.messages}, {"broken", "healthy"})

    async def test_recorder_failure_happens_after_send(self):
        events = []
        client = BotClient("test-token")
        client.strategies = {"game": SlowStrategy(events)}

        class BrokenRecorder:
            def record_turn(self, **kwargs):
                events.append("record")
                raise RuntimeError("disk unavailable")

        class OrderedSocket(FakeWebSocket):
            async def send(inner_self, raw_message):
                events.append("send")
                await super().send(raw_message)

        client.recorder = BrokenRecorder()
        websocket = OrderedSocket()
        with self.assertRaises(RuntimeError):
            await client.process_turn(websocket, self.turn("game", "rival"))

        self.assertEqual(events[:3], ["decide", "send", "record"])
        self.assertEqual(len(websocket.messages), 1)

    async def test_listener_finishes_without_orphan_event_tasks(self):
        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies = {"game_1": SlowStrategy(), "game_2": SlowStrategy()}

        class Incoming(FakeWebSocket):
            def __init__(inner_self):
                super().__init__()
                inner_self.events = iter([
                    json.dumps({"event": "your_turn", "data": self.turn("game_1", "r1")}),
                    json.dumps({"event": "your_turn", "data": self.turn("game_2", "r2")}),
                ])
            def __aiter__(inner_self):
                return inner_self
            async def __anext__(inner_self):
                try:
                    return next(inner_self.events)
                except StopIteration:
                    raise StopAsyncIteration

        websocket = Incoming()
        await client.listen(websocket)

        self.assertEqual(len(websocket.messages), 2)
        self.assertEqual(client.event_tasks, set())


if __name__ == "__main__":
    unittest.main()
