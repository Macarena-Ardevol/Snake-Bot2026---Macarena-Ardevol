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
    def record_turn(self, **kwargs) -> None:
        return


class SlowStrategy:
    def __init__(self) -> None:
        self.last_enemy_prediction = None
        self.last_analysis = {"down": {"total": 1}}
        self.opponent = None

    def set_opponent(self, opponent: str | None) -> None:
        self.opponent = opponent

    def choose_move(self, *args) -> str:
        time.sleep(0.15)
        return "down"

    def print_analysis(self) -> None:
        return


class TestClientConcurrency(unittest.IsolatedAsyncioTestCase):

    async def test_two_games_calculate_moves_concurrently(self):
        client = BotClient("test-token")
        client.recorder = FakeRecorder()
        client.strategies = {
            "game_1": SlowStrategy(),
            "game_2": SlowStrategy(),
        }
        websocket = FakeWebSocket()

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

        started = time.perf_counter()
        await asyncio.gather(
            client.process_turn(websocket, turn("game_1", "rival_1")),
            client.process_turn(websocket, turn("game_2", "rival_2")),
        )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.27)
        self.assertEqual(len(websocket.messages), 2)
        self.assertEqual(
            {message["data"]["game_id"] for message in websocket.messages},
            {"game_1", "game_2"},
        )
        self.assertIsNot(client.strategies["game_1"], client.strategies["game_2"])


if __name__ == "__main__":
    unittest.main()
