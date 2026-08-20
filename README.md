# Trend-FVG Bitunix Scanner

A signal-only Python scanner for Bitunix futures. It does **not** place any
trades -- it periodically checks a list of symbols across multiple
timeframes and prints a status line whenever price is interacting with a
qualifying trend + Fibonacci + Fair Value Gap (FVG) setup.

## Strategy summary

For each symbol and each timeframe (`5m`, `15m`, `30m`, `1h`, checked
independently):

1. **Market bias filter** -- you set `LONG` or `SHORT` manually once a day,
   either interactively (`main.py` prompts `LONG? (y/n):` at startup) or
   non-interactively with `--set-bias` for cron/scripting. Only trends
   matching that bias are considered.
2. **Trend filter** -- swing highs/lows (fractals) are detected; a
   sequence of higher-high + higher-low is an uptrend, lower-high +
   lower-low is a downtrend. Anything else is skipped.
3. **Fibonacci** -- drawn in the standard direction: low -> high for an
   uptrend (0% at the swing low, 100% at the swing high), high -> low for
   a downtrend. Levels marked: `0.382`, `0.295`, `0.21` -- the mirror of
   the classic `0.618`/`0.705`/`0.79` around the 50% midpoint, which is
   what standard-direction drawing requires to land the zone in the
   discount (resp. premium) area. Same prices either way; see
   `trend_fvg/fibonacci.py`.
4. **FVG confluence** -- all valid Fair Value Gaps inside that impulsive
   leg are found; at least one must overlap a fib level. "The zone" from
   here on is the **FVG/fib intersection** -- `max(FVG_low, fib_low)` to
   `min(FVG_high, fib_high)` -- not the full FVG range. Price wicking
   into a part of the FVG that falls outside the fib band never counts
   as reaching the zone, for anything below: not the regression endpoint,
   not touch detection, not breakout/exit, not stop-loss placement. This
   intersection is computed once (`trend_fvg/confluence.py`,
   `intersect_zone`) and reused everywhere so nothing downstream can
   disagree about what's "inside". See `trend_fvg/confluence.py`.
5. **Retracement slope, via linear regression** -- fit a simple linear
   regression (close price vs. candle index) over every candle from the
   true start of the impulsive move (the swing that began the leg) up
   to the first candle that reached the zone. Convert the fitted slope
   to degrees the same way a raw two-point slope is normalized (against
   the leg's own price range, so raw price/time units are never compared
   directly -- see `trend_fvg/slope.py`), take the absolute value, and
   require it to be shallow (< 30 degrees). Fitting over the whole
   observed leg is far more robust than checking a handful of discrete
   points on a two/three-point trendline: one noisy candle can't flip
   the verdict.
6. **Signal** -- once price has touched the zone (a wick touch is enough,
   no close required):
   - still trading in/around the zone -> `IN_RANGE`
   - a candle with body > 70% of its own range breaks through the zone in
     the trend direction -> `MARKET`, with a stop-loss behind the zone and
     a target at the swing extreme the fib was drawn from
   - price touched the zone and left again without breaking -> `EXITED`

### FVG detection detail (the riskiest part)

A Fair Value Gap uses the standard 3-candle definition (candle1 vs candle3
gap, candle2 is the impulsive move in between). Before an FVG is treated as
valid, a 5-candle window (the 3 gap candles plus the 2 that follow) is
checked: if **either of the 2 follow-up candles' bodies** (open-close
range) intrudes into the gap, the FVG is invalidated. candle1/candle3
can't intrude past their own boundary by construction, and candle2 is the
impulsive move that creates the gap in the first place (its body is
expected to span across it), so only the follow-up candles matter. A long
wick poking into the gap does **not** invalidate it -- only a body overlap
counts, since a wick just means indecision, not the gap actually being
filled. See `trend_fvg/fvg.py`.

## Project layout

```
main.py                  CLI entrypoint / scan loop
config.json               settings + today's manual market bias
trend_fvg/
  config.py                load/save config.json, --set-bias helper
  bitunix_client.py         REST client for Bitunix (symbols + klines)
  models.py                 Candle / Swing / FVG / Signal data structures
  swings.py                 pivot detection + HH/HL / LH/LL trend classification
  fibonacci.py               fib level calculation (standard direction)
  fvg.py                     FVG detection with the 5-candle invalidation rule
  confluence.py               FVG <-> fib level overlap check + FVG/fib intersect_zone
  slope.py                    normalized retracement angle via linear regression
  engine.py                   per symbol/timeframe pipeline (steps 1-6), returns AnalysisResult
  scanner.py                  loops over symbols x timeframes, condensed scan log + report
tests/                       unit tests for the pivot/fib/FVG/slope/confluence logic (synthetic data)
```

