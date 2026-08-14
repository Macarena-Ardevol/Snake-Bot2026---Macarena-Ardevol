from collections import deque
from functools import lru_cache

from game.board import GameBoard


class FloodFill:
    """
    Calcula el área alcanzable desde una posición.

    Usa caché para estados de tablero repetidos.
    """

    def reachable_area(
        self,
        board: GameBoard,
        start: tuple[int, int],
    ) -> int:

        if not board.is_inside(*start):
            return 0

        if not board.is_free(*start):
            return 0

        return self._cached_area(
            tuple(board.grid),
            board.rows,
            board.cols,
            start,
            False,
        )

    def reachable_area_from_head(
        self,
        board: GameBoard,
        side: str,
    ) -> int:

        start = board.my_head(side)

        return self._cached_area(
            tuple(board.grid),
            board.rows,
            board.cols,
            start,
            True,
        )

    @staticmethod
    @lru_cache(maxsize=4096)
    def _cached_area(
        grid: tuple[str, ...],
        rows: int,
        cols: int,
        start: tuple[int, int],
        allow_occupied_start: bool,
    ) -> int:

        sr, sc = start

        if not (
            0 <= sr < rows
            and 0 <= sc < cols
        ):
            return 0

        if (
            not allow_occupied_start
            and grid[sr][sc] not in (" ", "*")
        ):
            return 0

        queue = deque([start])
        visited = {start}

        while queue:
            row, col = queue.popleft()

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

                if grid[nr][nc] not in (" ", "*"):
                    continue

                visited.add(neighbour)
                queue.append(neighbour)

        return len(visited)

    @staticmethod
    def clear_cache() -> None:
        FloodFill._cached_area.cache_clear()