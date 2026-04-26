from typing import Iterable, Iterator

from kline.core import (
    IntervalAggregationState,
    IntervalStates,
    KlineBar,
    SymbolAggregationState,
    TaskConfig,
    TickRecord,
)
from kline.runtime.logger import get_logger


class KlineAggregator:
    def __init__(
        self,
        config: TaskConfig,
        max_lateness_ms: int = 30_000,
        initial_states: IntervalStates | None = None,
    ) -> None:
        self.config = config
        self.max_lateness_ms = max_lateness_ms
        self.interval_states = initial_states or IntervalStates()
        self.logger = get_logger("kline.aggregator", config.log_dir)

    def aggregate(
        self,
        rows: Iterable[TickRecord],
        intervals: str | list[str],
        finalize: bool = True,
    ) -> Iterator[tuple[str, KlineBar]]:
        if isinstance(intervals, str):
            intervals = [intervals]

        for interval in intervals:
            self.interval_states.get_or_create(interval)

        for row in rows:
            for interval in intervals:
                yield from self._process_row_for_interval(
                    row=row, interval_state=self.interval_states[interval]
                )

        if finalize:
            for interval_state in self.interval_states.values():
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
