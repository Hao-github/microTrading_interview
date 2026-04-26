from kline import CSVReader, KlineAggregator, KlineBar

SAMPLE_CSV_PATH = "tests/sample_ticks_100.csv"


def _aggregate_1m_bars() -> dict[tuple[str, int], KlineBar]:
    reader = CSVReader()
    aggregator = KlineAggregator(max_lateness_ms=30_000)
    rows = reader.read(SAMPLE_CSV_PATH)
    bars = aggregator.aggregate(rows, "1m")
    return {(bar.symbol, bar.bucket_start_timestamp): bar for bar in bars}


def test_aggregator_builds_expected_bars_from_sample_csv() -> None:
    reader = CSVReader()
    aggregator = KlineAggregator(max_lateness_ms=30_000)
    rows = reader.read(SAMPLE_CSV_PATH)
    bars = aggregator.aggregate(rows, "1m")
    bars = _aggregate_1m_bars()

    assert len(bars) == 15

    first_bar = bars[("000001.SZ", 1668043800000)]
    assert first_bar.interval == "1m"
    assert first_bar.trading_day == "20221110"
    assert first_bar.open_price == 10.0
    assert first_bar.high_price == 12.0
    assert first_bar.low_price == 10.0
    assert first_bar.close_price == 11.0
    assert first_bar.volume == 220.0
    assert first_bar.amount == 2370.0
    assert first_bar.bucket_end_timestamp == 1668043860000

    dense_bar = bars[("300001.SZ", 1668043800000)]
    assert dense_bar.open_price == 200.0
    assert dense_bar.high_price == 209.0
    assert dense_bar.low_price == 200.0
    assert dense_bar.close_price == 209.0
    assert dense_bar.volume == 100.0
    assert dense_bar.amount == 20450.0
    assert dense_bar.bucket_end_timestamp == 1668043860000


def test_aggregator_tolerates_small_out_of_order_ticks_within_same_bar() -> None:
    bars = _aggregate_1m_bars()

    bar = bars[("601399.SH", 1668044040000)]
    assert bar.open_price == 102.0
    assert bar.close_price == 104.0
    assert bar.high_price == 104.0
    assert bar.low_price == 102.0
    assert bar.volume == 230.0
    assert bar.amount == 23720.0
