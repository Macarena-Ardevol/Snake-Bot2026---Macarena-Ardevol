"""Auditoría offline de decisiones registradas por GameRecorder."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from statistics import fmean
from typing import Any

from ai.pathfinding import PathFinder
from game.board import GameBoard


class RealMatchAuditor:
    """Analiza comida cercana sin alterar ni reproducir decisiones del bot."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.pathfinder = PathFinder()

    def analyze(
        self,
        game_id: str | None = None,
        losses_only: bool = False,
    ) -> dict[str, Any]:
        games, warnings = self._load_games(game_id)
        selected = [
            game for game in games
            if not losses_only or self._outcome(game) == "loss"
        ]
        decisions: list[dict[str, Any]] = []
        for game in selected:
            for index, turn in enumerate(self._turns(game)):
                decision = self._analyze_turn(game, turn, index)
                if decision is not None:
                    decisions.append(decision)

        summary = self._summarize(games, selected, decisions)
        comparison = self._compare_outcomes(decisions)
        return {
            "status": "ok" if selected else "no_games",
            "source_directory": str(self.directory),
            "filters": {"game_id": game_id, "losses_only": losses_only},
            "summary": summary,
            "decisions": decisions,
            "suspicious_decisions": [
                decision for decision in decisions if decision["suspicious"]
            ],
            "candidate_cases": self._candidate_cases(decisions),
            "outcome_comparison": comparison,
            "warnings": warnings,
            "limitations": [
                "compute_level no está registrado en los JSON actuales",
                "BFS usa el tablero estático del turno y no modela movimientos futuros del rival",
                "analysis histórico puede faltar o contener componentes distintos",
                "la intención del movimiento elegido no está registrada explícitamente",
            ],
        }

    def save(self, report: dict[str, Any], output: str | Path) -> Path:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        export = {
            key: report[key]
            for key in (
                "status", "source_directory", "filters", "summary",
                "suspicious_decisions", "candidate_cases",
                "outcome_comparison", "warnings", "limitations",
            )
        }
        destination.write_text(
            json.dumps(export, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return destination

    def _load_games(
        self,
        requested_game_id: str | None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        games: list[dict[str, Any]] = []
        warnings: list[str] = []
        if not self.directory.exists():
            return games, [f"directorio inexistente: {self.directory}"]

        for path in sorted(self.directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                warnings.append(f"{path.name}: JSON inválido ({error})")
                continue
            if not isinstance(payload, dict):
                warnings.append(f"{path.name}: raíz JSON no es un objeto")
                continue
            identifier = str(payload.get("game_id") or path.stem.removeprefix("game_"))
            if requested_game_id and identifier != requested_game_id:
                continue
            payload = dict(payload)
            payload["_file"] = path.name
            payload["_resolved_game_id"] = identifier
            games.append(payload)
        return games, warnings

    @staticmethod
    def _turns(game: dict[str, Any]) -> list[dict[str, Any]]:
        turns = game.get("turns")
        return [turn for turn in turns if isinstance(turn, dict)] if isinstance(turns, list) else []

    def _analyze_turn(
        self,
        game: dict[str, Any],
        turn: dict[str, Any],
        turn_index: int,
    ) -> dict[str, Any] | None:
        board_text = turn.get("board")
        side = turn.get("side")
        if not isinstance(board_text, str) or side not in ("A", "B"):
            return None
        try:
            board = GameBoard(board_text)
            head = board.my_head(side)
            enemy_head = board.enemy_head(side)
        except (ValueError, IndexError, KeyError):
            return None

        chosen = turn.get("chosen_direction")
        valid_moves = board.valid_moves(side)
        analysis = turn.get("analysis") if isinstance(turn.get("analysis"), dict) else {}
        foods = []
        for food in board.food:
            path = self.pathfinder.shortest_path(board, head, food)
            distance = len(path) - 1 if path else None
            enemy_path = self.pathfinder.shortest_path(board, enemy_head, food)
            enemy_distance = len(enemy_path) - 1 if enemy_path else None
            shortest_routes = self._shortest_routes(board, head, food, distance)
            shortest_directions = list(dict.fromkeys(route[0] for route in shortest_routes))
            manhattan = abs(head[0] - food[0]) + abs(head[1] - food[1])
            classification = self._path_classification(
                chosen, shortest_directions, distance, board, head, food
            )
            food_entry = {
                "position": list(food),
                "distance": distance,
                "manhattan_distance": manhattan,
                "blocked_apparently_close": manhattan <= 3 and (distance is None or distance > 3),
                "shortest_first_directions": shortest_directions,
                "shortest_routes": [list(route) for route in shortest_routes],
                "multiple_shortest_routes": len(shortest_routes) > 1,
                "chosen_path_classification": classification,
                "enemy_distance": enemy_distance,
                "contested": (
                    distance is not None
                    and enemy_distance is not None
                    and enemy_distance <= distance
                ),
            }
            if distance == 1:
                direction = shortest_directions[0] if shortest_directions else None
                food_entry["adjacent_analysis"] = self._adjacent_analysis(
                    direction, chosen, analysis, valid_moves, food_entry, board, head
                )
            foods.append(food_entry)

        nearest = min(
            (food["distance"] for food in foods if food["distance"] is not None),
            default=None,
        )
        adjacent_missed = [
            food for food in foods
            if food["distance"] == 1
            and food.get("adjacent_analysis", {}).get("taken") is False
        ]
        suspicious_foods = [
            food for food in adjacent_missed
            if food["adjacent_analysis"].get("suspicious")
        ]
        my_score, rival_score = self._scores(turn, side)
        opponent = game.get("player_2") if side == "A" else game.get("player_1")
        return {
            "game_id": game.get("_resolved_game_id"),
            "file": game.get("_file"),
            "turn_index": turn_index,
            "outcome": self._outcome(game),
            "remaining_moves": turn.get("remaining_moves"),
            "side": side,
            "player_1": game.get("player_1"),
            "player_2": game.get("player_2"),
            "opponent": opponent,
            "my_score": my_score,
            "rival_score": rival_score,
            "board": board_text,
            "chosen_direction": chosen,
            "valid_moves": valid_moves,
            "mode": turn.get("mode"),
            "compute_level": turn.get("compute_level"),
            "nearest_food_distance": nearest,
            "foods": foods,
            "analysis": analysis,
            "suspicious": bool(suspicious_foods),
            "suspicious_reasons": [
                food["adjacent_analysis"]["reason"] for food in suspicious_foods
            ],
            "confidence": "medium" if suspicious_foods else "none",
        }

    @staticmethod
    def _candidate_cases(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cases = []
        for decision in decisions:
            interesting = []
            for food in decision["foods"]:
                adjacent = food.get("adjacent_analysis")
                if adjacent and not adjacent["taken"]:
                    interesting.append({
                        "food": food["position"],
                        "distance": 1,
                        "classification": adjacent["reason"],
                        "food_direction": adjacent["direction"],
                        "score_gap": adjacent["chosen_minus_food_total"],
                        "component_differences": adjacent["component_differences"][:5],
                    })
                elif (
                    food["distance"] in (2, 3)
                    and food["chosen_path_classification"] == "off_shortest_path"
                ):
                    interesting.append({
                        "food": food["position"],
                        "distance": food["distance"],
                        "classification": "off_shortest_path",
                        "shortest_routes": food["shortest_routes"],
                    })
            if interesting:
                cases.append({
                    "game_id": decision["game_id"],
                    "turn_index": decision["turn_index"],
                    "opponent": decision["opponent"],
                    "board": decision["board"],
                    "side": decision["side"],
                    "my_score": decision["my_score"],
                    "rival_score": decision["rival_score"],
                    "remaining_moves": decision["remaining_moves"],
                    "chosen_direction": decision["chosen_direction"],
                    "mode": decision["mode"],
                    "compute_level": decision["compute_level"],
                    "interesting_foods": interesting,
                })
        return cases

    def _shortest_routes(
        self,
        board: GameBoard,
        start: tuple[int, int],
        food: tuple[int, int],
        distance: int | None,
    ) -> list[tuple[str, ...]]:
        if distance not in (1, 2, 3):
            return []
        routes: list[tuple[str, ...]] = []

        def visit(
            position: tuple[int, int],
            route: tuple[str, ...],
            visited: set[tuple[int, int]],
        ) -> None:
            if len(route) == distance:
                if position == food:
                    routes.append(route)
                return
            for direction in board.DIRECTIONS:
                destination = board.next_position(position, direction)
                if destination in visited or not board.is_free(*destination):
                    continue
                visit(destination, route + (direction,), visited | {destination})

        visit(start, (), {start})
        return routes

    def _path_classification(
        self,
        chosen: Any,
        shortest_directions: list[str],
        distance: int | None,
        board: GameBoard,
        head: tuple[int, int],
        food: tuple[int, int],
    ) -> str:
        if distance is None or chosen not in board.DIRECTIONS:
            return "unknown"
        if not shortest_directions:
            return "unknown"
        if chosen in shortest_directions:
            return "equivalent_shortest_path" if len(shortest_directions) > 1 else "on_shortest_path"
        chosen_position = board.next_position(head, chosen)
        if not board.is_free(*chosen_position):
            return "unknown"
        chosen_path = self.pathfinder.shortest_path(board, chosen_position, food)
        if not chosen_path:
            return "target_ambiguous"
        return "off_shortest_path"

    def _adjacent_analysis(
        self,
        food_direction: str | None,
        chosen: Any,
        analysis: dict[str, Any],
        valid_moves: dict[str, bool],
        food: dict[str, Any],
        board: GameBoard,
        head: tuple[int, int],
    ) -> dict[str, Any]:
        taken = food_direction is not None and chosen == food_direction
        food_analysis = analysis.get(food_direction) if food_direction else None
        chosen_analysis = analysis.get(chosen) if isinstance(chosen, str) else None
        if not isinstance(food_analysis, dict):
            food_analysis = {}
        if not isinstance(chosen_analysis, dict):
            chosen_analysis = {}
        differences = self._component_differences(chosen_analysis, food_analysis)
        reason = "taken" if taken else self._miss_reason(
            food_direction, chosen, food_analysis, chosen_analysis,
            valid_moves, food, board, head, differences,
        )
        food_total = self._number(food_analysis.get("total"))
        chosen_total = self._number(chosen_analysis.get("total"))
        gap = (
            chosen_total - food_total
            if chosen_total is not None and food_total is not None
            else None
        )
        safe_evidence = all(
            self._number(food_analysis.get(key)) is not None
            and self._number(food_analysis.get(key)) >= threshold
            for key, threshold in (
                ("food_safety", 0), ("enemy_risk", 0),
                ("survival", 0), ("mobility", 1), ("bottleneck", -200),
            )
        )
        suspicious = (
            not taken
            and safe_evidence
            and not food["contested"]
            and gap is not None
            and 0 <= gap <= 350
        )
        return {
            "direction": food_direction,
            "taken": taken,
            "valid": valid_moves.get(food_direction, False) if food_direction else False,
            "food_total": food_total,
            "chosen_total": chosen_total,
            "chosen_minus_food_total": gap,
            "food_components": food_analysis,
            "chosen_components": chosen_analysis,
            "component_differences": differences,
            "reason": reason,
            "suspicious": suspicious,
            "confidence": "medium" if suspicious else "high" if reason != "unknown" else "low",
        }

    def _miss_reason(
        self,
        food_direction: str | None,
        chosen: Any,
        food_analysis: dict[str, Any],
        chosen_analysis: dict[str, Any],
        valid_moves: dict[str, bool],
        food: dict[str, Any],
        board: GameBoard,
        head: tuple[int, int],
        differences: list[dict[str, Any]],
    ) -> str:
        if not food_analysis or not chosen_analysis:
            return "insufficient_recorded_data"
        if not food_direction or not valid_moves.get(food_direction, False):
            return "unsafe_food"
        if food["contested"]:
            return "contested_food"
        if self._negative(food_analysis, "enemy_risk"):
            return "immediate_enemy_risk"
        if self._below(food_analysis, "food_safety", 0):
            return "unsafe_food"
        if self._below(food_analysis, "bottleneck", -200):
            return "bottleneck"
        if self._below(food_analysis, "survival", 0) or self._below(food_analysis, "mobility", 1):
            return "low_future_space"
        if isinstance(chosen, str) and self._targets_other_adjacent_food(board, head, chosen, food):
            return "alternative_food_target"
        if differences and differences[0]["component"] == "two_ply" and differences[0]["difference"] > 0:
            return "alternative_move_higher_two_ply"
        return "unknown"

    @staticmethod
    def _targets_other_adjacent_food(
        board: GameBoard,
        head: tuple[int, int],
        chosen: str,
        current_food: dict[str, Any],
    ) -> bool:
        return (
            chosen in board.DIRECTIONS
            and board.next_position(head, chosen) in board.food
            and list(board.next_position(head, chosen)) != current_food["position"]
        )

    @classmethod
    def _component_differences(
        cls,
        chosen: dict[str, Any],
        food: dict[str, Any],
    ) -> list[dict[str, Any]]:
        differences = []
        for key in sorted(set(chosen) | set(food)):
            if key == "total":
                continue
            chosen_value = cls._number(chosen.get(key))
            food_value = cls._number(food.get(key))
            if chosen_value is None or food_value is None:
                continue
            differences.append({
                "component": key,
                "chosen": chosen_value,
                "food_direction": food_value,
                "difference": chosen_value - food_value,
            })
        return sorted(differences, key=lambda item: abs(item["difference"]), reverse=True)

    @staticmethod
    def _number(value: Any) -> float | None:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    @classmethod
    def _negative(cls, analysis: dict[str, Any], key: str) -> bool:
        value = cls._number(analysis.get(key))
        return value is not None and value < 0

    @classmethod
    def _below(cls, analysis: dict[str, Any], key: str, threshold: float) -> bool:
        value = cls._number(analysis.get(key))
        return value is not None and value < threshold

    @staticmethod
    def _scores(turn: dict[str, Any], side: str) -> tuple[Any, Any]:
        return (
            (turn.get("score_1"), turn.get("score_2"))
            if side == "A"
            else (turn.get("score_2"), turn.get("score_1"))
        )

    @staticmethod
    def _outcome(game: dict[str, Any]) -> str:
        winner = game.get("winner")
        if winner in (None, "", "tie", "draw"):
            return "draw" if winner in ("tie", "draw") else "unknown"
        side = game.get("bot_side")
        if side not in ("A", "B"):
            turns = game.get("turns")
            if isinstance(turns, list):
                side = next((turn.get("side") for turn in turns if isinstance(turn, dict) and turn.get("side") in ("A", "B")), None)
        bot_player = game.get("player_1") if side == "A" else game.get("player_2") if side == "B" else None
        opponent = game.get("player_2") if side == "A" else game.get("player_1") if side == "B" else None
        if bot_player is not None and winner == bot_player:
            return "win"
        if opponent is not None and winner == opponent:
            return "loss"
        return "unknown"

    def _summarize(
        self,
        all_games: list[dict[str, Any]],
        selected: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        opportunities = Counter()
        exploited = Counter()
        alternatives = 0
        equivalent = 0
        adjacent_missed = Counter()
        blocked = 0
        for decision in decisions:
            for food in decision["foods"]:
                distance = food["distance"]
                if distance in (1, 2, 3):
                    opportunities[str(distance)] += 1
                    if food["chosen_path_classification"] in ("on_shortest_path", "equivalent_shortest_path"):
                        exploited[str(distance)] += 1
                if distance in (1, 2, 3):
                    alternatives += int(food["multiple_shortest_routes"])
                    equivalent += int(food["chosen_path_classification"] == "equivalent_shortest_path")
                blocked += int(food["blocked_apparently_close"])
                adjacent = food.get("adjacent_analysis")
                if adjacent and not adjacent["taken"]:
                    adjacent_missed[adjacent["reason"]] += 1
        return {
            "game_files_found": len(all_games),
            "games_selected": len(selected),
            "games_with_turns": sum(bool(self._turns(game)) for game in selected),
            "turns_analyzed": len(decisions),
            "outcomes": dict(Counter(self._outcome(game) for game in selected)),
            "food_opportunities": {
                key: {
                    "count": opportunities[key],
                    "on_any_shortest_path": exploited[key],
                    "rate": exploited[key] / opportunities[key] if opportunities[key] else None,
                }
                for key in ("1", "2", "3")
            },
            "foods_with_multiple_shortest_routes": alternatives,
            "chosen_equivalent_shortest_routes": equivalent,
            "apparently_close_but_blocked": blocked,
            "adjacent_food_not_taken": sum(adjacent_missed.values()),
            "adjacent_miss_reasons": dict(adjacent_missed),
            "suspicious_decisions": sum(decision["suspicious"] for decision in decisions),
        }

    def _compare_outcomes(self, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for decision in decisions:
            if decision["outcome"] in ("win", "loss"):
                groups[decision["outcome"]].append(decision)
        result = {}
        for outcome in ("win", "loss"):
            turns = groups[outcome]
            adjacent = []
            distance_two_off = 0
            modes = Counter()
            levels = Counter()
            unknown = 0
            gaps = []
            for decision in turns:
                modes[str(decision.get("mode"))] += 1
                levels[str(decision.get("compute_level"))] += 1
                for food in decision["foods"]:
                    if food["distance"] == 2 and food["chosen_path_classification"] == "off_shortest_path":
                        distance_two_off += 1
                    item = food.get("adjacent_analysis")
                    if item and not item["taken"]:
                        adjacent.append(item)
                        unknown += item["reason"] in ("unknown", "insufficient_recorded_data")
                        if item["chosen_minus_food_total"] is not None:
                            gaps.append(item["chosen_minus_food_total"])
            result[outcome] = {
                "turns": len(turns),
                "adjacent_food_ignored": len(adjacent),
                "distance_2_off_shortest_path": distance_two_off,
                "unknown_adjacent_reasons": unknown,
                "mean_chosen_minus_food_total": fmean(gaps) if gaps else None,
                "modes": dict(modes),
                "compute_levels": dict(levels),
            }
        result["warning"] = "Comparación descriptiva; no implica significancia ni causalidad."
        return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="data/games")
    parser.add_argument("--game-id")
    parser.add_argument("--losses-only", action="store_true")
    parser.add_argument("--output")
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    auditor = RealMatchAuditor(arguments.directory)
    report = auditor.analyze(arguments.game_id, arguments.losses_only)
    if arguments.output:
        auditor.save(report, arguments.output)
    console_report = {
        "status": report["status"],
        "summary": report["summary"],
        "outcome_comparison": report["outcome_comparison"],
        "suspicious_decisions": report["suspicious_decisions"],
        "warnings": report["warnings"],
        "output": arguments.output,
    }
    print(json.dumps(console_report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
