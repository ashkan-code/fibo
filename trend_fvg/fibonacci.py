"""Reverse Fibonacci retracement levels, drawn from the recent swing extreme
back to the prior opposite swing (high -> previous low for uptrends,
low -> previous high for downtrends).
"""


def compute_fib_levels(trend, extreme_price, prior_price, ratios=(0.618, 0.705, 0.79)):
    """Return {ratio: price_level} for the given trend.

    UP:   extreme_price = swing high, prior_price = swing low.
          level = high - ratio * (high - low)
    DOWN: extreme_price = swing low, prior_price = swing high.
          level = low + ratio * (high - low)
    """
    if trend == "UP":
        high, low = extreme_price, prior_price
        rng = high - low
        return {r: high - r * rng for r in ratios}
    elif trend == "DOWN":
        low, high = extreme_price, prior_price
        rng = high - low
        return {r: low + r * rng for r in ratios}
    raise ValueError("trend must be 'UP' or 'DOWN', got %r" % (trend,))
