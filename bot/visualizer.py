import json
import queue
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class LiveStateHub:
    """Distribuye el último estado del juego a los navegadores conectados."""

    def __init__(self, recent_limit: int = 50) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue[None]] = set()
        self._games: dict[str, dict[str, Any]] = {}
        self._finished_order: list[str] = []
        self.recent_limit = max(0, recent_limit)

    def publish(self, state: dict[str, Any]) -> None:
        with self._lock:
            game_id = state.get("game_id")

            if game_id:
                key = str(game_id)
                previous = self._games.get(key, {})
                merged = {**previous, **state, "game_id": key}
                self._games[key] = merged
                self._track_finished(key, merged)
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            try:
                subscriber.put_nowait(None)
            except queue.Full:
                pass

    def snapshot(self) -> str:
        with self._lock:
            payload = {"games": [state.copy() for state in self._games.values()]}
        return json.dumps(payload, ensure_ascii=False)

    def subscribe(self) -> queue.Queue[None]:
        subscriber: queue.Queue[None] = queue.Queue(maxsize=1)

        with self._lock:
            self._subscribers.add(subscriber)

        subscriber.put_nowait(None)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[None]) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def _track_finished(self, game_id: str, state: dict[str, Any]) -> None:
        if state.get("status") != "finished":
            if game_id in self._finished_order:
                self._finished_order.remove(game_id)
            return

        if game_id not in self._finished_order:
            self._finished_order.append(game_id)

        while len(self._finished_order) > self.recent_limit:
            oldest = self._finished_order.pop(0)
            self._games.pop(oldest, None)


class LiveVisualizer:
    """Servidor HTTP local con actualizaciones en vivo mediante SSE."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.hub = LiveStateHub()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._index = (
            Path(__file__).parent
            / "static"
            / "visualizer.html"
        )

    def start(self) -> bool:
        if self._server is not None:
            return True

        handler = self._make_handler()

        try:
            self._server = ThreadingHTTPServer(
                (self.host, self.port),
                handler,
            )
        except OSError as error:
            print(f"No se pudo iniciar el visualizador: {error}")
            return False

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="snake-live-visualizer",
            daemon=True,
        )
        self._thread.start()
        actual_port = self._server.server_address[1]
        print(f"Visualizador: http://{self.host}:{actual_port}")
        return True

    def stop(self) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    def publish(self, state: dict[str, Any]) -> None:
        self.hub.publish(state)

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        hub = self.hub
        index = self._index

        class VisualizerHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                if self.path in ("/", "/index.html"):
                    self._serve_index()
                elif self.path == "/events":
                    self._serve_events()
                elif self.path == "/health":
                    self._send_bytes(b"ok", "text/plain; charset=utf-8")
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def _serve_index(self) -> None:
                try:
                    content = index.read_bytes()
                except OSError:
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
                    return

                self._send_bytes(content, "text/html; charset=utf-8")

            def _serve_events(self) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                subscriber = hub.subscribe()

                try:
                    while True:
                        try:
                            subscriber.get(timeout=15)
                            raw_state = hub.snapshot()
                            message = f"data: {raw_state}\n\n"
                        except queue.Empty:
                            message = ": keep-alive\n\n"

                        self.wfile.write(message.encode("utf-8"))
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    hub.unsubscribe(subscriber)
                    # No intentes leer otra petición HTTP después de que el
                    # stream SSE terminó (por ejemplo, al cerrar el navegador).
                    self.close_connection = True

            def _send_bytes(self, content: bytes, content_type: str) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, format: str, *args: object) -> None:
                return

        return VisualizerHandler
