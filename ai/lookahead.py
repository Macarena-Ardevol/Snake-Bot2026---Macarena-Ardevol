from ai import weights
from ai.flood_fill import FloodFill
from ai.opponent_model import OpponentModel
from game.board import GameBoard
from game.simulator import BoardSimulator
from ai.weight_config import WeightConfig


class LookaheadAnalyzer:
    """
    Analiza la respuesta inmediata del rival.

    Combina:
    - peor respuesta posible;
    - respuesta que nuestro modelo considera más probable.

    Así mantenemos seguridad sin asumir que el rival
    siempre elegirá un movimiento perfecto.
    """

    def __init__(
        self,
        opponent_model: OpponentModel | None = None,
        weight_config: WeightConfig | None = None,
    ) -> None:
        self.weight_config = weight_config or WeightConfig.from_current_defaults()
        self.simulator = BoardSimulator()
        self.flood_fill = FloodFill()

        self.opponent_model = (
            opponent_model
            if opponent_model is not None
            else OpponentModel()
        )
    
    def score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        enemy = "B" if side == "A" else "A"

        ranked_moves = self.opponent_model.ranked_moves(
            board,
            enemy,
        )

        if not ranked_moves:
            return self.weight_config.ENEMY_TRAPPED_BONUS

        responses: list[tuple[str, float]] = []

        for direction, _ in ranked_moves:
            enemy_head = board.my_head(enemy)

            next_position = board.next_position(
                enemy_head,
                direction,
            )

            enemy_eats = next_position in board.food

            simulated = self.simulator.simulate_move(
                board,
                enemy,
                direction,
            )

            if simulated is None:
                continue

            response_score = self._score_response(
                simulated,
                side,
                enemy,
                enemy_eats,
            )

            responses.append(
                (direction, response_score)
            )

        if not responses:
            return self.weight_config.ENEMY_TRAPPED_BONUS

        # Protección ante el peor caso.
        worst_score = min(
            score
            for _, score in responses
        )

        # El primer movimiento del ranking es el que
        # consideramos más probable.
        predicted_direction = ranked_moves[0][0]

        predicted_score = worst_score

        for direction, score in responses:
            if direction == predicted_direction:
                predicted_score = score
                break

        prediction_confidence = (
            self.opponent_model.prediction_confidence()
        )

        # Sin historial:
        # 85% peor caso / 15% predicción.
        #
        # Con un predictor muy confiable:
        # 55% peor caso / 45% predicción.
        predicted_weight = (
            0.15
            + 0.30 * prediction_confidence
        )

        worst_weight = (
            1.0
            - predicted_weight
        )

        return (
            worst_score * worst_weight
            + predicted_score * predicted_weight
        )

    def _score_response(
        self,
        board: GameBoard,
        side: str,
        enemy: str,
        enemy_eats: bool,
    ) -> float:
        my_area = self.flood_fill.reachable_area_from_head(
            board,
            side,
        )

        enemy_area = self.flood_fill.reachable_area_from_head(
            board,
            enemy,
        )

        my_length = (
            1
            + len(board.snakes[side]["body"])
        )

        score = (
            my_area - enemy_area
        ) * self.weight_config.LOOKAHEAD_SPACE_WEIGHT

        if my_area <= my_length:
            score += self.weight_config.LOOKAHEAD_CRITICAL_PENALTY

        elif my_area <= my_length * 2:
            score += self.weight_config.LOOKAHEAD_LOW_SPACE_PENALTY

        if enemy_eats:
            score += self.weight_config.ENEMY_EAT_PENALTY

        return score
