"""Iterate symbols x timeframes, run the pipeline, and report signals.

Kline fetches are I/O-bound (waiting on Bitunix's API), so symbol/timeframe
pairs are fetched concurrently with a thread pool instead of one blocking
request after another -- across ~200 symbols x 4 timeframes that would
otherwise make a full scan cycle take far longer than the poll interval.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import engine
from .bitunix_client import BitunixAPIError

DEFAULT_MAX_WORKERS = 15


def get_symbol_list(client, cfg, override=None):
    if override:
        return override
    return client.get_symbols(cfg["quote_currency"])


def _fetch_and_analyze(client, cfg, symbol, timeframe):
    """Runs in a worker thread. Never raises -- API errors (including
    timeouts on an unresponsive symbol) are turned into a warning string
    so one bad symbol can't stall or crash the batch.
    """
    try:
        candles = client.get_klines(symbol, timeframe, cfg["candle_history"])
    except BitunixAPIError as exc:
        return None, "%s %s: skipped (%s)" % (symbol, timeframe, exc)
    signal = engine.analyze(candles, symbol, timeframe, cfg["market_bias"], cfg)
    return signal, None


def run_scan(client, cfg, symbols=None):
    symbols = get_symbol_list(client, cfg, symbols)
    tasks = [(symbol, timeframe) for symbol in symbols for timeframe in cfg["timeframes"]]
    max_workers = cfg.get("max_workers", DEFAULT_MAX_WORKERS)

    signals = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch_and_analyze, client, cfg, symbol, timeframe) for symbol, timeframe in tasks]
        for future in as_completed(futures):
            signal, warning = future.result()
            if warning:
                print("[WARN] %s" % warning, file=sys.stderr)
            if signal:
                signals.append(signal)
    return signals


def format_signal(signal):
    base = "[%s] [%s] %s | direction=%s | zone=[%.8g, %.8g] | fib=%.3f | angle=%.1fdeg" % (
        signal.symbol,
        signal.timeframe,
        signal.status,
        signal.trend,
        signal.zone_low,
        signal.zone_high,
        signal.fib_ratio,
        signal.angle_degrees,
    )
    if signal.status == "MARKET":
        base += " | entry=%.8g | stop_loss=%.8g | target=%.8g" % (
            signal.entry,
            signal.stop_loss,
            signal.target,
        )
    return base


def print_report(signals):
    if not signals:
        print("No active signals this cycle.")
        return
    for signal in signals:
        print(format_signal(signal))
