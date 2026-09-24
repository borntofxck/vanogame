"""Дробная AABB-физика, статическая сетка и кинематические платформы.

Движение разбивается на короткие отрезки, на каждом сначала разрешается X,
затем Y. Проверяется пересечённый промежуток, а не только конечная позиция:
даже тонкая плита не теряется между двумя положениями тела.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, hypot

from . import config
from .commands import Commands
from .geometry import AABB

EPSILON = 1e-7
GROUND_PROBE = 0.02


class SpatialGrid:
    """Индекс неизменяемых стен; query возвращает кандидатов без дубликатов.

    Запрос стоит O(C + K), где C — число посещённых клеток, K — число
    прочитанных ссылок на коллайдеры в этих клетках (включая дубликаты).
    Стены после создания сетки перемещать нельзя; платформы передаются отдельно.
    """

    def __init__(self, solids: list[AABB], cell_size: float = config.TILE_SIZE):
        if cell_size <= 0:
            raise ValueError("Размер клетки должен быть положительным")
        self.solids = list(solids)
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], list[int]] = {}
        for index, box in enumerate(self.solids):
            for cell in self._occupied_cells(box):
                self._cells.setdefault(cell, []).append(index)

    def _occupied_cells(self, box: AABB):
        if box.w <= 0 or box.h <= 0:
            return
        left, top = floor(box.left / self.cell_size), floor(box.top / self.cell_size)
        right = ceil(box.right / self.cell_size) - 1
        bottom = ceil(box.bottom / self.cell_size) - 1
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                yield column, row

    def query(self, box: AABB) -> list[AABB]:
        indices: set[int] = set()
        candidates: list[AABB] = []
        for cell in self._occupied_cells(box):
            for index in self._cells.get(cell, ()):
                if index not in indices:
                    indices.add(index)
                    candidates.append(self.solids[index])
        return candidates


@dataclass
class Body:
    box: AABB
    vx: float = 0.0
    vy: float = 0.0
    grounded: bool = False
    support_id: str | None = None
    facing: int = 1


@dataclass
class PlayerBody(Body):
    coyote_timer: float = 0.0
    jump_buffer_timer: float = 0.0


@dataclass
class CollisionResult:
    hit_x: bool = False
    hit_y: bool = False
    landed: bool = False
    ceiling: bool = False


class MovingPlatform:
    """Платформа ходит от start к end и обратно с постоянной скоростью.

    end — координаты верхнего левого угла. dx/dy относятся к последнему шагу;
    мир обновляет все платформы до тел, поэтому пассажир знает их перенос.
    """

    def __init__(self, id: str, start: AABB, end: tuple[float, float], speed: float):
        if speed < 0 or start.w <= 0 or start.h <= 0:
            raise ValueError("Недопустимая скорость или размер платформы")
        self.id = id
        self.start = start.copy()
        self.end = end
        self.speed = speed
        self._length = hypot(end[0] - start.x, end[1] - start.y)
        self._phase = 0.0
        self.box = start.copy()
        self.dx = self.dy = 0.0

    def reset(self) -> None:
        self.box = self.start.copy()
        self._phase = 0.0
        self.dx = self.dy = 0.0

    def update(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("Отрицательный шаг времени")
        old_x, old_y = self.box.x, self.box.y
        if self._length > EPSILON:
            self._phase = (self._phase + self.speed * dt) % (2 * self._length)
            distance = min(self._phase, 2 * self._length - self._phase)
            fraction = distance / self._length
            self.box.x = self.start.x + (self.end[0] - self.start.x) * fraction
            self.box.y = self.start.y + (self.end[1] - self.start.y) * fraction
        self.dx, self.dy = self.box.x - old_x, self.box.y - old_y


def _overlap_x(a: AABB, b: AABB) -> bool:
    return a.left < b.right - EPSILON and a.right > b.left + EPSILON


def _overlap_y(a: AABB, b: AABB) -> bool:
    return a.top < b.bottom - EPSILON and a.bottom > b.top + EPSILON


def _move_axis(body: Body, distance: float, horizontal: bool,
               grid: SpatialGrid, extra: list[AABB]) -> bool:
    if abs(distance) < EPSILON:
        return False
    box = body.box
    sweep = AABB(min(box.x, box.x + (distance if horizontal else 0)),
                 min(box.y, box.y + (0 if horizontal else distance)),
                 box.w + (abs(distance) if horizontal else 0),
                 box.h + (0 if horizontal else abs(distance)))
    allowed = distance
    collided = False
    for obstacle in grid.query(sweep.expanded(EPSILON)) + extra:
        if horizontal:
            if not _overlap_y(box, obstacle):
                continue
            near = obstacle.left - box.right if distance > 0 else obstacle.right - box.left
        else:
            if not _overlap_x(box, obstacle):
                continue
            near = obstacle.top - box.bottom if distance > 0 else obstacle.bottom - box.top
        # Только поверхности перед телом: исходное зажатие обрабатывается
        # отдельно, а не чередованием непредсказуемых выталкиваний по осям.
        if distance > 0 and -EPSILON <= near <= allowed + EPSILON:
            allowed, collided = max(0.0, near), True
        elif distance < 0 and allowed - EPSILON <= near <= EPSILON:
            allowed, collided = min(0.0, near), True
    if horizontal:
        box.x += allowed
        if collided:
            body.vx = 0.0
    else:
        box.y += allowed
        if collided:
            body.vy = 0.0
    return collided


def move_body(body: Body, dx: float, dy: float, grid: SpatialGrid,
              extra: list[AABB] | None = None) -> CollisionResult:
    """Применить смещение без гравитации; вернуть контакты по обеим осям.

    Скорость обнуляется на заблокированной оси. grounded обновляется при
    вертикальном движении. extra — текущие прямоугольники движущихся платформ.
    """
    obstacles = extra if extra is not None else []
    result = CollisionResult()
    if abs(dy) > EPSILON:
        body.grounded = False
    steps = max(1, ceil(max(abs(dx), abs(dy)) / config.COLLISION_STEP))
    for _ in range(steps):
        if _move_axis(body, dx / steps, True, grid, obstacles):
            result.hit_x = True
        if _move_axis(body, dy / steps, False, grid, obstacles):
            result.hit_y = True
            if dy > 0:
                result.landed = True
                body.grounded = True
            else:
                result.ceiling = True
    return result


def _support(body: Body, grid: SpatialGrid,
             platforms: list[MovingPlatform], previous: bool = False) -> tuple[bool, str | None]:
    if body.vy < -EPSILON:
        return False, None
    probe = body.box.moved(0, GROUND_PROBE)
    for obstacle in grid.query(probe):
        if _overlap_x(body.box, obstacle) and abs(body.box.bottom - obstacle.top) <= GROUND_PROBE:
            return True, None
    for platform in platforms:
        obstacle = platform.box.moved(-platform.dx, -platform.dy) if previous else platform.box
        if _overlap_x(body.box, obstacle) and abs(body.box.bottom - obstacle.top) <= GROUND_PROBE:
            return True, platform.id
    return False, None


def _approach(value: float, target: float, amount: float) -> float:
    return min(value + amount, target) if value < target else max(value - amount, target)


def _jump(player: PlayerBody, events: list[str]) -> None:
    player.vy = -config.JUMP_SPEED
    player.grounded = False
    player.support_id = None
    player.coyote_timer = 0.0
    player.jump_buffer_timer = 0.0
    events.append("jump")


def _platform_push(player: PlayerBody, platform: MovingPlatform,
                   grid: SpatialGrid, others: list[AABB]) -> bool:
    """Вытолкнуть из пути платформы; True означает неразрешимое зажатие."""
    box, previous = platform.box, platform.box.moved(-platform.dx, -platform.dy)
    target_dx = target_dy = 0.0
    # Проверяем также пересечение всего пути: быстрый движущийся блок
    # не может незаметно перескочить сквозь персонажа.
    if platform.dx > EPSILON and previous.right <= player.box.left + EPSILON:
        if box.right > player.box.left and _overlap_y(player.box, box):
            target_dx = box.right - player.box.left
    elif platform.dx < -EPSILON and previous.left >= player.box.right - EPSILON:
        if box.left < player.box.right and _overlap_y(player.box, box):
            target_dx = box.left - player.box.right
    if platform.dy > EPSILON and previous.bottom <= player.box.top + EPSILON:
        if box.bottom > player.box.top and _overlap_x(player.box, box):
            target_dy = box.bottom - player.box.top
    elif platform.dy < -EPSILON and previous.top >= player.box.bottom - EPSILON:
        if box.top < player.box.bottom and _overlap_x(player.box, box):
            target_dy = box.top - player.box.bottom
    if not target_dx and not target_dy:
        return player.box.intersects(box)
    old_x, old_y = player.box.x, player.box.y
    move_body(player, target_dx, target_dy, grid, others)
    blocked = (abs(player.box.x - old_x - target_dx) > GROUND_PROBE
               or abs(player.box.y - old_y - target_dy) > GROUND_PROBE)
    return blocked or player.box.intersects(box)


def update_player(player: PlayerBody, commands: Commands, dt: float,
                  grid: SpatialGrid, platforms: list[MovingPlatform]) -> list[str]:
    """Один фиксированный шаг; платформы уже обновлены миром.

    Порядок: фронт ввода/таймеры → прыжок → перенос/зажатие → скорость →
    осевые коллизии → опора/буфер прыжка. При зажатии выдаётся crushed;
    уровень единожды возрождает героя вместо бесконечных выталкиваний.
    """
    if dt <= 0:
        return []
    events: list[str] = []
    on_ground, support_id = _support(player, grid, platforms, previous=True)
    was_grounded = player.grounded
    if on_ground:
        player.grounded, player.support_id = True, support_id
    elif player.grounded:
        player.grounded, player.support_id = False, None
    player.coyote_timer = (config.COYOTE_TIME if on_ground
                           else max(0.0, player.coyote_timer - dt))
    player.jump_buffer_timer = (config.JUMP_BUFFER if commands.jump_pressed
                                else max(0.0, player.jump_buffer_timer - dt))
    if player.jump_buffer_timer > 0 and (player.grounded or player.coyote_timer > 0):
        _jump(player, events)

    carried_id = player.support_id if player.grounded else None
    if carried_id is not None:
        carrier = next((p for p in platforms if p.id == carried_id), None)
        if carrier is not None:
            old_x, old_y = player.box.x, player.box.y
            move_body(player, carrier.dx, carrier.dy, grid,
                      [p.box for p in platforms if p.id != carried_id])
            if (abs(player.box.x - old_x - carrier.dx) > GROUND_PROBE
                    or abs(player.box.y - old_y - carrier.dy) > GROUND_PROBE):
                return events + ["crushed"]

    for platform in platforms:
        if platform.id == carried_id:
            continue
        if _platform_push(player, platform, grid,
                          [p.box for p in platforms if p is not platform]):
            return events + ["crushed"]

    move = max(-1, min(1, commands.move))
    rate = config.ACCELERATION if move else config.BRAKING
    player.vx = _approach(player.vx, move * config.RUN_SPEED, rate * dt)
    if move:
        player.facing = move
    if not commands.jump_held and player.vy < -config.JUMP_CUT_SPEED:
        player.vy = -config.JUMP_CUT_SPEED
    player.vy = min(player.vy + config.GRAVITY * dt, config.MAX_FALL_SPEED)
    move_body(player, player.vx * dt, player.vy * dt, grid, [p.box for p in platforms])
    player.grounded, player.support_id = _support(player, grid, platforms)
    if player.grounded:
        player.vy = 0.0
        player.coyote_timer = config.COYOTE_TIME
        if not was_grounded:
            events.append("land")
        if player.jump_buffer_timer > 0:
            _jump(player, events)
            if not commands.jump_held:
                player.vy = -config.JUMP_CUT_SPEED
    return events
