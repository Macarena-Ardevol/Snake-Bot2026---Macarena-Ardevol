from ai.strategy import SnakeStrategy
from local_game.engine import LocalSnakeGame


def run_mirror_benchmark(
    number_of_matches: int = 100,
) -> None:
    wins_a = 0
    wins_b = 0
    draws = 0

    crashes_a = 0
    crashes_b = 0

    total_score_a = 0
    total_score_b = 0
    total_turns = 0

    for seed in range(number_of_matches):
        game = LocalSnakeGame(
            strategy_a=SnakeStrategy(),
            strategy_b=SnakeStrategy(),
            seed=seed,
        )

        result = game.play()

        total_score_a += result.score_a
        total_score_b += result.score_b
        total_turns += result.turns

        if result.crashed_side == "A":
            crashes_a += 1

        elif result.crashed_side == "B":
            crashes_b += 1

        if result.winner == "A":
            wins_a += 1

        elif result.winner == "B":
            wins_b += 1

        else:
            draws += 1

    print("\n=== SELF-PLAY ESPEJO ===")
    print(f"Partidas: {number_of_matches}")

    print("\nVictorias")
    print(f"A: {wins_a}")
    print(f"B: {wins_b}")
    print(f"Empates: {draws}")

    print("\nChoques")
    print(f"A: {crashes_a}")
    print(f"B: {crashes_b}")

    print("\nPromedios")
    print(
        "Puntaje A: "
        f"{total_score_a / number_of_matches:.2f}"
    )
    print(
        "Puntaje B: "
        f"{total_score_b / number_of_matches:.2f}"
    )
    print(
        "Turnos: "
        f"{total_turns / number_of_matches:.2f}"
    )


if __name__ == "__main__":
    run_mirror_benchmark()