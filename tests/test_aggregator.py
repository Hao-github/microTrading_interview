from src.kline.aggregator import KlineAggregator
from src.kline.models import TickRecord


def test_aggregator_builds_1m_bars() -> None:
    aggregator = KlineAggregator(max_lateness_ms=0)
    rows = [
        TickRecord(
            symbol="000001.SZ",
            trading_day="20221110",
            timestamp=1668043801000,
            price=10.0,
            volume=100,
            turnover=1000,
            recv_index=1,
        ),
        TickRecord(
            symbol="000001.SZ",
            trading_day="20221110",
            timestamp=1668043815000,
            price=11.0,
            volume=50,
            turnover=550,
            recv_index=2,
        ),
        TickRecord(
            symbol="000001.SZ",
            trading_day="20221110",
            timestamp=1668043865000,
            price=9.0,
            volume=30,
            turnover=270,
            recv_index=3,
        ),
    ]

    bars = list(aggregator.aggregate(rows, "1m"))

    assert len(bars) == 2

    first_bar = bars[0]
    assert first_bar.symbol == "000001.SZ"
    assert first_bar.interval == "1m"
    assert first_bar.trading_day == "20221110"
    assert first_bar.open_price == 10.0
    assert first_bar.high_price == 11.0
    assert first_bar.low_price == 10.0
    assert first_bar.close_price == 11.0
    assert first_bar.volume == 150.0
    assert first_bar.amount == 1550.0
    assert first_bar.start_time == "09:30:00"
    assert first_bar.end_time == "09:31:00"

    second_bar = bars[1]
    assert second_bar.open_price == 9.0
    assert second_bar.high_price == 9.0
    assert second_bar.low_price == 9.0
    assert second_bar.close_price == 9.0
    assert second_bar.volume == 30.0
    assert second_bar.amount == 270.0
    assert second_bar.start_time == "09:31:00"
    assert second_bar.end_time == "09:32:00"
