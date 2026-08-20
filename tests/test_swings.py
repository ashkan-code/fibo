import unittest

from trend_fvg.fibonacci import compute_fib_levels
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
        # ZIGZAG_UP's two low pivots are low8(idx2, the true start of the
        # move) then low9.5(idx4, a shallower higher-low pullback that
        # happened later, closer to the top). prior must resolve to the
        # deeper/earlier one -- the leg's true origin -- not the nearest
        # one chronologically.
        candles = make_candles(ZIGZAG_UP)
        pivots = find_pivots(candles, lookback=1)
        extreme, prior = get_impulsive_leg(pivots, "UP")
        self.assertEqual((extreme.index, extreme.price), (5, 18))
        self.assertEqual((prior.index, prior.price), (2, 8))


def _ramp(p0, p1, n):
    """n small-bodied candles moving from just past p0 to just past p1,
    exclusive of both endpoints -- callers supply the actual pivot
    candles themselves so extremes are unambiguous.
    """
    rows = []
    for i in range(n):
        t = (i + 1) / (n + 1)
        r = p0 + (p1 - p0) * t
        rows.append((r - 0.3, r + 0.4, r - 0.4, r + 0.3))
    return rows


class TestImpulsiveLegFindsTrueMoveOrigin(unittest.TestCase):
    """Regression test for a real false-positive found via live testing
    (AWEUSDT, 5m): the strategy drew its fib/FVG zone at the TOP of the
    move -- right where price currently was -- instead of in the deep
    discount area below the leg's midpoint.

    Root cause: get_impulsive_leg() picked the *nearest* swing low before
    the current high as the fib's 100% anchor, rather than walking back
    to the swing low where the impulsive move actually started. A large
    rally followed by a series of minor, shallower higher-low pullbacks
    near the top (completely normal, realistic price action -- e.g. a
    "grind higher" after the initial impulse) means the nearest prior low
    is one of those minor pullbacks, not the true origin. Using it draws
    the fib across only the last small internal leg, placing the
    0.382/0.295/0.21 levels near the recent highs instead of deep below
    the real move's midpoint.

    This fixture reproduces that shape with realistic multi-candle OHLC:
    a deep true-start low, a large impulsive ramp up, then two rounds of
    "new marginal high -> minor higher-low pullback" near the top, ending
    at the current confirmed high with no real retracement since.
    """

    LOOKBACK = 3

    def _candles(self):
        rows = []
        rows += [(15, 15.5, 14.5, 15.2)] * 4          # idx0-3 filler, above the true low
        rows += _ramp(15, 10.5, 4)                     # idx4-7 descent toward the true start
        rows += [(10.2, 10.5, 10, 10.4)]               # idx8 TRUE START low pivot (price 10)
        rows += _ramp(10.5, 78, 12)                    # idx9-20 the big impulsive leg up
        rows += [(79, 80, 78.5, 79.5)]                 # idx21 first high pivot (80)
        rows += _ramp(78, 71, 4)                       # idx22-25 minor pullback down
        rows += [(70.5, 71, 70, 70.8)]                 # idx26 minor pullback low (70) -- a higher low, NOT the origin
        rows += _ramp(71, 84, 4)                       # idx27-30 push to a new marginal high
        rows += [(84.5, 85, 84, 84.8)]                 # idx31 second high pivot (85)
        rows += _ramp(84, 77, 4)                       # idx32-35 another minor pullback
        rows += [(76.5, 77, 76, 76.8)]                 # idx36 minor pullback low (77) -- another higher low, near the top
        rows += _ramp(77, 89, 4)                       # idx37-40 push to the current high
        rows += [(89.5, 90, 89, 89.8)]                 # idx41 CURRENT confirmed high (90) -- "extreme"
        rows += [(88, 89, 87.5, 88.5)] * 4              # idx42-45 padding (right-side pivot window)
        return make_candles(rows)

    def test_prior_is_the_true_move_origin_not_a_minor_pullback(self):
        candles = self._candles()
        pivots = find_pivots(candles, self.LOOKBACK)
        trend = classify_trend(pivots)
        self.assertEqual(trend, "UP")

        extreme, prior = get_impulsive_leg(pivots, trend)
        self.assertEqual((extreme.index, extreme.price), (41, 90))

        # The fib's 100% point must be the true start of the move...
        self.assertEqual((prior.index, prior.price), (8, 10))
        # ...specifically NOT either of the minor internal pullbacks that
        # happened later, near the top of the move.
        self.assertNotEqual((prior.index, prior.price), (26, 70))
        self.assertNotEqual((prior.index, prior.price), (36, 76))

    def test_fib_zone_lands_in_the_discount_area_below_midpoint(self):
        candles = self._candles()
        pivots = find_pivots(candles, self.LOOKBACK)
        trend = classify_trend(pivots)
        extreme, prior = get_impulsive_leg(pivots, trend)

        midpoint = (extreme.price + prior.price) / 2
        levels = compute_fib_levels(trend, extreme.price, prior.price, ratios=(0.382, 0.295, 0.21))
        for ratio, level in levels.items():
            self.assertLess(level, midpoint, "0.%s level should sit below the true leg's midpoint" % ratio)

    def test_using_the_nearest_minor_pullback_would_have_placed_the_zone_at_the_top(self):
        # Sanity check on the fixture itself, proving this is a real
        # regression test: if the OLD (buggy) "nearest prior low" logic
        # were used instead of the true move origin, the resulting fib
        # levels would land ABOVE the true midpoint -- i.e. right at the
        # top of the move, exactly matching the reported false positive.
        candles = self._candles()
        pivots = find_pivots(candles, self.LOOKBACK)
        trend = classify_trend(pivots)
        extreme, prior = get_impulsive_leg(pivots, trend)
        true_midpoint = (extreme.price + prior.price) / 2

        nearest_minor_pullback_price = 76  # idx36, the most recent low before the extreme
        buggy_levels = compute_fib_levels(
            trend, extreme.price, nearest_minor_pullback_price, ratios=(0.382, 0.295, 0.21)
        )
        for ratio, level in buggy_levels.items():
            self.assertGreater(
                level, true_midpoint, "0.%s level under the old buggy anchor should be above the true midpoint" % ratio
            )


if __name__ == "__main__":
    unittest.main()
