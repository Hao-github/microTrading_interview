from typing import Iterable, Iterator

from kline.core.models import KlineBar, TaskConfig, TickRecord
from kline.core.state import (
    IntervalAggregationState,
    IntervalStates,
    SymbolAggregationState,
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
            self.interval_states.create(interval)

        for row in rows:
            for interval in intervals:
                yield from self._process_row_for_interval(
                    row=row, interval_state=self.interval_states[interval]
                )

        if finalize:
            for interval_state in self.interval_states.values():
                for bar in interval_state.flush_remaining_bars():
                    yield interval_state.interval, bar

    def _process_row_for_interval(
        self,
        row: TickRecord,
        interval_state: IntervalAggregationState,
    ) -> Iterator[tuple[str, KlineBar]]:
        symbol = row.symbol
        timestamp = row.timestamp
        recv_index = row.recv_index
        interval = interval_state.interval
        interval_ms = interval_state.interval_ms
        symbol_states = interval_state.symbol_states

        if (state := symbol_states.get(symbol)) is None:
            state = SymbolAggregationState(watermark=timestamp)
            symbol_states[symbol] = state

        previous_watermark, is_out_of_order = state.update_watermark(timestamp)
        if is_out_of_order:
            self.logger.warning(
                f"Out-of-order tick for {symbol}: "
                f"recv_index={recv_index}, "
                f"timestamp={timestamp}, "
                f"watermark={previous_watermark}"
            )

        bucket_start = timestamp - (timestamp % interval_ms)
        timestamp_bucket = (bucket_start, bucket_start + interval_ms)
        if state.should_drop_late_tick(timestamp_bucket):
            self.logger.warning(
                f"Drop late tick for flushed bucket: "
                f"symbol={symbol}, "
                f"recv_index={recv_index}, "
                f"timestamp={timestamp}, "
                f"interval={interval}"
            )
            return

        state.upsert_bar(row=row, interval=interval, timestamp_bucket=timestamp_bucket)

        for bar in state.flush_ready_bars(self.max_lateness_ms):
            yield interval, bar
