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
        self.intervals = config.intervals
        self.max_lateness_ms = max_lateness_ms
        self.interval_states = initial_states or IntervalStates()
        self.interval_states.create_from_intervals(self.intervals)
        self._symbol_watermarks = self._build_symbol_watermarks(self.interval_states)
        self.logger = get_logger("kline.aggregator", config.log_dir)

    def aggregate(
        self, rows: Iterable[TickRecord], finalize: bool = True
    ) -> Iterator[tuple[str, KlineBar]]:
        """Aggregate tick rows into K-line bars for one or more intervals.

        Args:
            rows: Tick record iterable to be consumed in input order.
            finalize: Whether to flush all remaining bars after input is exhausted.

        Yields:
            Tuples of ``(interval, bar)`` for each completed or finalized K-line bar.
        """

        intervals = self.intervals
        for row in rows:
            self._log_out_of_order_tick_once(row)
            for interval in intervals:
                yield from self._process_row_for_interval(
                    row=row, interval_state=self.interval_states[interval]
                )

        if finalize:
            for interval in self.intervals:
                interval_state = self.interval_states[interval]
                for bar in interval_state.flush_remaining_bars():
                    yield interval_state.interval, bar

    def _process_row_for_interval(
        self,
        row: TickRecord,
        interval_state: IntervalAggregationState,
    ) -> Iterator[tuple[str, KlineBar]]:
        """Process one tick for a specific interval state.

        Args:
            row: Tick record to merge into the target interval.
            interval_state: Aggregation state for the current interval.

        Yields:
            Tuples of ``(interval, bar)`` for bars that become flushable after this tick.
        """
        symbol = row.symbol
        timestamp = row.timestamp
        recv_index = row.recv_index
        interval = interval_state.interval
        interval_ms = interval_state.interval_ms
        symbol_states = interval_state.symbol_states

        if (state := symbol_states.get(symbol)) is None:
            state = SymbolAggregationState(watermark=timestamp)
            symbol_states[symbol] = state

        state.update_watermark(timestamp)

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

    def _log_out_of_order_tick_once(self, row: TickRecord) -> None:
        """Log out-of-order ticks once per input row instead of once per interval.

        Args:
            row: Tick record currently being aggregated.

        Returns:
            ``None``.
        """
        symbol = row.symbol
        timestamp = row.timestamp
        recv_index = row.recv_index
        previous_watermark = self._symbol_watermarks.get(symbol, timestamp)

        if timestamp < previous_watermark:
            self.logger.warning(
                f"Out-of-order tick for {symbol}: "
                f"recv_index={recv_index}, "
                f"timestamp={timestamp}, "
                f"watermark={previous_watermark}"
            )

        self._symbol_watermarks[symbol] = max(previous_watermark, timestamp)

    @staticmethod
    def _build_symbol_watermarks(interval_states: IntervalStates) -> dict[str, int]:
        """Extract the latest known watermark per symbol from interval states.

        Args:
            interval_states: Existing interval aggregation states.

        Returns:
            A mapping from symbol to its latest known watermark.
        """
        symbol_watermarks: dict[str, int] = {}
        for interval_state in interval_states.values():
            for symbol, state in interval_state.symbol_states.items():
                current_watermark = symbol_watermarks.get(symbol, state.watermark)
                symbol_watermarks[symbol] = max(current_watermark, state.watermark)
        return symbol_watermarks
