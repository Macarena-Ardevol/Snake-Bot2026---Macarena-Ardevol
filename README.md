# Snake Bot

Proyecto final de la materia Computación.

Bot desarrollado en Python para competir en el juego Snake mediante WebSockets.

## Ejecución

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py <YOUR_BOT_TOKEN>
```

Al iniciar, el tablero en vivo queda disponible en:

```text
http://127.0.0.1:8765
```

El cliente admite varias partidas simultáneas. Cada `game_id` mantiene una
estrategia y un estado independientes; el visualizador muestra una pestaña por
partida para alternar entre juegos activos y finalizados.

Como alternativa, el token puede cargarse sin escribirlo en el código:

```bash
export BOT_TOKEN="<YOUR_BOT_TOKEN>"
python run.py
```

El token es secreto: no debe subirse al repositorio ni incluirse en capturas o
registros. Si un token fue expuesto, hay que regenerarlo en **My Bots**.

## Pruebas locales

```bash
python -m unittest discover -s tests -v
python -m local_game.benchmark
```
