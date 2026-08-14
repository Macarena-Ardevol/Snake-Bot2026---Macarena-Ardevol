import json
import math
from pathlib import Path
from typing import Any


class LearningAdvisor:
    """
    Convierte estadísticas históricas en recomendaciones observacionales.

    No importa ni modifica la estrategia, sus pesos o configuración. El
    resultado expresa correlaciones y señales para revisión humana, nunca
    cambios automáticos.
    """

    def __init__(
        self,
        min_matches: int = 10,
        min_component_samples: int = 20,
        min_component_matches: int = 5,
        min_mode_matches: int = 8,
        min_cause_count: int = 3,
        rate_gap: float = 0.15,
        component_gap: float = 0.20,
        selection_gap: float = 0.25,
    ) -> None:
        self.min_matches = max(2, min_matches)
        self.min_component_samples = max(2, min_component_samples)
        self.min_component_matches = max(2, min_component_matches)
        self.min_mode_matches = max(2, min_mode_matches)
        self.min_cause_count = max(2, min_cause_count)
        self.rate_gap = max(0.0, rate_gap)
        self.component_gap = max(0.0, component_gap)
        self.selection_gap = max(0.0, selection_gap)

    def analyze(self, summary: dict[str, Any]) -> dict[str, Any]:
        report = self._empty_report()

        if not isinstance(summary, dict):
            self._warning(
                report,
                "incomplete_summary",
                "El resumen no es un objeto estructurado.",
            )
            self._add_insufficient_data(report, 0)
            return report

        outcomes = self._mapping(summary.get("outcomes"))
        files = self._mapping(summary.get("files"))
        turns = self._mapping(summary.get("turns"))
        wins = self._count(outcomes.get("wins"))
        losses = self._count(outcomes.get("losses"))
        draws = self._count(outcomes.get("draws"))
        unknown = self._count(outcomes.get("unknown"))
        known_outcomes = wins + losses + draws
        matches_analyzed = self._count(files.get("matches_analyzed"))
        if matches_analyzed == 0:
            matches_analyzed = known_outcomes + unknown

        report["evidence"].update({
            "matches_analyzed": matches_analyzed,
            "known_outcomes": known_outcomes,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "unknown_outcomes": unknown,
            "turns": self._count(turns.get("total")),
        })

        required_sections = (
            "files",
            "outcomes",
            "evaluation_components",
            "evaluation_components_by_outcome",
            "mode_performance",
        )
        if any(not isinstance(summary.get(section), dict) for section in required_sections):
            self._warning(
                report,
                "incomplete_summary",
                "Faltan secciones del resumen necesarias para algunas comparaciones.",
            )

        if unknown:
            self._warning(
                report,
                "unknown_outcomes",
                f"Hay {unknown} partidas cuyo resultado no pudo determinarse.",
            )

        if known_outcomes < self.min_matches:
            self._add_insufficient_data(report, known_outcomes)
            return report

        win_rate = wins / known_outcomes
        self._analyze_global_performance(
            report,
            known_outcomes,
            wins,
            losses,
            draws,
            win_rate,
        )
        self._analyze_loss_causes(report, outcomes, losses, known_outcomes)
        self._analyze_components(report, summary)
        self._analyze_selection_gaps(report, summary)
        self._analyze_modes(report, summary, win_rate, known_outcomes, outcomes)

        if not report["recommendations"]:
            report["status"] = "no_clear_signal"
            self._warning(
                report,
                "no_clear_signal",
                "La evidencia disponible no supera los umbrales para una recomendación direccional.",
            )
        else:
            report["status"] = "ready"

        report["metrics_used"] = sorted(set(report["metrics_used"]))
        return report

    @staticmethod
    def save_report(report: dict[str, Any], output_path: str | Path) -> Path:
        """Guarda el reporte solo cuando se solicita explícitamente."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        return path

    def _empty_report(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": "insufficient_data",
            "evidence": {
                "matches_analyzed": 0,
                "known_outcomes": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "unknown_outcomes": 0,
                "turns": 0,
                "component_metrics_compared": 0,
                "modes_evaluated": 0,
            },
            "thresholds": {
                "min_matches": self.min_matches,
                "min_component_samples_per_outcome": self.min_component_samples,
                "min_component_matches_per_outcome": self.min_component_matches,
                "min_mode_matches": self.min_mode_matches,
                "min_confirmed_cause_count": self.min_cause_count,
                "minimum_rate_gap": self.rate_gap,
                "minimum_component_relative_gap": self.component_gap,
                "minimum_selection_relative_gap": self.selection_gap,
            },
            "recommendations": [],
            "warnings": [],
            "metrics_used": [],
        }

    def _add_insufficient_data(self, report: dict[str, Any], sample: int) -> None:
        confidence = round(
            min(0.49, 0.49 * sample / self.min_matches),
            2,
        )
        report["status"] = "insufficient_data"
        report["recommendations"].append(self._recommendation(
            kind="insufficient_data",
            category="data_quality",
            priority="low",
            confidence=confidence,
            evidence={
                "known_outcomes": sample,
                "minimum_required": self.min_matches,
            },
            sample_size=sample,
            metric=None,
            direction="collect_more_data",
            explanation=(
                "La muestra es insuficiente para emitir recomendaciones históricas fiables."
            ),
        ))
        self._warning(
            report,
            "insufficient_data",
            f"Se requieren al menos {self.min_matches} resultados conocidos.",
        )

    def _analyze_global_performance(
        self,
        report: dict[str, Any],
        sample: int,
        wins: int,
        losses: int,
        draws: int,
        win_rate: float,
    ) -> None:
        report["metrics_used"].append("outcomes.win_rate")
        if win_rate >= 0.65:
            direction = "maintain"
            explanation = (
                "El rendimiento global es predominantemente ganador; conviene preservar "
                "la configuración mientras se valida con más partidas."
            )
        elif win_rate <= 0.35:
            direction = "review"
            explanation = (
                "El rendimiento global es predominantemente perdedor y justifica una "
                "revisión humana, no un cambio automático."
            )
        else:
            return

        confidence = self._confidence(sample, self.min_matches)
        report["recommendations"].append(self._recommendation(
            kind="performance",
            category="global_performance",
            priority=self._priority(confidence, abs(win_rate - 0.5) * 2),
            confidence=confidence,
            evidence={
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": win_rate,
            },
            sample_size=sample,
            metric="win_rate",
            direction=direction,
            explanation=explanation,
        ))

    def _analyze_loss_causes(
        self,
        report: dict[str, Any],
        outcomes: dict[str, Any],
        losses: int,
        known_outcomes: int,
    ) -> None:
        causes = self._mapping(outcomes.get("loss_causes"))
        if losses <= 0:
            return

        for cause in ("collision", "score", "timeout"):
            count = self._count(causes.get(cause))
            if count > losses:
                self._warning(
                    report,
                    "contradictory_cause_counts",
                    f"La causa {cause} supera la cantidad total de derrotas.",
                )
                continue

            rate = count / losses
            if count < self.min_cause_count or rate < 0.30:
                continue

            report["metrics_used"].append(f"loss_causes.{cause}")
            confidence = self._confidence(count, self.min_cause_count)
            explanations = {
                "collision": (
                    "Las colisiones confirmadas representan una parte material de las "
                    "derrotas; corresponde revisar decisiones terminales de seguridad."
                ),
                "score": (
                    "Las derrotas confirmadas por puntaje son frecuentes; corresponde "
                    "revisar el equilibrio entre supervivencia y acumulación de puntos."
                ),
                "timeout": (
                    "Hay varios timeouts confirmados; corresponde revisar rendimiento y "
                    "márgenes de tiempo fuera del camino competitivo."
                ),
            }
            report["recommendations"].append(self._recommendation(
                kind="loss_cause",
                category="termination_risk",
                priority=self._priority(confidence, rate),
                confidence=confidence,
                evidence={
                    "count": count,
                    "losses": losses,
                    "rate_among_losses": rate,
                    "known_outcomes": known_outcomes,
                },
                sample_size=count,
                metric=cause,
                direction="review",
                explanation=explanations[cause],
            ))

    def _analyze_components(
        self,
        report: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        segmented = self._mapping(summary.get("evaluation_components_by_outcome"))
        win_metrics = self._mapping(
            self._mapping(segmented.get("wins")).get("chosen_moves")
        )
        loss_metrics = self._mapping(
            self._mapping(segmented.get("losses")).get("chosen_moves")
        )
        common = sorted(set(win_metrics) & set(loss_metrics))
        compared = 0

        for metric in common:
            win_stats = self._valid_stats(win_metrics.get(metric))
            loss_stats = self._valid_stats(loss_metrics.get(metric))
            if win_stats is None or loss_stats is None:
                continue

            win_average, win_count, win_matches = win_stats
            loss_average, loss_count, loss_matches = loss_stats
            sample = min(win_count, loss_count)
            supporting_matches = min(win_matches, loss_matches)
            if (
                sample < self.min_component_samples
                or supporting_matches < self.min_component_matches
            ):
                continue

            compared += 1
            denominator = max(abs(win_average), abs(loss_average), 1.0)
            relative_difference = (loss_average - win_average) / denominator
            if abs(relative_difference) < self.component_gap:
                continue

            confidence = min(
                self._confidence(sample, self.min_component_samples),
                self._confidence(
                    supporting_matches,
                    self.min_component_matches,
                ),
            )
            report["metrics_used"].append(f"component.{metric}.by_outcome")
            report["recommendations"].append(self._recommendation(
                kind="component_correlation",
                category="evaluation_component",
                priority=self._priority(confidence, abs(relative_difference)),
                confidence=confidence,
                evidence={
                    "win_average": win_average,
                    "loss_average": loss_average,
                    "win_samples": win_count,
                    "loss_samples": loss_count,
                    "win_matches": win_matches,
                    "loss_matches": loss_matches,
                    "relative_difference": relative_difference,
                },
                sample_size=sample,
                metric=metric,
                direction="review",
                explanation=(
                    f"El componente dinámico '{metric}' presenta una diferencia histórica "
                    "entre movimientos de partidas ganadas y perdidas. Es una correlación "
                    "para investigar y no demuestra causalidad ni que deba cambiarse su peso."
                ),
            ))

        report["evidence"]["component_metrics_compared"] = compared
        if compared == 0:
            self._warning(
                report,
                "missing_segmented_components",
                "No hay componentes comparables con muestra suficiente en victorias y derrotas.",
            )
        elif any(item["kind"] == "component_correlation" for item in report["recommendations"]):
            self._warning(
                report,
                "correlation_not_causation",
                "Las diferencias de componentes son correlaciones observadas, no efectos causales.",
            )

    def _analyze_selection_gaps(
        self,
        report: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        components = self._mapping(summary.get("evaluation_components"))
        chosen = self._mapping(components.get("valid_chosen_moves"))
        candidates = self._mapping(components.get("valid_candidates"))
        context = self._mapping(components.get("selection_context"))
        comparable_turns = self._count(
            context.get("turns_with_multiple_valid_candidates")
        )
        comparable_matches = self._count(
            context.get("matches_with_multiple_valid_candidates")
        )

        # Los resúmenes anteriores no demostraban la validez de cada opción.
        # No reutilizamos sus agregados ambiguos para inferir una señal.
        if (
            comparable_turns < self.min_component_samples
            or comparable_matches < self.min_component_matches
        ):
            self._warning(
                report,
                "insufficient_valid_candidate_data",
                "No hay suficientes turnos y partidas con al menos dos candidatos inequívocamente válidos para comparar la selección.",
            )
            return

        for metric in sorted(set(chosen) & set(candidates)):
            chosen_stats = self._valid_stats(chosen.get(metric))
            candidate_stats = self._valid_stats(candidates.get(metric))
            if chosen_stats is None or candidate_stats is None:
                continue

            chosen_average, chosen_count, chosen_matches = chosen_stats
            candidate_average, candidate_count, candidate_matches = candidate_stats
            sample = min(chosen_count, candidate_count)
            supporting_matches = min(chosen_matches, candidate_matches)
            if (
                sample < self.min_component_samples
                or supporting_matches < self.min_component_matches
            ):
                continue

            denominator = max(abs(chosen_average), abs(candidate_average), 1.0)
            relative_difference = (
                (chosen_average - candidate_average) / denominator
            )
            # Elegir candidatos con promedio superior al conjunto completo es
            # esperable. Solo señalamos el caso inverso y material.
            if relative_difference > -self.selection_gap:
                continue

            confidence = min(
                self._confidence(sample, self.min_component_samples),
                self._confidence(
                    supporting_matches,
                    self.min_component_matches,
                ),
            )
            report["metrics_used"].append(f"component.{metric}.selection_gap")
            report["recommendations"].append(self._recommendation(
                kind="selection_gap",
                category="move_selection",
                priority=self._priority(confidence, abs(relative_difference)),
                confidence=confidence,
                evidence={
                    "chosen_average": chosen_average,
                    "candidate_average": candidate_average,
                    "chosen_samples": chosen_count,
                    "candidate_samples": candidate_count,
                    "chosen_matches": chosen_matches,
                    "candidate_matches": candidate_matches,
                    "relative_difference": relative_difference,
                },
                sample_size=sample,
                metric=metric,
                direction="review",
                explanation=(
                    f"El valor medio de '{metric}' en movimientos elegidos es menor que "
                    "en el conjunto de candidatos. La comparación sirve para auditar "
                    "selección, pero no indica por sí sola qué peso debería cambiar."
                ),
            ))

    def _analyze_modes(
        self,
        report: dict[str, Any],
        summary: dict[str, Any],
        overall_win_rate: float,
        known_outcomes: int,
        outcomes: dict[str, Any],
    ) -> None:
        modes = self._mapping(summary.get("mode_performance"))
        global_causes = self._mapping(outcomes.get("loss_causes"))
        global_cause_rates = {
            cause: (
                self._count(global_causes.get(cause)) / known_outcomes
                if known_outcomes else 0.0
            )
            for cause in ("collision", "score", "timeout")
        }
        evaluated = 0

        for mode, raw_performance in sorted(modes.items()):
            if mode == "unknown":
                continue
            performance = self._mapping(raw_performance)
            matches = self._count(performance.get("matches"))
            wins = self._count(performance.get("wins"))
            losses = self._count(performance.get("losses"))
            draws = self._count(performance.get("draws"))
            known = wins + losses + draws
            if matches < self.min_mode_matches or known < self.min_mode_matches:
                continue
            if known > matches:
                self._warning(
                    report,
                    "contradictory_mode_counts",
                    f"El modo {mode} tiene más resultados que partidas atribuidas.",
                )
                continue

            evaluated += 1
            mode_win_rate = wins / known
            rate_difference = mode_win_rate - overall_win_rate
            if abs(rate_difference) >= self.rate_gap:
                confidence = self._confidence(known, self.min_mode_matches)
                report["metrics_used"].append(f"mode.{mode}.win_rate")
                report["recommendations"].append(self._recommendation(
                    kind="mode_performance",
                    category="strategy_mode",
                    priority=self._priority(confidence, abs(rate_difference)),
                    confidence=confidence,
                    evidence={
                        "mode_win_rate": mode_win_rate,
                        "overall_win_rate": overall_win_rate,
                        "rate_difference": rate_difference,
                        "wins": wins,
                        "losses": losses,
                        "draws": draws,
                    },
                    sample_size=known,
                    metric=mode,
                    direction="maintain" if rate_difference > 0 else "review",
                    explanation=(
                        f"Las partidas con modo dominante '{mode}' muestran un rendimiento "
                        "distinto del promedio global. La asociación no prueba que el modo "
                        "sea la causa y no habilita selección automática."
                    ),
                ))

            causes = self._mapping(performance.get("loss_causes"))
            for cause in ("collision", "score", "timeout"):
                cause_count = self._count(causes.get(cause))
                if cause_count > losses:
                    self._warning(
                        report,
                        "contradictory_mode_causes",
                        f"El modo {mode} tiene más casos de {cause} que derrotas.",
                    )
                    continue

                cause_rate = cause_count / matches
                cause_gap = cause_rate - global_cause_rates[cause]
                if not (
                    cause_count >= self.min_cause_count
                    and cause_rate >= 0.25
                    and cause_gap >= self.rate_gap
                ):
                    continue

                confidence = self._confidence(matches, self.min_mode_matches)
                report["metrics_used"].append(f"mode.{mode}.{cause}_rate")
                report["recommendations"].append(self._recommendation(
                    kind="mode_risk",
                    category="strategy_mode_safety",
                    priority=self._priority(confidence, cause_rate),
                    confidence=confidence,
                    evidence={
                        "cause": cause,
                        "cause_count": cause_count,
                        "mode_matches": matches,
                        "mode_cause_rate": cause_rate,
                        "global_cause_rate": global_cause_rates[cause],
                        "rate_difference": cause_gap,
                    },
                    sample_size=matches,
                    metric=mode,
                    direction="review",
                    explanation=(
                        f"El modo dominante '{mode}' aparece asociado a una tasa de "
                        f"{cause} confirmado mayor que la global. Es una señal para "
                        "revisión y no una prueba causal."
                    ),
                ))

        report["evidence"]["modes_evaluated"] = evaluated
        if evaluated == 0:
            self._warning(
                report,
                "insufficient_mode_data",
                "Ningún modo tiene suficientes partidas con atribución dominante única.",
            )

    @staticmethod
    def _recommendation(
        *,
        kind: str,
        category: str,
        priority: str,
        confidence: float,
        evidence: dict[str, Any],
        sample_size: int,
        metric: str | None,
        direction: str,
        explanation: str,
    ) -> dict[str, Any]:
        return {
            "kind": kind,
            "category": category,
            "priority": priority,
            "confidence": confidence,
            "evidence": evidence,
            "sample_size": sample_size,
            "metric": metric,
            "direction": direction,
            "explanation": explanation,
            "automatic_action": False,
        }

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) else None

    @classmethod
    def _count(cls, value: Any) -> int:
        number = cls._number(value)
        if number is None or number < 0:
            return 0
        return int(number)

    @classmethod
    def _valid_stats(cls, value: Any) -> tuple[float, int, int] | None:
        stats = cls._mapping(value)
        average = cls._number(stats.get("average"))
        count = cls._count(stats.get("count"))
        matches = cls._count(stats.get("matches"))
        if average is None or count <= 0 or matches <= 0:
            return None
        return average, count, matches

    @staticmethod
    def _warning(report: dict[str, Any], code: str, message: str) -> None:
        if any(item["code"] == code and item["message"] == message for item in report["warnings"]):
            return
        report["warnings"].append({"code": code, "message": message})

    @staticmethod
    def _confidence(sample: int, minimum: int) -> float:
        if sample <= 0 or minimum <= 0:
            return 0.0
        return round(min(0.95, 0.5 * math.sqrt(sample / minimum)), 2)

    @staticmethod
    def _priority(confidence: float, magnitude: float) -> str:
        if confidence >= 0.75 and magnitude >= 0.30:
            return "high"
        if confidence >= 0.50 and magnitude >= 0.15:
            return "medium"
        return "low"
