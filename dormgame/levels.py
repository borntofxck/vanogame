"""Загрузка и строгая проверка трёх ручных карт из JSON."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .config import (DRONE_HEIGHT, DRONE_WIDTH, PATROL_HEIGHT, PATROL_WIDTH,
                     PLAYER_HEIGHT, PLAYER_WIDTH)
from .geometry import AABB

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_level(spec: dict[str, Any]) -> None:
    """Не исправляем неверную карту молча: указываем объект с ошибкой."""
    for key in ('name', 'subtitle', 'width', 'height', 'start', 'solids',
                'pages', 'checkpoints', 'notes', 'hazards', 'platforms', 'enemies', 'exit'):
        if key not in spec:
            raise ValueError(f'Нет обязательного поля: {key}')
    for key in ('name', 'subtitle'):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError(f'Пустая строка {key}')
    width, height = spec['width'], spec['height']
    if not all(_number(v) and 0 < v <= 4096 for v in (width, height)):
        raise ValueError('Неверный размер уровня')
    identifiers: set[str] = set()

    def point(value: Any, label: str) -> None:
        if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(_number(v) for v in value):
            raise ValueError(f'Неверная точка {label}')
        if not (0 <= value[0] < width and 0 <= value[1] < height):
            raise ValueError(f'Точка за границами: {label}')

    def rect(value: Any, label: str) -> AABB:
        if not isinstance(value, (list, tuple)) or len(value) != 4 or not all(_number(v) for v in value):
            raise ValueError(f'Неверный прямоугольник: {label}')
        x, y, w, h = value
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
            raise ValueError(f'Прямоугольник за границами: {label}')
        return AABB(*value)

    def identify(obj: Any, label: str) -> None:
        if not isinstance(obj, dict) or not isinstance(obj.get('id'), str) or not obj['id']:
            raise ValueError(f'Нет идентификатора: {label}')
        if obj['id'] in identifiers:
            raise ValueError(f'Повтор идентификатора: {obj["id"]}')
        identifiers.add(obj['id'])

    point(spec['start'], 'start')
    for group in ('solids', 'pages', 'checkpoints', 'notes', 'hazards', 'platforms', 'enemies'):
        if not isinstance(spec[group], list):
            raise ValueError(f'{group} должен быть списком')
    solids = [rect(value, f'solids[{i}]') for i, value in enumerate(spec['solids'])]
    if not isinstance(spec.get('souvenirs', []), list):
        raise ValueError('souvenirs должен быть списком')
    for obj in spec.get('souvenirs', []):
        identify(obj, 'souvenir')
        box = rect(obj.get('rect'), obj['id'])
        if obj.get('kind') not in ('badge', 'mug', 'usb'):
            raise ValueError(f'Неизвестный сувенир: {obj.get("kind")}')
        if not isinstance(obj.get('text'), str):
            raise ValueError(f'Нет подписи сувенира: {obj["id"]}')
        if any(box.intersects(solid) for solid in solids):
            raise ValueError(f'Сувенир внутри стены: {obj["id"]}')
    if not spec['pages'] or not spec['checkpoints'] or not spec['notes']:
        raise ValueError('Нужны страницы, контрольная точка и записка')
    for group in ('pages', 'checkpoints', 'notes', 'hazards'):
        for obj in spec[group]:
            identify(obj, group)
            rect(obj.get('rect'), obj['id'])
            if 'text' in obj and not isinstance(obj['text'], str):
                raise ValueError(f'Неверный текст: {obj["id"]}')
            if group == 'checkpoints':
                point(obj.get('spawn'), obj['id'])
    identify(spec['exit'], 'exit')
    rect(spec['exit'].get('rect'), 'exit')
    for obj in spec['platforms']:
        identify(obj, 'platform')
        box = rect(obj.get('rect'), obj['id'])
        point(obj.get('end'), obj['id'])
        rect([*obj['end'], box.w, box.h], obj['id'] + '/end')
        if not _number(obj.get('speed')) or not 0 < obj['speed'] <= 100:
            raise ValueError(f'Неверная скорость платформы: {obj["id"]}')
        if obj['end'][0] != box.x and obj['end'][1] != box.y:
            raise ValueError('В этой игре платформы движутся вдоль одной оси')
        end_x, end_y = obj['end']
        swept = AABB(min(box.x, end_x), min(box.y, end_y),
                     abs(box.x - end_x) + box.w, abs(box.y - end_y) + box.h)
        if any(swept.intersects(solid) for solid in solids):
            raise ValueError(f'Маршрут платформы проходит через стену: {obj["id"]}')
    for obj in spec['enemies']:
        identify(obj, 'enemy')
        if obj.get('kind') not in ('patrol', 'drone'):
            raise ValueError(f'Неизвестный тип врага: {obj.get("kind")}')
        point([obj.get('x'), obj.get('y')], obj['id'])
        size = (PATROL_WIDTH, PATROL_HEIGHT) if obj['kind'] == 'patrol' else (DRONE_WIDTH, DRONE_HEIGHT)
        enemy_box = rect([obj['x'], obj['y'], *size], obj['id'])
        if any(enemy_box.intersects(solid) for solid in solids):
            raise ValueError(f'Враг появляется в стене: {obj["id"]}')
        if obj['kind'] == 'patrol':
            if not all(_number(obj.get(k)) for k in ('left', 'right')) or not 0 <= obj['left'] < obj['right'] <= width:
                raise ValueError(f'Неверный патруль: {obj["id"]}')
            if not obj['left'] <= enemy_box.left < enemy_box.right <= obj['right']:
                raise ValueError(f'Враг появляется вне своего патруля: {obj["id"]}')
        else:
            if not isinstance(obj.get('route'), list) or not obj['route']:
                raise ValueError(f'Нет маршрута: {obj["id"]}')
            for waypoint in obj['route']:
                point(waypoint, obj['id'])
    for label, p in [('start', spec['start'])] + [(o['id'], o['spawn']) for o in spec['checkpoints']]:
        box = rect([*p, PLAYER_WIDTH, PLAYER_HEIGHT], label)
        if any(box.intersects(solid) for solid in solids):
            raise ValueError(f'Точка появления в стене: {label}')
        if any(box.intersects(AABB(*obj['rect'])) for obj in spec['hazards']):
            raise ValueError(f'Точка появления в опасности: {label}')


def load_levels(directory: Path = DATA_DIR) -> list[dict[str, Any]]:
    levels = [json.loads((directory / f'level{i}.json').read_text(encoding='utf-8')) for i in range(1, 4)]
    for level in levels:
        validate_level(level)
    return levels
