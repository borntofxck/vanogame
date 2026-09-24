"""Полиморфное поведение врагов. Модуль не зависит от Pygame."""
from __future__ import annotations

from abc import ABC, abstractmethod
import math

from . import config
from .geometry import AABB
from .pathfinding import Cell, NavigationGrid, astar, manhattan
from .physics import Body, SpatialGrid, move_body

PATROL_WIDTH, PATROL_HEIGHT = config.PATROL_WIDTH, config.PATROL_HEIGHT
DRONE_WIDTH, DRONE_HEIGHT = config.DRONE_WIDTH, config.DRONE_HEIGHT
EDGE_PROBE_DEPTH = 4.0
WAYPOINT_EPSILON = 1e-6
TARGET_CELL_CHANGE = 3


class Enemy(ABC):
    """Общий жизненный цикл, но физику задаёт конкретное поведение."""

    kind: str

    def __init__(self, identifier: str, box: AABB):
        self.id = identifier
        self.box = box.copy()
        self._spawn = box.copy()
        self.facing = 1
        self.age = 0.0
        self.state = "Патруль"

    def update(self, dt: float, player_box: AABB,
               grid: SpatialGrid) -> list[str]:
        if dt <= 0:
            return []
        self.age += dt
        return self.update_behavior(dt, player_box, grid)

    @abstractmethod
    def update_behavior(self, dt: float, player_box: AABB,
                        grid: SpatialGrid) -> list[str]:
        """Обновить поведение и вернуть события для представления."""

    def reset(self) -> None:
        self.box = self._spawn.copy()
        self.facing = 1
        self.age = 0.0
        self.state = "Патруль"


class PatrolEnemy(Enemy):
    kind = "patrol"

    def __init__(self, identifier: str, box: AABB,
                 left: float, right: float):
        super().__init__(identifier, box)
        self.left, self.right = left, right
        self.body = Body(self.box)

    def reset(self) -> None:
        super().reset()
        self.body = Body(self.box)

    def update_behavior(self, dt: float, player_box: AABB,
                        grid: SpatialGrid) -> list[str]:
        # Гравитация применяется отдельно: она не нужна летающему подклассу.
        self.body.vy = min(config.MAX_FALL_SPEED, self.body.vy + config.GRAVITY * dt)
        move_body(self.body, 0.0, self.body.vy * dt, grid)
        distance = config.PATROL_SPEED * dt
        front = (self.box.right + distance if self.facing > 0
                 else self.box.left - distance)
        foot = AABB(front - 1.0, self.box.bottom, 2.0, EDGE_PROBE_DEPTH)
        has_floor = any(foot.intersects(wall) for wall in grid.query(foot))
        proposed = self.box.moved(distance * self.facing, 0)
        wall_ahead = any(proposed.intersects(wall) for wall in grid.query(proposed))
        beyond_patrol = proposed.left < self.left or proposed.right > self.right
        if self.body.grounded and (not has_floor or wall_ahead or beyond_patrol):
            self.facing *= -1
        if self.body.grounded:
            self.body.vx = config.PATROL_SPEED * self.facing
            move_body(self.body, self.body.vx * dt, 0.0, grid)
        self.body.facing = self.facing
        return []


