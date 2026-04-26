import logging
from dataclasses import dataclass, field
from typing import Iterable

from .models import KlineBar, TickRecord


@dataclass
class SymbolAggregationState:
    active_bars: dict[int, KlineBar] = field(default_factory=dict)
    watermark: int = 0
    flushed_until: int = -1


@dataclass
class IntervalAggregationState:
    interval: str
    interval_ms: int
    symbol_states: dict[str, SymbolAggregationState] = field(default_factory=dict)
    aggregated_bars: list[KlineBar] = field(default_factory=list)

    @classmethod
    def from_interval(cls, interval: str) -> "IntervalAggregationState":
        if interval.endswith("m") and (minutes := int(interval[:-1])) > 0:
            return cls(interval=interval, interval_ms=minutes * 60 * 1000)
        raise ValueError(f"unsupported interval: {interval}")


class KlineAggregator:
    def __init__(
        self,
        max_lateness_ms: int = 30_000,
        logger: logging.Logger | None = None,
    ) -> None:
        self.max_lateness_ms = max_lateness_ms
        self.logger = logger or logging.getLogger("kline.aggregator")

    def aggregate(
        self, rows: Iterable[TickRecord], interval: str
    ) -> Iterable[KlineBar]:
        return self.aggregate_many(rows, [interval])[interval]

    def aggregate_many(
        self, rows: Iterable[TickRecord], intervals: list[str]
    ) -> dict[str, list[KlineBar]]:
        interval_states = {
            interval: IntervalAggregationState.from_interval(interval)
            for interval in intervals
        }

        for row in rows:
            for interval in intervals:
                interval_state = interval_states[interval]
                self._process_row_for_interval(
                    row=row,
                    interval_state=interval_state,
                )

        for interval_state in interval_states.values():
            interval_state.aggregated_bars.extend(
                self._flush_remaining_bars(interval_state.symbol_states)
            )

        return {
            interval: interval_state.aggregated_bars
            for interval, interval_state in interval_states.items()
        }

    def _bucket_range(self, timestamp: int, interval_ms: int) -> tuple[int, int]:
        start = timestamp - (timestamp % interval_ms)
        return start, start + interval_ms

    def _process_row_for_interval(
        self,
        row: TickRecord,
        interval_state: IntervalAggregationState,
    ) -> None:
        if (state := interval_state.symbol_states.get(row.symbol)) is None:
            state = SymbolAggregationState(watermark=row.timestamp)
            interval_state.symbol_states[row.symbol] = state
        self._update_watermark(row, state)

        bucket_start, bucket_end = self._bucket_range(
            row.timestamp, interval_state.interval_ms
        )
        if bucket_end <= state.flushed_until:
            self.logger.warning(
                f"Drop late tick for flushed bucket: "
                f"symbol={row.symbol}, "
                f"recv_index={row.recv_index}, "
                f"timestamp={row.timestamp}, "
                f"interval={interval_state.interval}"
            )
            return

        if (bar := state.active_bars.get(bucket_start)) is None:
            state.active_bars[bucket_start] = KlineBar.from_tick(
                row=row,
                interval=interval_state.interval,
                start_timestamp=bucket_start,
                end_timestamp=bucket_end,
            )
        else:
            bar.update_from_tick(row)

        interval_state.aggregated_bars.extend(self._flush_ready_bars(state))

    def _update_watermark(
        self,
        row: TickRecord,
        state: SymbolAggregationState,
    ) -> None:
        previous_watermark = state.watermark
        if row.timestamp < previous_watermark:
            self.logger.warning(
                f"Out-of-order tick for {row.symbol}: "
                f"recv_index={row.recv_index}, "
                f"timestamp={row.timestamp}, "
                f"watermark={previous_watermark}"
            )
        state.watermark = max(previous_watermark, row.timestamp)

    def _flush_ready_bars(self, state: SymbolAggregationState) -> list[KlineBar]:
        flush_before = state.watermark - self.max_lateness_ms
        flushable_starts = [
            start
            for start, bar in state.active_bars.items()
            if bar.end_timestamp <= flush_before
        ]

        flushed_bars: list[KlineBar] = []
        for start in sorted(flushable_starts):
            bar_to_flush = state.active_bars.pop(start)
            state.flushed_until = max(state.flushed_until, bar_to_flush.end_timestamp)
            flushed_bars.append(bar_to_flush)
        return flushed_bars

    def _flush_remaining_bars(
        self, symbol_states: dict[str, SymbolAggregationState]
    ) -> list[KlineBar]:
        remaining_bars: list[KlineBar] = []
        for symbol in sorted(symbol_states):
            state = symbol_states[symbol]
            for start in sorted(state.active_bars):
                remaining_bars.append(state.active_bars[start])
        return remaining_bars
