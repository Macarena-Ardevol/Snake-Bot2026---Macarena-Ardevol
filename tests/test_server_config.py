import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from bot.client import BotClient


class TestServerConfig(unittest.TestCase):

    def test_client_builds_exact_new_websocket_url(self):
        client = BotClient("abc")
        self.addCleanup(client.decision_executor.shutdown)
        self.addCleanup(client.background_executor.shutdown)

        with patch(
            "bot.client.SERVER_URI",
            "wss://server.codechallenge.net.ar/ws",
        ):
            uri = client._websocket_uri()

        self.assertEqual(
            uri,
            "wss://server.codechallenge.net.ar/ws?token=abc",
        )

    def test_normal_token_does_not_duplicate_query_or_ws_path(self):
        client = BotClient("abc-XYZ_123")
        self.addCleanup(client.decision_executor.shutdown)
        self.addCleanup(client.background_executor.shutdown)

        uri = client._websocket_uri()

        self.assertNotIn("??token=", uri)
        self.assertEqual(uri.count("?"), 1)
        self.assertEqual(uri.count("/ws"), 1)
        self.assertNotIn("codechallenge-server.up.railway.app", uri)


class TestServerConnection(unittest.IsolatedAsyncioTestCase):

    async def test_reconnection_loop_uses_built_url_and_keeps_retry_delay(self):
        client = BotClient("abc")
        self.addCleanup(client.decision_executor.shutdown)
        self.addCleanup(client.background_executor.shutdown)
        requested_urls = []

        class FailingConnection:
            async def __aenter__(self):
                raise RuntimeError("offline test")

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        def fake_connect(uri):
            requested_urls.append(uri)
            return FailingConnection()

        fake_sleep = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch("bot.client.websockets.connect", side_effect=fake_connect),
            patch("bot.client.asyncio.sleep", fake_sleep),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await client.connect_forever()

        self.assertEqual(
            requested_urls,
            ["wss://server.codechallenge.net.ar/ws?token=abc"],
        )
        fake_sleep.assert_awaited_once_with(3)


if __name__ == "__main__":
    unittest.main()
