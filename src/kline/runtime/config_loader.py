from configparser import ConfigParser
from pathlib import Path

from ..core.models import TaskConfig

SUPPORTED_OUTPUT_FORMATS = {"csv", "parquet"}
SUPPORTED_INTERVAL_UNITS = ("m", "min", "h", "s")


class ConfigLoader:
    def __init__(self) -> None:
        """Initialize the parser used for loading task config files."""
        self.parser = ConfigParser()

    def load(self, config_path: str | Path = "config.ini") -> TaskConfig:
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

        self.validate(config)
        return config

    def validate(self, config: TaskConfig) -> None:
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
