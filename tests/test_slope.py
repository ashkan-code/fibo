import unittest

from trend_fvg.models import Candle
from trend_fvg.slope import compute_angle_degrees, count_trendline_touches, trendline_price_at


def _candle(i, o, h, l, c):
    return Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)


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


class TestTrendlineTouches(unittest.TestCase):
    def test_price_at_interpolates_linearly(self):
        self.assertAlmostEqual(trendline_price_at(0, 100, 10, 50, 5), 75)
        self.assertAlmostEqual(trendline_price_at(0, 100, 10, 50, 0), 100)
        self.assertAlmostEqual(trendline_price_at(0, 100, 10, 50, 10), 50)

    def test_endpoints_always_count_as_touches(self):
        # A straight decline where only the two endpoints actually sit on
        # the line -- everything in between is well above it.
        candles = [
            _candle(0, 100, 100, 100, 100),
            _candle(1, 95, 96, 94, 95),
            _candle(2, 90, 91, 89, 90),
            _candle(3, 60, 61, 59, 60),
        ]
        touches = count_trendline_touches(candles, start_idx=0, start_price=100, end_idx=3, end_price=60)
        self.assertEqual(touches, 2)

    def test_confirmed_line_has_at_least_three_touches(self):
        # Candles that actually decline along the same straight line from
        # (0, 100) to (4, 60) -- every candle's wick brackets the line
        # price at its index, so all 5 should register as touches.
        candles = [_candle(i, 100 - 10 * i + 0.5, 100 - 10 * i + 1, 100 - 10 * i - 1, 100 - 10 * i - 0.5) for i in range(5)]
        touches = count_trendline_touches(candles, start_idx=0, start_price=100, end_idx=4, end_price=60)
        self.assertGreaterEqual(touches, 3)

    def test_invalid_range_returns_zero(self):
        candles = [_candle(0, 10, 11, 9, 10), _candle(1, 10, 11, 9, 10)]
        self.assertEqual(count_trendline_touches(candles, start_idx=1, start_price=10, end_idx=0, end_price=10), 0)
        self.assertEqual(count_trendline_touches(candles, start_idx=0, start_price=10, end_idx=0, end_price=10), 0)


if __name__ == "__main__":
    unittest.main()
