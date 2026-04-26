from itertools import islice

from kline import CSVReader


def test_csv_reader_reads_millionth_row_from_large_csv() -> None:
    reader = CSVReader()
    millionth_row = next(
        islice(
            reader.read("data/sample_input/md_20221110_head_1000000.csv"), 999999, None
        )
    )

    assert millionth_row.symbol == "000581.SZ"
    assert millionth_row.trading_day == "20221110"
    assert millionth_row.timestamp == 1668044103000
    assert millionth_row.price == 176300.0
    assert millionth_row.volume == 198600
    assert millionth_row.turnover == 3506263
    assert millionth_row.recv_index == 999999
