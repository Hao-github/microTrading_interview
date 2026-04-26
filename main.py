from kline import (
    CheckpointManager,
    ConfigLoader,
    CSVReader,
    KlineAggregator,
    KlineWriter,
)


def main() -> None:
    """CLI entry point."""
    config_loader = ConfigLoader()
    config = config_loader.load()

    reader = CSVReader(config)
    checkpoint_manager = CheckpointManager(config.checkpoint_dir)
    start_offset, initial_states = checkpoint_manager.restore_latest()

    aggregator = KlineAggregator(config=config, initial_states=initial_states)
    rows = reader.read(config.input_file_path, start_offset=start_offset)

    def rows_with_checkpoints():
        processed_count = 0
        for row in rows:
            yield row
            processed_count += 1

            if (
                config.checkpoint_interval > 0
                and processed_count % config.checkpoint_interval == 0
            ):
                checkpoint_manager.save_snapshot(
                    offset=row.recv_index,
                    interval_states=aggregator.interval_states,
                )

    bars = aggregator.aggregate(rows_with_checkpoints(), config.intervals)

    writer = KlineWriter(config)
    writer.write_stream(bars)
    checkpoint_manager.clear_latest()


if __name__ == "__main__":
    main()
