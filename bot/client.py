import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import websockets
import time

from ai.opponent_memory import OpponentMemory
from ai.opponent_observer import OpponentObserver
from ai.strategy import SnakeStrategy
from bot.game_recorder import GameRecorder
from bot.visualizer import LiveVisualizer
from config import SERVER_URI
from game.board import GameBoard


class BotClient:
    """
    Cliente encargado de comunicarse con el servidor,
    jugar y aprender del comportamiento de los rivales.
    """

    def __init__(
        self,
        token: str,
        decision_workers: int = 2,
        background_workers: int = 4,
        max_pending_events: int = 256,
    ) -> None:
        self.token = token

        self.opponent_memory = OpponentMemory()

        # Cada partida necesita su propia estrategia: el perfil del rival y el
        # último análisis son estado mutable y no deben mezclarse entre juegos.
        self.strategies: dict[str, SnakeStrategy] = {}
        self.game_locks: dict[str, asyncio.Lock] = {}
        self.event_tasks: set[asyncio.Task] = set()
        self.send_lock = asyncio.Lock()
        # choose_move es CPU-bound en Python. Un pool pequeño mantiene el
        # event loop receptivo y evita que decenas de threads compitan por el
        # GIL, lo que empeora la latencia media en ráfagas grandes.
        self.decision_executor = ThreadPoolExecutor(
            max_workers=max(1, decision_workers),
            thread_name_prefix="snake-decision",
        )
        self.background_executor = ThreadPoolExecutor(
            max_workers=max(1, background_workers),
            thread_name_prefix="snake-background",
        )
        self.event_slots = asyncio.Semaphore(max(1, max_pending_events))

        self.recorder = GameRecorder()
        self.opponent_observer = OpponentObserver()
        self.visualizer = LiveVisualizer()

        # Guardamos información separada por partida.
        self.previous_boards: dict[str, GameBoard] = {}
        self.opponents: dict[str, str] = {}

        self.enemy_predictions: dict[
            str,
            str
        ] = {}

    def start(self) -> None:
        print("Iniciando Snake Bot...")
        self.visualizer.start()

        try:
            asyncio.run(self.connect_forever())
        except KeyboardInterrupt:
            print("\nBot detenido.")

    async def connect_forever(self) -> None:
        uri = self._websocket_uri()

        while True:
            try:
                print(f"Conectando a: {SERVER_URI}")

                async with websockets.connect(uri) as websocket:
                    print("Conexión establecida correctamente.")
                    await self.listen(websocket)

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(f"Error de conexión: {error}")
                print("Reintentando en 3 segundos...")
                await asyncio.sleep(3)

    def _websocket_uri(self) -> str:
        return f"{SERVER_URI}?token={self.token}"

    async def listen(self, websocket: Any) -> None:
        try:
            async for raw_message in websocket:
                try:
                    event = json.loads(raw_message)
                except json.JSONDecodeError:
                    print(f"Mensaje JSON inválido: {raw_message}")
                    continue

                # Los cálculos de distintas partidas se despachan sin bloquear
                # la recepción de nuevos eventos del websocket.
                if event.get("event") in ("your_turn", "game_over"):
                    task = asyncio.create_task(
                        self._handle_event_safely(websocket, event)
                    )
                    self.event_tasks.add(task)
                    task.add_done_callback(self.event_tasks.discard)
                else:
                    await self._handle_event_safely(websocket, event)
        finally:
            if self.event_tasks:
                await asyncio.gather(
                    *tuple(self.event_tasks),
                    return_exceptions=True,
                )

    async def _handle_event_safely(
        self,
        websocket: Any,
        event: dict,
    ) -> None:
        async with self.event_slots:
            try:
                await self.handle_event(websocket, event)
            except Exception as error:
                print(f"Error procesando evento: {error}")

    async def handle_event(
        self,
        websocket: Any,
        event: dict,
    ) -> None:
        event_type = event.get("event")
        data = event.get("data", {})

        print(f"\nEVENTO RECIBIDO COMPLETO:")
        print(json.dumps(event, indent=2, ensure_ascii=False))

        if event_type in (
            "list_users",
            "update_user_list",
        ):
            self.show_users(data)

        elif event_type == "challenge":
            await self.accept_challenge(
                websocket,
                data,
            )

        elif event_type == "your_turn":
            await self.process_turn(
                websocket,
                data,
            )

        elif event_type == "game_over":
            await self.process_game_over(data)

        elif event_type == "error":
            print(
                f"Error del servidor: {data}"
            )

        else:
            print(
                f"Evento desconocido: {event}"
            )

    def show_users(
        self,
        data: dict,
    ) -> None:
        users = data.get(
            "users",
            [],
        )

        print("Usuarios conectados:")

        for user in users:
            print(f"- {user}")

    async def accept_challenge(
        self,
        websocket: Any,
        data: dict,
    ) -> None:
        challenge_id = data.get(
            "challenge_id"
        )

        opponent = data.get(
            "opponent",
            "desconocido",
        )

        if not challenge_id:
            print(
                "El desafío no contiene "
                "challenge_id."
            )
            return

        action = {
            "action": "accept_challenge",
            "data": {
                "challenge_id": challenge_id,
            },
        }

        await self.send(
            websocket,
            action,
        )

        print(
            f"Desafío aceptado contra "
            f"{opponent}."
        )

    async def process_turn(
        self,
        websocket: Any,
        data: dict,
    ) -> None:
        game_id = data.get("game_id")

        if not game_id:
            print("El evento your_turn no contiene game_id.")
            return

        game_lock = self.game_locks.setdefault(
            game_id,
            asyncio.Lock(),
        )

        async with game_lock:
            await self._process_turn_locked(websocket, data)

    async def _process_turn_locked(
        self,
        websocket: Any,
        data: dict,
    ) -> None:
        turn_start = time.perf_counter()

        print("\n>>> PROCESS_TURN EJECUTADO")
        print(f"game_id recibido: {data.get('game_id')}")
        print(f"side recibido: {data.get('side')}")
        print(f"turn_token recibido: {data.get('turn_token')}")

        board_text = data.get("board")
        side = data.get("side")
        game_id = data.get("game_id")
        turn_token = data.get("turn_token")

        if not all(
            (
                board_text,
                side,
                game_id,
                turn_token,
            )
        ):
            print(
                "El evento your_turn está incompleto."
            )
            return

        board = GameBoard(board_text)

        opponent = self._get_opponent(
            data,
            side,
        )

        if opponent:
            self.opponents[game_id] = opponent

        strategy = self.strategies.get(game_id)

        if strategy is None:
            strategy = SnakeStrategy(opponent_memory=self.opponent_memory)
            self.strategies[game_id] = strategy

        strategy.set_opponent(opponent)

        previous_board = self.previous_boards.get(
            game_id
        )

        remaining_moves = data.get(
            "remaining_moves"
        )

        if side == "A":
            my_score = data.get(
                "score_1",
                0,
            )

            enemy_score = data.get(
                "score_2",
                0,
            )

        else:
            my_score = data.get(
                "score_2",
                0,
            )

            enemy_score = data.get(
                "score_1",
                0,
            )

        decision_start = time.perf_counter()

        try:
            direction = await asyncio.get_running_loop().run_in_executor(
                self.decision_executor,
                strategy.choose_move,
                board,
                side,
                remaining_moves,
                my_score,
                enemy_score,
            )
        except Exception as error:
            # Una estrategia compleja nunca debe costarnos un timeout. Si el
            # análisis falla, enviamos de inmediato el primer movimiento que
            # el tablero actual considera legal.
            legal_moves = [
                direction
                for direction, is_legal in board.valid_moves(side).items()
                if is_legal
            ]

            direction = legal_moves[0] if legal_moves else "up"
            strategy.last_analysis = {}

            print(
                "La estrategia falló; usando movimiento seguro "
                f"{direction}: {error}"
            )

        decision_time = (
            time.perf_counter()
            - decision_start
        )

        action = {
            "action": "move",
            "data": {
                "game_id": game_id,
                "turn_token": turn_token,
                "direction": direction,
            },
        }

        await self.send(
            websocket,
            action,
        )

        send_time = (
            time.perf_counter()
            - turn_start
        )

        print(
            f"Movimiento enviado: {direction} "
            f"| decisión: "
            f"{decision_time * 1000:.2f} ms "
            f"| total hasta envío: "
            f"{send_time * 1000:.2f} ms"
        )

        await asyncio.get_running_loop().run_in_executor(
            self.background_executor,
            self._post_process_turn,
            data,
            board,
            previous_board,
            opponent,
            strategy,
            direction,
            decision_time,
        )

    def _post_process_turn(
        self,
        data: dict,
        board: GameBoard,
        previous_board: GameBoard | None,
        opponent: str | None,
        strategy: SnakeStrategy,
        direction: str,
        decision_time: float,
    ) -> None:
        game_id = data["game_id"]
        side = data["side"]
        self.visualizer.publish({
            **data,
            "status": "playing",
            "direction": direction,
            "decision_ms": decision_time * 1000,
        })

        if strategy.last_enemy_prediction:
            self.enemy_predictions[
                game_id
            ] = (
                strategy.last_enemy_prediction
            )

        if (
            previous_board is not None
            and opponent
        ):
            self._observe_opponent(
                game_id=game_id,
                previous_board=previous_board,
                current_board=board,
                side=side,
                opponent=opponent,
            )

        print(
            f">>> GUARDANDO TURNO "
            f"| game_id={game_id} "
            f"| dirección={direction}"
        )

        self.recorder.record_turn(
            game_id=game_id,
            data=data,
            direction=direction,
            analysis=strategy.last_analysis,
            mode=getattr(strategy, "current_mode", None),
        )

        self.previous_boards[
            game_id
        ] = board

        strategy.print_analysis()

    def _observe_opponent(
        self,
        game_id: str,
        previous_board: GameBoard,
        current_board: GameBoard,
        side: str,
        opponent: str,
    ) -> None:
        direction = (
            self.opponent_observer.infer_direction(
                previous_board,
                current_board,
                side,
            )
        )

        if direction is None:
            return

        predicted_direction = (
            self.enemy_predictions.get(
                game_id
            )
        )

        if predicted_direction is not None:
            self.opponent_memory.record_prediction(
                opponent=opponent,
                predicted_direction=predicted_direction,
                actual_direction=direction,
            )

            accuracy = (
                self.opponent_memory.prediction_accuracy(
                    opponent
                )
            )

            print(
                f"Predicción rival: "
                f"{predicted_direction} "
                f"| real: {direction} "
                f"| precisión histórica: "
                f"{accuracy:.1%}"
            )

        moved_toward_food = (
            self.opponent_observer.moved_toward_food(
                previous_board,
                current_board,
                side,
            )
        )

        moved_toward_us = (
            self.opponent_observer.moved_toward_us(
                previous_board,
                current_board,
                side,
            )
        )

        contested_food = (
            self.opponent_observer.contested_food(
                previous_board,
                current_board,
                side,
            )
        )

        self.opponent_memory.record_move(
            opponent=opponent,
            direction=direction,
            moved_toward_food=moved_toward_food,
            moved_toward_us=moved_toward_us,
            contested_food=contested_food,
        )

        print(
            f"Rival observado: {direction} "
            f"| comida={moved_toward_food} "
            f"| presión={moved_toward_us} "
            f"| disputa={contested_food}"
        )

    async def process_game_over(
        self,
        data: dict,
    ) -> None:
        game_id = data.get(
            "game_id"
        )

        if not game_id:
            self._finish_game(data)
            return

        game_lock = self.game_locks.setdefault(
            game_id,
            asyncio.Lock(),
        )

        async with game_lock:
            await asyncio.get_running_loop().run_in_executor(
                self.background_executor,
                self._finish_game,
                data,
            )
            self._cleanup_game(game_id)

    def _finish_game(
        self,
        data: dict,
    ) -> None:
        game_id = data.get("game_id")

        player_1 = data.get(
            "player_1"
        )

        player_2 = data.get(
            "player_2"
        )

        score_1 = data.get(
            "score_1"
        )

        score_2 = data.get(
            "score_2"
        )

        winner = data.get(
            "winner"
        )

        print("Partida terminada.")
        self.visualizer.publish({
            **data,
            "status": "finished",
        })
        print(
            f"{player_1}: {score_1}"
        )
        print(
            f"{player_2}: {score_2}"
        )
        print(
            f"Ganador: {winner}"
        )

        if game_id:
            file_path = (
                self.recorder.finish_game(
                    game_id,
                    data,
                )
            )

            print(
                f"Partida guardada en: "
                f"{file_path}"
            )

            opponent = self.opponents.get(
                game_id
            )

            if opponent:
                won = (
                    winner is not None
                    and winner != opponent
                )

                self.opponent_memory.record_game(
                    opponent=opponent,
                    won=won,
                )

    def _cleanup_game(self, game_id: str) -> None:
        self.previous_boards.pop(game_id, None)
        self.opponents.pop(game_id, None)
        self.enemy_predictions.pop(game_id, None)
        self.strategies.pop(game_id, None)
        self.game_locks.pop(game_id, None)

    def _get_opponent(
        self,
        data: dict,
        side: str,
    ) -> str | None:
        """
        A corresponde a player_1 y
        B corresponde a player_2.
        """
        if side == "A":
            return data.get(
                "player_2"
            )

        return data.get(
            "player_1"
        )

    async def send(
        self,
        websocket: Any,
        message: dict,
    ) -> None:
        raw_message = json.dumps(
            message
        )

        async with self.send_lock:
            await websocket.send(raw_message)

        print(
            f"> {raw_message}"
        )
