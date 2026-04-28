import csv

from kline import ConfigLoader, KlineBar, KlineWriter

from tests.conftest import TEST_CONFIG_PATH, make_temp_dir, remove_temp_dir


def _make_bar() -> KlineBar:
    return KlineBar(
        symbol="000001.SZ",
        interval="1m",
        trading_day="20221110",
        open_price=10.0,
        high_price=11.0,
        low_price=9.5,
        close_price=10.5,
        volume=100.0,
        amount=1050.0,
        bucket_start_timestamp=1668043800000,
        bucket_end_timestamp=1668043860000,
        first_tick_timestamp=1668043801000,
        last_tick_timestamp=1668043859000,
    )


def test_writer_commit_segment_writes_csv_with_header() -> None:
    temp_dir = make_temp_dir("writer-tests")
    try:
        config = ConfigLoader().load(TEST_CONFIG_PATH)
        config.output_dir = temp_dir / "out"
        config.log_dir = temp_dir / "logs"
        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.log_dir.mkdir(parents=True, exist_ok=True)

        writer = KlineWriter(config)
        writer.write_bar("1m", _make_bar())

        written_paths = writer.commit_segment(1, segment_kind="final")

        assert len(written_paths) == 1
        assert written_paths[0].parent.name == "segments"
        with written_paths[0].open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.reader(csv_file))

        assert rows[0] == KlineBar.csv_fieldnames()
        assert rows[1][0] == "000001.SZ"
        assert rows[1][1] == "1m"
    finally:
        remove_temp_dir(temp_dir)


def test_writer_discard_open_segment_removes_tmp_file() -> None:
    temp_dir = make_temp_dir("writer-tests")
    try:
        config = ConfigLoader().load(TEST_CONFIG_PATH)
        config.output_dir = temp_dir / "out"
        config.log_dir = temp_dir / "logs"
        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.log_dir.mkdir(parents=True, exist_ok=True)

        writer = KlineWriter(config)
        writer.write_bar("1m", _make_bar())
        tmp_paths = list((config.output_dir / "segments").glob("*_current.csv.tmp"))
        assert len(tmp_paths) == 1
        tmp_path_written = tmp_paths[0]

        writer.discard_open_segment()

        assert not tmp_path_written.exists()
        assert not writer.has_open_segment()
    finally:
        remove_temp_dir(temp_dir)


def test_writer_build_complete_outputs_merges_segments() -> None:
    temp_dir = make_temp_dir("writer-tests")
    try:
        config = ConfigLoader().load(TEST_CONFIG_PATH)
        config.output_dir = temp_dir / "out"
        config.log_dir = temp_dir / "logs"
        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.log_dir.mkdir(parents=True, exist_ok=True)

        writer = KlineWriter(config)
        writer.write_bar("1m", _make_bar())
        writer.commit_segment(1, segment_kind="batch")

        bar2 = _make_bar()
        bar2.symbol = "000002.SZ"
        writer.write_bar("1m", bar2)
        writer.commit_segment(2, segment_kind="final")

        writer.build_complete_outputs()
        output_path = config.output_dir / "kline_1m_for_sample_ticks_100.csv"
        assert output_path.exists()
        with output_path.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.reader(csv_file))

        assert rows[0] == KlineBar.csv_fieldnames()
        assert rows[1][0] == "000001.SZ"
        assert rows[2][0] == "000002.SZ"
    finally:
        remove_temp_dir(temp_dir)
