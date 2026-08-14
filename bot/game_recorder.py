import json
from datetime import datetime
from pathlib import Path
from typing import Any


class GameRecorder:
    """
    Guarda los turnos y el resultado de cada partida.
    """

    def __init__(self, directory: str = "data/games") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.games: dict[str, list[dict[str, Any]]] = {}

    def record_turn(
        self,
        game_id: str,
        data: dict,
        direction: str,
        analysis: dict,
        mode: str | None = None,
    ) -> None:
        """
        Guarda el estado recibido y la decisión tomada.
        """

        print(
            f"[RECORDER] record_turn "
            f"| game_id={game_id}"
        )

        turn = {
            "timestamp": datetime.now().isoformat(),
            "remaining_moves": data.get("remaining_moves"),
            "side": data.get("side"),
            "player_1": data.get("player_1"),
            "player_2": data.get("player_2"),
            "score_1": data.get("score_1"),
            "score_2": data.get("score_2"),
            "board": data.get("board"),
            "chosen_direction": direction,
            "mode": mode,
            "analysis": analysis,
        }

        self.games.setdefault(
            game_id,
            [],
        ).append(turn)

        print(
            f"[RECORDER] turnos guardados para "
            f"{game_id}: "
            f"{len(self.games[game_id])}"
        )

    def finish_game(
        self,
        game_id: str,
        data: dict,
    ) -> Path:
        """
        Guarda la partida completa y elimina
        los datos temporales.
        """

        print(
            f"[RECORDER] finish_game "
            f"| game_id={game_id}"
        )

        print(
            f"[RECORDER] turnos encontrados: "
            f"{len(self.games.get(game_id, []))}"
        )

        turns = self.games.get(game_id, [])
        bot_side = next(
            (
                turn.get("side")
                for turn in turns
                if turn.get("side") in ("A", "B")
            ),
            None,
        )

        game_data = {
            "game_id": game_id,
            "finished_at": datetime.now().isoformat(),
            "player_1": data.get("player_1"),
            "player_2": data.get("player_2"),
            "score_1": data.get("score_1"),
            "score_2": data.get("score_2"),
            "winner": data.get("winner"),
            "remaining_moves": data.get("remaining_moves"),
            "bot_side": bot_side,
            "final_board": data.get("board"),
            "turns": turns,
        }

        file_path = (
            self.directory
            / f"game_{game_id}.json"
        )

        with file_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                game_data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        self.games.pop(
            game_id,
            None,
        )

        return file_path
