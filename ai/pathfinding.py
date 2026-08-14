from collections import deque
from functools import lru_cache

from game.board import GameBoard


class PathFinder:
    """
    Busca caminos mínimos mediante BFS.

    Usa caché para evitar recalcular el mismo camino
    sobre exactamente el mismo estado del tablero.
    """

    def shortest_path(
        self,
        board: GameBoard,
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> list[tuple[int, int]]:

        grid_key = tuple(board.grid)

        cached_path = self._cached_shortest_path(
            grid_key,
            board.rows,
            board.cols,
            start,
            goal,
        )

        return list(cached_path)

    @staticmethod
    @lru_cache(maxsize=4096)
    def _cached_shortest_path(
        grid: tuple[str, ...],
        rows: int,
        cols: int,
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> tuple[tuple[int, int], ...]:

        if start == goal:
            return (start,)

        queue = deque([start])
        visited = {start}
        parents: dict[
            tuple[int, int],
            tuple[int, int],
        ] = {}

        while queue:
            current = queue.popleft()

            row, col = current

            neighbours = (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            )

            for neighbour in neighbours:
                nr, nc = neighbour

                if not (
                    0 <= nr < rows
                    and 0 <= nc < cols
                ):
                    continue

                if neighbour in visited:
                    continue

                cell = grid[nr][nc]

                # El objetivo puede estar ocupado por comida
                # o por la casilla que específicamente buscamos.
                if (
                    neighbour != goal
                    and cell not in (" ", "*")
                ):
                    continue

                visited.add(neighbour)
                parents[neighbour] = current

                if neighbour == goal:
                    return PathFinder._build_cached_path(
                        parents,
                        start,
                        goal,
                    )

                queue.append(neighbour)

        return ()

    @staticmethod
    def _build_cached_path(
        parents: dict[
            tuple[int, int],
            tuple[int, int],
        ],
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> tuple[tuple[int, int], ...]:

        path = [goal]
        current = goal

        while current != start:
            current = parents[current]
            path.append(current)

        path.reverse()

        return tuple(path)

    @staticmethod
    def clear_cache() -> None:
        """
        Permite vaciar la caché manualmente si fuera necesario.
        """
        PathFinder._cached_shortest_path.cache_clear()