from configparser import ConfigParser
from pathlib import Path

from ..core.models import TaskConfig


class ConfigLoader:
    def __init__(self) -> None:
        """Initialize the parser used for loading task config files."""
        self.parser = ConfigParser()

    def load(
        self,
        config_path: str | Path = "config.ini",
    ) -> TaskConfig:
        """Load config values and override the default TaskConfig fields."""
        self.parser.clear()
        self.parser.read(Path(config_path), encoding="utf-8")

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
                config.output_format = runtime["output_format"]

        return config
