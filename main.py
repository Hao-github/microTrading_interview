from kline import (
    AggregationRunner,
    CheckpointManager,
    ConfigLoader,
    CSVReader,
    KlineWriter,
)


def main() -> None:
    """CLI entry point."""
    config_loader = ConfigLoader()
    config = config_loader.load()

    runner = AggregationRunner(
        config=config,
        reader=CSVReader(config),
        writer=KlineWriter(config),
        checkpoint_manager=CheckpointManager(config),
    )
    runner.run()


if __name__ == "__main__":
    main()
