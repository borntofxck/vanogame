"""Приёмочная проверка: пройти карты, а не расставить героя возле предметов."""
import unittest

from dormgame.commands import Commands
from dormgame.config import FIXED_DT
from dormgame.levels import load_levels
from dormgame.model import GameSession
from tools.verify_routes import RouteController, measure_jump, verify_campaign


class RouteTests(unittest.TestCase):
    def test_entire_campaign_with_enemies_and_moving_platforms(self):
        results = verify_campaign()
        self.assertEqual([result.level for result in results], [1, 2, 3])
        self.assertEqual([result.pages for result in results], [4, 4, 5])
        self.assertEqual(sum(result.deaths for result in results), 0)
        self.assertGreater(sum(result.jumps for result in results), 15)
        self.assertLess(sum(result.seconds for result in results), 120)

    def test_optional_student_set_is_reachable_in_full_campaign(self):
        self.assertEqual(sum(result.deaths for result in verify_campaign(True)), 0)

    def test_simulated_jump_supports_the_authored_platform_spacing(self):
        height, distance = measure_jump()
        # Замер целой траектории выявляет регрессии порядка гравитации/прыжка;
        # карты используют подъёмы 32 px, а не предельные 55 px.
        self.assertGreater(height, 54)
        self.assertLess(height, 57)
        self.assertGreater(distance, 105)
        self.assertLess(distance, 111)

    def test_second_checkpoint_can_recover_missing_platform_page(self):
        session = GameSession([load_levels()[1]])
        control = RouteController(session)
        control.walk(158)
        control.jump(216)
        control.walk(278)
        control.jump(356)
        control.walk(428)
        self.assertEqual(session.level.checkpoint_id, 'cp2')
        self.assertFalse(session.level.pages[2].collected)
        session.update(FIXED_DT, Commands(reset=True))
        self.assertEqual(session.deaths, 1)
        self.assertEqual(session.level.collected_pages, 2)
        control.walk(428)
        platform = session.level.platforms[0]
        control.wait_for(lambda: platform.box.x <= 494 and platform.dx < 0)
        control.jump(lambda: platform.box.x + 25)
        control.wait_for(lambda: platform.box.x >= 542 and platform.dx > 0)
        control.walk(580)
        control.require_page('p3')
        self.assertEqual(session.deaths, 1)


if __name__ == '__main__':
    unittest.main()
