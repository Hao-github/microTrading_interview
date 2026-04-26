from src.kline import ConfigLoader, CSVReader, KlineAggregator, KlineWriter
from src.kline.runtime import get_logger


def main() -> None:
    """CLI entry point."""
    config_loader = ConfigLoader()
    config = config_loader.load()

    reader = CSVReader(logger=get_logger("kline.reader", config.log_dir))
    aggregator = KlineAggregator(
        logger=get_logger("kline.aggregator", config.log_dir)
    )
    writer = KlineWriter(config, logger=get_logger("kline.writer", config.log_dir))

    ticks = reader.read(config.input_file_path)
    bars = aggregator.aggregate(ticks, config.intervals)
    writer.write_stream(bars)


if __name__ == "__main__":
    main()
