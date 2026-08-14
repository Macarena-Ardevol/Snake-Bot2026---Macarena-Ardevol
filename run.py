import sys

from bot.client import BotClient
from config import BOT_TOKEN


def main() -> None:
    token = sys.argv[1] if len(sys.argv) > 1 else BOT_TOKEN

    if not token:
        raise SystemExit(
            "Falta el token. Ejecutá: python run.py <YOUR_BOT_TOKEN> "
            "o definí la variable de entorno BOT_TOKEN."
        )

    client = BotClient(token)
    client.start()


if __name__ == "__main__":
    main()
