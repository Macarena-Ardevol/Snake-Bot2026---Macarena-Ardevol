from ai.evaluator import MoveEvaluator
from ai.two_ply import TwoPlyAnalyzer
from ai import weights
from game.board import GameBoard
from ai.opponent_memory import OpponentMemory
from ai.opponent_model import OpponentModel
from ai.opponent_profile import OpponentProfile
from ai.weight_config import WeightConfig


class SnakeStrategy:
    """
    Elige el movimiento con mayor puntaje considerando
    el estado actual y dos niveles futuros.
    """

    MOVE_ORDER = (
        "up",
        "down",
        "left",
        "right",
    )

    def __init__(
        self,
        opponent_memory: OpponentMemory | None = None,
        weight_config: WeightConfig | None = None,
    ) -> None:
        self.weight_config = weight_config or WeightConfig.from_current_defaults()
        self.opponent_memory = opponent_memory

        self.opponent_profile = (
            OpponentProfile(opponent_memory)
            if opponent_memory is not None
            else None
        )

        self.current_opponent: str | None = None
        self.current_opponent_profile = "unknown"

        self.opponent_model = OpponentModel(
            memory=opponent_memory,
        )

        self.evaluator = MoveEvaluator(
            opponent_model=self.opponent_model,
            weight_config=self.weight_config,
        )

        self.two_ply = TwoPlyAnalyzer(weight_config=self.weight_config)

        self.last_analysis: dict[
            str,
            dict[str, float]
        ] = {}

        self.current_mode = "balanced"
        self.last_compute_level = "normal"

    def choose_move(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None = None,
        my_score: int = 0,
        enemy_score: int = 0,
        compute_level: str = "normal",
    ) -> str:
        if compute_level not in ("normal", "busy", "critical"):
            raise ValueError(f"Nivel de cálculo desconocido: {compute_level}")

        self.last_compute_level = compute_level
        self.current_mode = self._choose_mode(
            remaining_moves=remaining_moves,
            my_score=my_score,
            enemy_score=enemy_score,
        )

        enemy = "B" if side == "A" else "A"

        self.last_enemy_prediction = None
        if compute_level != "critical":
            self.last_enemy_prediction = (
                self.opponent_model.predicted_move(
                    board,
                    enemy,
                )
            )

        self.last_analysis = {}

        candidates = []

        # Primera etapa:
        # evaluación rápida de todos los movimientos.
        for direction in self.MOVE_ORDER:
            analysis = self.evaluator.analyze_move(
                board,
                side,
                direction,
                compute_level=compute_level,
            )

            analysis["two_ply"] = 0

            self.last_analysis[direction] = analysis

            if (
                analysis["total"]
                != self.evaluator.INVALID_MOVE_SCORE
            ):
                candidates.append(
                    (
                        direction,
                        analysis["total"],
                    )
                )

        # Si no hay movimientos legales.
        if not candidates:
            return "up"

        # Ordenamos por evaluación inmediata.
        candidates.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        deep_candidates = candidates[:2]

        should_search_deeper = False

        if len(deep_candidates) == 1:
            should_search_deeper = True

        else:
            best_fast_score = deep_candidates[0][1]
            second_fast_score = deep_candidates[1][1]

            score_gap = abs(
                best_fast_score - second_fast_score
            )

            should_search_deeper = (
                score_gap <= self.weight_config.DEEP_SEARCH_GAP
            )

        if compute_level == "normal" and should_search_deeper:
            for direction, _ in deep_candidates:
                two_ply_score = (
                    self.two_ply.score(
                        board,
                        side,
                        direction,
                    )
                    * self.weight_config.TWO_PLY_WEIGHT
                )

                self.last_analysis[
                    direction
                ]["two_ply"] = two_ply_score

        critical_position = self._is_critical_position(
            board=board,
            side=side,
            remaining_moves=remaining_moves,
            my_score=my_score,
            enemy_score=enemy_score,
            candidates=candidates,
        )

        if compute_level == "normal" and critical_position:
            self._deep_search_candidates(
                board,
                side,
                candidates,
            )

        best_move = candidates[0][0]
        best_score = float("-inf")

        # Ahora aplicamos modos y perfil del rival.
        for direction, _ in candidates:
            adjusted = self._adjust_analysis(
                self.last_analysis[direction],
                self.current_mode,
            )

            self.last_analysis[
                direction
            ] = adjusted

            if adjusted["total"] > best_score:
                best_score = adjusted["total"]
                best_move = direction

        return best_move
   
    def _choose_mode(
            self,
            remaining_moves: int | None,
            my_score: int,
            enemy_score: int,
        ) -> str:
            """
            Decide el comportamiento según el estado de la partida.

            balanced:
                Juego normal.

            aggressive:
                Necesitamos recuperar puntos.

            defensive:
                Tenemos ventaja y conviene protegerla.
            """
            score_difference = my_score - enemy_score

            if remaining_moves is None:
                if score_difference <= -200:
                    return "aggressive"

                if score_difference >= 400:
                    return "defensive"

                return "balanced"

            # Final de partida
            if remaining_moves <= 40:
                if score_difference > 0:
                    return "defensive"

                return "aggressive"

            # Segunda mitad
            if remaining_moves <= 100:
                if score_difference >= 300:
                    return "defensive"

                if score_difference <= -150:
                    return "aggressive"

            # Resto de la partida
            if score_difference >= 600:
                return "defensive"

            if score_difference <= -300:
                return "aggressive"

            return "balanced"

    def _adjust_analysis(
        self,
        analysis: dict[str, float],
        mode: str,
    ) -> dict[str, float]:
        adjusted = analysis.copy()


        if analysis["total"] == self.evaluator.INVALID_MOVE_SCORE:
            return adjusted

        if mode == "defensive":
            adjusted["space"] *= 1.4
            adjusted["survival"] *= 1.5
            adjusted["mobility"] *= 1.3
            adjusted["food"] *= 0.5
            adjusted["food_safety"] *= 1.3
            adjusted["territory"] *= 1.2
            adjusted["lookahead"] *= 1.3
            adjusted["two_ply"] *= 1.3
            adjusted["bottleneck"] *= 1.4
            adjusted["opponent_pressure"] *= 0.8

        elif mode == "aggressive":
            adjusted["food"] *= 1.8
            adjusted["food_race"] *= 1.4
            adjusted["food_safety"] *= 0.8
            adjusted["space"] *= 0.8
            adjusted["territory"] *= 0.8
            adjusted["enemy_risk"] *= 0.7
            adjusted["lookahead"] *= 0.8
            adjusted["two_ply"] *= 0.9
            adjusted["bottleneck"] *= 0.8
            adjusted["opponent_pressure"] *= 1.4

        self._apply_opponent_profile(
            adjusted
        )

        adjusted["total"] = (
            adjusted["space"]
            + adjusted["survival"]
            + adjusted["food"]
            + adjusted["food_race"]
            + adjusted["food_safety"]
            + adjusted["mobility"]
            + adjusted["territory"]
            + adjusted["enemy_risk"]
            + adjusted["lookahead"]
            + adjusted["bottleneck"]
            + adjusted["opponent_pressure"]
            + adjusted["two_ply"]
        )

        return adjusted

    def print_analysis(self) -> None:
        print(
            f"\n--- ANÁLISIS DE MOVIMIENTOS "
            f"| MODO: {self.current_mode.upper()} "
            f"| RIVAL: {self.current_opponent_profile.upper()} ---"
        )

        for direction, analysis in self.last_analysis.items():
            print(
                f"{direction.upper():>5} | "
                f"espacio={analysis['space']:>7.0f} | "
                f"supervivencia={analysis['survival']:>7.0f} | "
                f"comida={analysis['food']:>7.0f} | "
                f"carrera={analysis['food_race']:>7.0f} | "
                f"seg_comida={analysis['food_safety']:>7.0f} | "
                f"movilidad={analysis['mobility']:>7.0f} | "
                f"territorio={analysis['territory']:>7.0f} | "
                f"rival={analysis['enemy_risk']:>7.0f} | "
                f"futuro={analysis['lookahead']:>7.0f} | "
                f"presión={analysis['opponent_pressure']:>7.0f} | "
                f"2ply={analysis.get('two_ply', 0):>7.0f} | "
                f"cuello={analysis['bottleneck']:>7.0f} | "
                f"TOTAL={analysis['total']:>9.0f}"
            )

        print("---------------------------------------------\n")


    def set_opponent(
        self,
        opponent: str | None,
    ) -> None:
        self.current_opponent = opponent

        self.opponent_model.set_opponent(
            opponent
        )

        if (
            opponent is not None
            and self.opponent_profile is not None
        ):
            self.current_opponent_profile = (
                self.opponent_profile.classify(
                    opponent
                )
            )
        else:
            self.current_opponent_profile = "unknown"

    def _apply_opponent_profile(
        self,
        analysis: dict[str, float],
    ) -> None:
        """
        Ajusta suavemente el puntaje según el estilo
        histórico del rival.
        """

        profile = self.current_opponent_profile

        if profile == "food_hunter":
            # Disputará comida con frecuencia.
            analysis["food_race"] *= 1.25
            analysis["lookahead"] *= 1.15

        elif profile == "aggressive":
            # Puede intentar acercarse y encerrarnos.
            analysis["space"] *= 1.10
            analysis["enemy_risk"] *= 1.30
            analysis["lookahead"] *= 1.20

        elif profile == "defensive":
            # Podemos priorizar más comida y presión.
            analysis["food"] *= 1.15
            analysis["opponent_pressure"] *= 1.20


    def _is_critical_position(
        self,
        board: GameBoard,
        side: str,
        remaining_moves: int | None,
        my_score: int,
        enemy_score: int,
        candidates: list[tuple[str, float]],
    ) -> bool:
        """
        Determina si vale la pena invertir más cálculo
        en la posición actual.
        """

        if remaining_moves is not None:
            if remaining_moves <= self.weight_config.CRITICAL_REMAINING_MOVES:
                return True

        score_difference = my_score - enemy_score

        if score_difference <= self.weight_config.CRITICAL_SCORE_DEFICIT:
            return True

        if len(candidates) >= 2:
            gap = abs(
                candidates[0][1]
                - candidates[1][1]
            )

            if gap <= self.weight_config.CRITICAL_SEARCH_GAP:
                return True

        my_head = board.my_head(side)
        enemy_head = board.enemy_head(side)

        head_distance = (
            abs(my_head[0] - enemy_head[0])
            + abs(my_head[1] - enemy_head[1])
        )

        if head_distance <= self.weight_config.CRITICAL_HEAD_DISTANCE:
            return True

        for food in board.food:
            food_distance = (
                abs(my_head[0] - food[0])
                + abs(my_head[1] - food[1])
            )

            if food_distance <= 2:
                return True

        return False


    def _deep_search_candidates(
        self,
        board: GameBoard,
        side: str,
        candidates: list[tuple[str, float]],
    ) -> None:
        """
        Refuerza el análisis futuro de los dos mejores
        movimientos cuando la posición es crítica.
        """

        for direction, _ in candidates[:2]:
            extra_future_score = (
                self.two_ply.score(
                    board,
                    side,
                    direction,
                )
                * self.weight_config.DEEP_TWO_PLY_WEIGHT
            )

            self.last_analysis[
                direction
            ]["two_ply"] += extra_future_score
