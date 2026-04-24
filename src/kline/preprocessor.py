from typing import Iterable

from .models import TickRecord


class TickPreprocessor:
    def clean_columns(self, rows: Iterable[TickRecord]) -> Iterable[TickRecord]:
        pass

    def parse_timestamp(self, rows: Iterable[TickRecord]) -> Iterable[TickRecord]:
        pass

    def process(self, rows: Iterable[TickRecord]) -> Iterable[TickRecord]:
        pass
