from ai.flood_fill import FloodFill
from ai.opponent_memory import OpponentMemory
from ai.pathfinding import PathFinder
from game.board import GameBoard
from game.simulator import BoardSimulator


class OpponentModel:
    """
    Predice las decisiones del rival combinando:

    - espacio;
    - movilidad;
    - comida;
    - tendencia a disputar comida;
    - tendencia a acercarse a nuestra cabeza;
    - comportamiento histórico observado.
    """

    def __init__(
        self,
        memory: OpponentMemory | None = None,
    ) -> None:
        self.simulator = BoardSimulator()
        self.flood_fill = FloodFill()
        self.pathfinder = PathFinder()

        self.memory = memory
        self.current_opponent: str | None = None

    def set_opponent(
        self,
        opponent: str | None,
    ) -> None:
        self.current_opponent = opponent

    def ranked_moves(
        self,
        board: GameBoard,
        side: str,
    ) -> list[tuple[str, float]]:
        results = []

        for direction in board.DIRECTIONS:
            score = self._score_move(
                board,
                side,
                direction,
            )

            if score is not None:
                results.append(
                    (direction, score)
                )

        results.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return results

    def predicted_move(
        self,
        board: GameBoard,
        side: str,
    ) -> str | None:
        moves = self.ranked_moves(
            board,
            side,
        )

        if not moves:
            return None

        return moves[0][0]

    def _score_move(
        self,
        board: GameBoard,
        side: str,
        direction: str,
    ) -> float | None:
        head = board.my_head(side)

        next_position = board.next_position(
            head,
            direction,
        )

        eating = next_position in board.food

        simulated = self.simulator.simulate_move(
            board,
            side,
            direction,
        )

        if simulated is None:
            return None

        score = 0.0

        # Espacio
        area = (
            self.flood_fill.reachable_area_from_head(
                simulated,
                side,
            )
        )

        score += area * 8

        # Movilidad
        free_moves = sum(
            simulated.valid_moves(side).values()
        )

        score += free_moves * 100

        # Comida
        score += self._food_score(
            board=board,
            simulated=simulated,
            side=side,
            eating=eating,
        )

        # Tendencia a acercarse a nuestra cabeza
        score += self._head_pressure_score(
            board=board,
            simulated=simulated,
            side=side,
        )

        return score

    def _food_score(
        self,
        board: GameBoard,
        simulated: GameBoard,
        side: str,
        eating: bool,
    ) -> float:
        food_aggression = self._food_aggression()
        contest_aggression = self._contest_aggression()

        # Rival desconocido: valores neutrales.
        food_multiplier = (
            0.6
            + food_aggression * 0.8
        )

        contest_multiplier = (
            0.7
            + contest_aggression * 0.6
        )

        score = 0.0

        if eating:
            score += (
                2500
                * food_multiplier
            )

        distance_score = self._food_distance_score(
            simulated,
            side,
        )

        score += (
            distance_score
            * food_multiplier
            * contest_multiplier
        )

        return score

    def _head_pressure_score(
        self,
        board: GameBoard,
        simulated: GameBoard,
        side: str,
    ) -> float:
        """
        Modela si el rival suele acercarse a nuestra cabeza.
        """
        aggression = self._head_aggression()

        enemy_head = simulated.my_head(side)

        other_side = (
            "B"
            if side == "A"
            else "A"
        )

        other_head = simulated.my_head(
            other_side
        )

        distance = (
            abs(enemy_head[0] - other_head[0])
            + abs(enemy_head[1] - other_head[1])
        )

        if distance == 1:
            return 500 * aggression

        if distance == 2:
            return 250 * aggression

        if distance == 3:
            return 100 * aggression

        return 0

    def _food_aggression(self) -> float:
        if (
            self.memory is None
            or self.current_opponent is None
        ):
            return 0.5

        observed = self.memory.food_aggression(
            self.current_opponent
        )

        confidence = self.memory.confidence(
            self.current_opponent
        )

        return (
            0.5 * (1 - confidence)
            + observed * confidence
        )

    def _head_aggression(self) -> float:
        if (
            self.memory is None
            or self.current_opponent is None
        ):
            return 0.5

        observed = self.memory.head_aggression(
            self.current_opponent
        )

        confidence = self.memory.confidence(
            self.current_opponent
        )

        return (
            0.5 * (1 - confidence)
            + observed * confidence
        )
 
    def _contest_aggression(self) -> float:
        if (
            self.memory is None
            or self.current_opponent is None
        ):
            return 0.5

        observed = self.memory.contest_aggression(
            self.current_opponent
        )

        confidence = self.memory.confidence(
            self.current_opponent
        )

        return (
            0.5 * (1 - confidence)
            + observed * confidence
        )

    def _food_distance_score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        if not board.food:
            return 0

        head = board.my_head(side)

        best_distance = None

        for food in board.food:
            path = self.pathfinder.shortest_path(
                board,
                head,
                food,
            )

            if not path:
                continue

            distance = len(path) - 1

            if (
                best_distance is None
                or distance < best_distance
            ):
                best_distance = distance

        if best_distance is None:
            return -300

        return (
            500
            - best_distance * 25
        )

    def prediction_confidence(self) -> float:
        """
        Determina cuánto podemos confiar en las predicciones
        aprendidas para el rival actual.
        """
        if (
            self.memory is None
            or self.current_opponent is None
        ):
            return 0.0

        accuracy = self.memory.prediction_accuracy(
            self.current_opponent
        )

        if accuracy is None:
            return 0.0

        stats = self.memory.get_stats(
            self.current_opponent
        )

        predictions = stats["predictions"]

        # No confiamos demasiado con pocas predicciones.
        sample_confidence = min(
            predictions / 20,
            1.0,
        )

        # Una precisión de 25% equivale aproximadamente
        # a elegir al azar entre cuatro direcciones.
        useful_accuracy = max(
            0.0,
            (accuracy - 0.25) / 0.75,
        )

        return (
            sample_confidence
            * useful_accuracy
        )