import unittest

from trend_fvg import engine
from trend_fvg.models import Candle

CFG = {
    "pivot_lookback": 1,
    "fib_ratios": (0.382, 0.295, 0.21),
    "max_retracement_angle_degrees": 30,
    "min_trendline_touches": 3,
    "breakout_body_ratio": 0.70,
    "recent_touch_window": 30,
}


def _hand_prefix():
    """idx0-10: builds a clean HH/HL uptrend structure (pivot high 12 @1,
    pivot low 8 @2, pivot high 15 @3, pivot low 9.5 @4) followed by an
    impulsive rally (idx5-9) that carves a bullish FVG at gap=[20, 30]
    (c1=idx5 high=20, c3=idx7 low=30), confirmed by idx8-9, and finally a
    new swing high of 50 at idx10.
    """
    return [
        (9.5, 10, 9, 9.8),      # 0 filler
        (11.2, 12, 11, 11.8),   # 1 pivot high 12
        (8.6, 9, 8, 8.4),       # 2 pivot low 8
        (13.5, 15, 13, 14.5),   # 3 pivot high 15
        (9.8, 10, 9.5, 9.6),    # 4 pivot low 9.5 (prior swing low)
        (15, 20, 14, 19),       # 5 c1: high=20
        (19, 32, 18, 31),       # 6 c2: impulsive
        (31, 33, 30, 32),       # 7 c3: low=30 -> gap [20, 30]
        (32, 35, 31, 34),       # 8 window candle, stays above gap
        (34, 40, 33, 39),       # 9 window candle, stays above gap
        (39, 50, 38, 49),       # 10 pivot high 50 (extreme swing)
    ]


def _decline(start_price, end_price, start_idx, count):
    """Small-bodied candles gradually declining in a straight line, so the
    retracement is shallow (touches the FVG zone many candles after the
    swing high, and never produces an accidental >70%-body candle). Being
    close to a straight line from the swing high also means many of these
    candles sit on the extreme->touch trendline, satisfying the
    min_trendline_touches requirement.
    """
    rows = []
    for i in range(count):
        t = i / (count - 1)
        r = start_price + (end_price - start_price) * t
        rows.append((r + 0.3, r + 1.0, r - 1.0, r - 0.3))
    return rows


def build_candles(tail_rows):
    rows = _hand_prefix() + _decline(46, 28, 11, 14) + tail_rows
    return [
        Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
        for i, (o, h, l, c) in enumerate(rows)
    ]


class TestEnginePipeline(unittest.TestCase):
    def test_in_range(self):
        candles = build_candles([(27, 29, 24, 25)])
        result = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNone(result.reason)
        self.assertIsNotNone(result.signal)
        self.assertEqual(result.signal.status, "IN_RANGE")
        self.assertEqual(result.signal.trend, "UP")
        self.assertEqual((result.signal.zone_low, result.signal.zone_high), (20, 30))

    def test_market_breakout(self):
        candles = build_candles([(26, 38, 25, 37)])
        result = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNotNone(result.signal)
        self.assertEqual(result.signal.status, "MARKET")
        self.assertEqual(result.signal.entry, 37)
        self.assertEqual(result.signal.stop_loss, 20)
        self.assertEqual(result.signal.target, 50)

    def test_exited(self):
        candles = build_candles([(15, 17, 12, 13)])
        result = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNotNone(result.signal)
        self.assertEqual(result.signal.status, "EXITED")

    def test_bias_mismatch_returns_reason(self):
        candles = build_candles([(27, 29, 24, 25)])
        result = engine.analyze(candles, "TESTUSDT", "5m", "SHORT", CFG)
        self.assertIsNone(result.signal)
        self.assertEqual(result.reason, "trend does not match bias")

    def test_no_clear_trend_returns_reason(self):
        # Flat/insufficient structure -> classify_trend can't find HH/HL or LH/LL.
        flat = [(10, 10.5, 9.5, 10)] * 30
        candles = [
            Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
            for i, (o, h, l, c) in enumerate(flat)
        ]
        result = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNone(result.signal)
        self.assertEqual(result.reason, "no clear trend")

    def test_steep_retracement_is_rejected_with_angle_in_reason(self):
        # A single huge-bodied candle that violently re-enters the zone
        # right after the swing high -> steep angle, should be rejected
        # regardless of the (negative, downward) sign of the price move.
        rows = _hand_prefix() + [(49, 50, 21, 22)]
        candles = [
            Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
            for i, (o, h, l, c) in enumerate(rows)
        ]
        result = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNone(result.signal)
        self.assertTrue(result.reason.startswith("retracement too steep, angle="))

    def test_still_trending_with_no_pullback_is_not_a_signal(self):
        # Price makes the swing high and then just keeps climbing, exactly
        # like the reported AWEUSDT false positive: it never comes back
        # down into the FVG/fib zone at all. Must NOT produce IN_RANGE or
        # MARKET -- there's nothing to evaluate an entry status for yet.
        #
        # idx11 dips slightly (stays below 50) so idx10 remains a valid
        # swing-high pivot; idx12 onward then climbs straight through and
        # past it with no pullback, same as "decline" but inverted (climb
        # instead of drop) -- it never dips back toward the zone again.
        rows = _hand_prefix() + [(48, 49, 47, 48.5)] + _decline(50, 70, 12, 19)
        candles = [
            Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
            for i, (o, h, l, c) in enumerate(rows)
        ]
        result = engine.analyze(candles, "AWEUSDT", "5m", "LONG", CFG)
        self.assertIsNone(result.signal)
        self.assertEqual(result.reason, "zone not reached yet")


