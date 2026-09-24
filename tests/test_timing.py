import unittest

from dormgame.config import FIXED_DT, MAX_STEPS
from dormgame.timing import FixedStepper, InputBuffer


class TimingTests(unittest.TestCase):
    def test_edge_survives_frame_with_no_step(self):
        inputs, clock = InputBuffer(), FixedStepper()
        commands = []
        inputs.jump(True)
        clock.advance(FIXED_DT / 3, lambda dt: commands.append(inputs.consume()))
        self.assertEqual(commands, [])
        clock.advance(3 * FIXED_DT, lambda dt: commands.append(inputs.consume()))
        self.assertEqual(sum(c.jump_pressed for c in commands), 1)
        self.assertTrue(all(c.jump_held for c in commands))

    def test_quick_press_release_preserved_in_order(self):
        inputs = InputBuffer()
        inputs.jump(True)
        inputs.jump(False)
        self.assertTrue(inputs.consume().jump_pressed)
        self.assertFalse(inputs.consume().jump_held)
        self.assertFalse(inputs.consume().jump_pressed)

    def test_repeated_keydown_is_not_another_press(self):
        inputs = InputBuffer()
        for _ in range(10):
            inputs.jump(True)
        self.assertTrue(inputs.consume().jump_pressed)
        self.assertFalse(inputs.consume().jump_pressed)

    def test_two_distinct_presses_both_consumed(self):
        inputs = InputBuffer()
        for state in (True, False, True, False):
            inputs.jump(state)
        self.assertEqual(sum(inputs.consume().jump_pressed for _ in range(8)), 2)

    def test_interact_reset_are_one_shot(self):
        inputs = InputBuffer()
        inputs.interact()
        inputs.reset_checkpoint()
        first, second = inputs.consume(), inputs.consume()
        self.assertTrue(first.interact and first.reset)
        self.assertFalse(second.interact or second.reset)

    def test_catch_up_is_limited(self):
        clock, ticks = FixedStepper(), []
        clock.advance(30.0, lambda dt: ticks.append(dt))
        self.assertLessEqual(len(ticks), MAX_STEPS)
        self.assertLessEqual(sum(ticks), 0.101)

    def test_pause_drops_accumulator_without_advancing(self):
        clock, ticks = FixedStepper(), []
        clock.advance(FIXED_DT / 2, lambda dt: ticks.append(dt))
        clock.advance(30, lambda dt: ticks.append(dt), paused=True)
        self.assertEqual(clock.accumulator, 0.0)
        self.assertEqual(ticks, [])
        clock.advance(FIXED_DT, lambda dt: ticks.append(dt))
        self.assertEqual(ticks, [FIXED_DT])

    def test_stop_transition_cancels_remaining_steps(self):
        clock = FixedStepper()
        self.assertEqual(clock.advance(0.1, lambda dt: False), 1)
        self.assertEqual(clock.accumulator, 0.0)


if __name__ == '__main__':
    unittest.main()
