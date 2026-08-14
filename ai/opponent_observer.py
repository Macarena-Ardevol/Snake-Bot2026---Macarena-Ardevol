from ai.pathfinding import PathFinder
from game.board import GameBoard


class OpponentObserver:
    """
    Analiza cómo se comportó el rival entre dos tableros.
    """

    def __init__(self) -> None:
        self.pathfinder = PathFinder()

    def infer_direction(
        self,
        previous_board: GameBoard,
        current_board: GameBoard,
        my_side: str,
    ) -> str | None:
        previous_head = previous_board.enemy_head(
            my_side
        )

        current_head = current_board.enemy_head(
            my_side
        )

        difference = (
            current_head[0] - previous_head[0],
            current_head[1] - previous_head[1],
        )

        directions = {
            (-1, 0): "up",
            (1, 0): "down",
            (0, -1): "left",
            (0, 1): "right",
        }

        return directions.get(difference)

    def moved_toward_food(
        self,
        previous_board: GameBoard,
        current_board: GameBoard,
        my_side: str,
    ) -> bool:
        if not previous_board.food:
            return False

        previous_head = previous_board.enemy_head(
            my_side
        )

        current_head = current_board.enemy_head(
            my_side
        )

        return (
            self._nearest_food_distance(
                previous_board,
                previous_head,
            )
            >
            self._nearest_food_distance(
                previous_board,
                current_head,
            )
        )

    def moved_toward_us(
        self,
        previous_board: GameBoard,
        current_board: GameBoard,
        my_side: str,
    ) -> bool:
        previous_enemy = previous_board.enemy_head(
            my_side
        )

        current_enemy = current_board.enemy_head(
            my_side
        )

        my_previous_head = previous_board.my_head(
            my_side
        )

        previous_distance = self._manhattan(
            previous_enemy,
            my_previous_head,
        )

        current_distance = self._manhattan(
            current_enemy,
            my_previous_head,
        )

        return current_distance < previous_distance

    def contested_food(
        self,
        previous_board: GameBoard,
        current_board: GameBoard,
        my_side: str,
    ) -> bool:
        """
        Consideramos disputada una comida cuando ambos
        podían alcanzarla y el rival decidió acercarse.
        """
        if not previous_board.food:
            return False

        my_head = previous_board.my_head(
            my_side
        )

        enemy_head = previous_board.enemy_head(
            my_side
        )

        current_enemy = current_board.enemy_head(
            my_side
        )

        for food in previous_board.food:
            my_path = self.pathfinder.shortest_path(
                previous_board,
                my_head,
                food,
            )

            enemy_path = self.pathfinder.shortest_path(
                previous_board,
                enemy_head,
                food,
            )

            if not my_path or not enemy_path:
                continue

            before = self._manhattan(
                enemy_head,
                food,
            )

            after = self._manhattan(
                current_enemy,
                food,
            )

            if after < before:
                return True

        return False

    def _nearest_food_distance(
        self,
        board: GameBoard,
        position: tuple[int, int],
    ) -> int:
        return min(
            self._manhattan(
                position,
                food,
            )
            for food in board.food
        )

    @staticmethod
    def _manhattan(
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> int:
        return (
            abs(first[0] - second[0])
            + abs(first[1] - second[1])
        )