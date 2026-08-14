from ai.flood_fill import FloodFill
from game.board import GameBoard
from game.simulator import BoardSimulator


class OpponentPressureAnalyzer:
    """
    Evalúa cuánto limitamos los movimientos del rival.

    Premia:
    - dejarlo con pocas salidas;
    - reducir su espacio disponible;
    - encerrarlo completamente.
    """

    def __init__(self) -> None:
        self.simulator = BoardSimulator()
        self.flood_fill = FloodFill()

    def score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        enemy = "B" if side == "A" else "A"

        legal_moves = self._legal_moves(
            board,
            enemy,
        )

        if not legal_moves:
            return 5_000

        enemy_area = (
            self.flood_fill.reachable_area_from_head(
                board,
                enemy,
            )
        )

        enemy_length = (
            1
            + len(board.snakes[enemy]["body"])
        )

        score = 0.0

        if len(legal_moves) == 1:
            score += 800

        elif len(legal_moves) == 2:
            score += 200

        if enemy_area <= enemy_length:
            score += 3_000

        elif enemy_area <= enemy_length * 2:
            score += 700

        return score

    def _legal_moves(
        self,
        board: GameBoard,
        side: str,
    ) -> list[str]:
        legal_moves = []

        for direction in board.DIRECTIONS:
            simulated = self.simulator.simulate_move(
                board,
                side,
                direction,
            )

            if simulated is not None:
                legal_moves.append(direction)

        return legal_moves