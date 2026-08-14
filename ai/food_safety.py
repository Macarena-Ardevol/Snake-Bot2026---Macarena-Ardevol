from ai.flood_fill import FloodFill
from game.board import GameBoard
from game.simulator import BoardSimulator


class FoodSafetyAnalyzer:
    """
    Evalúa si comer en el próximo movimiento es seguro.

    La comida hace crecer la serpiente, por lo que una
    casilla atractiva puede convertirse en una trampa.
    """

    def __init__(self) -> None:
        self.simulator = BoardSimulator()
        self.flood_fill = FloodFill()

    def score(
        self,
        board: GameBoard,
        side: str,
        direction: str,
    ) -> float:
        head = board.my_head(side)

        next_position = board.next_position(
            head,
            direction,
        )

        # Solo evaluamos especialmente movimientos
        # que comen inmediatamente.
        if next_position not in board.food:
            return 0

        simulated = self.simulator.simulate_move(
            board,
            side,
            direction,
        )

        if simulated is None:
            return -10_000

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

        exits = self._count_safe_exits(
            simulated,
            side,
        )

        # Comimos pero quedamos prácticamente encerrados.
        if reachable_area <= snake_length:
            return -6_000

        if exits == 0:
            return -6_000

        # Muy poco margen después de crecer.
        if reachable_area <= snake_length * 2:
            return -2_500

        if exits == 1:
            return -1_200

        # Comida segura con buen espacio posterior.
        if reachable_area >= snake_length * 4:
            return 500

        return 100

    def _count_safe_exits(
        self,
        board: GameBoard,
        side: str,
    ) -> int:
        head = board.my_head(side)

        exits = 0

        for direction in board.DIRECTIONS:
            simulated = self.simulator.simulate_move(
                board,
                side,
                direction,
            )

            if simulated is not None:
                exits += 1

        return exits