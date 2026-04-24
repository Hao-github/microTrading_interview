from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TickRecord:
    symbol: str = ""
    trading_day: str = ""
    timestamp: int = 0
    price: float = 0.0
    volume: int = 0
    turnover: int = 0
    recv_index: int = 0

    @classmethod
    def from_csv_fields(
        cls,
        *,
        symbol: str,
        trading_day: str,
        time_value: str,
        price: str,
        volume: str,
        turnover: str,
        recv_index: str,
    ) -> "TickRecord":
        time_value = time_value.zfill(9)
        dt = datetime.strptime(f"{trading_day}{time_value}", "%Y%m%d%H%M%S%f")
        return cls(
            symbol=symbol,
            trading_day=trading_day,
            timestamp=int(dt.timestamp() * 1000),
            price=float(price) if price else 0.0,
            volume=int(volume) if volume else 0,
            turnover=int(turnover) if turnover else 0,
            recv_index=int(recv_index) if recv_index else 0,
        )


@dataclass
class KlineBar:
    symbol: str = ""
    interval: str = ""
    trading_day: str = ""
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    start_time: str = ""
    end_time: str = ""

    def update_from_tick(self, row: TickRecord) -> None:
        self.high_price = max(self.high_price, row.price)
        self.low_price = min(self.low_price, row.price)
        self.close_price = row.price
        self.volume += float(row.volume)
        self.amount += float(row.turnover)


@dataclass
class TaskConfig:
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    log_dir: Path = Path("logs")
    checkpoint_dir: Path = Path("checkpoints")
    intervals: list[str] = field(default_factory=lambda: ["1m", "5m", "10m", "30m"])
    output_format: str = "csv"
