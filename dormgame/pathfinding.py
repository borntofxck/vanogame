"""Четырёхсвязная навигация дрона и самостоятельный алгоритм A*.

Здесь нет графики и перемещения сущностей. Сетка строится для центра
прямоугольного агента: проверяются и клетки, и весь отрезок между ними.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
import itertools
import math
from typing import Iterable, Protocol

from .geometry import AABB

Cell = tuple[int, int]
DIRECTIONS: tuple[Cell, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


class SearchGrid(Protocol):
    def is_walkable(self, cell: Cell) -> bool: ...

    def neighbors(self, cell: Cell) -> Iterable[Cell]: ...


@dataclass
class SearchResult:
    path: list[Cell]
    expanded: int

    @property
    def cost(self) -> int | None:
        return len(self.path) - 1 if self.path else None


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(grid: SearchGrid, start: Cell, goal: Cell) -> SearchResult:
    """Кратчайший путь, включая начало и конец; [] означает отсутствие пути.

    В heapq нет decrease-key: улучшение добавляет новую запись. Старая
    запись отбрасывается сравнением её g с актуальным g_score, до раскрытия.
    Манхэттенская оценка согласована для четырёх направлений с ценой 1.
    """
    if not grid.is_walkable(start) or not grid.is_walkable(goal):
        return SearchResult([], 0)
    serial = itertools.count()
    queue: list[tuple[int, int, int, Cell]] = [
        (manhattan(start, goal), 0, next(serial), start)
    ]
    g_score: dict[Cell, int] = {start: 0}
    came_from: dict[Cell, Cell] = {}
    expanded = 0
    while queue:
        _, queued_g, _, current = heapq.heappop(queue)
        if queued_g != g_score.get(current):
            continue
        expanded += 1
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return SearchResult(path, expanded)
        for neighbor in grid.neighbors(current):
            candidate_g = queued_g + 1
            if candidate_g < g_score.get(neighbor, math.inf):
                came_from[neighbor] = current
                g_score[neighbor] = candidate_g
                heapq.heappush(queue, (
                    candidate_g + manhattan(neighbor, goal), candidate_g,
                    next(serial), neighbor,
                ))
    return SearchResult([], expanded)


class NavigationGrid:
    """Неизменяемая после построения сетка для статических стен.

    Движущиеся платформы — решётчатые грузовые лифты. Они поддерживают
    наземных персонажей, но дрон пролетает сквозь них. Поэтому их здесь нет.
    Компоненты связности позволяют выбрать достижимую точку приближения,
    даже когда игрок находится в слишком узком проходе или за глухой стеной.
    """

    def __init__(self, width: int, height: int, solids: list[AABB],
                 cell_size: int = 16, agent_size: tuple[float, float] = (18, 14)):
        if width <= 0 or height <= 0 or cell_size <= 0 or min(agent_size) <= 0:
            raise ValueError("Размеры сетки и агента должны быть положительными")
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.cols = math.ceil(width / cell_size)
        self.rows = math.ceil(height / cell_size)
        self.agent_size = agent_size
        self.solids = tuple(box.copy() for box in solids)
        self.walkable: set[Cell] = set()
        self.adjacency: dict[Cell, tuple[Cell, ...]] = {}
        self.components: dict[Cell, int] = {}
        self.component_cells: list[list[Cell]] = []
        # Это однократное построение, а не перебор стен на каждом шаге.
        for row in range(self.rows):
            for col in range(self.cols):
                cell = (col, row)
                box = self.agent_box(self.cell_center(cell))
                if (box.left >= 0 and box.top >= 0
                        and box.right <= width and box.bottom <= height
                        and not any(box.intersects(wall) for wall in self.solids)):
                    self.walkable.add(cell)
        for cell in sorted(self.walkable):
            linked = []
            for dx, dy in DIRECTIONS:
                neighbor = (cell[0] + dx, cell[1] + dy)
                if neighbor in self.walkable and self.segment_clear(
                        self.cell_center(cell), self.cell_center(neighbor)):
                    linked.append(neighbor)
            self.adjacency[cell] = tuple(linked)
        for cell in sorted(self.walkable):
            if cell in self.components:
                continue
            component = len(self.component_cells)
            cells = []
            queue = deque([cell])
            self.components[cell] = component
            while queue:
                current = queue.popleft()
                cells.append(current)
                for neighbor in self.neighbors(current):
                    if neighbor not in self.components:
                        self.components[neighbor] = component
                        queue.append(neighbor)
            self.component_cells.append(cells)

    def cell_center(self, cell: Cell) -> tuple[float, float]:
        return ((cell[0] + 0.5) * self.cell_size,
                (cell[1] + 0.5) * self.cell_size)

    def world_to_cell(self, point: tuple[float, float]) -> Cell:
        return (math.floor(point[0] / self.cell_size),
                math.floor(point[1] / self.cell_size))

    def agent_box(self, point: tuple[float, float]) -> AABB:
        w, h = self.agent_size
        return AABB(point[0] - w / 2, point[1] - h / 2, w, h)

    def segment_clear(self, start: tuple[float, float],
                      end: tuple[float, float]) -> bool:
        """Проверка всего объёма при осевом движении, включая тонкие стены.

        Для диагонали bounding box был бы консервативным приближением;
        навигационные рёбра всегда строго горизонтальны или вертикальны.
        """
        a, b = self.agent_box(start), self.agent_box(end)
        sweep = AABB(min(a.x, b.x), min(a.y, b.y),
                     abs(a.x - b.x) + a.w, abs(a.y - b.y) + a.h)
        return (sweep.left >= 0 and sweep.top >= 0
                and sweep.right <= self.width and sweep.bottom <= self.height
                and not any(sweep.intersects(wall) for wall in self.solids))

    def is_walkable(self, cell: Cell) -> bool:
        return cell in self.walkable

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return self.adjacency.get(cell, ())

    def nearest_free(self, point: tuple[float, float],
                     component: int | None = None) -> Cell | None:
        candidates = (self.component_cells[component] if component is not None
                      else self.walkable)
        # Равные расстояния разрешаются координатами, без случайности множества.
        return min(candidates, key=lambda cell: (
            (self.cell_center(cell)[0] - point[0]) ** 2
            + (self.cell_center(cell)[1] - point[1]) ** 2,
            cell,
        ), default=None)

    def reachable_target(self, start: Cell,
                         point: tuple[float, float]) -> Cell | None:
        component = self.components.get(start)
        if component is None:
            return None
        goal = self.world_to_cell(point)
        if self.components.get(goal) == component:
            return goal
        # Ближайший к игроку центр в компоненте дрона. Это O(V_component)
        # только при пересчёте маршрута, с гарантией существования пути.
        return self.nearest_free(point, component)
