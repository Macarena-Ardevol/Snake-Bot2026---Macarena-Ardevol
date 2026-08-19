import io
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.visualizer import LiveStateHub, LiveVisualizer


class FakeServer:
    def __init__(self, address, handler):
        self.server_address = (address[0], 43210)
        self.handler = handler
        self.serve_forever = MagicMock()
        self.shutdown = MagicMock()
        self.server_close = MagicMock()


class TestVisualizerLifecycle(unittest.TestCase):
    @patch("bot.visualizer.ThreadingHTTPServer", side_effect=OSError("port busy"))
    def test_start_returns_false_when_server_cannot_bind(self, server_class):
        visualizer = LiveVisualizer(port=8765)
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertFalse(visualizer.start())
        self.assertIn("port busy", output.getvalue())
        server_class.assert_called_once()

    @patch("bot.visualizer.ThreadingHTTPServer", side_effect=FakeServer)
    def test_start_is_idempotent_and_stop_releases_server(self, server_class):
        visualizer = LiveVisualizer(port=0)
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertTrue(visualizer.start())
            server = visualizer._server
            self.assertTrue(visualizer.start())
        self.assertEqual(server_class.call_count, 1)
        self.assertIn("43210", output.getvalue())

        visualizer.stop()
        server.shutdown.assert_called_once_with()
        server.server_close.assert_called_once_with()
        self.assertIsNone(visualizer._server)
        self.assertIsNone(visualizer._thread)
        visualizer.stop()

    def test_publish_delegates_to_hub(self):
        visualizer = LiveVisualizer()
        visualizer.hub.publish = MagicMock()
        state = {"game_id": "one", "score_1": 7}
        visualizer.publish(state)
        visualizer.hub.publish.assert_called_once_with(state)


class TestVisualizerHandler(unittest.TestCase):
    def setUp(self):
        self.visualizer = LiveVisualizer()
        self.handler_class = self.visualizer._make_handler()

    def handler(self):
        handler = self.handler_class.__new__(self.handler_class)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.send_error = MagicMock()
        handler.wfile = MagicMock()
        return handler

    def test_get_routes_index_events_health_and_not_found(self):
        handler = self.handler()
        handler._serve_index = MagicMock()
        handler._serve_events = MagicMock()
        handler._send_bytes = MagicMock()

        for path in ("/", "/index.html"):
            handler.path = path
            handler.do_GET()
        handler.path = "/events"
        handler.do_GET()
        handler.path = "/health"
        handler.do_GET()
        handler.path = "/missing"
        handler.do_GET()

        self.assertEqual(handler._serve_index.call_count, 2)
        handler._serve_events.assert_called_once_with()
        handler._send_bytes.assert_called_once_with(b"ok", "text/plain; charset=utf-8")
        handler.send_error.assert_called_once_with(404)

    def test_index_serves_bytes_and_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "index.html"
            index.write_bytes(b"<h1>dashboard</h1>")
            visualizer = LiveVisualizer()
            visualizer._index = index
            handler_class = visualizer._make_handler()
            handler = handler_class.__new__(handler_class)
            handler._send_bytes = MagicMock()
            handler.send_error = MagicMock()
            handler._serve_index()
            handler._send_bytes.assert_called_once_with(
                b"<h1>dashboard</h1>", "text/html; charset=utf-8"
            )

            index.unlink()
            handler._serve_index()
            handler.send_error.assert_called_once_with(500)

    def test_send_bytes_writes_complete_http_response(self):
        handler = self.handler()
        handler._send_bytes(b"payload", "text/plain")
        handler.send_response.assert_called_once_with(200)
        self.assertEqual(
            handler.send_header.call_args_list[1].args,
            ("Content-Length", "7"),
        )
        handler.wfile.write.assert_called_once_with(b"payload")

    def test_sse_disconnect_always_unsubscribes(self):
        handler = self.handler()
        handler.wfile.write.side_effect = BrokenPipeError
        handler._serve_events()
        self.assertEqual(len(self.visualizer.hub._subscribers), 0)
        self.assertTrue(handler.close_connection)

    def test_sse_keepalive_exits_cleanly_when_stopping(self):
        handler = self.handler()
        subscriber = MagicMock()
        subscriber.get.side_effect = queue.Empty
        self.visualizer.hub.subscribe = MagicMock(return_value=subscriber)
        self.visualizer.hub.unsubscribe = MagicMock()

        def stop_after_write(_message):
            self.visualizer._stopping.set()

        handler.wfile.write.side_effect = stop_after_write
        handler._serve_events()
        handler.wfile.write.assert_called_once_with(b": keep-alive\n\n")
        self.visualizer.hub.unsubscribe.assert_called_once_with(subscriber)


class TestHubNotification(unittest.TestCase):
    def test_notify_subscribers_coalesces_when_queue_is_full(self):
        hub = LiveStateHub()
        subscriber = hub.subscribe()
        hub.notify_subscribers()
        self.assertEqual(subscriber.qsize(), 1)
        hub.unsubscribe(subscriber)
        self.assertEqual(len(hub._subscribers), 0)


if __name__ == "__main__":
    unittest.main()
