import unittest

from trend_fvg.fibonacci import compute_fib_levels


class TestFibonacci(unittest.TestCase):
    def test_uptrend_levels(self):
        levels = compute_fib_levels("UP", extreme_price=100, prior_price=50, ratios=(0.618, 0.79))
        self.assertAlmostEqual(levels[0.618], 100 - 0.618 * 50)
        self.assertAlmostEqual(levels[0.79], 100 - 0.79 * 50)
        # deeper ratio -> level closer to the prior low
        self.assertLess(levels[0.79], levels[0.618])

    def test_downtrend_levels(self):
        levels = compute_fib_levels("DOWN", extreme_price=50, prior_price=100, ratios=(0.618, 0.79))
        self.assertAlmostEqual(levels[0.618], 50 + 0.618 * 50)
        self.assertAlmostEqual(levels[0.79], 50 + 0.79 * 50)
        # deeper ratio -> level closer to the prior high
        self.assertGreater(levels[0.79], levels[0.618])

    def test_invalid_trend_raises(self):
        with self.assertRaises(ValueError):
            compute_fib_levels("SIDEWAYS", extreme_price=100, prior_price=50)


if __name__ == "__main__":
    unittest.main()
