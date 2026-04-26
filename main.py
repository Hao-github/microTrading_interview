from src.kline import ConfigLoader, CSVReader, KlineAggregator, KlineWriter


def main() -> None:
    """CLI entry point."""
    config_loader = ConfigLoader()
    config = config_loader.load(
        input_file_path="data/sample_input/md_20221110_head_1000000.csv"
    )
    reader = CSVReader()
    aggregator = KlineAggregator()
    writer = KlineWriter(config)

    ticks = reader.read(config.input_file_path)
    bars = aggregator.aggregate(ticks, config.intervals)
    writer.write_stream(bars)


if __name__ == "__main__":
    main()
