from kline import CSVReader


def test_csv_reader_reads_expected_rows_from_csv(tmp_path) -> None:
    sample_file = tmp_path / "sample_ticks.csv"
    sample_file.write_text(
        "\n".join(
            [
                "szWindCode,nTradingDay,nTime,nMatch,iVolume,iTurnover,recv_index",
                "000001.SZ,20221110,93000000,10.5,100,1050,1",
                "000002.SZ,20221110,93001000,20.0,200,4000,2",
            ]
        ),
        encoding="utf-8",
    )

    reader = CSVReader()
    rows = list(reader.read(sample_file))

    assert len(rows) == 2
    assert rows[0].symbol == "000001.SZ"
    assert rows[0].trading_day == "20221110"
    assert rows[0].timestamp == 1668043800000
    assert rows[0].price == 10.5
    assert rows[0].volume == 100
    assert rows[0].turnover == 1050
    assert rows[0].recv_index == 1

    assert rows[1].symbol == "000002.SZ"
    assert rows[1].timestamp == 1668043801000
