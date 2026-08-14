"""
Pesos utilizados por la inteligencia del bot.

Perfil competitivo:
- mantiene penalizaciones fuertes por encerrarse;
- aumenta la prioridad de comer;
- reduce ligeramente el exceso de conservadurismo.
"""

INVALID_MOVE_SCORE = -1_000_000

# Espacio libre
SPACE_WEIGHT = 8

# Supervivencia
CRITICAL_SPACE_PENALTY = -8_000
LOW_SPACE_PENALTY = -1_500

# Comida
EAT_FOOD_BONUS = 3_500
FOOD_BASE_SCORE = 900
FOOD_DISTANCE_WEIGHT = 35
UNREACHABLE_FOOD_PENALTY = -400

# Movilidad
NO_EXIT_PENALTY = -5_000
ONE_EXIT_PENALTY = -900
MOBILITY_WEIGHT = 30

# Control territorial
TERRITORY_WEIGHT = 3

# Riesgo frente al rival
ENEMY_DISTANCE_ONE_PENALTY = -1_500
ENEMY_DISTANCE_TWO_PENALTY = -300

# Carrera por la comida
FOOD_RACE_WEIGHT = 1.5

# Análisis de la respuesta inmediata del rival
LOOKAHEAD_WEIGHT = 1

LOOKAHEAD_SPACE_WEIGHT = 4
LOOKAHEAD_CRITICAL_PENALTY = -5_000
LOOKAHEAD_LOW_SPACE_PENALTY = -1_200

ENEMY_EAT_PENALTY = -800
ENEMY_TRAPPED_BONUS = 3_000

# Búsqueda de dos niveles
TWO_PLY_WEIGHT = 0.20

TWO_PLY_FORCED_CRASH_PENALTY = -15_000
TWO_PLY_ENEMY_TRAPPED_BONUS = 8_000

# Presión sobre el rival
OPPONENT_PRESSURE_WEIGHT = 1

# Solo profundizamos cuando los dos mejores
# movimientos tienen puntajes parecidos.
DEEP_SEARCH_GAP = 700

# Búsqueda profunda selectiva
CRITICAL_SEARCH_GAP = 350
CRITICAL_REMAINING_MOVES = 60
CRITICAL_SCORE_DEFICIT = -150
CRITICAL_HEAD_DISTANCE = 4

DEEP_TWO_PLY_WEIGHT = 0.30

