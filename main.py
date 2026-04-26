from itertools import islice

from src.kline import (
    CSVReader,
    CheckpointManager,
    ConfigLoader,
    KlineAggregator,
    KlineWriter,
)


def build_pipeline(config_path: str = "config.ini") -> dict:
    """Create project components and return them as a simple container."""
    config_loader = ConfigLoader()
    reader = CSVReader()
    # aggregator = KlineAggregator()
    # writer = KlineWriter()
    # checkpoint_manager = CheckpointManager()
    # logger = get_logger("kline")
    return {
        "config_loader": config_loader,
        "config_path": config_path,
        "input_file_path": "data/input/md_20221110_head_1000000.csv",
        "reader": reader,
        # "aggregator": aggregator,
        # "writer": writer,
        # "checkpoint_manager": checkpoint_manager,
        # "logger": logger,
    }


def main() -> None:
    """CLI entry point."""
    pipeline = build_pipeline()
    config = pipeline["config_loader"].load(
        pipeline["config_path"],
        input_file_path=pipeline["input_file_path"],
    )
    reader = pipeline["reader"]

    for row in islice(reader.read(config.input_file_path), 10):
        print(row)


if __name__ == "__main__":
    main()
