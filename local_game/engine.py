import random
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from game.board import GameBoard


Position = tuple[int, int]


class Strategy(Protocol):
    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
    ) -> str:
        ...


@dataclass
class MatchResult:
    winner: str | None
    score_a: int
    score_b: int
    turns: int
    crashed_side: str | None


class LocalSnakeGame:
    """
    Motor local para probar estrategias de Snake.

    Aplica:
    - turnos alternados;
    - +1 por sobrevivir;
    - +100 por comer;
    - -500 al chocar;
    - +1000 al rival cuando ocurre un choque.
    """

    DIRECTIONS = {
        "up": (-1, 0),
        "down": (1, 0),
        "left": (0, -1),
        "right": (0, 1),
    }

    def __init__(
        self,
        strategy_a: Strategy,
        strategy_b: Strategy,
        rows: int = 15,
        cols: int = 15,
        max_moves: int = 300,
        food_count: int = 3,
        seed: int | None = None,
    ) -> None:
        if rows < 7 or cols < 7:
            raise ValueError("El tablero debe tener al menos 7 filas y 7 columnas.")

        self.strategy_a = strategy_a
        self.strategy_b = strategy_b

        self.rows = rows
        self.cols = cols
        self.max_moves = max_moves
        self.food_count = food_count

        self.random = random.Random(seed)

        snake_a_row = rows // 3
        snake_b_row = (rows * 2) // 3

        self.snakes: dict[str, deque[Position]] = {
            "A": deque([
                (snake_a_row, 3),
                (snake_a_row, 2),
                (snake_a_row, 1),
            ]),
            "B": deque([
                (snake_b_row, cols - 4),
                (snake_b_row, cols - 3),
                (snake_b_row, cols - 2),
            ]),
        }

        self.scores = {
            "A": 0,
            "B": 0,
        }

        self.food: set[Position] = set()
        self.turns_played = 0
        self.crashed_side: str | None = None

        self._spawn_food()

    def play(self) -> MatchResult:
        """
        Ejecuta una partida completa.
        """
        current_side = "A"

        while (
            self.turns_played < self.max_moves
            and self.crashed_side is None
        ):
            self._play_turn(current_side)

            current_side = self._enemy_side(current_side)

        winner = self._winner()

        return MatchResult(
            winner=winner,
            score_a=self.scores["A"],
            score_b=self.scores["B"],
            turns=self.turns_played,
            crashed_side=self.crashed_side,
        )

    def _play_turn(self, side: str) -> None:
        board = GameBoard(self.board_text())

        strategy = (
            self.strategy_a
            if side == "A"
            else self.strategy_b
        )

        enemy = self._enemy_side(side)

        direction = strategy.choose_move(
            board=board,
            side=side,
            remaining_moves=self.max_moves - self.turns_played,
            my_score=self.scores[side],
            enemy_score=self.scores[enemy],
        )

        self._apply_move(side, direction)

        self.turns_played += 1

    def _apply_move(
        self,
        side: str,
        direction: str,
    ) -> None:
        if direction not in self.DIRECTIONS:
            self._register_crash(side)
            return

        snake = self.snakes[side]
        head = snake[0]

        dr, dc = self.DIRECTIONS[direction]
        next_position = (
            head[0] + dr,
            head[1] + dc,
        )

        eating = next_position in self.food

        if self._is_collision(
            side=side,
            next_position=next_position,
            eating=eating,
        ):
            self._register_crash(side)
            return

        snake.appendleft(next_position)

        if eating:
            self.food.remove(next_position)
            self.scores[side] += 100
            self._spawn_food()
        else:
            snake.pop()

        self.scores[side] += 1

    def _is_collision(
        self,
        side: str,
        next_position: Position,
        eating: bool,
    ) -> bool:
        row, col = next_position

        if not (
            0 <= row < self.rows
            and 0 <= col < self.cols
        ):
            return True

        own_snake = self.snakes[side]
        enemy_snake = self.snakes[self._enemy_side(side)]

        own_occupied = set(own_snake)

        # Si no come, la cola se moverá y puede dejar libre esa casilla.
        if not eating and own_snake:
            own_occupied.discard(own_snake[-1])

        if next_position in own_occupied:
            return True

        if next_position in set(enemy_snake):
            return True

        return False

    def _register_crash(self, side: str) -> None:
        enemy = self._enemy_side(side)

        self.scores[side] -= 500
        self.scores[enemy] += 1000

        self.crashed_side = side

    def _spawn_food(self) -> None:
        while len(self.food) < self.food_count:
            free_cells = self._free_cells()

            if not free_cells:
                return

            self.food.add(
                self.random.choice(free_cells)
            )

    def _free_cells(self) -> list[Position]:
        occupied = (
            set(self.snakes["A"])
            | set(self.snakes["B"])
            | self.food
        )

        return [
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if (row, col) not in occupied
        ]

    def board_text(self) -> str:
        """
        Devuelve el tablero con el mismo formato textual del servidor.
        """
        grid = [
            [" " for _ in range(self.cols)]
            for _ in range(self.rows)
        ]

        for row, col in self.food:
            grid[row][col] = "*"

        for side in ("A", "B"):
            snake = self.snakes[side]

            if not snake:
                continue

            head = snake[0]
            grid[head[0]][head[1]] = side

            body_symbol = side.lower()

            for row, col in list(snake)[1:]:
                grid[row][col] = body_symbol

        return "\n".join(
            f"|{''.join(row)}|"
            for row in grid
        )

    def _winner(self) -> str | None:
        if self.crashed_side is not None:
            return self._enemy_side(self.crashed_side)

        if self.scores["A"] > self.scores["B"]:
            return "A"

        if self.scores["B"] > self.scores["A"]:
            return "B"

        return None

    @staticmethod
    def _enemy_side(side: str) -> str:
        return "B" if side == "A" else "A"