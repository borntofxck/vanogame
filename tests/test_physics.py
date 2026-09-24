"""Регрессии физики без Pygame, окна и реального времени."""
import unittest

from dormgame import config
from dormgame.commands import Commands
from dormgame.geometry import AABB
from dormgame.physics import Body, MovingPlatform, PlayerBody, SpatialGrid, move_body, update_player


class CollisionTests(unittest.TestCase):
    def test_landing_stops_at_floor_and_sets_grounded(self):
        body = Body(AABB(5, 0, 10, 10), vy=150)
        result = move_body(body, 0, 55, SpatialGrid([AABB(0, 40, 100, 8)]))
        self.assertTrue(result.landed)
        self.assertTrue(body.grounded)
        self.assertEqual(body.box.bottom, 40)
        self.assertEqual(body.vy, 0)

    def test_wall_stops_horizontal_motion_without_losing_height(self):
        body = Body(AABB(0, 5, 10, 10), vx=100)
        result = move_body(body, 60, 0, SpatialGrid([AABB(30, 0, 8, 100)]))
        self.assertTrue(result.hit_x)
        self.assertEqual(body.box.right, 30)
        self.assertEqual(body.box.y, 5)
        self.assertEqual(body.vx, 0)

    def test_ceiling_clears_upward_speed(self):
        body = Body(AABB(5, 40, 10, 10), vy=-200)
        result = move_body(body, 0, -70, SpatialGrid([AABB(0, 10, 100, 4)]))
        self.assertTrue(result.ceiling)
        self.assertFalse(body.grounded)
        self.assertEqual(body.box.top, 14)
        self.assertEqual(body.vy, 0)

    def test_max_speed_cannot_tunnel_through_subpixel_platform(self):
        body = Body(AABB(5, 0, 10, 10), vy=config.MAX_FALL_SPEED)
        floor = AABB(0, 23.123, 60, 0.1)
        result = move_body(body, 0, config.MAX_FALL_SPEED * 0.1, SpatialGrid([floor]))
        self.assertTrue(result.landed)
        self.assertAlmostEqual(body.box.bottom, floor.top)

    def test_diagonal_corner_stays_outside_walls(self):
        walls = [AABB(40, 0, 8, 100), AABB(0, 60, 100, 8)]
        body = Body(AABB(15, 15, 10, 10))
        move_body(body, 100, 100, SpatialGrid(walls))
        self.assertEqual(body.box.right, 40)
        self.assertEqual(body.box.bottom, 60)
        self.assertFalse(any(body.box.intersects(wall) for wall in walls))

    def test_spatial_index_deduplicates_and_supports_negative_cells(self):
        large = AABB(-40, -30, 100, 100)
        far = AABB(500, 0, 10, 10)
        grid = SpatialGrid([large, far], 16)
        self.assertEqual(grid.query(AABB(-20, -20, 40, 40)), [large])


class JumpTests(unittest.TestCase):
    def setUp(self):
        self.dt = config.FIXED_DT
        self.floor = SpatialGrid([AABB(-100, 100, 500, 10)])
        self.player = PlayerBody(AABB(0, 74, 16, 26))
        update_player(self.player, Commands(), self.dt, self.floor, [])

    def test_coyote_jump_after_leaving_edge(self):
        self.player.box.x = 420
        for _ in range(8):
            update_player(self.player, Commands(), self.dt, self.floor, [])
        events = update_player(self.player, Commands(jump_pressed=True, jump_held=True),
                               self.dt, self.floor, [])
        self.assertIn("jump", events)
        self.assertLess(self.player.vy, -250)

    def test_coyote_expires(self):
        self.player.box.x = 420
        for _ in range(16):
            update_player(self.player, Commands(), self.dt, self.floor, [])
        events = update_player(self.player, Commands(jump_pressed=True, jump_held=True),
                               self.dt, self.floor, [])
        self.assertNotIn("jump", events)
        self.assertGreater(self.player.vy, 0)

    def test_jump_buffer_consumed_on_landing(self):
        player = PlayerBody(AABB(0, 52, 16, 26), vy=280)
        events = update_player(player, Commands(jump_pressed=True, jump_held=True),
                               self.dt, self.floor, [])
        for _ in range(10):
            events += update_player(player, Commands(jump_held=True), self.dt, self.floor, [])
        self.assertEqual(events.count("jump"), 1)
        self.assertIn("land", events)
        self.assertLess(player.vy, 0)

    def test_expired_buffer_does_not_jump_on_landing(self):
        player = PlayerBody(AABB(0, 0, 16, 26))
        events = update_player(player, Commands(jump_pressed=True, jump_held=True),
                               self.dt, self.floor, [])
        for _ in range(100):
            events += update_player(player, Commands(jump_held=True), self.dt, self.floor, [])
        self.assertNotIn("jump", events)
        self.assertTrue(player.grounded)

    def test_holding_after_one_press_never_repeats_jump(self):
        events = update_player(self.player, Commands(jump_pressed=True, jump_held=True),
                               self.dt, self.floor, [])
        for _ in range(240):
            events += update_player(self.player, Commands(jump_held=True), self.dt, self.floor, [])
        self.assertEqual(events.count("jump"), 1)
        self.assertTrue(self.player.grounded)

    def test_early_release_reduces_jump_height(self):
        def apex(hold_steps):
            player = PlayerBody(AABB(0, 74, 16, 26))
            top = player.box.y
            for step in range(120):
                update_player(player, Commands(jump_pressed=step == 0, jump_held=step < hold_steps),
                              self.dt, self.floor, [])
                top = min(top, player.box.y)
            return top
        self.assertLess(apex(100), apex(4) - 15)

    def test_stationary_grounded_does_not_emit_repeated_landings(self):
        events = []
        for _ in range(120):
            events += update_player(self.player, Commands(), self.dt, self.floor, [])
        self.assertEqual(events, [])
        self.assertTrue(self.player.grounded)


