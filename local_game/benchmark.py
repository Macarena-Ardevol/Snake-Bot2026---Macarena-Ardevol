from collections.abc import Callable

from ai.baseline_strategy import BaselineStrategy
from ai.random_safe_strategy import RandomSafeStrategy
from ai.strategy import SnakeStrategy
from ai.survival_strategy import SurvivalStrategy
from local_game.engine import LocalSnakeGame


StrategyFactory = Callable[[], object]


def play_pair(
    seed: int,
    opponent_factory: StrategyFactory,
) -> dict[str, int]:
    results = {
        "advanced_wins": 0,
        "opponent_wins": 0,
        "draws": 0,
        "advanced_crashes": 0,
        "opponent_crashes": 0,
        "advanced_score": 0,
        "opponent_score": 0,
    }

    for advanced_side in ("A", "B"):
        opponent_side = "B" if advanced_side == "A" else "A"

        if advanced_side == "A":
            strategy_a = SnakeStrategy()
            strategy_b = opponent_factory()
        else:
            strategy_a = opponent_factory()
            strategy_b = SnakeStrategy()

        game = LocalSnakeGame(
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            seed=seed,
        )

        result = game.play()

        advanced_score = (
            result.score_a
            if advanced_side == "A"
            else result.score_b
        )

        opponent_score = (
            result.score_b
            if advanced_side == "A"
            else result.score_a
        )

        results["advanced_score"] += advanced_score
        results["opponent_score"] += opponent_score

        if result.crashed_side == advanced_side:
            results["advanced_crashes"] += 1

        elif result.crashed_side == opponent_side:
            results["opponent_crashes"] += 1

        if result.winner is None:
            results["draws"] += 1

        elif result.winner == advanced_side:
            results["advanced_wins"] += 1

        else:
            results["opponent_wins"] += 1

    return results


def benchmark_opponent(
    name: str,
    opponent_factory: StrategyFactory,
    number_of_pairs: int = 10,
) -> None:
    totals = {
        "advanced_wins": 0,
        "opponent_wins": 0,
        "draws": 0,
        "advanced_crashes": 0,
        "opponent_crashes": 0,
        "advanced_score": 0,
        "opponent_score": 0,
    }

    for seed in range(number_of_pairs):
        pair_results = play_pair(
            seed,
            opponent_factory,
        )

        for key in totals:
            totals[key] += pair_results[key]

    total_matches = number_of_pairs * 2

    win_rate = (
        totals["advanced_wins"]
        / total_matches
        * 100
    )

    print(f"\n=== CONTRA {name.upper()} ===")
    print(f"Partidas: {total_matches}")
    print(f"Victorias avanzadas: {totals['advanced_wins']}")
    print(f"Victorias rival: {totals['opponent_wins']}")
    print(f"Empates: {totals['draws']}")
    print(f"Choques avanzados: {totals['advanced_crashes']}")
    print(f"Choques rival: {totals['opponent_crashes']}")

    print(
        "Puntaje medio avanzado: "
        f"{totals['advanced_score'] / total_matches:.2f}"
    )

    print(
        "Puntaje medio rival: "
        f"{totals['opponent_score'] / total_matches:.2f}"
    )

    print(f"Tasa de victoria: {win_rate:.2f}%")


def run_benchmark() -> None:
    benchmark_opponent(
        "BFS básico",
        BaselineStrategy,
    )

    benchmark_opponent(
        "supervivencia",
        SurvivalStrategy,
    )

    benchmark_opponent(
        "aleatorio seguro",
        RandomSafeStrategy,
    )


if __name__ == "__main__":
    run_benchmark()