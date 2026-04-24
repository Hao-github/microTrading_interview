from itertools import islice
from pathlib import Path

from kline.reader import CSVReader


def test_csv_reader_reads_millionth_row_from_large_csv(monkeypatch) -> None:
    reader = CSVReader()
    file_path = Path("data/input/md_20221110.csv")

    # Silence the debug print in CSVReader so the test can scan efficiently.
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)

    millionth_row = next(islice(reader.read(file_path), 999999, None))

    assert millionth_row.symbol == "000581.SZ"
    assert millionth_row.trading_day == "20221110"
    assert millionth_row.timestamp == 1668044103000
    assert millionth_row.price == 176300.0
    assert millionth_row.volume == 198600
    assert millionth_row.turnover == 3506263
    assert millionth_row.recv_index == 999999
