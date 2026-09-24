"""Фиксированный шаг и накопитель фронтов ввода, без зависимости от Pygame."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable

from .commands import Commands
from .config import FIXED_DT, MAX_FRAME_TIME, MAX_STEPS


class InputBuffer:
    """Нажатие и отпускание живут до своего шага, даже при кадре без update.

    Очередь сохраняет и очень короткий прыжок между двумя шагами: сначала
    симуляция увидит нажатие, на следующем шаге — отпускание. Удержание само
    по себе никогда не создаёт новый фронт.
    """

    def __init__(self) -> None:
        self.move = 0
        self.held = False
        self._simulated_held = False
        self._jump_edges: deque[bool] = deque()
        self._interact = False
        self._reset = False

    def jump(self, pressed: bool) -> None:
        if pressed != self.held:
            self.held = pressed
            self._jump_edges.append(pressed)

    def interact(self) -> None:
        self._interact = True

    def reset_checkpoint(self) -> None:
        self._reset = True

    def consume(self) -> Commands:
        pressed = False
        if self._jump_edges:
            self._simulated_held = self._jump_edges.popleft()
            pressed = self._simulated_held
        command = Commands(self.move, pressed, self._simulated_held,
                           self._interact, self._reset)
        self._interact = self._reset = False
        return command

    def clear(self) -> None:
        self.move = 0
        self.held = self._simulated_held = False
        self._jump_edges.clear()
        self._interact = self._reset = False


class FixedStepper:
    """Отбрасывает избыток после подвисания; пауза обнуляет аккумулятор."""

    def __init__(self, dt: float = FIXED_DT, max_steps: int = MAX_STEPS) -> None:
        self.dt = dt
        self.max_steps = max_steps
        self.accumulator = 0.0
        self.steps = 0

    def clear(self) -> None:
        self.accumulator = 0.0
        self.steps = 0

    def advance(self, frame_dt: float, update: Callable[[float], object],
                paused: bool = False) -> int:
        self.steps = 0
        if paused:
            self.clear()
            return 0
        self.accumulator += max(0.0, min(frame_dt, MAX_FRAME_TIME))
        while self.accumulator + 1e-12 >= self.dt and self.steps < self.max_steps:
            self.accumulator -= self.dt
            self.steps += 1
            if update(self.dt) is False:
                self.accumulator = 0.0
                break
        if self.steps == self.max_steps:
            self.accumulator = min(self.accumulator, self.dt)
        return self.steps
