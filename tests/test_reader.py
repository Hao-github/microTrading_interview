from kline import CSVReader, ConfigLoader

from tests.conftest import (
    SAMPLE_CSV_PATH,
    TEST_CONFIG_PATH,
    make_temp_dir,
    remove_temp_dir,
)


def test_csv_reader_reads_first_sample_row() -> None:
    config = ConfigLoader().load(TEST_CONFIG_PATH)
    reader = CSVReader(config=config)

    first_row = next(iter(reader.read(SAMPLE_CSV_PATH)))

    assert first_row.symbol == "000001.SZ"
    assert first_row.trading_day == "20221110"
    assert first_row.timestamp == 1668043801000
    assert first_row.price == 10.0
    assert first_row.volume == 100
    assert first_row.turnover == 1000
    assert first_row.recv_index == 0


def test_csv_reader_honors_start_offset() -> None:
    config = ConfigLoader().load(TEST_CONFIG_PATH)
    reader = CSVReader(config=config)

    row = next(iter(reader.read(SAMPLE_CSV_PATH, start_offset=10)))

    assert row.symbol == "601399.SH"
    assert row.recv_index == 10


def test_csv_reader_skips_invalid_rows() -> None:
    temp_dir = make_temp_dir("reader-tests")
    try:
        invalid_csv = temp_dir / "invalid_ticks.csv"
        invalid_csv.write_text(
            "szWindCode,nTradingDay,nTime,nMatch,iVolume,iTurnover,recv_index\n"
            "000001.SZ,20221110,093001000,10,100,1000,0\n"
            "000001.SZ,20221110,bad-time,10,100,1000,1\n"
            "000001.SZ,20221110,093002000,11,50,550,2\n",
            encoding="utf-8",
        )

        config = ConfigLoader().load(TEST_CONFIG_PATH)
        reader = CSVReader(config=config)
        rows = list(reader.read(invalid_csv))

        assert [row.recv_index for row in rows] == [0, 2]
        assert rows[1].price == 11.0
    finally:
        remove_temp_dir(temp_dir)


def test_csv_reader_skips_non_positive_price_rows() -> None:
    temp_dir = make_temp_dir("reader-tests")
    try:
        invalid_csv = temp_dir / "zero_price_ticks.csv"
        invalid_csv.write_text(
            "szWindCode,nTradingDay,nTime,nMatch,iVolume,iTurnover,recv_index\n"
            "000001.SZ,20221110,093001000,10,100,1000,0\n"
            "000001.SZ,20221110,093002000,0,100,0,1\n"
            "000001.SZ,20221110,093003000,-1,100,-100,2\n"
            "000001.SZ,20221110,093004000,11,50,550,3\n",
            encoding="utf-8",
        )

        config = ConfigLoader().load(TEST_CONFIG_PATH)
        reader = CSVReader(config=config)
        rows = list(reader.read(invalid_csv))

        assert [row.recv_index for row in rows] == [0, 3]
        assert [row.price for row in rows] == [10.0, 11.0]
    finally:
        remove_temp_dir(temp_dir)
