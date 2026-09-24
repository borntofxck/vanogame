"""Воспроизводимое прохождение чистой модели командами, без Pygame.

Запуск: python -m tools.verify_routes. Проверка не заменяет игру человеком:
контроллер видит дробные координаты, но пользуется той же физикой и вводом.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from dormgame import config
from dormgame.commands import Commands
from dormgame.geometry import AABB
from dormgame.model import GameSession
from dormgame.physics import PlayerBody, SpatialGrid, update_player


@dataclass
class RouteResult:
    level: int
    seconds: float
    pages: int
    deaths: int
    jumps: int


class RouteController:
    """Обратная связь управляет только кнопками, координаты мира не меняет."""

    def __init__(self, session: GameSession):
        self.session = session
        self.jumps = 0
        self.steps = 0

    @property
    def player(self):
        return self.session.level.player

    def tick(self, move: int = 0, jump: bool = False, held: bool = False,
             interact: bool = False) -> None:
        previous_deaths = self.session.deaths
        previous_box = self.player.box.copy()
        enemy_positions = [(enemy.id, enemy.box.copy()) for enemy in self.session.level.enemies]
        self.session.update(config.FIXED_DT, Commands(move, jump, held, interact))
        self.steps += 1
        self.jumps += sum(event.kind == 'jump' for event in self.session.drain_events())
        if self.session.deaths != previous_deaths:
            raise AssertionError(f'Уровень {self.session.level_index + 1}, шаг {self.steps}: '
                                 f'смерть у {previous_box}; враги {enemy_positions}')

    def direction(self, target_x: float) -> int:
        distance = target_x - self.player.box.x
        stopping = self.player.vx ** 2 / (2 * config.BRAKING)
        if abs(distance) < 0.8:
            return 0
        if distance * self.player.vx > 0 and abs(distance) <= stopping + 0.5:
            return 0
        return 1 if distance > 0 else -1

    def wait_for(self, predicate: Callable[[], bool], limit: float = 8.0) -> None:
        for _ in range(round(limit / config.FIXED_DT)):
            if predicate():
                return
            self.tick()
        raise AssertionError(f'Ожидание не завершилось: {self.player.box}')

    def walk(self, target_x: float, limit: float = 8.0) -> None:
        for _ in range(round(limit / config.FIXED_DT)):
            if abs(self.player.box.x - target_x) < 1.5 and abs(self.player.vx) < 20:
                return
            self.tick(self.direction(target_x))
        raise AssertionError(f'Не дошёл до {target_x}: {self.player.box}')

    def jump(self, target_x: float | Callable[[], float], limit: float = 2.0) -> None:
        if not self.player.grounded:
            self.wait_for(lambda: self.player.grounded)
        target = target_x if callable(target_x) else lambda: target_x
        self.tick(self.direction(target()), jump=True, held=True)
        airborne = not self.player.grounded
        for _ in range(round(limit / config.FIXED_DT)):
            if airborne and self.player.grounded:
                # Перед следующим нажатием действительно отпускаем кнопку.
                # Это позволяет воспроизвести маршрут через InputBuffer окна.
                self.tick(held=False)
                return
            self.tick(self.direction(target()), held=True)
            airborne |= not self.player.grounded
        raise AssertionError(f'Прыжок не завершился: {self.player.box}')

    def require_page(self, identifier: str) -> None:
        item = next(page for page in self.session.level.pages if page.id == identifier)
        if not item.collected:
            raise AssertionError(f'Не подобрана {identifier}: {self.player.box}')


def route_one(control: RouteController) -> None:
    control.walk(174)
    control.jump(232)
    control.walk(326)
    control.jump(404)
    control.walk(502)
    control.jump(580)
    control.walk(678)
    control.jump(756)
    control.walk(854)
    control.jump(932)
    control.walk(1030)
    control.tick(interact=True)


def route_two(control: RouteController) -> None:
    control.walk(158)
    control.jump(216)
    control.walk(278)
    control.jump(356)
    control.walk(428)
    platform = control.session.level.platforms[0]
    control.wait_for(lambda: platform.box.x <= 494 and platform.dx < 0)
    control.jump(lambda: platform.box.x + 25)
    if control.player.support_id != platform.id:
        raise AssertionError('Прыжок не достиг горизонтальной решётки')
    control.wait_for(lambda: platform.box.x >= 542 and platform.dx > 0)
    control.walk(580)
    control.require_page('p3')
    control.walk(684)
    control.jump(730)
    control.jump(806)
    control.jump(868)
    control.walk(934)
    control.jump(1012)
    control.walk(1088)
    control.tick(interact=True)


def route_three(control: RouteController) -> None:
    control.walk(142)
    control.jump(200)
    control.walk(294)
    guard = control.session.level.enemies[0]
    control.wait_for(lambda: guard.box.x >= 400 and guard.facing > 0)
    control.jump(380)
    control.require_page('p2')
    control.jump(446)
    platform = control.session.level.platforms[0]
    control.jump(lambda: platform.box.x + 30)
    if control.player.support_id != platform.id:
        raise AssertionError('Прыжок не достиг подъёмника')
    control.wait_for(lambda: platform.box.y <= 310 and platform.dy < 0)
    control.walk(538)
    control.require_page('p3')
    control.jump(632)
    control.walk(734)
    control.jump(812)
    control.walk(850)
    control.require_page('p5')
    control.jump(926)
    control.jump(988)
    control.walk(1086)
    control.tick(interact=True)


def verify_campaign(collect_souvenirs: bool = False) -> list[RouteResult]:
    session = GameSession()
    controller = RouteController(session)
    results = []
    for index, route in enumerate((route_one, route_two, route_three)):
        start_time, start_jumps, start_deaths = session.elapsed, controller.jumps, session.deaths
        if collect_souvenirs:
            controller.walk(8)
            controller.walk(48)
        route(controller)
        if not session.level.complete:
            raise AssertionError(f'Выход уровня {index + 1} не активирован, страниц {session.level.collected_pages}')
        results.append(RouteResult(index + 1, session.elapsed - start_time,
                                   session.level.collected_pages,
                                   session.deaths - start_deaths, controller.jumps - start_jumps))
        session.advance_level()
    if not session.finished:
        raise AssertionError('Финал не достигнут')
    if collect_souvenirs and session.total_souvenirs != 3:
        raise AssertionError('Набор студента собран не полностью')
    return results


def measure_jump() -> tuple[float, float]:
    """Полный прыжок при установившейся скорости, измеренный симуляцией."""
    player = PlayerBody(AABB(0, 74, config.PLAYER_WIDTH, config.PLAYER_HEIGHT),
                        vx=config.RUN_SPEED, grounded=True)
    grid = SpatialGrid([AABB(-1000, 100, 3000, 20)])
    top = player.box.top
    for step in range(240):
        update_player(player, Commands(1, step == 0, True), config.FIXED_DT, grid, [])
        top = min(top, player.box.top)
        if step and player.grounded:
            return 74 - top, player.box.x
    raise AssertionError('Прыжок не приземлился')


if __name__ == '__main__':
    height, distance = measure_jump()
    print(f'Измеренный прыжок: высота {height:.2f} px, дальность {distance:.2f} px')
    for result in verify_campaign():
        print(f'Уровень {result.level}: {result.seconds:.2f} с; страниц {result.pages}; '
              f'смертей {result.deaths}; прыжков {result.jumps}')
