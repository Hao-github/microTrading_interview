from kline import (
    AggregationRunner,
    CheckpointManager,
    ConfigLoader,
    CSVReader,
    KlineWriter,
)


def main() -> None:
    """Run the K-line aggregation task from the default project config.

    Args:
        None.

    Returns:
        ``None``. Aggregated outputs are written to ``paths.output_dir``,
        and checkpoint files are written to ``paths.checkpoint_dir``.
    """
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
