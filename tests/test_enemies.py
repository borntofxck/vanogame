import unittest
from unittest.mock import patch

from dormgame import config
from dormgame.enemies import DroneEnemy, Enemy, PatrolEnemy, build_enemy
from dormgame.geometry import AABB
from dormgame.physics import SpatialGrid


class EnemyTests(unittest.TestCase):
    def test_enemy_contract_is_abstract(self):
        with self.assertRaises(TypeError):
            Enemy("abstract", AABB(0, 0, 18, 14))

    def test_factory_uses_common_lifecycle(self):
        specs = [
            {"id": "guard", "kind": "patrol", "x": 32, "y": 80,
             "left": 16, "right": 160},
            {"id": "drone", "kind": "drone", "x": 48, "y": 48,
             "route": [[56, 56], [136, 56]]},
        ]
        grid = SpatialGrid([])
        for spec in specs:
            enemy = build_enemy(spec, [], 320, 240)
            self.assertIsInstance(enemy, Enemy)
            self.assertIsInstance(enemy.update(.01, AABB(300, 200, 16, 26), grid), list)
            enemy.reset()
            self.assertEqual(enemy.age, 0)
            self.assertEqual(enemy.state, "Патруль")

    def test_drone_chases_around_wall_without_any_intersection(self):
        wall = AABB(176, 64, 16, 176)
        grid = SpatialGrid([wall])
        drone = DroneEnemy("test", AABB(95, 145, 18, 14), [(104, 152)],
                           [wall], 400, 240)
        player = AABB(240, 140, 16, 26)
        detected = 0
        visited_above_wall = False
        for _ in range(1200):
            detected += drone.update(config.FIXED_DT, player, grid).count("detected")
            self.assertFalse(drone.box.intersects(wall))
            visited_above_wall |= drone.box.bottom <= wall.top
        self.assertEqual(detected, 1)
        self.assertTrue(visited_above_wall)
        self.assertGreater(drone.box.left, wall.right)
        self.assertGreater(drone.expanded, 0)
        self.assertEqual(drone.state, DroneEnemy.CHASE)

    def test_drone_state_machine_and_predictable_reset(self):
        grid = SpatialGrid([])
        drone = DroneEnemy("test", AABB(55, 65, 18, 14), [(56, 72), (216, 72)],
                           [], 640, 240)
        spawn = drone.box.copy()
        near = AABB(140, 62, 16, 26)
        self.assertEqual(drone.update(.01, near, grid), ["detected"])
        self.assertEqual(drone.update(.01, near, grid), [])
        for _ in range(120):
            drone.update(config.FIXED_DT, near, grid)
        far = AABB(600, 190, 16, 26)
        drone.update(config.FIXED_DT, far, grid)
        self.assertEqual(drone.state, DroneEnemy.RETURN)
        for _ in range(600):
            drone.update(config.FIXED_DT, far, grid)
        self.assertEqual(drone.state, DroneEnemy.PATROL)
        drone.reset()
        self.assertEqual(drone.box, spawn)
        self.assertEqual(drone.path, [])
        self.assertEqual(drone.state, DroneEnemy.PATROL)

    def test_drone_does_not_recalculate_every_step(self):
        grid = SpatialGrid([])
        drone = DroneEnemy("test", AABB(55, 65, 18, 14), [(216, 72)], [], 640, 240)
        original = drone._find_path
        searches = []

        def counting_search(target):
            searches.append(target)
            original(target)

        drone._find_path = counting_search
        for _ in range(120):
            drone.update(config.FIXED_DT, AABB(600, 190, 16, 26), grid)
        self.assertGreaterEqual(len(searches), 2)
        self.assertLessEqual(len(searches), 3)

    def test_drone_cannot_cross_disconnected_wall_even_with_large_dt(self):
        wall = AABB(128, 0, 2, 192)
        grid = SpatialGrid([wall])
        drone = DroneEnemy("test", AABB(47, 81, 18, 14), [(56, 88)],
                           [wall], 320, 192)
        player = AABB(168, 81, 16, 26)
        for _ in range(20):
            drone.update(1.0, player, grid)
            self.assertFalse(drone.box.intersects(wall))
            self.assertLessEqual(drone.box.right, wall.left)

    def test_drone_no_navigation_space_is_safe(self):
        wall = AABB(0, 0, 64, 64)
        drone = DroneEnemy("test", AABB(5, 5, 18, 14), [], [wall], 64, 64)
        drone.update(.1, AABB(50, 50, 10, 10), SpatialGrid([wall]))
        self.assertEqual(drone.path, [])

    def test_no_path_still_respects_repath_interval(self):
        wall = AABB(0, 0, 64, 64)
        drone = DroneEnemy('blocked', AABB(5, 5, 18, 14), [], [wall], 64, 64)
        with patch.object(drone, '_find_path', wraps=drone._find_path) as search:
            for _ in range(120):
                drone.update(config.FIXED_DT, AABB(500, 500, 16, 26), SpatialGrid([wall]))
            self.assertGreaterEqual(search.call_count, 2)
            self.assertLessEqual(search.call_count, 3)

    def test_patrol_turns_before_wall_and_ledge(self):
        floor = AABB(0, 100, 220, 20)
        wall = AABB(150, 40, 16, 60)
        grid = SpatialGrid([floor, wall])
        guard = PatrolEnemy("test", AABB(60, 74, 18, 26), 0, 220)
        positions, directions = [], set()
        for _ in range(1800):
            guard.update(config.FIXED_DT, AABB(300, 200, 16, 26), grid)
            self.assertFalse(guard.box.intersects(floor))
            self.assertFalse(guard.box.intersects(wall))
            self.assertAlmostEqual(guard.box.bottom, floor.top)
            positions.append(guard.box.x)
            directions.add(guard.facing)
        self.assertEqual(directions, {-1, 1})
        self.assertGreaterEqual(min(positions), 0)
        self.assertLessEqual(max(positions) + guard.box.w, wall.left)

    def test_patrol_does_not_walk_off_unbounded_platform(self):
        floor = AABB(40, 100, 130, 10)
        grid = SpatialGrid([floor])
        guard = PatrolEnemy("test", AABB(90, 74, 18, 26), 0, 300)
        for _ in range(1600):
            guard.update(config.FIXED_DT, AABB(300, 200, 16, 26), grid)
            self.assertAlmostEqual(guard.box.bottom, floor.top)
            self.assertGreaterEqual(guard.box.left, floor.left - 1)
            self.assertLessEqual(guard.box.right, floor.right + 1)


if __name__ == "__main__":
    unittest.main()