class DroneEnemy(Enemy):
    kind = "drone"
    PATROL = "Патруль"
    CHASE = "Погоня"
    RETURN = "Возвращение"

    def __init__(self, identifier: str, box: AABB, route: list[tuple[float, float]],
                 solids: list[AABB], width: int, height: int):
        super().__init__(identifier, box)
        self.nav = NavigationGrid(width, height, solids, config.NAV_CELL,
                                  (box.w, box.h))
        spawn_cell = self.nav.nearest_free(box.center)
        if spawn_cell is not None:
            self.box = self.nav.agent_box(self.nav.cell_center(spawn_cell))
            self._spawn = self.box.copy()
        self.route = list(route) if route else [self.box.center]
        self.path: list[Cell] = []
        self.expanded = 0
        self._route_index = 0
        self._repath_timer = 0.0
        self._last_goal_cell: Cell | None = None
        self._goal_cell: Cell | None = None

    def reset(self) -> None:
        super().reset()
        self.path.clear()
        self.expanded = 0
        self._route_index = 0
        self._repath_timer = 0.0
        self._last_goal_cell = None
        self._goal_cell = None

    def _change_state(self, state: str) -> None:
        self.state = state
        self._repath_timer = 0.0
        self._last_goal_cell = None
        # Текущий отрезок остаётся: поворот выполняется в его безопасном конце.

    def update_behavior(self, dt: float, player_box: AABB,
                        grid: SpatialGrid) -> list[str]:
        distance = math.dist(self.box.center, player_box.center)
        events: list[str] = []
        if self.state != self.CHASE and distance <= config.DRONE_DETECT:
            self._change_state(self.CHASE)
            events.append("detected")
        elif self.state == self.CHASE and distance >= config.DRONE_LOSE:
            self._change_state(self.RETURN)
        if self.state == self.CHASE:
            target = player_box.center
        else:
            target = self.route[self._route_index]
        self._repath_timer -= dt
        target_cell = self.nav.world_to_cell(target)
        changed = (self._last_goal_cell is not None
                   and manhattan(target_cell, self._last_goal_cell) >= TARGET_CELL_CHANGE)
        if self._repath_timer <= 0.0 or changed:
            self._find_path(target)
            self._repath_timer = config.DRONE_REPATH
            self._last_goal_cell = target_cell
        self._follow_path(config.DRONE_SPEED * dt, grid)
        reached_goal = self._goal_cell is not None and math.dist(
            self.box.center, self.nav.cell_center(self._goal_cell)) <= WAYPOINT_EPSILON
        if not self.path and self.state != self.CHASE and reached_goal:
            if self.state == self.RETURN:
                self._change_state(self.PATROL)
            self._route_index = (self._route_index + 1) % len(self.route)
            self._repath_timer = 0.0
        return events

    def _find_path(self, target: tuple[float, float]) -> None:
        # Пересчёт посреди ребра сохраняет его конечную клетку. Иначе округление
        # позиции могло бы срезать угол при смене направления возле стены.
        start = self.path[0] if self.path else self.nav.world_to_cell(self.box.center)
        goal = self.nav.reachable_target(start, target)
        self._goal_cell = goal
        if goal is None:
            self.path = []
            self.expanded = 0
            return
        result = astar(self.nav, start, goal)
        self.path = result.path
        self.expanded = result.expanded

    def _follow_path(self, distance: float, grid: SpatialGrid) -> None:
        while self.path and distance > WAYPOINT_EPSILON:
            target_x, target_y = self.nav.cell_center(self.path[0])
            x, y = self.box.center
            dx, dy = target_x - x, target_y - y
            length = math.hypot(dx, dy)
            if length <= WAYPOINT_EPSILON:
                self.path.pop(0)
                continue
            amount = min(distance, length)
            move_x, move_y = dx / length * amount, dy / length * amount
            proposed = self.box.moved(move_x, move_y)
            sweep = AABB(min(self.box.x, proposed.x), min(self.box.y, proposed.y),
                         self.box.w + abs(move_x), self.box.h + abs(move_y))
            # Проверка по spatial grid защищает физические стены и при большом dt.
            if any(sweep.intersects(wall) for wall in grid.query(sweep)):
                self.path.clear()
                self._repath_timer = config.DRONE_REPATH
                return
            self.box.x, self.box.y = proposed.x, proposed.y
            if abs(move_x) > WAYPOINT_EPSILON:
                self.facing = 1 if move_x > 0 else -1
            distance -= amount
            if amount >= length - WAYPOINT_EPSILON:
                self.path.pop(0)


def build_enemy(spec: dict, solids: list[AABB], width: int, height: int) -> Enemy:
    """Выбор класса только при создании. Игровой цикл вызывает общий update."""
    if spec["kind"] == "patrol":
        return PatrolEnemy(spec["id"],
                           AABB(spec["x"], spec["y"], PATROL_WIDTH, PATROL_HEIGHT),
                           spec["left"], spec["right"])
    if spec["kind"] == "drone":
        return DroneEnemy(spec["id"],
                          AABB(spec["x"], spec["y"], DRONE_WIDTH, DRONE_HEIGHT),
                          [tuple(point) for point in spec.get("route", [])],
                          solids, width, height)
    raise ValueError(f"Неизвестный вид врага: {spec['kind']}")
