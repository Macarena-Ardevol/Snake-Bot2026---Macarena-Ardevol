from ai.flood_fill import FloodFill
from game.board import GameBoard
from game.simulator import BoardSimulator


class SurvivalStrategy:
    """
    Estrategia defensiva que prioriza el espacio disponible.
    """

    MOVE_ORDER = (
        "up",
        "down",
        "left",
        "right",
    )

    def __init__(self) -> None:
        self.simulator = BoardSimulator()
        self.flood_fill = FloodFill()

    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
    ) -> str:
        best_move = "up"
        best_area = -1

        for direction in self.MOVE_ORDER:
            simulated = self.simulator.simulate_move(
                board,
                side,
                direction,
            )

            if simulated is None:
                continue

            area = self.flood_fill.reachable_area_from_head(
                simulated,
                side,
            )

            if area > best_area:
                best_area = area
                best_move = direction

        return best_move