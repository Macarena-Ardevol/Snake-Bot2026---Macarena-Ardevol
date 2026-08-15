import argparse
import json
import math
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ai.baseline_strategy import BaselineStrategy
from ai.random_safe_strategy import RandomSafeStrategy
from ai.strategy import SnakeStrategy
from ai.survival_strategy import SurvivalStrategy
from ai.weight_config import WeightConfig
from local_game.engine import LocalSnakeGame


MatchRunner = Callable[[WeightConfig, WeightConfig, str, int, str], dict[str, Any]]
NON_ADJUSTABLE_WEIGHTS = {"INVALID_MOVE_SCORE"}


def generate_candidates(
    baseline: WeightConfig,
    adjustable: Sequence[str],
    variations: Sequence[float] = (0.05, -0.05, 0.10, -0.10),
    limit: int | None = None,
    advisor_report: Mapping[str, Any] | None = None,
    metric_to_weight: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Genera cambios de un solo parámetro, pequeños y trazables."""
    values = baseline.as_dict()
    unknown = sorted(set(adjustable) - set(values))
    if unknown:
        raise ValueError(f"Pesos ajustables desconocidos: {', '.join(unknown)}")
    forbidden = sorted(set(adjustable) & NON_ADJUSTABLE_WEIGHTS)
    if forbidden:
        raise ValueError(f"Parámetros estructurales no optimizables: {', '.join(forbidden)}")
    if any(not math.isfinite(value) or abs(value) > 0.50 or value == 0 for value in variations):
        raise ValueError("Las variaciones deben ser finitas, no nulas y de hasta 50%.")

    prioritized: list[str] = []
    mapping = dict(metric_to_weight or {})
    if advisor_report and mapping:
        for recommendation in advisor_report.get("recommendations", []):
            metric = recommendation.get("metric") if isinstance(recommendation, dict) else None
            weight = mapping.get(metric)
            if weight in adjustable and weight not in prioritized:
                prioritized.append(weight)
    ordered = prioritized + [name for name in adjustable if name not in prioritized]

    candidates = []
    for name in ordered:
        baseline_value = values[name]
        for variation in variations:
            candidate_value = baseline_value * (1.0 + variation)
            config = baseline.with_changes(**{name: candidate_value})
            candidates.append({
                "config": config,
                "parameter": name,
                "variation": variation,
                "reason": (
                    "advisor_priority" if name in prioritized else "conservative_local_search"
                ),
            })
            if limit is not None and len(candidates) >= max(0, limit):
                return candidates
    return candidates


class CandidateOptimizer:
    """Evalúa configuraciones offline; nunca instala ni persiste pesos."""

    LOCAL_RIVALS = ("baseline", "survival", "random_safe", "mirror")

    def __init__(
        self,
        matches_per_rival: int = 10,
        base_seed: int = 0,
        rivals: Sequence[str] = (),
        min_matches: int = 10,
        promotion_margin: float = 0.10,
        max_crash_rate: float = 0.10,
        reject_score_differential: float = -100.0,
        rows: int = 15,
        cols: int = 15,
        max_moves: int = 300,
        food_count: int = 3,
        match_runner: MatchRunner | None = None,
    ) -> None:
        if matches_per_rival < 0 or matches_per_rival % 2:
            raise ValueError("matches_per_rival debe ser par y no negativo.")
        unknown = sorted(set(rivals) - set(self.LOCAL_RIVALS))
        if unknown:
            raise ValueError(f"Rivales desconocidos: {', '.join(unknown)}")
        self.matches_per_rival = matches_per_rival
        self.base_seed = base_seed
        self.rivals = tuple(rivals)
        self.min_matches = max(2, min_matches)
        self.promotion_margin = max(0.0, promotion_margin)
        self.max_crash_rate = min(1.0, max(0.0, max_crash_rate))
        self.reject_score_differential = reject_score_differential
        self.rows = rows
        self.cols = cols
        self.max_moves = max_moves
        self.food_count = food_count
        self.match_runner = match_runner or self._play_match
        self._cache: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}

    def evaluate(
        self,
        baseline: WeightConfig,
        candidates: Iterable[WeightConfig | Mapping[str, Any]],
    ) -> dict[str, Any]:
        entries = []
        for item in candidates:
            if isinstance(item, WeightConfig):
                config, reason = item, "explicit_candidate"
            else:
                config = item.get("config")
                reason = item.get("reason", "generated_candidate")
                if not isinstance(config, WeightConfig):
                    raise TypeError("Cada candidato debe contener un WeightConfig.")
            entries.append(self._evaluate_candidate(baseline, config, str(reason)))

        ranking = sorted(
            entries,
            key=lambda entry: (-entry["ranking_score"], entry["fingerprint"]),
        )
        for position, entry in enumerate(ranking, 1):
            entry["rank"] = position
        return {
            "schema_version": 1,
            "status": "complete",
            "baseline": {
                "fingerprint": baseline.fingerprint,
                "weights": baseline.as_dict(),
            },
            "experiment": {
                "matches_per_rival": self.matches_per_rival,
                "base_seed": self.base_seed,
                "seeds": [self.base_seed + index for index in range(self.matches_per_rival // 2)],
                "primary_opponent": "stable",
                "auxiliary_rivals": list(self.rivals),
                "paired_sides": ["A", "B"],
                "engine": {
                    "rows": self.rows,
                    "cols": self.cols,
                    "max_moves": self.max_moves,
                    "food_count": self.food_count,
                },
            },
            "candidates": ranking,
            "ranking": [entry["fingerprint"] for entry in ranking],
            "warnings": [
                "Los resultados de self-play son evidencia sintética y no implican mejora competitiva real.",
                "Ningún candidato fue instalado automáticamente.",
            ],
        }

    @staticmethod
    def save_report(report: Mapping[str, Any], output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
        return path

    def _evaluate_candidate(
        self,
        baseline: WeightConfig,
        candidate: WeightConfig,
        reason: str,
    ) -> dict[str, Any]:
        by_rival = {}
        all_matches = []
        for rival in ("stable", *self.rivals):
            matches = []
            for pair_index in range(self.matches_per_rival // 2):
                seed = self.base_seed + pair_index
                for side in ("A", "B"):
                    key = (
                        baseline.fingerprint,
                        candidate.fingerprint,
                        rival,
                        seed,
                        side,
                    )
                    if key not in self._cache:
                        self._cache[key] = self.match_runner(
                            candidate, baseline, rival, seed, side
                        )
                    matches.append(dict(self._cache[key]))
            by_rival[rival] = self._aggregate(matches)
            all_matches.extend(matches)

        aggregate = self._aggregate(all_matches)
        primary = by_rival["stable"]
        auxiliary = [by_rival[name]["composite_score"] for name in self.rivals]
        ranking_score = (
            primary["composite_score"] if not auxiliary else
            0.70 * primary["composite_score"] + 0.30 * statistics.fmean(auxiliary)
        )
        status, status_reason = self._classify(primary)
        return {
            "fingerprint": candidate.fingerprint,
            "modified_parameters": candidate.differences_from(baseline),
            "generation_reason": reason,
            "results": aggregate,
            "results_by_side": aggregate["by_side"],
            "results_by_rival": by_rival,
            "ranking_score": ranking_score,
            "status": status,
            "status_reason": status_reason,
        }

    def _classify(self, primary: Mapping[str, Any]) -> tuple[str, str]:
        if primary["matches"] < self.min_matches:
            return "inconclusive", "Muestra emparejada insuficiente frente a la baseline estable."
        win_rate = primary["win_rate"]
        loss_rate = primary["loss_rate"]
        if primary["own_crash_rate"] > self.max_crash_rate:
            return "rejected", "La tasa de choques propios supera el límite de seguridad."
        if (
            loss_rate - win_rate >= self.promotion_margin
            or primary["average_score_differential"] <= self.reject_score_differential
        ):
            return "rejected", "El candidato pierde margen o puntaje frente a la baseline."
        if (
            win_rate - loss_rate >= self.promotion_margin
            and primary["average_score_differential"] > 0
        ):
            return "promising", "Supera el margen mínimo sin exceder el riesgo de choque."
        return "inconclusive", "La evidencia no separa al candidato de la baseline."

    @staticmethod
    def _aggregate(matches: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(matches)
        wins = sum(match["outcome"] == "win" for match in matches)
        losses = sum(match["outcome"] == "loss" for match in matches)
        draws = count - wins - losses
        own_crashes = sum(bool(match["own_crash"]) for match in matches)
        opponent_crashes = sum(bool(match["opponent_crash"]) for match in matches)
        differentials = [match["own_score"] - match["opponent_score"] for match in matches]
        by_side = {}
        for side in ("A", "B"):
            side_matches = [match for match in matches if match["side"] == side]
            by_side[side] = {
                "matches": len(side_matches),
                "wins": sum(match["outcome"] == "win" for match in side_matches),
                "losses": sum(match["outcome"] == "loss" for match in side_matches),
                "draws": sum(match["outcome"] == "draw" for match in side_matches),
            }
        win_rate = wins / count if count else 0.0
        loss_rate = losses / count if count else 0.0
        crash_rate = own_crashes / count if count else 0.0
        average_diff = statistics.fmean(differentials) if differentials else 0.0
        side_rates = [
            values["wins"] / values["matches"]
            for values in by_side.values() if values["matches"]
        ]
        side_imbalance = abs(side_rates[0] - side_rates[1]) if len(side_rates) == 2 else 0.0
        stability = statistics.pstdev(differentials) if len(differentials) > 1 else 0.0
        composite = (
            100.0 * (win_rate - loss_rate)
            + average_diff / 100.0
            - 100.0 * crash_rate
            + 20.0 * (opponent_crashes / count if count else 0.0)
            - 20.0 * side_imbalance
            - stability / 1000.0
        )
        return {
            "matches": count,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "average_score": statistics.fmean([m["own_score"] for m in matches]) if matches else 0.0,
            "average_opponent_score": statistics.fmean([m["opponent_score"] for m in matches]) if matches else 0.0,
            "average_score_differential": average_diff,
            "own_crashes": own_crashes,
            "opponent_crashes": opponent_crashes,
            "own_crash_rate": crash_rate,
            "score_differential_stddev": stability,
            "side_win_rate_imbalance": side_imbalance,
            "by_side": by_side,
            "composite_score": composite,
        }

    def _play_match(
        self,
        candidate: WeightConfig,
        baseline: WeightConfig,
        rival: str,
        seed: int,
        candidate_side: str,
    ) -> dict[str, Any]:
        candidate_strategy = SnakeStrategy(weight_config=candidate)
        if rival in ("stable", "mirror"):
            opponent = SnakeStrategy(weight_config=baseline)
        elif rival == "baseline":
            opponent = BaselineStrategy()
        elif rival == "survival":
            opponent = SurvivalStrategy()
        else:
            opponent = RandomSafeStrategy(seed=seed)
        strategy_a, strategy_b = (
            (candidate_strategy, opponent) if candidate_side == "A" else (opponent, candidate_strategy)
        )
        result = LocalSnakeGame(
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            rows=self.rows,
            cols=self.cols,
            max_moves=self.max_moves,
            food_count=self.food_count,
            seed=seed,
        ).play()
        opponent_side = "B" if candidate_side == "A" else "A"
        own_score = result.score_a if candidate_side == "A" else result.score_b
        opponent_score = result.score_b if candidate_side == "A" else result.score_a
        outcome = "draw" if result.winner is None else (
            "win" if result.winner == candidate_side else "loss"
        )
        return {
            "seed": seed,
            "side": candidate_side,
            "outcome": outcome,
            "own_score": own_score,
            "opponent_score": opponent_score,
            "own_crash": result.crashed_side == candidate_side,
            "opponent_crash": result.crashed_side == opponent_side,
            "turns": result.turns,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa pesos candidatos offline.")
    parser.add_argument("--weights", default="SPACE_WEIGHT,FOOD_DISTANCE_WEIGHT")
    parser.add_argument("--variations", default="5,-5,10,-10")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--matches", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rivals", default="")
    parser.add_argument("--max-moves", type=int, default=60)
    parser.add_argument("--output")
    args = parser.parse_args()
    baseline = WeightConfig.from_current_defaults()
    candidates = generate_candidates(
        baseline,
        [name.strip() for name in args.weights.split(",") if name.strip()],
        [float(value) / 100.0 for value in args.variations.split(",")],
        args.limit,
    )
    optimizer = CandidateOptimizer(
        matches_per_rival=args.matches,
        base_seed=args.seed,
        rivals=[name.strip() for name in args.rivals.split(",") if name.strip()],
        max_moves=args.max_moves,
    )
    report = optimizer.evaluate(baseline, candidates)
    if args.output:
        CandidateOptimizer.save_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
