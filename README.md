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
3. **Reverse Fibonacci** -- drawn from the most recent swing extreme back
   to the prior opposite swing. Levels marked: `0.618`, `0.705`, `0.79`.
4. **FVG confluence** -- all valid Fair Value Gaps inside that impulsive
   leg are found; at least one must overlap a fib level.
5. **Retracement slope + trendline** -- a line is drawn from the swing
   extreme to the *last* candle that touched the FVG zone (not just any
   two points), and that touch must have happened strictly *after* the
   swing extreme -- price passing through the zone's price band on its
   way up to make the high (which it always does) doesn't count; see
   "zone-entry false positive" below. The line's angle (abs value, on a
   price-range-normalized synthetic scale -- see `trend_fvg/slope.py` for
   why raw price/time units can't be compared directly) must be shallow
   (< 30 degrees), and at least `min_trendline_touches` (default 3)
   candles along that line -- swing extreme and final touch included --
   must actually rest on it for the line to count as confirmed rather
   than two arbitrary points.
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
  fibonacci.py               reverse fib level calculation
  fvg.py                     FVG detection with the 5-candle invalidation rule
  confluence.py               FVG <-> fib level overlap check
  slope.py                    normalized retracement angle + trendline touch count
  engine.py                   per symbol/timeframe pipeline (steps 1-6), returns AnalysisResult
  scanner.py                  loops over symbols x timeframes, condensed scan log + report
tests/                       unit tests for the pivot/fib/FVG/slope logic (synthetic data)
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