class PlatformTests(unittest.TestCase):
    def test_horizontal_platform_carries_passenger(self):
        platform = MovingPlatform("lift", AABB(0, 100, 60, 8), (120, 100), 45)
        player = PlayerBody(AABB(15, 74, 16, 26), grounded=True, support_id="lift")
        grid = SpatialGrid([])
        for _ in range(60):
            platform.update(config.FIXED_DT)
            self.assertNotIn("crushed", update_player(player, Commands(), config.FIXED_DT, grid, [platform]))
        self.assertAlmostEqual(player.box.x, 37.5)
        self.assertAlmostEqual(player.box.bottom, platform.box.top)
        self.assertEqual(player.support_id, "lift")

    def test_vertical_platform_carries_passenger(self):
        platform = MovingPlatform("lift", AABB(0, 100, 60, 8), (0, 40), 30)
        player = PlayerBody(AABB(15, 74, 16, 26), grounded=True, support_id="lift")
        for _ in range(60):
            platform.update(config.FIXED_DT)
            self.assertNotIn("crushed", update_player(player, Commands(), config.FIXED_DT,
                                                     SpatialGrid([]), [platform]))
        self.assertAlmostEqual(player.box.bottom, 85)
        self.assertTrue(player.grounded)

    def test_jump_detaches_without_platform_drag(self):
        platform = MovingPlatform("lift", AABB(0, 100, 60, 8), (120, 100), 45)
        player = PlayerBody(AABB(15, 74, 16, 26), grounded=True, support_id="lift")
        grid = SpatialGrid([])
        platform.update(config.FIXED_DT)
        events = update_player(player, Commands(jump_pressed=True, jump_held=True),
                               config.FIXED_DT, grid, [platform])
        self.assertIn("jump", events)
        self.assertIsNone(player.support_id)
        self.assertEqual(player.box.x, 15)
        for _ in range(10):
            platform.update(config.FIXED_DT)
            update_player(player, Commands(jump_held=True), config.FIXED_DT, grid, [platform])
        self.assertEqual(player.box.x, 15)
        self.assertLess(player.box.bottom, platform.box.top)

    def test_upward_platform_under_ceiling_emits_crush(self):
        platform = MovingPlatform("lift", AABB(0, 100, 60, 8), (0, 0), 60)
        player = PlayerBody(AABB(15, 74, 16, 26), grounded=True, support_id="lift")
        grid = SpatialGrid([AABB(-10, 50, 100, 10)])
        events = []
        for _ in range(40):
            platform.update(config.FIXED_DT)
            events = update_player(player, Commands(), config.FIXED_DT, grid, [platform])
            if "crushed" in events:
                break
        self.assertIn("crushed", events)
        self.assertGreaterEqual(player.box.top, 60)

    def test_platform_pushes_from_side_and_crushes_against_wall(self):
        platform = MovingPlatform("pusher", AABB(0, 50, 20, 60), (150, 50), 120)
        player = PlayerBody(AABB(24, 74, 16, 26), grounded=True)
        grid = SpatialGrid([AABB(0, 100, 200, 8), AABB(55, 0, 8, 100)])
        events = []
        for _ in range(50):
            platform.update(config.FIXED_DT)
            events = update_player(player, Commands(), config.FIXED_DT, grid, [platform])
            if "crushed" in events:
                break
        self.assertIn("crushed", events)
        self.assertEqual(player.box.right, 55)

    def test_platform_pingpong_handles_endpoint_and_resets(self):
        platform = MovingPlatform("lift", AABB(0, 10, 60, 8), (100, 10), 100)
        platform.update(1.25)
        self.assertAlmostEqual(platform.box.x, 75)
        platform.update(0.5)
        self.assertAlmostEqual(platform.box.x, 25)
        self.assertAlmostEqual(platform.dx, -50)
        platform.reset()
        self.assertEqual(platform.box.x, 0)
        self.assertEqual(platform.dx, 0)


if __name__ == "__main__":
    unittest.main()
