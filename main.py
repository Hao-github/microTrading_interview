from src.kline.aggregator import KlineAggregator
from src.kline.checkpoint import CheckpointManager
from src.kline.config_loader import ConfigLoader
from src.kline.logger import get_logger
from src.kline.preprocessor import TickPreprocessor
from src.kline.reader import CSVReader
from src.kline.writer import KlineWriter


def build_pipeline(config_path: str = "config.ini") -> dict:
    """Create project components and return them as a simple container."""
    config_loader = ConfigLoader(config_path)
    reader = CSVReader()
    preprocessor = TickPreprocessor()
    aggregator = KlineAggregator()
    writer = KlineWriter()
    checkpoint_manager = CheckpointManager()
    logger = get_logger("kline")

    return {
        "config_loader": config_loader,
        "reader": reader,
        "preprocessor": preprocessor,
        "aggregator": aggregator,
        "writer": writer,
        "checkpoint_manager": checkpoint_manager,
        "logger": logger,
    }


def main() -> None:
    """CLI entry point."""
    build_pipeline()
    pass


if __name__ == "__main__":
    main()
