"""Per-symbol/per-timeframe pipeline: trend filter -> fib ->
FVG/fib confluence -> regression slope -> current price status.
"""

from .confluence import fvgs_overlapping_fib, intersect_zone
from .fibonacci import compute_fib_levels
from .fvg import detect_fvgs
from .models import AnalysisResult, Signal
from .slope import compute_regression_angle_degrees
from .swings import classify_trend, find_pivots, get_impulsive_leg


def analyze(candles, symbol, timeframe, market_bias, cfg):
    """Run the full pipeline for one symbol/timeframe.

    Returns an AnalysisResult: signal=Signal, reason=None on acceptance;
    signal=None, reason=<short string> on rejection at any stage. The
    reason is meant for a one-line scan log entry, e.g.
    "no clear trend" or "retracement too steep, angle=42.3deg".
    """
    pivot_lookback = cfg["pivot_lookback"]
    min_candles = pivot_lookback * 2 + 10
    if len(candles) < min_candles:
        return AnalysisResult(None, "insufficient candle history")

    pivots = find_pivots(candles, pivot_lookback)
    trend = classify_trend(pivots)
    if trend is None:
        return AnalysisResult(None, "no clear trend")

    if market_bias == "LONG" and trend != "UP":
        return AnalysisResult(None, "trend does not match bias")
    if market_bias == "SHORT" and trend != "DOWN":
        return AnalysisResult(None, "trend does not match bias")

    extreme, prior = get_impulsive_leg(pivots, trend)
    if extreme is None or prior is None:
        return AnalysisResult(None, "no valid swing leg")

    leg_range = abs(extreme.price - prior.price)
    if leg_range <= 0:
        return AnalysisResult(None, "no valid swing leg")

    fib_levels = compute_fib_levels(trend, extreme.price, prior.price, cfg["fib_ratios"])

    leg_start_idx = min(extreme.index, prior.index)
    leg_end_idx = max(extreme.index, prior.index)
    fvgs = detect_fvgs(candles, leg_start_idx, leg_end_idx, trend)
    if not fvgs:
        return AnalysisResult(None, "no valid FVG in trend leg")

    matched = fvgs_overlapping_fib(fvgs, fib_levels)
    if not matched:
        return AnalysisResult(None, "no FVG overlaps fib levels")

    # Most recent qualifying FVG is the one currently relevant to price.
    matched.sort(key=lambda pair: pair[0].idx3)
    fvg, ratio = matched[-1]

    # "The zone" is the FVG/fib INTERSECTION, not the raw FVG range --
    # computed once here and reused for every downstream check (touch
    # detection, the regression endpoint, breakout/exit, stop-loss) so
    # none of them can disagree about what counts as "inside". Price
    # sitting in a part of the FVG that falls outside the fib band must
    # never count as having reached the zone.
    zone = intersect_zone(fvg, fib_levels)
    if zone is None:
        return AnalysisResult(None, "no FVG/fib intersection")
    zone_low, zone_high = zone

    # Only look at recent price action for the touch -- a zone that price
    # touched long ago and has since drifted away from is not "live".
    #
    # Critical: the window must never reach back to candles at or before
    # the swing extreme itself. The impulsive leg naturally passes
    # through the eventual zone's price band on its way up, and a
    # mid-rally consolidation can easily wick back into it too -- none of
    # that is a real retracement. Only a candle strictly AFTER the
    # extreme represents price actually pulling back into the zone once
    # the high was made.
    window_start = max(fvg.confirmed_idx, len(candles) - cfg["recent_touch_window"], extreme.index + 1)
    touching_indices = [
        j
        for j in range(window_start, len(candles))
        if candles[j].low <= zone_high and candles[j].high >= zone_low
    ]
    if not touching_indices:
        return AnalysisResult(None, "zone not reached yet")
    first_touch_idx = touching_indices[0]
    last_touch_idx = touching_indices[-1]

    # Linear regression of closes from the TRUE start of the impulsive
    # move (prior -- the leg's actual origin, per get_impulsive_leg)
    # through to the first candle that reached the zone. This replaces
    # the old two/three-point trendline check: fitting a line over the
    # whole observed leg is a much more robust "was this an orderly,
    # gentle move" check than a handful of discrete touch points.
    angle = compute_regression_angle_degrees(candles, prior.index, first_touch_idx, leg_range)
    if abs(angle) >= cfg["max_retracement_angle_degrees"]:
        return AnalysisResult(None, "retracement too steep, angle=%.1fdeg" % angle)

    status, breakout_candle = _resolve_status(candles, last_touch_idx, zone_low, zone_high, trend, cfg["breakout_body_ratio"])

    signal = Signal(
        symbol=symbol,
        timeframe=timeframe,
        trend=trend,
        status=status,
        zone_low=zone_low,
        zone_high=zone_high,
        fib_ratio=ratio,
        angle_degrees=angle,
        touch_index=last_touch_idx,
    )
    if status == "MARKET" and breakout_candle is not None:
        signal.entry = breakout_candle.close
        signal.stop_loss = zone_low if trend == "UP" else zone_high
        signal.target = extreme.price
    return AnalysisResult(signal, None)


def _resolve_status(candles, touch_idx, zone_low, zone_high, trend, body_ratio_threshold):
    """From the last touch onward, look for a strong breakout candle.
    If none is found, classify the latest candle as still ranging inside
    the zone (IN_RANGE) or having left it without breaking (EXITED).
    """
    for j in range(touch_idx, len(candles)):
        c = candles[j]
        if trend == "UP":
            broke = c.close > zone_high
        else:
            broke = c.close < zone_low
        if broke and c.body_ratio > body_ratio_threshold:
            return "MARKET", c

    last = candles[-1]
    touching = last.low <= zone_high and last.high >= zone_low
    return ("IN_RANGE", None) if touching else ("EXITED", None)
