class BoardParser:
    """
    Convierte el tablero recibido del servidor
    en información utilizable por el bot.
    """

    def __init__(self, board: str):
        self.board = board
        self.grid = self._convert_to_grid()

    def _convert_to_grid(self):
        """
        Convierte el string del tablero
        en una lista de filas.
        """

        # El servidor suele terminar el tablero con un salto de línea.  Si se
        # conserva, aparece una fila vacía y los algoritmos que recorren una
        # grilla rectangular terminan con IndexError.
        rows = self.board.splitlines()

        while rows and not rows[-1].strip():
            rows.pop()

        if not rows:
            raise ValueError("El tablero está vacío.")

        # Quitamos los bordes | |
        clean_rows = []

        for row in rows:
            # También admite sangría accidental en fixtures multilínea, pero
            # nunca altera los espacios que pertenecen al interior del tablero.
            left_border = row.find("|")
            right_border = row.rfind("|")

            if left_border == -1 or right_border <= left_border:
                raise ValueError(f"Fila de tablero inválida: {row!r}")

            if row[right_border + 1:].strip():
                raise ValueError(f"Fila de tablero inválida: {row!r}")

            clean_rows.append(row[left_border + 1:right_border])

        width = len(clean_rows[0])

        if width == 0 or any(len(row) != width for row in clean_rows):
            raise ValueError("El tablero no es una grilla rectangular.")

        return clean_rows

    def find_food(self):
        """
        Busca todas las posiciones de comida.
        """

        food_positions = []

        for row, line in enumerate(self.grid):
            for col, cell in enumerate(line):
                if cell == "*":
                    food_positions.append((row, col))

        return food_positions

    def find_snakes(self):
        """
        Busca cabezas y cuerpos de ambas serpientes.
        """

        snakes = {
            "A": {
                "head": None,
                "body": []
            },
            "B": {
                "head": None,
                "body": []
            }
        }

        for row, line in enumerate(self.grid):
            for col, cell in enumerate(line):

                if cell == "A":
                    snakes["A"]["head"] = (row, col)

                elif cell == "a":
                    snakes["A"]["body"].append((row, col))

                elif cell == "B":
                    snakes["B"]["head"] = (row, col)

                elif cell == "b":
                    snakes["B"]["body"].append((row, col))

        return snakes
