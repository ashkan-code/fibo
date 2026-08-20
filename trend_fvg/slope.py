"""Retracement slope + trendline confirmation.

Price and time aren't directly comparable units, so the price axis is
normalized against the impulsive leg's own range (swing-extreme to
prior-swing) before computing an angle. This turns "how steep was the
pullback" into a dimensionless, chart-shape-independent measurement:
a pullback that retraces the *entire* leg in a single candle is ~90
degrees, one that grinds back a tiny fraction over many candles is
close to 0 degrees.

The angle is always treated as a magnitude: in an uptrend the pullback
moves down (a negative price delta) while in a downtrend it moves up (a
positive one), so the sign of price_delta carries no information about
steepness on its own -- only abs(price_delta) does. compute_angle_degrees
takes abs() of the price delta before the trig call, and abs() again on
the result, so it can never return (or be compared as) a signed value.
"""

import math


def compute_angle_degrees(price_delta, leg_range, candle_delta):
    if leg_range <= 0 or candle_delta <= 0:
        return 0.0
    normalized_price = abs(price_delta) / leg_range
    return abs(math.degrees(math.atan2(normalized_price, candle_delta)))


def trendline_price_at(start_idx, start_price, end_idx, end_price, index):
    """Linearly interpolate the trendline's price at candle `index`."""
    if end_idx == start_idx:
        return start_price
    t = (index - start_idx) / (end_idx - start_idx)
    return start_price + (end_price - start_price) * t


def count_trendline_touches(candles, start_idx, start_price, end_idx, end_price):
    """Count candles (from start_idx to end_idx, inclusive) whose wick
    range crosses the straight line from (start_idx, start_price) to
    (end_idx, end_price).

    Two points always define *a* line; this counts how many candles
    actually respect it, so a line can be rejected as unconfirmed unless
    enough price action (endpoints included) actually touched it.
    """
    if end_idx <= start_idx:
        return 0
    touches = 0
    for idx in range(start_idx, end_idx + 1):
        candle = candles[idx]
        line_price = trendline_price_at(start_idx, start_price, end_idx, end_price, idx)
        if candle.low <= line_price <= candle.high:
            touches += 1
    return touches
