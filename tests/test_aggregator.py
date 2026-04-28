from kline import CSVReader, ConfigLoader, KlineAggregator, KlineBar
from kline.core.state import IntervalAggregationState, SymbolAggregationState

from tests.conftest import SAMPLE_CSV_PATH, TEST_CONFIG_PATH


def _aggregate_1m_bars() -> dict[tuple[str, int], KlineBar]:
    config = ConfigLoader().load(TEST_CONFIG_PATH)
    reader = CSVReader(config)
    aggregator = KlineAggregator(max_lateness_ms=30_000, config=config)
    rows = reader.read(SAMPLE_CSV_PATH)
    bars = aggregator.aggregate(rows)
    return {(bar.symbol, bar.bucket_start_timestamp): bar for _, bar in bars}


def test_aggregator_builds_expected_bars_from_sample_csv() -> None:
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


def test_aggregator_finalize_only_emits_configured_intervals() -> None:
    config = ConfigLoader().load(TEST_CONFIG_PATH)
    aggregator = KlineAggregator(config=config)
    aggregator.interval_states.create_from_intervals(["5m"])

    rows = CSVReader(config).read(SAMPLE_CSV_PATH)
    bars = list(aggregator.aggregate(rows))

    assert bars
    assert {interval for interval, _ in bars} == {"1m"}


def test_interval_flush_remaining_bars_returns_globally_sorted_bars() -> None:
    interval_state = IntervalAggregationState.from_interval("1m")

    later_tick = next(
        iter(CSVReader(ConfigLoader().load(TEST_CONFIG_PATH)).read(SAMPLE_CSV_PATH))
    )
    earlier_tick = later_tick.__class__(
        symbol="000002.SZ",
        trading_day="20221110",
        timestamp=1668043740000,
        price=9.0,
        volume=10,
        turnover=90,
        recv_index=1,
    )

    later_state = SymbolAggregationState()
    later_state.upsert_bar(
        row=later_tick,
        interval="1m",
        timestamp_bucket=(1668043800000, 1668043860000),
    )
    earlier_state = SymbolAggregationState()
    earlier_state.upsert_bar(
        row=earlier_tick,
        interval="1m",
        timestamp_bucket=(1668043740000, 1668043800000),
    )

    interval_state.symbol_states["000001.SZ"] = later_state
    interval_state.symbol_states["000002.SZ"] = earlier_state

    bars = interval_state.flush_remaining_bars()

    assert [bar.symbol for bar in bars] == ["000002.SZ", "000001.SZ"]
    assert [bar.bucket_start_timestamp for bar in bars] == [
        1668043740000,
        1668043800000,
    ]
