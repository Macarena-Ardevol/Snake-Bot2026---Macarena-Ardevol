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

## Dataset local de self-play

La generación es manual y escribe exclusivamente bajo `data/selfplay/`:

```bash
python -m learning.selfplay_dataset --matches 8 --seed 42 \
  --opponents baseline,survival,random_safe,mirror
```

Las partidas consecutivas se emparejan con la misma semilla: primero el bot
avanzado juega como A y luego como B. El reporte puede analizarse offline sin
mezclarlo con las partidas reales:

```python
from learning.learning_advisor import LearningAdvisor
from learning.match_analyzer import MatchAnalyzer

summary = MatchAnalyzer("data/selfplay/run_<id>").analyze()
report = LearningAdvisor().analyze(summary)
```

Para combinar fuentes hay que solicitarlo explícitamente:

```python
summary = MatchAnalyzer(["data/games", "data/selfplay/run_<id>"]).analyze()
```

## Optimización experimental de candidatos

El optimizador compara configuraciones aisladas contra los pesos estables. No
modifica `ai/weights.py` ni instala el candidato mejor posicionado:

```bash
python3 -m learning.candidate_optimizer \
  --weights SPACE_WEIGHT,FOOD_DISTANCE_WEIGHT \
  --variations 5,-5,10,-10 \
  --limit 4 --matches 4 --seed 42 \
  --rivals baseline,survival --max-moves 60
```

El reporte solo se persiste si se pasa `--output data/learning/reporte.json`.
