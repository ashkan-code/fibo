"""Check overlap between detected FVG zones and the Fibonacci levels."""


def fvgs_overlapping_fib(fvgs, fib_levels):
    """Return [(fvg, ratio), ...] for every FVG whose [gap_low, gap_high]
    range contains at least one of the fib price levels.
    """
    matches = []
    for fvg in fvgs:
        for ratio, price in fib_levels.items():
            if fvg.gap_low <= price <= fvg.gap_high:
                matches.append((fvg, ratio))
                break
    return matches
