"""Проверки правил сеанса: события, сохранение и полный цикл трёх карт."""
import copy
import subprocess
import sys
import unittest

from dormgame.commands import Commands
from dormgame.config import FIXED_DT, RESPAWN_SHIELD
from dormgame.geometry import AABB
from dormgame.levels import load_levels, validate_level
from dormgame.model import GameSession


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.game = GameSession()

    def touch(self, item):
        self.game.level.player.box.x = item.box.x
        self.game.level.player.box.y = item.box.y - 4
        self.game.level.player.vy = 0.0

    def test_page_collected_once_across_many_steps(self):
        page = self.game.level.pages[0]
        self.touch(page)
        for _ in range(15):
            self.game.update(FIXED_DT, Commands())
        self.assertTrue(page.collected)
        self.assertEqual(self.game.total_pages, 1)
        self.assertEqual(sum(e.kind == 'page' for e in self.game.drain_events()), 1)
        self.assertEqual(self.game.drain_events(), [])

    def test_optional_souvenir_is_unique_and_survives_respawn(self):
        souvenir = self.game.level.souvenirs[0]
        self.touch(souvenir)
        for _ in range(10):
            self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.total_souvenirs, 1)
        self.assertEqual(sum(e.kind == 'souvenir' for e in self.game.drain_events()), 1)
        self.game.level.reset_cooldown = 0
        self.game.update(FIXED_DT, Commands(reset=True))
        self.assertEqual(self.game.total_souvenirs, 1)
        self.game.new_game()
        self.assertEqual(self.game.total_souvenirs, 0)

    def test_souvenirs_accumulate_across_levels_and_do_not_lock_exit(self):
        for index in range(3):
            self.touch(self.game.level.souvenirs[0])
            self.game.update(FIXED_DT, Commands())
            for page in self.game.level.pages:
                page.collected = True
            self.touch(self.game.level.exit)
            self.game.update(FIXED_DT, Commands(interact=True))
            self.game.advance_level()
            self.assertEqual(self.game.total_souvenirs, index + 1)
        self.assertTrue(self.game.finished)
        self.assertEqual(self.game.souvenir_goal, 3)

    def test_checkpoint_and_death_preserve_pages_reset_enemies_and_platforms(self):
        self.game.level.pages[0].collected = True
        checkpoint = self.game.level.checkpoints[0]
        self.touch(checkpoint)
        self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.level.checkpoint_id, checkpoint.id)
        self.game.level.enemies[0].box.x += 30
        self.game.level.reset_cooldown = 0.0
        self.game.update(FIXED_DT, Commands(reset=True))
        self.assertEqual(self.game.deaths, 1)
        self.assertEqual(self.game.total_pages, 1)
        self.assertEqual(self.game.level.player.box.x, checkpoint.spawn[0])
        self.assertEqual(self.game.level.player.box.y, checkpoint.spawn[1])
        self.assertEqual(self.game.level.enemies[0].box.x, self.game.level.spec['enemies'][0]['x'])
        self.assertEqual(self.game.level.invulnerable, RESPAWN_SHIELD)

    def test_reset_has_short_cooldown(self):
        self.game.level.reset_cooldown = 0.0
        self.game.update(FIXED_DT, Commands(reset=True))
        for _ in range(20):
            self.game.update(FIXED_DT, Commands(reset=True))
        self.assertEqual(self.game.deaths, 1)

    def test_hazard_enemy_and_fall_each_cause_one_death(self):
        level = self.game.level
        level.invulnerable = 0.0
        self.touch(level.hazards[0])
        self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.deaths, 1)
        level.invulnerable = 0.0
        self.touch(level.enemies[0])
        self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.deaths, 2)
        level.player.box.y = level.height + 60
        self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.deaths, 3)

    def test_spawn_shield_prevents_contact_repeat(self):
        self.touch(self.game.level.enemies[0])
        self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.deaths, 0)

    def test_exit_closed_until_all_pages_collected(self):
        level = self.game.level
        self.touch(level.exit)
        self.game.update(FIXED_DT, Commands(interact=True))
        self.assertFalse(level.complete)
        events = self.game.drain_events()
        self.assertEqual(events[-1].kind, 'locked')
        self.assertIn(str(len(level.pages)), events[-1].text)
        for page in level.pages:
            page.collected = True
        self.game.update(FIXED_DT, Commands(interact=True))
        self.assertTrue(level.complete)

    def test_exit_requires_interaction(self):
        for page in self.game.level.pages:
            page.collected = True
        self.touch(self.game.level.exit)
        self.game.update(FIXED_DT, Commands())
        self.assertFalse(self.game.level.complete)

    def test_note_interaction_produces_story(self):
        note = self.game.level.notes[0]
        self.touch(note)
        self.game.update(FIXED_DT, Commands(interact=True))
        self.assertTrue(note.active)
        self.assertIn(note.text, [e.text for e in self.game.drain_events()])

    def test_pause_stops_all_timers_and_motion(self):
        self.game.update(FIXED_DT, Commands(move=1))
        before = (self.game.elapsed, self.game.level.player.box.copy(),
                  self.game.level.invulnerable, self.game.level.reset_cooldown)
        self.game.paused = True
        for _ in range(100):
            self.game.update(0.1, Commands(move=1, reset=True, jump_pressed=True))
        after = (self.game.elapsed, self.game.level.player.box,
                 self.game.level.invulnerable, self.game.level.reset_cooldown)
        self.assertEqual(before, after)

    def test_three_levels_final_statistics_and_new_game(self):
        expected_pages = sum(len(s['pages']) for s in self.game.specs)
        for index in range(3):
            self.assertEqual(self.game.level_index, index)
            for page in self.game.level.pages:
                page.collected = True
            self.touch(self.game.level.exit)
            self.game.update(FIXED_DT, Commands(interact=True))
            self.game.advance_level()
        self.assertTrue(self.game.finished)
        self.assertEqual(self.game.total_pages, expected_pages)
        final_time = self.game.elapsed
        self.game.update(FIXED_DT, Commands())
        self.assertEqual(self.game.elapsed, final_time)
        self.game.new_game()
        self.assertFalse(self.game.finished)
        self.assertEqual((self.game.level_index, self.game.total_pages, self.game.deaths, self.game.elapsed), (0, 0, 0, 0.0))
        self.assertIsNone(self.game.level.checkpoint_id)

    def test_cannot_advance_without_exit(self):
        self.game.advance_level()
        self.assertEqual(self.game.level_index, 0)

    def test_model_imports_without_pygame_or_site_packages(self):
        result = subprocess.run([sys.executable, '-S', '-c',
                                 "import sys; from dormgame.model import GameSession; GameSession(); assert 'pygame' not in sys.modules"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class LevelValidationTests(unittest.TestCase):
    def setUp(self):
        self.spec = copy.deepcopy(load_levels()[0])

    def test_all_real_levels_valid(self):
        self.assertEqual(len(load_levels()), 3)

    def test_start_and_exit_required(self):
        for key in ('start', 'exit'):
            spec = copy.deepcopy(self.spec)
            del spec[key]
            with self.assertRaises(ValueError):
                validate_level(spec)

    def test_unique_ids_across_object_groups(self):
        self.spec['exit']['id'] = self.spec['pages'][0]['id']
        with self.assertRaises(ValueError):
            validate_level(self.spec)

    def test_unknown_enemy_rejected(self):
        self.spec['enemies'][0]['kind'] = 'dragon'
        with self.assertRaises(ValueError):
            validate_level(self.spec)

    def test_unknown_souvenir_and_duplicate_id_rejected(self):
        for key, value in [('kind', 'unknown'), ('id', self.spec['pages'][0]['id'])]:
            spec = copy.deepcopy(self.spec)
            spec['souvenirs'][0][key] = value
            with self.assertRaises(ValueError):
                validate_level(spec)

    def test_outside_invalid_size_nan_and_wrong_type(self):
        for rect in ([0, 0, -1, 8], [2000, 0, 8, 8], [0, float('nan'), 8, 8], 'bad', [False, 0, 8, 8]):
            spec = copy.deepcopy(self.spec)
            spec['pages'][0]['rect'] = rect
            with self.assertRaises(ValueError):
                validate_level(spec)

    def test_start_inside_wall_rejected(self):
        self.spec['start'] = [40, 430]
        with self.assertRaises(ValueError):
            validate_level(self.spec)

    def test_enemy_start_inside_wall_rejected(self):
        self.spec['enemies'][0].update(x=220, y=390, left=180, right=330)
        with self.assertRaises(ValueError):
            validate_level(self.spec)

    def test_platform_path_crossing_static_wall_rejected(self):
        self.spec['platforms'] = [{'id': 'invalid', 'rect': [10, 390, 20, 8],
                                  'end': [400, 390], 'speed': 25}]
        with self.assertRaises(ValueError):
            validate_level(self.spec)


if __name__ == '__main__':
    unittest.main()
