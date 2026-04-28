from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
_CHINA_TZ_OFFSET_SECONDS = 8 * 60 * 60
_MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000


@lru_cache(maxsize=32)
def _trading_day_base_timestamp_ms(trading_day: str) -> int:
    """Convert a trading day string into its local-midnight UTC timestamp.

    Args:
        trading_day: Trading day in ``YYYYMMDD`` format.

    Returns:
        Midnight timestamp in milliseconds for the trading day under China timezone.
    """
    if len(trading_day) != 8 or not trading_day.isdigit():
        raise ValueError(f"invalid trading_day: {trading_day}")

    epoch_day = (
        date(
            int(trading_day[0:4]),
            int(trading_day[4:6]),
            int(trading_day[6:8]),
        ).toordinal()
        - _EPOCH_ORDINAL
    )
    return (epoch_day * 24 * 60 * 60 - _CHINA_TZ_OFFSET_SECONDS) * 1000


def _parse_timestamp_ms(trading_day: str, time_value: str) -> int:
    """Build a tick timestamp from trading day and intra-day time text.

    Args:
        trading_day: Trading day in ``YYYYMMDD`` format.
        time_value: Time text in ``HHMMSSmmm`` format, allowing left padding.

    Returns:
        Tick timestamp in milliseconds.
    """
    time_text = time_value.zfill(9)
    if len(time_text) != 9 or not time_text.isdigit():
        raise ValueError(f"invalid time_value: {time_value}")

    time_offset_ms = (
        int(time_text[0:2]) * 60 * 60 * 1000
        + int(time_text[2:4]) * 60 * 1000
        + int(time_text[4:6]) * 1000
        + int(time_text[6:9])
    )
    return _trading_day_base_timestamp_ms(trading_day) + time_offset_ms


