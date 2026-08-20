"""Retracement slope check.

Price and time aren't directly comparable units, so the price axis is
normalized against the impulsive leg's own range (swing-extreme to
prior-swing) before computing an angle. This turns "how steep was the
pullback" into a dimensionless, chart-shape-independent measurement:
a pullback that retraces the *entire* leg in a single candle is ~90
degrees, one that grinds back a tiny fraction over many candles is
close to 0 degrees.
"""

import math


def compute_angle_degrees(price_delta, leg_range, candle_delta):
    if leg_range <= 0 or candle_delta <= 0:
        return 0.0
    normalized_price = abs(price_delta) / leg_range
    return math.degrees(math.atan2(normalized_price, candle_delta))
