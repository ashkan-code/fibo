from trend_fvg.models import Candle


def make_candles(ohlc):
    """ohlc: list of (open, high, low, close) tuples -> list[Candle] with
    sequential index/timestamp.
    """
    return [
        Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
        for i, (o, h, l, c) in enumerate(ohlc)
    ]
