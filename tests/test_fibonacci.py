import unittest

from trend_fvg.fibonacci import compute_fib_levels


class TestFibonacci(unittest.TestCase):
    def test_uptrend_levels(self):
        # Standard direction: 0% at the swing low, 100% at the swing high.
        levels = compute_fib_levels("UP", extreme_price=100, prior_price=50, ratios=(0.21, 0.382))
        self.assertAlmostEqual(levels[0.21], 50 + 0.21 * 50)
        self.assertAlmostEqual(levels[0.382], 50 + 0.382 * 50)
        # smaller ratio -> closer to the 0% anchor (the prior low)
        self.assertLess(levels[0.21], levels[0.382])

    def test_downtrend_levels(self):
        # Standard direction: 0% at the swing high, 100% at the swing low.
        levels = compute_fib_levels("DOWN", extreme_price=50, prior_price=100, ratios=(0.21, 0.382))
        self.assertAlmostEqual(levels[0.21], 100 - 0.21 * 50)
        self.assertAlmostEqual(levels[0.382], 100 - 0.382 * 50)
        # smaller ratio -> closer to the 0% anchor (the prior high)
        self.assertGreater(levels[0.21], levels[0.382])

    def test_invalid_trend_raises(self):
        with self.assertRaises(ValueError):
            compute_fib_levels("SIDEWAYS", extreme_price=100, prior_price=50)

    def test_uptrend_levels_land_in_the_discount_zone(self):
        # Standard direction: for an uptrend the fib is drawn low (0%) ->
        # high (100%), so 0.382/0.295/0.21 -- the mirror of 0.618/0.705/0.79
        # around the midpoint -- must land in the "discount", strictly
        # BELOW the leg's midpoint (buying cheap relative to the swing).
        high, low = 100, 50
        midpoint = (high + low) / 2
        levels = compute_fib_levels("UP", extreme_price=high, prior_price=low, ratios=(0.382, 0.295, 0.21))
        for ratio, level in levels.items():
            self.assertLess(level, midpoint, "0.%s level should be below the midpoint in an uptrend" % ratio)

    def test_downtrend_levels_land_in_the_premium_zone(self):
        # Mirror of the above: for a downtrend the fib is drawn high (0%)
        # -> low (100%), so 0.382/0.295/0.21 must land in the "premium",
        # strictly ABOVE the leg's midpoint (selling expensive relative to
        # the swing).
        low, high = 50, 100
        midpoint = (high + low) / 2
        levels = compute_fib_levels("DOWN", extreme_price=low, prior_price=high, ratios=(0.382, 0.295, 0.21))
        for ratio, level in levels.items():
            self.assertGreater(level, midpoint, "0.%s level should be above the midpoint in a downtrend" % ratio)


if __name__ == "__main__":
    unittest.main()
