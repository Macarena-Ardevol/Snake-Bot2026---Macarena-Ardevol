from collections import deque
from functools import lru_cache

from game.board import GameBoard


class TerritoryAnalyzer:
    """
    Estima qué zonas del tablero alcanza antes cada serpiente.

    Usa caché para evitar recalcular mapas de distancia
    sobre estados idénticos.
    """

    def distance_map(
        self,
        board: GameBoard,
        start: tuple[int, int],
    ) -> dict[tuple[int, int], int]:

        cached = self._cached_distance_map(
            tuple(board.grid),
            board.rows,
            board.cols,
            start,
        )

        return dict(cached)

    @staticmethod
    @lru_cache(maxsize=4096)
    def _cached_distance_map(
        grid: tuple[str, ...],
        rows: int,
        cols: int,
        start: tuple[int, int],
    ) -> tuple[
        tuple[tuple[int, int], int],
        ...
    ]:

        distances = {
            start: 0
        }

        queue = deque([start])

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

                if neighbour in distances:
                    continue

                if grid[nr][nc] not in (
                    " ",
                    "*",
                ):
                    continue

                distances[neighbour] = (
                    distances[(row, col)]
                    + 1
                )

                queue.append(neighbour)

        return tuple(
            distances.items()
        )

    def territory_balance(
        self,
        board: GameBoard,
        side: str,
    ) -> int:

        my_head = board.my_head(side)
        enemy_head = board.enemy_head(side)

        my_distances = self.distance_map(
            board,
            my_head,
        )

        enemy_distances = self.distance_map(
            board,
            enemy_head,
        )

        my_territory = 0
        enemy_territory = 0

        positions = (
            set(my_distances)
            | set(enemy_distances)
        )

        for position in positions:
            my_distance = my_distances.get(
                position
            )

            enemy_distance = (
                enemy_distances.get(
                    position
                )
            )

            if my_distance is None:
                enemy_territory += 1

            elif enemy_distance is None:
                my_territory += 1

            elif my_distance < enemy_distance:
                my_territory += 1

            elif enemy_distance < my_distance:
                enemy_territory += 1

        return (
            my_territory
            - enemy_territory
        )

    @staticmethod
    def clear_cache() -> None:
        TerritoryAnalyzer._cached_distance_map.cache_clear()