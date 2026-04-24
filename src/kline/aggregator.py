import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from .models import KlineBar, TickRecord


@dataclass
class SymbolAggregationState:
    active_bars: dict[int, KlineBar] = field(default_factory=dict)
    watermark: int = 0
    flushed_until: int = -1


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
        interval_ms_map = {
            interval: self._interval_to_milliseconds(interval) for interval in intervals
        }
        interval_states = {
            interval: {} for interval in intervals
        }
        aggregated_bars: dict[str, list[KlineBar]] = {
            interval: [] for interval in intervals
        }

        for row in rows:
            for interval in intervals:
                bars = self._process_row_for_interval(
                    row=row,
                    interval=interval,
                    interval_ms=interval_ms_map[interval],
                    symbol_states=interval_states[interval],
                )
                aggregated_bars[interval].extend(bars)

        for interval in intervals:
            aggregated_bars[interval].extend(
                self._flush_remaining_bars(interval_states[interval])
            )

        return aggregated_bars

    def _interval_to_milliseconds(self, interval: str) -> int:
        if interval.endswith("m"):
            minutes = int(interval[:-1])
            if minutes > 0:
                return minutes * 60 * 1000
        raise ValueError(f"unsupported interval: {interval}")

    def _bucket_start(self, timestamp: int, interval_ms: int) -> int:
        return timestamp - (timestamp % interval_ms)

    def _process_row_for_interval(
        self,
        row: TickRecord,
        interval: str,
        interval_ms: int,
        symbol_states: dict[str, SymbolAggregationState],
    ) -> list[KlineBar]:
        symbol = row.symbol
        state = symbol_states.get(symbol)
        if state is None:
            state = SymbolAggregationState(watermark=row.timestamp)
            symbol_states[symbol] = state

        previous_watermark = state.watermark

        if row.timestamp < previous_watermark:
            self.logger.warning(
                f"Out-of-order tick for {symbol}: "
                f"recv_index={row.recv_index}, "
                f"timestamp={row.timestamp}, "
                f"watermark={previous_watermark}"
            )

        watermark = max(previous_watermark, row.timestamp)
        state.watermark = watermark

        bucket_start = self._bucket_start(row.timestamp, interval_ms)
        bucket_end = bucket_start + interval_ms
        if bucket_end <= state.flushed_until:
            self.logger.warning(
                f"Drop late tick for flushed bucket: "
                f"symbol={symbol}, "
                f"recv_index={row.recv_index}, "
                f"timestamp={row.timestamp}, "
                f"interval={interval}"
            )
            return []

        bar = state.active_bars.get(bucket_start)
        if bar is None:
            state.active_bars[bucket_start] = self._new_bar(
                row=row,
                interval=interval,
                bucket_start=bucket_start,
                bucket_end=bucket_end,
            )
        else:
            self._update_bar(bar, row)

        flush_before = watermark - self.max_lateness_ms
        flushable_starts = [
            start for start in state.active_bars if start + interval_ms <= flush_before
        ]

        flushed_bars: list[KlineBar] = []
        for start in sorted(flushable_starts):
            bar_to_flush = state.active_bars.pop(start)
            state.flushed_until = max(state.flushed_until, start + interval_ms)
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

    def _new_bar(
        self,
        row: TickRecord,
        interval: str,
        bucket_start: int,
        bucket_end: int,
    ) -> KlineBar:
        return KlineBar(
            symbol=row.symbol,
            interval=interval,
            trading_day=row.trading_day,
            open_price=row.price,
            high_price=row.price,
            low_price=row.price,
            close_price=row.price,
            volume=float(row.volume),
            amount=float(row.turnover),
            start_time=self._format_timestamp(bucket_start),
            end_time=self._format_timestamp(bucket_end),
        )

    def _update_bar(self, bar: KlineBar, row: TickRecord) -> None:
        bar.high_price = max(bar.high_price, row.price)
        bar.low_price = min(bar.low_price, row.price)
        bar.close_price = row.price
        bar.volume += float(row.volume)
        bar.amount += float(row.turnover)

    def _format_timestamp(self, timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp / 1000).strftime("%H:%M:%S")
