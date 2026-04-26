from kline import ConfigLoader, CSVReader, KlineAggregator, KlineWriter


def main() -> None:
    """CLI entry point."""
    config_loader = ConfigLoader()
    config = config_loader.load()

    reader = CSVReader(config)
    aggregator = KlineAggregator(config)
    writer = KlineWriter(config)

    ticks = reader.read(config.input_file_path)
    bars = aggregator.aggregate(ticks, config.intervals)
    writer.write_stream(bars)


if __name__ == "__main__":
    main()
