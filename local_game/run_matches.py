from ai.baseline_strategy import BaselineStrategy
from ai.strategy import SnakeStrategy
from local_game.engine import LocalSnakeGame


def run_single_match(
    seed: int,
    advanced_side: str,
):
    if advanced_side == "A":
        strategy_a = SnakeStrategy()
        strategy_b = BaselineStrategy()
    else:
        strategy_a = BaselineStrategy()
        strategy_b = SnakeStrategy()

    game = LocalSnakeGame(
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        seed=seed,
    )

    return game.play()


def run_matches(number_of_pairs: int = 500) -> None:
    results = {
        "advanced_wins": 0,
        "baseline_wins": 0,
        "draws": 0,
        "advanced_crashes": 0,
        "baseline_crashes": 0,
        "advanced_score_wins": 0,
        "baseline_score_wins": 0,
        "advanced_as_a_wins": 0,
        "advanced_as_b_wins": 0,
    }

    total_advanced_score = 0
    total_baseline_score = 0
    total_turns = 0

    for seed in range(number_of_pairs):
        for advanced_side in ("A", "B"):
            baseline_side = (
                "B"
                if advanced_side == "A"
                else "A"
            )

            result = run_single_match(
                seed=seed,
                advanced_side=advanced_side,
            )

            advanced_score = (
                result.score_a
                if advanced_side == "A"
                else result.score_b
            )

            baseline_score = (
                result.score_b
                if advanced_side == "A"
                else result.score_a
            )

            total_advanced_score += advanced_score
            total_baseline_score += baseline_score
            total_turns += result.turns

            if result.crashed_side == advanced_side:
                results["advanced_crashes"] += 1

            elif result.crashed_side == baseline_side:
                results["baseline_crashes"] += 1

            if result.winner is None:
                results["draws"] += 1
                continue

            if result.winner == advanced_side:
                results["advanced_wins"] += 1

                if advanced_side == "A":
                    results["advanced_as_a_wins"] += 1
                else:
                    results["advanced_as_b_wins"] += 1

                if result.crashed_side == baseline_side:
                    pass
                else:
                    results["advanced_score_wins"] += 1

            else:
                results["baseline_wins"] += 1

                if result.crashed_side == advanced_side:
                    pass
                else:
                    results["baseline_score_wins"] += 1

    total_matches = number_of_pairs * 2

    advanced_win_rate = (
        results["advanced_wins"]
        / total_matches
        * 100
    )

    advanced_a_rate = (
        results["advanced_as_a_wins"]
        / number_of_pairs
        * 100
    )

    advanced_b_rate = (
        results["advanced_as_b_wins"]
        / number_of_pairs
        * 100
    )

    print("\n=== SELF-PLAY EMPAREJADO ===")
    print(f"Semillas: {number_of_pairs}")
    print(f"Partidas: {total_matches}")

    print("\nVictorias totales")
    print(f"Bot avanzado: {results['advanced_wins']}")
    print(f"Bot básico: {results['baseline_wins']}")
    print(f"Empates: {results['draws']}")

    print("\nVictorias por puntaje")
    print(
        "Bot avanzado: "
        f"{results['advanced_score_wins']}"
    )
    print(
        "Bot básico: "
        f"{results['baseline_score_wins']}"
    )

    print("\nChoques")
    print(
        "Bot avanzado: "
        f"{results['advanced_crashes']}"
    )
    print(
        "Bot básico: "
        f"{results['baseline_crashes']}"
    )

    print("\nRendimiento por lado")
    print(
        f"Avanzado como A: "
        f"{results['advanced_as_a_wins']} "
        f"({advanced_a_rate:.2f}%)"
    )
    print(
        f"Avanzado como B: "
        f"{results['advanced_as_b_wins']} "
        f"({advanced_b_rate:.2f}%)"
    )

    print("\nPromedios")
    print(
        "Puntaje avanzado: "
        f"{total_advanced_score / total_matches:.2f}"
    )
    print(
        "Puntaje básico: "
        f"{total_baseline_score / total_matches:.2f}"
    )
    print(
        "Turnos por partida: "
        f"{total_turns / total_matches:.2f}"
    )

    print(
        "\nTasa de victoria avanzada: "
        f"{advanced_win_rate:.2f}%"
    )


if __name__ == "__main__":
    run_matches(500)