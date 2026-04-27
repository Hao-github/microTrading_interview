import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from kline.core.models import TaskConfig, TickRecord
from kline.runtime.logger import get_logger


@dataclass(frozen=True, slots=True)
class CSVColumnIndexes:
    COLUMN_NAMES = {
        "symbol": "szWindCode",
        "trading_day": "nTradingDay",
        "time_value": "nTime",
        "price": "nMatch",
        "volume": "iVolume",
        "turnover": "iTurnover",
        "recv_index": "recv_index",
    }

    symbol: int
    trading_day: int
    time_value: int
    price: int
    volume: int
    turnover: int
    recv_index: int


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
        """Close the currently active row generator if one exists.

        Args:
            None.

        Returns:
            ``None``.
        """
        if self._active_rows is None:
            return

        self._active_rows.close()
        self._active_rows = None

    def _get_column_indexes(
        self, header: list[str], file_path: Path
    ) -> CSVColumnIndexes:
        """Resolve required CSV column positions from the header row.

        Args:
            header: CSV header row.
            file_path: Source CSV path used for error reporting.

        Returns:
            A ``CSVColumnIndexes`` instance with resolved positions.
        """
        index_map = {name: idx for idx, name in enumerate(header)}
        required_columns = list(CSVColumnIndexes.COLUMN_NAMES.values())
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
                for field_name, csv_column in CSVColumnIndexes.COLUMN_NAMES.items()
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
        """Parse one CSV row into a tick record.

        Args:
            row: Raw CSV row values.
            row_number: One-based line number in the source file.
            file_path: Source CSV path used for logging.
            column_indexes: Resolved index mapping for required columns.
            start_offset: Optional minimum ``recv_index`` to include.

        Returns:
            A ``TickRecord`` when parsing succeeds and passes the offset filter;
            otherwise ``None``.
        """
        try:
            symbol = row[column_indexes.symbol].strip()
            trading_day = row[column_indexes.trading_day].strip()
            time_value = row[column_indexes.time_value].strip()
            price = row[column_indexes.price].strip()
            volume = row[column_indexes.volume].strip()
            turnover = row[column_indexes.turnover].strip()
            recv_index = int(row[column_indexes.recv_index].strip() or 0)

            if start_offset is not None and recv_index < start_offset:
                return None

            return TickRecord.from_csv_fields(
                symbol=symbol,
                trading_day=trading_day,
                time_value=time_value,
                price=price,
                volume=volume,
                turnover=turnover,
                recv_index=recv_index,
            )
        except (IndexError, ValueError) as exc:
            self.logger.warning(f"skip invalid row {row_number} in {file_path}: {exc}")
            return None

    def read(
        self, file_path: str | Path, start_offset: int | None = None
    ) -> CSVTickStream:
        """Open a CSV file and stream parsed tick records.

        Args:
            file_path: CSV file path to read.
            start_offset: Optional minimum ``recv_index`` to include.

        Returns:
            A ``CSVTickStream`` context manager / iterable of ``TickRecord`` objects.
        """
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
