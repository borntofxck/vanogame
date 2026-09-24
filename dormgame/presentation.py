"""Только представление: пиксельные спрайты, камера, меню, HUD и эффекты."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import random
from typing import Any

import pygame

from .config import VIEW_WIDTH as W, VIEW_HEIGHT as H

INK = (15, 22, 40)
PANEL = (24, 34, 54)
WHITE = (236, 236, 215)
MUTED = (147, 166, 183)
MINT = (111, 230, 203)
GOLD = (255, 201, 117)
CORAL = (241, 125, 120)
ROOT = Path(__file__).resolve().parents[1]


def time_text(seconds: float) -> str:
    minutes, seconds_int = divmod(int(seconds), 60)
    return f'{minutes:02d}:{seconds_int:02d}'


class Text:
    """Шрифты и готовые подписи кэшируются, кириллица поставляется с игрой."""

    def __init__(self) -> None:
        candidates = (ROOT / 'assets/fonts/DejaVuSans.ttf',
                      ROOT / 'assets/fonts/Arial.ttf',
                      Path('C:/Windows/Fonts/arial.ttf'),
                      Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        self.path = next((str(path) for path in candidates if path.exists()), None)
        if self.path is None:
            self.path = pygame.font.match_font('dejavusans,arial,liberationsans')
        self.fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self.cache: dict[tuple, pygame.Surface] = {}

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = size, bold
        if key not in self.fonts:
            self.fonts[key] = pygame.font.Font(self.path, size)
            self.fonts[key].set_bold(bold)
        return self.fonts[key]

    def draw(self, surface: pygame.Surface, value: str, xy: tuple[float, float],
             size: int = 12, color: tuple = WHITE, bold: bool = False,
             center: bool = False) -> pygame.Rect:
        key = value, size, color, bold
        if key not in self.cache:
            if len(self.cache) > 1500:
                self.cache.clear()
            self.cache[key] = self.font(size, bold).render(value, True, color)
        rendered = self.cache[key]
        rect = rendered.get_rect()
        if center:
            rect.center = (round(xy[0]), round(xy[1]))
        else:
            rect.topleft = (round(xy[0]), round(xy[1]))
        surface.blit(rendered, rect)
        return rect

    def wrapped(self, surface: pygame.Surface, value: str, xy: tuple[int, int],
                max_width: int, size: int = 12, color: tuple = WHITE,
                line_height: int | None = None) -> int:
        y = xy[1]
        line_height = line_height or size + 6
        for paragraph in value.split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = f'{line} {word}'.strip()
                if line and self.font(size).size(candidate)[0] > max_width:
                    self.draw(surface, line, (xy[0], y), size, color)
                    y += line_height
                    line = word
                else:
                    line = candidate
            self.draw(surface, line, (xy[0], y), size, color)
            y += line_height
        return y


class Sprites:
    def __init__(self) -> None:
        self.cache: dict[tuple, pygame.Surface] = {}

    def actor(self, kind: str, facing: int, frame: int) -> pygame.Surface:
        key = kind, facing, frame
        if key in self.cache:
            return self.cache[key]
        sprite = pygame.Surface((34, 38), pygame.SRCALPHA)
        draw = pygame.draw
        if kind == 'drone':
            draw.rect(sprite, (40, 56, 73), (4, 16, 26, 7))
            draw.rect(sprite, (164, 201, 209), (9, 13, 16, 11))
            draw.rect(sprite, (72, 98, 121), (10, 21, 14, 4))
            draw.rect(sprite, MINT, (13, 16, 8, 3))
            draw.rect(sprite, (23, 33, 54), (16, 16, 2, 3))
            draw.line(sprite, (99, 153, 175), (4, 12), (8, 16))
            draw.line(sprite, (99, 153, 175), (29, 12), (25, 16))
            rotor = 3 if frame % 2 else 0
            draw.line(sprite, (196, 219, 208), (rotor, 11), (11 - rotor, 11))
            draw.line(sprite, (196, 219, 208), (23 + rotor, 11), (33 - rotor, 11))
        else:
            bob = 1 if frame in (1, 6) else 0
            stride = 0 if frame >= 5 else (-2, 0, 2, 0, 1)[frame]
            if kind == 'patrol':
                draw.rect(sprite, (32, 43, 69), (9, 14 + bob, 15, 15))
                draw.rect(sprite, (65, 79, 99), (10, 15 + bob, 13, 11))
                draw.rect(sprite, GOLD, (19, 17 + bob, 3, 3))
                draw.rect(sprite, (200, 155, 119), (12, 5 + bob, 10, 10))
                draw.rect(sprite, (44, 60, 82), (10, 3 + bob, 14, 5))
                draw.rect(sprite, (71, 87, 110), (10, 3 + bob, 12, 2))
                draw.rect(sprite, GOLD, (21, 6 + bob, 5, 2))
                draw.rect(sprite, INK, (20, 9 + bob, 2, 2))
                draw.rect(sprite, (33, 39, 57), (11, 28, 5, 6 + stride))
                draw.rect(sprite, (33, 39, 57), (18, 28, 5, 6 - stride))
                draw.rect(sprite, (125, 145, 153), (10, 33 + stride, 7, 2))
                draw.rect(sprite, (125, 145, 153), (18, 33 - stride, 7, 2))
                draw.rect(sprite, (204, 166, 124), (24, 21 + bob, 4, 4))
                draw.rect(sprite, (35, 50, 66), (26, 19 + bob, 5, 4))
            else:
                # Рюкзак читается отдельной формой даже без цвета.
                draw.rect(sprite, (93, 64, 64), (5, 16 + bob, 7, 13))
                draw.rect(sprite, (221, 138, 87), (5, 15 + bob, 6, 11))
                draw.rect(sprite, GOLD, (5, 19 + bob, 5, 2))
                draw.rect(sprite, (84, 159, 180), (11, 15 + bob, 12, 13))
                draw.rect(sprite, (123, 198, 194), (12, 15 + bob, 10, 3))
                draw.rect(sprite, (51, 100, 138), (11, 25 + bob, 12, 4))
                draw.rect(sprite, (232, 181, 140), (12, 6 + bob, 10, 10))
                draw.rect(sprite, (100, 62, 60), (11, 3 + bob, 12, 6))
                draw.rect(sprite, (149, 83, 62), (11, 3 + bob, 9, 2))
                draw.rect(sprite, (100, 62, 60), (11, 6 + bob, 3, 5))
                draw.rect(sprite, INK, (20, 10 + bob, 2, 2))
                draw.rect(sprite, (241, 197, 154), (23, 21 + bob, 3, 6))
                draw.rect(sprite, (35, 54, 83), (12, 28, 4, 5 + stride))
                draw.rect(sprite, (35, 54, 83), (19, 28, 4, 5 - stride))
                draw.rect(sprite, WHITE, (11, 33 + stride, 7, 2))
                draw.rect(sprite, WHITE, (19, 33 - stride, 7, 2))
        if facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        self.cache[key] = sprite
        return sprite

    def object(self, kind: str) -> pygame.Surface:
        key = (kind,)
        if key in self.cache:
            return self.cache[key]
        surface = pygame.Surface((40, 52), pygame.SRCALPHA)
        draw = pygame.draw
        if kind == 'plant':
            draw.rect(surface, (172, 101, 78), (13, 35, 17, 13))
            draw.rect(surface, GOLD, (11, 33, 21, 4))
            draw.line(surface, (89, 166, 131), (21, 33), (20, 10), 2)
            for x, y, orientation in [(20, 12, -1), (21, 21, 1), (20, 26, -1)]:
                draw.polygon(surface, (98, 190, 152), [(x, y + 5), (x + orientation * 12, y - 5), (x + orientation * 12, y + 2)])
        elif kind == 'dryer':
            draw.line(surface, MUTED, (3, 46), (13, 17), 2)
            draw.line(surface, MUTED, (35, 46), (25, 17), 2)
            draw.line(surface, MUTED, (3, 18), (37, 18), 2)
            draw.rect(surface, (126, 126, 165), (8, 19, 11, 16))
            draw.rect(surface, (103, 171, 172), (23, 19, 10, 20))
            draw.line(surface, (174, 195, 192), (24, 20), (31, 20))
        elif kind == 'box':
            draw.rect(surface, (124, 92, 76), (7, 27, 29, 22))
            draw.rect(surface, (160, 119, 83), (7, 27, 29, 3))
            draw.rect(surface, GOLD, (19, 27, 5, 22))
        elif kind == 'radiator':
            draw.rect(surface, (47, 55, 77), (2, 26, 36, 23))
            for x in range(4, 37, 6):
                draw.rect(surface, (90, 83, 100), (x, 27, 4, 20))
                draw.line(surface, (142, 117, 115), (x, 27), (x, 46))
        else:
            draw.rect(surface, (60, 78, 93), (9, 16, 24, 32))
            draw.rect(surface, (136, 194, 190), (12, 20, 18, 15))
            draw.rect(surface, GOLD, (13, 38, 6, 3))
        self.cache[key] = surface
        return surface


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple
    size: int


class Renderer:
    MAX_PARTICLES = 90

    def __init__(self, canvas: pygame.Surface) -> None:
        self.canvas = canvas
        self.text = Text()
        self.sprites = Sprites()
        self.time = 0.0
        self.camera_x = self.camera_y = 0.0
        self.offset_x = self.offset_y = 0.0
        self.particles: list[Particle] = []
        self.rng = random.Random(427)
        self.shake = 0.0
        self.message = ''
        self.message_time = 0.0
        self.current_level = -1
        self._veil = pygame.Surface((W, H), pygame.SRCALPHA)
        self._vignette = pygame.Surface((W, H), pygame.SRCALPHA)
        for inset in range(15):
            pygame.draw.rect(self._vignette, (5, 9, 25, max(1, 22 - inset)),
                             (inset, inset, W - inset * 2, H - inset * 2), 1)
        self._glows: dict[tuple, pygame.Surface] = {}

    def reset_camera(self, level: Any) -> None:
        self.camera_x = max(0, min(level.width - W, level.player.box.center[0] - W * .35))
        self.camera_y = max(0, min(level.height - H, level.player.box.center[1] - H * .62))
        self.offset_x, self.offset_y = self.camera_x, self.camera_y
        self.particles.clear()
        self.shake = 0
        self.message = ''

    def point(self, x: float, y: float) -> tuple[int, int]:
        return round(x - self.offset_x), round(y - self.offset_y)

    def rect(self, box: Any) -> pygame.Rect:
        return pygame.Rect(*self.point(box.x, box.y), round(box.w), round(box.h))

    def glow(self, position: tuple[int, int], color: tuple, radius: int = 25) -> None:
        key = color, radius
        if key not in self._glows:
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            for r in range(radius, 0, -3):
                pygame.draw.circle(glow, (*color, int(3 + 21 * (1 - r / radius))),
                                   (radius, radius), r)
            self._glows[key] = glow
        self.canvas.blit(self._glows[key], (position[0] - radius, position[1] - radius))

    def tick(self, dt: float, settings: Any) -> None:
        self.time += dt
        self.message_time = max(0, self.message_time - dt)
        self.shake = max(0, self.shake - dt)
        for particle in self.particles:
            particle.life -= dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy += 90 * dt
        self.particles[:] = [particle for particle in self.particles if particle.life > 0]
        if settings.reduced_effects:
            self.particles[:] = self.particles[-20:]

    def accept_events(self, events: list[Any], settings: Any) -> None:
        for event in events:
            if event.kind in ('page', 'souvenir', 'checkpoint', 'land', 'died', 'win'):
                color = {'page': GOLD, 'checkpoint': MINT, 'land': MUTED,
                         'died': CORAL, 'win': GOLD, 'souvenir': MINT}[event.kind]
                count = 3 if event.kind == 'land' else 14
                if settings.reduced_effects:
                    count = min(count, 3)
                for _ in range(count):
                    self.particles.append(Particle(event.x, event.y,
                                                   self.rng.uniform(-55, 55),
                                                   self.rng.uniform(-95, -15),
                                                   self.rng.uniform(.2, .7), color,
                                                   self.rng.choice((1, 2, 2, 3))))
                self.particles[:] = self.particles[-self.MAX_PARTICLES:]
            if event.kind == 'died' and settings.shake and not settings.reduced_effects:
                self.shake = .18
            if event.text and event.kind in ('note', 'locked', 'checkpoint', 'detected', 'page', 'souvenir'):
                self.message = event.text
                self.message_time = 6 if event.kind == 'note' else 2.4

    def sky(self, camera_x: float = 0, reduced: bool = False) -> None:
        surface = self.canvas
        for y in range(0, H, 3):
            fraction = y / H
            pygame.draw.rect(surface, (int(16 + fraction * 12), int(25 + fraction * 10),
                                       int(45 + fraction * 13)), (0, y, W, 3))
        pygame.draw.circle(surface, (146, 172, 174), (540, 46), 15)
        pygame.draw.circle(surface, (23, 33, 54), (546, 40), 14)
        for layer in range(2):
            for index in range(-1, 16):
                x = int(index * 67 - (camera_x * (.08 + layer * .1)) % 67)
                height = 40 + ((index * 29 + layer * 31) % 80)
                y = 225 + layer * 24 - height
                color = (30 + layer * 5, 40 + layer * 4, 64 + layer * 8)
                pygame.draw.rect(surface, color, (x, y, 51, H - y))
                pygame.draw.rect(surface, color, (x + 8, y - 5, 30, 7))
                for wx in range(x + 7, x + 46, 10):
                    for wy in range(y + 12, 256, 15):
                        if (wx + wy + index) % 4 == 0:
                            pygame.draw.rect(surface, (113, 111, 98), (wx, wy, 3, 5))
        if not reduced:
            for i in range(55):
                x = int((i * 127 + self.time * 31) % (W + 20)) - 10
                y = int((i * 61 + self.time * 180) % (H + 20)) - 10
                pygame.draw.line(surface, (54, 75, 99), (x, y), (x - 3, y + 8))

    def window(self, x: int, y: int, index: int, big: bool = False) -> None:
        surface = self.canvas
        width, height = (92, 108) if big else (68, 76)
        pygame.draw.rect(surface, (15, 23, 42), (x - 4, y - 4, width + 8, height + 8))
        pygame.draw.rect(surface, (32, 46, 69), (x, y, width, height))
        for j in range(4):
            bx = x + 3 + j * (width // 4)
            bh = 12 + (j * 19 + index * 13) % 34
            pygame.draw.rect(surface, (43, 57, 80), (bx, y + height - bh, width // 4 - 2, bh))
            pygame.draw.rect(surface, (113, 132, 137), (bx + 5, y + height - bh + 8, 3, 4))
        for i in range(8):
            rx = x + 5 + (i * 23 + int(self.time * 12)) % (width - 10)
            ry = y + (i * 29 + int(self.time * 75)) % (height - 7)
            pygame.draw.line(surface, (80, 117, 140), (rx, ry), (rx - 2, ry + 6))
        pygame.draw.rect(surface, (95, 84, 103), (x + width // 2 - 2, y, 4, height))
        pygame.draw.rect(surface, (95, 84, 103), (x, y + height // 2, width, 3))
        pygame.draw.rect(surface, (144, 125, 128), (x - 6, y + height, width + 12, 5))
        pygame.draw.rect(surface, (98, 72, 98), (x - 2, y, 8, height - 9))
        pygame.draw.rect(surface, (116, 81, 103), (x + width - 6, y, 8, height - 9))

    def architecture(self, level: Any) -> None:
        surface = self.canvas
        # Здание — фон. Его дверцы и мебель не притворяются коллайдерами.
        surface.fill((36, 39, 62))
        for y in range(-48, int(level.height), 160):
            sy = self.point(0, y)[1]
            pygame.draw.rect(surface, (40, 43, 67), (0, sy, W, 153))
            pygame.draw.rect(surface, (54, 52, 76), (0, sy + 148, W, 5))
            pygame.draw.line(surface, (74, 60, 79), (0, sy + 155), (W, sy + 155))
        for wx in range(60, int(level.width), 180):
            sx, sy = self.point(wx, 213)
            if -100 < sx < W + 20:
                self.window(sx, sy, wx // 180)
                self.canvas.blit(self.sprites.object('radiator'), (sx + 14, sy + 87))
            sx, sy = self.point(wx, 38)
            if -100 < sx < W + 20:
                self.window(sx, sy, wx // 180 + 2)
        for wx in range(22, int(level.width), 240):
            sx, sy = self.point(wx, 185)
            if -20 < sx < W + 20:
                pygame.draw.rect(surface, (14, 31, 43), (sx, sy, 27, 8))
                pygame.draw.rect(surface, MINT, (sx + 3, sy + 2, 21, 3))
                self.glow((sx + 13, sy + 5), MINT, 32)
        # Труба, от которой и начался сюжет.
        y = self.point(0, 345)[1]
        pygame.draw.line(surface, (20, 31, 48), (0, y + 3), (W, y + 3), 7)
        pygame.draw.line(surface, (89, 103, 118), (0, y), (W, y), 5)
        pygame.draw.line(surface, (135, 140, 146), (0, y - 2), (W, y - 2))
        for x in range(0, int(level.width), 90):
            sx, _ = self.point(x, 0)
            pygame.draw.rect(surface, (49, 63, 80), (sx, y - 5, 5, 11))
        for decor in level.spec.get('decor', []):
            sx, sy = self.point(decor['x'], decor['y'])
            if not -100 < sx < W + 50:
                continue
            kind = decor.get('kind', 'plant')
            if kind in ('sign', 'poster'):
                caption = decor.get('text', 'Тише. Идёт защита.')
                max_width = 138 if kind == 'sign' else 105
                height = 36 if kind == 'sign' else 56
                pygame.draw.rect(surface, (20, 29, 47), (sx - 2, sy - 2, max_width + 4, height + 4))
                pygame.draw.rect(surface, (177, 153, 121) if kind == 'poster' else (53, 88, 99), (sx, sy, max_width, height))
                self.text.wrapped(surface, caption, (sx + 6, sy + 5), max_width - 12,
                                  9, INK if kind == 'poster' else WHITE, 12)
            else:
                surface.blit(self.sprites.object(kind), (sx, sy - 48))

    def solid(self, box: Any) -> None:
        rect = self.rect(box)
        if not rect.colliderect(self.canvas.get_rect()):
            return
        surface = self.canvas
        pygame.draw.rect(surface, (20, 27, 43), rect)
        pygame.draw.rect(surface, (79, 79, 96), (rect.x, rect.y, rect.w, min(5, rect.h)))
        pygame.draw.line(surface, (180, 175, 168), rect.topleft, (rect.right - 1, rect.top))
        pygame.draw.line(surface, (47, 56, 76), (rect.x, rect.y + 6), (rect.right - 1, rect.y + 6))
        if rect.h > 20:
            for row in range(max(0, rect.y + 13), min(H, rect.bottom), 19):
                pygame.draw.line(surface, (40, 43, 61), (max(0, rect.left), row), (min(W, rect.right), row))
                for x in range(rect.left + (12 if (row // 19) % 2 else 0), rect.right, 38):
                    pygame.draw.line(surface, (40, 43, 61), (x, row), (x, min(row + 19, rect.bottom)))
        else:
            pygame.draw.rect(surface, (51, 60, 80), (rect.x + 2, rect.bottom - 3, max(0, rect.w - 4), 3))

    def item(self, item: Any, kind: str, active: bool = False) -> None:
        surface = self.canvas
        rect = self.rect(item.box)
        if not rect.inflate(80, 80).colliderect(surface.get_rect()):
            return
        if kind == 'page':
            if item.collected:
                return
            rect.y += round(math.sin(self.time * 3.1 + item.box.x) * 2)
            self.glow(rect.center, GOLD, 19)
            pygame.draw.polygon(surface, (245, 230, 183), [(rect.x, rect.y), (rect.right - 4, rect.y), (rect.right, rect.y + 4), (rect.right, rect.bottom), (rect.x, rect.bottom)])
            pygame.draw.polygon(surface, (177, 150, 113), [(rect.right - 4, rect.y), (rect.right - 4, rect.y + 4), (rect.right, rect.y + 4)])
            for y in range(rect.y + 6, rect.bottom - 2, 4):
                pygame.draw.line(surface, (128, 117, 105), (rect.x + 3, y), (rect.right - 3, y))
        elif kind == 'souvenir':
            if item.collected:
                return
            rect.y += round(math.sin(self.time * 2.5) * 2)
            self.glow(rect.center, MINT, 23)
            if item.kind == 'badge':
                pygame.draw.rect(surface, (222, 211, 170), rect)
                pygame.draw.rect(surface, (58, 98, 112), (rect.x + 2, rect.y + 3, 5, 7))
                pygame.draw.line(surface, INK, (rect.x + 9, rect.y + 5), (rect.right - 2, rect.y + 5))
                pygame.draw.line(surface, INK, (rect.x + 2, rect.bottom - 4), (rect.right - 2, rect.bottom - 4))
            elif item.kind == 'mug':
                pygame.draw.rect(surface, MINT, (rect.x + 1, rect.y + 5, 11, 12))
                pygame.draw.rect(surface, MINT, (rect.x + 10, rect.y + 7, 6, 7), 2)
                pygame.draw.line(surface, WHITE, (rect.x + 4, rect.y + 2), (rect.x + 6, rect.y - 2))
            else:
                pygame.draw.rect(surface, MUTED, (rect.x + 5, rect.y, 7, 6))
                pygame.draw.rect(surface, (95, 172, 177), (rect.x + 2, rect.y + 5, 13, 12))
                pygame.draw.rect(surface, GOLD, (rect.x + 6, rect.y + 10, 5, 2))
            self.text.draw(surface, 'БОНУС', (rect.centerx, rect.y - 8), 7, MINT, center=True)
        elif kind == 'checkpoint':
            color = MINT if active else MUTED
            pygame.draw.rect(surface, (22, 34, 50), rect)
            pygame.draw.rect(surface, (59, 85, 100), (rect.x + 2, rect.y + 2, rect.w - 4, rect.h - 2))
            pygame.draw.rect(surface, color, (rect.x + 4, rect.y + 5, rect.w - 8, 12))
            pygame.draw.line(surface, INK, (rect.x + 7, rect.y + 11), (rect.x + 10, rect.y + 14), 2)
            pygame.draw.line(surface, INK, (rect.x + 10, rect.y + 14), (rect.right - 6, rect.y + 8), 2)
            pygame.draw.rect(surface, GOLD, (rect.centerx - 3, rect.bottom - 7, 6, 2))
            self.glow((rect.centerx, rect.y + 10), color, 23)
            self.text.draw(surface, 'СОХР.', (rect.centerx, rect.y - 7), 8, color, center=True)
        elif kind == 'note':
            pygame.draw.rect(surface, (123, 88, 67), rect.inflate(4, 4))
            pygame.draw.rect(surface, (218, 178, 124), rect)
            for y in range(rect.y + 4, rect.bottom - 2, 4):
                pygame.draw.line(surface, (94, 74, 66), (rect.x + 3, y), (rect.right - 3, y))
            self.text.draw(surface, 'E', (rect.centerx, rect.y - 9), 10, GOLD, True, True)
        elif kind == 'exit':
            color = MINT if active else GOLD
            pygame.draw.rect(surface, (12, 26, 40), rect.inflate(8, 5))
            pygame.draw.rect(surface, (59, 87, 95), rect, 2)
            pygame.draw.rect(surface, (23, 56, 65), rect.inflate(-6, -5))
            pygame.draw.rect(surface, color, (rect.x + 6, rect.y + 7, rect.w - 12, 13))
            pygame.draw.line(surface, INK, (rect.centerx - 5, rect.y + 13), (rect.centerx + 5, rect.y + 13), 2)
            pygame.draw.lines(surface, INK, False, [(rect.centerx + 1, rect.y + 9), (rect.centerx + 5, rect.y + 13), (rect.centerx + 1, rect.y + 17)], 2)
            pygame.draw.rect(surface, GOLD, (rect.right - 7, rect.centery + 7, 3, 3))
            self.text.draw(surface, 'ВЫХОД', (rect.centerx, rect.top - 10), 9, color, True, True)
            self.glow((rect.centerx, rect.top), color, 28)

    def draw_game(self, session: Any, settings: Any, dt: float = 0.0,
                  debug: bool = False, fps: float = 0, steps: int = 0) -> None:
        level = session.level
        if self.current_level != session.level_index:
            self.current_level = session.level_index
            self.reset_camera(level)
        target_x = max(0, min(level.width - W, level.player.box.center[0] - W * .42))
        target_y = max(0, min(level.height - H, level.player.box.center[1] - H * .63))
        smoothing = 1 - math.exp(-dt * 8)
        self.camera_x += (target_x - self.camera_x) * smoothing
        self.camera_y += (target_y - self.camera_y) * smoothing
        self.offset_x, self.offset_y = self.camera_x, self.camera_y
        if self.shake > 0 and settings.shake and not settings.reduced_effects:
            self.offset_x += self.rng.randint(-2, 2)
            self.offset_y += self.rng.randint(-2, 2)
        self.architecture(level)
        surface = self.canvas
        for solid in level.solids:
            self.solid(solid)
        for hazard in level.hazards:
            rect = self.rect(hazard.box)
            if not rect.colliderect(surface.get_rect()):
                continue
            pygame.draw.rect(surface, (29, 97, 122), rect)
            pygame.draw.line(surface, MINT, rect.topleft, rect.topright, 2)
            for x in range(rect.x, rect.right, 12):
                y = rect.y + 5 + int(math.sin(self.time * 4 + x * .2) * 2)
                pygame.draw.line(surface, (81, 170, 180), (x, y), (min(x + 6, rect.right), y))
            for x in range(rect.x + 6, rect.right, 28):
                pygame.draw.lines(surface, GOLD, False, [(x, rect.y - 2), (x + 3, rect.y - 8), (x + 7, rect.y - 6), (x + 9, rect.y - 13)], 1)
        for platform in level.platforms:
            rect = self.rect(platform.box)
            pygame.draw.rect(surface, (21, 47, 57), rect)
            pygame.draw.rect(surface, MINT, (rect.x, rect.y, rect.w, 3))
            for x in range(rect.x + 4, rect.right - 4, 10):
                pygame.draw.line(surface, (82, 134, 140), (x, rect.y + 5), (x + 4, rect.y + 8))
            pygame.draw.circle(surface, GOLD, (rect.centerx, rect.centery + 2), 2)
        for page in level.pages:
            self.item(page, 'page')
        for souvenir in level.souvenirs:
            self.item(souvenir, 'souvenir')
        for checkpoint in level.checkpoints:
            self.item(checkpoint, 'checkpoint', checkpoint.active)
        for note in level.notes:
            self.item(note, 'note')
        remaining = sum(not page.collected for page in level.pages)
        self.item(level.exit, 'exit', remaining == 0)
        for enemy in level.enemies:
            x, y = self.point(enemy.box.x, enemy.box.y)
            if enemy.kind == 'drone':
                y += round(math.sin(self.time * 6) * 1)
                surface.blit(self.sprites.actor('drone', enemy.facing, int(self.time * 18) % 2), (x - 8, y - 12))
                if enemy.state == 'Погоня':
                    self.text.draw(surface, '!', (x + 9, y - 15), 13, CORAL, True, True)
            else:
                surface.blit(self.sprites.actor('patrol', enemy.facing, int(self.time * 7) % 4), (x - 8, y - 9))
        player = level.player
        x, y = self.point(player.box.x, player.box.y)
        frame = 4 if not player.grounded else (
            int(self.time * 12) % 4 if abs(player.vx) > 8 else 5 + int(self.time * 1.6) % 2)
        shield = level.invulnerable
        if not shield or int(self.time * 12) % 3:
            surface.blit(self.sprites.actor('student', player.facing, frame), (x - 9, y - 9))
        for particle in self.particles:
            pygame.draw.rect(surface, particle.color, (*self.point(particle.x, particle.y), particle.size, particle.size))
        if debug:
            self.draw_debug(level, fps, steps)
        surface.blit(self._vignette, (0, 0))
        self.hud(session, remaining, settings)

    def hud(self, session: Any, remaining: int, settings: Any) -> None:
        surface = self.canvas
        pygame.draw.rect(surface, INK, (10, 9, 620, 41), border_radius=4)
        pygame.draw.rect(surface, (47, 65, 83), (10, 9, 620, 41), 1, border_radius=4)
        self.text.draw(surface, f'0{session.level_index + 1} / 03', (21, 15), 10, MINT, True)
        name = session.level.name.split('. ', 1)[-1]
        self.text.draw(surface, name, (21, 29), 10, WHITE)
        pygame.draw.line(surface, (55, 69, 87), (277, 18), (277, 41))
        collected = len(session.level.pages) - remaining
        self.text.draw(surface, 'КУРСОВАЯ', (292, 14), 8, MUTED)
        self.text.draw(surface, f'{collected} / {len(session.level.pages)} стр.', (292, 26), 12, GOLD, True)
        self.text.draw(surface, 'ВРЕМЯ', (410, 14), 8, MUTED)
        self.text.draw(surface, time_text(session.elapsed), (410, 26), 12, WHITE, True)
        self.text.draw(surface, 'ПАДЕНИЯ', (496, 14), 8, MUTED)
        self.text.draw(surface, str(session.deaths), (496, 26), 12, CORAL, True)
        self.text.draw(surface, 'II  Esc', (573, 26), 10, MUTED)
        pygame.draw.rect(surface, INK, (0, H - 18, W, 18))
        self.text.draw(surface, 'A / D  движение     Пробел  прыжок     E  действие     R  к сохранению', (13, H - 15), 9, MUTED)
        self.text.draw(surface, 'F3  схема', (W - 68, H - 15), 9, MINT)
        self.text.draw(surface, f'Набор студента  {session.total_souvenirs}/{session.souvenir_goal}',
                       (355, 55), 9, MINT)
        if not settings.sound:
            self.text.draw(surface, 'ЗВУК ВЫКЛ.', (W - 87, 57), 8, MUTED)
        player = session.level.player.box
        exit_box = session.level.exit.box
        if abs(player.center[0] - exit_box.center[0]) < 70 and abs(player.center[1] - exit_box.center[1]) < 65:
            hint = 'E  На следующий этаж' if remaining == 0 else f'Нужно ещё {remaining} стр.'
            if session.level_index == 2 and remaining == 0:
                hint = 'E  На крышу!'
            self.text.draw(surface, hint, (W / 2, H - 32), 12, GOLD, True, True)
        if self.message_time > 0 and self.message:
            width = 450
            self._veil.fill((0, 0, 0, 0))
            pygame.draw.rect(self._veil, (14, 23, 40, 238), (95, 281, width, 52), border_radius=4)
            surface.blit(self._veil, (0, 0))
            pygame.draw.rect(surface, GOLD, (95, 285, 2, 44))
            self.text.wrapped(surface, self.message, (107, 290), width - 24, 11, WHITE, 15)

    def draw_debug(self, level: Any, fps: float, steps: int) -> None:
        surface = self.canvas
        for solid in level.solids:
            pygame.draw.rect(surface, (244, 142, 213), self.rect(solid), 1)
        for collection in (level.pages, level.souvenirs, level.checkpoints, level.notes, level.hazards, level.platforms):
            for item in collection:
                pygame.draw.rect(surface, GOLD, self.rect(item.box), 1)
        pygame.draw.rect(surface, WHITE, self.rect(level.player.box), 1)
        pygame.draw.rect(surface, MINT, self.rect(level.exit.box), 1)
        for enemy in level.enemies:
            pygame.draw.rect(surface, CORAL, self.rect(enemy.box), 1)
            if enemy.kind == 'drone':
                nav = enemy.nav
                cx = int(enemy.box.center[0] // nav.cell_size)
                cy = int(enemy.box.center[1] // nav.cell_size)
                for row in range(max(0, cy - 9), min(nav.rows, cy + 10)):
                    for col in range(max(0, cx - 12), min(nav.cols, cx + 13)):
                        x, y = self.point(col * nav.cell_size, row * nav.cell_size)
                        color = (53, 115, 110) if (col, row) in nav.walkable else (114, 56, 83)
                        pygame.draw.rect(surface, color, (x + 1, y + 1, nav.cell_size - 2, nav.cell_size - 2), 1)
                points = [self.point(*enemy.box.center)] + [self.point(*nav.cell_center(cell)) for cell in enemy.path]
                if len(points) > 1:
                    pygame.draw.lines(surface, GOLD, False, points, 2)
                    for point in points[1:]:
                        pygame.draw.circle(surface, WHITE, point, 2)
                caption = f'{enemy.state} • раскрыто: {enemy.expanded}'
            else:
                caption = enemy.state
            x, y = self.point(enemy.box.center[0], enemy.box.y - 19)
            self.text.draw(surface, caption, (x, y), 9, WHITE, center=True)
        pygame.draw.rect(surface, INK, (10, 57, 275, 49))
        self.text.draw(surface, f'F3  Диагностика     {fps:4.0f} FPS     шагов: {steps}', (17, 62), 10, MINT)
        self.text.draw(surface, 'Розовый: стены   Жёлтый: маршрут A*', (17, 79), 9, WHITE)
        self.text.draw(surface, 'Сетка: зазор с учётом размеров дрона', (17, 92), 8, MUTED)

    def backdrop(self, settings: Any) -> None:
        self.sky(self.time * 4, settings.reduced_effects)
        surface = self.canvas
        # Небольшой разрез общаги на титульном экране.
        pygame.draw.rect(surface, (16, 24, 41), (332, 47, 270, 268))
        pygame.draw.rect(surface, (55, 51, 72), (344, 51, 248, 256))
        for floor in range(3):
            y = 58 + floor * 77
            pygame.draw.rect(surface, (78, 65, 85), (343, y + 70, 250, 7))
            for room in range(3):
                x = 355 + room * 77
                lit = (floor + room) % 3 != 0
                pygame.draw.rect(surface, (20, 33, 50), (x, y + 8, 61, 54))
                pygame.draw.rect(surface, (139, 105, 87) if lit else (40, 66, 86), (x + 3, y + 11, 55, 48))
                if lit:
                    pygame.draw.rect(surface, (214, 165, 108), (x + 8, y + 14, 44, 20))
                    pygame.draw.rect(surface, (113, 90, 91), (x + 7, y + 36, 46, 20))
                    self.glow((x + 30, y + 31), GOLD, 32)
                pygame.draw.rect(surface, (26, 36, 54), (x + 29, y + 8, 3, 54))
                pygame.draw.rect(surface, (96, 81, 95), (x - 2, y + 62, 65, 3))
                if floor == 1 and room == 2:
                    surface.blit(self.sprites.object('plant'), (x + 8, y + 13))
        pygame.draw.rect(surface, (91, 106, 121), (329, 43, 276, 6))
        pygame.draw.rect(surface, MINT, (350, 297, 235, 3))
        pygame.draw.rect(surface, (19, 35, 49), (328, 307, 282, 15))
        for x in range(340, 601, 12):
            pygame.draw.line(surface, (50, 106, 123), (x, 315), (x + 6, 315))
        pygame.draw.line(surface, (152, 142, 146), (343, 277), (585, 277), 2)
        for x in range(344, 592, 30):
            pygame.draw.line(surface, (115, 109, 126), (x, 277), (x, 300), 2)
        surface.blit(self.sprites.actor('student', 1, int(self.time * 2) % 2), (437, 263))
        surface.blit(self.sprites.actor('drone', -1, int(self.time * 12) % 2), (535, 155 + int(math.sin(self.time * 2) * 6)))
        pygame.draw.line(surface, (64, 70, 95), (370, 28), (370, 42), 2)
        pygame.draw.line(surface, (64, 70, 95), (359, 32), (381, 32), 2)
        for i in range(3):
            py = 180 + i * 21 + int(math.sin(self.time * 2 + i) * 3)
            pygame.draw.rect(surface, GOLD, (468 - i * 16, py, 8, 11))
            pygame.draw.line(surface, (147, 118, 93), (470 - i * 16, py + 4), (473 - i * 16, py + 4))
        self.text.draw(surface, '03', (575, 35), 10, MINT, True)
        surface.blit(self._vignette, (0, 0))

    def buttons(self, labels: list[str], selected: int,
                x: int, y: int, width: int, height: int = 29,
                gap: int = 7) -> list[pygame.Rect]:
        rects = []
        for index, label in enumerate(labels):
            rect = pygame.Rect(x, y + index * (height + gap), width, height)
            rects.append(rect)
            active = index == selected
            pygame.draw.rect(self.canvas, MINT if active else PANEL, rect, border_radius=3)
            if not active:
                pygame.draw.rect(self.canvas, (59, 73, 92), rect, 1, border_radius=3)
            self.text.draw(self.canvas, label, (x + 14, rect.y + (height - 16) // 2), 12,
                           INK if active else WHITE, active)
            if active:
                self.text.draw(self.canvas, '›', (rect.right - 22, rect.y + 3), 17, INK, True)
        return rects

    def front_menu(self, selected: int, settings: Any) -> list[pygame.Rect]:
        self.backdrop(settings)
        self.text.draw(self.canvas, 'НОЧЬ ПЕРЕД ЗАЩИТОЙ', (39, 35), 9, MINT, True)
        self.text.draw(self.canvas, 'ОБЩАГА', (35, 51), 48, WHITE, True)
        self.text.draw(self.canvas, 'пять минут до выселения', (39, 110), 15, GOLD)
        self.text.wrapped(self.canvas, 'Трубу прорвало. Курсовую унесло.\nОсталось добраться до крыши.', (40, 144), 270, 11, MUTED, 17)
        buttons = self.buttons(['Начать историю', 'Управление', 'Настройки', 'Выйти'],
                               selected, 40, 194, 250, 27, 7)
        self.text.draw(self.canvas, '↑ ↓  выбрать    Enter  открыть', (41, 337), 9, MUTED)
        self.text.draw(self.canvas, 'byVanoGame', (501, 336), 11, MINT, True)
        return buttons

    def shade(self, alpha: int = 190) -> None:
        self._veil.fill((7, 13, 27, alpha))
        self.canvas.blit(self._veil, (0, 0))

    def panel(self, title: str, subtitle: str, labels: list[str], selected: int,
              top: int = 85) -> list[pygame.Rect]:
        self.shade()
        height = 90 + len(labels) * 37
        pygame.draw.rect(self.canvas, PANEL, (142, top - 20, 356, height), border_radius=6)
        pygame.draw.rect(self.canvas, (65, 82, 101), (142, top - 20, 356, height), 1, border_radius=6)
        pygame.draw.rect(self.canvas, MINT, (165, top - 20, 44, 2))
        self.text.draw(self.canvas, title, (W // 2, top + 4), 24, WHITE, True, True)
        self.text.draw(self.canvas, subtitle, (W // 2, top + 33), 10, MUTED, center=True)
        return self.buttons(labels, selected, 174, top + 58, 292)

    def controls(self, selected: int) -> list[pygame.Rect]:
        self.shade(220)
        self.text.draw(self.canvas, 'Как спасти курсовую', (W // 2, 39), 25, WHITE, True, True)
        controls = [('A / D   ← / →', 'Двигаться'), ('Пробел', 'Прыгать: дольше держишь — выше'),
                    ('E', 'Читать записки / открыть выход'), ('R', 'Вернуться к контрольной точке'),
                    ('Esc', 'Пауза: время тоже остановится'), ('F3', 'Коллизии, сетка и маршрут A*'),
                    ('M', 'Включить / выключить звук')]
        for index, (key, value) in enumerate(controls):
            y = 82 + index * 26
            pygame.draw.rect(self.canvas, PANEL, (74, y - 2, 492, 24), border_radius=2)
            self.text.draw(self.canvas, key, (87, y + 2), 11, MINT, True)
            self.text.draw(self.canvas, value, (212, y + 2), 11, WHITE)
        self.text.draw(self.canvas, 'Собери все страницы этажа. Терминал сохранит точку возврата.', (320, 277), 10, GOLD, center=True)
        return self.buttons(['Всё понятно'], selected, 211, 302, 218)

    def intro(self, selected: int, settings: Any) -> list[pygame.Rect]:
        self.backdrop(settings)
        self.shade(215)
        self.text.draw(self.canvas, '23:55  /  ОБЩЕЖИТИЕ № 5', (320, 49), 10, MINT, True, True)
        self.text.draw(self.canvas, 'До защиты была одна ночь.', (320, 89), 25, WHITE, True, True)
        self.text.wrapped(self.canvas,
                          'Теперь ещё и трубу прорвало. Система объявила эвакуацию, '
                          'дроны решили навести порядок, а сквозняк разнёс твою курсовую по трём этажам.',
                          (112, 124), 416, 13, WHITE, 22)
        self.text.wrapped(self.canvas,
                          'На крыше ждёт друг с запасным ноутбуком. Собери страницы и доберись до него. '
                          'Пять минут — это настроение. Таймер тебя не выгонит.',
                          (112, 205), 416, 12, MUTED, 19)
        return self.buttons(['За курсовой!  /  Пропустить'], selected, 174, 300, 292)

    def transition(self, session: Any, selected: int) -> list[pygame.Rect]:
        next_names = ('Комендантский час', 'До крыши рукой подать')
        lines = ('Лифт не работает с 2008-го. Сегодня традицию не нарушаем.',
                 'Вода поднялась до второго этажа. А стипендия — нет.')
        self.shade(215)
        self.text.draw(self.canvas, 'ЭТАЖ ПРОЙДЕН', (320, 82), 11, MINT, True, True)
        self.text.draw(self.canvas, 'Курсовая стала чуть полнее.', (320, 123), 26, WHITE, True, True)
        self.text.draw(self.canvas, lines[min(session.level_index, 1)], (320, 172), 11, GOLD, center=True)
        self.text.draw(self.canvas, 'Дальше: ' + next_names[min(session.level_index, 1)], (320, 216), 14, WHITE, center=True)
        return self.buttons(['Подняться выше'], selected, 208, 269, 224)

    def ending(self, session: Any, selected: int, settings: Any) -> list[pygame.Rect]:
        self.sky(0, settings.reduced_effects)
        surface = self.canvas
        pygame.draw.rect(surface, (52, 61, 78), (0, 190, W, 170))
        pygame.draw.rect(surface, (127, 144, 152), (0, 187, W, 4))
        for x in range(0, W, 32):
            pygame.draw.line(surface, (40, 51, 68), (x, 202), (x, H))
        surface.blit(self.sprites.actor('student', 1, 0), (273, 153))
        surface.blit(self.sprites.actor('student', -1, 0), (333, 153))
        pygame.draw.rect(surface, (92, 148, 161), (307, 169, 20, 14))
        pygame.draw.rect(surface, MINT, (309, 171, 16, 9))
        pygame.draw.rect(surface, (174, 210, 208), (304, 183, 27, 3))
        self.glow((318, 175), MINT, 38)
        self.text.draw(surface, 'КРЫША. СВЯЗЬ ЕСТЬ.', (320, 25), 10, MINT, True, True)
        self.text.draw(surface, 'Курсовая спасена!', (320, 63), 34, WHITE, True, True)
        self.text.draw(surface, '«Ноутбук сухой. Теперь главное — вспомнить пароль».', (320, 106), 12, GOLD, center=True)
        bonus_line = (f'Набор студента: {session.total_souvenirs}/{session.souvenir_goal}. '
                      + ('Билет, кружка и резервная копия спасены!' if session.total_souvenirs == session.souvenir_goal
                         else 'За сувенирами можно вернуться в новой игре.'))
        self.text.draw(surface, bonus_line, (320, 134), 10, MINT, center=True)
        values = [('ВРЕМЯ', time_text(session.elapsed)), ('ПАДЕНИЯ', str(session.deaths)),
                  ('СТРАНИЦЫ', str(session.total_pages))]
        for index, (label, value) in enumerate(values):
            x = 167 + index * 154
            self.text.draw(surface, label, (x, 218), 9, MUTED, center=True)
            self.text.draw(surface, value, (x, 243), 24, WHITE, True, True)
        return self.buttons(['Ещё одна ночь', 'Главное меню'], selected, 200, 283, 240, 27, 7)
