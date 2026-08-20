"""Per-symbol/per-timeframe pipeline: trend filter -> reverse fib ->
FVG/fib confluence -> retracement slope -> current price status.
"""

from .confluence import fvgs_overlapping_fib
from .fibonacci import compute_fib_levels
from .fvg import detect_fvgs
from .models import Signal
from .slope import compute_angle_degrees
from .swings import classify_trend, find_pivots, get_impulsive_leg


def analyze(candles, symbol, timeframe, market_bias, cfg):
    """Return a Signal if this symbol/timeframe currently has an active
    setup, otherwise None.
    """
    pivot_lookback = cfg["pivot_lookback"]
    min_candles = pivot_lookback * 2 + 10
    if len(candles) < min_candles:
        return None

    pivots = find_pivots(candles, pivot_lookback)
    trend = classify_trend(pivots)
    if trend is None:
        return None

    if market_bias == "LONG" and trend != "UP":
        return None
    if market_bias == "SHORT" and trend != "DOWN":
        return None

    extreme, prior = get_impulsive_leg(pivots, trend)
    if extreme is None or prior is None:
        return None

    leg_range = abs(extreme.price - prior.price)
    if leg_range <= 0:
        return None

    fib_levels = compute_fib_levels(trend, extreme.price, prior.price, cfg["fib_ratios"])

    leg_start_idx = min(extreme.index, prior.index)
    leg_end_idx = max(extreme.index, prior.index)
    fvgs = detect_fvgs(candles, leg_start_idx, leg_end_idx, trend)
    if not fvgs:
        return None

    matched = fvgs_overlapping_fib(fvgs, fib_levels)
    if not matched:
        return None

    # Most recent qualifying FVG is the one currently relevant to price.
    matched.sort(key=lambda pair: pair[0].idx3)
    fvg, ratio = matched[-1]

    # Only look at recent price action for the touch -- an FVG that price
    # touched long ago and has since drifted away from is not "live".
    window_start = max(fvg.confirmed_idx, len(candles) - cfg["recent_touch_window"])
    touch_idx = None
    for j in range(window_start, len(candles)):
        c = candles[j]
        if c.low <= fvg.gap_high and c.high >= fvg.gap_low:
            touch_idx = j
            break
    if touch_idx is None:
        return None  # zone not reached (yet) this cycle

    touch_price = candles[touch_idx].low if trend == "UP" else candles[touch_idx].high
    price_delta = touch_price - extreme.price
    candle_delta = touch_idx - extreme.index
    angle = compute_angle_degrees(price_delta, leg_range, candle_delta)
    if angle >= cfg["max_retracement_angle_degrees"]:
        return None

    status, breakout_candle = _resolve_status(candles, touch_idx, fvg, trend, cfg["breakout_body_ratio"])

    signal = Signal(
        symbol=symbol,
        timeframe=timeframe,
        trend=trend,
        status=status,
        zone_low=fvg.gap_low,
        zone_high=fvg.gap_high,
        fib_ratio=ratio,
        angle_degrees=angle,
        touch_index=touch_idx,
    )
    if status == "MARKET" and breakout_candle is not None:
        signal.entry = breakout_candle.close
        signal.stop_loss = fvg.gap_low if trend == "UP" else fvg.gap_high
        signal.target = extreme.price
    return signal


def _resolve_status(candles, touch_idx, fvg, trend, body_ratio_threshold):
    """From the first touch onward, look for a strong breakout candle.
    If none is found, classify the latest candle as still ranging inside
    the zone (IN_RANGE) or having left it without breaking (EXITED).
    """
    for j in range(touch_idx, len(candles)):
        c = candles[j]
        if trend == "UP":
            broke = c.close > fvg.gap_high
        else:
            broke = c.close < fvg.gap_low
        if broke and c.body_ratio > body_ratio_threshold:
            return "MARKET", c

    last = candles[-1]
    touching = last.low <= fvg.gap_high and last.high >= fvg.gap_low
    return ("IN_RANGE", None) if touching else ("EXITED", None)
