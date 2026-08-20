import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from trend_fvg import scanner
from trend_fvg.bitunix_client import BitunixAPIError
from trend_fvg.models import Signal


class _FakeClient:
    """Stubs get_klines so run_scan can be exercised without any network
    access -- one symbol/timeframe raises (simulating a timeout/API
    error), the rest return an empty candle list, which engine.analyze
    rejects early with a deterministic reason.
    """

    def __init__(self):
        self.calls = []

    def get_klines(self, symbol, timeframe, limit):
        self.calls.append((symbol, timeframe))
        if symbol == "FAILUSDT":
            raise BitunixAPIError("Request timed out after 8s")
        return []  # too few candles -> deterministic "insufficient candle history" rejection


class TestCondensedScanLog(unittest.TestCase):
    def test_run_scan_prints_one_line_per_check_and_routes_errors_to_debug_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "debug.log")
            scanner.configure_debug_logging(log_path)

            client = _FakeClient()
            cfg = {
                "quote_currency": "USDT",
                "timeframes": ["5m"],
                "candle_history": 250,
                "market_bias": "LONG",
                "max_workers": 4,
                "pivot_lookback": 3,
            }

            buf = io.StringIO()
            with redirect_stdout(buf):
                signals = scanner.run_scan(client, cfg, symbols=["FAILUSDT", "OKUSDT"])

            self.assertEqual(signals, [])
            lines = [line for line in buf.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)  # exactly one condensed line per symbol/timeframe check
            for line in lines:
                self.assertNotIn("\n", line)
                self.assertLess(len(line), 120)  # stays short enough for a narrow terminal

            fail_line = next(l for l in lines if l.startswith("FAILUSDT"))
            self.assertEqual(fail_line, "FAILUSDT 5m: rejected (fetch failed: timeout)")
            ok_line = next(l for l in lines if l.startswith("OKUSDT"))
            self.assertEqual(ok_line, "OKUSDT 5m: rejected (insufficient candle history)")

            # The raw exception text must NOT appear on stdout...
            self.assertNotIn("Request timed out after 8s", buf.getvalue())
            # ...but must be in the debug log file.
            with open(log_path, "r", encoding="utf-8") as f:
                debug_contents = f.read()
            self.assertIn("Request timed out after 8s", debug_contents)

    def test_accepted_signal_line_format(self):
        signal = Signal(
            symbol="BTCUSDT",
            timeframe="1h",
            trend="UP",
            status="MARKET",
            zone_low=20,
            zone_high=30,
            fib_ratio=0.382,
            angle_degrees=12.1,
            touch_index=5,
            entry=0.0909,
            stop_loss=0.0899,
            target=0.0914,
        )

        class _OneSignalClient:
            def get_klines(self, symbol, timeframe, limit):
                return ["not-empty"]

        import trend_fvg.engine as engine_module

        original_analyze = engine_module.analyze
        try:
            from trend_fvg.models import AnalysisResult

            engine_module.analyze = lambda *a, **k: AnalysisResult(signal, None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                scanner.run_scan(
                    _OneSignalClient(),
                    {"quote_currency": "USDT", "timeframes": ["1h"], "candle_history": 250, "market_bias": "LONG"},
                    symbols=["BTCUSDT"],
                )
            self.assertEqual(buf.getvalue().strip(), "BTCUSDT 1h: accepted -> MARKET")
        finally:
            engine_module.analyze = original_analyze


if __name__ == "__main__":
    unittest.main()
