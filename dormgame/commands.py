"""Снимок ввода одного шага. Pressed — фронт, held — состояние кнопки."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Commands:
    move: int = 0
    jump_pressed: bool = False
    jump_held: bool = False
    interact: bool = False
    reset: bool = False
