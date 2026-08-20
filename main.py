#!/usr/bin/env python3
"""Trend-FVG signal scanner for Bitunix futures (Termux-friendly, signal-only).

Usage examples:
  python main.py --set-bias LONG          # set today's manual market bias and exit
  python main.py --once                   # run a single scan pass and exit
  python main.py                          # run continuously, scanning every poll_interval_minutes
  python main.py --symbols BTCUSDT,ETHUSDT --once
  python main.py --check-api              # dump raw Bitunix API responses for debugging
"""

import argparse
import datetime
import sys
import time

from trend_fvg import config as config_module
from trend_fvg.bitunix_client import BitunixAPIError, BitunixClient
from trend_fvg.scanner import print_report, run_scan


def parse_args():
    parser = argparse.ArgumentParser(description="Trend-FVG signal scanner for Bitunix futures.")
    parser.add_argument("--config", default=None, help="Path to config.json (default: ./config.json)")
    parser.add_argument("--set-bias", choices=["LONG", "SHORT"], help="Set today's market bias and exit.")
    parser.add_argument("--once", action="store_true", help="Run a single scan pass and exit.")
    parser.add_argument("--interval", type=float, default=None, help="Override poll interval in minutes.")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbol override, e.g. BTCUSDT,ETHUSDT")
    parser.add_argument("--timeframes", default=None, help="Comma-separated timeframe override, e.g. 5m,15m")
    parser.add_argument("--check-api", action="store_true", help="Print raw API responses and exit.")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.set_bias:
        config_module.set_market_bias(args.set_bias, args.config)
        print("Market bias set to %s." % args.set_bias)
        return

    cfg = config_module.load_config(args.config)
    if args.interval is not None:
        cfg["poll_interval_minutes"] = args.interval
    if args.timeframes:
        cfg["timeframes"] = [tf.strip() for tf in args.timeframes.split(",") if tf.strip()]

    client = BitunixClient(cfg)

    if args.check_api:
        client.check_api()
        return

    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    print("Trend-FVG scanner starting. market_bias=%s timeframes=%s" % (cfg["market_bias"], cfg["timeframes"]))

    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n=== Scan at %s (bias=%s) ===" % (now, cfg["market_bias"]))
        try:
            signals = run_scan(client, cfg, symbols)
            print_report(signals)
        except BitunixAPIError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)

        if args.once:
            break
        time.sleep(cfg["poll_interval_minutes"] * 60)


if __name__ == "__main__":
    main()
