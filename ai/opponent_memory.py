import json
import threading
from functools import wraps
from pathlib import Path


def synchronized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class OpponentMemory:
    """
    Guarda estadísticas históricas sobre cada rival.
    """

    def __init__(
        self,
        file_path: str = "data/opponents.json",
    ) -> None:
        self.file_path = Path(file_path)

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()
        self.data = self._load()

    def _load(self) -> dict:
        if not self.file_path.exists():
            return {}

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return {}

    @synchronized
    def save(self) -> None:
        temporary_path = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        with self._lock:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
            temporary_path.replace(self.file_path)

    @synchronized
    def record_move(
        self,
        opponent: str,
        direction: str,
        moved_toward_food: bool = False,
        moved_toward_us: bool = False,
        contested_food: bool = False,
    ) -> None:
        stats = self._get_stats(opponent)

        stats["moves"] += 1

        if direction in stats["directions"]:
            stats["directions"][direction] += 1

        if moved_toward_food:
            stats["toward_food"] += 1

        if moved_toward_us:
            stats["toward_us"] += 1

        if contested_food:
            stats["contested_food"] += 1

        self.save()

    @synchronized
    def record_game(
        self,
        opponent: str,
        won: bool,
    ) -> None:
        stats = self._get_stats(opponent)

        stats["games"] += 1

        if won:
            stats["wins_against"] += 1
        else:
            stats["losses_against"] += 1

        self.save()

    @synchronized
    def get_stats(
        self,
        opponent: str,
    ) -> dict:
        return self._get_stats(opponent).copy()

    @synchronized
    def direction_probability(
        self,
        opponent: str,
        direction: str,
    ) -> float:
        stats = self._get_stats(opponent)

        total_moves = stats["moves"]

        if total_moves == 0:
            return 0.25

        return (
            stats["directions"].get(direction, 0)
            / total_moves
        )

    @synchronized
    def food_aggression(
        self,
        opponent: str,
    ) -> float:
        return self._ratio(
            opponent,
            "toward_food",
            default=0.5,
        )

    @synchronized
    def head_aggression(
        self,
        opponent: str,
    ) -> float:
        return self._ratio(
            opponent,
            "toward_us",
            default=0.5,
        )

    @synchronized
    def contest_aggression(
        self,
        opponent: str,
    ) -> float:
        return self._ratio(
            opponent,
            "contested_food",
            default=0.5,
        )

    def _ratio(
        self,
        opponent: str,
        key: str,
        default: float,
    ) -> float:
        stats = self._get_stats(opponent)

        if stats["moves"] == 0:
            return default

        return stats[key] / stats["moves"]

    def _get_stats(
        self,
        opponent: str,
    ) -> dict:
        if opponent not in self.data:
            self.data[opponent] = {}

        stats = self.data[opponent]

        # setdefault permite mantener compatibles
        # archivos opponents.json antiguos.
        stats.setdefault("games", 0)
        stats.setdefault("wins_against", 0)
        stats.setdefault("losses_against", 0)

        stats.setdefault("moves", 0)
        stats.setdefault("toward_food", 0)
        stats.setdefault("toward_us", 0)
        stats.setdefault("contested_food", 0)
        stats.setdefault("predictions", 0)
        stats.setdefault("correct_predictions", 0)

        stats.setdefault(
            "directions",
            {
                "up": 0,
                "down": 0,
                "left": 0,
                "right": 0,
            },
        )

        for direction in (
            "up",
            "down",
            "left",
            "right",
        ):
            stats["directions"].setdefault(
                direction,
                0,
            )

        return stats

    @synchronized
    def confidence(
        self,
        opponent: str,
        sample_size: int = 20,
    ) -> float:
        """
        Devuelve un valor entre 0 y 1 según cuántos
        movimientos observamos del rival.

        Con pocas observaciones, la memoria pesa poco.
        Con suficientes observaciones, pesa más.
        """
        stats = self._get_stats(opponent)

        moves = stats["moves"]

        if moves <= 0:
            return 0.0

        return min(
            moves / sample_size,
            1.0,
        )

    @synchronized
    def record_prediction(
        self,
        opponent: str,
        predicted_direction: str,
        actual_direction: str,
    ) -> None:
        stats = self._get_stats(opponent)

        stats["predictions"] += 1

        if predicted_direction == actual_direction:
            stats["correct_predictions"] += 1

        self.save()


    @synchronized
    def prediction_accuracy(
        self,
        opponent: str,
    ) -> float | None:
        stats = self._get_stats(opponent)

        total = stats["predictions"]

        if total == 0:
            return None

        return (
            stats["correct_predictions"]
            / total
        )
