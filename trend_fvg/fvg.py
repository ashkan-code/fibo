"""Fair Value Gap (FVG) detection with the 5-candle invalidation window.

Standard 3-candle definition:
  bullish FVG: candle1.high < candle3.low   -> gap = [candle1.high, candle3.low]
  bearish FVG: candle1.low  > candle3.high  -> gap = [candle3.high, candle1.low]

Extra validity rule (the important one): look at the 5-candle window made of
the 3 gap candles plus the 2 candles that follow. If either of those 2
follow-up candles has a *body* (open-close range, not its wick) that
intrudes into the interior of the gap, the FVG is invalidated -- even
though candle1/candle3 alone would otherwise look valid. A long-wicked
doji poking into the gap does NOT invalidate it; only a body overlap
counts. (candle1/candle3 can never intrude past their own boundary by
construction, and candle2 is the impulsive move that creates the gap in
the first place -- its body is expected to span across it -- so neither
is checked.)
"""

from .models import FVG


def _body_intrudes(candle, gap_low, gap_high):
    """True if this candle's body enters the *interior* of the gap.
    Strict inequalities so a body that merely touches the gap boundary
    (which candle1/candle3 always do, by construction) does not count.
    """
    return candle.body_high > gap_low and candle.body_low < gap_high


def detect_fvgs(candles, start_idx, end_idx, trend):
    """Detect confirmed-valid FVGs within candles[start_idx..end_idx]
    (inclusive), in the direction implied by `trend` (UP -> bullish gaps,
    DOWN -> bearish gaps).

    An FVG candidate that doesn't yet have 2 full candles after candle3
    (i.e. the 5-candle window hasn't closed) is skipped -- it will be
    picked up on a later run once enough candles exist.
    """
    fvgs = []
    last_i = min(end_idx, len(candles) - 1) - 2
    for i in range(start_idx, last_i + 1):
        c1, c3 = candles[i], candles[i + 2]

        if trend == "UP":
            if not (c1.high < c3.low):
                continue
            gap_low, gap_high, kind = c1.high, c3.low, "bullish"
        elif trend == "DOWN":
            if not (c1.low > c3.high):
                continue
            gap_low, gap_high, kind = c3.high, c1.low, "bearish"
        else:
            raise ValueError("trend must be 'UP' or 'DOWN', got %r" % (trend,))

        window_end = i + 4
        if window_end >= len(candles):
            continue  # not enough history yet to confirm this candidate

        # Check the 5-candle window (candle1..candle3 plus the 2 that
        # follow) for a body filling the gap. candle1/candle3 can never
        # intrude past their own boundary by construction, and candle2 is
        # the impulsive move that creates the gap in the first place (its
        # body is expected to span across it) -- so only the two follow-up
        # candles can actually invalidate the FVG.
        invalidated = any(_body_intrudes(candles[j], gap_low, gap_high) for j in (i + 3, i + 4))
        if invalidated:
            continue

        fvgs.append(
            FVG(
                idx1=i,
                idx2=i + 1,
                idx3=i + 2,
                kind=kind,
                gap_low=gap_low,
                gap_high=gap_high,
                confirmed_idx=window_end,
            )
        )
    return fvgs
