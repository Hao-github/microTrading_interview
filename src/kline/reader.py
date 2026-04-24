import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import TickRecord


class CSVReader:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("kline.reader")

    def read(self, file_path: str | Path) -> Iterator[TickRecord]:
        """Yield tick records from a CSV file."""
        file_path = Path(file_path)
        self.logger.info("start reading csv file: %s", file_path)
        row_count = 0

        with file_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.reader(csv_file)
            header = next(reader, [])
            index_map = {name: idx for idx, name in enumerate(header)}
            required_columns = [
                "szWindCode",
                "nTradingDay",
                "nTime",
                "nMatch",
                "iVolume",
                "iTurnover",
                "recv_index",
            ]
            missing_columns = [
                column for column in required_columns if column not in index_map
            ]

            if missing_columns:
                warning_str = f"missing required csv columns in {file_path}: {','.join(missing_columns)}"
                self.logger.error(warning_str)
                raise ValueError(warning_str)

            symbol_idx = index_map["szWindCode"]
            trading_day_idx = index_map["nTradingDay"]
            time_value_idx = index_map["nTime"]
            price_idx = index_map["nMatch"]
            volume_idx = index_map["iVolume"]
            turnover_idx = index_map["iTurnover"]
            recv_index_idx = index_map["recv_index"]
            for row_number, row in enumerate(reader, start=2):
                try:
                    record = TickRecord(
                        symbol=row[symbol_idx].strip(),
                        trading_day=row[trading_day_idx].strip(),
                        timestamp=self._to_timestamp(
                            row[trading_day_idx].strip(),
                            row[time_value_idx].strip(),
                        ),
                        price=self._to_float(row[price_idx].strip()),
                        volume=self._to_int(row[volume_idx].strip()),
                        turnover=self._to_int(row[turnover_idx].strip()),
                        recv_index=self._to_int(row[recv_index_idx].strip()),
                    )
                except (IndexError, ValueError) as exc:
                    self.logger.warning(
                        f"skip invalid row {row_number} in {file_path}: {exc}"
                    )
                    continue

                row_count += 1
                yield record

        self.logger.info(
            f"finished reading csv file: {file_path}, valid rows={row_count}"
        )

    def _to_float(self, value: str) -> float:
        """Convert a string to float."""
        return float(value) if value else 0.0

    def _to_int(self, value: str) -> int:
        """Convert a string to float."""
        return int(value) if value else 0

    def _to_timestamp(self, trading_day: str, time_value: str) -> int:
        """Convert trading day and HHMMSSmmm time into a millisecond timestamp."""
        time_value = time_value.zfill(9)
        dt = datetime.strptime(f"{trading_day}{time_value}", "%Y%m%d%H%M%S%f")
        return int(dt.timestamp() * 1000)
