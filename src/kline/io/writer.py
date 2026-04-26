import csv
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator

from kline.core.models import KlineBar, TaskConfig
from kline.runtime.logger import get_logger


@dataclass(slots=True)
class IntervalWriterState:
    output_path: Path
    csv_file: IO[str]
    writer: csv.DictWriter
    row_count: int = 0

    @classmethod
    def for_interval(
        cls,
        interval: str,
        output_dir: Path,
        original_file_name: str,
    ) -> "IntervalWriterState":
        output_path = output_dir / f"kline_{interval}_for_{original_file_name}.csv"
        csv_file = output_path.open("w", encoding="utf-8", newline="")
        writer = csv.DictWriter(csv_file, fieldnames=KlineBar.csv_fieldnames())
        writer.writeheader()
        return cls(output_path=output_path, csv_file=csv_file, writer=writer)

    def close(self) -> None:
        self.csv_file.close()

    def write_row(self, row: KlineBar) -> None:
        self.writer.writerow(row.to_csv_row())
        self.row_count += 1


class KlineWriter:
    def __init__(self, config: TaskConfig) -> None:
        self.config = config
        self.logger = get_logger("kline.writer", config.log_dir)
        self.output_dir = Path(self.config.output_dir)
        self.original_file_name = Path(self.config.input_file_path).stem

    def _validate_output_format(self) -> None:
        output_format = self.config.output_format
        if output_format != "csv":
            if output_format == "parquet":
                raise NotImplementedError("parquet output is not implemented yet")
            raise ValueError(f"unsupported output format: {output_format}")

    def _build_batch_output_path(
        self,
        interval: str,
        batch_end_offset: int,
        segment_kind: str,
    ) -> Path:
        return self.output_dir / (
            f"kline_{interval}_for_{self.original_file_name}"
            f"_offset_{batch_end_offset:020d}_{segment_kind}.csv"
        )

    def write_batch(
        self,
        rows: list[tuple[str, KlineBar]],
        batch_end_offset: int,
        segment_kind: str = "batch",
    ) -> list[Path]:
        self._validate_output_format()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        rows_by_interval: dict[str, list[KlineBar]] = {}
        for interval, row in rows:
            rows_by_interval.setdefault(interval, []).append(row)

        written_paths: list[Path] = []
        for interval, interval_rows in rows_by_interval.items():
            output_path = self._build_batch_output_path(
                interval, batch_end_offset, segment_kind
            )
            with output_path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=KlineBar.csv_fieldnames())
                writer.writeheader()
                for row in interval_rows:
                    writer.writerow(row.to_csv_row())

            written_paths.append(output_path)
            self.logger.info(
                "finished writing batch csv file for interval %s: %s, rows=%s",
                interval,
                output_path,
                len(interval_rows),
            )

        return written_paths

    def write_stream(self, rows: Iterator[tuple[str, KlineBar]]) -> None:
        self._validate_output_format()

        interval_states: dict[str, IntervalWriterState] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            for interval, row in rows:
                if interval not in interval_states:
                    interval_states[interval] = IntervalWriterState.for_interval(
                        interval=interval,
                        output_dir=self.output_dir,
                        original_file_name=self.original_file_name,
                    )
                    self.logger.info(
                        f"start writing stream csv file for interval {interval}: "
                        f"{interval_states[interval].output_path}"
                    )

                interval_states[interval].write_row(row)
        finally:
            for interval, interval_state in interval_states.items():
                interval_state.close()
                self.logger.info(
                    f"finished writing stream csv file for interval {interval}, rows={interval_state.row_count}"
                )
