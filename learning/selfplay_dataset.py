import argparse
import copy
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ai import weights
from ai.baseline_strategy import BaselineStrategy
from ai.random_safe_strategy import RandomSafeStrategy
from ai.strategy import SnakeStrategy
from ai.survival_strategy import SurvivalStrategy
from game.board import GameBoard
from local_game.engine import LocalSnakeGame


OpponentFactory = Callable[[int], object]


class _RecordingStrategy:
    """Observa una estrategia sin intervenir en su decisión."""

    def __init__(self, strategy: SnakeStrategy) -> None:
        self.strategy = strategy
        self.turns: list[dict[str, Any]] = []

    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
    ) -> str:
        direction = self.strategy.choose_move(
            board=board,
            side=side,
            remaining_moves=remaining_moves,
            my_score=my_score,
            enemy_score=enemy_score,
        )
        score_1, score_2 = (
            (my_score, enemy_score) if side == "A" else (enemy_score, my_score)
        )
        self.turns.append({
            "remaining_moves": remaining_moves,
            "side": side,
            "score_1": score_1,
            "score_2": score_2,
            "board": "\n".join(f"|{''.join(row)}|" for row in board.grid),
            "chosen_direction": direction,
            "mode": self.strategy.current_mode,
            "analysis": copy.deepcopy(self.strategy.last_analysis),
        })
        return direction


