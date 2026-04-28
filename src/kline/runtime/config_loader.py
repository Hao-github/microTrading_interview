from configparser import ConfigParser
from pathlib import Path

from kline.core.models import TaskConfig

SUPPORTED_OUTPUT_FORMATS = {"csv"}
SUPPORTED_INTERVAL_UNITS = ("m", "min", "h", "s")


class ConfigLoader:
    def __init__(self) -> None:
        """Initialize the parser used for loading task config files."""
        self.parser = ConfigParser()

    def load(self, config_path: str | Path = "config.ini", **overrides) -> TaskConfig:
        """Load task configuration from an INI file.

        Args:
            config_path: Path to the configuration file.
            validate: Whether to validate the loaded config before returning.
            **overrides: Optional config field overrides applied after file load.

        Returns:
            A validated ``TaskConfig`` instance.
        """
        self.parser.clear()

        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        self.parser.read(config_path, encoding="utf-8")

        config = TaskConfig()

        if self.parser.has_section("paths"):
            paths = self.parser["paths"]
            for field_name in (
                "input_file_path",
                "output_dir",
                "log_dir",
                "checkpoint_dir",
            ):
                if paths.get(field_name):
                    setattr(config, field_name, Path(paths[field_name]))

        if self.parser.has_section("runtime"):
            runtime = self.parser["runtime"]
            if runtime.get("intervals"):
                config.intervals = [
                    item.strip()
                    for item in runtime["intervals"].split(",")
                    if item.strip()
                ]
            if runtime.get("output_format"):
                config.output_format = runtime["output_format"].strip().lower()
            if runtime.get("checkpoint_interval"):
                config.checkpoint_interval = self._parse_checkpoint_interval(
                    runtime["checkpoint_interval"]
                )

        self._apply_overrides(config, overrides)

        self.validate(config)
        return config

    def _apply_overrides(self, config: TaskConfig, overrides: dict) -> None:
        for field_name in (
            "input_file_path",
            "output_dir",
            "log_dir",
            "checkpoint_dir",
        ):
            if (value := overrides.get(field_name)) is not None:
                setattr(config, field_name, Path(value))

        if (intervals := overrides.get("intervals")) is not None:
            if isinstance(intervals, str):
                config.intervals = [
                    item.strip() for item in intervals.split(",") if item.strip()
                ]
            else:
                config.intervals = [
                    str(item).strip() for item in intervals if str(item).strip()
                ]

        if (output_format := overrides.get("output_format")) is not None:
            config.output_format = str(output_format).strip().lower()

        if (checkpoint_interval := overrides.get("checkpoint_interval")) is not None:
            config.checkpoint_interval = self._parse_checkpoint_interval(
                str(checkpoint_interval)
            )

    def validate(self, config: TaskConfig) -> None:
        """Validate config values and ensure required directories exist.

        Args:
            config: Task configuration to validate.

        Returns:
            ``None``.
        """
        if not config.input_file_path.exists():
            raise FileNotFoundError(f"Input file not found: {config.input_file_path}")

        if not config.intervals:
            raise ValueError("runtime.intervals cannot be empty")

        for interval in config.intervals:
            if not self._is_valid_minute_interval(interval):
                raise ValueError(
                    f"Invalid interval: {interval}. "
                    "Only minute intervals are supported, e.g. 1m, 5m, 10m, 30m."
                )

        if config.output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"Unsupported output_format: {config.output_format}. "
                f"Supported: {sorted(SUPPORTED_OUTPUT_FORMATS)}"
            )

        if config.checkpoint_interval < 0:
            raise ValueError("runtime.checkpoint_interval must be >= 0")

        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.log_dir.mkdir(parents=True, exist_ok=True)
        config.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_valid_minute_interval(interval: str) -> bool:
        interval = interval.strip().lower()

        if not interval.endswith("m"):
            return False

        number = interval[:-1]
        return number.isdigit() and int(number) > 0

    @staticmethod
    def _parse_checkpoint_interval(value: str) -> int:
        normalized = value.strip().lower()
        if not normalized:
            return 0

        if normalized.endswith("w"):
            number = normalized[:-1]
            if number.isdigit():
                return int(number) * 10_000

        if normalized.isdigit():
            return int(normalized)

        raise ValueError(
            "Invalid checkpoint_interval. Use a non-negative integer or values "
            "like 100w."
        )