Kline fetches for all symbol x timeframe pairs run concurrently through a
thread pool (`max_workers` in `config.json`, default 15) since they're
I/O-bound waits on Bitunix's API, not CPU work -- across ~200 symbols x 4
timeframes that keeps a full scan cycle well under the poll interval. A
short per-request timeout (`request_timeout_seconds`, default 8s) means one
slow/unresponsive symbol is logged as skipped and the rest of the batch
keeps going instead of stalling.

### Scan log

Every symbol/timeframe check prints exactly one condensed line, e.g.:

```
MUSDT 5m: rejected (no clear trend)
MUSDT 15m: rejected (retracement too steep, angle=42.3deg)
BTCUSDT 1h: accepted -> MARKET
```

`engine.analyze()` returns an `AnalysisResult(signal, reason)`: on
acceptance `signal` is set and `reason` is `None`; on rejection `signal`
is `None` and `reason` is a short phrase describing exactly which pipeline
step said no. `scanner.py` turns that straight into the one-line summary
above -- no raw exception text, JSON, or multi-line dumps on stdout.

Full error detail (raw HTTP/timeout/connection errors from a fetch
failure) is written instead to a debug log file (`debug_log_file` in
`config.json`, default `trend_fvg_debug.log`; override per run with
`--log-file`). Accepted signals additionally get the detailed multi-line
block (direction/zone/fib/angle/entry/stop_loss/target) after the scan log,
as before.

## Setup (Termux)

```
pkg update && pkg install python
pip install -r requirements.txt
```

## Usage

```
# Interactive: prompts "LONG? (y/n): " for today's bias, then runs continuously
python main.py

# Non-interactive bias override, e.g. for cron/scripting (skips the prompt)
python main.py --set-bias LONG

# Sanity-check the Bitunix endpoints before trusting the scanner
python main.py --check-api

# Single pass, useful while testing
python main.py --set-bias LONG --once

# Limit to specific symbols/timeframes while testing
python main.py --set-bias LONG --once --symbols BTCUSDT,ETHUSDT --timeframes 5m,15m
```

To run it in the background on Termux across app restarts, use
`termux-wake-lock` plus a persistent session (e.g. `tmux` or
`termux-services`), or schedule single `--once` runs with `termux-job-scheduler`
/ `cron` (via `termux-boot` + `crond`) at your preferred interval.

## Important: verify the Bitunix API mapping before relying on this

The Bitunix API documentation host was unreachable from the environment
this scanner was written in, so the endpoint paths, query parameters, and
response field names in `trend_fvg/bitunix_client.py` are best-effort
guesses based on public references, **not** a verified integration.

Before trusting any signal from this script:

1. Run `python main.py --check-api` on a device with real network access.
2. Compare the raw JSON it prints against the actual Bitunix OpenAPI docs
   (https://openapidoc.bitunix.com/).
3. Fix `base_url` / `interval_map` in `config.json`, and the field-name
   fallbacks in `BitunixClient.get_symbols` / `get_klines`, if anything
   doesn't match.

### Fixed: zone-entry false positive (pre-extreme touch)

Live testing surfaced a real false-positive signal (AWEUSDT, 5m): the
symbol was flagged as having entered its FVG zone while price was still
trending up, well above the swing high, having never pulled back at all.
Root cause: the "has price touched the zone" search window
(`window_start` in `engine.py`) was bounded only by the FVG's
confirmation index and `recent_touch_window`, with no floor at the swing
extreme itself. An impulsive leg always passes through its own eventual
FVG's price band on the way up (candle1 of a bullish FVG touches
`gap_low` by construction), and can easily wick back into it during a
mid-rally consolidation *before* the swing high is even made -- neither
is a real retracement, but the old code could pick either up as a
"touch" if it fell inside the window. Fixed by adding
`extreme.index + 1` as an explicit floor, so only candles strictly after
the swing extreme can ever count as a zone entry. Regression-tested in
`tests/test_engine.py` (`TestPreExtremeTouchIsNotARetracement`), with a
fixture verified to reproduce the bug against the old (unfloored)
window before the fix.

### Fixed: fib/FVG zone drawn from the wrong swing low (wrong-anchor bug)

A second, deeper bug behind the same AWEUSDT false positive: even once a
touch is only counted after the swing extreme, the fib itself was being
drawn from the wrong low. `get_impulsive_leg()` (`trend_fvg/swings.py`)
picked the *nearest* swing low before the current high as the fib's 100%
anchor. In a large impulsive move followed by a series of minor,
shallower higher-low pullbacks near the top -- completely normal price
action -- the nearest prior low is one of those minor pullbacks, not
where the move actually started. Anchoring the fib there draws it across
only the last small internal leg, so the 0.618/0.705/0.79 levels land up
near the recent highs instead of deep below the true leg's midpoint,
which is exactly what was seen on the live chart: the zone sitting at
the top of the move instead of in the discount area.