def _format_time_text(timestamp_ms: int) -> str:
    local_ms = timestamp_ms + _CHINA_TZ_OFFSET_SECONDS * 1000
    time_of_day_ms = local_ms % _MILLISECONDS_PER_DAY

    hours = time_of_day_ms // (60 * 60 * 1000)
    minutes = (time_of_day_ms // (60 * 1000)) % 60
    seconds = (time_of_day_ms // 1000) % 60
    milliseconds = time_of_day_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


@dataclass(slots=True)
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
        recv_index: int,
    ) -> "TickRecord":
        """Create a tick record from raw CSV field strings.

        Args:
            symbol: Security symbol.
            trading_day: Trading day in ``YYYYMMDD`` format.
            time_value: Tick time text from the CSV row.
            price: Price field text.
            volume: Volume field text.
            turnover: Turnover field text.
            recv_index: Receive order index from the source file.

        Returns:
            A parsed ``TickRecord`` instance.
        """
        return cls(
            symbol=symbol,
            trading_day=trading_day,
            timestamp=_parse_timestamp_ms(trading_day, time_value),
            price=float(price) if price else 0.0,
            volume=int(volume) if volume else 0,
            turnover=int(turnover) if turnover else 0,
            recv_index=recv_index,
        )


@dataclass(slots=True)
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
    bucket_start_timestamp: int = 0
    bucket_end_timestamp: int = 0
    first_tick_timestamp: int = 0
    last_tick_timestamp: int = 0

    @classmethod
    def csv_fieldnames(cls) -> list[str]:
        """Return CSV column names for serialized K-line bars.

        Args:
            None.

        Returns:
            Field names in output CSV order.
        """
        return [
            "symbol",
            "interval",
            "trading_day",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "amount",
            "bucket_start_timestamp",
            "bucket_end_timestamp",
            "bucket_start_time",
            "bucket_end_time",
        ]

    @classmethod
    def from_tick(
        cls,
        row: TickRecord,
        interval: str,
        timestamp_bucket: tuple[int, int],
    ) -> "KlineBar":
        """Create a new K-line bar initialized from a single tick.

        Args:
            row: Source tick record.
            interval: Interval label such as ``"1m"``.
            timestamp_bucket: Bucket range as ``(start_timestamp, end_timestamp)``.

        Returns:
            A new ``KlineBar`` seeded from the tick.
        """
        return cls(
            symbol=row.symbol,
            interval=interval,
            trading_day=row.trading_day,
            open_price=row.price,
            high_price=row.price,
            low_price=row.price,
            close_price=row.price,
            volume=float(row.volume),
            amount=float(row.turnover),
            bucket_start_timestamp=timestamp_bucket[0],
            bucket_end_timestamp=timestamp_bucket[1],
            first_tick_timestamp=row.timestamp,
            last_tick_timestamp=row.timestamp,
        )

    def update_from_tick(self, row: TickRecord) -> None:
        """Merge a tick into the current K-line bar.

        Args:
            row: Tick record belonging to the same bar bucket.

        Returns:
            ``None``.
        """
        if row.timestamp < self.first_tick_timestamp:
            self.open_price = row.price
            self.first_tick_timestamp = row.timestamp

        if row.timestamp >= self.last_tick_timestamp:
            self.close_price = row.price
            self.last_tick_timestamp = row.timestamp

        self.high_price = max(self.high_price, row.price)
        self.low_price = min(self.low_price, row.price)
        self.volume += float(row.volume)
        self.amount += float(row.turnover)

    def to_checkpoint_dict(self) -> dict[str, str | int | float]:
        """Convert the bar into a dictionary suitable for checkpoints.

        Args:
            None.

        Returns:
            A field-name to field-value mapping for the bar.
        """
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "trading_day": self.trading_day,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "amount": self.amount,
            "bucket_start_timestamp": self.bucket_start_timestamp,
            "bucket_end_timestamp": self.bucket_end_timestamp,
            "first_tick_timestamp": self.first_tick_timestamp,
            "last_tick_timestamp": self.last_tick_timestamp,
        }

    def to_csv_values(self) -> list[str | int | float]:
        """Convert the bar into a positional CSV row.

        Args:
            None.

        Returns:
            Field values ordered to match ``csv_fieldnames()``.
        """
        return [
            self.symbol,
            self.interval,
            self.trading_day,
            self.open_price,
            self.high_price,
            self.low_price,
            self.close_price,
            self.volume,
            self.amount,
            self.bucket_start_timestamp,
            self.bucket_end_timestamp,
            _format_time_text(self.bucket_start_timestamp),
            _format_time_text(self.bucket_end_timestamp),
        ]

    @classmethod
    def from_dict(cls, payload: dict[str, str | int | float]) -> "KlineBar":
        """Restore a bar from serialized dictionary data.

        Args:
            payload: Serialized bar dictionary.

        Returns:
            A restored ``KlineBar`` instance.
        """
        return cls(
            symbol=str(payload["symbol"]),
            interval=str(payload["interval"]),
            trading_day=str(payload["trading_day"]),
            open_price=float(payload["open_price"]),
            high_price=float(payload["high_price"]),
            low_price=float(payload["low_price"]),
            close_price=float(payload["close_price"]),
            volume=float(payload["volume"]),
            amount=float(payload["amount"]),
            bucket_start_timestamp=int(payload["bucket_start_timestamp"]),
            bucket_end_timestamp=int(payload["bucket_end_timestamp"]),
            first_tick_timestamp=int(payload["first_tick_timestamp"]),
            last_tick_timestamp=int(payload["last_tick_timestamp"]),
        )


@dataclass(slots=True)
class TaskConfig:
    input_file_path: Path = Path("data/input/md_20221110.csv")
    output_dir: Path = Path("data/output")
    log_dir: Path = Path("logs")
    checkpoint_dir: Path = Path("checkpoints")
    intervals: list[str] = field(default_factory=lambda: ["1m", "5m", "10m", "30m"])
    output_format: str = "csv"
    checkpoint_interval: int = 1000000
