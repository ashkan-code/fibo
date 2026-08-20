"""Iterate symbols x timeframes, run the pipeline, and report signals."""

import sys

from . import engine
from .bitunix_client import BitunixAPIError


def get_symbol_list(client, cfg, override=None):
    if override:
        return override
    return client.get_symbols(cfg["quote_currency"])


def run_scan(client, cfg, symbols=None):
    symbols = get_symbol_list(client, cfg, symbols)
    signals = []
    for symbol in symbols:
        for timeframe in cfg["timeframes"]:
            try:
                candles = client.get_klines(symbol, timeframe, cfg["candle_history"])
                signal = engine.analyze(candles, symbol, timeframe, cfg["market_bias"], cfg)
                if signal:
                    signals.append(signal)
            except BitunixAPIError as exc:
                print("[WARN] %s %s: %s" % (symbol, timeframe, exc), file=sys.stderr)
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