Fixed by walking backward from the nearest prior low through the chain
of consecutive swing lows (for an uptrend; consecutive swing highs for a
downtrend), extending the anchor back as long as each earlier one is
still lower (resp. higher), and stopping at the earliest point still in
that unbroken chain -- i.e. the swing that actually began the current
impulsive structure, not just the closest one in time. Regression-tested
in `tests/test_swings.py` (`TestImpulsiveLegFindsTrueMoveOrigin`) with
realistic multi-candle OHLC modeling exactly this shape (a deep true
start, a large impulsive ramp, then two rounds of new-high-then-minor-
pullback near the top), asserting both that the true origin is selected
over either minor pullback and that the resulting fib levels land below
the leg's true midpoint -- and, in a fixture-sanity test, that the old
nearest-low anchor would have placed them above it.

### Changed: fib ratios switched to standard draw direction (0.382/0.295/0.21)

`fibonacci.py` previously drew the fib in a "reverse" direction (0% at
the swing extreme, 100% at the prior swing) and used the classic
0.618/0.705/0.79 ratios to land the confluence zone in the discount
(resp. premium) area. It now draws the fib in the standard direction
instead -- low -> high for an uptrend (0% at the swing low, 100% at the
swing high), high -> low for a downtrend -- which means the ratios that
land in the same discount/premium area are the mirror around the 50%
midpoint: `0.382`, `0.295`, `0.21` (default `fib_ratios` in
`config.json`). Both conventions produce the *exact same prices*; only
which end of the leg is labeled "0%" changed. Regression-tested in
`tests/test_fibonacci.py` (discount/premium-zone tests use the new
ratios against the standard-direction formula) and
`tests/test_swings.py` (`TestImpulsiveLegFindsTrueMoveOrigin`, updated
to match).

### Changed: zone is now the FVG/fib intersection, and slope uses linear regression

Two related changes, both centered on treating the FVG/fib **intersection**
as the one true "valid zone" instead of the full FVG range:

- **Zone entry.** `intersect_zone()` (`trend_fvg/confluence.py`) computes
  `max(FVG_low, fib_low)` to `min(FVG_high, fib_high)` once per analysis,
  and `engine.py` uses that result -- not the raw FVG -- for every
  downstream check: touch detection, the regression endpoint, the
  breakout/exit scan, and stop-loss placement. Price wicking into the
  part of an FVG that falls outside the fib band no longer counts as
  reaching the zone at all.
- **Retracement slope.** Replaced the two/three-point trendline +
  touch-counting check (`count_trendline_touches`,
  `min_trendline_touches`, removed) with a linear regression
  (`compute_regression_angle_degrees` in `trend_fvg/slope.py`) fit over
  every candle's close price from the true start of the impulsive move
  (the leg's actual origin, per the earlier true-move-origin fix) through
  to the *first* candle that reached the (now intersection-based) zone.
  The fitted slope is normalized into degrees the same way the old
  two-point slope was (via `compute_angle_degrees` with `candle_delta=1`,
  reusing the same normalize-by-leg-range-then-atan2 primitive), and its
  absolute value must stay under `max_retracement_angle_degrees`.

  Touch-counting was removed rather than kept as a secondary check: the
  regression already fits over the whole observed leg (frequently dozens
  of candles), which is a substantially more robust "was this an orderly
  move" signal than whether ~3 discrete candles happened to sit on a
  straight line -- keeping both would have been redundant complexity for
  little additional signal, and the touches threshold was calibrated for
  the old (much shorter) extreme-to-touch span, not this one.

  One notable property: because the regression is a least-squares fit
  over the *entire* leg (routinely 8+ candles just for the impulsive
  climb before any pullback even starts), a single noisy candle now has
  much less leverage over the verdict than it used to -- see the
  "steep retracement" test in `tests/test_engine.py` for what it actually
  takes to trip the threshold once real leg structure is mixed in, versus
  the clean, isolated cases in `tests/test_slope.py`
  (`TestRegressionAngle`).

Regression-tested in `tests/test_confluence.py` (`intersect_zone` against
FVG-narrower-than-band, band-narrower-than-FVG -- the reported bug shape
-- partial overlap on each side, and no-overlap cases) and
`tests/test_engine.py` (price reaching the FVG but not the intersection
-> no signal; price reaching the actual intersection -> normal signal
logic; shallow/steep regression slopes for both uptrend and downtrend
pullbacks, confirming abs() handles the naturally-opposite raw slope sign
in each direction).

## Known limitations / ideas for later

- The scanner is stateless across runs: it recomputes everything from
  fresh candle history each cycle rather than persisting signal state, so
  a `MARKET` signal may be reprinted on the next cycle if the breakout
  candle is still inside the lookback window. Adding a small on-disk
  state store to dedupe repeated alerts is a natural next step.
- The daily market bias is fully manual, as specified. Automating it from
  OTHERS.D or another source is left for a future version.
- Pivot lookback (3 candles each side) and other thresholds are in
  `config.json` and were chosen as reasonable starting points -- tune them
  with backtesting once real data is available.
