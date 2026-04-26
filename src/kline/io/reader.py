import csv
from pathlib import Path
from typing import Iterator

from kline.core import TaskConfig, TickRecord
from kline.runtime.logger import get_logger


class CSVReader:
    def __init__(self, config: TaskConfig) -> None:
        self.logger = get_logger("kline.reader", config.log_dir)

    def read(
        self, file_path: str | Path, start_offset: int | None = None
    ) -> Iterator[TickRecord]:
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
                    recv_index = int(row[recv_index_idx].strip() or 0)
                    if start_offset is not None and recv_index < start_offset:
                        continue

                    record = TickRecord.from_csv_fields(
                        symbol=row[symbol_idx].strip(),
                        trading_day=row[trading_day_idx].strip(),
                        time_value=row[time_value_idx].strip(),
                        price=row[price_idx].strip(),
                        volume=row[volume_idx].strip(),
                        turnover=row[turnover_idx].strip(),
                        recv_index=recv_index,
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
