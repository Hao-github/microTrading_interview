import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import TickRecord


class CSVReader:
    def read(self, file_path: str | Path) -> Iterator[TickRecord]:
        """Yield tick records from a CSV file."""
        file_path = Path(file_path)

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
                raise ValueError(
                    f"missing required csv columns: {', '.join(missing_columns)}"
                )

            symbol_idx = index_map["szWindCode"]
            trading_day_idx = index_map["nTradingDay"]
            time_value_idx = index_map["nTime"]
            price_idx = index_map["nMatch"]
            volume_idx = index_map["iVolume"]
            turnover_idx = index_map["iTurnover"]
            recv_index_idx = index_map["recv_index"]
            for row in reader:
                print(row[price_idx])
                yield TickRecord(
                    symbol=row[symbol_idx].strip(),
                    trading_day=row[trading_day_idx].strip(),
                    timestamp=self._to_timestamp(
                        row[trading_day_idx].strip(),
                        row[time_value_idx].strip(),
                    ),
                    price=self._to_float(row[price_idx].strip()),
                    volume=self._to_int(row[volume_idx].strip()),
                    turnover=self._to_int(row[turnover_idx].strip()),
                    recv_index=self._to_int(row[recv_index_idx].strip())
                    
                )

    def _to_float(self, value: str) -> float:
        """Convert a string to float."""
        return float(value) if value else 0.0

    def _to_int(self, value: str) -> int:
        """Convert a string to float."""
        return int(value) if value else 0

    def _to_timestamp(self, trading_day: str, time_value: str) -> int:
        """Convert trading day and HHMMSSmmm time into a millisecond timestamp."""
        trading_day = trading_day.strip()
        time_value = time_value.strip().zfill(9)
        dt = datetime.strptime(f"{trading_day}{time_value}", "%Y%m%d%H%M%S%f")
        return int(dt.timestamp() * 1000)
