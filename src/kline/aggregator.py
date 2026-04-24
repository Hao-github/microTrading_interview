from typing import Iterable

from .models import KlineBar, TickRecord


class KlineAggregator:
    def aggregate(self, rows: Iterable[TickRecord], interval: str) -> Iterable[KlineBar]:
        pass

    def aggregate_many(self, rows: Iterable[TickRecord], intervals: list[str]) -> dict[str, Iterable[KlineBar]]:
        pass
