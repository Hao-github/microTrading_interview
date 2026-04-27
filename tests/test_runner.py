import shutil
import uuid
from pathlib import Path

from kline import AggregationRunner, CheckpointManager, CSVReader, KlineWriter
from kline.core.models import TaskConfig


def _make_temp_root() -> Path:
    temp_root = Path(".tmp/runner-tests")
    temp_root.mkdir(parents=True, exist_ok=True)
    root = temp_root / f"runner-{uuid.uuid4().hex}"
    root.mkdir()
    return root


def _make_config(root: Path, checkpoint_interval: int = 10) -> TaskConfig:
    config = TaskConfig(
        input_file_path=Path("tests/sample_ticks_100.csv"),
        output_dir=root / "out",
        log_dir=root / "logs",
        checkpoint_dir=root / "ckpt",
        intervals=["1m"],
        output_format="csv",
        checkpoint_interval=checkpoint_interval,
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return config


def test_runner_generates_commit_id_named_segments_and_clears_checkpoints() -> None:
    root = _make_temp_root()
    config = _make_config(root)

    try:
        runner = AggregationRunner(
            config=config,
            reader=CSVReader(config),
            writer=KlineWriter(config),
            checkpoint_manager=CheckpointManager(config),
        )

        runner.run()

        output_names = sorted(path.name for path in config.output_dir.glob("*.csv"))
        checkpoint_names = sorted(
            path.name for path in config.checkpoint_dir.glob("*.pkl")
        )

        assert output_names[0] == (
            "kline_1m_for_sample_ticks_100_part_00000000000000000001_batch.csv"
        )
        assert output_names[-1] == (
            "kline_1m_for_sample_ticks_100_part_00000000000000000011_final.csv"
        )
        assert checkpoint_names == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_runner_cleanup_removes_future_segments_by_commit_id() -> None:
    root = _make_temp_root()
    config = _make_config(root)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        kept = (
            config.output_dir
            / "kline_1m_for_sample_ticks_100_part_00000000000000000001_batch.csv"
        )
        removed = (
            config.output_dir
            / "kline_1m_for_sample_ticks_100_part_00000000000000000002_batch.csv"
        )
        tmp_file = (
            config.output_dir / "kline_1m_for_sample_ticks_100_current.csv.tmp"
        )
        kept.write_text("kept", encoding="utf-8")
        removed.write_text("removed", encoding="utf-8")
        tmp_file.write_text("tmp", encoding="utf-8")

        writer = KlineWriter(config)
        writer.cleanup_outputs_after(commit_id=1)

        assert kept.exists()
        assert not removed.exists()
        assert not tmp_file.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
