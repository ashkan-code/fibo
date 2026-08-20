"""Retracement slope, via linear regression over the observed leg.

Price and time aren't directly comparable units, so the price axis is
normalized against the impulsive leg's own range (swing-extreme to
prior-swing) before computing an angle. This turns "how steep was the
move" into a dimensionless, chart-shape-independent measurement: a move
that covers the *entire* leg's price range in a single candle is ~90
degrees, one that grinds across it over many candles is close to 0
degrees.

The angle is always treated as a magnitude: in an uptrend the pullback
moves down (a negative price delta/slope) while in a downtrend it moves
up (a positive one), so the sign carries no information about steepness
on its own -- only the absolute value does. compute_angle_degrees takes
abs() of the price delta before the trig call, and abs() again on the
result, so it can never return (or be compared as) a signed value.
"""

import math


def compute_angle_degrees(price_delta, leg_range, candle_delta):
    if leg_range <= 0 or candle_delta <= 0:
        return 0.0
    normalized_price = abs(price_delta) / leg_range
    return abs(math.degrees(math.atan2(normalized_price, candle_delta)))


def linear_regression_slope(xs, ys):
    """Least-squares slope of y = slope*x + intercept. Returns 0.0 if
    there are fewer than 2 points or all x values are identical.
    """
    n = len(xs)
    if n < 2:
        return 0.0
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_regression_angle_degrees(candles, start_idx, end_idx, leg_range):
    """Fit a linear regression of close price vs. candle index over
    candles[start_idx..end_idx] (inclusive) -- the true start of the
    impulsive move through to where price first reached the zone -- and
    return the abs angle in degrees of that fitted slope.

    Reuses compute_angle_degrees for the actual normalization/trig step:
    a regression slope is already "price change per 1 candle index", so
    feeding it in as price_delta with candle_delta=1 is exactly the same
    normalize-by-leg_range-then-atan2 computation compute_angle_degrees
    already does for a raw two-point slope.
    """
    if leg_range <= 0 or end_idx <= start_idx:
        return 0.0
    xs = list(range(start_idx, end_idx + 1))
    ys = [candles[i].close for i in xs]
    slope = linear_regression_slope(xs, ys)
    return compute_angle_degrees(slope, leg_range, 1)
