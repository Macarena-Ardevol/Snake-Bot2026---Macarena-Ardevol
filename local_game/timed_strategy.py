import time
from typing import Any

from game.board import GameBoard


class TimedStrategy:
    """
    Envuelve una estrategia y registra cuánto tarda
    en elegir cada movimiento.
    """

    def __init__(self, strategy: Any) -> None:
        self.strategy = strategy
        self.decision_times: list[float] = []

    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
    ) -> str:
        start = time.perf_counter()

        move = self.strategy.choose_move(
            board=board,
            side=side,
            remaining_moves=remaining_moves,
            my_score=my_score,
            enemy_score=enemy_score,
        )

        elapsed = time.perf_counter() - start
        self.decision_times.append(elapsed)

        return move