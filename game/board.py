from game.parser import BoardParser


class GameBoard:
    """
    Representa el tablero completo del juego.
    """

    DIRECTIONS = {
        "up": (-1, 0),
        "down": (1, 0),
        "left": (0, -1),
        "right": (0, 1),
    }

    def __init__(self, board: str):
        parser = BoardParser(board)

        self.grid = parser.grid
        self.snakes = parser.find_snakes()
        self.food = parser.find_food()

        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.grid else 0

    def is_inside(self, row: int, col: int) -> bool:
        """
        Indica si una posición está dentro del tablero.
        """
        return (
            0 <= row < self.rows
            and 0 <= col < self.cols
        )

    def cell(self, row: int, col: int) -> str:
        """
        Devuelve el contenido de una casilla.
        """
        if not self.is_inside(row, col):
            raise IndexError(
                "La posición está fuera del tablero."
            )

        return self.grid[row][col]

    def is_free(self, row: int, col: int) -> bool:
        """
        Indica si la serpiente puede avanzar
        a la casilla.

        Las únicas casillas transitables son:
        - espacio vacío
        - comida
        """
        if not self.is_inside(row, col):
            return False

        return self.grid[row][col] in (" ", "*")

    def my_head(
        self,
        side: str,
    ) -> tuple[int, int]:
        """
        Devuelve la cabeza de la serpiente indicada.
        """
        head = self.snakes[side]["head"]

        if head is None:
            raise ValueError(
                f"No se encontró la cabeza "
                f"de la serpiente {side}."
            )

        return head

    def enemy_head(
        self,
        side: str,
    ) -> tuple[int, int]:
        """
        Devuelve la cabeza rival.
        """
        enemy = (
            "B"
            if side == "A"
            else "A"
        )

        return self.my_head(enemy)

    def next_position(
        self,
        position: tuple[int, int],
        direction: str,
    ) -> tuple[int, int]:
        """
        Calcula la posición después de moverse.
        """
        if direction not in self.DIRECTIONS:
            raise ValueError(
                f"Dirección inválida: {direction}"
            )

        row, col = position
        dr, dc = self.DIRECTIONS[direction]

        return (
            row + dr,
            col + dc,
        )

    def neighbours(
        self,
        row: int,
        col: int,
    ) -> list[tuple[int, int]]:
        """
        Devuelve las posiciones vecinas dentro del tablero.
        """
        candidates = [
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ]

        return [
            position
            for position in candidates
            if self.is_inside(*position)
        ]

    def valid_moves(
        self,
        side: str,
    ) -> dict[str, bool]:
        """
        Devuelve los movimientos actualmente legales.
        """
        head = self.my_head(side)

        return {
            direction: self.is_free(
                *self.next_position(
                    head,
                    direction,
                )
            )
            for direction in self.DIRECTIONS
        }

    def clone(self) -> "GameBoard":
        """
        Devuelve una copia independiente del tablero.
        """
        board = GameBoard.__new__(
            GameBoard
        )

        board.grid = self.grid.copy()

        board.snakes = {
            snake: {
                "head": data["head"],
                "body": data["body"].copy(),
            }
            for snake, data
            in self.snakes.items()
        }

        board.food = self.food.copy()

        board.rows = self.rows
        board.cols = self.cols

        return board