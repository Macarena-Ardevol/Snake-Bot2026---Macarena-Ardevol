from ai.opponent_memory import OpponentMemory


class OpponentProfile:
    """
    Clasifica el estilo histórico de un rival.

    Perfiles posibles:
    - unknown
    - food_hunter
    - aggressive
    - defensive
    - balanced
    """

    def __init__(
        self,
        memory: OpponentMemory,
    ) -> None:
        self.memory = memory

    def classify(
        self,
        opponent: str,
    ) -> str:
        confidence = self.memory.confidence(
            opponent
        )

        # Todavía no tenemos suficientes datos.
        if confidence < 0.30:
            return "unknown"

        food = self.memory.food_aggression(
            opponent
        )

        head = self.memory.head_aggression(
            opponent
        )

        contest = self.memory.contest_aggression(
            opponent
        )

        if (
            food >= 0.70
            and contest >= 0.55
        ):
            return "food_hunter"

        if head >= 0.65:
            return "aggressive"

        if (
            food <= 0.35
            and head <= 0.35
            and contest <= 0.35
        ):
            return "defensive"

        return "balanced"