import json
import socket
import threading
import time
import unittest
from urllib.request import urlopen

from bot.visualizer import LiveStateHub, LiveVisualizer


class TestLiveStateHub(unittest.TestCase):

    @staticmethod
    def states(hub):
        return json.loads(hub.snapshot())["games"]

    @staticmethod
    def wait_until(condition, timeout=1.0, action=None):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            if action is not None:
                action()
            time.sleep(0.005)
        return condition()

    @staticmethod
    def subscriber_count(visualizer):
        with visualizer.hub._lock:
            return len(visualizer.hub._subscribers)

    @staticmethod
    def receive_until(client, expected, timeout=1.0):
        deadline = time.monotonic() + timeout
        received = b""
        while expected not in received and time.monotonic() < deadline:
            client.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                received += client.recv(8192)
            except TimeoutError:
                break
        return received

    def test_new_subscriber_receives_latest_state(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "game_1",
            "status": "playing",
            "score_1": 101,
        })

        subscriber = hub.subscribe()
        subscriber.get_nowait()
        message = hub.snapshot()

        self.assertIn('"status": "playing"', message)
        self.assertIn('"score_1": 101', message)

    def test_subscriber_receives_updates(self):
        hub = LiveStateHub()
        subscriber = hub.subscribe()
        subscriber.get_nowait()

        hub.publish({"game_id": "game_1", "direction": "right"})

        self.assertIsNone(subscriber.get_nowait())
        self.assertIn('"direction": "right"', hub.snapshot())

    def test_keeps_multiple_games_in_snapshot(self):
        hub = LiveStateHub()
        hub.publish({"game_id": "game_1", "score_1": 10})
        hub.publish({"game_id": "game_2", "score_1": 20})

        message = hub.subscribe().get_nowait()
        self.assertIsNone(message)
        snapshot = hub.snapshot()
        self.assertIn('"game_id": "game_1"', snapshot)
        self.assertIn('"game_id": "game_2"', snapshot)

    def test_supports_dashboard_sizes_without_mixing_games(self):
        for count in (1, 2, 10, 50, 70, 100):
            hub = LiveStateHub()
            for index in range(count):
                hub.publish({
                    "game_id": f"game_{index}",
                    "board": f"board_{index}",
                    "score_1": index,
                    "compute_level": ("normal", "busy", "critical")[index % 3],
                })

            states = {state["game_id"]: state for state in self.states(hub)}
            self.assertEqual(len(states), count)
            for index in range(count):
                self.assertEqual(states[f"game_{index}"]["board"], f"board_{index}")
                self.assertEqual(states[f"game_{index}"]["score_1"], index)

    def test_updates_merge_with_previous_state_for_same_game(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "same",
            "board": "first",
            "score_1": 1,
            "side": "B",
            "compute_level": "busy",
        })
        hub.publish({"game_id": "same", "board": "second", "score_1": 101})

        state = self.states(hub)[0]
        self.assertEqual(state["board"], "second")
        self.assertEqual(state["score_1"], 101)
        self.assertEqual(state["side"], "B")
        self.assertEqual(state["compute_level"], "busy")

    def test_same_rival_and_self_challenge_remain_distinct_by_game_id(self):
        hub = LiveStateHub()
        hub.publish({"game_id": "one", "player_1": "bot", "player_2": "Haunter", "side": "A"})
        hub.publish({"game_id": "two", "player_1": "bot", "player_2": "Haunter", "side": "B"})
        hub.publish({"game_id": "self", "player_1": "macarena", "player_2": "macarena", "side": "B"})

        states = {state["game_id"]: state for state in self.states(hub)}
        self.assertEqual(set(states), {"one", "two", "self"})
        self.assertEqual(states["one"]["side"], "A")
        self.assertEqual(states["two"]["side"], "B")
        self.assertEqual(states["self"]["player_1"], states["self"]["player_2"])

    def test_finished_games_keep_detail_and_recent_limit(self):
        hub = LiveStateHub(recent_limit=3)
        for index in range(5):
            game_id = f"finished_{index}"
            hub.publish({"game_id": game_id, "board": f"board_{index}", "side": "A"})
            hub.publish({
                "game_id": game_id,
                "status": "finished",
                "score_1": index + 1,
                "score_2": index,
                "winner": "bot",
            })
        hub.publish({"game_id": "active", "status": "playing"})

        states = {state["game_id"]: state for state in self.states(hub)}
        self.assertEqual(set(states), {"finished_2", "finished_3", "finished_4", "active"})
        self.assertEqual(states["finished_4"]["board"], "board_4")
        self.assertEqual(states["finished_4"]["status"], "finished")

    def test_concurrent_updates_preserve_all_game_identities(self):
        hub = LiveStateHub()
        threads = [
            threading.Thread(
                target=hub.publish,
                args=({"game_id": f"game_{index}", "score_1": index},),
            )
            for index in range(100)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        states = {state["game_id"]: state for state in self.states(hub)}
        self.assertEqual(len(states), 100)
        self.assertTrue(all(states[f"game_{i}"]["score_1"] == i for i in range(100)))

    def test_subscriber_queue_coalesces_visual_updates(self):
        hub = LiveStateHub()
        subscriber = hub.subscribe()
        subscriber.get_nowait()
        for score in range(100):
            hub.publish({"game_id": "game", "score_1": score})

        self.assertEqual(subscriber.qsize(), 1)
        subscriber.get_nowait()
        self.assertEqual(self.states(hub)[0]["score_1"], 99)

    def test_http_server_serves_visualizer(self):
        visualizer = LiveVisualizer(port=0)

        try:
            if not visualizer.start():
                self.skipTest("El entorno no permite abrir puertos locales")

            port = visualizer._server.server_address[1]

            with urlopen(f"http://127.0.0.1:{port}/health") as response:
                self.assertEqual(response.read(), b"ok")

            with urlopen(f"http://127.0.0.1:{port}/") as response:
                html = response.read()
                self.assertIn(b"Snake Bot", html)
                self.assertIn(b'id="dashboard"', html)
                self.assertIn(b'id="detailDialog"', html)
                self.assertIn(b"VICTORIA", html)
                self.assertIn(b"DERROTA", html)
                self.assertIn(b"EMPATE", html)
                self.assertIn(b"RENDER_INTERVAL_MS = 100", html)
        finally:
            visualizer.stop()

    def test_disconnected_sse_client_is_removed_without_server_error(self):
        visualizer = LiveVisualizer(port=0)
        if not visualizer.start():
            self.skipTest("El entorno no permite abrir un puerto local")

        errors = []
        server = visualizer._server
        server.handle_error = lambda request, address: errors.append(address)
        port = server.server_address[1]

        try:
            client = socket.create_connection(("127.0.0.1", port), timeout=2)
            client.sendall(
                b"GET /events HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Connection: close\r\n\r\n"
            )
            self.assertIn(b"200 OK", client.recv(8192))
            self.assertTrue(self.wait_until(
                lambda: self.subscriber_count(visualizer) == 1,
            ))
            client.close()

            score = iter(range(1000))
            self.assertTrue(self.wait_until(
                lambda: self.subscriber_count(visualizer) == 0,
                action=lambda: visualizer.publish({
                    "game_id": "active",
                    "score_1": next(score),
                }),
            ))
            self.assertEqual(errors, [])
        finally:
            visualizer.stop()

    def test_multiple_sse_clients_receive_updates_and_cleanup(self):
        visualizer = LiveVisualizer(port=0)
        if not visualizer.start():
            self.skipTest("El entorno no permite abrir un puerto local")

        clients = []
        port = visualizer._server.server_address[1]
        try:
            for _ in range(3):
                client = socket.create_connection(("127.0.0.1", port), timeout=2)
                client.sendall(b"GET /events HTTP/1.1\r\nHost: localhost\r\n\r\n")
                self.assertIn(b"200 OK", client.recv(8192))
                clients.append(client)

            self.assertTrue(self.wait_until(
                lambda: self.subscriber_count(visualizer) == 3,
            ))
            visualizer.publish({"game_id": "shared", "score_1": 7})
            for client in clients:
                self.assertIn(
                    b'"game_id": "shared"',
                    self.receive_until(client, b'"game_id": "shared"'),
                )
        finally:
            for client in clients:
                client.close()
            visualizer.stop()

    def test_stop_cleans_open_sse_subscribers(self):
        visualizer = LiveVisualizer(port=0)
        if not visualizer.start():
            self.skipTest("El entorno no permite abrir un puerto local")

        client = socket.create_connection(
            ("127.0.0.1", visualizer._server.server_address[1]),
            timeout=2,
        )
        try:
            client.sendall(b"GET /events HTTP/1.1\r\nHost: localhost\r\n\r\n")
            self.assertIn(b"200 OK", client.recv(8192))
            self.assertTrue(self.wait_until(
                lambda: self.subscriber_count(visualizer) == 1,
            ))

            visualizer.stop()

            self.assertTrue(self.wait_until(
                lambda: self.subscriber_count(visualizer) == 0,
            ))
        finally:
            client.close()
            visualizer.stop()


if __name__ == "__main__":
    unittest.main()
