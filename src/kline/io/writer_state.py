import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from kline.core.models import KlineBar


@dataclass(slots=True)
class IntervalSegmentState:
    output_path: Path
    csv_file: IO[str]
    writer: Any
    row_count: int = 0

    @classmethod
    def from_output_path(cls, output_path: Path) -> "IntervalSegmentState":
        csv_file = output_path.open("w", encoding="utf-8", newline="")
        writer = csv.writer(csv_file)
        writer.writerow(KlineBar.csv_fieldnames())
        return cls(output_path=output_path, csv_file=csv_file, writer=writer)

    def close(self) -> None:
        self.csv_file.close()

    def write_bar(self, row: KlineBar) -> None:
        self.writer.writerow(row.to_csv_values())
        self.row_count += 1

    def commit_to(self, committed_path: Path) -> Path:
        self.close()
        self.output_path.replace(committed_path)
        return committed_path

    def discard(self) -> None:
        self.close()
        if self.output_path.exists():
            self.output_path.unlink()


@dataclass(slots=True)
class SegmentStates:
    by_interval: dict[str, IntervalSegmentState] = field(default_factory=dict)

    def __contains__(self, interval: str) -> bool:
        return interval in self.by_interval

    def __getitem__(self, interval: str) -> IntervalSegmentState:
        return self.by_interval[interval]

    def __setitem__(self, interval: str, state: IntervalSegmentState) -> None:
        self.by_interval[interval] = state

    def get_or_create(
        self,
        interval: str,
        output_path: Path,
    ) -> tuple[IntervalSegmentState, bool]:
        if interval in self.by_interval:
            return self.by_interval[interval], False

        state = IntervalSegmentState.from_output_path(output_path)
        self.by_interval[interval] = state
        return state, True

    def values(self):
        return self.by_interval.values()

    def items(self):
        return self.by_interval.items()

    def clear(self) -> None:
        self.by_interval.clear()

    def has_open_segments(self) -> bool:
        return bool(self.by_interval)
