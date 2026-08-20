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
    """Return (extreme_swing, prior_swing) that bound the FULL impulsive
    leg in the direction of `trend`:
      - UP:   extreme = latest swing high; prior = the swing low where
              this impulsive move actually STARTED.
      - DOWN: extreme = latest swing low;  prior = the swing high where
              this impulsive move actually STARTED.
    Returns (None, None) if no valid leg can be formed.

    "Where it started" is found by walking backward from the swing
    nearest the extreme through the chain of consecutive swing points
    that keep extending the same structure (each earlier low is lower
    than the last for an uptrend; each earlier high is higher for a
    downtrend), and stopping at the earliest one still in that unbroken
    chain. This deliberately does NOT stop at the nearest prior swing --
    a minor internal pullback that happened during the later, shallower
    part of a large impulsive move (e.g. a small dip near new highs)
    must not be mistaken for the leg's true origin: using it would draw
    the reverse fib from the wrong anchor and place the 0.618/0.705/0.79
    zone near the top of the move instead of in the deep/discount area
    below its midpoint, where a real retracement zone belongs.
    """
    highs = [p for p in pivots if p.kind == "high"]
    lows = [p for p in pivots if p.kind == "low"]
    if not highs or not lows:
        return None, None

    if trend == "UP":
        extreme = highs[-1]
        candidates = [p for p in lows if p.index < extreme.index]
        better = lambda earlier, current: earlier.price < current.price
    elif trend == "DOWN":
        extreme = lows[-1]
        candidates = [p for p in highs if p.index < extreme.index]
        better = lambda earlier, current: earlier.price > current.price
    else:
        return None, None

    if not candidates:
        return None, None

    prior = candidates[-1]
    for earlier in reversed(candidates[:-1]):
        if better(earlier, prior):
            prior = earlier
        else:
            break
    return extreme, prior
