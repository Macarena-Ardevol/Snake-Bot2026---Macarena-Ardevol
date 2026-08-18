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
        return self.analyze(board, side)["score"]

    def analyze(
        self,
        board: GameBoard,
        side: str,
    ) -> dict:
        """Devuelve el mismo score junto con el objetivo que lo produjo."""
        if not board.food:
            return {
                "score": 0,
                "target_status": "none",
                "food": None,
                "my_distance": None,
                "enemy_distance": None,
                "result": "unknown",
            }

        my_head = board.my_head(side)
        enemy_head = board.enemy_head(side)

        best_score = float("-inf")
        best_entries = []

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

            entry = {
                "food": list(food),
                "my_distance": my_distance,
                "enemy_distance": enemy_distance,
                "result": self._result(my_distance, enemy_distance),
            }
            if food_score > best_score:
                best_score = food_score
                best_entries = [entry]
            elif food_score == best_score:
                best_entries.append(entry)

        if best_score == float("-inf"):
            return {
                "score": 0,
                "target_status": "none",
                "food": None,
                "my_distance": None,
                "enemy_distance": None,
                "result": "unknown",
            }

        unique = len(best_entries) == 1
        selected = best_entries[0] if unique else {}
        return {
            "score": best_score,
            "target_status": "known" if unique else "ambiguous",
            "food": selected.get("food"),
            "my_distance": selected.get("my_distance"),
            "enemy_distance": selected.get("enemy_distance"),
            "result": selected.get("result", "unknown"),
        }

    @staticmethod
    def _result(
        my_distance: int | None,
        enemy_distance: int | None,
    ) -> str:
        if my_distance is None:
            return "unknown"
        if enemy_distance is None or my_distance < enemy_distance:
            return "winning"
        if my_distance == enemy_distance:
            return "tied"
        return "losing"

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
