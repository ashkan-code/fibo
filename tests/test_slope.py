import unittest

from trend_fvg.slope import compute_angle_degrees


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


if __name__ == "__main__":
    unittest.main()
