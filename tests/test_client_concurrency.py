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

    def record_turn(self, **kwargs) -> None:
        self.last_turn = kwargs
        if self.events is not None:
            self.events.append(f"record:{kwargs.get('mode')}")


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
        self.events = events

    def set_opponent(self, opponent: str | None) -> None:
        self.opponent = opponent

    def choose_move(self, *args) -> str:
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


if __name__ == "__main__":
    unittest.main()
