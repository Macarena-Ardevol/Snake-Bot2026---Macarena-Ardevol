from ai import weights
from ai.evaluator import MoveEvaluator
from game.board import GameBoard
from game.simulator import BoardSimulator
from ai.weight_config import WeightConfig


class TwoPlyAnalyzer:
    """
    Analiza dos niveles hacia adelante:

    1. Nuestro movimiento.
    2. Respuesta del rival.
    3. Nuestra mejor contestación.

    El rival se considera inteligente y elige
    la respuesta que peor resultado nos produce.
    """

    def __init__(self, weight_config: WeightConfig | None = None) -> None:
        self.weight_config = weight_config or WeightConfig.from_current_defaults()
        self.simulator = BoardSimulator()
        self.evaluator = MoveEvaluator(weight_config=self.weight_config)

    def score(
        self,
        board: GameBoard,
        side: str,
        direction: str,
    ) -> float:
        after_my_move = self.simulator.simulate_move(
            board,
            side,
            direction,
        )

        if after_my_move is None:
            return self.weight_config.INVALID_MOVE_SCORE

        enemy = "B" if side == "A" else "A"
        enemy_results: list[float] = []

        for enemy_direction in board.DIRECTIONS:
            after_enemy_move = self.simulator.simulate_move(
                after_my_move,
                enemy,
                enemy_direction,
            )

            if after_enemy_move is None:
                continue

            best_reply_score = self._best_reply_score(
                after_enemy_move,
                side,
            )

            enemy_results.append(best_reply_score)

        # El rival no tiene movimientos posibles.
        if not enemy_results:
            return self.weight_config.TWO_PLY_ENEMY_TRAPPED_BONUS

        # El rival elige la respuesta que más nos perjudica.
        return min(enemy_results)

    def _best_reply_score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        best_score = float("-inf")

        for direction in board.DIRECTIONS:
            score = self.evaluator.score_move(
                board,
                side,
                direction,
            )

            best_score = max(
                best_score,
                score,
            )

        if best_score == self.weight_config.INVALID_MOVE_SCORE:
            return self.weight_config.TWO_PLY_FORCED_CRASH_PENALTY

        return best_score
