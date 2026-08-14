from collections import deque

from game.board import GameBoard


class BottleneckAnalyzer:
    """
    Detecta si la cabeza está entrando en una región
    conectada al resto del tablero por muy pocas salidas.
    """

    def score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        head = board.my_head(side)

        reachable = self._reachable_cells(
            board,
            head,
        )

        if not reachable:
            return -5000

        exits = self._count_boundary_connections(
            board,
            reachable,
        )

        snake_length = (
            1
            + len(board.snakes[side]["body"])
        )

        area = len(reachable)

        # Espacio insuficiente para el tamaño de la serpiente.
        if area <= snake_length:
            return -5000

        # Región muy ajustada.
        if area <= snake_length * 2:
            return -1500

        # Región razonablemente grande pero con una sola
        # conexión importante: posible trampa futura.
        if exits <= 1 and area < board.rows * board.cols * 0.40:
            return -900

        if exits == 2:
            return -200

        return 0

    def _reachable_cells(
        self,
        board: GameBoard,
        start: tuple[int, int],
    ) -> set[tuple[int, int]]:
        visited = {start}
        queue = deque([start])

        while queue:
            current = queue.popleft()

            for neighbour in board.neighbours(*current):
                if neighbour in visited:
                    continue

                if (
                    neighbour != start
                    and not board.is_free(*neighbour)
                    and neighbour not in board.food
                ):
                    continue

                visited.add(neighbour)
                queue.append(neighbour)

        return visited

    def _count_boundary_connections(
        self,
        board: GameBoard,
        region: set[tuple[int, int]],
    ) -> int:
        connections = set()

        for cell in region:
            for neighbour in board.neighbours(*cell):
                if neighbour in region:
                    continue

                if board.is_free(*neighbour):
                    connections.add(neighbour)

        return len(connections)