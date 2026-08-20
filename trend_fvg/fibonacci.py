"""Fibonacci retracement levels, drawn in the STANDARD direction: low ->
high for an uptrend (0% at the swing low, 100% at the swing high),
high -> low for a downtrend (0% at the swing high, 100% at the swing
low) -- not reversed.

Because the fib is anchored this way, the deep/discount retracement zone
we actually want is the MIRROR of the classic 0.618/0.705/0.79 levels
around the 50% midpoint: 0.382/0.295/0.21 (1 - 0.618 = 0.382, etc). Both
sets of numbers produce the exact same prices -- only which end of the
leg is called "0%" differs -- but 0.382/0.295/0.21 is what the standard
low-to-high (resp. high-to-low) direction requires to land in the
discount/premium zone below/above the midpoint.
"""


def compute_fib_levels(trend, extreme_price, prior_price, ratios=(0.382, 0.295, 0.21)):
    """Return {ratio: price_level} for the given trend.

    UP:   extreme_price = swing high, prior_price = swing low.
          level = low + ratio * (high - low)
    DOWN: extreme_price = swing low, prior_price = swing high.
          level = high - ratio * (high - low)
    """
    if trend == "UP":
        high, low = extreme_price, prior_price
        rng = high - low
        return {r: low + r * rng for r in ratios}
    elif trend == "DOWN":
        low, high = extreme_price, prior_price
        rng = high - low
        return {r: high - r * rng for r in ratios}
    raise ValueError("trend must be 'UP' or 'DOWN', got %r" % (trend,))
