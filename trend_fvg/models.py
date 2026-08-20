"""Core data structures shared across the strategy modules."""

from dataclasses import dataclass
from typing import NamedTuple, Optional


@dataclass(frozen=True)
class Candle:
    index: int
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body_low(self) -> float:
        return min(self.open, self.close)

    @property
    def body_high(self) -> float:
        return max(self.open, self.close)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_ratio(self) -> float:
        rng = self.range
        return self.body_size / rng if rng > 0 else 0.0


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str  # "high" or "low"


@dataclass(frozen=True)
class FVG:
    idx1: int
    idx2: int
    idx3: int
    kind: str  # "bullish" or "bearish"
    gap_low: float
    gap_high: float
    confirmed_idx: int  # index at which the 5-candle invalidation window closes


@dataclass
class Signal:
    symbol: str
    timeframe: str
    trend: str  # "UP" or "DOWN"
    status: str  # "IN_RANGE", "MARKET", "EXITED"
    zone_low: float
    zone_high: float
    fib_ratio: float
    angle_degrees: float
    touch_index: int
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None


class AnalysisResult(NamedTuple):
    """Outcome of running the pipeline for one symbol/timeframe: either a
    Signal (accepted) with reason=None, or signal=None with a short,
    human-readable reason suitable for a one-line scan log entry.
    """

    signal: Optional[Signal]
    reason: Optional[str]
