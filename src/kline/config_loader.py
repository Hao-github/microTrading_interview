from configparser import ConfigParser
from pathlib import Path

from .models import TaskConfig


class ConfigLoader:
    def __init__(self, config_path: str | Path | None = "config.ini") -> None:
        """Store the config file path and initialize the parser."""
        if config_path is None:
            self.config_path = Path("config.ini")
        else:
            self.config_path = Path(config_path)
        self.parser = ConfigParser()

    def load(self) -> TaskConfig:
        """Load config values and override the default TaskConfig fields."""
        self.parser.clear()
        self.parser.read(self.config_path, encoding="utf-8")

        config = TaskConfig()

        if self.parser.has_section("paths"):
            paths = self.parser["paths"]
            for field_name in ("input_dir", "output_dir", "log_dir", "checkpoint_dir"):
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
