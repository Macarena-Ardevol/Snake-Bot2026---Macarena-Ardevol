import os


# Nunca guardar el token oficial en el repositorio. Puede pasarse como primer
# argumento a run.py o mediante la variable de entorno BOT_TOKEN.
BOT_TOKEN = os.getenv("BOT_TOKEN")

SERVER_URI = (
    "wss://codechallenge-server.up.railway.app/ws"
)
