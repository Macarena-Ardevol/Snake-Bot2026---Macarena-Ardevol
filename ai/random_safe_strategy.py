import random

from game.board import GameBoard


class RandomSafeStrategy:
    """
    Elige aleatoriamente entre los movimientos legales.

    Sirve para probar que nuestro bot no dependa
    únicamente del comportamiento de un rival BFS.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
    ) -> str:
        valid_moves = [
            direction
            for direction, valid in board.valid_moves(side).items()
            if valid
        ]

        if not valid_moves:
            return "up"

        return self.random.choice(valid_moves)