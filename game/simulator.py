from game.board import GameBoard


class BoardSimulator:
    """
    Simula un movimiento propio sin modificar
    el tablero original.
    """

    def simulate_move(
        self,
        board: GameBoard,
        side: str,
        direction: str,
    ) -> GameBoard | None:
        head = board.my_head(side)

        next_position = board.next_position(
            head,
            direction,
        )

        if not board.is_free(
            *next_position
        ):
            return None

        simulated = board.clone()

        mutable_grid = [
            list(row)
            for row in simulated.grid
        ]

        head_symbol = side
        body_symbol = side.lower()

        eating = (
            next_position
            in simulated.food
        )

        # La cabeza anterior pasa a cuerpo.
        mutable_grid[
            head[0]
        ][
            head[1]
        ] = body_symbol

        # Nueva cabeza.
        mutable_grid[
            next_position[0]
        ][
            next_position[1]
        ] = head_symbol

        old_body = (
            simulated.snakes[
                side
            ]["body"].copy()
        )

        new_body = [
            head
        ] + old_body

        # Si no come intentamos liberar
        # una cola inequívoca.
        if not eating:
            tail = self._find_safe_tail(
                board,
                side,
            )

            if tail is not None:
                mutable_grid[
                    tail[0]
                ][
                    tail[1]
                ] = " "

                if tail in new_body:
                    new_body.remove(
                        tail
                    )

        else:
            simulated.food.remove(
                next_position
            )

        simulated.grid = [
            "".join(row)
            for row in mutable_grid
        ]

        simulated.snakes[
            side
        ]["head"] = next_position

        simulated.snakes[
            side
        ]["body"] = new_body

        return simulated

    def _find_safe_tail(
        self,
        board: GameBoard,
        side: str,
    ) -> tuple[int, int] | None:
        """
        Identifica una cola solo cuando hay
        una candidata inequívoca.
        """
        head = board.my_head(side)

        body = set(
            board.snakes[
                side
            ]["body"]
        )

        snake_cells = (
            body
            | {head}
        )

        candidates = []

        for position in body:
            connected_neighbours = sum(
                neighbour in snake_cells
                for neighbour
                in board.neighbours(
                    *position
                )
            )

            if connected_neighbours == 1:
                candidates.append(
                    position
                )

        if len(candidates) == 1:
            return candidates[0]

        return None