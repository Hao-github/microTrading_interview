import argparse

from kline import (
    AggregationRunner,
    CheckpointManager,
    ConfigLoader,
    CSVReader,
    KlineWriter,
)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the K-line aggregation task.")
    parser.add_argument("--config", default="config.ini", help="Path to config file.")
    parser.add_argument("--input-file-path", help="Override paths.input_file_path.")
    parser.add_argument("--output-dir", help="Override paths.output_dir.")
    parser.add_argument("--log-dir", help="Override paths.log_dir.")
    parser.add_argument("--checkpoint-dir", help="Override paths.checkpoint_dir.")
    parser.add_argument(
        "--intervals",
        help="Override runtime.intervals, for example: 1m,5m,10m,30m",
    )
    parser.add_argument(
        "--output-format",
        help="Override runtime.output_format.",
    )
    parser.add_argument(
        "--checkpoint-interval",
        help="Override runtime.checkpoint_interval, for example: 1000000 or 100w",
    )
    return parser


def main() -> None:
    """Run the K-line aggregation task from the default project config.

    Args:
        None.

    Returns:
        ``None``. Aggregated outputs are written to ``paths.output_dir``,
        and checkpoint files are written to ``paths.checkpoint_dir``.
    """
    args = _build_argument_parser().parse_args()
    config_loader = ConfigLoader()
    config = config_loader.load(
        args.config,
        input_file_path=args.input_file_path,
        output_dir=args.output_dir,
        log_dir=args.log_dir,
        checkpoint_dir=args.checkpoint_dir,
        intervals=args.intervals,
        output_format=args.output_format,
        checkpoint_interval=args.checkpoint_interval,
    )

    runner = AggregationRunner(
        config=config,
        reader=CSVReader(config),
        writer=KlineWriter(config),
        checkpoint_manager=CheckpointManager(config),
    )
    runner.run()


if __name__ == "__main__":
    main()
