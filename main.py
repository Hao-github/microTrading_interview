from itertools import islice
from pathlib import Path

from src.kline.aggregator import KlineAggregator
from src.kline.checkpoint import CheckpointManager
from src.kline.config_loader import ConfigLoader
from src.kline.logger import get_logger
from src.kline.reader import CSVReader
from src.kline.writer import KlineWriter


def build_pipeline(config_path: str = "config.ini") -> dict:
    """Create project components and return them as a simple container."""
    config_loader = ConfigLoader(config_path)
    reader = CSVReader()
    # aggregator = KlineAggregator()
    # writer = KlineWriter()
    # checkpoint_manager = CheckpointManager()
    # logger = get_logger("kline")
    return {
        "config_loader": config_loader,
        "reader": reader,
        # "aggregator": aggregator,
        # "writer": writer,
        # "checkpoint_manager": checkpoint_manager,
        # "logger": logger,
    }


def main() -> None:
    """CLI entry point."""
    pipeline = build_pipeline()
    config = pipeline["config_loader"].load()
    reader = pipeline["reader"]

    csv_files = sorted(Path(config.input_dir).glob("*.csv"))
    if not csv_files:
        print("No CSV files found.")
        return

    for row in islice(reader.read(csv_files[0]), 10):
        print(row)


if __name__ == "__main__":
    main()
