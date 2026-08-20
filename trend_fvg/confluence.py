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


def intersect_zone(fvg, fib_levels):
    """Return (zone_low, zone_high): the overlap between the FVG's
    [gap_low, gap_high] range and the fib band spanned by the target
    ratios (from the shallowest to the deepest configured fib level).

    This intersection -- not the raw FVG range -- IS "the zone" for
    every downstream purpose (touch detection, the regression endpoint,
    breakout/exit checks, stop-loss placement): price entering a part of
    the FVG that falls outside the fib band must never count as a valid
    zone entry. Compute this once per analysis and reuse it everywhere
    "the zone" is referenced, so nothing downstream can disagree about
    what counts as "inside".

    Returns None if the FVG and the fib band don't actually overlap
    (shouldn't happen for an FVG already selected by
    fvgs_overlapping_fib, since that requires at least one fib price
    inside the FVG -- which is itself inside [fib_low, fib_high] -- but
    guarded here for safety).
    """
    fib_low = min(fib_levels.values())
    fib_high = max(fib_levels.values())
    zone_low = max(fvg.gap_low, fib_low)
    zone_high = min(fvg.gap_high, fib_high)
    if zone_low > zone_high:
        return None
    return zone_low, zone_high