class TestPreExtremeTouchIsNotARetracement(unittest.TestCase):
    """Regression test for a real false-positive found via live testing
    (AWEUSDT, 5m): a candle that wicked into what later became the FVG
    zone *before* the swing high was even made (completely normal -- the
    original impulsive rally has to pass through that price band on its
    way up, and can easily wobble back into it during a mid-rally
    consolidation) must never be mistaken for a genuine post-high
    retracement touch. Only candles strictly after the swing extreme
    count.

    This fixture is built to specifically exercise that path: the FVG
    confirms well before the swing high forms, there's a multi-candle gap
    between confirmation and the high with a wick dipping back into the
    zone in between, and afterward price only keeps climbing (no real
    pullback ever happens). Before the fix, this would incorrectly
    resolve to a signal; see the assertion in
    test_pre_extreme_wick_is_rejected below plus the standalone
    reproduction used while diagnosing the bug.
    """

    CFG = {
        "pivot_lookback": 5,
        "fib_ratios": (0.382, 0.295, 0.21),
        "max_retracement_angle_degrees": 30,
        "min_trendline_touches": 3,
        "breakout_body_ratio": 0.70,
        "recent_touch_window": 50,
    }

    def _candles(self):
        rows = []
        rows += [(25, 26, 24, 25)] * 5              # idx0-4 filler
        rows += [(20.5, 21, 20, 20.8)]                # idx5 early low pivot (20)
        rows += [(21, 22, 20.5, 21.5)] * 4            # idx6-9 filler
        rows += [(29.5, 30, 29, 29.8)]                # idx10 early high pivot (30)
        rows += [(28, 29, 27, 28)] * 4                # idx11-14 filler
        rows += [(24.5, 25, 24, 24.8)]                # idx15 low pivot (24) -- "prior"
        rows += [(25, 29, 24.5, 28)] * 3              # idx16-18 climb
        rows += [(30, 40, 29, 39)]                    # idx19 FVG c1: high=40
        rows += [(39, 70, 38, 69)]                    # idx20 FVG c2: impulsive
        rows += [(65, 80, 55, 79)]                    # idx21 FVG c3: low=55 -> gap [40, 55]
        rows += [(79, 85, 78, 84)]                    # idx22 confirm candle 1
        rows += [(84, 90, 83, 89)]                    # idx23 confirm candle 2 (FVG confirmed)
        rows += [(89, 95, 88, 94)]                    # idx24 still climbing
        rows += [(94, 96, 45, 95)]                    # idx25 mid-rally wick dips into [40, 55]
        rows += [(95, 99, 94, 98)]                    # idx26 climbing again
        rows += [(98, 105, 97, 104)]                  # idx27 swing high pivot (105) -- "extreme"
        rows += [(103, 104, 102, 103)] * 6            # idx28-33 padding after the high, never retraces
        return [
            Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
            for i, (o, h, l, c) in enumerate(rows)
        ]

    def test_pre_extreme_wick_is_rejected(self):
        candles = self._candles()
        result = engine.analyze(candles, "AWEUSDT", "5m", "LONG", self.CFG)
        self.assertIsNone(result.signal)
        self.assertEqual(result.reason, "zone not reached yet")

    def test_fixture_actually_exercises_the_bug(self):
        # Sanity check on the fixture itself: confirm the pre-extreme
        # candle (idx25) really does sit inside the FVG's window under the
        # OLD (pre-fix) bound -- i.e. this test would have failed before
        # the extreme.index+1 floor was added, proving it's a real
        # regression test and not a fixture that happens to pass anyway.
        from trend_fvg.confluence import fvgs_overlapping_fib
        from trend_fvg.fibonacci import compute_fib_levels
        from trend_fvg.fvg import detect_fvgs
        from trend_fvg.swings import classify_trend, find_pivots, get_impulsive_leg

        candles = self._candles()
        pivots = find_pivots(candles, self.CFG["pivot_lookback"])
        trend = classify_trend(pivots)
        extreme, prior = get_impulsive_leg(pivots, trend)
        fib_levels = compute_fib_levels(trend, extreme.price, prior.price, self.CFG["fib_ratios"])
        fvgs = detect_fvgs(candles, min(extreme.index, prior.index), max(extreme.index, prior.index), trend)
        matched = sorted(fvgs_overlapping_fib(fvgs, fib_levels), key=lambda pair: pair[0].idx3)
        fvg, _ratio = matched[-1]

        old_window_start = max(fvg.confirmed_idx, len(candles) - self.CFG["recent_touch_window"])
        pre_extreme_touch_idx = None
        for j in range(old_window_start, len(candles)):
            c = candles[j]
            if c.low <= fvg.gap_high and c.high >= fvg.gap_low:
                pre_extreme_touch_idx = j
        self.assertIsNotNone(pre_extreme_touch_idx)
        self.assertLess(pre_extreme_touch_idx, extreme.index)


if __name__ == "__main__":
    unittest.main()