class SelfPlayDatasetGenerator:
    """Genera evidencia local reproducible sin ajustar el bot."""

    DEFAULT_OPPONENTS = ("baseline", "survival", "random_safe", "mirror")

    def __init__(
        self,
        output_root: str | Path = "data/selfplay",
        opponents: Sequence[str] | None = None,
        rows: int = 15,
        cols: int = 15,
        max_moves: int = 300,
        food_count: int = 3,
    ) -> None:
        self.output_root = Path(output_root)
        self.opponents = tuple(opponents or self.DEFAULT_OPPONENTS)
        if not self.opponents:
            raise ValueError("Debe configurarse al menos una estrategia rival.")
        unknown = sorted(set(self.opponents) - set(self.DEFAULT_OPPONENTS))
        if unknown:
            raise ValueError(f"Rivales desconocidos: {', '.join(unknown)}")
        self.rows = rows
        self.cols = cols
        self.max_moves = max_moves
        self.food_count = food_count

    def generate(self, matches: int, base_seed: int = 0) -> dict[str, Any]:
        if matches < 0:
            raise ValueError("La cantidad de partidas no puede ser negativa.")

        dataset_path = self._dataset_path(matches, base_seed)
        dataset_path.mkdir(parents=True, exist_ok=True)
        records = []

        for index in range(matches):
            pair_index = index // 2
            seed = base_seed + pair_index
            advanced_side = "A" if index % 2 == 0 else "B"
            opponent_name = self.opponents[pair_index % len(self.opponents)]
            record = self._play_match(
                index=index,
                seed=seed,
                pair_index=pair_index,
                advanced_side=advanced_side,
                opponent_name=opponent_name,
            )
            path = dataset_path / f"selfplay_{index:06d}.json"
            path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            records.append(record)

        return self._summarize(records, dataset_path, base_seed)

    def _play_match(
        self,
        index: int,
        seed: int,
        pair_index: int,
        advanced_side: str,
        opponent_name: str,
    ) -> dict[str, Any]:
        advanced = _RecordingStrategy(SnakeStrategy())
        opponent = self._create_opponent(opponent_name, seed)
        strategy_a, strategy_b = (
            (advanced, opponent) if advanced_side == "A" else (opponent, advanced)
        )
        game = LocalSnakeGame(
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            rows=self.rows,
            cols=self.cols,
            max_moves=self.max_moves,
            food_count=self.food_count,
            seed=seed,
        )
        result = game.play()
        opponent_side = "B" if advanced_side == "A" else "A"
        opponent_player = f"local:{opponent_name}"
        player_1 = "advanced" if advanced_side == "A" else opponent_player
        player_2 = opponent_player if advanced_side == "A" else "advanced"
        winner = None
        if result.winner == advanced_side:
            winner = "advanced"
        elif result.winner == opponent_side:
            winner = opponent_player

        for turn in advanced.turns:
            turn["player_1"] = player_1
            turn["player_2"] = player_2

        remaining_moves = self.max_moves - result.turns
        end_reason = (
            "collision"
            if result.crashed_side is not None
            else ("score" if winner is not None else "draw")
        )
        pair_id = f"pair_{pair_index:06d}"
        game_id = f"selfplay_{seed}_{pair_index}_{advanced_side}_{opponent_name}"
        return {
            "schema_version": 1,
            "source": "selfplay",
            "game_id": game_id,
            "player_1": player_1,
            "player_2": player_2,
            "bot_side": advanced_side,
            "score_1": result.score_a,
            "score_2": result.score_b,
            "winner": winner,
            "remaining_moves": remaining_moves,
            "turn_count": result.turns,
            "final_board": game.board_text(),
            "crashed_side": result.crashed_side,
            "end_reason": end_reason,
            "turns": advanced.turns,
            "selfplay": {
                "seed": seed,
                "base_seed": seed - pair_index,
                "match_index": index,
                "pair_id": pair_id,
                "pair_index": pair_index,
                "paired_side": advanced_side,
                "opponent_strategy": opponent_name,
                "bot": {
                    "strategy": "ai.strategy.SnakeStrategy",
                    "configuration": "current_defaults",
                    "weights_fingerprint": self._weights_fingerprint(),
                },
                "engine": {
                    "rows": self.rows,
                    "cols": self.cols,
                    "max_moves": self.max_moves,
                    "food_count": self.food_count,
                },
            },
        }

    @staticmethod
    def _create_opponent(name: str, seed: int) -> object:
        factories: dict[str, OpponentFactory] = {
            "baseline": lambda _: BaselineStrategy(),
            "survival": lambda _: SurvivalStrategy(),
            "random_safe": lambda value: RandomSafeStrategy(seed=value),
            "mirror": lambda _: SnakeStrategy(),
        }
        return factories[name](seed)

    def _dataset_path(self, matches: int, base_seed: int) -> Path:
        identity = json.dumps({
            "matches": matches,
            "base_seed": base_seed,
            "opponents": self.opponents,
            "rows": self.rows,
            "cols": self.cols,
            "max_moves": self.max_moves,
            "food_count": self.food_count,
            "weights_fingerprint": self._weights_fingerprint(),
        }, sort_keys=True)
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        return self.output_root / f"run_{suffix}"

    @staticmethod
    def _weights_fingerprint() -> str:
        configuration = {
            name: value
            for name, value in vars(weights).items()
            if name.isupper() and isinstance(value, (int, float, str, bool))
        }
        encoded = json.dumps(configuration, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _summarize(
        records: list[dict[str, Any]],
        dataset_path: Path,
        base_seed: int,
    ) -> dict[str, Any]:
        opponent_counts = Counter(
            record["selfplay"]["opponent_strategy"] for record in records
        )
        side_results = {
            side: {"matches": 0, "wins": 0, "losses": 0, "draws": 0}
            for side in ("A", "B")
        }
        wins = losses = draws = advanced_crashes = opponent_crashes = 0
        own_score = opponent_score = total_turns = 0
        seeds = []
        for record in records:
            side = record["bot_side"]
            side_results[side]["matches"] += 1
            seeds.append(record["selfplay"]["seed"])
            own = record["score_1"] if side == "A" else record["score_2"]
            enemy = record["score_2"] if side == "A" else record["score_1"]
            own_score += own
            opponent_score += enemy
            total_turns += record["turn_count"]
            if record["crashed_side"] == side:
                advanced_crashes += 1
            elif record["crashed_side"] in ("A", "B"):
                opponent_crashes += 1
            if record["winner"] is None:
                draws += 1
                side_results[side]["draws"] += 1
            elif record["winner"] == "advanced":
                wins += 1
                side_results[side]["wins"] += 1
            else:
                losses += 1
                side_results[side]["losses"] += 1

        total = len(records)
        return {
            "matches": total,
            "by_opponent": dict(sorted(opponent_counts.items())),
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "performance_by_side": side_results,
            "advanced_crashes": advanced_crashes,
            "opponent_crashes": opponent_crashes,
            "average_advanced_score": own_score / total if total else 0.0,
            "average_opponent_score": opponent_score / total if total else 0.0,
            "average_turns": total_turns / total if total else 0.0,
            "base_seed": base_seed,
            "seeds": seeds,
            "dataset_path": str(dataset_path),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera partidas locales analizables.")
    parser.add_argument("--matches", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default="data/selfplay")
    parser.add_argument(
        "--opponents",
        default=",".join(SelfPlayDatasetGenerator.DEFAULT_OPPONENTS),
        help="Lista separada por comas: baseline,survival,random_safe,mirror",
    )
    parser.add_argument("--max-moves", type=int, default=300)
    args = parser.parse_args()
    generator = SelfPlayDatasetGenerator(
        output_root=args.output,
        opponents=[name.strip() for name in args.opponents.split(",") if name.strip()],
        max_moves=args.max_moves,
    )
    print(json.dumps(generator.generate(args.matches, args.seed), indent=2))


if __name__ == "__main__":
    main()
