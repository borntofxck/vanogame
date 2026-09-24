"""Маленькая геометрия без зависимости от графической библиотеки."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class AABB:
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2

    def intersects(self, other: AABB) -> bool:
        return (self.left < other.right and self.right > other.left
                and self.top < other.bottom and self.bottom > other.top)

    def moved(self, dx: float, dy: float) -> AABB:
        return AABB(self.x + dx, self.y + dy, self.w, self.h)

    def expanded(self, margin: float) -> AABB:
        return AABB(self.x - margin, self.y - margin,
                    self.w + 2 * margin, self.h + 2 * margin)

    def copy(self) -> AABB:
        return AABB(self.x, self.y, self.w, self.h)
