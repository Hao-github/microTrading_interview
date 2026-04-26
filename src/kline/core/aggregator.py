from dataclasses import dataclass, field
from typing import Iterable, Iterator

from src.kline.core.models import TaskConfig
from ..runtime.logger import get_logger
from .models import KlineBar, TickRecord


@dataclass
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


@dataclass
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


class KlineAggregator:
    def __init__(self, config: TaskConfig, max_lateness_ms: int = 30_000) -> None:
        self.max_lateness_ms = max_lateness_ms
        self.logger = get_logger("kline.aggregator", config.log_dir)

    def aggregate(
        self, rows: Iterable[TickRecord], intervals: str | list[str]
    ) -> Iterator[tuple[str, KlineBar]]:
        if isinstance(intervals, str):
            intervals = [intervals]

        interval_states = {
            interval: IntervalAggregationState.from_interval(interval)
            for interval in intervals
        }

        for row in rows:
            for interval in intervals:
                yield from self._process_row_for_interval(
                    row=row, interval_state=interval_states[interval]
                )

        for interval_state in interval_states.values():
            for bar in interval_state.flush_remaining_bars():
                yield interval_state.interval, bar

    def _bucket_range(self, timestamp: int, interval_ms: int) -> tuple[int, int]:
        start = timestamp - (timestamp % interval_ms)
        return start, start + interval_ms

    def _process_row_for_interval(
        self,
        row: TickRecord,
        interval_state: IntervalAggregationState,
    ) -> Iterator[tuple[str, KlineBar]]:
        if (state := interval_state.symbol_states.get(row.symbol)) is None:
            state = SymbolAggregationState(watermark=row.timestamp)
            interval_state.symbol_states[row.symbol] = state

        previous_watermark, is_out_of_order = state.update_watermark(row.timestamp)
        if is_out_of_order:
            self.logger.warning(
                f"Out-of-order tick for {row.symbol}: "
                f"recv_index={row.recv_index}, "
                f"timestamp={row.timestamp}, "
                f"watermark={previous_watermark}"
            )

        timestamp_bucket = self._bucket_range(row.timestamp, interval_state.interval_ms)
        if state.should_drop_late_tick(timestamp_bucket):
            self.logger.warning(
                f"Drop late tick for flushed bucket: "
                f"symbol={row.symbol}, "
                f"recv_index={row.recv_index}, "
                f"timestamp={row.timestamp}, "
                f"interval={interval_state.interval}"
            )
            return

        state.upsert_bar(
            row=row, interval=interval_state.interval, timestamp_bucket=timestamp_bucket
        )

        for bar in state.flush_ready_bars(self.max_lateness_ms):
            yield interval_state.interval, bar
