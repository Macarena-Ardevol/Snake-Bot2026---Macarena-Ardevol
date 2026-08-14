import json
import math
from pathlib import Path
from typing import Any


class MatchAnalyzer:
    """
    Analiza globalmente partidas registradas sin modificar pesos ni estrategia.

    La perspectiva del bot se obtiene, en orden, del ``player_name`` opcional,
    de ``bot_side`` y del campo ``side`` de los turnos históricos.
    """

    MODES = ("balanced", "aggressive", "defensive")
    CAUSES = ("timeout", "collision", "score", "unknown")

    def __init__(
        self,
        games_directory: str | Path = "data/games",
        player_name: str | None = None,
        recent_loss_moves: int = 5,
    ) -> None:
        self.games_directory = Path(games_directory)
        self.player_name = player_name
        self.recent_loss_moves = max(0, recent_loss_moves)

    def analyze(self) -> dict[str, Any]:
        summary = self._empty_summary()
        chosen_components: dict[str, dict[str, float | int]] = {}
        candidate_components: dict[str, dict[str, float | int]] = {}

        if not self.games_directory.exists():
            return summary

        for file_path in sorted(self.games_directory.glob("*.json")):
            summary["files"]["files_seen"] += 1
            match = self._read_match(file_path, summary)

            if match is None:
                continue

            summary["files"]["matches_analyzed"] += 1
            self._analyze_match(
                match,
                summary,
                chosen_components,
                candidate_components,
            )

        self._finalize(summary, chosen_components, candidate_components)
        return summary

    @staticmethod
    def save_summary(summary: dict[str, Any], output_path: str | Path) -> Path:
        """Persiste un resumen solo cuando el llamador lo solicita."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        return path

    def _empty_summary(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "files": {
                "files_seen": 0,
                "matches_analyzed": 0,
                "invalid_files": 0,
                "incomplete_matches": 0,
                "skipped": [],
            },
            "outcomes": {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "unknown": 0,
                "win_rate": 0.0,
                "loss_causes": {cause: 0 for cause in self.CAUSES},
            },
            "scores": {
                "matches_counted": 0,
                "own_average": 0.0,
                "opponent_average": 0.0,
            },
            "terminations": {
                "timeouts": {"own": 0, "opponent": 0},
                "collisions": {"own": 0, "opponent": 0},
                "score_decisions": 0,
                "unknown": 0,
            },
            "strategy_modes": {
                **{mode: 0 for mode in self.MODES},
                "unknown": 0,
            },
            "turns": {
                "total": 0,
                "with_analysis": 0,
                "matches_without_turns": 0,
            },
            "evaluation_components": {
                "chosen_moves": {},
                "all_candidates": {},
            },
            "recent_moves_before_losses": [],
        }

    def _read_match(
        self,
        file_path: Path,
        summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self._skip_file(summary, file_path, type(error).__name__)
            return None

        if not isinstance(data, dict):
            self._skip_file(summary, file_path, "invalid_structure")
            return None

        return data

    @staticmethod
    def _skip_file(
        summary: dict[str, Any],
        file_path: Path,
        reason: str,
    ) -> None:
        summary["files"]["invalid_files"] += 1
        summary["files"]["skipped"].append({
            "file": file_path.name,
            "reason": reason,
        })

    def _analyze_match(
        self,
        match: dict[str, Any],
        summary: dict[str, Any],
        chosen_components: dict[str, dict[str, float | int]],
        candidate_components: dict[str, dict[str, float | int]],
    ) -> None:
        turns_value = match.get("turns", [])
        turns = turns_value if isinstance(turns_value, list) else []
        valid_turns = [turn for turn in turns if isinstance(turn, dict)]
        side = self._resolve_bot_side(match, valid_turns)
        outcome = self._resolve_outcome(match, side)

        incomplete = (
            side is None
            or outcome == "unknown"
            or not self._has_numeric_scores(match)
            or not isinstance(turns_value, list)
            or len(valid_turns) != len(turns)
        )
        if incomplete:
            summary["files"]["incomplete_matches"] += 1

        summary["outcomes"][outcome] += 1
        self._collect_scores(match, side, summary)
        self._collect_turns(
            match,
            valid_turns,
            outcome,
            summary,
            chosen_components,
            candidate_components,
        )
        self._collect_termination(match, valid_turns, side, outcome, summary)

    def _resolve_bot_side(
        self,
        match: dict[str, Any],
        turns: list[dict[str, Any]],
    ) -> str | None:
        player_1 = match.get("player_1")
        player_2 = match.get("player_2")

        if self.player_name is not None:
            if player_1 == self.player_name and player_2 != self.player_name:
                return "A"
            if player_2 == self.player_name and player_1 != self.player_name:
                return "B"
            return None

        observed_sides = {
            candidate
            for candidate in (match.get("bot_side"), match.get("side"))
            if candidate in ("A", "B")
        }
        observed_sides.update(
            turn["side"]
            for turn in turns
            if turn.get("side") in ("A", "B")
        )

        return observed_sides.pop() if len(observed_sides) == 1 else None

    def _resolve_outcome(
        self,
        match: dict[str, Any],
        side: str | None,
    ) -> str:
        if side is None:
            return "unknown"

        winner = match.get("winner")
        own_name = match.get("player_1" if side == "A" else "player_2")
        opponent_name = match.get("player_2" if side == "A" else "player_1")
        opponent_side = "B" if side == "A" else "A"

        if winner in ("A", "B"):
            return "wins" if winner == side else "losses"

        if winner is not None and own_name != opponent_name:
            if winner == own_name:
                return "wins"
            if winner == opponent_name:
                return "losses"

            return "unknown"

        if winner is not None:
            return "unknown"

        remaining = self._number(match.get("remaining_moves"))
        if remaining != 0:
            return "unknown"

        scores = self._scores_for_side(match, side)
        if scores is None:
            return "unknown"

        own_score, opponent_score = scores
        if own_score > opponent_score:
            return "wins"
        if own_score < opponent_score:
            return "losses"
        return "draws"

    @staticmethod
    def _has_numeric_scores(match: dict[str, Any]) -> bool:
        return MatchAnalyzer._number(match.get("score_1")) is not None and (
            MatchAnalyzer._number(match.get("score_2")) is not None
        )

    def _collect_scores(
        self,
        match: dict[str, Any],
        side: str | None,
        summary: dict[str, Any],
    ) -> None:
        if side is None:
            return

        scores = self._scores_for_side(match, side)
        if scores is None:
            return

        own_score, opponent_score = scores
        summary["scores"]["matches_counted"] += 1
        summary["scores"].setdefault("_own_sum", 0.0)
        summary["scores"].setdefault("_opponent_sum", 0.0)
        summary["scores"]["_own_sum"] += own_score
        summary["scores"]["_opponent_sum"] += opponent_score

    def _collect_turns(
        self,
        match: dict[str, Any],
        turns: list[dict[str, Any]],
        outcome: str,
        summary: dict[str, Any],
        chosen_components: dict[str, dict[str, float | int]],
        candidate_components: dict[str, dict[str, float | int]],
    ) -> None:
        if not turns:
            summary["turns"]["matches_without_turns"] += 1
        summary["turns"]["total"] += len(turns)

        for turn in turns:
            mode = turn.get("mode", turn.get("strategy_mode"))
            if isinstance(mode, str) and mode:
                summary["strategy_modes"].setdefault(mode, 0)
                summary["strategy_modes"][mode] += 1
            else:
                summary["strategy_modes"]["unknown"] += 1

            analysis = turn.get("analysis")
            if not isinstance(analysis, dict) or not analysis:
                continue

            summary["turns"]["with_analysis"] += 1
            direction = turn.get("chosen_direction")
            chosen_analysis = analysis.get(direction)

            if isinstance(chosen_analysis, dict):
                self._accumulate_components(chosen_components, chosen_analysis)
            elif self._looks_like_component_map(analysis):
                self._accumulate_components(chosen_components, analysis)

            for candidate in analysis.values():
                if isinstance(candidate, dict):
                    self._accumulate_components(candidate_components, candidate)

        if outcome == "losses" and turns and self.recent_loss_moves > 0:
            recent = turns[-self.recent_loss_moves:]
            summary["recent_moves_before_losses"].append({
                "game_id": match.get("game_id"),
                "moves": [self._compact_turn(turn) for turn in recent],
            })

    def _collect_termination(
        self,
        match: dict[str, Any],
        turns: list[dict[str, Any]],
        side: str | None,
        outcome: str,
        summary: dict[str, Any],
    ) -> None:
        if outcome not in ("wins", "losses") or side is None:
            if outcome != "draws":
                summary["terminations"]["unknown"] += 1
            return

        affected = "own" if outcome == "losses" else "opponent"
        affected_side = side if affected == "own" else self._other_side(side)
        cause = self._termination_cause(match, turns, affected_side, outcome)

        if outcome == "losses":
            summary["outcomes"]["loss_causes"][cause] += 1

        if cause == "timeout":
            summary["terminations"]["timeouts"][affected] += 1
        elif cause == "collision":
            summary["terminations"]["collisions"][affected] += 1
        elif cause == "score":
            summary["terminations"]["score_decisions"] += 1
        else:
            summary["terminations"]["unknown"] += 1

    def _termination_cause(
        self,
        match: dict[str, Any],
        turns: list[dict[str, Any]],
        affected_side: str,
        outcome: str,
    ) -> str:
        explicit_causes = self._explicit_causes(match, affected_side)
        if len(explicit_causes) == 1:
            explicit_cause = explicit_causes.pop()
            if explicit_cause in ("timeout", "collision"):
                return explicit_cause
        elif len(explicit_causes) > 1:
            return "unknown"

        if outcome == "losses" and self._reliable_collision_delta(
            match,
            turns,
            affected_side,
        ):
            return "collision"

        remaining = self._number(match.get("remaining_moves"))
        affected_scores = self._scores_for_side(match, affected_side)
        has_lower_score = (
            affected_scores is not None
            and affected_scores[0] < affected_scores[1]
        )
        if remaining == 0 and has_lower_score:
            return "score"
        return "unknown"

    def _explicit_causes(
        self,
        match: dict[str, Any],
        affected_side: str,
    ) -> set[str]:
        causes = set()

        if self._side_field_matches(
            match,
            ("timeout_side", "timed_out_side"),
            affected_side,
        ):
            causes.add("timeout")
        if self._side_field_matches(
            match,
            ("crashed_side", "collision_side"),
            affected_side,
        ):
            causes.add("collision")

        if match.get("timeout") is True or match.get("timed_out") is True:
            causes.add("timeout")
        if match.get("collision") is True or match.get("crashed") is True:
            causes.add("collision")

        for field in ("end_reason", "termination_reason", "reason"):
            value = match.get(field)
            if not isinstance(value, str):
                continue

            reason = value.strip().lower().replace("_", "-")
            if (
                "timeout" in reason
                or "time-out" in reason
                or "timed out" in reason
            ):
                causes.add("timeout")
            if (
                "collision" in reason
                or "crashed" in reason
                or "collided" in reason
                or "choque" in reason
            ):
                causes.add("collision")

        return causes

    def _side_field_matches(
        self,
        match: dict[str, Any],
        fields: tuple[str, ...],
        side: str,
    ) -> bool:
        player = match.get("player_1" if side == "A" else "player_2")
        for field in fields:
            value = match.get(field)
            if value is None:
                continue
            if value == side or (player is not None and value == player):
                return True
        return False

    def _reliable_collision_delta(
        self,
        match: dict[str, Any],
        turns: list[dict[str, Any]],
        side: str,
    ) -> bool:
        if not turns:
            return False

        last_turn = turns[-1]
        final_scores = self._scores_for_side(match, side)
        previous_scores = self._scores_for_side(last_turn, side)

        if final_scores is None or previous_scores is None:
            return False

        final_own, final_opponent = final_scores
        previous_own, previous_opponent = previous_scores
        return (
            final_own == previous_own - 500
            and final_opponent == previous_opponent + 1000
        )

    @staticmethod
    def _compact_turn(turn: dict[str, Any]) -> dict[str, Any]:
        direction = turn.get("chosen_direction")
        analysis = turn.get("analysis")
        selected_analysis = None
        if isinstance(analysis, dict):
            candidate = analysis.get(direction)
            if isinstance(candidate, dict):
                selected_analysis = candidate

        return {
            "direction": direction,
            "mode": turn.get("mode", turn.get("strategy_mode")),
            "remaining_moves": turn.get("remaining_moves"),
            "score_1": turn.get("score_1"),
            "score_2": turn.get("score_2"),
            "selected_analysis": selected_analysis,
        }

    @staticmethod
    def _looks_like_component_map(analysis: dict[str, Any]) -> bool:
        return any(MatchAnalyzer._number(value) is not None for value in analysis.values())

    @staticmethod
    def _accumulate_components(
        destination: dict[str, dict[str, float | int]],
        components: dict[str, Any],
    ) -> None:
        for name, raw_value in components.items():
            value = MatchAnalyzer._number(raw_value)
            if value is None:
                continue

            stats = destination.setdefault(name, {
                "count": 0,
                "sum": 0.0,
                "minimum": value,
                "maximum": value,
            })
            stats["count"] += 1
            stats["sum"] += value
            stats["minimum"] = min(stats["minimum"], value)
            stats["maximum"] = max(stats["maximum"], value)

    @staticmethod
    def _finalize_components(
        components: dict[str, dict[str, float | int]],
    ) -> dict[str, dict[str, float | int]]:
        finalized = {}
        for name, stats in sorted(components.items()):
            count = int(stats["count"])
            finalized[name] = {
                "count": count,
                "average": stats["sum"] / count if count else 0.0,
                "minimum": stats["minimum"],
                "maximum": stats["maximum"],
            }
        return finalized

    def _finalize(
        self,
        summary: dict[str, Any],
        chosen_components: dict[str, dict[str, float | int]],
        candidate_components: dict[str, dict[str, float | int]],
    ) -> None:
        known_outcomes = sum(
            summary["outcomes"][key]
            for key in ("wins", "losses", "draws")
        )
        if known_outcomes:
            summary["outcomes"]["win_rate"] = (
                summary["outcomes"]["wins"] / known_outcomes
            )

        score_count = summary["scores"]["matches_counted"]
        if score_count:
            summary["scores"]["own_average"] = (
                summary["scores"].pop("_own_sum", 0.0) / score_count
            )
            summary["scores"]["opponent_average"] = (
                summary["scores"].pop("_opponent_sum", 0.0) / score_count
            )
        else:
            summary["scores"].pop("_own_sum", None)
            summary["scores"].pop("_opponent_sum", None)

        summary["evaluation_components"]["chosen_moves"] = (
            self._finalize_components(chosen_components)
        )
        summary["evaluation_components"]["all_candidates"] = (
            self._finalize_components(candidate_components)
        )

    @staticmethod
    def _scores_for_side(
        data: dict[str, Any],
        side: str,
    ) -> tuple[float, float] | None:
        first = MatchAnalyzer._number(data.get("score_1"))
        second = MatchAnalyzer._number(data.get("score_2"))
        if first is None or second is None:
            return None
        return (first, second) if side == "A" else (second, first)

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    @staticmethod
    def _other_side(side: str) -> str:
        return "B" if side == "A" else "A"
