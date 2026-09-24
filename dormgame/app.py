"""Окно Pygame, ввод и переходы экранов; правила остаются в GameSession."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame

from .audio import Audio
from .config import VIEW_HEIGHT, VIEW_WIDTH
from .model import GameSession
from .presentation import Renderer
from .timing import FixedStepper, InputBuffer


@dataclass
class Settings:
    sound: bool = True
    music: bool = True
    shake: bool = True
    reduced_effects: bool = False

    @classmethod
    def load(cls, path: Path) -> Settings:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return cls(**{name: value for name, value in data.items()
                          if name in cls.__dataclass_fields__ and type(value) is bool})
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')
        except OSError:
            # Игра остаётся доступной и при каталоге пользователя только для чтения.
            pass


class Application:
    """У каждого экрана свой переход; только экран game расходует игровое время."""

    SCENES = ('menu', 'game', 'intro', 'pause', 'controls', 'settings', 'transition', 'ending')

    def __init__(self, *, smoke: bool = False, level: int = 1,
                 scene: str = 'menu', debug: bool = False) -> None:
        pygame.mixer.pre_init(22050, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption('Общага: пять минут до выселения')
        self.window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        self.canvas = pygame.Surface((VIEW_WIDTH, VIEW_HEIGHT)).convert()
        self.renderer = Renderer(self.canvas)
        icon = pygame.transform.scale(self.renderer.sprites.actor('student', 1, 0), (34, 38))
        pygame.display.set_icon(icon)
        self.settings_path = Path.home() / '.obshchaga' / 'settings.json'
        self.settings = Settings() if smoke else Settings.load(self.settings_path)
        self.audio = Audio()
        self.audio.configure(self.settings.sound, self.settings.music)
        self.session = GameSession()
        for _ in range(level - 1):
            self.session.level.complete = True
            self.session.advance_level()
        self.scene = scene
        self.return_scene = 'menu' if scene not in ('game', 'pause') else 'pause'
        self.selected = 0
        self.buttons: list[pygame.Rect] = []
        self.input = InputBuffer()
        self.stepper = FixedStepper()
        self.clock = pygame.time.Clock()
        self.running = True
        self.smoke = smoke
        self.debug = debug
        self.frames = 0
        self.viewport = pygame.Rect(0, 0, 1280, 720)
        self.fullscreen = False
        self.windowed_size = (1280, 720)
        self._last_mouse = (-1, -1)
        self.session.paused = self.scene != 'game'
        self.render(0)

    def set_scene(self, scene: str) -> None:
        self.scene = scene
        self.selected = 0
        self.buttons = []
        self.session.paused = scene != 'game'
        self.input.clear()
        self.stepper.clear()

    def start(self, intro: bool = True) -> None:
        self.session.new_game()
        self.renderer.current_level = -1
        self.renderer.reset_camera(self.session.level)
        self.set_scene('intro' if intro else 'game')

    def _toggle_setting(self, name: str) -> None:
        setattr(self.settings, name, not getattr(self.settings, name))
        self.audio.configure(self.settings.sound, self.settings.music)
        if not self.smoke:
            self.settings.save(self.settings_path)

    def activate(self, index: int) -> None:
        if self.scene == 'menu':
            if index == 0:
                self.start()
            elif index in (1, 2):
                self.return_scene = 'menu'
                self.set_scene('controls' if index == 1 else 'settings')
            else:
                self.running = False
        elif self.scene == 'intro':
            self.set_scene('game')
        elif self.scene == 'pause':
            if index == 0:
                self.set_scene('game')
            elif index in (1, 2):
                self.return_scene = 'pause'
                self.set_scene('controls' if index == 1 else 'settings')
            else:
                self.set_scene('menu')
        elif self.scene == 'controls':
            self.set_scene(self.return_scene)
        elif self.scene == 'settings':
            if index < 4:
                self._toggle_setting(('sound', 'music', 'shake', 'reduced_effects')[index])
            else:
                self.set_scene(self.return_scene)
        elif self.scene == 'transition':
            self.session.advance_level()
            self.set_scene('game')
        elif self.scene == 'ending':
            if index == 0:
                self.start()
            else:
                self.set_scene('menu')

    def escape(self) -> None:
        if self.scene == 'game':
            self.set_scene('pause')
        elif self.scene == 'pause':
            self.set_scene('game')
        elif self.scene in ('settings', 'controls'):
            self.set_scene(self.return_scene)
        elif self.scene == 'intro':
            self.set_scene('game')
        elif self.scene == 'transition':
            self.activate(0)
        elif self.scene == 'ending':
            self.set_scene('menu')

    def _mouse_position(self, position: tuple[int, int]) -> tuple[float, float]:
        return ((position[0] - self.viewport.x) * VIEW_WIDTH / self.viewport.w,
                (position[1] - self.viewport.y) * VIEW_HEIGHT / self.viewport.h)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWFOCUSLOST and self.scene == 'game':
            self.set_scene('pause')
        elif event.type == pygame.KEYDOWN:
            if getattr(event, 'repeat', False):
                return
            if event.key == pygame.K_ESCAPE:
                self.escape()
            elif event.key == pygame.K_m:
                self._toggle_setting('sound')
            elif event.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif event.key == pygame.K_F3:
                self.debug = not self.debug
            elif self.scene == 'game':
                if event.key == pygame.K_SPACE:
                    self.input.jump(True)
                elif event.key == pygame.K_e:
                    self.input.interact()
                elif event.key == pygame.K_r:
                    self.input.reset_checkpoint()
            else:
                count = max(1, len(self.buttons))
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected = (self.selected - 1) % count
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected = (self.selected + 1) % count
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.activate(self.selected)
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.input.jump(False)
        elif event.type == pygame.MOUSEMOTION and self.scene != 'game':
            position = self._mouse_position(event.pos)
            if event.pos != self._last_mouse:
                self._last_mouse = event.pos
                for index, button in enumerate(self.buttons):
                    if button.collidepoint(position):
                        self.selected = index
                        break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.scene != 'game':
            position = self._mouse_position(event.pos)
            for index, button in enumerate(self.buttons):
                if button.collidepoint(position):
                    self.activate(index)
                    break

    def toggle_fullscreen(self) -> None:
        if self.fullscreen:
            self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        else:
            self.windowed_size = self.window.get_size()
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.fullscreen = not self.fullscreen

    def step(self, dt: float) -> bool:
        self.session.update(dt, self.input.consume())
        if self.session.level.complete:
            if self.session.level_index == len(self.session.specs) - 1:
                self.session.advance_level()
                self.set_scene('ending')
            else:
                self.set_scene('transition')
            return False
        return True

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.input.move = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        self.stepper.advance(dt, self.step, paused=self.scene != 'game')
        events = self.session.drain_events()
        self.renderer.accept_events(events, self.settings)
        for event in events:
            self.audio.play(event.kind)
        # В паузе замирают также частицы и анимация мира, не только физика.
        world_paused = self.scene == 'pause' or (
            self.scene in ('controls', 'settings') and self.return_scene == 'pause')
        if not world_paused:
            self.renderer.tick(dt, self.settings)

    def render(self, dt: float) -> None:
        if self.scene == 'menu':
            self.buttons = self.renderer.front_menu(self.selected, self.settings)
        elif self.scene == 'intro':
            self.buttons = self.renderer.intro(self.selected, self.settings)
        elif self.scene == 'ending':
            self.buttons = self.renderer.ending(self.session, self.selected, self.settings)
        else:
            in_world = self.scene in ('game', 'pause', 'transition') or self.return_scene == 'pause'
            if in_world:
                self.renderer.draw_game(self.session, self.settings, dt if self.scene == 'game' else 0,
                                        self.debug, self.clock.get_fps(), self.stepper.steps)
            else:
                self.renderer.backdrop(self.settings)
            if self.scene == 'pause':
                self.buttons = self.renderer.panel('Перерыв на чай', 'Время стоит. Курсовая никуда не убежит.',
                                                   ['Продолжить', 'Управление', 'Настройки', 'Главное меню'], self.selected, 76)
            elif self.scene == 'controls':
                self.buttons = self.renderer.controls(self.selected)
            elif self.scene == 'settings':
                labels = [f'Звук: {"вкл." if self.settings.sound else "выкл."}',
                          f'Музыка: {"вкл." if self.settings.music else "выкл."}',
                          f'Тряска камеры: {"вкл." if self.settings.shake else "выкл."}',
                          f'Меньше эффектов: {"да" if self.settings.reduced_effects else "нет"}', 'Назад']
                subtitle = 'Спокойнее, тише, уютнее.' if self.audio.available else 'Аудиоустройство недоступно. Игра работает без звука.'
                self.buttons = self.renderer.panel('Настройки', subtitle, labels, self.selected, 56)
            elif self.scene == 'transition':
                self.buttons = self.renderer.transition(self.session, self.selected)
            else:
                self.buttons = []
        width, height = self.window.get_size()
        scale = min(width / VIEW_WIDTH, height / VIEW_HEIGHT)
        size = max(1, round(VIEW_WIDTH * scale)), max(1, round(VIEW_HEIGHT * scale))
        self.viewport = pygame.Rect((width - size[0]) // 2, (height - size[1]) // 2, *size)
        self.window.fill((7, 11, 20))
        pygame.transform.scale(self.canvas, size, self.window.subsurface(self.viewport))
        pygame.display.flip()

    def run(self, max_frames: int = 0, screenshot: Path | None = None) -> dict[str, Any]:
        while self.running and (not max_frames or self.frames < max_frames):
            dt = 1 / 60 if self.smoke else self.clock.tick(60) / 1000
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.render(dt)
            self.frames += 1
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.window, str(screenshot))
        return {'frames': self.frames, 'scene': self.scene,
                'level': self.session.level_index + 1,
                'elapsed': round(self.session.elapsed, 3),
                'deaths': self.session.deaths, 'pages': self.session.total_pages,
                'audio': self.audio.available, 'physics_steps': self.stepper.steps}

    def close(self) -> None:
        pygame.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Общага: пять минут до выселения — Python + Pygame')
    parser.add_argument('--smoke', action='store_true', help='Детерминированная проверка без задержки между кадрами')
    parser.add_argument('--frames', type=int, default=0, help='Закрыть игру после заданного числа кадров')
    parser.add_argument('--screenshot', type=Path, help='Сохранить последний отрисованный кадр в PNG')
    parser.add_argument('--level', type=int, choices=(1, 2, 3), help='Открыть этаж для демонстрации')
    parser.add_argument('--scene', choices=Application.SCENES, help='Открыть экран для визуальной проверки')
    parser.add_argument('--debug', action='store_true', help='Сразу показать диагностику F3')
    args = parser.parse_args(argv)
    if args.smoke:
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    scene = args.scene or ('game' if args.level else 'menu')
    application: Application | None = None
    try:
        application = Application(smoke=args.smoke, level=args.level or 1, scene=scene, debug=args.debug)
        frames = args.frames if args.frames > 0 else (120 if args.smoke else 0)
        result = application.run(frames, args.screenshot)
        if args.smoke:
            print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        if application is not None:
            application.close()
        else:
            pygame.quit()
