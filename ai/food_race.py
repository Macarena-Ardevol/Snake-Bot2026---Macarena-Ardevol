from ai.pathfinding import PathFinder
from game.board import GameBoard


class FoodRaceAnalyzer:
    """
    Compara quién puede llegar antes a cada comida.
    """

    def __init__(self) -> None:
        self.pathfinder = PathFinder()

    def score(
        self,
        board: GameBoard,
        side: str,
    ) -> float:
        if not board.food:
            return 0

        my_head = board.my_head(side)
        enemy_head = board.enemy_head(side)

        best_score = float("-inf")

        for food in board.food:
            my_path = self.pathfinder.shortest_path(
                board,
                my_head,
                food,
            )

            enemy_path = self.pathfinder.shortest_path(
                board,
                enemy_head,
                food,
            )

            my_distance = (
                len(my_path) - 1
                if my_path
                else None
            )

            enemy_distance = (
                len(enemy_path) - 1
                if enemy_path
                else None
            )

            food_score = self._compare_distances(
                my_distance,
                enemy_distance,
            )

            best_score = max(best_score, food_score)

        if best_score == float("-inf"):
            return 0

        return best_score

    def _compare_distances(
        self,
        my_distance: int | None,
        enemy_distance: int | None,
    ) -> float:
        if my_distance is None:
            return -500

        if enemy_distance is None:
            return 600

        difference = enemy_distance - my_distance

        if difference >= 3:
            return 500

        if difference == 2:
            return 350

        if difference == 1:
            return 200

        if difference == 0:
            return -150

        if difference == -1:
            return -300

        return -500