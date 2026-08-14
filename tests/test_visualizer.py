import unittest
from urllib.request import urlopen

from bot.visualizer import LiveStateHub, LiveVisualizer


class TestLiveStateHub(unittest.TestCase):

    def test_new_subscriber_receives_latest_state(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "game_1",
            "status": "playing",
            "score_1": 101,
        })

        subscriber = hub.subscribe()
        message = subscriber.get_nowait()

        self.assertIn('"status": "playing"', message)
        self.assertIn('"score_1": 101', message)

    def test_subscriber_receives_updates(self):
        hub = LiveStateHub()
        subscriber = hub.subscribe()
        subscriber.get_nowait()

        hub.publish({"game_id": "game_1", "direction": "right"})

        self.assertIn('"direction": "right"', subscriber.get_nowait())

    def test_keeps_multiple_games_in_snapshot(self):
        hub = LiveStateHub()
        hub.publish({"game_id": "game_1", "score_1": 10})
        hub.publish({"game_id": "game_2", "score_1": 20})

        message = hub.subscribe().get_nowait()

        self.assertIn('"game_id": "game_1"', message)
        self.assertIn('"game_id": "game_2"', message)

    def test_http_server_serves_visualizer(self):
        visualizer = LiveVisualizer(port=0)

        try:
            if not visualizer.start():
                self.skipTest("El entorno no permite abrir puertos locales")

            port = visualizer._server.server_address[1]

            with urlopen(f"http://127.0.0.1:{port}/health") as response:
                self.assertEqual(response.read(), b"ok")

            with urlopen(f"http://127.0.0.1:{port}/") as response:
                self.assertIn(b"Snake Bot", response.read())
        finally:
            visualizer.stop()


if __name__ == "__main__":
    unittest.main()
