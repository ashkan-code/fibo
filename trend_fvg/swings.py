"""Swing (fractal) detection and ICT-style market structure classification."""

from .models import Swing


def find_pivots(candles, lookback=3):
    """Find fractal swing highs/lows: a candle whose high (low) is the
    max (min) within `lookback` candles on both sides.
    """
    pivots = []
    n = len(candles)
    for i in range(lookback, n - lookback):
        window = candles[i - lookback : i + lookback + 1]
        c = candles[i]
        if c.high == max(w.high for w in window):
            pivots.append(Swing(index=c.index, price=c.high, kind="high"))
        if c.low == min(w.low for w in window):
            pivots.append(Swing(index=c.index, price=c.low, kind="low"))
    return pivots


def classify_trend(pivots):
    """Classify structure using the last two swing highs and last two swing
    lows. Returns "UP" (HH+HL), "DOWN" (LH+LL), or None (no clear structure).
    """
    highs = [p for p in pivots if p.kind == "high"]
    lows = [p for p in pivots if p.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return None
    last_high, prev_high = highs[-1], highs[-2]
    last_low, prev_low = lows[-1], lows[-2]
    if last_high.price > prev_high.price and last_low.price > prev_low.price:
        return "UP"
    if last_high.price < prev_high.price and last_low.price < prev_low.price:
        return "DOWN"
    return None


def get_impulsive_leg(pivots, trend):
    """Return (extreme_swing, prior_swing) that bound the most recent
    impulsive leg in the direction of `trend`:
      - UP:   extreme = latest swing high, prior = latest swing low before it
      - DOWN: extreme = latest swing low,  prior = latest swing high before it
    Returns (None, None) if no valid leg can be formed.
    """
    highs = [p for p in pivots if p.kind == "high"]
    lows = [p for p in pivots if p.kind == "low"]
    if not highs or not lows:
        return None, None

    if trend == "UP":
        extreme = highs[-1]
        candidates = [p for p in lows if p.index < extreme.index]
    elif trend == "DOWN":
        extreme = lows[-1]
        candidates = [p for p in highs if p.index < extreme.index]
    else:
        return None, None

    if not candidates:
        return None, None
    prior = candidates[-1]
    return extreme, prior
