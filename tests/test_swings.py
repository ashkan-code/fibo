import unittest

from trend_fvg.swings import classify_trend, find_pivots, get_impulsive_leg
from .util import make_candles

# Clean zigzag, lookback=1: pivots land on interior indices 1..5.
# idx: 0        1(H)      2(L)     3(H)      4(L)       5(H)      6
ZIGZAG_UP = [
    (9.5, 10, 9, 9.8),
    (11, 12, 11, 11.5),    # pivot high 12
    (10.5, 9, 8, 8.5),     # pivot low 8
    (13, 15, 13, 14.5),    # pivot high 15 (HH)
    (10, 10, 9.5, 9.8),    # pivot low 9.5 (HL)
    (16, 18, 14, 17.5),    # pivot high 18 (HH)
    (11, 11, 10, 10.5),
]


class TestSwings(unittest.TestCase):
    def test_find_pivots(self):
        candles = make_candles(ZIGZAG_UP)
        pivots = find_pivots(candles, lookback=1)
        highs = [(p.index, p.price) for p in pivots if p.kind == "high"]
        lows = [(p.index, p.price) for p in pivots if p.kind == "low"]
        self.assertEqual(highs, [(1, 12), (3, 15), (5, 18)])
        self.assertEqual(lows, [(2, 8), (4, 9.5)])

    def test_classify_trend_up(self):
        candles = make_candles(ZIGZAG_UP)
        pivots = find_pivots(candles, lookback=1)
        self.assertEqual(classify_trend(pivots), "UP")

    def test_classify_trend_down_is_mirror(self):
        # mirror the zigzag around a constant to build a downtrend
        mirrored = [(20 - o, 20 - l, 20 - h, 20 - c) for (o, h, l, c) in ZIGZAG_UP]
        candles = make_candles(mirrored)
        pivots = find_pivots(candles, lookback=1)
        self.assertEqual(classify_trend(pivots), "DOWN")

    def test_classify_trend_none_when_insufficient(self):
        candles = make_candles(ZIGZAG_UP[:3])
        pivots = find_pivots(candles, lookback=1)
        self.assertIsNone(classify_trend(pivots))

    def test_impulsive_leg_up(self):
        candles = make_candles(ZIGZAG_UP)
        pivots = find_pivots(candles, lookback=1)
        extreme, prior = get_impulsive_leg(pivots, "UP")
        self.assertEqual((extreme.index, extreme.price), (5, 18))
        self.assertEqual((prior.index, prior.price), (4, 9.5))


if __name__ == "__main__":
    unittest.main()
