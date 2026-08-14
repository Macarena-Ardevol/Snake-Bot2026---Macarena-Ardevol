from ai.pathfinding import PathFinder
from game.board import GameBoard


class BaselineStrategy:
    """
    Estrategia de referencia:

    - busca la comida más cercana;
    - usa BFS;
    - si no encuentra camino, elige un movimiento válido.
    """

    MOVE_ORDER = (
        "up",
        "down",
        "left",
        "right",
    )

    def __init__(self) -> None:
        self.pathfinder = PathFinder()

    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
    ) -> str:
        head = board.my_head(side)
        best_path = None

        for food in board.food:
            path = self.pathfinder.shortest_path(
                board,
                head,
                food,
            )

            if not path:
                continue

            if best_path is None or len(path) < len(best_path):
                best_path = path

        if best_path and len(best_path) >= 2:
            return self._direction_between(
                best_path[0],
                best_path[1],
            )

        valid_moves = board.valid_moves(side)

        for direction in self.MOVE_ORDER:
            if valid_moves[direction]:
                return direction

        return "up"

    @staticmethod
    def _direction_between(
        start: tuple[int, int],
        destination: tuple[int, int],
    ) -> str:
        row_difference = destination[0] - start[0]
        col_difference = destination[1] - start[1]

        if row_difference == -1:
            return "up"

        if row_difference == 1:
            return "down"

        if col_difference == -1:
            return "left"

        return "right"