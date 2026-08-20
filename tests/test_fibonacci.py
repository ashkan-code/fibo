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

    def test_uptrend_levels_land_in_the_discount_zone(self):
        # ICT convention: for an uptrend the reverse fib is drawn high (0%)
        # -> prior low (100%), so 0.618/0.705/0.79 must land in the
        # "discount" -- strictly BELOW the leg's midpoint (buying cheap
        # relative to the swing), not above it.
        high, low = 100, 50
        midpoint = (high + low) / 2
        levels = compute_fib_levels("UP", extreme_price=high, prior_price=low, ratios=(0.618, 0.705, 0.79))
        for ratio, level in levels.items():
            self.assertLess(level, midpoint, "0.%s level should be below the midpoint in an uptrend" % ratio)

    def test_downtrend_levels_land_in_the_premium_zone(self):
        # Mirror of the above: for a downtrend the fib is drawn low (0%)
        # -> prior high (100%), so the levels must land in the "premium"
        # -- strictly ABOVE the leg's midpoint (selling expensive relative
        # to the swing).
        low, high = 50, 100
        midpoint = (high + low) / 2
        levels = compute_fib_levels("DOWN", extreme_price=low, prior_price=high, ratios=(0.618, 0.705, 0.79))
        for ratio, level in levels.items():
            self.assertGreater(level, midpoint, "0.%s level should be above the midpoint in a downtrend" % ratio)


if __name__ == "__main__":
    unittest.main()
