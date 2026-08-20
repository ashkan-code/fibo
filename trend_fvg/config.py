"""Configuration loading/saving, including the manually set daily market bias."""

import json
import os

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
DEFAULT_DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trend_fvg_debug.log")

DEFAULTS = {
    "market_bias": "LONG",
    "pivot_lookback": 3,
    "fib_ratios": [0.618, 0.705, 0.79],
    "max_retracement_angle_degrees": 30,
    "min_trendline_touches": 3,
    "breakout_body_ratio": 0.70,
    "recent_touch_window": 20,
    "candle_history": 250,
    "poll_interval_minutes": 5,
    "timeframes": ["5m", "15m", "30m", "1h"],
    "quote_currency": "USDT",
    "base_url": "https://fapi.bitunix.com/api/v1/futures/market",
    "interval_map": {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h"},
    "request_timeout_seconds": 8,
    "max_workers": 15,
    "debug_log_file": DEFAULT_DEBUG_LOG_PATH,
}

VALID_BIAS = ("LONG", "SHORT")


def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    config = dict(DEFAULTS)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        config.update(stored)
    else:
        save_config(config, path)
    if config["market_bias"] not in VALID_BIAS:
        raise ValueError(
            "Invalid market_bias '%s' in config. Must be LONG or SHORT." % config["market_bias"]
        )
    return config


def save_config(config, path=None):
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")


def set_market_bias(bias, path=None):
    bias = bias.upper()
    if bias not in VALID_BIAS:
        raise ValueError("market_bias must be one of %s, got '%s'" % (VALID_BIAS, bias))
    config = load_config(path)
    config["market_bias"] = bias
    save_config(config, path)
    return config
