from ai import weights
from ai.flood_fill import FloodFill
from ai.food_race import FoodRaceAnalyzer
from ai.pathfinding import PathFinder
from ai.territory import TerritoryAnalyzer
from game.board import GameBoard
from game.simulator import BoardSimulator
from ai.lookahead import LookaheadAnalyzer
from ai.bottleneck import BottleneckAnalyzer
from ai.opponent_pressure import OpponentPressureAnalyzer
from ai.food_safety import FoodSafetyAnalyzer
from ai.opponent_model import OpponentModel
from ai.weight_config import WeightConfig
from typing import Any


class MoveEvaluator:
    """
    Evalúa cada movimiento y devuelve el detalle del puntaje.
    """

    INVALID_MOVE_SCORE = weights.INVALID_MOVE_SCORE

    def __init__(
        self, 
        opponent_model: OpponentModel | None = None,
        weight_config: WeightConfig | None = None,
    ) -> None:
        self.weight_config = weight_config or WeightConfig.from_current_defaults()
        self.INVALID_MOVE_SCORE = self.weight_config.INVALID_MOVE_SCORE
        self.flood_fill = FloodFill()
        self.pathfinder = PathFinder()
        self.simulator = BoardSimulator()
        self.territory = TerritoryAnalyzer()
        self.food_race = FoodRaceAnalyzer()
        self.lookahead = LookaheadAnalyzer(
            opponent_model=opponent_model,
            weight_config=self.weight_config,
        )
        self.bottleneck = BottleneckAnalyzer()
        self.opponent_pressure = OpponentPressureAnalyzer()
        self.food_safety = FoodSafetyAnalyzer()

    def score_move(
        self,
        board: GameBoard,
        side: str,
        direction: str,
    ) -> float:
        return self.analyze_move(
            board,
            side,
            direction,
        )["total"]

    def analyze_move(
        self,
        board: GameBoard,
        side: str,
        direction: str,
        compute_level: str = "normal",
    ) -> dict[str, Any]:
        head = board.my_head(side)
        next_position = board.next_position(head, direction)
        eating = next_position in board.food

        food_safety_score = self.food_safety.score(
            board,
            side,
            direction,
        )

        simulated = self.simulator.simulate_move(
            board,
            side,
            direction,
        )

        if simulated is None:
            return {
                "space": 0,
                "survival": 0,
                "food": 0,
                "food_race": 0,
                "mobility": 0,
                "territory": 0,
                "enemy_risk": 0,
                "lookahead": 0,
                "bottleneck": 0,
                "opponent_pressure": 0,
                "food_safety": 0,
                "total": self.weight_config.INVALID_MOVE_SCORE,
                "candidate_context": {
                    "valid": False,
                    "food_target": {"status": "none"},
                    "food_race": {"target_status": "not_evaluated"},
                },
            }

        position = simulated.my_head(side)

        reachable_area = (
            self.flood_fill.reachable_area_from_head(
                simulated,
                side,
            )
        )

        snake_length = (
            1
            + len(simulated.snakes[side]["body"])
        )

        space_score = (
            reachable_area
            * self.weight_config.SPACE_WEIGHT
        )

        survival_score = 0

        if reachable_area <= snake_length:
            survival_score = (
                self.weight_config.CRITICAL_SPACE_PENALTY
            )

        elif reachable_area <= snake_length * 2:
            survival_score = (
                self.weight_config.LOW_SPACE_PENALTY
            )

        if eating:
            food_score = self.weight_config.EAT_FOOD_BONUS
            food_race_score = 0
            food_target = {
                "status": "known",
                "food": list(next_position),
                "distance": 1,
                "path": [direction],
                "shortest_path_count": "unknown",
            }
            food_race_context = {
                "target_status": "not_evaluated_eating",
                "distance_basis": "not_evaluated",
                "food": list(next_position),
                "my_distance": 1,
                "enemy_distance": None,
                "result": "unknown",
            }
        else:
            food_score, food_target = self._food_score_with_context(
                simulated,
                position,
                direction,
            )

            food_race_score = 0
            food_race_context = {
                "target_status": "not_evaluated_critical",
                "distance_basis": "not_evaluated",
                "food": None,
                "my_distance": None,
                "enemy_distance": None,
                "result": "unknown",
            }
            if compute_level != "critical":
                food_race_context = self.food_race.analyze(
                    simulated,
                    side,
                )
                food_race_context["distance_basis"] = "after_candidate_move"
                food_race_score = (
                    food_race_context["score"]
                    * self.weight_config.FOOD_RACE_WEIGHT
                )

        mobility_score = self._mobility_score(
            simulated,
            position,
        )

        territory_score = 0
        if compute_level != "critical":
            territory_score = self._territory_score(
                simulated,
                side,
            )

        enemy_risk_score = self._enemy_risk_score(
            simulated,
            side,
            position,
        )

        lookahead_score = 0
        if compute_level != "critical":
            lookahead_score = (
                self.lookahead.score(
                    simulated,
                    side,
                )
                * self.weight_config.LOOKAHEAD_WEIGHT
            )

        bottleneck_score = 0
        if compute_level != "critical":
            bottleneck_score = self.bottleneck.score(
                simulated,
                side,
            )

        opponent_pressure_score = 0
        if compute_level != "critical":
            opponent_pressure_score = (
                self.opponent_pressure.score(
                    simulated,
                    side,
                )
                * self.weight_config.OPPONENT_PRESSURE_WEIGHT
            )

        total = (
            space_score
            + survival_score
            + food_score
            + food_race_score
            + food_safety_score
            + mobility_score
            + territory_score
            + enemy_risk_score
            + lookahead_score
            + bottleneck_score
            + opponent_pressure_score
        )

        return {
            "space": space_score,
            "survival": survival_score,
            "food": food_score,
            "food_race": food_race_score,
            "food_safety": food_safety_score,
            "mobility": mobility_score,
            "territory": territory_score,
            "enemy_risk": enemy_risk_score,
            "lookahead": lookahead_score,
            "bottleneck": bottleneck_score,
            "opponent_pressure": opponent_pressure_score,
            "total": total,
            "candidate_context": {
                "valid": True,
                "food_target": food_target,
                "food_race": {
                    key: value
                    for key, value in food_race_context.items()
                    if key != "score"
                },
            },
        }

    def _food_score(
        self,
        board: GameBoard,
        position: tuple[int, int],
    ) -> float:
        if not board.food:
            return 0

        shortest_distance = None

        for food in board.food:
            path = self.pathfinder.shortest_path(
                board,
                position,
                food,
            )

            if not path:
                continue

            distance = len(path) - 1

            if (
                shortest_distance is None
                or distance < shortest_distance
            ):
                shortest_distance = distance

        if shortest_distance is None:
            return self.weight_config.UNREACHABLE_FOOD_PENALTY

        return (
            self.weight_config.FOOD_BASE_SCORE
            - shortest_distance
            * self.weight_config.FOOD_DISTANCE_WEIGHT
        )

    def _food_score_with_context(
        self,
        board: GameBoard,
        position: tuple[int, int],
        first_direction: str,
    ) -> tuple[float, dict[str, Any]]:
        """Conserva el objetivo del mismo recorrido BFS usado por el score."""
        if not board.food:
            return 0, {"status": "none"}

        nearest: list[tuple[tuple[int, int], list[tuple[int, int]]]] = []
        shortest_distance = None
        for food in board.food:
            path = self.pathfinder.shortest_path(board, position, food)
            if not path:
                continue
            distance = len(path) - 1
            if shortest_distance is None or distance < shortest_distance:
                shortest_distance = distance
                nearest = [(food, path)]
            elif distance == shortest_distance:
                nearest.append((food, path))

        if shortest_distance is None:
            return self.weight_config.UNREACHABLE_FOOD_PENALTY, {
                "status": "none",
                "reason": "unreachable",
            }

        score = (
            self.weight_config.FOOD_BASE_SCORE
            - shortest_distance * self.weight_config.FOOD_DISTANCE_WEIGHT
        )
        if len(nearest) != 1:
            return score, {
                "status": "ambiguous",
                "distance": shortest_distance + 1,
                "candidate_count": len(nearest),
                "shortest_path_count": "unknown",
            }

        food, path = nearest[0]
        directions = [first_direction]
        directions.extend(
            self._direction_between(path[index], path[index + 1])
            for index in range(len(path) - 1)
        )
        return score, {
            "status": "known",
            "food": list(food),
            "distance": shortest_distance + 1,
            "path": directions,
            "shortest_path_count": "unknown",
        }

    @staticmethod
    def _direction_between(
        start: tuple[int, int],
        destination: tuple[int, int],
    ) -> str:
        row_delta = destination[0] - start[0]
        col_delta = destination[1] - start[1]
        if row_delta == -1:
            return "up"
        if row_delta == 1:
            return "down"
        if col_delta == -1:
            return "left"
        return "right"

    def _mobility_score(
        self,
        board: GameBoard,
        position: tuple[int, int],
    ) -> float:
        free_neighbours = sum(
            board.is_free(*neighbour)
            for neighbour in board.neighbours(
                *position
            )
        )

        if free_neighbours == 0:
            return self.weight_config.NO_EXIT_PENALTY

        if free_neighbours == 1:
            return self.weight_config.ONE_EXIT_PENALTY

        return (
            free_neighbours
            * self.weight_config.MOBILITY_WEIGHT
        )

    def _territory_score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        balance = self.territory.territory_balance(
            board,
            side,
        )

        return (
            balance
            * self.weight_config.TERRITORY_WEIGHT
        )

    def _enemy_risk_score(
        self,
        board: GameBoard,
        side: str,
        position: tuple[int, int],
    ) -> float:
        enemy_head = board.enemy_head(side)

        distance = (
            abs(position[0] - enemy_head[0])
            + abs(position[1] - enemy_head[1])
        )

        if distance == 1:
            return (
                self.weight_config.ENEMY_DISTANCE_ONE_PENALTY
            )

        if distance == 2:
            return (
                self.weight_config.ENEMY_DISTANCE_TWO_PENALTY
            )

        return 0
