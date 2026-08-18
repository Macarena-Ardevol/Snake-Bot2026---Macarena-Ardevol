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
    def perspective(state):
        side = state["side"]
        if side == "A":
            own_player, rival = state["player_1"], state["player_2"]
            own_score, rival_score = state["score_1"], state["score_2"]
        else:
            own_player, rival = state["player_2"], state["player_1"]
            own_score, rival_score = state["score_2"], state["score_1"]
        if own_score > rival_score:
            standing, result = "GANANDO", "VICTORIA"
        elif own_score < rival_score:
            standing, result = "PERDIENDO", "DERROTA"
        else:
            standing = result = "EMPATE"
        return own_player, rival, own_score, rival_score, standing, result

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

    def test_bot_as_a_and_b_uses_its_side_for_wins_and_losses(self):
        cases = (
            ("a-win", "A", 20, 10, "bot", 20, "GANANDO", "VICTORIA"),
            ("b-win", "B", 10, 20, "bot", 20, "GANANDO", "VICTORIA"),
            ("a-loss", "A", 10, 20, "bot", 10, "PERDIENDO", "DERROTA"),
            ("b-loss", "B", 20, 10, "bot", 10, "PERDIENDO", "DERROTA"),
            ("draw", "B", 15, 15, "bot", 15, "EMPATE", "EMPATE"),
        )
        hub = LiveStateHub()
        for game_id, side, score_1, score_2, player, score, standing, result in cases:
            hub.publish({
                "game_id": game_id, "side": side,
                "player_1": "bot" if side == "A" else "rival",
                "player_2": "bot" if side == "B" else "rival",
                "score_1": score_1, "score_2": score_2,
                "status": "finished",
            })
        states = {state["game_id"]: state for state in self.states(hub)}
        for game_id, _, _, _, player, score, standing, result in cases:
            own, rival, own_score, _, actual_standing, actual_result = self.perspective(states[game_id])
            self.assertEqual((own, own_score), (player, score))
            self.assertEqual((actual_standing, actual_result), (standing, result))
            self.assertEqual(rival, "rival")

    def test_real_bot_a_game_over_preserves_identity_and_result(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "73452406", "side": "A", "status": "playing",
            "player_1": "macarenaardevol", "player_2": "maximoadarvez",
            "score_1": 1238, "score_2": 1139, "board": "last-a-board",
            "direction": "left", "mode": "defensive", "compute_level": "normal",
        })
        hub.publish({
            "game_id": "73452406", "side": "A", "status": "finished",
            "player_1": "macarenaardevol", "player_2": "maximoadarvez",
            "score_1": 1239, "score_2": 1140, "winner": "macarenaardevol",
        })
        state = self.states(hub)[0]
        self.assertEqual(
            self.perspective(state),
            ("macarenaardevol", "maximoadarvez", 1239, 1140, "GANANDO", "VICTORIA"),
        )
        self.assertEqual((state["board"], state["direction"], state["mode"]),
                         ("last-a-board", "left", "defensive"))

    def test_real_bot_b_rejects_valid_but_contradictory_final_side(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "bce5e99c", "side": "B", "status": "playing",
            "player_1": "arielcohen", "player_2": "macarenaardevol",
            "score_1": 1635, "score_2": 1139, "board": "last-b-board",
            "direction": "down", "mode": "aggressive", "compute_level": "normal",
        })
        hub.publish({
            "game_id": "bce5e99c", "side": "A", "status": "finished",
            "player_1": "arielcohen", "player_2": "macarenaardevol",
            "score_1": 1635, "score_2": 1140, "winner": "arielcohen",
        })
        state = self.states(hub)[0]
        self.assertEqual(state["side"], "B")
        self.assertEqual(state["board"], "last-b-board")
        self.assertEqual(state["direction"], "down")
        self.assertEqual(state["mode"], "aggressive")
        self.assertEqual(state["compute_level"], "normal")
        self.assertEqual(
            self.perspective(state),
            ("macarenaardevol", "arielcohen", 1140, 1635, "PERDIENDO", "DERROTA"),
        )

    def test_game_over_cannot_swap_established_players(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "stable-identity", "side": "B", "status": "playing",
            "player_1": "rival", "player_2": "macarenaardevol",
            "score_1": 10, "score_2": 20,
        })
        hub.publish({
            "game_id": "stable-identity", "side": "A", "status": "finished",
            "player_1": "macarenaardevol", "player_2": "rival",
            "score_1": 10, "score_2": 20, "winner": "macarenaardevol",
        })
        state = self.states(hub)[0]
        self.assertEqual((state["side"], state["player_1"], state["player_2"]),
                         ("B", "rival", "macarenaardevol"))

    def test_self_challenge_and_multiple_games_keep_side_perspective(self):
        hub = LiveStateHub()
        hub.publish({
            "game_id": "self-a", "side": "A", "player_1": "macarenaardevol",
            "player_2": "macarenaardevol", "score_1": 30, "score_2": 20,
        })
        hub.publish({
            "game_id": "self-b", "side": "B", "player_1": "macarenaardevol",
            "player_2": "macarenaardevol", "score_1": 30, "score_2": 20,
        })
        states = {state["game_id"]: state for state in self.states(hub)}
        self.assertEqual(self.perspective(states["self-a"])[2:5], (30, 20, "GANANDO"))
        self.assertEqual(self.perspective(states["self-b"])[2:5], (20, 30, "PERDIENDO"))
        self.assertEqual(states["self-a"]["side"], "A")
        self.assertEqual(states["self-b"]["side"], "B")

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
                self.assertIn(b"--status-size: clamp(24px, 3vw, 38px)", html)
                self.assertIn(b"--score-size: clamp(17px, 1.05vw, 20px)", html)
                self.assertIn(b"--moves-size: clamp(18px, 1.15vw, 22px)", html)
                self.assertIn(b"width: min(100%, var(--board-max))", html)
                self.assertIn(b'class="score-row own-score"', html)
                self.assertIn(b'class="score-row rival-score"', html)
                self.assertIn(b"MOVIMIENTOS", html)
                self.assertIn(b"GANANDO", html)
                self.assertIn(b"PERDIENDO", html)
                self.assertIn(b"function standing(state)", html)
                self.assertIn(b"state.status === 'finished' ? resultLabel(outcome) : position.label", html)
                self.assertIn(
                    b"state.side === 'B' ? (state.score_2 ?? 0) : (state.score_1 ?? 0)",
                    html,
                )
                self.assertIn(
                    b"state.side === 'B' ? (state.score_1 ?? 0) : (state.score_2 ?? 0)",
                    html,
                )
                self.assertIn(b"function isSelfChallenge(state)", html)
                self.assertIn(b"function sideClass(side)", html)
                self.assertIn(b"side === 'B' ? 'side-b' : 'side-a'", html)
                self.assertIn(b"sideClass(state.side)", html)
                self.assertIn(b"sideClass(rivalSide(state))", html)
                self.assertIn(b"MI BOT", html)
                self.assertIn(b".side-dot.side-a { color: var(--a); background: var(--a); }", html)
                self.assertIn(b".side-dot.side-b { color: var(--b); background: var(--b); }", html)
                self.assertIn(b"A: cssColor('--a')", html)
                self.assertIn(b"B: cssColor('--b')", html)
                self.assertIn(b"detailIdentityRow('Mi bot'", html)
                self.assertIn(b"detailIdentityRow('Rival'", html)
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
