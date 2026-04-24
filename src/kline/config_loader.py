from configparser import ConfigParser
from pathlib import Path

from .models import TaskConfig


class ConfigLoader:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.parser = ConfigParser()

    def load(self) -> TaskConfig:
        pass
