"""Игровые правила. Не импортирует Pygame и ничего не рисует."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .commands import Commands
from .config import PLAYER_HEIGHT, PLAYER_WIDTH, RESET_COOLDOWN, RESPAWN_SHIELD
from .enemies import build_enemy
from .geometry import AABB
from .levels import load_levels
from .physics import MovingPlatform, PlayerBody, SpatialGrid, update_player


@dataclass(frozen=True)
class GameEvent:
    kind: str
    x: float
    y: float
    text: str = ''


@dataclass
class Item:
    id: str
    box: AABB
    text: str = ''
    collected: bool = False
    active: bool = False
    spawn: tuple[float, float] | None = None
    kind: str = ''

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> Item:
        spawn = tuple(spec['spawn']) if 'spawn' in spec else None
        return cls(spec['id'], AABB(*spec['rect']), spec.get('text', ''),
                   spawn=spawn, kind=spec.get('kind', ''))


class LevelState:
    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.width, self.height = spec['width'], spec['height']
        self.name, self.subtitle = spec['name'], spec['subtitle']
        self.solids = [AABB(*rect) for rect in spec['solids']]
        self.grid = SpatialGrid(self.solids)
        self.spawn = tuple(spec['start'])
        self.player = self._new_player()
        self.platforms = [MovingPlatform(p['id'], AABB(*p['rect']), tuple(p['end']), p['speed']) for p in spec['platforms']]
        self.enemies = [build_enemy(e, self.solids, self.width, self.height) for e in spec['enemies']]
        self.pages = [Item.from_spec(p) for p in spec['pages']]
        self.souvenirs = [Item.from_spec(p) for p in spec.get('souvenirs', [])]
        self.checkpoints = [Item.from_spec(p) for p in spec['checkpoints']]
        self.notes = [Item.from_spec(p) for p in spec['notes']]
        self.hazards = [Item.from_spec(p) for p in spec['hazards']]
        self.exit = Item.from_spec(spec['exit'])
        self.checkpoint_id: str | None = None
        self.complete = False
        self.invulnerable = RESPAWN_SHIELD
        self.reset_cooldown = RESET_COOLDOWN

    @property
    def collected_pages(self) -> int:
        return sum(page.collected for page in self.pages)

    def _new_player(self) -> PlayerBody:
        return PlayerBody(AABB(*self.spawn, PLAYER_WIDTH, PLAYER_HEIGHT))

    def respawn(self) -> None:
        """Страницы и контрольная точка сохраняются; динамика начинает цикл заново."""
        for platform in self.platforms:
            platform.reset()
        for enemy in self.enemies:
            enemy.reset()
        self.player = self._new_player()
        self.invulnerable = RESPAWN_SHIELD
        self.reset_cooldown = RESET_COOLDOWN


class GameSession:
    """Один сеанс от старта до крыши. Приложение управляет экранными сценами."""
    def __init__(self, specs: list[dict[str, Any]] | None = None):
        self.specs = specs if specs is not None else load_levels()
        self.new_game()

    def new_game(self) -> None:
        self.level_index = 0
        self.elapsed = 0.0
        self.deaths = 0
        self.banked_pages = 0
        self.banked_souvenirs = 0
        self.finished = False
        self.paused = False
        self.events: list[GameEvent] = []
        self.level = LevelState(self.specs[0])

    @property
    def total_pages(self) -> int:
        return self.banked_pages + self.level.collected_pages

    @property
    def total_souvenirs(self) -> int:
        return self.banked_souvenirs + sum(item.collected for item in self.level.souvenirs)

    @property
    def souvenir_goal(self) -> int:
        return sum(len(spec.get('souvenirs', [])) for spec in self.specs)

    def drain_events(self) -> list[GameEvent]:
        events, self.events = self.events, []
        return events

    def _emit(self, kind: str, box: AABB, text: str = '') -> None:
        self.events.append(GameEvent(kind, *box.center, text))

    def _die(self, reason: str) -> None:
        self._emit('died', self.level.player.box, reason)
        self.deaths += 1
        self.level.respawn()

    def advance_level(self) -> None:
        if not self.level.complete or self.finished:
            return
        if self.level_index == len(self.specs) - 1:
            self.finished = True
            self._emit('win', self.level.exit.box, 'Ноутбук сухой. Защита состоится!')
            return
        self.banked_pages += self.level.collected_pages
        self.banked_souvenirs += sum(item.collected for item in self.level.souvenirs)
        self.level_index += 1
        self.level = LevelState(self.specs[self.level_index])

    def update(self, dt: float, commands: Commands) -> None:
        if self.paused or self.finished or self.level.complete:
            return
        level = self.level
        self.elapsed += dt
        level.invulnerable = max(0.0, level.invulnerable - dt)
        level.reset_cooldown = max(0.0, level.reset_cooldown - dt)
        if commands.reset and level.reset_cooldown <= 0:
            self._die('Вернулись за здравым смыслом.')
            return
        # Порядок является частью правил: перенос опоры предшествует движению героя.
        for platform in level.platforms:
            platform.update(dt)
        movement_events = update_player(level.player, commands, dt, level.grid, level.platforms)
        for kind in movement_events:
            if kind != 'crushed':
                self._emit(kind, level.player.box)
        # Один полиморфный контракт: тип врага здесь не проверяется.
        for enemy in level.enemies:
            for kind in enemy.update(dt, level.player.box, level.grid):
                self._emit(kind, enemy.box)
        box = level.player.box
        if 'crushed' in movement_events or box.top > level.height + 48:
            self._die('Общага проверила гравитацию.')
            return
        # Горизонтальные границы мира закрыты; верх допускает прыжок за край камеры.
        if box.x < 0:
            box.x, level.player.vx = 0.0, 0.0
        elif box.right > level.width:
            box.x, level.player.vx = level.width - box.w, 0.0
        if level.invulnerable <= 0 and (
            any(box.intersects(h.box) for h in level.hazards)
            or any(box.intersects(e.box) for e in level.enemies)
        ):
            self._die('Диплом важнее тапочек. Ещё попытка!')
            return
        for page in level.pages:
            if not page.collected and box.intersects(page.box):
                page.collected = True
                self._emit('page', page.box, page.text or 'Курсовая намокла, зато теперь с водой.')
        for souvenir in level.souvenirs:
            if not souvenir.collected and box.intersects(souvenir.box):
                souvenir.collected = True
                self._emit('souvenir', souvenir.box, souvenir.text)
        for checkpoint in level.checkpoints:
            if box.intersects(checkpoint.box) and level.checkpoint_id != checkpoint.id:
                level.checkpoint_id = checkpoint.id
                level.spawn = checkpoint.spawn or tuple(level.spec['start'])
                for other in level.checkpoints:
                    other.active = other is checkpoint
                self._emit('checkpoint', checkpoint.box, 'Чайник сохранён. Прогресс тоже.')
        if commands.interact:
            reach = box.expanded(20)
            for note in level.notes:
                if reach.intersects(note.box):
                    note.active = True
                    self._emit('note', note.box, note.text)
            if reach.intersects(level.exit.box):
                remaining = len(level.pages) - level.collected_pages
                if remaining:
                    self._emit('locked', level.exit.box, f'До выхода не хватает страниц: {remaining}.')
                else:
                    level.complete = True
                    self._emit('exit', level.exit.box, 'Ещё один этаж позади.')
