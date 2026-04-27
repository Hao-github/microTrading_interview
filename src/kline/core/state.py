from dataclasses import dataclass, field
import heapq
from typing import Any

from kline.core.models import KlineBar, TickRecord


@dataclass(slots=True)
class SymbolAggregationState:
    active_bars: dict[int, KlineBar] = field(default_factory=dict)
    active_bar_starts: list[int] = field(default_factory=list)
    watermark: int = 0
    flushed_until: int = -1

    def update_watermark(self, timestamp: int) -> tuple[int, bool]:
        """Advance the symbol watermark with a new tick timestamp.

        Args:
            timestamp: Tick timestamp in milliseconds.

        Returns:
            A tuple of ``(previous_watermark, is_out_of_order)``.
        """
        previous_watermark = self.watermark
        self.watermark = max(previous_watermark, timestamp)
        return previous_watermark, timestamp < previous_watermark

    def should_drop_late_tick(self, timestamp_bucket: tuple[int, int]) -> bool:
        """Check whether a tick belongs to an already flushed bucket.

        Args:
            timestamp_bucket: Bucket range as ``(start_timestamp, end_timestamp)``.

        Returns:
            ``True`` if the bucket has already been flushed; otherwise ``False``.
        """
        return timestamp_bucket[1] <= self.flushed_until

    def upsert_bar(
        self,
        row: TickRecord,
        interval: str,
        timestamp_bucket: tuple[int, int],
    ) -> None:
        """Create or update the active bar for the tick's time bucket.

        Args:
            row: Tick record to merge.
            interval: Interval label such as ``"1m"``.
            timestamp_bucket: Bucket range as ``(start_timestamp, end_timestamp)``.

        Returns:
            ``None``.
        """
        bucket_start = timestamp_bucket[0]
        if (bar := self.active_bars.get(bucket_start)) is None:
            self.active_bars[bucket_start] = KlineBar.from_tick(
                row=row, interval=interval, timestamp_bucket=timestamp_bucket
            )
            heapq.heappush(self.active_bar_starts, bucket_start)
            return

        bar.update_from_tick(row)

    def flush_ready_bars(self, max_lateness_ms: int) -> list[KlineBar]:
        """Flush bars that are older than the allowed lateness window.

        Args:
            max_lateness_ms: Maximum tolerated out-of-order delay in milliseconds.

        Returns:
            A list of bars that are ready to be emitted.
        """
        flush_before = self.watermark - max_lateness_ms
        flushed_bars: list[KlineBar] = []
        while self.active_bar_starts:
            start = self.active_bar_starts[0]
            if (bar_to_flush := self.active_bars.get(start)) is None:
                heapq.heappop(self.active_bar_starts)
                continue

            if bar_to_flush.bucket_end_timestamp > flush_before:
                break

            heapq.heappop(self.active_bar_starts)
            self.active_bars.pop(start)
            self.flushed_until = max(
                self.flushed_until, bar_to_flush.bucket_end_timestamp
            )
            flushed_bars.append(bar_to_flush)
        return flushed_bars

    def flush_remaining_bars(self) -> list[KlineBar]:
        """Return all remaining active bars without mutating ordering metadata.

        Args:
            None.

        Returns:
            Remaining active bars sorted by bucket start time.
        """
        return [self.active_bars[start] for start in sorted(self.active_bars)]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the symbol state into a checkpoint-friendly dictionary.

        Args:
            None.

        Returns:
            A dictionary containing active bars and watermark metadata.
        """
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
        """Rebuild a symbol aggregation state from serialized payload data.

        Args:
            payload: Serialized symbol state dictionary.

        Returns:
            A restored ``SymbolAggregationState`` instance.
        """
        active_bars = {
            int(bar_payload["bucket_start_timestamp"]): KlineBar.from_dict(bar_payload)
            for bar_payload in payload.get("active_bars", [])
        }
        return cls(
            active_bars=active_bars,
            active_bar_starts=sorted(active_bars),
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
        """Create interval state from an interval label.

        Args:
            interval: Interval string such as ``"1m"``.

        Returns:
            An ``IntervalAggregationState`` with parsed interval length.
        """
        if interval.endswith("m") and (minutes := int(interval[:-1])) > 0:
            return cls(interval=interval, interval_ms=minutes * 60 * 1000)
        raise ValueError(f"unsupported interval: {interval}")

    def flush_remaining_bars(self) -> list[KlineBar]:
        """Collect all remaining bars across all symbols in this interval.

        Args:
            None.

        Returns:
            A list of unflushed bars for the interval.
        """
        return [
            bar
            for symbol_state in self.symbol_states.values()
            for bar in symbol_state.flush_remaining_bars()
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the interval state for checkpoint persistence.

        Args:
            None.

        Returns:
            A dictionary containing interval metadata and symbol states.
        """
        return {
            "interval": self.interval,
            "interval_ms": self.interval_ms,
            "symbol_states": {
                symbol: state.to_dict() for symbol, state in self.symbol_states.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IntervalAggregationState":
        """Restore interval state from serialized payload data.

        Args:
            payload: Serialized interval state dictionary.

        Returns:
            A restored ``IntervalAggregationState`` instance.
        """
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

    def create(self, interval: str):
        """Ensure that aggregation state exists for the given interval.

        Args:
            interval: Interval string such as ``"1m"``.

        Returns:
            ``None``.
        """
        if interval not in self.by_interval:
            self.by_interval[interval] = IntervalAggregationState.from_interval(
                interval
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize all interval states into a plain dictionary.

        Args:
            None.

        Returns:
            A mapping from interval string to serialized interval state.
        """
        return {
            interval: state.to_dict() for interval, state in self.by_interval.items()
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "IntervalStates":
        """Restore interval states from serialized checkpoint data.

        Args:
            payload: Serialized interval-state mapping, or ``None``.

        Returns:
            A restored ``IntervalStates`` instance.
        """
        if payload is None:
            return cls()

        return cls(
            by_interval={
                interval: IntervalAggregationState.from_dict(state_payload)
                for interval, state_payload in payload.items()
            }
        )
