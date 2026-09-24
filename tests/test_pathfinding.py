from collections import deque
import random
import unittest

from dormgame.geometry import AABB
from dormgame.pathfinding import DIRECTIONS, NavigationGrid, astar, manhattan


class SmallGrid:
    def __init__(self, rows):
        self.walkable = {(x, y) for y, row in enumerate(rows)
                         for x, value in enumerate(row) if value != "#"}

    def is_walkable(self, cell):
        return cell in self.walkable

    def neighbors(self, cell):
        return tuple((cell[0] + dx, cell[1] + dy) for dx, dy in DIRECTIONS
                     if (cell[0] + dx, cell[1] + dy) in self.walkable)


def bfs_cost(grid, start, goal):
    if not grid.is_walkable(start) or not grid.is_walkable(goal):
        return None
    queue = deque([(start, 0)])
    visited = {start}
    while queue:
        cell, distance = queue.popleft()
        if cell == goal:
            return distance
        for neighbor in grid.neighbors(cell):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    return None


class AStarTests(unittest.TestCase):
    def assert_shortest(self, grid, start, goal):
        result = astar(grid, start, goal)
        self.assertEqual(result.cost, bfs_cost(grid, start, goal))
        if result.path:
            self.assertEqual(result.path[0], start)
            self.assertEqual(result.path[-1], goal)
            for current, neighbor in zip(result.path, result.path[1:]):
                self.assertIn(neighbor, grid.neighbors(current))
                self.assertEqual(manhattan(current, neighbor), 1)
            self.assertGreater(result.expanded, 0)

    def test_matches_bfs_on_handcrafted_maps(self):
        maps = [
            [".....", ".###.", "....."],
            [".......", ".#####.", "...#...", "##.#.##", "......."],
            ["..#..", "..#..", "..#.."],
        ]
        for rows in maps:
            grid = SmallGrid(rows)
            for start in sorted(grid.walkable):
                for goal in sorted(grid.walkable):
                    with self.subTest(rows=rows, start=start, goal=goal):
                        self.assert_shortest(grid, start, goal)

    def test_matches_bfs_on_reproducible_obstacle_maps(self):
        rng = random.Random(2718)
        for _ in range(30):
            grid = SmallGrid(["".join("#" if rng.random() < .28 else "."
                                      for _ in range(9)) for _ in range(7)])
            cells = sorted(grid.walkable)
            for _ in range(10):
                self.assert_shortest(grid, rng.choice(cells), rng.choice(cells))

    def test_unreachable_goal(self):
        grid = SmallGrid(["..#..", "..#.."])
        result = astar(grid, (0, 0), (4, 0))
        self.assertEqual(result.path, [])
        self.assertEqual(result.expanded, 4)

    def test_start_equals_goal(self):
        grid = SmallGrid([".#"])
        self.assertEqual(astar(grid, (0, 0), (0, 0)).path, [(0, 0)])
        self.assertEqual(astar(grid, (1, 0), (1, 0)).path, [])

    def test_invalid_start_or_goal(self):
        grid = SmallGrid(["..."])
        self.assertEqual(astar(grid, (-1, 0), (2, 0)).path, [])
        self.assertEqual(astar(grid, (0, 0), (7, 0)).path, [])


class NavigationTests(unittest.TestCase):
    def test_drone_cannot_fit_through_narrow_opening(self):
        # Две комнаты соединены проходом высотой 10 при высоте дрона 14.
        walls = [AABB(92, 0, 16, 55), AABB(92, 65, 16, 63)]
        grid = NavigationGrid(208, 128, walls, agent_size=(18, 14))
        start = grid.nearest_free((40, 56))
        goal = grid.nearest_free((168, 56))
        self.assertEqual(astar(grid, start, goal).path, [])
        approach = grid.reachable_target(start, (168, 56))
        self.assertEqual(grid.components[start], grid.components[approach])
        self.assertLess(grid.cell_center(approach)[0], 92)

    def test_segment_clearance_checks_between_cell_centers(self):
        # Центры обеих клеток свободны, но тонкая стена пересекает ребро.
        wall = AABB(15, 0, 1, 32)
        grid = NavigationGrid(32, 32, [wall], agent_size=(4, 4))
        self.assertIn((0, 0), grid.walkable)
        self.assertIn((1, 0), grid.walkable)
        self.assertNotIn((1, 0), grid.neighbors((0, 0)))
        self.assertEqual(astar(grid, (0, 0), (1, 0)).path, [])

    def test_all_edges_keep_drone_clear_of_solids(self):
        walls = [AABB(80, 48, 8, 64), AABB(130, 30, 16, 32)]
        grid = NavigationGrid(208, 144, walls)
        for cell in grid.walkable:
            for neighbor in grid.neighbors(cell):
                a, b = grid.cell_center(cell), grid.cell_center(neighbor)
                for step in range(17):
                    t = step / 16
                    box = grid.agent_box((a[0] + (b[0] - a[0]) * t,
                                          a[1] + (b[1] - a[1]) * t))
                    self.assertFalse(any(box.intersects(wall) for wall in walls))

    def test_navigation_path_matches_bfs(self):
        grid = NavigationGrid(256, 192, [AABB(112, 48, 16, 144)])
        start, goal = grid.nearest_free((40, 152)), grid.nearest_free((216, 152))
        result = astar(grid, start, goal)
        self.assertEqual(result.cost, bfs_cost(grid, start, goal))
        self.assertGreater(result.cost, manhattan(start, goal))

    def test_fully_blocked_map_is_safe(self):
        grid = NavigationGrid(64, 64, [AABB(0, 0, 64, 64)])
        self.assertIsNone(grid.nearest_free((32, 32)))
        self.assertIsNone(grid.reachable_target((2, 2), (40, 40)))

    def test_world_boundary_has_clearance(self):
        grid = NavigationGrid(101, 95, [])
        for cell in grid.walkable:
            box = grid.agent_box(grid.cell_center(cell))
            self.assertGreaterEqual(box.left, 0)
            self.assertGreaterEqual(box.top, 0)
            self.assertLessEqual(box.right, 101)
            self.assertLessEqual(box.bottom, 95)


if __name__ == "__main__":
    unittest.main()
