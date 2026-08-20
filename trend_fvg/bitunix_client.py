"""Minimal REST client for Bitunix futures market-data endpoints.

NOTE: Bitunix's public API documentation could not be reached from the
environment this script was written in (network egress to the docs host
was blocked). The endpoint paths and response field names below are the
best available guess based on public search results and Bitunix's own
usage examples, and MUST be verified on a device with real network access
before relying on this script for trading decisions.

Run `python main.py --check-api` to print the raw JSON returned by the
symbols and kline endpoints -- use that output to fix `base_url` /
`interval_map` / field names in config.json if anything below is wrong.
"""

import requests

from .models import Candle


class BitunixAPIError(RuntimeError):
    pass


class BitunixClient:
    def __init__(self, config):
        self.base_url = config["base_url"].rstrip("/")
        self.interval_map = config["interval_map"]
        self.timeout = config.get("request_timeout_seconds", 10)

    def _get(self, path, params=None):
        url = self.base_url + path
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise BitunixAPIError("Request to %s failed: %s" % (url, exc)) from exc
        if resp.status_code != 200:
            raise BitunixAPIError(
                "GET %s returned HTTP %s: %s" % (url, resp.status_code, resp.text[:500])
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise BitunixAPIError("GET %s returned non-JSON body: %s" % (url, resp.text[:500])) from exc
        return payload

    def get_symbols(self, quote_currency="USDT"):
        """Return a list of tradable symbols quoted in `quote_currency`."""
        payload = self._get("/tickers")
        data = payload.get("data", payload)
        if not isinstance(data, list):
            raise BitunixAPIError(
                "Unexpected /tickers response shape, expected a list under 'data': %r" % (payload,)
            )
        symbols = []
        for item in data:
            symbol = item.get("symbol") or item.get("symbolName")
            if symbol and symbol.upper().endswith(quote_currency.upper()):
                symbols.append(symbol)
        if not symbols:
            raise BitunixAPIError(
                "No symbols parsed from /tickers response -- check field names against raw output "
                "(run with --check-api)."
            )
        return sorted(set(symbols))

    def get_klines(self, symbol, timeframe, limit=250):
        """Return a chronologically ordered list of Candle objects."""
        interval = self.interval_map.get(timeframe, timeframe)
        payload = self._get("/kline", params={"symbol": symbol, "interval": interval, "limit": limit})
        data = payload.get("data", payload)
        if not isinstance(data, list):
            raise BitunixAPIError(
                "Unexpected /kline response shape for %s %s, expected a list under 'data': %r"
                % (symbol, timeframe, payload)
            )
        candles = []
        for raw in data:
            ts = raw.get("ts") or raw.get("time") or raw.get("t")
            try:
                candles.append(
                    Candle(
                        index=0,  # reassigned below after sorting
                        timestamp=int(ts),
                        open=float(raw.get("open") or raw.get("o")),
                        high=float(raw.get("high") or raw.get("h")),
                        low=float(raw.get("low") or raw.get("l")),
                        close=float(raw.get("close") or raw.get("c")),
                        volume=float(raw.get("baseVol") or raw.get("vol") or raw.get("volume") or raw.get("b") or 0.0),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise BitunixAPIError(
                    "Could not parse kline entry for %s %s: %r (%s)" % (symbol, timeframe, raw, exc)
                ) from exc
        candles.sort(key=lambda c: c.timestamp)
        candles = [
            Candle(
                index=i,
                timestamp=c.timestamp,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for i, c in enumerate(candles)
        ]
        return candles

    def check_api(self, symbol="BTCUSDT", timeframe="5m"):
        """Diagnostic helper: dump raw responses so endpoint/field mismatches can be fixed."""
        print("=== GET /tickers ===")
        try:
            print(self._get("/tickers"))
        except BitunixAPIError as exc:
            print("ERROR: %s" % exc)
        print()
        print("=== GET /kline (symbol=%s interval=%s) ===" % (symbol, self.interval_map.get(timeframe, timeframe)))
        try:
            print(
                self._get(
                    "/kline",
                    params={"symbol": symbol, "interval": self.interval_map.get(timeframe, timeframe), "limit": 5},
                )
            )
        except BitunixAPIError as exc:
            print("ERROR: %s" % exc)
