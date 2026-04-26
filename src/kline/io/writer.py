import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator

from ..core.models import KlineBar, TaskConfig
from ..runtime.logger import get_logger


@dataclass
class IntervalWriterState:
    output_path: Path
    csv_file: IO[str]
    writer: csv.DictWriter
    row_count: int = 0

    @classmethod
    def for_interval(
        cls,
        *,
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
    def __init__(
        self,
        config: TaskConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or get_logger("kline.writer")

    def write_stream(
        self,
        rows: Iterator[tuple[str, KlineBar]],
    ) -> None:
        output_format = self.config.output_format
        if output_format != "csv":
            if output_format == "parquet":
                raise NotImplementedError(
                    "stream parquet output is not implemented yet"
                )
            raise ValueError(f"unsupported output format: {output_format}")

        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        interval_states: dict[str, IntervalWriterState] = {}
        original_file_name = Path(self.config.input_file_path).stem

        try:
            for interval, row in rows:
                if interval not in interval_states:
                    interval_states[interval] = IntervalWriterState.for_interval(
                        interval=interval,
                        output_dir=output_dir,
                        original_file_name=original_file_name,
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
