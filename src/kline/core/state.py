from dataclasses import dataclass, field
from typing import Any

from kline.core.models import KlineBar, TickRecord


@dataclass(slots=True)
class SymbolAggregationState:
    active_bars: dict[int, KlineBar] = field(default_factory=dict)
    watermark: int = 0
    flushed_until: int = -1

    def update_watermark(self, timestamp: int) -> tuple[int, bool]:
        previous_watermark = self.watermark
        self.watermark = max(previous_watermark, timestamp)
        return previous_watermark, timestamp < previous_watermark

    def should_drop_late_tick(self, timestamp_bucket: tuple[int, int]) -> bool:
        return timestamp_bucket[1] <= self.flushed_until

    def upsert_bar(
        self,
        row: TickRecord,
        interval: str,
        timestamp_bucket: tuple[int, int],
    ) -> None:
        if (bar := self.active_bars.get(timestamp_bucket[0])) is None:
            self.active_bars[timestamp_bucket[0]] = KlineBar.from_tick(
                row=row, interval=interval, timestamp_bucket=timestamp_bucket
            )
            return

        bar.update_from_tick(row)

    def flush_ready_bars(self, max_lateness_ms: int) -> list[KlineBar]:
        flush_before = self.watermark - max_lateness_ms
        flushable_starts = [
            start
            for start, bar in self.active_bars.items()
            if bar.bucket_end_timestamp <= flush_before
        ]

        flushed_bars: list[KlineBar] = []
        for start in sorted(flushable_starts):
            bar_to_flush = self.active_bars.pop(start)
            self.flushed_until = max(
                self.flushed_until, bar_to_flush.bucket_end_timestamp
            )
            flushed_bars.append(bar_to_flush)
        return flushed_bars

    def flush_remaining_bars(self) -> list[KlineBar]:
        return [self.active_bars[start] for start in sorted(self.active_bars)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_bars": [
                self.active_bars[start].to_csv_row()
                for start in sorted(self.active_bars)
            ],
            "watermark": self.watermark,
            "flushed_until": self.flushed_until,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SymbolAggregationState":
        active_bars = {
            int(bar_payload["bucket_start_timestamp"]): KlineBar.from_dict(bar_payload)
            for bar_payload in payload.get("active_bars", [])
        }
        return cls(
            active_bars=active_bars,
            watermark=int(payload.get("watermark", 0)),
            flushed_until=int(payload.get("flushed_until", -1)),
        )


@dataclass(slots=True)
class IntervalAggregationState:
    interval: str
    interval_ms: int
    symbol_states: dict[str, SymbolAggregationState] = field(default_factory=dict)

    @classmethod
    def from_interval(cls, interval: str) -> "IntervalAggregationState":
        if interval.endswith("m") and (minutes := int(interval[:-1])) > 0:
            return cls(interval=interval, interval_ms=minutes * 60 * 1000)
        raise ValueError(f"unsupported interval: {interval}")

    def flush_remaining_bars(self) -> list[KlineBar]:
        return [
            bar
            for symbol_state in self.symbol_states.values()
            for bar in symbol_state.flush_remaining_bars()
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval": self.interval,
            "interval_ms": self.interval_ms,
            "symbol_states": {
                symbol: state.to_dict() for symbol, state in self.symbol_states.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IntervalAggregationState":
        return cls(
            interval=str(payload["interval"]),
            interval_ms=int(payload["interval_ms"]),
            symbol_states={
                symbol: SymbolAggregationState.from_dict(state_payload)
                for symbol, state_payload in payload.get("symbol_states", {}).items()
            },
        )


@dataclass(slots=True)
class IntervalStates:
    by_interval: dict[str, IntervalAggregationState] = field(default_factory=dict)

    def __contains__(self, interval: str) -> bool:
        return interval in self.by_interval

    def __getitem__(self, interval: str) -> IntervalAggregationState:
        return self.by_interval[interval]

    def __setitem__(self, interval: str, state: IntervalAggregationState) -> None:
        self.by_interval[interval] = state

    def items(self):
        return self.by_interval.items()

    def values(self):
        return self.by_interval.values()

    def get_or_create(self, interval: str) -> IntervalAggregationState:
        if interval not in self.by_interval:
            self.by_interval[interval] = IntervalAggregationState.from_interval(
                interval
            )
        return self.by_interval[interval]

    def to_dict(self) -> dict[str, Any]:
        return {
            interval: state.to_dict() for interval, state in self.by_interval.items()
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "IntervalStates":
        if payload is None:
            return cls()

        return cls(
            by_interval={
                interval: IntervalAggregationState.from_dict(state_payload)
                for interval, state_payload in payload.items()
            }
        )
