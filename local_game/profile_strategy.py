from statistics import mean

from ai.baseline_strategy import BaselineStrategy
from ai.strategy import SnakeStrategy
from local_game.engine import LocalSnakeGame
from local_game.timed_strategy import TimedStrategy


def percentile(
    values: list[float],
    percentage: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = int(
        (len(ordered) - 1)
        * percentage
    )

    return ordered[index]


def profile_strategy(
    number_of_matches: int = 20,
) -> None:
    all_times: list[float] = []

    for seed in range(number_of_matches):
        advanced = TimedStrategy(
            SnakeStrategy()
        )

        game = LocalSnakeGame(
            strategy_a=advanced,
            strategy_b=BaselineStrategy(),
            seed=seed,
        )

        game.play()

        all_times.extend(
            advanced.decision_times
        )

    if not all_times:
        print("No se registraron movimientos.")
        return

    print("\n=== PERFIL DE RENDIMIENTO ===")
    print(f"Partidas: {number_of_matches}")
    print(f"Decisiones medidas: {len(all_times)}")

    print(
        "Promedio: "
        f"{mean(all_times) * 1000:.2f} ms"
    )

    print(
        "Percentil 95: "
        f"{percentile(all_times, 0.95) * 1000:.2f} ms"
    )

    print(
        "Máximo: "
        f"{max(all_times) * 1000:.2f} ms"
    )


if __name__ == "__main__":
    profile_strategy()