import csv
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Generator

from kline.core.models import TaskConfig, TickRecord
from kline.runtime.logger import get_logger


@dataclass(frozen=True, slots=True)
class CSVColumnIndexes:
    symbol: int = field(metadata={"csv_column": "szWindCode"})
    trading_day: int = field(metadata={"csv_column": "nTradingDay"})
    time_value: int = field(metadata={"csv_column": "nTime"})
    price: int = field(metadata={"csv_column": "nMatch"})
    volume: int = field(metadata={"csv_column": "iVolume"})
    turnover: int = field(metadata={"csv_column": "iTurnover"})
    recv_index: int = field(metadata={"csv_column": "recv_index"})

    @classmethod
    def csv_columns(cls) -> dict[str, str]:
        return {
            dataclass_field.name: dataclass_field.metadata["csv_column"]
            for dataclass_field in fields(cls)
        }


class CSVTickStream:
    def __init__(
        self,
        reader: "CSVReader",
        rows: Generator[TickRecord, None, None],
    ) -> None:
        self._reader = reader
        self._rows = rows

    def __enter__(self) -> Generator[TickRecord, None, None]:
        return self._rows

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __iter__(self) -> Generator[TickRecord, None, None]:
        return self._rows

    def close(self) -> None:
        self._reader.close()


class CSVReader:
    def __init__(self, config: TaskConfig) -> None:
        self.logger = get_logger("kline.reader", config.log_dir)
        self._active_rows: Generator[TickRecord, None, None] | None = None

    def close(self) -> None:
        if self._active_rows is None:
            return

        self._active_rows.close()
        self._active_rows = None

    def _get_column_indexes(
        self, header: list[str], file_path: Path
    ) -> CSVColumnIndexes:
        index_map = {name: idx for idx, name in enumerate(header)}
        csv_columns = CSVColumnIndexes.csv_columns()
        required_columns = list(csv_columns.values())
        missing_columns = [
            column for column in required_columns if column not in index_map
        ]
        if missing_columns:
            warning_str = (
                f"missing required csv columns in {file_path}: "
                f"{','.join(missing_columns)}"
            )
            self.logger.error(warning_str)
            raise ValueError(warning_str)

        return CSVColumnIndexes(
            **{
                field_name: index_map[csv_column]
                for field_name, csv_column in csv_columns.items()
            }
        )

    def _parse_row(
        self,
        row: list[str],
        row_number: int,
        file_path: Path,
        column_indexes: CSVColumnIndexes,
        start_offset: int | None,
    ) -> TickRecord | None:
        try:
            raw_fields = {
                dataclass_field.name: row[
                    getattr(column_indexes, dataclass_field.name)
                ].strip()
                for dataclass_field in fields(CSVColumnIndexes)
            }
            recv_index = int(raw_fields["recv_index"] or 0)
            if start_offset is not None and recv_index < start_offset:
                return None

            raw_fields["recv_index"] = recv_index
            return TickRecord.from_csv_fields(**raw_fields)
        except (IndexError, ValueError) as exc:
            self.logger.warning(f"skip invalid row {row_number} in {file_path}: {exc}")
            return None

    def read(
        self, file_path: str | Path, start_offset: int | None = None
    ) -> CSVTickStream:
        """Yield tick records from a CSV file."""
        self.close()
        file_path = Path(file_path)

        def _iter_rows() -> Generator[TickRecord, None, None]:
            self.logger.info("start reading csv file: %s", file_path)
            row_count = 0

            try:
                with file_path.open("r", encoding="utf-8", newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    column_indexes = self._get_column_indexes(
                        next(reader, []), file_path
                    )

                    for row_number, row in enumerate(reader, start=2):
                        record = self._parse_row(
                            row=row,
                            row_number=row_number,
                            file_path=file_path,
                            column_indexes=column_indexes,
                            start_offset=start_offset,
                        )
                        if record is None:
                            continue

                        row_count += 1
                        yield record
            finally:
                self.logger.info(
                    f"finished reading csv file: {file_path}, valid rows={row_count}"
                )
                if self._active_rows is rows:
                    self._active_rows = None

        rows = _iter_rows()
        self._active_rows = rows
        return CSVTickStream(self, rows)
