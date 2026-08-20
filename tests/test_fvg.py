import unittest

from trend_fvg.fvg import detect_fvgs
from .util import make_candles


# index: 0        1(c1)      2(c2,impulse)  3(c3)      4          5
BASE = [
    (100, 101, 99, 100),   # 0 filler
    (100, 102, 99, 101),   # 1 c1: high=102
    (101, 110, 100, 109),  # 2 c2: impulsive move up
    (106, 112, 105, 111),  # 3 c3: low=105 -> gap [102, 105]
    (111, 113, 106, 112),  # 4 stays above the gap
    (112, 114, 107, 113),  # 5 stays above the gap
]


class TestFVGDetection(unittest.TestCase):
    def test_valid_bullish_fvg_confirmed(self):
        candles = make_candles(BASE)
        fvgs = detect_fvgs(candles, 0, len(candles) - 1, "UP")
        self.assertEqual(len(fvgs), 1)
        fvg = fvgs[0]
        self.assertEqual((fvg.idx1, fvg.idx2, fvg.idx3), (1, 2, 3))
        self.assertEqual((fvg.gap_low, fvg.gap_high), (102, 105))

    def test_body_intrusion_invalidates(self):
        rows = list(BASE)
        # candle 4's body dips into the gap interior [102, 105]
        rows[4] = (104, 113, 103, 106)
        candles = make_candles(rows)
        fvgs = detect_fvgs(candles, 0, len(candles) - 1, "UP")
        self.assertEqual(fvgs, [])

    def test_wick_only_intrusion_does_not_invalidate(self):
        rows = list(BASE)
        # candle 4's wick dips into the gap, but its body stays above it
        rows[4] = (110, 113, 103, 112)
        candles = make_candles(rows)
        fvgs = detect_fvgs(candles, 0, len(candles) - 1, "UP")
        self.assertEqual(len(fvgs), 1)

    def test_unconfirmed_window_is_skipped(self):
        # only 4 candles total: the 5-candle window (i=1..5) never closes
        candles = make_candles(BASE[:4])
        fvgs = detect_fvgs(candles, 0, len(candles) - 1, "UP")
        self.assertEqual(fvgs, [])

    def test_bearish_fvg(self):
        rows = [
            (100, 101, 99, 100),
            (100, 101, 98, 99),    # c1: low=98
            (99, 100, 90, 91),     # c2: impulsive move down
            (93, 95, 88, 89),      # c3: high=95 -> gap [95, 98]
            (89, 94, 87, 88),
            (88, 93, 86, 87),
        ]
        candles = make_candles(rows)
        fvgs = detect_fvgs(candles, 0, len(candles) - 1, "DOWN")
        self.assertEqual(len(fvgs), 1)
        fvg = fvgs[0]
        self.assertEqual((fvg.gap_low, fvg.gap_high), (95, 98))
        self.assertEqual(fvg.kind, "bearish")


if __name__ == "__main__":
    unittest.main()
