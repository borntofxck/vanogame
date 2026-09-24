"""Оригинальные короткие синтезированные звуки; устройство необязательно."""
from __future__ import annotations

from array import array
import math

import pygame


class Audio:
    SAMPLE_RATE = 22050

    def __init__(self) -> None:
        self.available = False
        self.enabled = True
        self.music_enabled = True
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: pygame.mixer.Sound | None = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.SAMPLE_RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(12)
            pygame.mixer.set_reserved(1)
            self.available = True
            specs = {
                'jump': (240, 610, .15), 'land': (105, 50, .09),
                'page': (659, 1320, .18), 'checkpoint': (440, 880, .30),
                'detected': (300, 510, .19), 'died': (190, 65, .26),
                'win': (523, 1046, .65), 'exit': (523, 784, .35),
                'locked': (150, 120, .10), 'note': (440, 540, .12),
                'souvenir': (784, 1568, .28),
            }
            for name, (start, end, length) in specs.items():
                self.sounds[name] = self._tone(start, end, length)
            self.music = self._make_music()
        except (pygame.error, ValueError):
            self.available = False

    @staticmethod
    def _pcm(values: list[float]) -> bytes:
        data = array('h')
        for value in values:
            sample = round(max(-1, min(1, value)) * 32767)
            data.extend((sample, sample))
        return data.tobytes()

    def _tone(self, start: float, end: float, length: float) -> pygame.mixer.Sound:
        values = []
        phase = 0.0
        count = int(self.SAMPLE_RATE * length)
        for i in range(count):
            p = i / count
            phase += 2 * math.pi * (start + (end - start) * p) / self.SAMPLE_RATE
            envelope = min(1, p * 25) * (1 - p) ** 1.5
            wave = math.sin(phase) * .8 + math.sin(phase * 2) * .2
            values.append(wave * envelope * .23)
        return pygame.mixer.Sound(buffer=self._pcm(values))

    def _make_music(self) -> pygame.mixer.Sound:
        # Своя спокойная фраза в ля-миноре. Ноты затухают до границы лупа.
        beat = .42
        melody = (440, 0, 523.25, 659.25, 587.33, 0, 523.25, 0,
                  349.23, 0, 440, 523.25, 392, 0, 329.63, 0)
        count = int(self.SAMPLE_RATE * beat * len(melody))
        values = [0.0] * count
        for index, frequency in enumerate(melody):
            if not frequency:
                continue
            offset = int(index * beat * self.SAMPLE_RATE)
            for sample in range(int(beat * 1.7 * self.SAMPLE_RATE)):
                if offset + sample >= count:
                    break
                t = sample / self.SAMPLE_RATE
                envelope = min(1, t / .015) * math.exp(-t * 7)
                values[offset + sample] += math.sin(2 * math.pi * frequency * t) * envelope * .13
        for chord, frequency in enumerate((110, 87.31, 130.81, 98)):
            offset = int(chord * beat * 4 * self.SAMPLE_RATE)
            for sample in range(int(beat * 4 * self.SAMPLE_RATE)):
                if offset + sample >= count:
                    break
                t = sample / self.SAMPLE_RATE
                envelope = math.sin(math.pi * t / (beat * 4)) ** 2
                values[offset + sample] += (math.sin(2 * math.pi * frequency * t)
                                            + .3 * math.sin(4 * math.pi * frequency * t)) * envelope * .035
        return pygame.mixer.Sound(buffer=self._pcm(values))

    def configure(self, enabled: bool, music_enabled: bool) -> None:
        self.enabled, self.music_enabled = enabled, music_enabled
        if not self.available:
            return
        channel = pygame.mixer.Channel(0)
        if enabled and music_enabled and self.music:
            if not channel.get_busy():
                channel.play(self.music, loops=-1)
            channel.set_volume(.45)
        else:
            channel.stop()
        if not enabled:
            for channel_id in range(1, 12):
                pygame.mixer.Channel(channel_id).stop()

    def play(self, name: str) -> None:
        if self.available and self.enabled and name in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.play(self.sounds[name])
