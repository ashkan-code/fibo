import unittest

from trend_fvg import engine
from trend_fvg.models import Candle

CFG = {
    "pivot_lookback": 1,
    "fib_ratios": (0.618, 0.705, 0.79),
    "max_retracement_angle_degrees": 30,
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
    swing high, and never produces an accidental >70%-body candle).
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
        signal = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.status, "IN_RANGE")
        self.assertEqual(signal.trend, "UP")
        self.assertEqual((signal.zone_low, signal.zone_high), (20, 30))

    def test_market_breakout(self):
        candles = build_candles([(26, 38, 25, 37)])
        signal = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.status, "MARKET")
        self.assertEqual(signal.entry, 37)
        self.assertEqual(signal.stop_loss, 20)
        self.assertEqual(signal.target, 50)

    def test_exited(self):
        candles = build_candles([(15, 17, 12, 13)])
        signal = engine.analyze(candles, "TESTUSDT", "5m", "LONG", CFG)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.status, "EXITED")

    def test_bias_mismatch_returns_none(self):
        candles = build_candles([(27, 29, 24, 25)])
        signal = engine.analyze(candles, "TESTUSDT", "5m", "SHORT", CFG)
        self.assertIsNone(signal)


if __name__ == "__main__":
    unittest.main()
