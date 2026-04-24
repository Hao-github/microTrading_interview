from dataclasses import dataclass, field
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


@dataclass
class TaskConfig:
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    log_dir: Path = Path("logs")
    checkpoint_dir: Path = Path("checkpoints")
    intervals: list[str] = field(default_factory=lambda: ["1m", "5m", "10m", "30m"])
    output_format: str = "csv"
