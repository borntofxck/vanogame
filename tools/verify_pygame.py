"""Проверка настоящего Pygame-приложения и снимки экранов.

python -m tools.verify_pygame             dummy SDL
python -m tools.verify_pygame --native    настоящее окно Windows

Контроллер посылает события кнопок и использует тот же фиксированный шаг.
Это автоматизированный прогон, а не ручное прохождение человеком.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def verify(native: bool = False) -> dict:
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    if not native:
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    import pygame
    from dormgame.app import Application, Settings
    from dormgame.config import FIXED_DT
    from tools.verify_routes import RouteController, route_one, route_two, route_three

    output = Path(__file__).resolve().parents[1] / 'artifacts'
    output.mkdir(exist_ok=True)
    app = Application(smoke=True)
    snapshots: list[str] = []

    def key(code: int, pressed: bool = True) -> None:
        app.handle_event(pygame.event.Event(pygame.KEYDOWN if pressed else pygame.KEYUP,
                                           key=code, repeat=False))

    def capture(name: str) -> None:
        app.render(0)
        pygame.image.save(app.window, str(output / f'{name}.png'))
        snapshots.append(name)

    class WindowController(RouteController):
        def tick(self, move=0, jump=False, held=False, interact=False):
            deaths = app.session.deaths
            app.input.move = move
            if jump:
                key(pygame.K_SPACE)
            if not held and app.input.held:
                key(pygame.K_SPACE, False)
            if interact:
                key(pygame.K_e)
            app.stepper.advance(FIXED_DT, app.step, paused=app.scene != 'game')
            events = app.session.drain_events()
            self.jumps += sum(e.kind == 'jump' for e in events)
            self.steps += 1
            app.renderer.accept_events(events, app.settings)
            for event in events:
                app.audio.play(event.kind)
            app.renderer.tick(FIXED_DT, app.settings)
            if self.steps % 4 == 0:
                app.render(4 * FIXED_DT)
                pygame.event.pump()
            around_wall = any(
                enemy.kind == 'drone' and enemy.state == 'Погоня'
                and any(648 <= enemy.nav.cell_center(cell)[0] <= 680
                        and enemy.nav.cell_center(cell)[1] >= 376 for cell in enemy.path)
                for enemy in app.session.level.enemies)
            if app.session.level_index == 1 and around_wall and 'astar-wall' not in snapshots:
                app.debug = True
                capture('astar-wall')
                app.debug = False
            assert app.session.deaths == deaths, f'Смерть при проверке экрана {app.scene}'

    try:
        capture('menu')
        # Навигация кнопками, мышь после изменения пропорций окна.
        key(pygame.K_DOWN)
        key(pygame.K_RETURN)
        assert app.scene == 'controls'
        capture('controls')
        key(pygame.K_ESCAPE)
        app.activate(2)
        capture('settings')
        app.activate(2)
        app.activate(3)
        assert not app.settings.shake and app.settings.reduced_effects
        app.activate(2)
        app.activate(3)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            app.settings.save(path)
            assert Settings.load(path) == app.settings
        key(pygame.K_ESCAPE)
        app.window = pygame.display.set_mode((1000, 700), pygame.RESIZABLE)
        app.render(0)
        assert app.viewport.height < 700 and app.viewport.width == 1000
        button = app.buttons[0]
        mouse = (round(app.viewport.x + button.centerx * app.viewport.w / 640),
                 round(app.viewport.y + button.centery * app.viewport.h / 360))
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=mouse))
        assert app.scene == 'intro'
        capture('intro-letterbox')
        app.window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        key(pygame.K_ESCAPE)
        assert app.scene == 'game'
        key(pygame.K_SPACE)
        key(pygame.K_ESCAPE)
        before = app.session.elapsed
        app.update(10)
        assert app.session.elapsed == before and app.stepper.accumulator == 0
        capture('pause')
        key(pygame.K_ESCAPE)
        assert not app.input.consume().jump_pressed
        app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        assert app.scene == 'pause'
        key(pygame.K_ESCAPE)
        key(pygame.K_m)
        assert not app.settings.sound
        key(pygame.K_m)
        assert app.settings.sound
        key(pygame.K_F3)
        assert app.debug
        key(pygame.K_F3)
        controller = WindowController(app.session)
        for index, route in enumerate((route_one, route_two, route_three)):
            capture(f'level{index + 1}-start')
            controller.walk(8)
            controller.walk(48)
            capture(f'souvenir{index + 1}')
            route(controller)
            assert app.session.level.complete
            if index < 2:
                assert app.scene == 'transition'
                capture(f'transition{index + 1}')
                key(pygame.K_RETURN)
                assert app.scene == 'game' and app.session.level_index == index + 1
            else:
                assert app.scene == 'ending' and app.session.finished
        assert app.session.total_pages == 13 and app.session.deaths == 0
        assert app.session.total_souvenirs == 3
        capture('ending')
        result = {'video_driver': pygame.display.get_driver(), 'audio': app.audio.available,
                  'completed': app.session.finished, 'pages': app.session.total_pages,
                  'deaths': app.session.deaths, 'seconds': round(app.session.elapsed, 3),
                  'souvenirs': app.session.total_souvenirs,
                  'jumps': controller.jumps, 'snapshots': snapshots}
        key(pygame.K_RETURN)
        assert app.scene == 'intro' and app.session.total_pages == 0 and app.session.elapsed == 0
        key(pygame.K_ESCAPE)
        assert app.scene == 'game'
        result['restart_verified'] = True
        (output / ('native-check.json' if native else 'pygame-check.json')).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        app.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.native), ensure_ascii=False, indent=2))
