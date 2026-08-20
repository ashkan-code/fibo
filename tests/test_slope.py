import unittest

from trend_fvg.models import Candle
from trend_fvg.slope import compute_angle_degrees, compute_regression_angle_degrees, linear_regression_slope


def _candle(i, o, h, l, c):
    return Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)


def _closes(values):
    """Candles whose close is exactly `values[i]` at index i (open/high/low
    are irrelevant to the regression, which only reads .close).
    """
    return [_candle(i, v, v + 0.5, v - 0.5, v) for i, v in enumerate(values)]


class TestSlope(unittest.TestCase):
    def test_zero_leg_range_is_flat(self):
        self.assertEqual(compute_angle_degrees(10, 0, 5), 0.0)

    def test_zero_candle_delta_is_flat(self):
        self.assertEqual(compute_angle_degrees(10, 100, 0), 0.0)

    def test_full_retrace_in_one_candle_is_steep(self):
        angle = compute_angle_degrees(price_delta=100, leg_range=100, candle_delta=1)
        self.assertGreaterEqual(angle, 45)

    def test_small_retrace_over_many_candles_is_shallow(self):
        angle = compute_angle_degrees(price_delta=5, leg_range=100, candle_delta=20)
        self.assertLess(angle, 30)

    def test_sign_of_price_delta_does_not_matter(self):
        a = compute_angle_degrees(price_delta=-20, leg_range=100, candle_delta=10)
        b = compute_angle_degrees(price_delta=20, leg_range=100, candle_delta=10)
        self.assertAlmostEqual(a, b)

    def test_result_is_never_negative(self):
        # An uptrend pullback moves price DOWN (negative price_delta) --
        # the angle must still come back as a non-negative magnitude, not
        # a signed slope that a naive "< 30" check could be fooled by.
        for price_delta in (-90, -20, -1, 0, 1, 20, 90):
            angle = compute_angle_degrees(price_delta=price_delta, leg_range=100, candle_delta=5)
            self.assertGreaterEqual(angle, 0.0)

    def test_steep_negative_move_is_not_mistaken_for_shallow(self):
        # A sharp downward pullback (uptrend) covering most of the leg
        # range in very few candles must register as steep, not pass a
        # signed "< 30" comparison just because price_delta is negative.
        angle = compute_angle_degrees(price_delta=-80, leg_range=100, candle_delta=1)
        self.assertGreaterEqual(abs(angle), 30)


class TestLinearRegressionSlope(unittest.TestCase):
    def test_perfect_line_slope_matches_exactly(self):
        xs = [0, 1, 2, 3, 4]
        ys = [10, 12, 14, 16, 18]  # slope = 2
        self.assertAlmostEqual(linear_regression_slope(xs, ys), 2.0)

    def test_negative_slope(self):
        xs = [0, 1, 2, 3]
        ys = [100, 90, 80, 70]  # slope = -10
        self.assertAlmostEqual(linear_regression_slope(xs, ys), -10.0)

    def test_fewer_than_two_points_is_flat(self):
        self.assertEqual(linear_regression_slope([], []), 0.0)
        self.assertEqual(linear_regression_slope([5], [100]), 0.0)

    def test_no_x_variance_is_flat(self):
        self.assertEqual(linear_regression_slope([3, 3, 3], [1, 5, 9]), 0.0)


class TestRegressionAngle(unittest.TestCase):
    def test_end_idx_not_after_start_idx_is_flat(self):
        candles = _closes([100, 99, 98])
        self.assertEqual(compute_regression_angle_degrees(candles, 1, 1, 100), 0.0)
        self.assertEqual(compute_regression_angle_degrees(candles, 2, 0, 100), 0.0)

    def test_zero_leg_range_is_flat(self):
        candles = _closes([100, 90, 80])
        self.assertEqual(compute_regression_angle_degrees(candles, 0, 2, 0), 0.0)

    def test_shallow_uptrend_pullback_passes(self):
        # Uptrend pullback: closes grind DOWN gently (naturally negative
        # raw slope) across many candles -- a small fraction of the leg
        # range -- must read as shallow.
        closes = [100 - i * (5 / 19) for i in range(20)]  # 100 -> ~95 over 20 candles
        candles = _closes(closes)
        angle = compute_regression_angle_degrees(candles, 0, 19, leg_range=100)
        self.assertLess(abs(angle), 30)

    def test_steep_uptrend_pullback_fails(self):
        # Uptrend pullback: closes collapse DOWN hard over just 2 candles
        # (naturally negative raw slope) -- must read as steep.
        candles = _closes([100, 60, 20])  # slope = -40 over a leg_range of 50
        angle = compute_regression_angle_degrees(candles, 0, 2, leg_range=50)
        self.assertGreaterEqual(abs(angle), 30)

    def test_shallow_downtrend_pullback_passes(self):
        # Downtrend pullback: closes grind UP gently (naturally positive
        # raw slope) -- must also read as shallow. Confirms abs() handles
        # the positive-slope direction the same as the negative one.
        closes = [95 + i * (5 / 19) for i in range(20)]  # 95 -> ~100 over 20 candles
        candles = _closes(closes)
        angle = compute_regression_angle_degrees(candles, 0, 19, leg_range=100)
        self.assertLess(abs(angle), 30)

    def test_steep_downtrend_pullback_fails(self):
        # Downtrend pullback: closes rip UP hard over just 2 candles
        # (naturally positive raw slope) -- must also read as steep.
        candles = _closes([20, 60, 100])  # slope = +40 over a leg_range of 50
        angle = compute_regression_angle_degrees(candles, 0, 2, leg_range=50)
        self.assertGreaterEqual(abs(angle), 30)

    def test_symmetric_steep_moves_give_the_same_angle_either_direction(self):
        # The uptrend (negative slope) and downtrend (positive slope)
        # steep cases above are mirror images of each other -- abs()
        # must make them compare equal, not treat one as steep and the
        # other as shallow because of sign.
        up = compute_regression_angle_degrees(_closes([100, 60, 20]), 0, 2, leg_range=50)
        down = compute_regression_angle_degrees(_closes([20, 60, 100]), 0, 2, leg_range=50)
        self.assertAlmostEqual(up, down)


if __name__ == "__main__":
    unittest.main()
