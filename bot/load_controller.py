from dataclasses import dataclass


@dataclass(frozen=True)
class LoadSnapshot:
    level: str
    pending_decisions: int


class AdaptiveLoadController:
    """Clasifica la presión de decisiones con histéresis."""

    def __init__(self, decision_workers: int) -> None:
        workers = max(1, decision_workers)
        self.busy_enter = workers + 1
        self.busy_exit = max(0, workers - 1)
        # La evaluación competitiva mostró que busy conserva mejor calidad
        # que critical. Permitimos hasta dieciséis tandas del executor antes
        # de usar el recorte máximo; aun así, el stress de 70/100 partidas se
        # mantiene ampliamente por debajo de la latencia de la estrategia
        # normal. La salida a ocho tandas evita oscilar cerca del umbral.
        self.critical_enter = workers * 16 + 1
        self.critical_exit = workers * 8
        self.pending_decisions = 0
        self.level = "normal"

    def decision_started(self) -> LoadSnapshot:
        self.pending_decisions += 1

        if self.level == "normal" and self.pending_decisions >= self.busy_enter:
            self.level = "busy"

        if self.level == "busy" and self.pending_decisions >= self.critical_enter:
            self.level = "critical"

        return LoadSnapshot(self.level, self.pending_decisions)

    def decision_finished(self) -> LoadSnapshot:
        self.pending_decisions = max(0, self.pending_decisions - 1)

        if self.level == "critical" and self.pending_decisions <= self.critical_exit:
            self.level = "busy"

        if self.level == "busy" and self.pending_decisions <= self.busy_exit:
            self.level = "normal"

        return LoadSnapshot(self.level, self.pending_decisions)
