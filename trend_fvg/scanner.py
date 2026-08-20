"""Iterate symbols x timeframes, run the pipeline, and report signals.

Kline fetches are I/O-bound (waiting on Bitunix's API), so symbol/timeframe
pairs are fetched concurrently with a thread pool instead of one blocking
request after another -- across ~200 symbols x 4 timeframes that would
otherwise make a full scan cycle take far longer than the poll interval.

Every symbol/timeframe check prints exactly one condensed line to stdout
(e.g. "BTCUSDT 5m: rejected (no clear trend)" or
"BTCUSDT 1h: accepted -> MARKET") so the log stays readable on a narrow
Termux terminal. Full error detail (raw HTTP/API errors, timeouts, etc.)
is written to a debug log file instead of stdout -- see
configure_debug_logging().
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import engine
from .bitunix_client import BitunixAPIError

DEFAULT_MAX_WORKERS = 15

_debug_logger = logging.getLogger("trend_fvg.debug")
_debug_logger.addHandler(logging.NullHandler())


def configure_debug_logging(log_path):
    """Route full error/API details to `log_path` instead of stdout.
    Call once at startup; stdout stays limited to one condensed line per
    symbol/timeframe check regardless of this setting.
    """
    _debug_logger.setLevel(logging.DEBUG)
    _debug_logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _debug_logger.addHandler(handler)
    _debug_logger.propagate = False


def get_symbol_list(client, cfg, override=None):
    if override:
        return override
    return client.get_symbols(cfg["quote_currency"])


def _short_fetch_error(exc):
    """A one-word-ish category for the condensed stdout line. The full
    exception text always goes to the debug log regardless.
    """
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "proxy" in text or "connection" in text:
        return "connection error"
    if "http" in text:
        return "HTTP error"
    return "fetch error"


def _check_one(client, cfg, symbol, timeframe):
    """Runs in a worker thread. Always returns (signal_or_None, log_line);
    never raises, so one bad symbol can't stall or crash the batch.
    """
    try:
        candles = client.get_klines(symbol, timeframe, cfg["candle_history"])
    except BitunixAPIError as exc:
        _debug_logger.debug("%s %s: kline fetch failed: %s", symbol, timeframe, exc)
        reason = _short_fetch_error(exc)
        return None, "%s %s: rejected (fetch failed: %s)" % (symbol, timeframe, reason)

    signal, reason = engine.analyze(candles, symbol, timeframe, cfg["market_bias"], cfg)
    if signal is None:
        return None, "%s %s: rejected (%s)" % (symbol, timeframe, reason)
    return signal, "%s %s: accepted -> %s" % (symbol, timeframe, signal.status)


def run_scan(client, cfg, symbols=None):
    symbols = get_symbol_list(client, cfg, symbols)
    tasks = [(symbol, timeframe) for symbol in symbols for timeframe in cfg["timeframes"]]
    max_workers = cfg.get("max_workers", DEFAULT_MAX_WORKERS)

    signals = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_check_one, client, cfg, symbol, timeframe) for symbol, timeframe in tasks]
        for future in as_completed(futures):
            signal, log_line = future.result()
            print(log_line)
            if signal:
                signals.append(signal)
    return signals


def format_signal(signal):
    """Multi-line, narrow-terminal-friendly rendering of a single signal
    (plain text only, no special characters -- this is read in Termux).
    """
    lines = [
        "[%s] [%s] %s" % (signal.symbol, signal.timeframe, signal.status),
        "  direction: %s" % signal.trend,
        "  zone: [%.8g, %.8g]" % (signal.zone_low, signal.zone_high),
        "  fib: %.3f" % signal.fib_ratio,
        "  angle: %.1fdeg" % signal.angle_degrees,
    ]
    if signal.status == "MARKET":
        lines.append("  entry: %.8g" % signal.entry)
        lines.append("  stop_loss: %.8g" % signal.stop_loss)
        lines.append("  target: %.8g" % signal.target)
    return "\n".join(lines)


def print_report(signals):
    if not signals:
        print("No active signals this cycle.")
        return
    for signal in signals:
        print(format_signal(signal))
        print()
